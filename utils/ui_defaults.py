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

    
    # --- 온보딩/역할 패널 구분선 역할 ---
    "role_onboarding_step_1":   {"name": "════════════ゲーム══════════", "is_prefix": False, "priority": 0},
    "role_onboarding_step_2":   {"name": "════════════通知════════════", "is_prefix": False, "priority": 0},
    "role_onboarding_step_3":   {"name": "════════════情報════════════", "is_prefix": False, "priority": 0},
    "role_onboarding_step_4":   {"name": "════════════等級════════════", "is_prefix": False, "priority": 0},
    "role_warning_separator":   {"name": "════════════警告════════════", "is_prefix": False, "priority": 0},
    "role_shop_separator":      {"name": "════════════商店════════════", "is_prefix": False, "priority": 0},
    
    # --- 개인 정보 역할 (성별, 연령대) ---
    "role_info_male":           {"name": "男性", "is_prefix": False, "priority": 0},
    "role_info_female":         {"name": "女性", "is_prefix": False, "priority": 0},
    "role_info_age_private":    {"name": "非公開", "is_prefix": False, "priority": 0},
    "role_info_age_70s":        {"name": "70年代生", "is_prefix": False, "priority": 0},
    "role_info_age_80s":        {"name": "80年代生", "is_prefix": False, "priority": 0},
    "role_info_age_90s":        {"name": "90年代生", "is_prefix": False, "priority": 0},
    "role_info_age_00s":        {"name": "00年代生", "is_prefix": False, "priority": 0},
    
    # --- 상점/아이템 역할 ---
    "role_item_event_priority": {"name": "イベント優先権", "is_prefix": False, "priority": 0},
    "role_item_warning_deduct": {"name": "警告1個差引権", "is_prefix": False, "priority": 0},
    "role_personal_room_key":   {"name": "個人部屋の鍵", "is_prefix": False, "priority": 0},

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

    # --- 경고 역할 ---
    "role_warning_level_1":     {"name": "警告1個", "is_prefix": False, "priority": 0},
    "role_warning_level_2":     {"name": "警告2個", "is_prefix": False, "priority": 0},
    "role_warning_level_3":     {"name": "警告3個", "is_prefix": False, "priority": 0},
    "role_warning_level_4":     {"name": "警告4個", "is_prefix": False, "priority": 0},
}

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 2. 임베드(Embed) 기본값
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
UI_EMBEDS = {
    # --- [서버 관리 봇] ---
    "welcome_embed": {"title": "🎉 {guild_name}へようこそ！", "description": "{member_mention}さん、はじめまして！\n\nまずは、サーバーの案内を読んで、自己紹介の作成をお願いします。", "color": 0x3498DB},
    "farewell_embed": {"title": "👋 また会いましょう", "description": "{member_name}さんが村から旅立ちました。", "color": 0x99AAB5},
    "panel_roles": {"title": "📖 役割付与", "description": "下のメニューからカテゴリーを選択して、自分に必要な役割を受け取ってください。", "color": 0x5865F2},
    "panel_onboarding": {"title": "📝 村役場・案内所", "description": "初めての方は、まず「案内を読む」ボタンを押して、サーバーでの過ごし方を確認してください。", "color": 0x5865F2},
    "panel_nicknames": {"title": "✒️ 名前変更", "description": "村で使う名前を変更したい場合は、下のボタンから申請してください。", "color": 0x5865F2},
    "embed_onboarding_info_roles": {"title": "📖 役割付与 (情報)", "description": "次に、ご自身の情報を表す役割を選択してください。\n\nこの情報は、他の住民があなたをよりよく知るのに役立ちます。（非公開も可能です）", "color": 0x5865F2},
    "embed_onboarding_final_rules": {"title": "📝 最終確認", "description": "ありがとうございます！\n\n最後に、村のルールをもう一度確認してください。\n\n- 他の住民を尊重し、迷惑をかけないこと。\n- 問題が発生した場合は、すぐに村役場（管理者）に報告すること。\n\n下のボタンを押すと、住民登録票の作成に進みます。", "color": 0x3498DB},
    "embed_onboarding_approval": {"title": "📝 新しい住民登録票", "description": "{member_mention}さんが住民登録票を提出しました。", "color": 0xE67E22},
    "embed_main_chat_welcome": {"description": "🎉 {member_mention}さんが新しい住民になりました！これからよろしくお願いします！", "color": 0x2ECC71},
    "embed_introduction_log": {"title": "📝 自己紹介", "description": "新しい住民がやってきました！みんなで歓迎しましょう！", "color": 0x2ECC71},
    "panel_warning": {"title": "🚨 警告管理パネル", "description": "サーバーのルールに違反したユーザーに対して、下のボタンから警告を発行できます。\n\n**この機能は`交番さん`のみ使用可能です。**", "color": 15548997},
    "log_warning": {"title": "🚨 警告発行通知", "color": 15548997},
    "log_item_use": {"title": "🛒 アイテム使用通知", "color": 11027200},
    "panel_item_usage": {"title": "✅ 警告差引権使用", "description": "所持している<@&1406959582500225087>を使用するには、下のボタンを押してください。", "color": 11027200},
    "dm_onboarding_approved": {"title": "✅ 住民登録完了のお知らせ", "description": "「{guild_name}」での住民登録が承認されました。\nこれからよろしくお願いします！", "color": 3066993},
    "dm_onboarding_rejected": {"title": "❌ 住民登録拒否のお知らせ", "description": "申し訳ありませんが、「{guild_name}」での住民登録は拒否されました。", "color": 15548997},
    "panel_anonymous_board": {"title": "🤫 匿名の声", "description": "誰にも知られずにあなたの考えや気持ちを共有しましょう。\n下のボタンを押して、1日に1回メッセージを投稿できます。", "color": 4342323},
    "anonymous_message": {"title": "匿名の声が届きました", "color": 16777215},
    
    # --- [게임 봇] ---
    "panel_commerce": {"title": "🏪 Dico森商店＆買取ボックス", "description": "アイテムを買ったり、釣った魚などを売ったりできます。", "color": 0x5865F2},
    "panel_profile": {"title": "📦 持ち物", "description": "自分の所持金やアイテム、装備などを確認できます。", "color": 0x5865F2},
    "embed_transfer_confirmation": {"title": "💸 送金確認", "description": "本当に {recipient_mention}さんへ `{amount}`{currency_icon} を送金しますか？", "color": 0xE67E22},
    "log_coin_gain": {"description": "{user_mention}さんが**{reason}**で`{amount}`{currency_icon}を獲得しました。", "color": 0x2ECC71},
    "log_coin_transfer": {"description": "💸 {sender_mention}さんが{recipient_mention}さんへ`{amount}`{currency_icon}を送金しました。", "color": 0x3498DB},
    "log_coin_admin": {"description": "⚙️ {admin_mention}さんが{target_mention}さんのコインを`{amount}`{currency_icon}だけ**{action}**しました。", "color": 0x3498DB},
    "panel_fishing_river": {"title": "🏞️ 川の釣り場", "description": "川辺でのんびり釣りを楽しみましょう。\n下のボタンを押して釣りを開始します。", "color": 0x5865F2},
    "panel_fishing_sea": {"title": "🌊 海の釣り場", "description": "広い海で大物の夢を追いかけましょう！\n下のボタンを押して釣りを開始します。", "color": 0x3498DB},
    "panel_atm": {"title": "🏧 Dico森 ATM", "description": "下のボタンから、他の住民にコインを送金できます。", "color": 0x2ECC71},
}

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 3. 패널 컴포넌트(Panel Components) 기본값
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
UI_PANEL_COMPONENTS = [
    # --- [서버 관리 봇] ---
    {"component_key": "start_onboarding_guide", "panel_key": "onboarding", "component_type": "button", "label": "案内を読む", "style": "success", "emoji": "📖", "row": 0},
    {"component_key": "request_nickname_change", "panel_key": "nicknames", "component_type": "button", "label": "名前変更申請", "style": "primary", "emoji": "✒️", "row": 0},
    {"component_key": "issue_warning_button", "panel_key": "warning", "component_type": "button", "label": "警告を発行する", "style": "danger", "emoji": "🚨", "row": 0},
    {"component_key": "use_item_button", "panel_key": "item_usage", "component_type": "button", "label": "アイテムを使用する", "style": "success", "emoji": "✨", "row": 0},
    {"component_key": "post_anonymous_message_button", "panel_key": "anonymous_board", "component_type": "button", "label": "匿名で投稿する", "style": "secondary", "emoji": "✍️", "row": 0},
    
    # --- [게임 봇] ---
    {"component_key": "open_shop", "panel_key": "commerce", "component_type": "button", "label": "商店 (アイテム購入)", "style": "primary", "emoji": "🏪", "row": 0},
    {"component_key": "open_market", "panel_key": "commerce", "component_type": "button", "label": "買取ボックス (アイテム売却)", "style": "secondary", "emoji": "📦", "row": 0},
    {"component_key": "open_inventory", "panel_key": "profile", "component_type": "button", "label": "持ち物を見る", "style": "primary", "emoji": "📦", "row": 0},
    {"component_key": "start_fishing_river", "panel_key": "panel_fishing_river", "component_type": "button", "label": "川で釣りをする", "style": "primary", "emoji": "🏞️", "row": 0},
    {"component_key": "start_fishing_sea", "panel_key": "panel_fishing_sea", "component_type": "button", "label": "海で釣りをする", "style": "secondary", "emoji": "🌊", "row": 0},
    {"component_key": "start_transfer", "panel_key": "atm", "component_type": "button", "label": "コインを送る", "style": "success", "emoji": "💸", "row": 0},
]

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 4. /setup 명령어 설정 맵
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
SETUP_COMMAND_MAP = {
    # --- [채널/패널 설정] ---
    "panel_roles":      {"type": "panel",   "cog_name": "RolePanel",    "key": "auto_role_channel_id",            "friendly_name": "역할 자동부여 패널", "channel_type": "text"},
    "panel_onboarding": {"type": "panel",   "cog_name": "Onboarding",   "key": "onboarding_panel_channel_id",     "friendly_name": "서버 안내 패널", "channel_type": "text"},
    "panel_nicknames":  {"type": "panel",   "cog_name": "Nicknames",    "key": "nickname_panel_channel_id",       "friendly_name": "닉네임 변경 패널", "channel_type": "text"},
    "panel_item_usage": {"type": "panel", "cog_name": "ItemSystem", "key": "item_usage_panel_channel_id", "friendly_name": "[패널] 아이템 사용", "channel_type": "text"},
    "panel_anonymous_board": {"type": "panel", "cog_name": "AnonymousBoard", "key": "anonymous_board_channel_id", "friendly_name": "[패널] 익명 게시판", "channel_type": "text"},    
    "panel_warning": {"type": "panel", "cog_name": "WarningSystem", "key": "warning_panel_channel_id", "friendly_name": "[패널] 경고 관리", "channel_type": "text"},
    "panel_commerce":        {"type": "panel", "cog_name": "Commerce",    "key": "commerce_panel_channel_id",        "friendly_name": "[게임] 상점 패널", "channel_type": "text"},
    "panel_fishing_river":   {"type": "panel", "cog_name": "Fishing",     "key": "river_fishing_panel_channel_id",   "friendly_name": "[게임] 강 낚시터 패널", "channel_type": "text"},
    "panel_fishing_sea":     {"type": "panel", "cog_name": "Fishing",     "key": "sea_fishing_panel_channel_id",     "friendly_name": "[게임] 바다 낚시터 패널", "channel_type": "text"},
    "panel_profile":         {"type": "panel", "cog_name": "UserProfile", "key": "profile_panel_channel_id",         "friendly_name": "[게임] 프로필 패널", "channel_type": "text"},
    
    "panel_inquiry": {"type": "panel", "cog_name": "TicketSystem", "key": "inquiry_panel_channel_id", "friendly_name": "[티켓] 문의/건의 패널", "channel_type": "text"},
    "panel_report":  {"type": "panel", "cog_name": "TicketSystem", "key": "report_panel_channel_id",  "friendly_name": "[티켓] 유저 신고 패널", "channel_type": "text"},
    
    "channel_new_welcome": {"type": "channel", "cog_name": "MemberEvents", "key": "new_welcome_channel_id",      "friendly_name": "신규 멤버 환영 채널", "channel_type": "text"},
    "channel_farewell":    {"type": "channel", "cog_name": "MemberEvents", "key": "farewell_channel_id",         "friendly_name": "멤버 퇴장 안내 채널", "channel_type": "text"},
    "channel_main_chat":   {"type": "channel", "cog_name": "Onboarding",   "key": "main_chat_channel_id",        "friendly_name": "메인 채팅 채널 (자기소개 승인 후 안내)", "channel_type": "text"},

    "channel_onboarding_approval": {"type": "channel", "cog_name": "Onboarding", "key": "onboarding_approval_channel_id", "friendly_name": "자기소개 승인/거절 채널", "channel_type": "text"},
    "channel_nickname_approval":   {"type": "channel", "cog_name": "Nicknames",  "key": "nickname_approval_channel_id",   "friendly_name": "닉네임 변경 승인 채널", "channel_type": "text"},
    
    "channel_vc_creator_3p": {"type": "channel", "cog_name": "VoiceMaster", "key": "vc_creator_channel_id_3p", "friendly_name": "음성 채널 자동 생성 (게임)", "channel_type": "voice"},
    "channel_vc_creator_4p": {"type": "channel", "cog_name": "VoiceMaster", "key": "vc_creator_channel_id_4p", "friendly_name": "음성 채널 자동 생성 (광장)", "channel_type": "voice"},
    "channel_vc_creator_newbie": {"type": "channel", "cog_name": "VoiceMaster", "key": "vc_creator_channel_id_newbie", "friendly_name": "[음성 채널] 뉴비 전용 생성기", "channel_type": "voice"},
    "channel_vc_creator_vip":    {"type": "channel", "cog_name": "VoiceMaster", "key": "vc_creator_channel_id_vip", "friendly_name": "[음성 채널] VIP 전용 생성기", "channel_type": "voice"},

    # --- [로그 채널 설정] ---
    "log_nickname":          {"type": "channel", "cog_name": "Nicknames",  "key": "nickname_log_channel_id",                "friendly_name": "[로그] 닉네임 변경 기록", "channel_type": "text"},
    "log_intro_approval":    {"type": "channel", "cog_name": "Onboarding", "key": "introduction_channel_id",                "friendly_name": "[로그] 자기소개 승인 기록", "channel_type": "text"},
    "log_intro_rejection":   {"type": "channel", "cog_name": "Onboarding", "key": "introduction_rejection_log_channel_id",  "friendly_name": "[로그] 자기소개 거절 기록", "channel_type": "text"},
    "log_item_usage": {"type": "channel", "cog_name": "ItemSystem", "key": "log_channel_item", "friendly_name": "[로그] 아이템 사용 기록", "channel_type": "text"},
    "log_message": {"type": "channel", "cog_name": "MessageLogger", "key": "log_channel_message", "friendly_name": "[로그] 메시지 (수정/삭제)", "channel_type": "text"},
    "log_voice":   {"type": "channel", "cog_name": "VoiceLogger",   "key": "log_channel_voice",   "friendly_name": "[로그] 음성 채널 (참여/이동/퇴장)", "channel_type": "text"},
    "log_member":  {"type": "channel", "cog_name": "MemberLogger",  "key": "log_channel_member",  "friendly_name": "[로그] 멤버 활동 (역할 부여/닉네임)", "channel_type": "text"},
    "log_channel": {"type": "channel", "cog_name": "ChannelLogger", "key": "log_channel_channel", "friendly_name": "[로그] 채널 관리 (생성/삭제/변경)", "channel_type": "text"},
    "log_server":  {"type": "channel", "cog_name": "ServerLogger",  "key": "log_channel_server",  "friendly_name": "[로그] 서버 및 역할 관리", "channel_type": "text"},
    "log_warning":   {"type": "channel", "cog_name": "WarningSystem", "key": "warning_log_channel_id", "friendly_name": "[로그] 경고 발행 기록", "channel_type": "text"},
    "channel_bump_reminder": {"type": "channel", "cog_name": "Reminder", "key": "bump_reminder_channel_id", "friendly_name": "[알림] Disboard BUMP 채널", "channel_type": "text"},
    "channel_dissoku_reminder": {"type": "channel", "cog_name": "Reminder", "key": "dissoku_reminder_channel_id", "friendly_name": "[알림] Dissoku UP 채널", "channel_type": "text"},
    "panel_atm":             {"type": "panel", "cog_name": "Atm", "key": "atm_panel_channel_id",             "friendly_name": "[게임] ATM 패널", "channel_type": "text"},
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
TICKET_MASTER_ROLES = [
    "role_staff_village_chief",
    "role_staff_deputy_chief",
]
TICKET_STAFF_GENERAL_ROLES = [
    "role_approval",
]
TICKET_STAFF_SPECIFIC_ROLES = [
    "role_staff_police",
    "role_staff_festival",
    "role_staff_pr",
    "role_staff_design",
    "role_staff_secretary",
    "role_staff_newbie_helper",
]
TICKET_REPORT_ROLES = [
    "role_staff_police",
]

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 8. 경고 시스템 설정
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
POLICE_ROLE_KEY = "role_staff_police"
WARNING_THRESHOLDS = [
    {"count": 1, "role_key": "role_warning_level_1"},
    {"count": 2, "role_key": "role_warning_level_2"},
    {"count": 3, "role_key": "role_warning_level_3"},
    {"count": 4, "role_key": "role_warning_level_4"},
]

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 9. 아이템 시스템 설정
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
USABLE_ITEMS = {
    "role_item_warning_deduct": {
        "name": "警告1個差引権",
        "type": "warning_deduction",
        "value": -1,
        "description": "累積警告を1回分減らします。"
    }
}
