# bot-management/utils/ui_defaults.py
"""
봇이 사용하는 모든 UI 요소 및 핵심 매핑 데이터의 기본값을 정의하는 파일입니다.
봇이 시작될 때 이 파일의 데이터가 Supabase 데이터베이스에 동기화됩니다.
"""

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 1. 역할 키 맵 (Role Key Map)
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
UI_ROLE_KEY_MAP = {
    # --- 관리/스태프 역할 ---
    "role_admin_total":         {"name": "森の妖精", "is_prefix": True, "priority": 100},
    "role_staff_village_chief": {"name": "村長", "is_prefix": True, "priority": 90},
    "role_staff_deputy_chief":  {"name": "副村長", "is_prefix": True, "priority": 85},
    "role_staff_police":        {"name": "交番さん", "is_prefix": True, "priority": 80},
    "role_staff_festival":      {"name": "お祭り係", "is_prefix": True, "priority": 70},
    "role_staff_pr":            {"name": "ビラ配りさん", "is_prefix": True, "priority": 70},
    "role_staff_design":        {"name": "村の絵描きさん", "is_prefix": True, "priority": 70},
    "role_staff_secretary":     {"name": "書記", "is_prefix": True, "priority": 70},
    "role_staff_newbie_helper": {"name": "お世話係", "is_prefix": True, "priority": 70},
    "role_approval":            {"name": "役場の職員", "is_prefix": True, "priority": 60},

    # --- 주민 등급 역할 ---
    "role_premium_booster":     {"name": "支援者", "is_prefix": True, "priority": 55},
    "role_resident_elder":      {"name": "長老", "is_prefix": True, "priority": 50},
    "role_resident_veteran":    {"name": "ベテラン住民", "is_prefix": False, "priority": 40},
    "role_resident_regular":    {"name": "おなじみ住民", "is_prefix": False, "priority": 30},
    "role_resident_rookie":     {"name": "かけだし住民", "is_prefix": False, "priority": 20},
    "role_resident":            {"name": "住民", "is_prefix": True, "priority": 10},
    "role_guest":               {"name": "旅の人", "is_prefix": True, "priority": 5},
    "role_personal_room_key":   {"name": "個人部屋の鍵", "is_prefix": False, "priority": 0},
    
    # --- 온보딩/역할 패널 구분선 역할 ---
    "role_onboarding_step_1":   {"name": "════════════ゲーム══════════", "is_prefix": False, "priority": 0},
    "role_onboarding_step_2":   {"name": "═════════════通知═══════════", "is_prefix": False, "priority": 0},
    "role_onboarding_step_3":   {"name": "═════════════情報═══════════", "is_prefix": False, "priority": 0},
    "role_onboarding_step_4":   {"name": "═════════════等級═══════════", "is_prefix": False, "priority": 0},

    # --- 개인 정보 역할 (성별, 연령대) ---
    "role_info_male":           {"name": "男性", "is_prefix": False, "priority": 0},
    "role_info_female":         {"name": "女性", "is_prefix": False, "priority": 0},
    "role_info_age_private":    {"name": "非公開", "is_prefix": False, "priority": 0},
    "role_info_age_70s":        {"name": "70年代生", "is_prefix": False, "priority": 0},
    "role_info_age_80s":        {"name": "80年代生", "is_prefix": False, "priority": 0},
    "role_info_age_90s":        {"name": "90年代生", "is_prefix": False, "priority": 0},
    "role_info_age_00s":        {"name": "00年代生", "is_prefix": False, "priority": 0},

    # --- 알림 역할 ---
    "role_notify_voice":        {"name": "通話", "is_prefix": False, "priority": 0},
    "role_notify_friends":      {"name": "友達", "is_prefix": False, "priority": 0},
    "role_notify_disboard":     {"name": "Disboard", "is_prefix": False, "priority": 0},
    "role_notify_up":           {"name": "Up", "is_prefix": False, "priority": 0},

    # --- 게임/플랫폼 역할 ---
    "role_game_minecraft":      {"name": "マインクラフト", "is_prefix": False, "priority": 0},
    "role_game_valorant":       {"name": "ヴァロラント", "is_prefix": False, "priority": 0},
    "role_game_overwatch":      {"name": "オーバーウォッチ", "is_prefix": False, "priority": 0},
    "role_game_lol":            {"name": "リーグ・オブ・レジェンド", "is_prefix": False, "priority": 0},
    "role_game_mahjong":        {"name": "麻雀", "is_prefix": False, "priority": 0},
    "role_game_amongus":        {"name": "アモングアス", "is_prefix": False, "priority": 0},
    "role_game_mh":             {"name": "モンスターハンター", "is_prefix": False, "priority": 0},
    "role_game_genshin":        {"name": "原神", "is_prefix": False, "priority": 0},
    "role_game_apex":           {"name": "エーペックスレジェンズ", "is_prefix": False, "priority": 0},
    "role_game_splatoon":       {"name": "スプラトゥーン", "is_prefix": False, "priority": 0},
    "role_game_gf":             {"name": "ゴッドフィールド", "is_prefix": False, "priority": 0},
    "role_platform_steam":      {"name": "スチーム", "is_prefix": False, "priority": 0},
    "role_platform_smartphone": {"name": "スマートフォン", "is_prefix": False, "priority": 0},
    "role_platform_switch":     {"name": "スイッチ", "is_prefix": False, "priority": 0},
}

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 2. 임베드(Embed) 기본값
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
UI_EMBEDS = {
    # --- 서버 입장/퇴장 ---
    "welcome_embed": {"title": "🎉 {guild_name}へようこそ！", "description": "{member_mention}さん、はじめまして！\n\nまずは、サーバーの案内を読んで、自己紹介の作成をお願いします。", "color": 0x3498DB},
    "farewell_embed": {"title": "👋 また会いましょう", "description": "{member_name}さんが村から旅立ちました。", "color": 0x99AAB5},
    # --- 패널 ---
    "panel_roles": {"title": "📖 役割付与", "description": "下のメニューからカテゴリーを選択して、自分に必要な役割を受け取ってください。", "color": 0x5865F2},
    "panel_onboarding": {"title": "📝 村役場・案内所", "description": "初めての方は、まず「案内を読む」ボタンを押して、サーバーでの過ごし方を確認してください。", "color": 0x5865F2},
    "panel_nicknames": {"title": "✒️ 名前変更", "description": "村で使う名前を変更したい場合は、下のボタンから申請してください。", "color": 0x5865F2},
    # --- 온보딩 프로세스 ---
    "embed_onboarding_info_roles": {"title": "📖 役割付与 (情報)", "description": "次に、ご自身の情報を表す役割を選択してください。\n\nこの情報は、他の住民があなたをよりよく知るのに役立ちます。（非公開も可能です）", "color": 0x5865F2},
    "embed_onboarding_final_rules": {"title": "📝 最終確認", "description": "ありがとうございます！\n\n最後に、村のルールをもう一度確認してください。\n\n- 他の住民を尊重し、迷惑をかけないこと。\n- 問題が発生した場合は、すぐに村役場（管理者）に報告すること。\n\n下のボタンを押すと、住民登録票の作成に進みます。", "color": 0x3498DB},
    "embed_onboarding_approval": {"title": "📝 新しい住民登録票", "description": "{member_mention}さんが住民登録票を提出しました。", "color": 0xE67E22},
    "embed_main_chat_welcome": {"description": "🎉 {member_mention}さんが新しい住民になりました！これからよろしくお願いします！", "color": 0x2ECC71},
    "embed_introduction_log": {"title": "📝 自己紹介", "description": "新しい住民がやってきました！みんなで歓迎しましょう！", "color": 0x2ECC71},
}

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 3. 패널 컴포넌트(Panel Components) 기본값
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
UI_PANEL_COMPONENTS = [
    {"component_key": "start_onboarding_guide", "panel_key": "onboarding", "component_type": "button", "label": "案内を読む", "style": "success", "emoji": "📖", "row": 0},
    {"component_key": "request_nickname_change", "panel_key": "nicknames", "component_type": "button", "label": "名前変更申請", "style": "primary", "emoji": "✒️", "row": 0},
]

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 4. /setup 명령어 설정 맵
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
SETUP_COMMAND_MAP = {
    # --- [채널/패널 설정] ---
    "panel_roles":      {"type": "panel",   "cog_name": "RolePanel",    "key": "auto_role_channel_id",            "friendly_name": "역할 자동부여 패널", "channel_type": "text"},
    "panel_onboarding": {"type": "panel",   "cog_name": "Onboarding",   "key": "onboarding_panel_channel_id",     "friendly_name": "서버 안내 패널", "channel_type": "text"},
    "panel_nicknames":  {"type": "panel",   "cog_name": "Nicknames",    "key": "nickname_panel_channel_id",       "friendly_name": "닉네임 변경 패널", "channel_type": "text"},
    
    "channel_new_welcome": {"type": "channel", "cog_name": "MemberEvents", "key": "new_welcome_channel_id",      "friendly_name": "신규 멤버 환영 채널", "channel_type": "text"},
    "channel_farewell":    {"type": "channel", "cog_name": "MemberEvents", "key": "farewell_channel_id",         "friendly_name": "멤버 퇴장 안내 채널", "channel_type": "text"},
    "channel_main_chat":   {"type": "channel", "cog_name": "Onboarding",   "key": "main_chat_channel_id",        "friendly_name": "메인 채팅 채널 (자기소개 승인 후 안내)", "channel_type": "text"},

    "channel_onboarding_approval": {"type": "channel", "cog_name": "Onboarding", "key": "onboarding_approval_channel_id", "friendly_name": "자기소개 승인/거절 채널", "channel_type": "text"},
    "channel_nickname_approval":   {"type": "channel", "cog_name": "Nicknames",  "key": "nickname_approval_channel_id",   "friendly_name": "닉네임 변경 승인 채널", "channel_type": "text"},
    
    "channel_vc_creator_3p": {"type": "channel", "cog_name": "VoiceMaster", "key": "vc_creator_channel_id_3p", "friendly_name": "음성 채널 자동 생성 (게임)", "channel_type": "voice"},
    "channel_vc_creator_4p": {"type": "channel", "cog_name": "VoiceMaster", "key": "vc_creator_channel_id_4p", "friendly_name": "음성 채널 자동 생성 (광장)", "channel_type": "voice"},
    "channel_vc_creator_newbie": {"type": "channel", "cog_name": "VoiceMaster", "key": "vc_creator_channel_id_newbie", "friendly_name": "[음성 채널] 뉴비 전용 생성기", "channel_type": "voice"},
    "channel_vc_creator_vip":    {"type": "channel", "cog_name": "VoiceMaster", "key": "vc_creator_channel_id_vip", "friendly_name": "[음성 채널] VIP 전용 생성기", "channel_type": "voice"},

    # [수정] channel_type을 "text"로 변경
    "panel_inquiry": {"type": "panel", "cog_name": "TicketSystem", "key": "inquiry_panel_channel_id", "friendly_name": "[티켓] 문의/건의 패널", "channel_type": "text"},
    "panel_report":  {"type": "panel", "cog_name": "TicketSystem", "key": "report_panel_channel_id",  "friendly_name": "[티켓] 유저 신고 패널", "channel_type": "text"},
    
    # --- [로그 채널 설정] ---
    "log_nickname":          {"type": "channel", "cog_name": "Nicknames",  "key": "nickname_log_channel_id",                "friendly_name": "[로그] 닉네임 변경 기록", "channel_type": "text"},
    "log_intro_approval":    {"type": "channel", "cog_name": "Onboarding", "key": "introduction_channel_id",                "friendly_name": "[로그] 자기소개 승인 기록", "channel_type": "text"},
    "log_intro_rejection":   {"type": "channel", "cog_name": "Onboarding", "key": "introduction_rejection_log_channel_id",  "friendly_name": "[로그] 자기소개 거절 기록", "channel_type": "text"},
    
    # --- [로그 채널 설정] ---
    "log_nickname":          {"type": "channel", "cog_name": "Nicknames",  "key": "nickname_log_channel_id",                "friendly_name": "[로그] 닉네임 변경 기록", "channel_type": "text"},
    "log_intro_approval":    {"type": "channel", "cog_name": "Onboarding", "key": "introduction_channel_id",                "friendly_name": "[로그] 자기소개 승인 기록", "channel_type": "text"},
    "log_intro_rejection":   {"type": "channel", "cog_name": "Onboarding", "key": "introduction_rejection_log_channel_id",  "friendly_name": "[로그] 자기소개 거절 기록", "channel_type": "text"},

    # --- [신규] 아래 로그 채널 설정들을 추가 ---
    "log_message": {"type": "channel", "cog_name": "MessageLogger", "key": "log_channel_message", "friendly_name": "[로그] 메시지 (수정/삭제)", "channel_type": "text"},
    "log_voice":   {"type": "channel", "cog_name": "VoiceLogger",   "key": "log_channel_voice",   "friendly_name": "[로그] 음성 채널 (참여/이동/퇴장)", "channel_type": "text"},
    "log_member":  {"type": "channel", "cog_name": "MemberLogger",  "key": "log_channel_member",  "friendly_name": "[로그] 멤버 활동 (역할 부여/닉네임)", "channel_type": "text"},
    "log_channel": {"type": "channel", "cog_name": "ChannelLogger", "key": "log_channel_channel", "friendly_name": "[로그] 채널 관리 (생성/삭제/변경)", "channel_type": "text"},
    "log_server":  {"type": "channel", "cog_name": "ServerLogger",  "key": "log_channel_server",  "friendly_name": "[로그] 서버 및 역할 관리", "channel_type": "text"},
}

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 5. 관리자 역할 키 목록
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
ADMIN_ROLE_KEYS = [
    "role_admin_total",
    "role_staff_village_chief",
    "role_staff_deputy_chief",
    "role_staff_police",
    "role_staff_festival",
    "role_staff_pr",
    "role_staff_design",
    "role_staff_secretary",
    "role_staff_newbie_helper",
    "role_approval",
]


# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 7. 티켓 시스템 설정
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

# [수정] '문의' 담당 역할을 세분화
# 촌장/부촌장 (항상 초대됨)
TICKET_MASTER_ROLES = [
    "role_staff_village_chief",
    "role_staff_deputy_chief",
]

# 역장 직원 전체 (선택지 1)
TICKET_STAFF_GENERAL_ROLES = [
    "role_approval", # 役場の職員
]

# 특정 담당자 (선택지 2)
TICKET_STAFF_SPECIFIC_ROLES = [
    "role_staff_police",
    "role_staff_festival",
    "role_staff_pr",
    "role_staff_design",
    "role_staff_secretary",
    "role_staff_newbie_helper",
]

# '유저 신고' 티켓 생성 시 자동으로 초대될 역할 키 목록
TICKET_REPORT_ROLES = [
    "role_staff_police", # 交番さん
]
