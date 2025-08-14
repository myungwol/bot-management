import os
import discord
from supabase import create_client, AsyncClient
import logging
import re

# 로깅 설정
logger = logging.getLogger(__name__)

# --- ⬇️ 역할 ID를 이곳에서 모두 관리합니다 ⬇️ ---
# ◀◀◀ 여기에 있는 모든 '123...' 가짜 ID를 실제 디스코드 서버 역할 ID로 변경하세요! ◀◀◀
ROLE_ID_CONFIG = {
    # --- 관리자 및 직원 역할 ---
    "admin_total": 1405325594228424795,
    "approval_role": 1405325627384402032,

    # --- 온보딩(신규 유저) 관련 역할 ---
    "temp_user_role": 1405325658871042100,
    "guest_role": 1405325653347405905,
    "mention_role_1": 1405328830327029921,

    # --- 온보딩 가이드 진행 중 부여/제거될 역할 ---
    "role_onboarding_step_1": 1405326693975195829,
    "role_onboarding_step_2": 1405326692662116555,
    "role_onboarding_step_3": 1405326186833514516,
    "role_onboarding_step_4": 1405325631918444598,

    # --- 나이 관련 역할 ---
    "age_70s_role": 1405325674499276840,  # 70년대생 역할 ID
    "age_80s_role": 1405325679142375435,  # 80년대생 역할 ID
    "age_90s_role": 1405325683822952603,  # 90년대생 역할 ID
    "age_00s_role": 1405325688281628804,  # 00년대생 역할 ID
    "age_private_role": 1405325668845097124,  # 나이 비공개 역할 ID
}

# --- ⬇️ 자기소개 기반 자동 역할 부여 규칙 (성별) ⬇️ ---
# [수정] 일본어 키워드로 변경
AUTO_ROLE_MAPPING = [
    {
        "field_name": "性別",
        "keywords": ["男", "男性", "おとこ", "オトコ", "man", "male"],
        "role_id": 1405489827884830742  # ◀◀◀ '남자' 역할 ID 변경 필수
    },
    {
        "field_name": "性別",
        "keywords": ["女", "女性", "おんな", "オンナ", "woman", "female"],
        "role_id": 1405489828908367972  # ◀◀◀ '여자' 역할 ID 변경 필수
    },
]

# --- Supabase 클라이언트 초기화 ---
supabase: AsyncClient = None
try:
    url: str = os.environ.get("SUPABASE_URL")
    key: str = os.environ.get("SUPABASE_KEY")
    if not url or not key: raise ValueError("SUPABASE_URL 또는 SUPABASE_KEY 환경 변수가 설정되지 않았습니다.")
    supabase = AsyncClient(supabase_url=url, supabase_key=key)
    logger.info("✅ Supabase 비동기 클라이언트가 성공적으로 생성되었습니다.")
except Exception as e:
    logger.error(f"❌ Supabase 클라이언트 생성 실패: {e}", exc_info=True)


# --- ⬇️ 패널 및 DB 관리 함수 섹션 (수정 완료) ⬇️ ---
async def save_embed_to_db(embed_key: str, embed_data: dict):
    if not supabase: return
    try: await supabase.table('embeds').upsert({'embed_key': embed_key, 'embed_data': embed_data}).execute()
    except Exception as e: logger.error(f"[DB Error] save_embed_to_db: {e}", exc_info=True)

async def get_embed_from_db(embed_key: str) -> dict | None:
    if not supabase: return None
    try:
        response = await supabase.table('embeds').select('embed_data').eq('embed_key', embed_key).limit(1).execute()
        return response.data[0]['embed_data'] if response.data else None
    except Exception as e:
        logger.error(f"[DB Error] get_embed_from_db: {e}", exc_info=True)
        return None

async def delete_embed_from_db(embed_key: str):
    if not supabase: return
    try: await supabase.table('embeds').delete().eq('embed_key', embed_key).execute()
    except Exception as e: logger.error(f"[DB Error] delete_embed_from_db: {e}", exc_info=True)

async def save_panel_id(panel_name: str, message_id: int, channel_id: int):
    if not supabase: return
    try: await supabase.table('panel_data').upsert({"panel_name": panel_name, "message_id": message_id, "channel_id": channel_id}, on_conflict="panel_name").execute()
    except Exception as e: logger.error(f"[DB Error] save_panel_id: {e}", exc_info=True)

async def get_panel_id(panel_name: str) -> dict | None:
    if not supabase: return None
    try:
        res = await supabase.table('panel_data').select('message_id, channel_id').eq('panel_name', panel_name).limit(1).execute()
        return res.data[0] if res.data else None
    except Exception as e:
        logger.error(f"[DB Error] get_panel_id: {e}", exc_info=True)
        return None

async def delete_panel_id(panel_name: str):
    if not supabase: return
    try: await supabase.table('panel_data').delete().eq('panel_name', panel_name).execute()
    except Exception as e: logger.error(f"[DB Error] delete_panel_id: {e}", exc_info=True)

async def add_auto_role_panel(message_id: int, guild_id: int, channel_id: int, title: str, description: str):
    if not supabase: return
    try: await supabase.table('auto_role_panels').upsert({'message_id': message_id, 'guild_id': guild_id, 'channel_id': channel_id, 'title': title, 'description': description}, on_conflict='message_id').execute()
    except Exception as e: logger.error(f"[DB Error] add_auto_role_panel: {e}", exc_info=True)

async def get_all_auto_role_panels():
    if not supabase: return []
    try:
        response = await supabase.table('auto_role_panels').select('*').execute()
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"[DB Error] get_all_auto_role_panels: {e}", exc_info=True)
        return []

async def delete_auto_role_panel(message_id: int):
    if not supabase: return
    try: await supabase.table('auto_role_panels').delete().eq('message_id', message_id).execute()
    except Exception as e: logger.error(f"[DB Error] delete_auto_role_panel: {e}", exc_info=True)

async def delete_all_buttons_for_panel(message_id: int):
    if not supabase: return
    try: await supabase.table('auto_roles').delete().eq('message_id', message_id).execute()
    except Exception as e: logger.error(f"[DB Error] delete_all_buttons_for_panel: {e}", exc_info=True)

async def bulk_add_auto_role_buttons(buttons_data: list[dict]):
    if not supabase or not buttons_data: return
    try: await supabase.table('auto_roles').insert(buttons_data).execute()
    except Exception as e: logger.error(f"[DB Error] bulk_add_auto_role_buttons: {e}", exc_info=True)

async def get_auto_role_buttons(message_id: int):
    if not supabase: return []
    try:
        response = await supabase.table('auto_roles').select('*').eq('message_id', message_id).execute()
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"[DB Error] get_auto_role_buttons: {e}", exc_info=True)
        return []

# --- ⬇️ 기존 기능 함수 섹션 (모든 누락 함수 복구 완료) ⬇️ ---
_cached_channel_configs: dict = {}
def get_role_id(key: str) -> int | None:
    role_id = ROLE_ID_CONFIG.get(key)
    if role_id is None: logger.warning(f"[get_role_id] Role ID for key '{key}' not set.")
    return role_id

def get_auto_role_mappings() -> list: # <--- 복구된 함수
    return AUTO_ROLE_MAPPING

async def get_counter_configs():
    if not supabase: return []
    try:
        response = await supabase.table('channel_counters').select('*').execute()
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"[DB Error] get_counter_configs: {e}", exc_info=True)
        return []

async def add_counter_config(channel_id: int, guild_id: int, counter_type: str, format_string: str, role_id: int = None): # <--- 복구된 함수
    if not supabase: return
    try:
        await supabase.table('channel_counters').upsert({'channel_id': channel_id, 'guild_id': guild_id, 'counter_type': counter_type, 'format_string': format_string, 'role_id': role_id}, on_conflict='channel_id').execute()
    except Exception as e: logger.error(f"[DB Error] add_counter_config: {e}", exc_info=True)

async def remove_counter_config(channel_id: int): # <--- 복구된 함수
    if not supabase: return
    try: await supabase.table('channel_counters').delete().eq('channel_id', channel_id).execute()
    except Exception as e: logger.error(f"[DB Error] remove_counter_config: {e}", exc_info=True)

async def get_or_create_user(table_name: str, user_id_str: str, default_data: dict):
    if not supabase: return {}
    try:
        response = await supabase.table(table_name).select("*").eq("user_id", user_id_str).limit(1).execute()
        if response.data: return response.data[0]
        insert_data = {"user_id": user_id_str, **default_data}
        response = await supabase.table(table_name).insert(insert_data, returning="representation").execute()
        return response.data[0] if response.data else {}
    except Exception as e:
        logger.error(f"[DB Error] get_or_create_user on '{table_name}': {e}", exc_info=True)
        return {}

async def get_wallet(user_id: int): # <--- 복구된 함수
    return await get_or_create_user('wallets', str(user_id), {"balance": 0}) or {"balance": 0}

async def update_wallet(user: discord.User, amount: int): # <--- 복구된 함수
    user_id_str = str(user.id)
    if not supabase: return None
    try:
        params = {'user_id_param': user_id_str, 'amount_param': amount}
        response = await supabase.rpc('increment_wallet_balance', params).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logger.error(f"[DB Error] update_wallet_rpc: {e}", exc_info=True)
        return None

async def get_inventory(user_id_str: str): # <--- 복구된 함수
    if not supabase: return {}
    try:
        response = await supabase.table('inventories').select('item_name, quantity').eq('user_id', user_id_str).gt('quantity', 0).execute()
        return {item['item_name']: item['quantity'] for item in response.data}
    except Exception as e:
        logger.error(f"[DB Error] get_inventory: {e}", exc_info=True)
        return {}

async def update_inventory(user_id_str: str, item_name: str, quantity: int): # <--- 복구된 함수
    if not supabase: return
    try:
        params = {'user_id_param': user_id_str, 'item_name_param': item_name, 'amount_param': quantity}
        await supabase.rpc('increment_inventory_quantity', params).execute()
    except Exception as e:
        logger.error(f"[DB Error] update_inventory: {e}", exc_info=True)

async def get_aquarium(user_id_str: str): # <--- 복구된 함수
    if not supabase: return []
    try:
        response = await supabase.table('aquariums').select('id, name, size, emoji').eq('user_id', user_id_str).execute()
        return response.data
    except Exception as e: logger.error(f"[DB Error] get_aquarium: {e}", exc_info=True); return []

async def add_to_aquarium(user_id_str: str, fish_data: dict): # <--- 복구된 함수
    if not supabase: return
    try:
        insert_data = {"user_id": user_id_str, **fish_data}
        await supabase.table('aquariums').insert(insert_data).execute()
    except Exception as e: logger.error(f"[DB Error] add_to_aquarium: {e}", exc_info=True)

async def remove_fish_from_aquarium(fish_id: int): # <--- 복구된 함수
    if not supabase: return
    try: await supabase.table('aquariums').delete().eq('id', fish_id).execute()
    except Exception as e: logger.error(f"[DB Error] remove_fish_from_aquarium: {e}", exc_info=True)

async def get_user_gear(user_id_str: str): # <--- 복구된 함수
    if not supabase: return {"rod": "素手", "bait": "エサなし"}
    gear = await get_or_create_user('gear_setups', user_id_str, {"rod": "古い釣竿", "bait": "エサなし"}) or {}
    inv = await get_inventory(user_id_str)
    rod = gear.get('rod', '素手')
    if rod not in ["素手", "古い釣竿"] and inv.get(rod, 0) <= 0: rod = "古い釣竿"
    bait = gear.get('bait', 'エサなし')
    if bait != "エサなし" and inv.get(bait, 0) <= 0: bait = "エサなし"
    return {"rod": rod, "bait": bait}

async def set_user_gear(user_id_str: str, rod: str = None, bait: str = None): # <--- 복구된 함수
    if not supabase: return
    try:
        await get_or_create_user('gear_setups', user_id_str, {"rod": "古い釣竿", "bait": "エサなし"})
        data_to_update = {}
        if rod is not None: data_to_update['rod'] = rod
        if bait is not None: data_to_update['bait'] = bait
        if data_to_update: await supabase.table('gear_setups').update(data_to_update).eq('user_id', user_id_str).execute()
    except Exception as e: logger.error(f"[DB Error] set_user_gear: {e}", exc_info=True)

async def get_activity_data(user_id_str: str): # <--- 복구된 함수
    return await get_or_create_user('activity_data', user_id_str, {"chat_counts":0, "voice_minutes":0}) or {}

async def update_activity_data(user_id_str: str, chat_increment=0, voice_increment=0, reset_chat=False, reset_voice=False): # <--- 복구된 함수
    if not supabase: return
    try:
        params = {'user_id_param': user_id_str, 'chat_increment_param': chat_increment, 'voice_increment_param': voice_increment, 'reset_chat_param': reset_chat, 'reset_voice_param': reset_voice}
        await supabase.rpc('increment_activity_data', params).execute()
    except Exception as e: logger.error(f"[DB Error] update_activity_data: {e}", exc_info=True)

async def get_cooldown(user_id_str: str) -> float: # <--- 복구된 함수
    if not supabase: return 0.0
    try:
        response = await supabase.table('cooldowns').select('last_cooldown_timestamp').eq('user_id', user_id_str).limit(1).execute()
        if response.data and response.data[0]['last_cooldown_timestamp'] is not None:
            return float(response.data[0]['last_cooldown_timestamp'])
        return 0.0
    except Exception as e: logger.error(f"[DB Error] get_cooldowns: {e}", exc_info=True); return 0.0

async def set_cooldown(user_id_str: str, timestamp: float): # <--- 복구된 함수
    if not supabase: return
    try: await supabase.table('cooldowns').upsert({"user_id": user_id_str, "last_cooldown_timestamp": timestamp}, on_conflict="user_id").execute()
    except Exception as e: logger.error(f"[DB Error] set_cooldown: {e}", exc_info=True)

# --- 하드코딩된 게임 데이터베이스 (유지) ---
CURRENCY_ICON = "🪙"
ROLE_PREFIX_MAPPING = {
    933077535405789205: "一", 933077534994755654: "二", 933077536253050970: "三", 1209471813319528468: "四", 1209471813319528468: "五",
    1209471819866841149: "六", 1209471820559032320: "七", 1209471821166944266: "八", 1209471821632770099: "九",
}
ROD_HIERARCHY = ["古い釣竿", "カーボン釣竿", "専門家用の釣竿", "伝説の釣竿"]
ITEM_DATABASE = {
    "住人票Lv.1": {"id": 1404444315383500811, "price": 100, "category": "里の役職", "description": "基本的な特典が含まれています。", "emoji": "1️⃣", "buyable": True, "sellable": False},
    "住人票Lv.2": {"id": 1404444316021035019, "price": 50, "category": "里の役職", "description": "追加のチャンネルへのアクセスが可能になります。", "emoji": "2️⃣", "buyable": True, "sellable": False},
    "仮住人": {"id": 1404444316843376721, "price": 10, "category": "里の役職", "description": "里の雰囲気を体験できます。", "emoji": "🧑‍🌾", "buyable": True, "sellable": False},
    "一般の釣りエサ": {"price": 5, "sell_price": 2, "category": "釣り", "buyable": True, "sellable": True, "description": "魚のアタリが来るまでの時間を短縮します。(5～10秒)", "emoji": "🐛", "bite_time_range": (5.0, 10.0)},
    "高級釣りエサ": {"price": 20, "sell_price": 10, "category": "釣り", "buyable": True, "sellable": True, "description": "魚のアタリが来るまでの時間を大幅に短縮します。(4～8秒)", "emoji": "✨", "bite_time_range": (4.0, 8.0)},
    "古い釣竿": {"price": 100, "category": "釣り", "sellable": False, "buyable": True, "description": "最も基本的な釣竿です。", "emoji": "🎣", "good_fish_bonus": 0.0, "is_upgrade_item": True},
    "カーボン釣竿": {"price": 5000, "category": "釣り", "sellable": False, "buyable": True, "description": "珍しい魚が釣れる確率が少し増加します。(+5%)", "emoji": "🎣", "good_fish_bonus": 0.05, "is_upgrade_item": True},
    "専門家用の釣竿": {"price": 20000, "category": "釣り", "sellable": False, "buyable": True, "description": "珍しい魚が釣れる確率が目に見えて増加します。(+10%)", "emoji": "🏆", "good_fish_bonus": 0.10, "is_upgrade_item": True},
    "伝説の釣竿": {"price": 100000, "category": "釣り", "sellable": False, "buyable": True, "description": "伝説の魚も釣れるかもしれません。(+15%)", "emoji": "🌟", "good_fish_bonus": 0.15, "is_upgrade_item": True},
    "ジャガイモの種": {"price": 10, "sell_price": 5, "category": "農業", "description": "植えるとジャガイモが育ちます。成長時間：1時間", "emoji": "🥔", "buyable": True, "sellable": True},
    "ジャガイモ": {"sell_price": 25, "category": "農業", "description": "美味しく料理できる、よく育ったジャガイモです。", "emoji": "🥔", "buyable": False, "sellable": True},
    "鶏のエサ": {"price": 8, "sell_price": 4, "category": "牧場", "description": "鶏に与えると卵を産む可能性があります。", "emoji": "🌾", "buyable": True, "sellable": True}
}
FISHING_LOOT = [
    {"name": "古びた長靴", "emoji": "👢", "weight": 200, "value": 0},
    {"name": "エビ", "emoji": "🦐", "weight": 250, "min_size": 5, "max_size": 15, "base_value": 5, "size_multiplier": 0.5},
    {"name": "小魚", "emoji": "🐟", "weight": 250, "min_size": 10, "max_size": 30, "base_value": 8, "size_multiplier": 0.8},
    {"name": "イカ", "emoji": "🦑", "weight": 150, "min_size": 20, "max_size": 50, "base_value": 15, "size_multiplier": 1.2},
    {"name": "熱帯魚", "emoji": "🐠", "weight": 100, "min_size": 8, "max_size": 25, "base_value": 25, "size_multiplier": 1.5},
    {"name": "タコ", "emoji": "🐙", "weight": 45, "min_size": 50, "max_size": 90, "base_value": 50, "size_multiplier": 2.0},
    {"name": "フグ", "emoji": "🐡", "weight": 20, "value": (-30, -10)},
    {"name": "キラキラの宝箱", "emoji": "💎", "weight": 5, "value": (150, 300)},
    {"name": "クジラ", "emoji": "🐳", "weight": 1, "min_size": 100, "max_size": 250, "base_value": 300, "size_multiplier": 2.5},
]
