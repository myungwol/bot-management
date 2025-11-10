# bot-management/utils/database.py

import os
import asyncio
import logging
import time
from functools import wraps
from datetime import datetime, timezone, timedelta

from typing import Dict, Callable, Any, List, Optional
import discord

from supabase import create_client, AsyncClient
from postgrest.exceptions import APIError

# --- ▼▼▼▼▼ 핵심 수정 시작 ▼▼▼▼▼ ---
# ui_defaults.py에서 BOSS_REWARD_TIERS를 import 합니다.
from .ui_defaults import (
    UI_EMBEDS, UI_PANEL_COMPONENTS, UI_ROLE_KEY_MAP, 
    SETUP_COMMAND_MAP, JOB_SYSTEM_CONFIG, AGE_ROLE_MAPPING, GAME_CONFIG,
    ONBOARDING_CHOICES, STATIC_AUTO_ROLE_PANELS, BOSS_REWARD_TIERS,
    TICKET_APPLICATION_DEPARTMENTS,
    # ▼▼▼ [추가] 이 줄을 추가해주세요 ▼▼▼
    TICKET_DEPARTMENT_MANAGERS,AGE_BRACKET_ROLES  
)
# --- ▲▲▲▲▲ 핵심 수정 종료 ▲▲▲▲▲ ---

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))


# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 1. 클라이언트 초기화 및 캐시
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
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

_bot_configs_cache: Dict[str, Any] = {}
_channel_id_cache: Dict[str, int] = {}
_user_abilities_cache: Dict[int, tuple[List[str], float]] = {}
# ▼▼▼ [추가] 고정 임베드 메시지 캐시 ▼▼▼
_sticky_messages_cache: Dict[int, Dict[str, Any]] = {}

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 2. DB 오류 처리 데코레이터
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
def supabase_retry_handler(retries: int = 3, delay: int = 2):
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
                    await asyncio.sleep(delay * (attempt + 1))
            
            logger.error(f"❌ '{func.__name__}' 함수가 모든 재시도({retries}번)에 실패했습니다. 마지막 오류: {last_exception}", exc_info=True)
            
            return_type = func.__annotations__.get("return")
            if return_type:
                type_str = str(return_type).lower()
                if "dict" in type_str: return {}
                if "list" in type_str: return []
            return None
        return wrapper
    return decorator

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 3. 데이터 로드 및 동기화
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# ▼▼▼▼▼ [수정] sync_defaults_to_db 함수 전체를 아래 코드로 교체합니다. ▼▼▼▼▼
async def sync_defaults_to_db():
    logger.info("------ [ 기본값 DB 동기화 시작 ] ------")
    try:
        # 새로운 UI_ROLE_KEY_MAP 전체를 DB에 동기화
        await save_config_to_db("UI_ROLE_KEY_MAP", UI_ROLE_KEY_MAP)
        
        # 병렬 처리로 나머지 설정 동기화
        await asyncio.gather(
            *[save_embed_to_db(key, data) for key, data in UI_EMBEDS.items()],
            *[save_panel_component_to_db(comp) for comp in UI_PANEL_COMPONENTS],
            save_config_to_db("SETUP_COMMAND_MAP", SETUP_COMMAND_MAP),
            save_config_to_db("STATIC_AUTO_ROLE_PANELS", STATIC_AUTO_ROLE_PANELS),
            save_config_to_db("JOB_SYSTEM_CONFIG", JOB_SYSTEM_CONFIG),
            save_config_to_db("AGE_ROLE_MAPPING", AGE_ROLE_MAPPING),
            save_config_to_db("GAME_CONFIG", GAME_CONFIG),
            save_config_to_db("ONBOARDING_CHOICES", ONBOARDING_CHOICES),
            # ▼▼▼ [수정 후] 이 라인 끝에 쉼표(,)를 추가하세요 ▼▼▼
            save_config_to_db("BOSS_REWARD_TIERS", BOSS_REWARD_TIERS),
            # ▲▲▲ [수정 후] 완료 ▲▲▲
            save_config_to_db("TICKET_APPLICATION_DEPARTMENTS", TICKET_APPLICATION_DEPARTMENTS),
            save_config_to_db("TICKET_DEPARTMENT_MANAGERS", TICKET_DEPARTMENT_MANAGERS)
        )

        all_role_keys = list(UI_ROLE_KEY_MAP.keys())
        all_channel_keys = [info['key'] for info in SETUP_COMMAND_MAP.values()]
        
        placeholder_records = [{"channel_key": key, "channel_id": "0"} for key in set(all_role_keys + all_channel_keys)]
        
        if placeholder_records:
            await supabase.table('channel_configs').upsert(placeholder_records, on_conflict="channel_key", ignore_duplicates=True).execute()

        logger.info(f"✅ 설정, 임베드({len(UI_EMBEDS)}개), 컴포넌트({len(UI_PANEL_COMPONENTS)}개), 및 기타 UI 기본값 동기화 완료.")

    except Exception as e:
        logger.error(f"❌ 기본값 DB 동기화 중 치명적 오류 발생: {e}", exc_info=True)
    logger.info("------ [ 기본값 DB 동기화 완료 ] ------")

async def load_all_data_from_db():
    logger.info("------ [ 모든 DB 데이터 캐시 로드 시작 ] ------")
    # ▼▼▼ [수정] load_sticky_messages_from_db() 추가 ▼▼▼
    await asyncio.gather(
        load_bot_configs_from_db(), 
        load_channel_ids_from_db(),
        load_sticky_messages_from_db()
    )
    # ▲▲▲ [수정 완료] ▲▲▲
    logger.info("------ [ 모든 DB 데이터 캐시 로드 완료 ] ------")

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 4. 설정 (bot_configs) 관련 함수
# ▼▼▼ [수정 1/2] load_bot_configs_from_db 함수를 아래 내용으로 교체 ▼▼▼
@supabase_retry_handler()
async def load_bot_configs_from_db():
    global _bot_configs_cache
    response = await supabase.table('bot_configs').select('config_key', 'config_value').execute()
    if response and response.data:
        # DB에서 가져온 값으로 기존 캐시를 업데이트(병합)합니다.
        # 이렇게 하면 sync_defaults_to_db가 미리 넣어둔 기본값이 보존됩니다.
        db_configs = {item['config_key']: item['config_value'] for item in response.data}
        _bot_configs_cache.update(db_configs)
        logger.info(f"✅ {len(db_configs)}개의 봇 설정을 DB에서 캐시로 로드/업데이트했습니다.")
# ▲▲▲ [수정 완료] ▲▲▲

@supabase_retry_handler()
async def save_config_to_db(key: str, value: Any):
    global _bot_configs_cache
    await supabase.table('bot_configs').upsert({"config_key": key, "config_value": value}).execute()
    _bot_configs_cache[key] = value
    
@supabase_retry_handler()
async def delete_config_from_db(key: str):
    """특정 설정 키를 DB와 로컬 캐시에서 삭제합니다."""
    global _bot_configs_cache
    try:
        await supabase.table('bot_configs').delete().eq('config_key', key).execute()
        _bot_configs_cache.pop(key, None)
        logger.info(f"설정 키 '{key}'가 DB와 로컬 캐시에서 성공적으로 삭제되었습니다.")
        return True
    except Exception as e:
        logger.error(f"설정 키 '{key}' 삭제 중 오류 발생: {e}", exc_info=True)
        return False
        
def get_config(key: str, default: Any = None) -> Any:
    return _bot_configs_cache.get(key, default)

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 5. ID (channel_configs) 관련 함수
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
@supabase_retry_handler()
async def load_channel_ids_from_db():
    global _channel_id_cache
    response = await supabase.table('channel_configs').select('channel_key, channel_id').execute()
    if response and response.data:
        _channel_id_cache = {item['channel_key']: int(item['channel_id']) for item in response.data if item.get('channel_id') and item['channel_id'] != '0'}
        logger.info(f"✅ {len(_channel_id_cache)}개의 유효한 채널/역할 ID를 DB에서 캐시로 로드했습니다.")

@supabase_retry_handler()
async def save_id_to_db(key: str, object_id: int) -> bool:
    global _channel_id_cache
    try:
        response = await supabase.table('channel_configs').upsert({"channel_key": key, "channel_id": str(object_id)}, on_conflict="channel_key").execute()
        if response.data:
            _channel_id_cache[key] = object_id
            logger.info(f"✅ '{key}' ID({object_id})를 DB와 캐시에 저장했습니다.")
            return True
        else:
            logger.error(f"❌ '{key}' ID({object_id})를 DB에 저장하려 했으나, DB가 성공 응답을 반환하지 않았습니다.")
            return False
    except Exception as e:
        logger.error(f"❌ '{key}' ID 저장 중 예외 발생: {e}", exc_info=True)
        return False

def get_id(key: str) -> Optional[int]:
    return _channel_id_cache.get(key)

async def save_panel_id(panel_name: str, message_id: int, channel_id: int):
    await save_id_to_db(f"panel_{panel_name}_message_id", message_id)
    await save_id_to_db(f"panel_{panel_name}_channel_id", channel_id)

def get_panel_id(panel_name: str) -> Optional[Dict[str, int]]:
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
    return response.data[0]['embed_data'] if response and response.data else None
@supabase_retry_handler()
async def get_all_embeds() -> List[Dict[str, Any]]:
    response = await supabase.table('embeds').select('embed_key, embed_data').order('embed_key').execute()
    return response.data if response and response.data else []
@supabase_retry_handler()
async def get_onboarding_steps() -> List[dict]:
    response = await supabase.table('onboarding_steps').select('*, embed_data:embeds(embed_data)').order('step_number', desc=False).execute()
    return response.data if response and response.data else []
@supabase_retry_handler()
async def save_panel_component_to_db(component_data: dict):
    await supabase.table('panel_components').upsert(component_data, on_conflict='component_key').execute()
@supabase_retry_handler()
async def get_panel_components_from_db(panel_key: str) -> list:
    response = await supabase.table('panel_components').select('*').eq('panel_key', panel_key).order('row', desc=False).order('order_in_row', desc=False).execute()
    return response.data if response and response.data else []
@supabase_retry_handler()
async def get_cooldown(user_id: int, cooldown_key: str) -> float: # 함수 인자 이름을 user_id_str -> user_id로 변경
    user_id_str = str(user_id) # 숫자로 받은 ID를 문자열로 변환
    response = await supabase.table('cooldowns').select('last_cooldown_timestamp').eq('subject_id', user_id_str).eq('cooldown_key', cooldown_key).limit(1).execute() # user_id -> subject_id
    if response and response.data and (timestamp_str := response.data[0].get('last_cooldown_timestamp')) is not None:
        try:
            if timestamp_str.endswith('Z'): timestamp_str = timestamp_str[:-1] + '+00:00'
            return datetime.fromisoformat(timestamp_str).timestamp()
        except (ValueError, TypeError): return 0.0
    return 0.0

@supabase_retry_handler()
async def set_cooldown(user_id: int, cooldown_key: str): # 함수 인자 이름을 user_id_str -> user_id로 변경
    user_id_str = str(user_id) # 숫자로 받은 ID를 문자열로 변환
    await supabase.table('cooldowns').upsert({ "subject_id": user_id_str, "cooldown_key": cooldown_key, "last_cooldown_timestamp": datetime.now(timezone.utc).isoformat() }, on_conflict='subject_id, cooldown_key').execute() # user_id -> subject_id
@supabase_retry_handler()
async def get_all_stats_channels() -> List[Dict[str, Any]]:
    response = await supabase.table('stats_channels').select('*').execute()
    return response.data if response and response.data else []
@supabase_retry_handler()
async def add_stats_channel(channel_id: int, guild_id: int, stat_type: str, template: str, role_id: Optional[int] = None):
    await supabase.table('stats_channels').upsert({"channel_id": channel_id, "guild_id": guild_id, "stat_type": stat_type, "channel_name_template": template, "role_id": role_id}, on_conflict="channel_id").execute()
@supabase_retry_handler()
async def remove_stats_channel(channel_id: int):
    await supabase.table('stats_channels').delete().eq('channel_id', channel_id).execute()
@supabase_retry_handler()
async def get_all_temp_channels() -> List[Dict[str, Any]]:
    response = await supabase.table('temp_voice_channels').select('*').execute()
    return response.data if response and response.data else []
@supabase_retry_handler()
async def add_temp_channel(channel_id: int, owner_id: int, guild_id: int, message_id: Optional[int], channel_type: str):
    # ▼▼▼ [수정] message_id가 None일 경우 0을 대신 삽입합니다. ▼▼▼
    await supabase.table('temp_voice_channels').insert({
        "channel_id": channel_id, 
        "owner_id": owner_id, 
        "guild_id": guild_id, 
        "message_id": message_id or 0, 
        "channel_type": channel_type
    }).execute()
@supabase_retry_handler()
async def update_temp_channel_owner(channel_id: int, new_owner_id: int):
    await supabase.table('temp_voice_channels').update({"owner_id": new_owner_id}).eq('channel_id', channel_id).execute()
@supabase_retry_handler()
async def remove_temp_channel(channel_id: int):
    await supabase.table('temp_voice_channels').delete().eq('channel_id', channel_id).execute()
@supabase_retry_handler()
async def remove_multiple_temp_channels(channel_ids: List[int]):
    if not channel_ids: return
    await supabase.table('temp_voice_channels').delete().in_('channel_id', channel_ids).execute()
@supabase_retry_handler()
async def get_all_tickets() -> List[Dict[str, Any]]:
    response = await supabase.table('tickets').select('*').execute()
    return response.data if response and response.data else []
@supabase_retry_handler()
async def add_ticket(thread_id: int, owner_id: int, guild_id: int, ticket_type: str):
    await supabase.table('tickets').insert({"thread_id": thread_id, "owner_id": owner_id, "guild_id": guild_id, "ticket_type": ticket_type}).execute()
@supabase_retry_handler()
async def remove_ticket(thread_id: int):
    await supabase.table('tickets').delete().eq('thread_id', thread_id).execute()
@supabase_retry_handler()
async def update_ticket_lock_status(thread_id: int, is_locked: bool):
    await supabase.table('tickets').update({"is_locked": is_locked}).eq('thread_id', thread_id).execute()
@supabase_retry_handler()
async def remove_multiple_tickets(thread_ids: List[int]):
    if not thread_ids: return
    await supabase.table('tickets').delete().in_('thread_id', thread_ids).execute()
@supabase_retry_handler()
async def add_warning(guild_id: int, user_id: int, moderator_id: int, reason: str, amount: int) -> Optional[dict]:
    response = await supabase.table('warnings').insert({
        "guild_id": guild_id, 
        "user_id": user_id, 
        "moderator_id": moderator_id, 
        "reason": reason, 
        "amount": amount
    }).execute()
    return response.data[0] if response and response.data else None
@supabase_retry_handler()
async def get_total_warning_count(user_id: int, guild_id: int) -> int:
    response = await supabase.table('warnings').select('amount').eq('user_id', user_id).eq('guild_id', guild_id).execute()
    return sum(item['amount'] for item in response.data) if response and response.data else 0
@supabase_retry_handler()
async def add_anonymous_message(guild_id: int, user_id: int, content: str):
    await supabase.table('anonymous_messages').insert({"guild_id": guild_id, "user_id": user_id, "message_content": content}).execute()
@supabase_retry_handler()
async def has_posted_anonymously_today(user_id: int) -> bool:
    today_kst_start = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    today_utc_start = today_kst_start.astimezone(timezone.utc)
    response = await supabase.table('anonymous_messages').select('id', count='exact').eq('user_id', user_id).gte('created_at', today_utc_start.isoformat()).limit(1).execute()
    return response.count > 0 if response else False
# ▼▼▼▼▼ [수정] schedule_reminder 함수 전체를 아래 코드로 교체 ▼▼▼▼▼
@supabase_retry_handler()
async def schedule_reminder(guild_id: int, reminder_type: str, remind_at: datetime, confirmation_message_id: Optional[int] = None):
    # 기존 활성 알림 비활성화
    await supabase.table('reminders').update({"is_active": False}).eq('guild_id', guild_id).eq('reminder_type', reminder_type).eq('is_active', True).execute()
    
    # 새 알림 예약 (확인 메시지 ID 포함)
    await supabase.table('reminders').insert({
        "guild_id": guild_id, 
        "reminder_type": reminder_type, 
        "remind_at": remind_at.isoformat(), 
        "is_active": True,
        "confirmation_message_id": confirmation_message_id
    }).execute()
# ▲▲▲▲▲ [수정] schedule_reminder 함수 교체 완료 ▲▲▲▲▲
@supabase_retry_handler()
async def get_due_reminders() -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc).isoformat()
    response = await supabase.table('reminders').select('*').eq('is_active', True).lte('remind_at', now).execute()
    return response.data if response and response.data else []
@supabase_retry_handler()
async def deactivate_reminder(reminder_id: int):
    await supabase.table('reminders').update({"is_active": False}).eq('id', reminder_id).execute()

# ▼▼▼ [핵심 추가] 이 함수를 추가하세요. ▼▼▼
@supabase_retry_handler()
async def set_reminder_message_id(reminder_id: int, message_id: int):
    """특정 알림에 대해 발송된 알림 메시지의 ID를 DB에 기록합니다."""
    await supabase.table('reminders').update({"reminder_message_id": message_id}).eq('id', reminder_id).execute()
# ▲▲▲ [추가 완료] ▲▲▲

@supabase_retry_handler()
async def update_wallet(user: discord.User, amount: int) -> Optional[dict]:
    params = {'p_user_id': str(user.id), 'p_amount': amount}
    response = await supabase.rpc('update_wallet_balance', params).execute()
    return response.data[0] if response and response.data else None
@supabase_retry_handler()
async def backup_member_data(user_id: int, guild_id: int, role_ids: List[int], nickname: Optional[str]):
    await supabase.table('left_members').upsert({ 'user_id': user_id, 'guild_id': guild_id, 'roles': role_ids, 'nickname': nickname, 'left_at': datetime.now(timezone.utc).isoformat() }).execute()
@supabase_retry_handler()
async def get_member_backup(user_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
    response = await supabase.table('left_members').select('*').eq('user_id', user_id).eq('guild_id', guild_id).maybe_single().execute()
    return response.data if response else None
@supabase_retry_handler()
async def delete_member_backup(user_id: int, guild_id: int):
    await supabase.table('left_members').delete().eq('user_id', user_id).eq('guild_id', guild_id).execute()
@supabase_retry_handler()
async def get_user_abilities(user_id: int) -> List[str]:
    CACHE_TTL = 300
    now = time.time()
    if user_id in _user_abilities_cache:
        cached_data, timestamp = _user_abilities_cache[user_id]
        if now - timestamp < CACHE_TTL:
            return cached_data
    response = await supabase.rpc('get_user_ability_keys', {'p_user_id': user_id}).execute()
    if response and hasattr(response, 'data'):
        abilities = response.data if response.data else []
        _user_abilities_cache[user_id] = (abilities, now)
        return abilities
    _user_abilities_cache[user_id] = ([], now)
    return []
@supabase_retry_handler()
async def load_sticky_messages_from_db():
    """DB에서 모든 고정 임베드 메시지 설정을 불러와 캐시에 저장합니다."""
    global _sticky_messages_cache
    response = await supabase.table('sticky_messages').select('*').execute()
    if response and response.data:
        _sticky_messages_cache = {item['channel_id']: item for item in response.data}
        logger.info(f"✅ {len(_sticky_messages_cache)}개의 고정 임베드 메시지 설정을 DB에서 캐시로 로드했습니다.")
    else:
        _sticky_messages_cache = {}

@supabase_retry_handler()
async def set_sticky_message(channel_id: int, message_id: int, guild_id: int, embed_data: dict):
    """채널에 대한 고정 임베드 메시지를 설정(추가/수정)합니다."""
    global _sticky_messages_cache
    record = {
        "channel_id": channel_id,
        "message_id": message_id,
        "guild_id": guild_id,
        "embed_data": embed_data
    }
    await supabase.table('sticky_messages').upsert(record).execute()
    _sticky_messages_cache[channel_id] = record
    logger.info(f"📌 채널(ID: {channel_id})에 고정 임베드 메시지(ID: {message_id})를 설정했습니다.")

@supabase_retry_handler()
async def remove_sticky_message(channel_id: int):
    """채널의 고정 임베드 메시지 설정을 삭제합니다."""
    global _sticky_messages_cache
    await supabase.table('sticky_messages').delete().eq('channel_id', channel_id).execute()
    _sticky_messages_cache.pop(channel_id, None)
    logger.info(f"📌 채널(ID: {channel_id})의 고정 임베드 메시지 설정을 삭제했습니다.")
