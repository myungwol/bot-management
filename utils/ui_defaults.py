# utils/ui_defaults.py
"""
봇이 사용하는 모든 UI 요소(임베드, 패널 버튼)의 기본값을 정의하는 파일입니다.
봇이 시작될 때 이 파일의 데이터가 Supabase 데이터베이스에 동기화됩니다.
"""

# ==============================================================================
# 1. 임베드(Embed) 기본값
# ==============================================================================
UI_EMBEDS = {
    "welcome_embed": {
        "title": "🎉 {guild_name}へようこそ！",
        "description":
        "{member_mention}さん、はじめまして！\n\nまずは、サーバーの案内を読んで、自己紹介の作成をお願いします。",
        "color": 0x3498DB
    },
    "farewell_embed": {
        "title": "👋 また会いましょう",
        "description": "{member_name}さんが村から旅立ちました。",
        "color": 0x99AAB5
    },
    "panel_roles": {
        "title": "📖 役割付与",
        "description": "下のメニューからカテゴリーを選択して、自分に必要な役割を受け取ってください。",
        "color": 0x5865F2
    },
    "panel_onboarding": {
        "title": "📝 村役場・案内所",
        "description": "初めての方は、まず「案内を読む」ボタンを押して、サーバーでの過ごし方を確認してください。",
        "color": 0x5865F2
    },
    "panel_nicknames": {
        "title": "✒️ 名前変更",
        "description": "村で使う名前を変更したい場合は、下のボタンから申請してください。",
        "color": 0x5865F2
    },
    "panel_commerce": {
        "title": "🏪 Dico森商店＆買取ボックス",
        "description": "アイテムを買ったり、釣った魚などを売ったりできます。",
        "color": 0x5865F2
    },
    "panel_fishing": {
        "title": "🎣 釣り場",
        "description": "のんびり釣りを楽しみましょう。\n「釣りをする」ボタンで釣りを開始します。",
        "color": 0x5865F2
    },
    "panel_profile": {
        "title": "📦 持ち物",
        "description": "自分の所持金やアイテム、装備などを確認できます。",
        "color": 0x5865F2
    },
    "embed_onboarding_approval": {
        "title": "📝 新しい住民登録票",
        "description": "{member_mention}さんが住民登録票を提出しました。",
        "color": 0xE67E22
    },
    "embed_onboarding_public_welcome": {
        "title": "🎊 新しい住民がやってきました！",
        "description":
        "{moderator_mention}さんの承認を経て、{member_mention}さんが新しい住民になりました！\nみんなで歓迎しましょう！",
        "color": 0x2ECC71
    },
    "embed_transfer_confirmation": {
        "title": "💸 送金確認",
        "description":
        "本当に {recipient_mention}さんへ `{amount}`{currency_icon} を送金しますか？",
        "color": 0xE67E22
    },
    "log_coin_gain": {
        "description":
        "{user_mention}さんが**{reason}**で`{amount}`{currency_icon}を獲得しました。",
        "color": 0x2ECC71
    },
    "log_coin_transfer": {
        "description":
        "💸 {sender_mention}さんが{recipient_mention}さんへ`{amount}`{currency_icon}を送金しました。",
        "color": 0x3498DB
    },
    "log_coin_admin": {
        "description":
        "⚙️ {admin_mention}さんが{target_mention}さんのコインを`{amount}`{currency_icon}だけ**{action}**しました。",
        "color": 0x3498DB
    },
    "embed_shop_buy": {
        "title": "🏪 Dico森商店 - 「{category}」",
        "description": "現在の所持金: `{balance}`{currency_icon}",
        "color": 0x3498DB
    },
    "embed_shop_sell": {
        "title": "📦 販売所 - 「{category}」",
        "description": "現在の所持金: `{balance}`{currency_icon}",
        "color": 0xE67E22
    }
}

# ==============================================================================
# 2. 패널 버튼(Panel Components) 기본값
# ==============================================================================
UI_PANEL_COMPONENTS = [
    # --- Onboarding Panel ---
    {
        "component_key": "start_onboarding_guide",
        "panel_key": "onboarding",
        "component_type": "button",
        "label": "案内を読む",
        "style": "success",
        "emoji": "📖",
        "row": 0
    },
    # --- Commerce Panel ---
    {
        "component_key": "open_shop",
        "panel_key": "commerce",
        "component_type": "button",
        "label": "商店 (アイテム購入)",
        "style": "primary",
        "emoji": "🏪",
        "row": 0
    },
    {
        "component_key": "open_market",
        "panel_key": "commerce",
        "component_type": "button",
        "label": "買取ボックス (アイテム売却)",
        "style": "secondary",
        "emoji": "📦",
        "row": 0
    },
    # --- Fishing Panel ---
    {
        "component_key": "start_fishing",
        "panel_key": "fishing",
        "component_type": "button",
        "label": "釣りをする",
        "style": "primary",
        "emoji": "🎣",
        "row": 0
    },
    # --- Nicknames Panel ---
    {
        "component_key": "request_nickname_change",
        "panel_key": "nicknames",
        "component_type": "button",
        "label": "名前変更申請",
        "style": "primary",
        "emoji": "✒️",
        "row": 0
    },
    # --- UserProfile Panel ---
    {
        "component_key": "open_inventory",
        "panel_key": "profile",
        "component_type": "button",
        "label": "持ち物を開く",
        "style": "primary",
        "emoji": "📦",
        "row": 0
    },
]
