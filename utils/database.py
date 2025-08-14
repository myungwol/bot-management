import os
import discord
from supabase import create_client, AsyncClient
import logging
import re

# 로깅 설정
logger = logging.getLogger(__name__)

# --- ⬇️ 역할 ID 등 핵심 데이터 관리 ⬇️ ---
ROLE_ID_CONFIG = {
    "admin_total": 1405325594228424795, "approval_role": 1405325627384402032,
    "temp_user_role": 1405325658871042100, "guest_role": 1405325653347405905, "mention_role_1": 1405328830327029921,
    "role_onboarding_step_1": 1405326693975195829, "role_onboarding_step_2": 1405326692662116555,
    "role_onboarding_step_3": 1405326186833514516, "role_onboarding_step_4": 1405325631918444598,
    "age_70s_role": 1405325674499276840, "age_80s_role": 1405325679142375435,
    "age_90s_role": 1405325683822952603, "age_00s_role": 1405325688281628804, "age_private_role": 1405325668845097124,
}
AUTO_ROLE_MAPPING = [
    {"field_name": "性別", "keywords": ["男", "男性", "おとこ", "オトコ", "man", "male"], "role_id": 1405489827884830742},
    {"field_name": "性別", "keywords": ["女", "女性", "おんな", "オンナ", "woman", "female"], "role_id": 1405489828908367972},
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
    if not supabase: return
    try: await supabase.table('panel_data').upsert({"panel_name": panel_name, "message_id": message_id, "channel_id": channel_id}, on_conflict="panel_name").execute()
    except Exception as e: logger.error(f"[DB Error] save_panel_id: {e}", exc_info=True)
async def get_panel_id(panel_name: str) -> dict | None:
    if not supabase: return None
    try:
        res = await supabase.table('panel_data').select('message_id, channel_id').eq('panel_name', panel_name).limit(1).execute()
        return res.data[0] if res.data else None
    except Exception as e: logger.error(f"[DB Error] get_panel_id: {e}", exc_info=True); return None
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
    except Exception as e: logger.error(f"[DB Error] get_all_auto_role_panels: {e}", exc_info=True); return []
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
    except Exception as e: logger.error(f"[DB Error] get_auto_role_buttons: {e}", exc_info=True); return []

# --- ⬇️ [복구] 기존 기능 함수 섹션 ⬇️ ---
_cached_channel_configs: dict = {}
def get_role_id(key: str) -> int | None:
    role_id = ROLE_ID_CONFIG.get(key)
    if role_id is None: logger.warning(f"[get_role_id] Role ID for key '{key}' not set.")
    return role_id
async def get_counter_configs():
    if not supabase: return []
    try: return (await supabase.table('channel_counters').select('*').execute()).data or []
    except Exception as e: logger.error(f"[DB Error] get_counter_configs: {e}", exc_info=True); return []
async def get_or_create_user(table_name: str, user_id_str: str, default_data: dict):
    if not supabase: return {}
    try:
        response = await supabase.table(table_name).select("*").eq("user_id", user_id_str).limit(1).execute()
        if response.data: return response.data[0]
        insert_data = {"user_id": user_id_str, **default_data}
        return (await supabase.table(table_name).insert(insert_data, returning="representation").execute()).data[0] or {}
    except Exception as e: logger.error(f"[DB Error] get_or_create_user on '{table_name}': {e}", exc_info=True); return {}
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
async def get_activity_data(user_id_str: str):
    return await get_or_create_user('activity_data', user_id_str, {"chat_counts":0, "voice_minutes":0}) or {}
async def save_channel_id_to_db(channel_key: str, object_id: int):
    if not supabase: return
    try:
        await supabase.table('channel_configs').upsert({"channel_key": channel_key, "channel_id": object_id}, on_conflict="channel_key").execute()
        _cached_channel_configs[channel_key] = object_id
    except Exception as e: logger.error(f"[DB Error] save_channel_id_to_db: {e}", exc_info=True)
async def get_all_channel_configs():
    global _cached_channel_configs
    if not supabase: return {}
    try:
        response = await supabase.table('channel_configs').select('channel_key, channel_id').execute()
        _cached_channel_configs = {item['channel_key']: item['channel_id'] for item in response.data} if response.data else {}
        return _cached_channel_configs
    except Exception as e: logger.error(f"[DB Error] get_all_channel_configs: {e}", exc_info=True); return {}
async def get_channel_id_from_db(channel_key: str) -> int | None:
    if channel_key in _cached_channel_configs: return _cached_channel_configs[channel_key]
    if not supabase: return None
    try:
        response = await supabase.table('channel_configs').select('channel_id').eq('channel_key', channel_key).limit(1).execute()
        if response.data:
            channel_id = response.data[0]['channel_id']
            _cached_channel_configs[channel_key] = channel_id
            return channel_id
        return None
    except Exception as e: logger.error(f"[DB Error] get_channel_id_from_db: {e}", exc_info=True); return None
# --- [복구] 하드코딩된 게임 데이터베이스 ---
ITEM_DATABASE = {
    "住人票Lv.1": {"id": 1404444315383500811, "price": 100, "category": "里の役職", "description": "基本的な特典が含まれています。", "emoji": "1️⃣", "buyable": True, "sellable": False},
    "住人票Lv.2": {"id": 1404444316021035019, "price": 50, "category": "里の役職", "description": "追加のチャンネルへのアクセスが可能になります。", "emoji": "2️⃣", "buyable": True, "sellable": False},
    "仮住人": {"id": 1404444316843376721, "price": 10, "category": "里の役職", "description": "里の雰囲気を体験できます。", "emoji": "🧑‍🌾", "buyable": True, "sellable": False},
    "一般の釣りエサ": {"price": 5, "sell_price": 2, "category": "釣り", "buyable": True, "sellable": True, "description": "魚のアタリが来るまでの時間を短縮します。(5～10秒)", "emoji": "🐛", "bite_time_range": (5.0, 10.0)},
}
FISHING_LOOT = [
    {"name": "古びた長靴", "emoji": "👢", "weight": 200, "value": 0},
    {"name": "エビ", "emoji": "🦐", "weight": 250, "min_size": 5, "max_size": 15, "base_value": 5, "size_multiplier": 0.5},
]
        return None
    except Exception as e: logger.error(f"[DB Error] get_channel_id_from_db: {e}", exc_info=True); return None
