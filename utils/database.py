# utils/database.py

import os
import discord
from supabase import create_client, AsyncClient
import logging
import asyncio
from typing import Dict, Callable, Any, List
from functools import wraps

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] %(message)s')
logger = logging.getLogger(__name__)

# --- [추가] 새로운 캐시 영역 ---
_bot_configs_cache: Dict[str, Any] = {}
_channel_id_cache: Dict[str, int] = {}
_item_database_cache: Dict[str, Dict[str, Any]] = {}
_fishing_loot_cache: List[Dict[str, Any]] = []

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

# --- [수정] 범용 재시도 핸들러 ---
def supabase_retry_handler(retries: int = 3, delay: int = 5):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not supabase:
                logger.error(f"❌ Supabase 클라이언트가 없어 '{func.__name__}' 함수를 실행할 수 없습니다.")
                # [수정] 반환 타입 힌트에 따라 기본값 반환
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
                        # [수정] 실패 시에도 기본값 반환
                        return_type = func.__annotations__.get("return")
                        if return_type:
                            if "dict" in str(return_type).lower(): return {}
                            if "list" in str(return_type).lower(): return []
                        return None
        return wrapper
    return decorator

# --- [신규] 모든 데이터 로더 통합 ---
async def load_all_data_from_db():
    """봇 시작 시 모든 필수 데이터를 DB에서 불러와 캐시에 저장합니다."""
    logger.info("------ [ 모든 DB 데이터 로드 시작 ] ------")
    await asyncio.gather(
        load_bot_configs_from_db(),
        load_channel_ids_from_db(),
        load_game_data_from_db()
    )
    logger.info("------ [ 모든 DB 데이터 로드 완료 ] ------")

# --- [신규] 봇 설정 로더 및 Getter ---
@supabase_retry_handler()
async def load_bot_configs_from_db():
    """'bot_configs' 테이블에서 모든 설정값을 불러와 캐시합니다."""
    global _bot_configs_cache
    response = await supabase.table('bot_configs').select('config_key, config_value').execute()
    if response.data:
        _bot_configs_cache = {item['config_key']: item['config_value'] for item in response.data}
        logger.info(f"✅ {_len(_bot_configs_cache)}개의 봇 설정을 DB에서 로드했습니다.")
    else:
        logger.warning("DB 'bot_configs' 테이블에서 설정 정보를 찾을 수 없습니다.")

def get_config(key: str, default: Any = None) -> Any:
    """캐시에서 봇 설정값을 가져옵니다. 없으면 기본값을 반환합니다."""
    value = _bot_configs_cache.get(key)
    if value is None:
        logger.warning(f"[Config Cache Miss] '{key}'에 해당하는 설정을 캐시에서 찾을 수 없습니다. 기본값을 사용합니다.")
        return default
    return value

# --- [수정] 게임 데이터 로더 및 Getter ---
@supabase_retry_handler()
async def load_game_data_from_db():
    """'items'와 'fishing_loots' 테이블에서 게임 데이터를 불러와 캐시합니다."""
    global _item_database_cache, _fishing_loot_cache
    
    # 아이템 데이터 로드
    item_response = await supabase.table('items').select('*').execute()
    if item_response.data:
        temp_item_db = {item.pop('name'): item for item in item_response.data}
        _item_database_cache = temp_item_db
        logger.info(f"✅ {_len(_item_database_cache)}개의 아이템 정보를 DB에서 로드했습니다.")
    else:
        logger.warning("DB 'items' 테이블에서 아이템 정보를 찾을 수 없습니다.")
        
    # 낚시 결과물 데이터 로드
    loot_response = await supabase.table('fishing_loots').select('*').execute()
    if loot_response.data:
        _fishing_loot_cache = loot_response.data
        logger.info(f"✅ {_len(_fishing_loot_cache)}개의 낚시 결과물 정보를 DB에서 로드했습니다.")
    else:
        logger.warning("DB 'fishing_loots' 테이블에서 낚시 결과물 정보를 찾을 수 없습니다.")

def get_item_database() -> Dict[str, Dict[str, Any]]:
    return _item_database_cache

def get_fishing_loot() -> List[Dict[str, Any]]:
    return _fishing_loot_cache
    
# --- [수정] 채널/역할 ID 로더 및 Getter ---
@supabase_retry_handler()
async def load_channel_ids_from_db():
    """'channel_configs' 테이블에서 모든 ID 설정을 불러와 캐시합니다."""
    global _channel_id_cache
    response = await supabase.table('channel_configs').select('channel_key, channel_id').execute()
    if response.data:
        _channel_id_cache = {item['channel_key']: int(item['channel_id']) for item in response.data}
        logger.info(f"✅ {_len(_channel_id_cache)}개의 채널/역할 ID를 DB에서 로드했습니다.")
    else:
        logger.warning("DB 'channel_configs' 테이블에서 ID 정보를 찾을 수 없습니다.")

def get_id(key: str) -> int | None:
    """캐시에서 채널/역할/메시지 ID를 가져옵니다."""
    config_id = _channel_id_cache.get(key)
    if config_id is None:
        logger.warning(f"[ID Cache Miss] '{key}'에 해당하는 ID를 캐시에서 찾을 수 없습니다.")
    return config_id

@supabase_retry_handler()
async def save_id_to_db(key: str, object_id: int):
    """채널/역할/메시지 ID를 DB와 캐시에 저장(업데이트)합니다."""
    global _channel_id_cache
    await supabase.table('channel_configs').upsert(
        {"channel_key": key, "channel_id": str(object_id)}, 
        on_conflict="channel_key"
    ).execute()
    _channel_id_cache[key] = object_id
    logger.info(f"✅ '{key}' ID({object_id})를 DB와 캐시에 저장했습니다.")

# --- 패널 ID 헬퍼 함수 ---
async def save_panel_id(panel_name: str, message_id: int, channel_id: int):
    await save_id_to_db(f"panel_{panel_name}_message_id", message_id)
    await save_id_to_db(f"panel_{panel_name}_channel_id", channel_id)

def get_panel_id(panel_name: str) -> dict | None:
    message_id = get_id(f"panel_{panel_name}_message_id")
    channel_id = get_id(f"panel_{panel_name}_channel_id")
    return {"message_id": message_id, "channel_id": channel_id} if message_id and channel_id else None

# --- 임베드 관리 함수 ---
@supabase_retry_handler()
async def save_embed_to_db(embed_key: str, embed_data: dict):
    await supabase.table('embeds').upsert(
        {'embed_key': embed_key, 'embed_data': embed_data}, 
        on_conflict='embed_key'
    ).execute()

@supabase_retry_handler()
async def get_embed_from_db(embed_key: str) -> dict | None:
    response = await supabase.table('embeds').select('embed_data').eq('embed_key', embed_key).limit(1).execute()
    return response.data[0]['embed_data'] if response.data else None

# --- UI 컴포넌트 관리 함수 ---
@supabase_retry_handler()
async def get_panel_components_from_db(panel_key: str) -> list:
    response = await supabase.table('panel_components').select('*').eq('panel_key', panel_key).order('row', desc=False).execute()
    return response.data if response.data else []

@supabase_retry_handler()
async def save_panel_component_to_db(component_data: dict):
    await supabase.table('panel_components').upsert(
        component_data, 
        on_conflict='component_key'
    ).execute()
    
# --- 온보딩 관리 함수 ---
@supabase_retry_handler()
async def get_onboarding_steps() -> list:
    # [수정] 외부 키 참조 대신 join을 사용하여 더 안정적으로 데이터를 가져옵니다.
    response = await supabase.table('onboarding_steps').select('*, embed_data:embeds(embed_data)').order('step_number', desc=False).execute()
    return response.data if response.data else []

# --- 유저 데이터 공용 함수 ---
@supabase_retry_handler()
async def get_or_create_user(table_name: str, user_id_str: str, default_data: dict) -> dict:
    """특정 테이블에서 유저 데이터를 가져오거나, 없으면 기본값으로 생성합니다."""
    try:
        response = await supabase.table(table_name).select("*").eq("user_id", user_id_str).limit(1).execute()
        if response.data:
            return response.data[0]
        
        insert_data = {"user_id": user_id_str, **default_data}
        response = await supabase.table(table_name).insert(insert_data, returning="representation").execute()
        return response.data[0] if response.data else default_data
    except Exception as e:
        logger.error(f"'{table_name}' 테이블에서 유저 데이터 조회/생성 실패. 기본 데이터를 반환합니다: {e}")
        return default_data

# --- 지갑(Wallet) 관련 함수 ---
async def get_wallet(user_id: int) -> dict:
    return await get_or_create_user('wallets', str(user_id), {"balance": 0})

@supabase_retry_handler()
async def update_wallet(user: discord.User, amount: int) -> dict | None:
    params = {'user_id_param': str(user.id), 'amount_param': amount}
    response = await supabase.rpc('increment_wallet_balance', params).execute()
    return response.data[0] if response.data else None

# --- 인벤토리(Inventory) 관련 함수 ---
@supabase_retry_handler()
async def get_inventory(user_id_str: str) -> dict:
    response = await supabase.table('inventories').select('item_name, quantity').eq('user_id', user_id_str).gt('quantity', 0).execute()
    return {item['item_name']: item['quantity'] for item in response.data} if response.data else {}

@supabase_retry_handler()
async def update_inventory(user_id_str: str, item_name: str, quantity: int):
    params = {'user_id_param': user_id_str, 'item_name_param': item_name, 'amount_param': quantity}
    await supabase.rpc('increment_inventory_quantity', params).execute()

# --- 장비(Gear) 관련 함수 ---
async def get_user_gear(user_id_str: str) -> dict:
    default_rod = get_config("DEFAULT_ROD", "古い釣竿")
    default_bait = get_config("DEFAULT_BAIT", "エサなし")
    default_gear = {"rod": default_rod, "bait": default_bait}
    
    gear = await get_or_create_user('gear_setups', user_id_str, default_gear)
    if not gear: gear = default_gear
    
    inv = await get_inventory(user_id_str)
    
    rod = gear.get('rod', '素手')
    if rod not in ["素手", default_rod] and inv.get(rod, 0) <= 0:
        rod = default_rod
        
    bait = gear.get('bait', default_bait)
    if bait != default_bait and inv.get(bait, 0) <= 0:
        bait = default_bait
        
    return {"rod": rod, "bait": bait}

@supabase_retry_handler()
async def set_user_gear(user_id_str: str, rod: str = None, bait: str = None):
    default_rod = get_config("DEFAULT_ROD", "古い釣竿")
    default_bait = get_config("DEFAULT_BAIT", "エサなし")
    await get_or_create_user('gear_setups', user_id_str, {"rod": default_rod, "bait": default_bait})
    
    data_to_update = {}
    if rod is not None: data_to_update['rod'] = rod
    if bait is not None: data_to_update['bait'] = bait
    
    if data_to_update:
        await supabase.table('gear_setups').update(data_to_update).eq('user_id', user_id_str).execute()

# --- 수족관(Aquarium) 관련 함수 ---
@supabase_retry_handler()
async def get_aquarium(user_id_str: str) -> list:
    response = await supabase.table('aquariums').select('id, name, size, emoji').eq('user_id', user_id_str).execute()
    return response.data if response.data else []

@supabase_retry_handler()
async def add_to_aquarium(user_id_str: str, fish_data: dict):
    insert_data = {"user_id": user_id_str, **fish_data}
    await supabase.table('aquariums').insert(insert_data).execute()

@supabase_retry_handler()
async def remove_fish_from_aquarium(fish_id: int):
    await supabase.table('aquariums').delete().eq('id', fish_id).execute()

# --- 쿨타임(Cooldown) 관련 함수 ---
@supabase_retry_handler()
async def get_cooldown(user_id_str: str, cooldown_key: str) -> float:
    response = await supabase.table('cooldowns').select('last_cooldown_timestamp').eq('user_id', user_id_str).eq('cooldown_key', cooldown_key).limit(1).execute()
    if response.data and response.data[0].get('last_cooldown_timestamp') is not None:
        return float(response.data[0]['last_cooldown_timestamp'])
    return 0.0

@supabase_retry_handler()
async def set_cooldown(user_id_str: str, cooldown_key: str, timestamp: float):
    await supabase.table('cooldowns').upsert(
        {"user_id": user_id_str, "cooldown_key": cooldown_key, "last_cooldown_timestamp": timestamp}
    ).execute()
    
# --- 헬퍼 함수 ---
def _len(data) -> int:
    """None을 확인하고 길이를 반환하는 안전한 길이 함수"""
    return len(data) if data else 0
