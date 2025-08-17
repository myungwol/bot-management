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

# --- 캐시 영역 및 클라이언트 초기화 (변경 없음) ---
_bot_configs_cache: Dict[str, Any] = {}
_channel_id_cache: Dict[str, int] = {}
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

# --- 재시도 핸들러 (변경 없음) ---
def supabase_retry_handler(retries: int = 3, delay: int = 5):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not supabase:
                logger.error(f"❌ Supabase 클라이언트가 없어 '{func.__name__}' 함수를 실행할 수 없습니다.")
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
                        return None
        return wrapper
    return decorator

# --- 나머지 DB 함수들 (변경 없음) ---
@supabase_retry_handler()
async def save_config_to_db(key: str, value: Any):
    await supabase.table('bot_configs').upsert({"config_key": key, "config_value": value}).execute()
async def sync_defaults_to_db():
    logger.info("------ [ 기본값 DB 동기화 시작 ] ------")
    try:
        role_name_map = {key: info["name"] for key, info in UI_ROLE_KEY_MAP.items()}
        await save_config_to_db("ROLE_KEY_MAP", role_name_map)
        prefix_hierarchy = sorted([info["name"] for info in UI_ROLE_KEY_MAP.values() if info.get("is_prefix")],key=lambda name: next((info.get("priority", 0) for info in UI_ROLE_KEY_MAP.values() if info["name"] == name), 0),reverse=True)
        await save_config_to_db("NICKNAME_PREFIX_HIERARCHY", prefix_hierarchy)
        for key, data in UI_EMBEDS.items(): await save_embed_to_db(key, data)
        for component_data in UI_PANEL_COMPONENTS: await save_panel_component_to_db(component_data)
        await save_config_to_db("SETUP_COMMAND_MAP", SETUP_COMMAND_MAP)
    except Exception as e: logger.error(f"❌ 기본값 DB 동기화 중 오류 발생: {e}", exc_info=True)
    logger.info("------ [ 기본값 DB 동기화 완료 ] ------")
async def load_all_data_from_db():
    await asyncio.gather(load_bot_configs_from_db(), load_channel_ids_from_db())
@supabase_retry_handler()
async def load_bot_configs_from_db():
    global _bot_configs_cache
    response = await supabase.table('bot_configs').select('config_key, config_value').execute()
    if response.data: _bot_configs_cache = {item['config_key']: item['config_value'] for item in response.data}
@supabase_retry_handler()
async def load_channel_ids_from_db():
    global _channel_id_cache
    response = await supabase.table('channel_configs').select('channel_key, channel_id').execute()
    if response.data: _channel_id_cache = {item['channel_key']: int(item['channel_id']) for item in response.data}
def get_config(key: str, default: Any = None) -> Any:
    return _bot_configs_cache.get(key, default)
def get_id(key: str) -> int | None:
    return _channel_id_cache.get(key)
@supabase_retry_handler()
async def save_id_to_db(key: str, object_id: int):
    global _channel_id_cache
    await supabase.table('channel_configs').upsert({"channel_key": key, "channel_id": str(object_id)}, on_conflict="channel_key").execute()
    _channel_id_cache[key] = object_id
async def save_panel_id(panel_name: str, message_id: int, channel_id: int):
    await save_id_to_db(f"panel_{panel_name}_message_id", message_id)
    await save_id_to_db(f"panel_{panel_name}_channel_id", channel_id)
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

# ==============================================================================
# [최후의 쿨다운 함수]
# ==============================================================================
@supabase_retry_handler()
async def get_cooldown(user_id_str: str, cooldown_key: str) -> float:
    response = await supabase.table('cooldowns').select('last_cooldown_timestamp').eq('user_id', user_id_str).eq('cooldown_key', cooldown_key).limit(1).execute()
    if response.data and (timestamp_str := response.data[0].get('last_cooldown_timestamp')) is not None:
        try:
            # 'Z'로 끝나는 UTC 시간 형식을 처리
            if timestamp_str.endswith('Z'):
                timestamp_str = timestamp_str[:-1] + '+00:00'
            # DB에서 온 날짜 문자열을 float 타임스탬프로 변환
            return datetime.fromisoformat(timestamp_str).timestamp()
        except (ValueError, TypeError):
            logger.error(f"DB의 타임스탬프 문자열 형식이 올바르지 않습니다: {timestamp_str}")
            return 0.0
    return 0.0

@supabase_retry_handler()
async def set_cooldown(user_id_str: str, cooldown_key: str):
    # 이제 DB가 알아서 시간을 기록하므로, 봇은 user_id와 key만 알려주면 됩니다.
    await supabase.table('cooldowns').delete().eq('user_id', user_id_str).eq('cooldown_key', cooldown_key).execute()
    await supabase.table('cooldowns').insert({ "user_id": user_id_str, "cooldown_key": cooldown_key }).execute()
