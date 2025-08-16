# utils/database.py (치명적 오류 수정 완료)

import os
import discord
from supabase import create_client, AsyncClient
import logging
import asyncio
from typing import Dict, Callable, Any
from functools import wraps

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] %(message)s')
logger = logging.getLogger(__name__)

_cached_ids: Dict[str, int] = {}

AUTO_ROLE_MAPPING = [
    {"field_name": "性別", "keywords": ["男", "男性", "おとこ", "オトコ", "man", "male"], "role_id_key": "role_info_male"},
    {"field_name": "性別", "keywords": ["女", "女性", "おんな", "オンナ", "woman", "female"], "role_id_key": "role_info_female"},
]

CURRENCY_ICON = "🪙"
ROD_HIERARCHY = ["古い釣竿", "カーボン釣竿", "専門家用の釣竿", "伝説の釣竿"]

ITEM_DATABASE = {
    "住人票Lv.1": {"id_key": "role_resident_tier1", "price": 100, "category": "里の役職", "description": "基本的な特典が含まれています。", "emoji": "1️⃣", "buyable": True, "sellable": False},
    "住人票Lv.2": {"id_key": "role_resident_tier2", "price": 50, "category": "里の役職", "description": "追加のチャンネルへのアクセスが可能になります。", "emoji": "2️⃣", "buyable": True, "sellable": False},
    "仮住人": {"id_key": "role_temp_user", "price": 10, "category": "里の役職", "description": "里の雰囲気を体験できます。", "emoji": "🧑‍🌾", "buyable": True, "sellable": False},
    "一般の釣りエサ": {"price": 5, "sell_price": 2, "category": "釣り", "buyable": True, "sellable": True, "description": "魚のアタリが来るまでの時間を短縮します。(5～10秒)", "emoji": "🐛", "bite_time_range": (5.0, 10.0)},
    "高級釣りエサ": {"price": 20, "sell_price": 10, "category": "釣り", "buyable": True, "sellable": True, "description": "魚のアタリが来るまでの時間を大幅に短縮します。(4～8秒)", "emoji": "✨", "bite_time_range": (4.0, 8.0)},
    "古い釣竿": {"price": 100, "category": "釣り", "sellable": False, "buyable": True, "description": "最も基本的な釣竿です。", "emoji": "🎣", "good_fish_bonus": 0.0, "is_upgrade_item": True},
    "カーボン釣竿": {"price": 5000, "category": "釣り", "sellable": False, "buyable": True, "description": "珍しい魚が釣れる確率が少し増加します。(+5%)", "emoji": "🎣", "good_fish_bonus": 0.05, "is_upgrade_item": True},
}

FISHING_LOOT = [
    {"name": "古びた長靴", "emoji": "👢", "weight": 200, "value": 0, "title": "...長靴？", "description": "{user_mention}さんは古びた長靴を釣り上げました。", "color": 0x8B4513},
    {"name": "エビ", "emoji": "🦐", "weight": 250, "min_size": 5, "max_size": 15, "base_value": 5, "size_multiplier": 0.5},
    {"name": "小魚", "emoji": "🐟", "weight": 250, "min_size": 10, "max_size": 30, "base_value": 8, "size_multiplier": 0.8},
]

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
    
def supabase_retry_handler(retries: int = 3, delay: int = 5):
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            if not supabase:
                logger.error(f"❌ Supabase 클라이언트가 없어 '{func.__name__}' 함수를 실행할 수 없습니다.")
                if "get" in func.__name__:
                    return {} if "dict" in str(func.__annotations__.get("return")) else []
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

@supabase_retry_handler()
async def load_all_configs_from_db():
    global _cached_ids
    response = await supabase.table('channel_configs').select('channel_key, channel_id').execute()
    if response and response.data:
        _cached_ids = {item['channel_key']: int(item['channel_id']) for item in response.data}
        logger.info(f"✅ 데이터베이스에서 {len(_cached_ids)}개의 설정을 성공적으로 불러와 캐시했습니다.")
    else:
        logger.warning("DB 'channel_configs' 테이블에서 설정 정보를 찾을 수 없습니다.")

def get_id(key: str) -> int | None:
    config_id = _cached_ids.get(key)
    if config_id is None:
        logger.warning(f"[Cache Miss] '{key}'에 해당하는 ID를 캐시에서 찾을 수 없습니다.")
    return config_id

@supabase_retry_handler()
async def save_id_to_db(key: str, object_id: int):
    global _cached_ids
    await supabase.table('channel_configs').upsert(
        {"channel_key": key, "channel_id": str(object_id)}, 
        on_conflict="channel_key"
    ).execute()
    _cached_ids[key] = object_id
    logger.info(f"✅ '{key}' ID({object_id})를 DB와 캐시에 저장했습니다.")

@supabase_retry_handler()
async def save_embed_to_db(embed_key: str, embed_data: dict):
    await supabase.table('embeds').upsert({'embed_key': embed_key, 'embed_data': embed_data}, on_conflict='embed_key').execute()

@supabase_retry_handler()
async def get_embed_from_db(embed_key: str) -> dict | None:
    response = await supabase.table('embeds').select('embed_data').eq('embed_key', embed_key).limit(1).execute()
    return response.data[0]['embed_data'] if response and response.data else None

async def save_panel_id(panel_name: str, message_id: int, channel_id: int):
    await save_id_to_db(f"panel_{panel_name}_message_id", message_id)
    await save_id_to_db(f"panel_{panel_name}_channel_id", channel_id)

def get_panel_id(panel_name: str) -> dict | None:
    message_id = get_id(f"panel_{panel_name}_message_id")
    channel_id = get_id(f"panel_{panel_name}_channel_id")
    return {"message_id": message_id, "channel_id": channel_id} if message_id and channel_id else None

@supabase_retry_handler()
async def get_or_create_user(table_name: str, user_id_str: str, default_data: dict) -> dict:
    try:
        response = await supabase.table(table_name).select("*").eq("user_id", user_id_str).limit(1).execute()
        if response and response.data:
            return response.data[0]
        insert_data = {"user_id": user_id_str, **default_data}
        response = await supabase.table(table_name).insert(insert_data, returning="representation").execute()
        return response.data[0] if response and response.data else default_data
    except Exception:
        logger.error(f"'{table_name}' 테이블에서 유저 데이터 조회/생성 실패. 기본 데이터를 반환합니다.")
        return default_data

async def get_wallet(user_id: int) -> dict:
    return await get_or_create_user('wallets', str(user_id), {"balance": 0})

@supabase_retry_handler()
async def update_wallet(user: discord.User, amount: int):
    params = {'user_id_param': str(user.id), 'amount_param': amount}
    response = await supabase.rpc('increment_wallet_balance', params).execute()
    return response.data[0] if response and response.data else None

@supabase_retry_handler()
async def get_inventory(user_id_str: str) -> dict:
    response = await supabase.table('inventories').select('item_name, quantity').eq('user_id', user_id_str).gt('quantity', 0).execute()
    return {item['item_name']: item['quantity'] for item in response.data} if response and response.data else {}

@supabase_retry_handler()
async def update_inventory(user_id_str: str, item_name: str, quantity: int):
    params = {'user_id_param': user_id_str, 'item_name_param': item_name, 'amount_param': quantity}
    await supabase.rpc('increment_inventory_quantity', params).execute()

async def get_user_gear(user_id_str: str) -> dict:
    default_gear = {"rod": "古い釣竿", "bait": "エサなし"}
    gear = await get_or_create_user('gear_setups', user_id_str, default_gear)
    if not gear: gear = default_gear
    inv = await get_inventory(user_id_str)
    rod = gear.get('rod', '素手')
    if rod not in ["素手", "古い釣竿"] and inv.get(rod, 0) <= 0:
        rod = "古い釣竿"
    bait = gear.get('bait', 'エサなし')
    if bait != "エサなし" and inv.get(bait, 0) <= 0:
        bait = "エサなし"
    return {"rod": rod, "bait": bait}

@supabase_retry_handler()
async def set_user_gear(user_id_str: str, rod: str = None, bait: str = None):
    await get_or_create_user('gear_setups', user_id_str, {"rod": "古い釣竿", "bait": "エサなし"})
    data_to_update = {}
    if rod is not None: data_to_update['rod'] = rod
    if bait is not None: data_to_update['bait'] = bait
    if data_to_update:
        await supabase.table('gear_setups').update(data_to_update).eq('user_id', user_id_str).execute()

@supabase_retry_handler()
async def get_aquarium(user_id_str: str) -> list:
    response = await supabase.table('aquariums').select('id, name, size, emoji').eq('user_id', user_id_str).execute()
    return response.data if response and response.data else []

@supabase_retry_handler()
async def add_to_aquarium(user_id_str: str, fish_data: dict):
    insert_data = {"user_id": user_id_str, **fish_data}
    await supabase.table('aquariums').insert(insert_data).execute()

@supabase_retry_handler()
async def remove_fish_from_aquarium(fish_id: int):
    await supabase.table('aquariums').delete().eq('id', fish_id).execute()

# [수정] 여기가 문제의 함수입니다.
@supabase_retry_handler()
async def get_panel_components_from_db(panel_key: str) -> list | None:
    # .order('row', ascending=True) -> .order('row', desc=False) 로 수정
    response = await supabase.table('panel_components').select('*').eq('panel_key', panel_key).order('row', desc=False).execute()
    return response.data if response and response.data else None

@supabase_retry_handler()
async def save_panel_component_to_db(component_data: dict):
    await supabase.table('panel_components').upsert(component_data, on_conflict='component_key').execute()

@supabase_retry_handler()
async def get_onboarding_steps() -> list | None:
    # .order('step_number', ascending=False) -> .order('step_number', desc=False) 로 수정
    response = await supabase.table('onboarding_steps').select('*, embed_data:embeds(embed_data)').order('step_number', desc=False).execute()
    return response.data if response and response.data else None

async def get_activity_data(user_id_str: str) -> dict:
    return await get_or_create_user('activity_data', user_id_str, {"chat_counts":0, "voice_minutes":0})

@supabase_retry_handler()
async def update_activity_data(user_id_str: str, chat_increment=0, voice_increment=0, reset_chat=False, reset_voice=False):
    params = {'user_id_param': user_id_str, 'chat_increment_param': chat_increment, 'voice_increment_param': voice_increment, 'reset_chat_param': reset_chat, 'reset_voice_param': reset_voice}
    await supabase.rpc('increment_activity_data', params).execute()

@supabase_retry_handler()
async def get_cooldown(user_id_str: str, cooldown_key: str) -> float:
    response = await supabase.table('cooldowns').select('last_cooldown_timestamp').eq('user_id', user_id_str).eq('cooldown_key', cooldown_key).limit(1).execute()
    if response and response.data and response.data[0].get('last_cooldown_timestamp') is not None:
        return float(response.data[0]['last_cooldown_timestamp'])
    return 0.0

@supabase_retry_handler()
async def set_cooldown(user_id_str: str, cooldown_key: str, timestamp: float):
    await supabase.table('cooldowns').upsert(
        {"user_id": user_id_str, "cooldown_key": cooldown_key, "last_cooldown_timestamp": timestamp}
    ).execute()

def get_auto_role_mappings() -> list:
    return AUTO_ROLE_MAPPING
