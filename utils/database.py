# bot-management/utils/database.py
"""
Supabase 데이터베이스와의 모든 상호작용을 관리하는 중앙 파일입니다.
- Supabase 클라이언트 초기화
- 데이터 CRUD(생성, 읽기, 업데이트, 삭제)를 위한 비동기 함수 제공
- 네트워크 오류에 대비한 재시도 로직 포함
- 봇 설정, 채널 ID, UI 데이터 등 모든 DB 관련 작업을 캡슐화합니다.
"""
import os
import asyncio
import logging
from typing import Dict, Callable, Any, List
from functools import wraps
from datetime import datetime, timezone

from supabase import create_client, AsyncClient
from postgrest.exceptions import APIError

# ui_defaults는 봇 시작 시 DB와 동기화할 기본값을 제공합니다.
from .ui_defaults import UI_EMBEDS, UI_PANEL_COMPONENTS, UI_ROLE_KEY_MAP, SETUP_COMMAND_MAP

logger = logging.getLogger(__name__)

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 1. 클라이언트 초기화 및 캐시
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

# Supabase 클라이언트 (비동기)
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
    supabase = None

# DB에서 읽어온 데이터를 저장하는 인-메모리 캐시
_bot_configs_cache: Dict[str, Any] = {}
_channel_id_cache: Dict[str, int] = {}


# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 2. DB 오류 처리 데코레이터
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

def supabase_retry_handler(retries: int = 3, delay: int = 2):
    """
    Supabase API 호출 중 발생하는 일시적 오류에 대해 재시도를 수행하는 데코레이터.
    최종 실패 시 None 또는 빈 객체를 반환하여 프로그램 중단을 방지합니다.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            if not supabase:
                logger.error(f"❌ Supabase 클라이언트가 초기화되지 않아 '{func.__name__}' 함수를 실행할 수 없습니다.")
                return None
            
            last_exception = None
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except APIError as e:
                    logger.warning(f"⚠️ '{func.__name__}' 함수 실행 중 Supabase API 오류 발생 (시도 {attempt + 1}/{retries}): {e.message}")
                    last_exception = e
                except Exception as e:
                    logger.warning(f"⚠️ '{func.__name__}' 함수 실행 중 예기치 않은 오류 발생 (시도 {attempt + 1}/{retries}): {e}")
                    last_exception = e
                
                if attempt < retries - 1:
                    await asyncio.sleep(delay * (attempt + 1)) # 재시도 간 딜레이 증가
            
            logger.error(f"❌ '{func.__name__}' 함수가 모든 재시도({retries}번)에 실패했습니다. 마지막 오류: {last_exception}", exc_info=True)
            
            # 반환 타입에 따라 적절한 기본값 반환
            return_type = func.__annotations__.get("return")
            if return_type:
                type_str = str(return_type).lower()
                if "dict" in type_str: return {}
                if "list" in type_str: return []
            return None
        return wrapper
    return decorator


# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 3. 데이터 로드 및 동기화 (봇 시작 시 호출)
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

async def sync_defaults_to_db():
    """ui_defaults.py에 정의된 기본값들을 DB에 동기화(upsert)합니다."""
    logger.info("------ [ 기본값 DB 동기화 시작 ] ------")
    try:
        # 역할 맵 동기화
        role_name_map = {key: info["name"] for key, info in UI_ROLE_KEY_MAP.items()}
        await save_config_to_db("ROLE_KEY_MAP", role_name_map)
        
        # 닉네임 접두사 우선순위 목록 동기화
        prefix_hierarchy = sorted(
            [info["name"] for info in UI_ROLE_KEY_MAP.values() if info.get("is_prefix")],
            key=lambda name: next((info.get("priority", 0) for info in UI_ROLE_KEY_MAP.values() if info["name"] == name), 0),
            reverse=True
        )
        await save_config_to_db("NICKNAME_PREFIX_HIERARCHY", prefix_hierarchy)
        
        # 임베드, 컴포넌트, 설정 맵 동기화
        await asyncio.gather(
            *[save_embed_to_db(key, data) for key, data in UI_EMBEDS.items()],
            *[save_panel_component_to_db(comp) for comp in UI_PANEL_COMPONENTS],
            save_config_to_db("SETUP_COMMAND_MAP", SETUP_COMMAND_MAP)
        )
        logger.info(f"✅ 역할, 닉네임, 임베드({len(UI_EMBEDS)}개), 컴포넌트({len(UI_PANEL_COMPONENTS)}개), 설정 맵 동기화 완료.")
    except Exception as e:
        logger.error(f"❌ 기본값 DB 동기화 중 치명적 오류 발생: {e}", exc_info=True)
    logger.info("------ [ 기본값 DB 동기화 완료 ] ------")

async def load_all_data_from_db():
    """DB의 모든 설정을 메모리 캐시로 로드합니다."""
    logger.info("------ [ 모든 DB 데이터 캐시 로드 시작 ] ------")
    await asyncio.gather(load_bot_configs_from_db(), load_channel_ids_from_db())
    logger.info("------ [ 모든 DB 데이터 캐시 로드 완료 ] ------")


# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 4. 설정 (bot_configs) 관련 함수
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

@supabase_retry_handler()
async def load_bot_configs_from_db():
    """'bot_configs' 테이블의 모든 데이터를 캐시에 로드합니다."""
    global _bot_configs_cache
    response = await supabase.table('bot_configs').select('config_key, config_value').execute()
    if response.data:
        _bot_configs_cache = {item['config_key']: item['config_value'] for item in response.data}
        logger.info(f"✅ {len(_bot_configs_cache)}개의 봇 설정을 DB에서 캐시로 로드했습니다.")

@supabase_retry_handler()
async def save_config_to_db(key: str, value: Any):
    """'bot_configs' 테이블에 특정 설정을 저장(upsert)하고 캐시를 업데이트합니다."""
    global _bot_configs_cache
    await supabase.table('bot_configs').upsert({"config_key": key, "config_value": value}).execute()
    _bot_configs_cache[key] = value

def get_config(key: str, default: Any = None) -> Any:
    """캐시에서 설정 값을 가져옵니다. 없으면 기본값을 반환합니다."""
    return _bot_configs_cache.get(key, default)


# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 5. ID (channel_configs) 관련 함수
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

@supabase_retry_handler()
async def load_channel_ids_from_db():
    """'channel_configs' 테이블의 모든 ID를 캐시에 로드합니다."""
    global _channel_id_cache
    response = await supabase.table('channel_configs').select('channel_key, channel_id').execute()
    if response.data:
        _channel_id_cache = {item['channel_key']: int(item['channel_id']) for item in response.data}
        logger.info(f"✅ {len(_channel_id_cache)}개의 채널/역할 ID를 DB에서 캐시로 로드했습니다.")

@supabase_retry_handler()
async def save_id_to_db(key: str, object_id: int):
    """'channel_configs' 테이블에 특정 ID를 저장(upsert)하고 캐시를 업데이트합니다."""
    global _channel_id_cache
    await supabase.table('channel_configs').upsert({"channel_key": key, "channel_id": str(object_id)}, on_conflict="channel_key").execute()
    _channel_id_cache[key] = object_id
    logger.info(f"✅ '{key}' ID({object_id})를 DB와 캐시에 저장했습니다.")

def get_id(key: str) -> Optional[int]:
    """캐시에서 채널/역할 ID를 가져옵니다."""
    config_id = _channel_id_cache.get(key)
    if config_id is None:
        logger.warning(f"[ID Cache Miss] '{key}'에 해당하는 ID를 캐시에서 찾을 수 없습니다.")
    return config_id

async def save_panel_id(panel_name: str, message_id: int, channel_id: int):
    """패널의 메시지 ID와 채널 ID를 DB에 저장합니다."""
    await save_id_to_db(f"panel_{panel_name}_message_id", message_id)
    await save_id_to_db(f"panel_{panel_name}_channel_id", channel_id)

def get_panel_id(panel_name: str) -> Optional[Dict[str, int]]:
    """패널의 메시지 ID와 채널 ID를 가져옵니다."""
    message_id = get_id(f"panel_{panel_name}_message_id")
    channel_id = get_id(f"panel_{panel_name}_channel_id")
    return {"message_id": message_id, "channel_id": channel_id} if message_id and channel_id else None


# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 6. 임베드 및 UI 컴포넌트 관련 함수
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

@supabase_retry_handler()
async def save_embed_to_db(embed_key: str, embed_data: dict):
    await supabase.table('embeds').upsert({'embed_key': embed_key, 'embed_data': embed_data}, on_conflict='embed_key').execute()

@supabase_retry_handler()
async def get_embed_from_db(embed_key: str) -> Optional[dict]:
    response = await supabase.table('embeds').select('embed_data').eq('embed_key', embed_key).limit(1).execute()
    return response.data[0]['embed_data'] if response.data else None

@supabase_retry_handler()
async def get_onboarding_steps(self) -> List[dict]:
    response = await supabase.table('onboarding_steps').select('*, embed_data:embeds(embed_data)').order('step_number', desc=False).execute()
    return response.data if response.data else []

@supabase_retry_handler()
async def save_panel_component_to_db(component_data: dict):
    await supabase.table('panel_components').upsert(component_data, on_conflict='component_key').execute()
    
@supabase_retry_handler()
async def get_panel_components_from_db(panel_key: str) -> List[dict]:
    response = await supabase.table('panel_components').select('*').eq('panel_key', panel_key).order('row', desc=False).execute()
    return response.data if response.data else []


# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 7. 쿨다운 (cooldowns) 관련 함수
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

@supabase_retry_handler()
async def get_cooldown(user_id_str: str, cooldown_key: str) -> float:
    """
    DB에서 마지막 쿨다운 시간을 가져와 Unix 타임스탬프(float)로 반환합니다.
    - DB의 컬럼 타입은 'timestamptz'여야 합니다.
    """
    response = await supabase.table('cooldowns').select('last_cooldown_timestamp').eq('user_id', user_id_str).eq('cooldown_key', cooldown_key).limit(1).execute()
    if response.data and (timestamp_str := response.data[0].get('last_cooldown_timestamp')) is not None:
        try:
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'
            return datetime.fromisoformat(timestamp_str).timestamp()
        except (ValueError, TypeError):
            logger.error(f"DB의 타임스탬프 문자열 형식이 올바르지 않습니다: {timestamp_str}")
            return 0.0
    return 0.0

@supabase_retry_handler()
async def set_cooldown(user_id_str: str, cooldown_key: str):
    """
    특정 유저의 쿨다운 기록을 현재 시간으로 DB에 설정합니다.
    - DB가 'now()' 함수를 통해 현재 시간을 직접 기록하도록 합니다.
    - 기존 기록을 삭제하고 새로 삽입하여 안정성을 확보합니다.
    """
    await supabase.table('cooldowns').delete().eq('user_id', user_id_str).eq('cooldown_key', cooldown_key).execute()
    await supabase.table('cooldowns').insert({ "user_id": user_id_str, "cooldown_key": cooldown_key }).execute()
