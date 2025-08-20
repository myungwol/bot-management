# bot-management/utils/database.py
"""
Supabase 데이터베이스와의 모든 상호작용을 관리하는 중앙 파일입니다.
"""
import os
import asyncio
import logging
from functools import wraps
from datetime import datetime, timezone
from typing import Dict, Callable, Any, List, Optional

from supabase import create_client, AsyncClient
from postgrest.exceptions import APIError

from .ui_defaults import UI_EMBEDS, UI_PANEL_COMPONENTS, UI_ROLE_KEY_MAP, SETUP_COMMAND_MAP

logger = logging.getLogger(__name__)

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
async def sync_defaults_to_db():
    logger.info("------ [ 기본값 DB 동기화 시작 ] ------")
    try:
        # [핵심 수정 1] 역할, 닉네임 관련 설정은 최신 상태를 유지해야 하므로 UPSERT (덮어쓰기)
        role_name_map = {key: info["name"] for key, info in UI_ROLE_KEY_MAP.items()}
        await save_config_to_db("ROLE_KEY_MAP", role_name_map)
        
        prefix_hierarchy = sorted(
            [info["name"] for info in UI_ROLE_KEY_MAP.values() if info.get("is_prefix")],
            key=lambda name: next((info.get("priority", 0) for info in UI_ROLE_KEY_MAP.values() if info["name"] == name), 0),
            reverse=True
        )
        await save_config_to_db("NICKNAME_PREFIX_HIERARCHY", prefix_hierarchy)
        
        # [핵심 수정 2] UI 요소(임베드, 컴포넌트), 명령어 맵은 UPSERT (덮어쓰기)
        await asyncio.gather(
            *[save_embed_to_db(key, data) for key, data in UI_EMBEDS.items()],
            *[save_panel_component_to_db(comp) for comp in UI_PANEL_COMPONENTS],
            save_config_to_db("SETUP_COMMAND_MAP", SETUP_COMMAND_MAP)
        )
        
        # [핵심 수정 3] channel_configs 테이블은 이미 설정된 값이 있다면 건드리지 않도록 (DO NOTHING)
        # 이는 관리자가 /setup으로 설정한 채널/역할 ID가 봇 재시작 시 초기화되는 것을 방지합니다.
        all_role_keys = list(UI_ROLE_KEY_MAP.keys())
        all_channel_keys = [info['key'] for info in SETUP_COMMAND_MAP.values()]
        
        placeholder_records = [
            {"channel_key": key, "channel_id": "0"} 
            for key in set(all_role_keys + all_channel_keys)
        ]
        
        if placeholder_records:
            # on_conflict='channel_key'와 함께 insert를 사용하면 UPSERT처럼 작동하지만,
            # supabase-py 2.x 에서는 on_conflict와 함께 명시적인 update나 ignore 액션이 필요할 수 있습니다.
            # 가장 안전한 방법은 upsert를 사용하되, 기존 값을 유지하는 로직을 구현하는 것이나,
            # 현재 라이브러리에서는 insert + on_conflict (do nothing) 이 직접 지원되지 않으므로,
            # 여기서는 insert를 호출하여 없는 키만 추가되도록 합니다. 
            # (만약 키가 있으면 라이브러리 레벨에서 에러가 날 수 있으나, 보통 무시됩니다)
            # 더 명확한 방법은 RLS 정책이나 DB 트리거를 사용하는 것이지만, 코드 레벨에서는 이것이 최선입니다.
            await supabase.table('channel_configs').upsert(placeholder_records, on_conflict="channel_key", ignore_duplicates=True).execute()

        logger.info(f"✅ 설정, 임베드({len(UI_EMBEDS)}개), 컴포넌트({len(UI_PANEL_COMPONENTS)}개) 동기화 완료. 기존 채널/역할 ID 설정은 유지됩니다.")

    except Exception as e:
        logger.error(f"❌ 기본값 DB 동기화 중 치명적 오류 발생: {e}", exc_info=True)
    logger.info("------ [ 기본값 DB 동기화 완료 ] ------")

async def load_all_data_from_db():
    logger.info("------ [ 모든 DB 데이터 캐시 로드 시작 ] ------")
    await asyncio.gather(load_bot_configs_from_db(), load_channel_ids_from_db())
    logger.info("------ [ 모든 DB 데이터 캐시 로드 완료 ] ------")

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 4. 설정 (bot_configs) 관련 함수
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
@supabase_retry_handler()
async def load_bot_configs_from_db():
    global _bot_configs_cache
    response = await supabase.table('bot_configs').select('config_key, config_value').execute()
    if response.data:
        _bot_configs_cache = {item['config_key']: item['config_value'] for item in response.data}
        logger.info(f"✅ {len(_bot_configs_cache)}개의 봇 설정을 DB에서 캐시로 로드했습니다.")

@supabase_retry_handler()
async def save_config_to_db(key: str, value: Any):
    global _bot_configs_cache
    await supabase.table('bot_configs').upsert({"config_key": key, "config_value": value}).execute()
    _bot_configs_cache[key] = value

def get_config(key: str, default: Any = None) -> Any:
    return _bot_configs_cache.get(key, default)

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 5. ID (channel_configs) 관련 함수
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
@supabase_retry_handler()
async def load_channel_ids_from_db():
    global _channel_id_cache
    response = await supabase.table('channel_configs').select('channel_key, channel_id').execute()
    if response.data:
        # channel_id가 '0'이 아닌 유효한 값만 캐시에 저장합니다.
        _channel_id_cache = {item['channel_key']: int(item['channel_id']) for item in response.data if item.get('channel_id') and item['channel_id'] != '0'}
        logger.info(f"✅ {len(_channel_id_cache)}개의 유효한 채널/역할 ID를 DB에서 캐시로 로드했습니다.")

@supabase_retry_handler()
async def save_id_to_db(key: str, object_id: int) -> bool: # [✅ 수정] bool 반환 타입을 명시
    global _channel_id_cache
    try:
        # [✅ 수정] DB 응답을 response 변수에 저장
        response = await supabase.table('channel_configs').upsert(
            {"channel_key": key, "channel_id": str(object_id)}, 
            on_conflict="channel_key"
        ).execute()
        
        # [✅ 수정] 응답 데이터가 있는지 확인하여 실제 성공 여부 판단
        if response.data:
            _channel_id_cache[key] = object_id
            logger.info(f"✅ '{key}' ID({object_id})를 DB와 캐시에 저장했습니다.")
            return True
        else:
            logger.error(f"❌ '{key}' ID({object_id})를 DB에 저장하려 했으나, DB가 성공 응답을 반환하지 않았습니다. (RLS 정책 확인 필요)")
            return False
    except Exception as e:
        logger.error(f"❌ '{key}' ID 저장 중 예외 발생: {e}", exc_info=True)
        return False

def get_id(key: str) -> Optional[int]:
    config_id = _channel_id_cache.get(key)
    if config_id is None:
        logger.warning(f"[ID Cache Miss] '{key}'에 해당하는 ID를 캐시에서 찾을 수 없습니다.")
    return config_id

async def save_panel_id(panel_name: str, message_id: int, channel_id: int):
    await save_id_to_db(f"panel_{panel_name}_message_id", message_id)
    await save_id_to_db(f"panel_{panel_name}_channel_id", channel_id)

def get_panel_id(panel_name: str) -> Optional[Dict[str, int]]:
    message_id = get_id(f"panel_{panel_name}_message_id")
    channel_id = get_id(f"panel_{panel_name}_channel_id")
    return {"message_id": message_id, "channel_id": channel_id} if message_id and channel_id else None

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# (이하 나머지 함수들은 기존과 동일합니다)
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 6. 임베드 및 UI 컴포넌트 관련 함수
@supabase_retry_handler()
async def save_embed_to_db(embed_key: str, embed_data: dict):
    await supabase.table('embeds').upsert({'embed_key': embed_key, 'embed_data': embed_data}, on_conflict='embed_key').execute()
@supabase_retry_handler()
async def get_embed_from_db(embed_key: str) -> Optional[dict]:
    response = await supabase.table('embeds').select('embed_data').eq('embed_key', embed_key).limit(1).execute()
    return response.data[0]['embed_data'] if response.data else None
@supabase_retry_handler()
async def get_onboarding_steps() -> List[dict]:
    response = await supabase.table('onboarding_steps').select('*, embed_data:embeds(embed_data)').order('step_number', desc=False).execute()
    return response.data if response.data else []
@supabase_retry_handler()
async def save_panel_component_to_db(component_data: dict):
    await supabase.table('panel_components').upsert(component_data, on_conflict='component_key').execute()
@supabase_retry_handler()
async def get_panel_components_from_db(panel_key: str) -> list:
    # [✅ 수정] row로 정렬한 뒤, 새로운 정렬 기준인 order_in_row로 한 번 더 정렬합니다.
    response = await supabase.table('panel_components').select('*').eq('panel_key', panel_key).order('row', desc=False).order('order_in_row', desc=False).execute()
    return response.data if response and response.data else []
# 7. 쿨다운 (cooldowns) 관련 함수
@supabase_retry_handler()
async def get_cooldown(user_id_str: str, cooldown_key: str) -> float:
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
    await supabase.table('cooldowns').upsert({ "user_id": user_id_str, "cooldown_key": cooldown_key, "last_cooldown_timestamp": datetime.now(timezone.utc).isoformat() }, on_conflict='user_id, cooldown_key').execute()
# 8. 통계 채널 (stats_channels) 관련 함수
@supabase_retry_handler()
async def get_all_stats_channels() -> List[Dict[str, Any]]:
    response = await supabase.table('stats_channels').select('*').execute()
    return response.data if response.data else []
@supabase_retry_handler()
async def add_stats_channel(channel_id: int, guild_id: int, stat_type: str, template: str, role_id: Optional[int] = None):
    await supabase.table('stats_channels').upsert({
        "channel_id": channel_id,
        "guild_id": guild_id,
        "stat_type": stat_type,
        "channel_name_template": template,
        "role_id": role_id
    }, on_conflict="channel_id").execute()
@supabase_retry_handler()
async def remove_stats_channel(channel_id: int):
    await supabase.table('stats_channels').delete().eq('channel_id', channel_id).execute()
# 9. 임시 음성 채널 (temp_voice_channels) 관련 함수
@supabase_retry_handler()
async def get_all_temp_channels() -> List[Dict[str, Any]]:
    response = await supabase.table('temp_voice_channels').select('*').execute()
    return response.data if response.data else []
@supabase_retry_handler()
async def add_temp_channel(channel_id: int, owner_id: int, guild_id: int, message_id: int, channel_type: str):
    await supabase.table('temp_voice_channels').insert({
        "channel_id": channel_id,
        "owner_id": owner_id,
        "guild_id": guild_id,
        "message_id": message_id,
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
# 11. 티켓 시스템 (tickets) 관련 함수
@supabase_retry_handler()
async def get_all_tickets() -> List[Dict[str, Any]]:
    response = await supabase.table('tickets').select('*').execute()
    return response.data if response.data else []
@supabase_retry_handler()
async def add_ticket(thread_id: int, owner_id: int, guild_id: int, ticket_type: str):
    await supabase.table('tickets').insert({
        "thread_id": thread_id,
        "owner_id": owner_id,
        "guild_id": guild_id,
        "ticket_type": ticket_type
    }).execute()
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
# 12. 경고 시스템 (warnings) 관련 함수
@supabase_retry_handler()
async def add_warning(guild_id: int, user_id: int, moderator_id: int, reason: str, amount: int) -> Optional[dict]:
    response = await supabase.table('warnings').insert({
        "guild_id": guild_id,
        "user_id": user_id,
        "moderator_id": moderator_id,
        "reason": reason,
        "amount": amount
    }).execute()
    return response.data[0] if response.data else None
@supabase_retry_handler()
async def get_total_warning_count(user_id: int, guild_id: int) -> int:
    response = await supabase.table('warnings').select('amount').eq('user_id', user_id).eq('guild_id', guild_id).execute()
    if response.data:
        return sum(item['amount'] for item in response.data)
    return 0

@supabase_retry_handler()
async def get_total_warning_count(user_id: int, guild_id: int) -> int:
    response = await supabase.table('warnings').select('amount').eq('user_id', user_id).eq('guild_id', guild_id).execute()
    if response.data:
        return sum(item['amount'] for item in response.data)
    return 0

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 13. 익명 게시판 (anonymous_messages) 관련 함수
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
@supabase_retry_handler()
async def add_anonymous_message(guild_id: int, user_id: int, content: str):
    """새로운 익명 메시지를 데이터베이스에 추가합니다."""
    await supabase.table('anonymous_messages').insert({
        "guild_id": guild_id,
        "user_id": user_id,
        "message_content": content
    }).execute()
    
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 14. 알림 (reminders) 관련 함수
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
@supabase_retry_handler()
async def schedule_reminder(guild_id: int, reminder_type: str, remind_at: datetime):
    """새로운 알림을 DB에 예약합니다."""
    # 같은 타입의 활성 알림이 이미 있는지 확인하고, 있다면 비활성화 처리
    await supabase.table('reminders') \
        .update({"is_active": False}) \
        .eq('guild_id', guild_id) \
        .eq('reminder_type', reminder_type) \
        .eq('is_active', True) \
        .execute()
    
    # 새로운 알림 삽입
    await supabase.table('reminders').insert({
        "guild_id": guild_id,
        "reminder_type": reminder_type,
        "remind_at": remind_at.isoformat(),
        "is_active": True
    }).execute()

@supabase_retry_handler()
async def get_due_reminders() -> List[Dict[str, Any]]:
    """현재 시간이 되어 알림을 보내야 하는 모든 활성 알림 목록을 가져옵니다."""
    now = datetime.now(timezone.utc).isoformat()
    response = await supabase.table('reminders') \
        .select('*') \
        .eq('is_active', True) \
        .lte('remind_at', now) \
        .execute()
    return response.data if response.data else []

@supabase_retry_handler()
async def deactivate_reminder(reminder_id: int):
    """알림 전송 완료 후 해당 알림을 비활성화합니다."""
    await supabase.table('reminders') \
        .update({"is_active": False}) \
        .eq('id', reminder_id) \
        .execute()
