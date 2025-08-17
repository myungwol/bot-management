# utils/database.py

import os
import discord
from supabase import create_client, AsyncClient
import logging
import asyncio
from typing import Dict, Callable, Any, List
from functools import wraps
from datetime import datetime, timezone

from .ui_defaults import UI_EMBEDS, UI_PANEL_COMPONENTS, UI_ROLE_KEY_MAP, SETUP_COMMAND_MAP

logger = logging.getLogger(__name__)

# --- 캐시 영역 ---
_bot_configs_cache: Dict[str, Any] = {}
_channel_id_cache: Dict[str, int] = {}

# --- Supabase 클라이언트 초기화 ---
supabase: AsyncClient = None
try:
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise ValueError("SUPABASE_URL 또는 SUPABASE_KEY 환경 변수가 설정되지 않았습니다.")
    supabase = AsyncClient(supabase_url=url, supabase_key=key)
    logger.info("✅ Supabase 비동기 클라이언트가 성공적으로 생성되었습니다.")
except Exception as e:
    logger.critical(f"❌ Supabase 클라이언트 생성 실패: {e}", exc_info=True)

# --- 범용 재시도 핸들러 ---
def supabase_retry_handler(retries: int = 3, delay: int = 5):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not supabase:
                logger.error(f"❌ Supabase 클라이언트가 없어 '{func.__name__}' 함수를 실행할 수 없습니다.")
                return_type = func.__annotations__.get("return")
                if return_type:
                    if "dict" in str(return_type).lower(): return {}
                    if "list" in str(return_type).lower(): return []
                return None
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"⚠️ '{func.__name__}' 함수 실행 중 오류 발생 (시도 {attempt + 1}/{retries}): {e}")
                    if attempt < retries - 1:
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"❌ '{func.__name__}' 함수가 모든 재시도({retries}번)에 실패했습니다.", exc_info=True)
                        return_type = func.__annotations__.get("return")
                        if return_type:
                            if "dict" in str(return_type).lower(): return {}
                            if "list" in str(return_type).lower(): return []
                        return None
        return wrapper
    return decorator

@supabase_retry_handler()
async def save_config_to_db(key: str, value: Any):
    await supabase.table('bot_configs').upsert({"config_key": key, "config_value": value}).execute()

async def sync_defaults_to_db():
    logger.info("------ [ 기본값 DB 동기화 시작 ] ------")
    try:
        role_name_map = {key: info["name"] for key, info in UI_ROLE_KEY_MAP.items()}
        await save_config_to_db("ROLE_KEY_MAP", role_name_map)
        logger.info(f"✅ 역할 이름 맵(ROLE_KEY_MAP)을 DB에 동기화했습니다.")
        prefix_hierarchy = sorted(
            [info["name"] for info in UI_ROLE_KEY_MAP.values() if info.get("is_prefix")],
            key=lambda name: next((info.get("priority", 0) for info in UI_ROLE_KEY_MAP.values() if info["name"] == name), 0),
            reverse=True
        )
        await save_config_to_db("NICKNAME_PREFIX_HIERARCHY", prefix_hierarchy)
        logger.info(f"✅ 닉네임 접두사 목록(NICKNAME_PREFIX_HIERARCHY)을 DB에 동기화했습니다.")
        for key, data in UI_EMBEDS.items():
            await save_embed_to_db(key, data)
        logger.info(f"✅ {len(UI_EMBEDS)}개의 임베드 기본값을 DB에 동기화했습니다.")
        for component_data in UI_PANEL_COMPONENTS:
            await save_panel_component_to_db(component_data)
        logger.info(f"✅ {len(UI_PANEL_COMPONENTS)}개의 패널 컴포넌트 기본값을 DB에 동기화했습니다.")
        await save_config_to_db("SETUP_COMMAND_MAP", SETUP_COMMAND_MAP)
        logger.info(f"✅ /setup 명령어 설정 맵(SETUP_COMMAND_MAP)을 DB에 동기화했습니다.")
    except Exception as e:
        logger.error(f"❌ 기본값 DB 동기화 중 오류 발생: {e}", exc_info=True)
    logger.info("------ [ 기본값 DB 동기화 완료 ] ------")

async def load_all_data_from_db():
    logger.info("------ [ 모든 DB 데이터 로드 시작 ] ------")
    await asyncio.gather(load_bot_configs_from_db(), load_channel_ids_from_db())
    logger.info("------ [ 모든 DB 데이터 로드 완료 ] ------")

@supabase_retry_handler()
async def load_bot_configs_from_db():
    global _bot_configs_cache
    response = await supabase.table('bot_configs').select('config_key, config_value').execute()
    if response.data:
        _bot_configs_cache = {item['config_key']: item['config_value'] for item in response.data}
        logger.info(f"✅ {len(_bot_configs_cache)}개의 봇 설정을 DB에서 로드했습니다.")
    else:
        logger.warning("DB 'bot_configs' 테이블에서 설정 정보를 찾을 수 없습니다.")

def get_config(key: str, default: Any = None) -> Any:
    value = _bot_configs_cache.get(key)
    if value is None:
        logger.warning(f"[Config Cache Miss] '{key}'에 해당하는 설정을 캐시에서 찾을 수 없습니다. 기본값을 사용합니다.")
        return default
    return value

@supabase_retry_handler()
async def load_channel_ids_from_db():
    global _channel_id_cache
    response = await supabase.table('channel_configs').select('channel_key, channel_id').execute()
    if response.data:
        _channel_id_cache = {item['channel_key']: int(item['channel_id']) for item in response.data}
        logger.info(f"✅ {len(_channel_id_cache)}개의 채널/역할 ID를 DB에서 로드했습니다.")
    else:
        logger.warning("DB 'channel_configs' 테이블에서 ID 정보를 찾을 수 없습니다.")

def get_id(key: str) -> int | None:
    config_id = _channel_id_cache.get(key)
    if config_id is None:
        logger.warning(f"[ID Cache Miss] '{key}'에 해당하는 ID를 캐시에서 찾을 수 없습니다.")
    return config_id

@supabase_retry_handler()
async def save_id_to_db(key: str, object_id: int):
    global _channel_id_cache
    await supabase.table('channel_configs').upsert({"channel_key": key, "channel_id": str(object_id)}, on_conflict="channel_key").execute()
    _channel_id_cache[key] = object_id
    logger.info(f"✅ '{key}' ID({object_id})를 DB와 캐시에 저장했습니다.")

async def save_panel_id(panel_name: str, message_id: int, channel_id: int):
    await save_id_to_db(f"panel_{panel_name}_message_id", message_id)
    await save_id_to_db(f"panel_{panel_name}_channel_id", channel_id)

def get_panel_id(panel_name: str) -> dict | None:
    message_id = get_id(f"panel_{panel_name}_message_id")
    channel_id = get_id(f"panel_{panel_name}_channel_id")
    return {"message_id": message_id, "channel_id": channel_id} if message_id and channel_id else None

@supabase_retry_handler()
async def save_embed_to_db(embed_key: str, embed_data: dict):
    await supabase.table('embeds').upsert({'embed_key': embed_key, 'embed_data': embed_data}, on_conflict='embed_key').execute()

@supabase_retry_handler()
async def get_embed_from_db(embed_key: str) -> dict | None:
    response = await supabase.table('embeds').select('embed_data').eq('embed_key', embed_key).limit(1).execute()
    return response.data[0]['embed_data'] if response.data else None

@supabase_retry_handler()
async def get_panel_components_from_db(panel_key: str) -> list:
    response = await supabase.table('panel_components').select('*').eq('panel_key', panel_key).order('row', desc=False).execute()
    return response.data if response.data else []

@supabase_retry_handler()
async def save_panel_component_to_db(component_data: dict):
    await supabase.table('panel_components').upsert(component_data, on_conflict='component_key').execute()

@supabase_retry_handler()
async def get_onboarding_steps() -> list:
    response = await supabase.table('onboarding_steps').select('*, embed_data:embeds(embed_data)').order('step_number', desc=False).execute()
    return response.data if response.data else []


# ==============================================================================
# [수정된 쿨다운 함수]
# ==============================================================================

@supabase_retry_handler()
async def get_cooldown(user_id_str: str, cooldown_key: str) -> float:
    """
    데이터베이스에서 쿨다운 정보를 가져와 float 형식의 Unix 타임스탬프로 반환합니다.
    """
    response = await supabase.table('cooldowns').select('last_cooldown_timestamp').eq('user_id', user_id_str).eq('cooldown_key', cooldown_key).limit(1).execute()
    
    # 데이터가 있고, 'last_cooldown_timestamp' 값이 None이 아닌지 확인
    if response.data and response.data[0].get('last_cooldown_timestamp') is not None:
        try:
            # DB에서 온 값(숫자 타입)을 float으로 변환하여 반환
            return float(response.data[0]['last_cooldown_timestamp'])
        except (ValueError, TypeError):
            # 혹시라도 잘못된 타입의 데이터가 들어있을 경우 에러 로깅 후 0.0 반환
            logger.error(f"DB의 타임스탬프 값이 숫자가 아닙니다: {response.data[0]['last_cooldown_timestamp']}")
            return 0.0
            
    # 데이터가 없으면 0.0을 반환하여 쿨다운이 없음을 알림
    return 0.0

@supabase_retry_handler()
async def set_cooldown(user_id_str: str, cooldown_key: str):
    """
    현재 UTC 시간을 float 형식의 Unix 타임스탬프로 데이터베이스에 저장합니다.
    이 방식은 데이터베이스의 'real' 또는 'float' 타입과 호환됩니다.
    """
    # UTC 시간 기준의 float 형식 Unix 타임스탬프를 가져옵니다.
    utc_timestamp = datetime.now(timezone.utc).timestamp()
    
    data_to_upsert = {
        "user_id": user_id_str,
        "cooldown_key": cooldown_key,
        "last_cooldown_timestamp": utc_timestamp
    }
    
    await supabase.table('cooldowns').upsert(data_to_upsert, on_conflict='user_id,cooldown_key').execute()
