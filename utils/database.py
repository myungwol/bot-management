# utils/database.py (역할 ID 자동 로딩 기능 추가 최종본)

import os
import discord
from supabase import create_client, AsyncClient
import logging
import re
from typing import Dict, Any

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- ⬇️ 역할 ID 관리 ⬇️ ---
# [수정] 이제 대부분의 역할 ID는 DB에서 자동으로 불러옵니다.
# DB에서 관리하기 어려운 극소수의 핵심 역할만 남겨둡니다.
ROLE_ID_CONFIG: Dict[str, int] = {
    "admin_total": 1405325594228424795,
    "approval_role": 1405325627384402032,
}

# [새로 추가된 부분] DB에서 불러온 역할/채널 ID를 저장할 전역 캐시
_cached_ids: Dict[str, int] = {}

# --- ⬇️ 자기소개 기반 자동 역할 부여 규칙 (성별) ⬇️ ---
AUTO_ROLE_MAPPING = [
    {
        "field_name": "性別",
        "keywords": ["男", "男性", "おとこ", "オトコ", "man", "male"],
        "role_id_db_key": "role_info_male" 
    },
    {
        "field_name": "性別",
        "keywords": ["女", "女性", "おんな", "オンナ", "woman", "female"],
        "role_id_db_key": "role_info_female"
    },
]

CURRENCY_ICON = "🪙"
ROLE_PREFIX_MAPPING = {
    933077535405789205: "一", 933077534994755654: "二", 933077536253050970: "三", 933077542699663390: "四", 1209471813319528468: "五",
    1209471819866841149: "六", 1209471820559032320: "七", 1209471821166944266: "八", 1209471821632770099: "九",
}
ROD_HIERARCHY = ["古い釣竿", "カーボン釣竿", "専門家用の釣竿", "伝説の釣竿"]

ITEM_DATABASE = {
    "住人票Lv.1": {"id_db_key": "role_resident_tier1", "price": 100, "category": "里の役職", "description": "基本的な特典が含まれています。", "emoji": "1️⃣", "buyable": True, "sellable": False},
    "住人票Lv.2": {"id_db_key": "role_resident_tier2", "price": 50, "category": "里の役職", "description": "追加のチャンネルへのアクセスが可能になります。", "emoji": "2️⃣", "buyable": True, "sellable": False},
    "仮住人": {"id_db_key": "role_temp_user", "price": 10, "category": "里の役職", "description": "里の雰囲気を体験できます。", "emoji": "🧑‍🌾", "buyable": True, "sellable": False},
    "一般の釣りエサ": {"price": 5, "sell_price": 2, "category": "釣り", "buyable": True, "sellable": True, "description": "魚のアタリが来るまでの時間を短縮します。(5～10秒)", "emoji": "🐛", "bite_time_range": (5.0, 10.0)},
    "高級釣りエサ": {"price": 20, "sell_price": 10, "category": "釣り", "buyable": True, "sellable": True, "description": "魚のアタリが来るまでの時間を大幅に短縮します。(4～8秒)", "emoji": "✨", "bite_time_range": (4.0, 8.0)},
    "古い釣竿": {"price": 100, "category": "釣り", "sellable": False, "buyable": True, "description": "最も基本的な釣竿です。", "emoji": "🎣", "good_fish_bonus": 0.0, "is_upgrade_item": True},
    "カーボン釣竿": {"price": 5000, "category": "釣り", "sellable": False, "buyable": True, "description": "珍しい魚が釣れる確率が少し増加します。(+5%)", "emoji": "🎣", "good_fish_bonus": 0.05, "is_upgrade_item": True},
}

FISHING_LOOT = [
    {"name": "古びた長靴", "emoji": "👢", "weight": 200, "value": 0},
    {"name": "エビ", "emoji": "🦐", "weight": 250, "min_size": 5, "max_size": 15, "base_value": 5, "size_multiplier": 0.5},
    {"name": "小魚", "emoji": "🐟", "weight": 250, "min_size": 10, "max_size": 30, "base_value": 8, "size_multiplier": 0.8},
]

supabase: AsyncClient = None
try:
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_KEY")
    if not url or not key: raise ValueError("SUPABASE_URL 또는 SUPABASE_KEY 환경 변수가 설정되지 않았습니다.")
    supabase = AsyncClient(supabase_url=url, supabase_key=key)
    logger.info("✅ Supabase 비동기 클라이언트가 성공적으로 생성되었습니다.")
except Exception as e:
    logger.error(f"❌ Supabase 클라이언트 생성 실패: {e}", exc_info=True)

# --- [새로운 핵심 함수] 모든 채널/역할 ID를 DB에서 불러와 캐시에 저장 ---
async def load_all_configs_from_db():
    global _cached_ids
    if not supabase: 
        logger.warning("Supabase client not available. Cannot load configs.")
        return
    try:
        response = await supabase.table('channel_configs').select('channel_key, channel_id').execute()
        if response.data:
            _cached_ids = {item['channel_key']: int(item['channel_id']) for item in response.data}
            logger.info(f"✅ Successfully loaded and cached {len(_cached_ids)} configs from the database.")
        else:
            logger.warning("No configs found in the database table 'channel_configs'.")
    except Exception as e:
        logger.error(f"[DB Error] Failed to execute get_all_channel_configs: {e}", exc_info=True)

# [수정] get_role_id와 get_channel_id를 하나의 함수로 통합
def get_id(key: str) -> int | None:
    # 1. 메모리에 캐시된 DB 값에서 먼저 찾아봄
    role_id = _cached_ids.get(key)
    if role_id:
        return role_id
    
    # 2. 캐시에 없다면, 코드에 하드코딩된 값에서 찾아봄 (예: admin_total)
    role_id = ROLE_ID_CONFIG.get(key)
    if role_id:
        return role_id

    # 3. 두 군데 모두 없으면 경고 로그를 남기고 None 반환
    logger.warning(f"[get_id] ID for key '{key}' not found in cache or config.")
    return None

async def save_id_to_db(key: str, object_id: int):
    global _cached_ids
    if not supabase: return
    try:
        await supabase.table('channel_configs').upsert({"channel_key": key, "channel_id": object_id}, on_conflict="channel_key").execute()
        # 실시간으로 캐시도 업데이트
        _cached_ids[key] = object_id
    except Exception as e:
        logger.error(f"[DB Error] save_id_to_db: {e}", exc_info=True)

# --- 기존 함수들은 새로운 get_id / save_id_to_db를 사용하도록 변경 ---
def get_role_id(key: str) -> int | None:
    return get_id(f"role_{key}") # 역할 키에는 'role_' 접두사를 붙여서 조회

def get_channel_id(key: str) -> int | None:
    return get_id(key) # 채널 키는 그대로 조회

async def save_channel_id_to_db(channel_key: str, object_id: int):
    await save_id_to_db(channel_key, object_id)

# --- ⬇️ 패널 및 DB 관리 함수 섹션 ⬇️ ---
async def save_embed_to_db(embed_key: str, embed_data: dict):
    if not supabase: return
    try: await supabase.table('embeds').upsert({'embed_key': embed_key, 'embed_data': embed_data}).execute()
    except Exception as e: logger.error(f"[DB Error] save_embed_to_db: {e}", exc_info=True)

async def get_embed_from_db(embed_key: str) -> dict | None:
    if not supabase: return None
    try:
        response = await supabase.table('embeds').select('embed_data').eq('embed_key', embed_key).limit(1).execute()
        return response.data[0]['embed_data'] if response.data else None
    except Exception as e: logger.error(f"[DB Error] get_embed_from_db: {e}", exc_info=True); return None

async def delete_embed_from_db(embed_key: str):
    if not supabase: return
    try: await supabase.table('embeds').delete().eq('embed_key', embed_key).execute()
    except Exception as e: logger.error(f"[DB Error] delete_embed_from_db: {e}", exc_info=True)

async def save_panel_id(panel_name: str, message_id: int, channel_id: int):
    await save_id_to_db(f"panel_{panel_name}_message_id", message_id)
    await save_id_to_db(f"panel_{panel_name}_channel_id", channel_id)

async def get_panel_id(panel_name: str) -> dict | None:
    message_id = get_id(f"panel_{panel_name}_message_id")
    channel_id = get_id(f"panel_{panel_name}_channel_id")
    if message_id and channel_id:
        return {"message_id": message_id, "channel_id": channel_id}
    return None

async def delete_panel_id(panel_name: str):
    # 이 기능은 이제 DB에서 직접 삭제해야 함
    logger.warning("delete_panel_id is deprecated. Please manage panel IDs directly in the database.")
    pass

def get_auto_role_mappings() -> list:
    return AUTO_ROLE_MAPPING

async def get_or_create_user(table_name: str, user_id_str: str, default_data: dict):
    if not supabase: return {}
    try:
        response = await supabase.table(table_name).select("*").eq("user_id", user_id_str).limit(1).execute()
        if response.data: return response.data[0]
        insert_data = {"user_id": user_id_str, **default_data}
        response = await supabase.table(table_name).insert(insert_data, returning="representation").execute()
        return response.data[0] if response.data else {}
    except Exception as e: logger.error(f"[DB Error] get_or_create_user on '{table_name}': {e}", exc_info=True); return {}

# (이하 나머지 함수들은 변경 없이 동일)
# ... (get_wallet, update_wallet, get_inventory 등)
async def get_wallet(user_id: int):
    return await get_or_create_user('wallets', str(user_id), {"balance": 0}) or {"balance": 0}

async def update_wallet(user: discord.User, amount: int):
    user_id_str = str(user.id)
    if not supabase: return None
    try:
        params = {'user_id_param': user_id_str, 'amount_param': amount}
        response = await supabase.rpc('increment_wallet_balance', params).execute()
        return response.data[0] if response.data else None
    except Exception as e: logger.error(f"[DB Error] update_wallet_rpc: {e}", exc_info=True); return None

async def get_inventory(user_id_str: str):
    if not supabase: return {}
    try:
        response = await supabase.table('inventories').select('item_name, quantity').eq('user_id', user_id_str).gt('quantity', 0).execute()
        return {item['item_name']: item['quantity'] for item in response.data}
    except Exception as e: logger.error(f"[DB Error] get_inventory: {e}", exc_info=True); return {}

async def update_inventory(user_id_str: str, item_name: str, quantity: int):
    if not supabase: return
    try:
        params = {'user_id_param': user_id_str, 'item_name_param': item_name, 'amount_param': quantity}
        await supabase.rpc('increment_inventory_quantity', params).execute()
    except Exception as e: logger.error(f"[DB Error] update_inventory: {e}", exc_info=True)

async def get_aquarium(user_id_str: str):
    if not supabase: return []
    try:
        response = await supabase.table('aquariums').select('id, name, size, emoji').eq('user_id', user_id_str).execute()
        return response.data
    except Exception as e: logger.error(f"[DB Error] get_aquarium: {e}", exc_info=True); return []

async def add_to_aquarium(user_id_str: str, fish_data: dict):
    if not supabase: return
    try:
        insert_data = {"user_id": user_id_str, **fish_data}
        await supabase.table('aquariums').insert(insert_data).execute()
    except Exception as e: logger.error(f"[DB Error] add_to_aquarium: {e}", exc_info=True)

async def remove_fish_from_aquarium(fish_id: int):
    if not supabase: return
    try: await supabase.table('aquariums').delete().eq('id', fish_id).execute()
    except Exception as e: logger.error(f"[DB Error] remove_fish_from_aquarium: {e}", exc_info=True)

async def get_user_gear(user_id_str: str):
    if not supabase: return {"rod": "素手", "bait": "エサなし"}
    gear = await get_or_create_user('gear_setups', user_id_str, {"rod": "古い釣竿", "bait": "エサなし"}) or {}
    inv = await get_inventory(user_id_str)
    rod = gear.get('rod', '素手')
    if rod not in ["素手", "古い釣竿"] and inv.get(rod, 0) <= 0: rod = "古い釣竿"
    bait = gear.get('bait', 'エサなし')
    if bait != "エサなし" and inv.get(bait, 0) <= 0: bait = "エサなし"
    return {"rod": rod, "bait": bait}

async def set_user_gear(user_id_str: str, rod: str = None, bait: str = None):
    if not supabase: return
    try:
        await get_or_create_user('gear_setups', user_id_str, {"rod": "古い釣竿", "bait": "エサなし"})
        data_to_update = {}
        if rod is not None: data_to_update['rod'] = rod
        if bait is not None: data_to_update['bait'] = bait
        if data_to_update: await supabase.table('gear_setups').update(data_to_update).eq('user_id', user_id_str).execute()
    except Exception as e: logger.error(f"[DB Error] set_user_gear: {e}", exc_info=True)

async def get_activity_data(user_id_str: str):
    return await get_or_create_user('activity_data', user_id_str, {"chat_counts":0, "voice_minutes":0}) or {}

async def update_activity_data(user_id_str: str, chat_increment=0, voice_increment=0, reset_chat=False, reset_voice=False):
    if not supabase: return
    try:
        params = {'user_id_param': user_id_str, 'chat_increment_param': chat_increment, 'voice_increment_param': voice_increment, 'reset_chat_param': reset_chat, 'reset_voice_param': reset_voice}
        await supabase.rpc('increment_activity_data', params).execute()
    except Exception as e: logger.error(f"[DB Error] update_activity_data: {e}", exc_info=True)

async def get_cooldown(user_id_str: str) -> float:
    if not supabase: return 0.0
    try:
        response = await supabase.table('cooldowns').select('last_cooldown_timestamp').eq('user_id', user_id_str).limit(1).execute()
        if response.data and response.data[0]['last_cooldown_timestamp'] is not None:
            return float(response.data[0]['last_cooldown_timestamp'])
        return 0.0
    except Exception as e: logger.error(f"[DB Error] get_cooldowns: {e}", exc_info=True); return 0.0

async def set_cooldown(user_id_str: str, timestamp: float):
    if not supabase: return
    try: await supabase.table('cooldowns').upsert({"user_id": user_id_str, "last_cooldown_timestamp": timestamp}, on_conflict="user_id").execute()
    except Exception as e: logger.error(f"[DB Error] set_cooldown: {e}", exc_info=True)
