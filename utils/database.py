# utils/database.py (새로운 동적 시스템을 지원하는 최종 수정본)

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

# --- [수정] 자동 역할 패널/버튼 관리 (최적화 적용) ---
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

# [신규] 특정 패널의 모든 버튼을 삭제하는 함수
async def delete_all_buttons_for_panel(message_id: int):
    if not supabase: return
    try: await supabase.table('auto_roles').delete().eq('message_id', message_id).execute()
    except Exception as e: logger.error(f"[DB Error] delete_all_buttons_for_panel: {e}", exc_info=True)

# [신규] 여러 버튼을 한번에 추가하는 함수
async def bulk_add_auto_role_buttons(buttons_data: list[dict]):
    if not supabase or not buttons_data: return
    try: await supabase.table('auto_roles').insert(buttons_data).execute()
    except Exception as e: logger.error(f"[DB Error] bulk_add_auto_role_buttons: {e}", exc_info=True)

# --- ⬇️ [유지] 기존 기능 함수 섹션 ⬇️ ---
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
            _cached_channel_configs[channel_id] = channel_id
            return channel_id
        return None
    except Exception as e: logger.error(f"[DB Error] get_channel_id_from_db: {e}", exc_info=True); return None
