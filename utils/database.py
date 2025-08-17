# bot-management/utils/database.py

import os
import discord
from supabase import create_client, AsyncClient
import logging
import asyncio
from typing import Dict, Callable, Any, List
from functools import wraps

# [개선] UI_DEFAULTS에서 SETUP_COMMAND_MAP도 가져옵니다.
from .ui_defaults import UI_EMBEDS, UI_PANEL_COMPONENTS, UI_ROLE_KEY_MAP, SETUP_COMMAND_MAP

logger = logging.getLogger(__name__)

# --- 캐시 영역 ---
_bot_configs_cache: Dict[str, Any] = {}
_channel_id_cache: Dict[str, int] = {}
# [수정] 서버 관리 봇에서는 게임 관련 캐시를 사용하지 않습니다.
# _item_database_cache: Dict[str, Dict[str, Any]] = {}
# _fishing_loot_cache: List[Dict[str, Any]] = []

# --- Supabase 클라이언트 초기화 ---
supabase: AsyncClient = None
try:
    url: str = os.environ.get("SUPABASE_URL"); key: str = os.environ.get("SUPABASE_KEY")
    if not url or not key: raise ValueError("SUPABASE_URL 또는 SUPABASE_KEY 환경 변수가 설정되지 않았습니다.")
    supabase = AsyncClient(supabase_url=url, supabase_key=key)
    logger.info("✅ Supabase 비동기 클라이언트가 성공적으로 생성되었습니다.")
except Exception as e: logger.critical(f"❌ Supabase 클라이언트 생성 실패: {e}", exc_info=True)

# --- 범용 재시도 핸들러 ---
def supabase_retry_handler(retries: int = 3, delay: int = 5):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not supabase:
                logger.error(f"❌ Supabase 클라이언트가 없어 '{func.__name__}' 함수를 실행할 수 없습니다.")
                return_type = func.__annotations__.get("return");
                if return_type:
                    if "dict" in str(return_type).lower(): return {}
                    if "list" in str(return_type).lower(): return []
                return None
            for attempt in range(retries):
                try: return await func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"⚠️ '{func.__name__}' 함수 실행 중 오류 발생 (시도 {attempt + 1}/{retries}): {e}")
                    if attempt < retries - 1: await asyncio.sleep(delay)
                    else:
                        logger.error(f"❌ '{func.__name__}' 함수가 모든 재시도({retries}번)에 실패했습니다.", exc_info=True)
                        return_type = func.__annotations__.get("return");
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
        # 1. 역할 맵 동기화
        role_name_map = {key: info["name"] for key, info in UI_ROLE_KEY_MAP.items()}
        await save_config_to_db("ROLE_KEY_MAP", role_name_map)
        logger.info(f"✅ 역할 이름 맵(ROLE_KEY_MAP)을 DB에 동기화했습니다.")
        prefix_hierarchy = sorted([info["name"] for info in UI_ROLE_KEY_MAP.values() if info.get("is_prefix")], key=lambda name: next((info.get("priority", 0) for info in UI_ROLE_KEY_MAP.values() if info["name"] == name), 0), reverse=True)
        await save_config_to_db("NICKNAME_PREFIX_HIERARCHY", prefix_hierarchy)
        logger.info(f"✅ 닉네임 접두사 목록(NICKNAME_PREFIX_HIERARCHY)을 DB에 동기화했습니다.")
        
        # 2. 임베드 동기화
        for key, data in UI_EMBEDS.items(): await save_embed_to_db(key, data)
        logger.info(f"✅ {len(UI_EMBEDS)}개의 임베드 기본값을 DB에 동기화했습니다.")

        # 3. 패널 컴포넌트 동기화
        for component_data in UI_PANEL_COMPONENTS: await save_panel_component_to_db(component_data)
        logger.info(f"✅ {len(UI_PANEL_COMPONENTS)}개의 패널 컴포넌트 기본값을 DB에 동기화했습니다.")
        
        # [개선] /setup 명령어의 설정 맵을 DB에 동기화합니다.
        await save_config_to_db("SETUP_COMMAND_MAP", SETUP_COMMAND_MAP)
        logger.info(f"✅ /setup 명령어 설정 맵(SETUP_COMMAND_MAP)을 DB에 동기화했습니다.")

    except Exception as e: logger.error(f"❌ 기본값 DB 동기화 중 오류 발생: {e}", exc_info=True)
    logger.info("------ [ 기본값 DB 동기화 완료 ] ------")

async def load_all_data_from_db():
    logger.info("------ [ 모든 DB 데이터 로드 시작 ] ------")
    # [수정] 서버 관리 봇에서는 게임 데이터를 로드하지 않습니다.
    await asyncio.gather(load_bot_configs_from_db(), load_channel_ids_from_db())
    logger.info("------ [ 모든 DB 데이터 로드 완료 ] ------")

@supabase_retry_handler()
async def load_bot_configs_from_db():
    global _bot_configs_cache
    response = await supabase.table('bot_configs').select('config_key, config_value').execute()
    if response.data: _bot_configs_cache = {item['config_key']: item['config_value'] for item in response.data}; logger.info(f"✅ {len(_bot_configs_cache)}개의 봇 설정을 DB에서 로드했습니다.")
    else: logger.warning("DB 'bot_configs' 테이블에서 설정 정보를 찾을 수 없습니다.")

def get_config(key: str, default: Any = None) -> Any:
    value = _bot_configs_cache.get(key)
    if value is None: logger.warning(f"[Config Cache Miss] '{key}'에 해당하는 설정을 캐시에서 찾을 수 없습니다. 기본값을 사용합니다."); return default
    return value

# [수정] 서버 관리 봇에서는 게임 관련 데이터를 로드/사용하는 함수들이 필요 없습니다.
# 하지만 다른 봇(게임 봇)과의 호환성을 위해 함수 정의는 남겨두되, 내용은 비워두거나 단순화 할 수 있습니다.
# 여기서는 일단 해당 함수들을 주석 처리하거나 삭제하는 방향으로 진행합니다.

# def get_item_database() -> Dict[str, Dict[str, Any]]: return _item_database_cache
# def get_fishing_loot() -> List[Dict[str, Any]]: return _fishing_loot_cache
# async def load_game_data_from_db(): ... (함수 전체 삭제 또는 주석 처리)

@supabase_retry_handler()
async def load_channel_ids_from_db():
    global _channel_id_cache
    response = await supabase.table('channel_configs').select('channel_key, channel_id').execute()
    if response.data: _channel_id_cache = {item['channel_key']: int(item['channel_id']) for item in response.data}; logger.info(f"✅ {len(_channel_id_cache)}개의 채널/역할 ID를 DB에서 로드했습니다.")
    else: logger.warning("DB 'channel_configs' 테이블에서 ID 정보를 찾을 수 없습니다.")

def get_id(key: str) -> int | None:
    config_id = _channel_id_cache.get(key)
    if config_id is None: logger.warning(f"[ID Cache Miss] '{key}'에 해당하는 ID를 캐시에서 찾을 수 없습니다.")
    return config_id

@supabase_retry_handler()
async def save_id_to_db(key: str, object_id: int):
    global _channel_id_cache
    await supabase.table('channel_configs').upsert({"channel_key": key, "channel_id": str(object_id)}, on_conflict="channel_key").execute()
    _channel_id_cache[key] = object_id; logger.info(f"✅ '{key}' ID({object_id})를 DB와 캐시에 저장했습니다.")

async def save_panel_id(panel_name: str, message_id: int, channel_id: int):
    await save_id_to_db(f"panel_{panel_name}_message_id", message_id); await save_id_to_db(f"panel_{panel_name}_channel_id", channel_id)

def get_panel_id(panel_name: str) -> dict | None:
    message_id = get_id(f"panel_{panel_name}_message_id"); channel_id = get_id(f"panel_{panel_name}_channel_id")
    return {"message_id": message_id, "channel_id": channel_id} if message_id and channel_id else None

@supabase_retry_handler()
async def save_embed_to_db(embed_key: str, embed_data: dict): await supabase.table('embeds').upsert({'embed_key': embed_key, 'embed_data': embed_data}, on_conflict='embed_key').execute()
@supabase_retry_handler()
async def get_embed_from_db(embed_key: str) -> dict | None:
    response = await supabase.table('embeds').select('embed_data').eq('embed_key', embed_key).limit(1).execute()
    return response.data[0]['embed_data'] if response.data else None
@supabase_retry_handler()
async def get_panel_components_from_db(panel_key: str) -> list:
    response = await supabase.table('panel_components').select('*').eq('panel_key', panel_key).order('row', desc=False).execute()
    return response.data if response.data else []
@supabase_retry_handler()
async def save_panel_component_to_db(component_data: dict): await supabase.table('panel_components').upsert(component_data, on_conflict='component_key').execute()
@supabase_retry_handler()
async def get_onboarding_steps() -> list:
    response = await supabase.table('onboarding_steps').select('*, embed_data:embeds(embed_data)').order('step_number', desc=False).execute()
    return response.data if response.data else []

# [수정] 아래는 게임 봇에서 주로 사용할 함수들이므로, 서버 관리 봇에서는 일단 주석처리 합니다.
# @supabase_retry_handler()
# async def get_or_create_user(table_name: str, user_id_str: str, default_data: dict) -> dict: ...
# async def get_wallet(user_id: int) -> dict: ...
# @supabase_retry_handler()
# async def update_wallet(user: discord.User, amount: int) -> dict | None: ...
# @supabase_retry_handler()
# async def get_inventory(user_id_str: str) -> dict: ...
# @supabase_retry_handler()
# async def update_inventory(user_id_str: str, item_name: str, quantity: int): ...
# async def get_user_gear(user_id_str: str) -> dict: ...
# @supabase_retry_handler()
# async def set_user_gear(user_id_str: str, rod: str = None, bait: str = None): ...
# @supabase_retry_handler()
# async def get_aquarium(user_id_str: str) -> list: ...
# @supabase_retry_handler()
# async def add_to_aquarium(user_id_str: str, fish_data: dict): ...
# @supabase_retry_handler()
# async def remove_fish_from_aquarium(fish_id: int): ...

@supabase_retry_handler()
async def get_cooldown(user_id_str: str, cooldown_key: str) -> float:
    response = await supabase.table('cooldowns').select('last_cooldown_timestamp').eq('user_id', user_id_str).eq('cooldown_key', cooldown_key).limit(1).execute()
    if response.data and response.data[0].get('last_cooldown_timestamp') is not None: return float(response.data[0]['last_cooldown_timestamp'])
    return 0.0
@supabase_retry_handler()
async def set_cooldown(user_id_str: str, cooldown_key: str, timestamp: float): await supabase.table('cooldowns').upsert({"user_id": user_id_str, "cooldown_key": cooldown_key, "last_cooldown_timestamp": timestamp}).execute()
