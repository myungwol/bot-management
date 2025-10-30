# bot-management/utils/ui_defaults.py
"""
ボットが使用するすべてのUI要素と主要なマッピングデータのデフォルト値を定義するファイルです。
ボットが起動する際、このファイルのデータがSupabaseデータベースに同期されます。
"""

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 1. 役職キーマップ (Role Key Map)
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
UI_ROLE_KEY_MAP = {
    # --- [コア] プレフィックス役職と優先順位 ---
    "role_admin_total": {
        "name": "森の妖精",
        "priority": 100
    },
    "role_staff_village_chief": {
        "name": "管理人かも",
        "priority": 90
    },
    "role_staff_deputy_chief": {
        "name": "エンジニア",
        "priority": 85
    },
    "role_premium_booster": {
        "name": "Server Booster",
        "priority": 55
    },
    "role_resident_elder": {
        "name": "Lv.150",
        "priority": 50
    },
    "role_job_master_chef": {
        "name": "マスターシェフ",
        "priority": 16
    },
    "role_job_master_angler": {
        "name": "太公望",
        "priority": 16
    },
    "role_job_master_farmer": {
        "name": "大農",
        "priority": 16
    },
    "role_job_expert_miner": {
        "name": "専門の鉱夫",
        "priority": 16
    },
    "role_job_chef": {
        "name": "料理人",
        "priority": 15
    },
    "role_job_fisherman": {
        "name": "釣り人",
        "priority": 15
    },
    "role_job_farmer": {
        "name": "農家",
        "priority": 15
    },
    "role_job_miner": {
        "name": "鉱夫",
        "priority": 15
    },
    "role_resident": {
        "name": "アメンバ",
        "priority": 10
    },
    "role_resident_veteran": {
        "name": "LV.100",
        "priority": 0
    },
    "role_resident_regular": {
        "name": "Lv.50",
        "priority": 0
    },
    "role_resident_rookie": {
        "name": "Lv.0",
        "priority": 0
    },

    # --- ゲーム/プラットフォーム役職 ---
    "role_game_minecraft": {
        "name": "マイクラーMinecraft",
        "priority": 0
    },
    "role_game_valorant": {
        "name": "ヴァローVALORANT",
        "priority": 0
    },
    "role_game_overwatch": {
        "name": "オバウォーOverwatch",
        "priority": 0
    },
    "role_game_lol": {
        "name": "ロルーLeague of Legends",
        "priority": 0
    },
    "role_game_mahjong": {
        "name": "麻雀ーMahjong",
        "priority": 0
    },
    "role_game_amongus": {
        "name": "アモアスーAmong Us",
        "priority": 0
    },
    "role_game_mh": {
        "name": "モンハンMonster Hunter",
        "priority": 0
    },
    "role_game_genshin": {
        "name": "原神ーGenshin Impact",
        "priority": 0
    },
    "role_game_apex": {
        "name": "エペーApex Legends",
        "priority": 0
    },
    "role_game_splatoon": { # 역할 추가됨
        "name": "スプラーSplatoon",
        "priority": 0
    },
    "role_game_godfield": { # 역할 추가됨
        "name": "ゴッフィーGod Field",
        "priority": 0
    },
    "role_platform_steam": {
        "name": "スチームーSteam",
        "priority": 0
    },
    "role_platform_smartphone": {
        "name": "スマホーSmartphone",
        "priority": 0
    },
    "role_platform_switch": {
        "name": "スイッチーSwitch",
        "priority": 0
    },

}

ONBOARDING_CHOICES = {
    "gender": [{
        "label": "男性",
        "value": "男性"
    }, {
        "label": "女性",
        "value": "女性"
    }],
    "birth_year_groups": {
        "2000s": [{
            "label": f"{year}年生まれ",
            "value": str(year)
        } for year in range(2009, 1999, -1)],
        "1990s": [{
            "label": f"{year}年生まれ",
            "value": str(year)
        } for year in range(1999, 1989, -1)],
        "1980s": [{
            "label": f"{year}年生まれ",
            "value": str(year)
        } for year in range(1989, 1979, -1)],
        "1970s": [{
            "label": f"{year}年生まれ",
            "value": str(year)
        } for year in range(1979, 1969, -1)],
        "private": [{
            "label": "非公開",
            "value": "非公開"
        }]
    }
}

USABLE_ITEMS = {
    "role_item_warning_deduct": {
        "name": "罰点1回取り消し券",
        "type": "deduct_warning",
        "value": -1,
        "description": "累積された罰点を1回取り消します。",
        "log_channel_key": "log_item_warning_deduct",
        "log_embed_key": "log_item_use_warning_deduct"
    },
    "role_item_event_priority": {
        "name": "イベント優先参加券",
        "type": "consume_with_reason",
        "description": "イベント参加申請時に優先権を行使します。",
        "log_channel_key": "log_item_event_priority",
        "log_embed_key": "log_item_use_event_priority"
    },
    "role_item_farm_expansion": {
        "name": "畑拡張許可証",
        "type": "farm_expansion",
        "description": "自分の農場を1マス拡張します。"
    },
    "item_mine_pass": {
        "name": "鉱山入場券",
        "type": "mine_entry",
        "description": "鉱山に10分間入場できるチケットです。",
        "log_channel_key": "log_item_mine_pass",
        "log_embed_key": "log_item_use_mine_pass"
    },
    "item_job_reset_ticket": {
        "name": "職業リセット券",
        "type": "job_reset",
        "description": "自分の職業をリセットし、レベルに合った転職を再度行うことができます。(レベルは維持されます)",
        "log_channel_key": "log_item_job_reset",
        "log_embed_key": "log_item_use_job_reset"
    },
    "item_weekly_boss_chest": {
        "name": "週間ボス宝箱",
        "type": "open_chest",
        "description": "週間ボスを討伐して得た戦利品箱。何が入っているだろうか？"
    },
    "item_monthly_boss_chest": {
        "name": "月間ボス宝箱",
        "type": "open_chest",
        "description": "月間ボスを討伐して得た貴重な戦利品箱。何が入っているだろうか？"
    }
}

UI_EMBEDS = {
    "onboarding_guide_server": {
        "title": "",
        "description":
        "## 🏡✨ 𝗗𝗜𝘀𝗰𝗼𝗿𝗱 𝗩𝗶𝗹𝗹𝗮𝗴𝗲へようこそ！ ✨🏡\n> ### いらっしゃいませ、新しい隣人さん！ 私たちは「村」をコンセプトにした特別なコミュニティです。\n> ### ここであなたは村の大切な住民となり、楽しく快適な時間を過ごすことができます。\n## ✨ 村で楽しめること ✨\n### 1. 居心地の良い村の生活 🏡\n- 温かいお茶を飲みながら日常を共有したり、些細な話を交わしながらリラックスした時間を過ごしてみてください。\n- お互いを尊重する温かく活気のある雰囲気が満ち溢れています。\n### 2. みんなで楽しむゲーム 🎮\n- 好きなゲームを一緒にプレイして、新しい友達を作ってみませんか？\n- 様々なゲームチャンネルで存分に楽しみ、忘れられない思い出を作りましょう。\n### 3. 村のオリジナルボット 🤖\n- 村専用のオリジナルボットで、より多彩な活動が楽しめます。\n- ボットを通じて様々なミニゲームをプレイし、財貨を集め、その財貨で特別なアイテムを購入する楽しさをぜひ体験してみてください！\n### 村へのご入居、心から歓迎いたします！ 💖\n### これからよろしくお願いします。\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n下の「次へ」ボタンを押して案内をお読みください。",
        "color": 0x5865F2,
        "footer": {
            "text": "1/7段階"
        }
    },
    "onboarding_guide_bots": {
        "title": "",
        "description":
        "## ✨ 村の二人の妖精紹介 ✨\n> ### 村の住民たちが楽しく便利に生活できるよう、二人の妖精がいつも一緒にいます。\n## 🌙 管理妖精『つき』\n- 住民たちのサーバー生活をより便利にしてくれる頼もしい妖精です。\n## ⭐ ゲーム妖精『ほし』\n- 村のすべての楽しさを担当するゲームの専門家です。ギャンブル、対戦、釣り、農業、採掘、料理、ペット、転職など、様々な活動で財貨を集め、集めた財貨で商店で特別なアイテムを購入する楽しさをぜひ体験してみてください！\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n下の「次へ」ボタンを押して案内をお読みください。",
        "color": 0x5865F2,
        "footer": {
            "text": "2/7段階"
        }
    },
    "onboarding_guide_rules": {
        "title": "",
        "description":
        "## 📜 村のルールを必ずお読みください！ 📜\n> ### 私たちの村のすべての住民が楽しく平和に過ごすための約束です。\n### 📜 ルールチャンネル確認のご案内\n- ルールチャンネルには、村の法と秩序を守るための重要な内容が記載されています。\n- すべての住民の方々がお互いを尊重し、思いやりながら楽しい時間を過ごせるよう、下のルールチャンネルの内容を少し時間を取ってじっくりお読みください。\n### <#1423522843131510916>\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n下の「次へ」ボタンを押して案内をお読みください。",
        "color": 0x5865F2,
        "footer": {
            "text": "3/7段階"
        }
    },
    "onboarding_guide_channels": {
        "title": "",
        "description":
        "## 🗺️ 村の地図を確認して散策してみましょう！ 🗺️\n> ### 🗺️ 村のどの場所で何ができるか、一目でわかります！\n### 村の地図確認のご案内\n- 村のあちこちを散策しながら、新しい隣人たちと楽しい思い出を作る準備をしましょう。\n- 村の地図チャンネルは、私たちの村の様々なチャンネルの紹介と利用方法を案内する場所です。\n- どこで話をし、どこでゲームを楽しむか気になるなら、下の村の地図チャンネルを開いてみてください！\n### <#1423522888539176980>\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n下の「次へ」ボタンを押して案内をお読みください。",
        "color": 0x5865F2,
        "footer": {
            "text": "4/7段階"
        }
    },
    "onboarding_guide_roles": {
        "title": "",
        "description":
        "## 🎭 村の役職を事前に見てみましょう！ 🎭\n> ### 私たちの村には、それぞれ個性と物語を持つ役職が存在します。\n### 🎭 役職紹介確認のご案内\n- 各役職によって参加できる特別なゲームやチャンネルが変わることもあります。\n- 自分に似合う役職は何か想像しながら、これからの村の生活をさらに楽しみにしてください！\n- 下の役職紹介チャンネルは、村の様々な役職がそれぞれどのような意味を持ち、どのような活動をするのかを説明してくれる場所です。\n### <#1423522940820914250>\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n下の「次へ」ボタンを押して案内をお読みください。",
        "color": 0x5865F2,
        "footer": {
            "text": "5/7段階"
        }
    },
    "onboarding_guide_staff": {
        "title": "",
        "description":
        "## 🏢 村役場の職員を紹介します！ 🏢\n> ### 村で困ったことや気になることがあれば、いつでも役場の職員を訪ねてください！\n### 🏢 職員紹介確認のご案内\n- 頼もしい職員たちがいるからこそ、私たちの村はいつも平和で楽しいのです！\n- 助けが必要だったり、提案したいことがあればいつでも職員を呼び出してください。親切に案内してくれます。\n- 下の職員紹介チャンネルでは、村のために尽力してくださる村長と副村長、職員（管理者）に会うことができます。\n### <#1423522971527680001>\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n下の「次へ」ボタンを押して案内をお読みください。",
        "color": 0x5865F2,
        "footer": {
            "text": "6/7段階"
        }
    },
    "onboarding_guide_intro": {
        "title": "",
        "description":
        "## 最後に、自己紹介である「住民登録証」を作成しましょう！\n### 住民登録のルール\n- 性別の公開は必須です。\n- 名前に特殊文字、絵文字、空白は使用できません。\n- 名前は最大8文字で、漢字は2文字、それ以外（ひらがな、カタカナ、英数字）は1文字として扱われます。\n- 不適切なニックネームは承認されません。\n- すべての項目を正確に記入してください。（未記入の場合、拒否されることがあります。）\n- 参加経緯を必ず記入してください。（例：Disboard、〇〇さんからの招待など）\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n提出後、職員が確認して承認すれば、正式な住民として認められます。",
        "color": 0x5865F2,
        "footer": {
            "text": "7/7段階"
        }
    },
    "welcome_embed": {
        "description":
        "## 🎉 {guild_name}へようこそ！\n### {member_mention}さん、村での生活を始める前に、\n### 少し時間を取って<#1423521850151141461>チャンネルで\n### 村についての案内を受け、自己紹介を作成してください。\n### これから楽しい時間を過ごせることを願っています！ 😊",
        "color": 0x3498DB
    },
    "farewell_embed": {
        "description":
        "## 👋 また会いましょう\n### **{member_name}**さんが村を去りました。\n### 一緒に過ごしたすべての瞬間に感謝します。\n### これからの旅に幸運が満ちることを願っています。",
        "color": 0x99AAB5
    },
    "panel_roles": {
        "title": "📖 ロール付与",
        "description": "下のメニューからカテゴリを選択し、自分に必要なロールを受け取ってください。",
        "color": 0x5865F2
    },
    "panel_onboarding": {
        "title": "📝 村役場・案内所",
        "description": "初めての方は、まず「案内を読む」ボタンを押してサーバーの利用方法を確認してください。",
        "color": 0x5865F2
    },
    "embed_onboarding_approval": {
        "title": "📝 新規住民登録申請",
        "description": "{member_mention}さんが住民登録証を提出しました。",
        "color": 0xE67E22
    },
    "panel_nicknames": {
        "title": "✒️ 名前変更",
        "description": "### 村で使用する名前を変更したい場合は、下のボタンから申請してください。\n- 名前に特殊文字、絵文字、空白は使用できません。\n- 名前は最大8文字で、漢字は2文字、それ以外（ひらがな、カタカナ、英数字）は1文字として扱われます。\n- 不適切なニックネームは承認されません。\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n提出後、職員が確認し承認されると名前が変更されます。",
        "color": 0x5865F2
    },
    "embed_main_chat_welcome": {
        "title": "",
        "description": "### 新しい隣人が増えました！みんなで温かい挨拶を交わしましょう。:sparkling_heart:\n**村での生活がもっと楽しくなるように、**\n**いくつかの便利な案内板を用意しました。:map:**\n### ┃ :house_with_garden: 村に馴染むのが難しいですか？\n　╰─➤ 助けが必要なときはいつでも{staff_role_mention}さんを訪ねてください！\n### ┃ :black_nib: 新しい名前が必要ですか？\n　╰─➤ {nickname_channel_mention}チャンネルで素敵な名前に変えられます。\n### ┃ :bell: お知らせを受け取りたいですか？\n　╰─➤ {role_channel_mention}で個性的な役職をもらってみましょう。\n### ┃ :love_letter: 何か良いアイデアが浮かびましたか？\n　╰─➤ {inquiry_channel_mention}に大切な意見を残してください。\n### ┃ :fairy: 村の妖精（ボット）が気になりますか？\n　╰─➤ {bot_guide_channel_mention}チャンネルで使い方を確認してください。\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n### ┃:circus_tent: 現在進行中の村祭り！\n　╰─➤ {festival_channel_mention}を確認してください。\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯",
        "color": 0x2ECC71
    },
    "panel_warning": {
        "title": "🚨 罰点管理パネル",
        "description":
        "サーパールールに違反したユーザーに、下のボタンを通じて罰点を付与することができます。\n\n**この機能は`警察官`のみ使用できます。**",
        "color": 15548997
    },
    "log_warning": {
        "title": "🚨 罰点発行のお知らせ",
        "color": 15548997
    },
    "dm_onboarding_approved": {
        "title": "✅ 住民登録完了のお知らせ",
        "description": "'{guild_name}'サーバーの住民登録が承認されました。\nこれからよろしくお願いします！",
        "color": 3066993
    },
    "dm_onboarding_rejected": {
        "title": "❌ 住民登録拒否のお知らせ",
        "description": "申し訳ありません。'{guild_name}'サーバーの住民登録が拒否されました。",
        "color": 15548997
    },
    "panel_anonymous_board": {
        "title": "🤫 匿名の声",
        "description":
        "誰にも知られていないあなたの考えや気持ちを共有してみてください。\n下のボタンを押して、1日に1回メッセージを作成できます。\n\n**※すべてのメッセージはサーバー管理者が記録・確認しており、問題が発生した場合は作成者を特定して措置を取ります。**",
        "color": 4342323
    },
    "anonymous_message": {
        "title": "匿名のメッセージが届きました",
        "color": 16777215
    },
    "panel_custom_embed": {
        "title": "📢 カスタムメッセージ送信パネル",
        "description":
        "下のボタンを押して、指定したチャンネルにボットが埋め込みメッセージを送信します。\n\n**この機能は特定の役職を持つスタッフのみが使用できます。**",
        "color": 0x34495E
    },
    "log_job_advancement": {
        "title":
        "🎉 新たな転職者！",
        "description":
        "{user_mention}さんがついに新しい道を選びました。",
        "color":
        0xFFD700,
        "fields": [{
            "name": "職業",
            "value": "```\n{job_name}\n```",
            "inline": True
        }, {
            "name": "選択した能力",
            "value": "```\n{ability_name}\n```",
            "inline": True
        }],
        "footer": {
            "text": "今後の活躍を期待しています！"
        }
    },
    "panel_commerce": {
        "title":
        "🏪 購入＆売却",
        "description":
        "> アイテムを買ったり、釣った魚などを売ったりできます。",
        "color":
        0x5865F2,
        "fields": [{
            "name": "📢 今日の主な相場変動",
            "value": "{market_updates}",
            "inline": False
        }]
    },
    "panel_fishing_river": {
        "title": "🏞️ 川の釣り場",
        "description": "> 川辺でゆったりと釣りを楽しんでみましょう。\n> 下のボタンを押して釣りを開始します。",
        "color": 0x5865F2
    },
    "panel_fishing_sea": {
        "title": "🌊 海の釣り場",
        "description": "> 広い海で大物を狙ってみましょう！\n> 下のボタンを押して釣りを開始します。",
        "color": 0x3498DB
    },
    "panel_atm": {
        "title": "🏧 ATM",
        "description": "> 下のボタンで他の住民にコインを送ることができます。",
        "color": 0x2ECC71
    },
    "panel_profile": {
        "title": "📦 所持品",
        "description": "> 自分の所持金、アイテム、装備などを確認できます。",
        "color": 0x5865F2
    },
    "panel_dice_game": {
        "title": "🎲 サイコロゲーム",
        "description":
        "> 運試しはいかがですか？\n> 下のボタンでゲームを開始し、10コイン単位でベットできます。",
        "color": 0xE91E63
    },
    "log_dice_game_win": {
        "title":
        "🎉 **サイコロゲーム勝利！** 🎉",
        "description":
        "**{user_mention}** さんが予測に成功しました！\n> ✨ **`+{reward_amount:,}`** {currency_icon} を獲得しました！",
        "color":
        0x2ECC71,
        "fields": [{
            "name": "ベット額",
            "value": "`{bet_amount:,}` {currency_icon}",
            "inline": True
        }, {
            "name": "選択した数字 / 結果",
            "value": "`{chosen_number}` / `🎲 {dice_result}`",
            "inline": True
        }]
    },
    "log_dice_game_lose": {
        "title":
        "💧 **サイコロゲーム敗北** 💧",
        "description":
        "**{user_mention}** さんは予測に失敗し **`{bet_amount:,}`** {currency_icon} を失いました。",
        "color":
        0xE74C3C,
        "fields": [{
            "name": "ベット額",
            "value": "`{bet_amount:,}` {currency_icon}",
            "inline": True
        }, {
            "name": "選択した数字 / 結果",
            "value": "`{chosen_number}` / `🎲 {dice_result}`",
            "inline": True
        }]
    },
    "panel_slot_machine": {
        "title": "🎰 スロットマシン",
        "description":
        "> 今日の運勢を試してみましょう！\n> 下のボタンでゲームを開始し、100コイン単位でベットできます。",
        "color": 0xFF9800
    },
    "log_slot_machine_win": {
        "title":
        "🎉 **スロットマシンジャックポット！** 🎉",
        "description":
        "**{user_mention}** さんが見事に絵柄を揃えました！\n> 💰 **`+{payout_amount:,}`** {currency_icon} を獲得しました！",
        "color":
        0x4CAF50,
        "fields": [{
            "name": "ベット額",
            "value": "`{bet_amount:,}` {currency_icon}",
            "inline": True
        }, {
            "name": "結果 / 役",
            "value": "**{result_text}**\n`{payout_name}` (`x{payout_rate}`)",
            "inline": True
        }]
    },
    "log_slot_machine_lose": {
        "title":
        "💧 **スロットマシン** 💧",
        "description":
        "**{user_mention}** さんは **`{bet_amount:,}`** {currency_icon} を失いました。\n> 次の幸運を祈ります！",
        "color":
        0xF44336,
        "fields": [{
            "name": "ベット額",
            "value": "`{bet_amount:,}` {currency_icon}",
            "inline": True
        }, {
            "name": "結果",
            "value": "**{result_text}**",
            "inline": True
        }]
    },
    "panel_rps_game": {
        "title": "✊✌️✋ じゃんけん部屋",
        "description":
        "> 他の住民とじゃんけん勝負！\n> 下のボタンを押して部屋を作り、参加者と勝負できます。",
        "color": 0x9B59B6
    },
    "log_rps_game_end": {
        "title":
        "🏆 **じゃんけん勝負終了！** 🏆",
        "description":
        "**{winner_mention}** さんが最終的な勝者となりました！",
        "color":
        0xFFD700,
        "fields": [{
            "name": "💰 総賞金",
            "value": "> **`{total_pot:,}`** {currency_icon}",
            "inline": False
        }, {
            "name": "ベット額（1人あたり）",
            "value": "`{bet_amount:,}` {currency_icon}",
            "inline": True
        }, {
            "name": "👥 参加者",
            "value": "{participants_list}",
            "inline": False
        }]
    },
    "panel_tasks": {
        "title": "✅ 今日のやること",
        "description": "> 下のボタンを押して毎日の出席報酬を受け取ったり、クエストを確認したりできます！",
        "color": 0x4CAF50
    },
    "log_daily_check": {
        "title": "✅ 出席チェック完了",
        "description":
        "{user_mention}さんが出席し、**`{reward}`**{currency_icon}を受け取りました。",
        "color": 0x8BC34A
    },
    "panel_farm_creation": {
        "title": "🌾 自分だけの農場作り！",
        "description":
        "> 下のボタンを押して、あなただけの農場（個人スレッド）を作ります。\n> 自分だけの空間で、作物を育ててみましょう！",
        "color": 0x8BC34A
    },
    "farm_thread_welcome": {
        "title": "{user_name}さんの農場",
        "description":
        "ようこそ！ここはあなただけの農場です。\n\n**始め方:**\n1. まず商店で「木のクワ」と「種」を購入します。\n2. 下のボタンで畑を耕し、種を植えてみましょう！",
        "color": 0x4CAF50
    },
    "log_coin_gain": {
        "title":
        "🪙 コイン獲得通知",
        "description":
        "{user_mention}さんが活動報酬でコインを獲得しました。",
        "color":
        0x2ECC71,
        "fields": [{
            "name": "獲得者",
            "value": "{user_mention}",
            "inline": True
        }, {
            "name": "獲得コイン",
            "value": "+{amount}{currency_icon}",
            "inline": True
        }],
        "footer": {
            "text": "おめでとうございます！"
        }
    },
    "log_coin_transfer": {
        "title": "💸 送金完了通知",
        "description":
        "**送金者:** {sender_mention}\n**受取人:** {recipient_mention}\n\n**金額:** `{amount}`{currency_icon}",
        "color": 0x3498DB
    },
    "log_coin_admin": {
        "description":
        "⚙️ {admin_mention}さんが{target_mention}さんのコインを`{amount}`{currency_icon} **{action}**しました。",
        "color": 0x3498DB
    },
    "embed_weather_forecast": {
        "title": "{emoji} 今日の天気予報",
        "description": "今日の天気は「**{weather_name}**」です！\n\n> {description}",
        "color": "{color}",
        "fields": [{
            "name": "💡 今日のヒント",
            "value": "> {tip}",
            "inline": False
        }],
        "footer": {
            "text": "天気は毎日深夜0時に変わります。"
        }
    },
    "log_whale_catch": {
        "title":
        "🐋 今月の主を釣る！ 🐋",
        "description":
        "今月、一度だけ姿を現すという幻の**クジラ**が**{user_mention}**さんの手にかかりました！\n\n巨大な影は来月まで再び深い海の底へと姿を消します...",
        "color":
        "0x206694",
        "fields": [{
            "name": "釣れた主",
            "value":
            "{emoji} **{name}**\n**サイズ**: `{size}`cm\n**価値**: `{value}`{currency_icon}",
            "inline": False
        }],
        "footer": {
            "text": "来月の挑戦者よ、来たれ！"
        }
    },
    "embed_whale_reset_announcement": {
        "title": "🐋 海からの噂...",
        "description":
        "今月、海の深いところで巨大な何かが目撃されたという噂が広まっている…\nどうやら腕のいい釣り人を待っているようだ。",
        "color": 0x3498DB,
        "footer": {
            "text": "今月の主が海に戻ってきました。"
        }
    },
    "log_item_use_warning_deduct": {
        "title": "🎫 罰点取り消し券使用のお知らせ",
        "color": 3066993
    },
    "log_item_use_event_priority": {
        "title": "✨ イベント優先権使用のお知らせ",
        "color": 16776960
    },
    "panel_champion_board": {
        "title":
        "🏆 総合チャンピオンボード 🏆",
        "description":
        "各分野で最も輝く総合1位の住民を紹介します！\n下のボタンで自分のステータスを確認したり、詳細ランキングを見たりできます。",
        "color":
        0xFFD700,
        "fields": [{
            "name": "👑 総合レベル",
            "value": "{level_champion}",
            "inline": False
        }, {
            "name": "🎙️ ボイスチャット",
            "value": "{voice_champion}",
            "inline": False
        }, {
            "name": "💬 チャット",
            "value": "{chat_champion}",
            "inline": False
        }, {
            "name": "🎣 釣り",
            "value": "{fishing_champion}",
            "inline": False
        }, {
            "name": "🌾 収穫",
            "value": "{harvest_champion}",
            "inline": False
        }, {
            "name": "⛏️ 採掘",
            "value": "{mining_champion}",
            "inline": False
        }],
        "footer": {
            "text": "毎日 00:05 JSTに更新されます。" # KST -> JST
        }
    },
    "panel_mining": {
        "title": "⛏️ 鉱山の入口",
        "description": "> 鉱山に入るには「鉱山入場券」が必要です。\n> 入場券は商店で購入できます。",
        "color": 0x607D8B
    },
    "mine_thread_welcome": {
        "title": "{user_name}さんの鉱山採掘",
        "description": "ようこそ！この鉱山は10分間維持されます。\n\n下の「鉱石を探す」ボタンを押して周辺を探索してください。\n探索と採掘には少し時間がかかります。",
        "color": 0x607D8B
    },
    "log_item_use_mine_pass": {
        "title": "🎟️ 鉱山入場券使用のお知らせ",
        "color": 0x607D8B
    },
    "panel_blacksmith": {
        "title": "🛠️ 鍛冶屋",
        "description": "> 各種道具をアップグレードして性能を向上させることができます。\n> アップグレードには材料と時間、コインが必要です。",
        "color": 0x964B00
    },
    "panel_trade": {
        "title": "🤝 取引所",
        "description": "> 他のユーザーとアイテムを交換したり、郵便を送ったりできます。",
        "color": 0x3498DB
    },
    "log_trade_success": {
        "title": "✅ 取引成立",
        "description": "{user1_mention}さんと{user2_mention}さんの取引が正常に完了しました。",
        "color": 0x2ECC71,
        "footer": {
            "text": "取引税: {commission}{currency_icon}"
        }
    },
    "dm_new_mail": {
        "title": "📫 新しい郵便が届きました",
        "description": "{sender_name}さんから新しい郵便が届きました。\n`/取引所`パネルの郵便受けで確認してください。",
        "color": 0x3498DB
    },
    "log_new_mail": {
        "title": "📫 新しい郵便が届きました",
        "description": "{sender_mention}さんが{recipient_mention}さんに郵便を送りました。",
        "color": 0x3498DB
    },
    "log_blacksmith_complete": {
        "title": "🎉 道具のアップグレード完了！",
        "description": "{user_mention}さんの**{tool_name}**のアップグレードが完了しました！インベントリを確認してください。",
        "color": 0xFFD700
    },
    "log_mining_result": {
        "title": "⛏️ 鉱山探索結果",
        "description": "{user_mention}さんの探索が終了しました。",
        "color": 0x607D8B,
        "fields": [
            {
                "name": "使用した装備",
                "value": "`{pickaxe_name}`",
                "inline": True
            },
            {
                "name": "採掘した鉱物",
                "value": "{mined_ores}",
                "inline": False
            }
        ]
    },
    "panel_cooking_creation": {
        "title": "🍲 自分だけのキッチン作り！",
        "description": "> 下のボタンを押して、あなただけのキッチン（個人スレッド）を作ります。\n> かまどを設置して、様々な料理に挑戦してみましょう！",
        "color": 15105078
    },
    "cooking_thread_welcome": {
        "title": "{user_name}さんのキッチン",
        "description": "ようこそ！ここはあなただけの料理空間です。\n\n**始め方:**\n1. まず商店で「かまど」を購入します。\n2. 下のメニューでかまどを選択し、材料を入れて料理を始めてみましょう！",
        "color": 15105078
    },
    "log_cooking_complete": {
        "title": "🎉 料理完成！",
        "description": "{user_mention}さんの**{recipe_name}**料理が完成しました！キッチンを確認してください。",
        "color": 16766720
    },
    "log_recipe_discovery": {
        "title": "🎉 新しいレシピ発見！",
        "description": "**{user_mention}**さんが新しい料理**「{recipe_name}」**のレシピを初めて発見しました！",
        "color": 0xFFD700,
        "fields": [
            {
                "name": "📜 レシピ",
                "value": "```{ingredients_str}```",
                "inline": False
            }
        ]
    },
    "log_item_use_job_reset": {
        "title": "📜 職業リセット券使用のお知らせ",
        "description": "{user_mention}さんが職業をリセットし、新たな旅を始めます。",
        "color": 0x9B59B6
    },
    "panel_friend_invite": {
        "title": "💌 友達招待イベント！",
        "description": "サーバーに友達を招待して、特別な報酬を手に入れましょう！\n\n> 下のボタンを押して、あなただけの**無期限招待コード**を確認または作成してください。\n> 友達がこのコードでサーバーに参加し、**「住民」になると**、あなたに**500コイン**が支給されます！\n\n**[イベント方式]**\n- コードは有効期限や使用回数に制限がありません。\n- すでにコードがある場合、ボタンを押しても新しいコードは作成されず、既存のコードが表示されます。\n- 報酬は、招待した友達がサーバーの正式な住民になったときに支給されます。",
        "color": 0x5865F2,
        "footer": {
            "text": "友達と一緒に楽しい村の生活を！"
        }
    },
    "log_friend_invite_success": {
        "title": "🎉 新しい住民の誕生！（友達招待）",
        "description": "{new_member_mention}さんが{inviter_mention}さんの招待で村に加わり、ついに正式な住民になりました！",
        "color": 0x3498DB,
        "fields": [{
            "name": "💌 招待した人",
            "value": "{inviter_mention}",
            "inline": True
        }, {
            "name": "🎁 新しく来た住民",
            "value": "{new_member_mention}",
            "inline": True
        }, {
            "name": "💰 支給された報酬",
            "value": "`500`{currency_icon}",
            "inline": False
        }, {
            "name": "🏆 総招待回数",
            "value": "**{invite_count}**名",
            "inline": False
        }],
        "footer": {
            "text": "友達招待イベント"
        }
    },
    "panel_incubator": {
        "title": "🥚 ペットインキュベーター",
        "description": "> 所持している卵を孵化器に入れてペットを手に入れることができます。\n> 孵化には時間が必要で、卵を長く温めるほどより良い能力値を持つ可能性があります。",
        "color": 0x7289DA
    },
    "panel_pet_exploration": {
        "title": "🏕️ ペット探検",
        "description": "ペットを送って報酬を手に入れましょう！\n\n> 各地域にはペットのレベル制限があり、レベルが高いほどより良い報酬を得られる地域に挑戦できます。",
        "color": 0x7289DA,
        "fields": [
            {
                "name": "🔥 ファイアスライムの巣",
                "value": "> 要求レベル: **Lv.1**",
                "inline": True
            },
            {
                "name": "💧 ウォータースライムの巣",
                "value": "> 要求レベル: **Lv.10**",
                "inline": True
            },
            {
                "name": "⚡ エレキスライムの巣",
                "value": "> 要求レベル: **Lv.20**",
                "inline": True
            },
            {
                "name": "🌿 グラススライムの巣",
                "value": "> 要求レベル: **Lv.30**",
                "inline": True
            },
            {
                "name": "✨ ライトスライムの巣",
                "value": "> 要求レベル: **Lv.40**",
                "inline": True
            },
            {
                "name": "🌑 ダークスライムの巣",
                "value": "> 要求レベル: **Lv.50**",
                "inline": True
            }
        ]
    },
    "panel_pet_pvp": {
        "title": "⚔️ ペット対戦場",
        "description": "> 他のユーザーのペットと腕を競いましょう！\n> 下のボタンを押して対戦相手を探すことができます。",
        "color": 0xC27C0E,
        "footer": { "text": "挑戦申請には5分間のクールダウンが適用されます。" }
    },
    "log_pet_pvp_result": {
        "title": "🏆 ペット対戦終了！ 🏆",
        "description": "**{winner_mention}**さんのペット**「{winner_pet_name}」**が激しい戦いの末に勝利しました！",
        "color": 0xFFD700,
        "fields": [
            { "name": "👑 勝者", "value": "{winner_mention}", "inline": True },
            { "name": "💧 敗者", "value": "{loser_mention}", "inline": True }
        ]
    },
}

UI_PANEL_COMPONENTS = [
    {
        # [수정] panel_key를 server_guide로 변경
        "component_key": "start_onboarding_guide",
        "panel_key": "server_guide",
        "component_type": "button",
        "label": "案内を読む",
        "style": "success",
        "emoji": "📖",
        "row": 0,
        "order_in_row": 0
    },
    # [추가] 새로운 주민 등록 패널용 버튼 추가
    {
        "component_key": "start_introduction",
        "panel_key": "introduction",
        "component_type": "button",
        "label": "住民登録証を作成する",
        "style": "success",
        "emoji": "📝",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "issue_warning_button",
        "panel_key": "warning",
        "component_type": "button",
        "label": "罰点を発行する",
        "style": "danger",
        "emoji": "🚨",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "post_anonymous_message_button",
        "panel_key": "anonymous_board",
        "component_type": "button",
        "label": "匿名で作成する",
        "style": "secondary",
        "emoji": "✍️",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "create_custom_embed",
        "panel_key": "custom_embed",
        "component_type": "button",
        "label": "埋め込みメッセージ作成",
        "style": "primary",
        "emoji": "✉️",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "open_shop",
        "panel_key": "commerce",
        "component_type": "button",
        "label": "購入（アイテム購入）",
        "style": "success",
        "emoji": "🏪",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "open_market",
        "panel_key": "commerce",
        "component_type": "button",
        "label": "売却（アイテム売却）",
        "style": "danger",
        "emoji": "📦",
        "row": 0,
        "order_in_row": 1
    },
    {
        "component_key": "open_inventory",
        "panel_key": "profile",
        "component_type": "button",
        "label": "所持品を見る",
        "style": "primary",
        "emoji": "📦",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "start_fishing_river",
        "panel_key": "panel_fishing_river",
        "component_type": "button",
        "label": "川で釣りをする",
        "style": "primary",
        "emoji": "🏞️",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "start_fishing_sea",
        "panel_key": "panel_fishing_sea",
        "component_type": "button",
        "label": "海で釣りをする",
        "style": "secondary",
        "emoji": "🌊",
        "row": 0,
        "order_in_row": 1
    },
    {
        "component_key": "start_transfer",
        "panel_key": "atm",
        "component_type": "button",
        "label": "コインを送る",
        "style": "success",
        "emoji": "💸",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "start_dice_game",
        "panel_key": "panel_dice_game",
        "component_type": "button",
        "label": "サイコロゲーム開始",
        "style": "primary",
        "emoji": "🎲",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "start_slot_machine",
        "panel_key": "panel_slot_machine",
        "component_type": "button",
        "label": "スロットマシンをプレイ",
        "style": "success",
        "emoji": "🎰",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "create_rps_room",
        "panel_key": "panel_rps_game",
        "component_type": "button",
        "label": "部屋を作る",
        "style": "secondary",
        "emoji": "✊",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "do_daily_check",
        "panel_key": "panel_tasks",
        "component_type": "button",
        "label": "出席チェック",
        "style": "success",
        "emoji": "✅",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "open_quests",
        "panel_key": "panel_tasks",
        "component_type": "button",
        "label": "クエスト確認",
        "style": "primary",
        "emoji": "📜",
        "row": 0,
        "order_in_row": 1
    },
    {
        "component_key": "create_farm",
        "panel_key": "panel_farm_creation",
        "component_type": "button",
        "label": "農場を作る",
        "style": "success",
        "emoji": "🌱",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "enter_mine",
        "panel_key": "panel_mining",
        "component_type": "button",
        "label": "入場する",
        "style": "secondary",
        "emoji": "⛏️",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "create_friend_invite",
        "panel_key": "friend_invite",
        "component_type": "button",
        "label": "招待コードを作成",
        "style": "success",
        "emoji": "💌",
        "row": 0,
        "order_in_row": 0
    },
]

# --- [관리자용 명령어 - 한국어 유지] ---
SETUP_COMMAND_MAP = {
    "panel_roles": {
        "type": "panel", "cog_name": "RolePanel", "key": "auto_role_channel_id",
        "friendly_name": "역할 자동부여 패널", "channel_type": "text"
    },
    "panel_server_guide": {
        "type": "panel", "cog_name": "Onboarding", "key": "server_guide_panel_channel_id",
        "friendly_name": "서버 안내 패널", "channel_type": "text"
    },
    # [추가] 새로운 주민 등록(자기소개) 패널 추가
    "panel_introduction": {
        "type": "panel", "cog_name": "Introduction", "key": "introduction_panel_channel_id",
        # [수정] '주민 등록' -> '자기소개'
        "friendly_name": "자기소개 패널", "channel_type": "text"
    },
    "panel_nicknames": {
        "type": "panel", "cog_name": "Nicknames", "key": "nickname_panel_channel_id",
        "friendly_name": "닉네임 변경 패널", "channel_type": "text"
    },
    "panel_level_check": {
        "type": "panel", "cog_name": "LevelSystem", "key": "level_check_panel_channel_id",
        "friendly_name": "[게임] 레벨 확인 패널", "channel_type": "text"
    },
    "channel_job_advancement": {
        "type": "channel", "cog_name": "LevelSystem", "key": "job_advancement_channel_id",
        "friendly_name": "[채널] 전직소", "channel_type": "text"
    },
    "panel_anonymous_board": {
        "type": "panel", "cog_name": "AnonymousBoard", "key": "anonymous_board_channel_id",
        "friendly_name": "[패널] 익명 게시판", "channel_type": "text"
    },
    "panel_warning": {
        "type": "panel", "cog_name": "WarningSystem", "key": "warning_panel_channel_id",
        "friendly_name": "[패널] 벌점 관리", "channel_type": "text"
    },
    "panel_custom_embed": {
        "type": "panel", "cog_name": "CustomEmbed", "key": "custom_embed_panel_channel_id",
        "friendly_name": "[패널] 커스텀 임베드 전송", "channel_type": "text"
    },
    "panel_commerce": {
        "type": "panel", "cog_name": "Commerce", "key": "commerce_panel_channel_id",
        "friendly_name": "[게임] 상점 패널", "channel_type": "text"
    },
    "panel_fishing_river": {
        "type": "panel", "cog_name": "Fishing", "key": "river_fishing_panel_channel_id",
        "friendly_name": "[게임] 강 낚시터 패널", "channel_type": "text"
    },
    "panel_fishing_sea": {
        "type": "panel", "cog_name": "Fishing", "key": "sea_fishing_panel_channel_id",
        "friendly_name": "[게임] 바다 낚시터 패널", "channel_type": "text"
    },
    "panel_profile": {
        "type": "panel", "cog_name": "UserProfile", "key": "profile_panel_channel_id",
        "friendly_name": "[게임] 프로필 패널", "channel_type": "text"
    },
    "panel_atm": {
        "type": "panel", "cog_name": "Atm", "key": "atm_panel_channel_id",
        "friendly_name": "[게임] ATM 패널", "channel_type": "text"
    },
    "panel_dice_game": {
        "type": "panel", "cog_name": "DiceGame", "key": "dice_game_panel_channel_id",
        "friendly_name": "[게임] 주사위 게임 패널", "channel_type": "text"
    },
    "panel_slot_machine": {
        "type": "panel", "cog_name": "SlotMachine", "key": "slot_machine_panel_channel_id",
        "friendly_name": "[게임] 슬롯머신 패널", "channel_type": "text"
    },
    "panel_rps_game": {
        "type": "panel", "cog_name": "RPSGame", "key": "rps_game_panel_channel_id",
        "friendly_name": "[게임] 가위바위보 패널", "channel_type": "text"
    },
    "panel_tasks": {
        "type": "panel", "cog_name": "Quests", "key": "tasks_panel_channel_id",
        "friendly_name": "[게임] 일일 게시판 패널", "channel_type": "text"
    },
    "panel_farm_creation": {
        "type": "panel", "cog_name": "Farm", "key": "farm_creation_panel_channel_id",
        "friendly_name": "[게임] 농장 생성 패널", "channel_type": "text"
    },
    "panel_mining": {
        "type": "panel", "cog_name": "Mining", "key": "mining_panel_channel_id",
        "friendly_name": "[게임] 광산 패널", "channel_type": "text"
    },
    "panel_trade": {
        "type": "panel", "cog_name": "Trade", "key": "trade_panel_channel_id",
        "friendly_name": "[게임] 거래소 패널", "channel_type": "text"
    },
    "panel_pet_exploration": {
        "type": "panel", "cog_name": "Exploration", "key": "exploration_panel_channel_id",
        "friendly_name": "[게임] 펫 탐사 패널", "channel_type": "text"
    },
    "panel_pet_pvp": {
        "type": "panel", "cog_name": "PetPvP", "key": "pet_pvp_panel_channel_id",
        "friendly_name": "[게임] 펫 대전장 패널", "channel_type": "text"
    },
    "log_trade": {
        "type": "channel", "cog_name": "Trade", "key": "trade_log_channel_id",
        "friendly_name": "[로그] 거래 기록", "channel_type": "text"
    },
    "panel_inquiry": {
        "type": "panel", "cog_name": "TicketSystem", "key": "inquiry_panel_channel_id",
        "friendly_name": "[티켓] 문의/건의 패널", "channel_type": "text"
    },
    "panel_report": {
        "type": "panel", "cog_name": "TicketSystem", "key": "report_panel_channel_id",
        "friendly_name": "[티켓] 유저 신고 패널", "channel_type": "text"
    },
    "channel_new_welcome": {
        "type": "channel", "cog_name": "MemberEvents", "key": "new_welcome_channel_id",
        "friendly_name": "신규 멤버 환영 채널", "channel_type": "text"
    },
    "channel_farewell": {
        "type": "channel", "cog_name": "MemberEvents", "key": "farewell_channel_id",
        "friendly_name": "멤버 퇴장 안내 채널", "channel_type": "text"
    },
    "channel_main_chat": {
        "type": "channel", "cog_name": "Onboarding", "key": "main_chat_channel_id",
        "friendly_name": "메인 채팅 채널 (자기소개 승인 후 안내)", "channel_type": "text"
    },
    "channel_onboarding_approval": {
        "type": "channel", "cog_name": "Onboarding", "key": "onboarding_approval_channel_id",
        "friendly_name": "자기소개 승인/거절 채널", "channel_type": "text"
    },
    "channel_nickname_approval": {
        "type": "channel", "cog_name": "Nicknames", "key": "nickname_approval_channel_id",
        "friendly_name": "닉네임 변경 승인 채널", "channel_type": "text"
    },
    "channel_vc_creator_3p": {
        "type": "channel", "cog_name": "VoiceMaster", "key": "vc_creator_channel_id_3p",
        "friendly_name": "음성 채널 자동 생성 (게임)", "channel_type": "voice"
    },
    "channel_vc_creator_4p": {
        "type": "channel", "cog_name": "VoiceMaster", "key": "vc_creator_channel_id_4p",
        "friendly_name": "음성 채널 자동 생성 (광장)", "channel_type": "voice"
    },
    "channel_vc_creator_newbie": {
        "type": "channel", "cog_name": "VoiceMaster", "key": "vc_creator_channel_id_ベンチ",
        "friendly_name": "[음성 채널] 뉴비 전용 생성기", "channel_type": "voice"
    },
    "channel_vc_creator_vip": {
        "type": "channel", "cog_name": "VoiceMaster", "key": "vc_creator_channel_id_마이룸",
        "friendly_name": "[음성 채널] VIP 전용 생성기", "channel_type": "voice"
    },
    "log_nickname": {
        "type": "channel", "cog_name": "Nicknames", "key": "nickname_log_channel_id",
        "friendly_name": "[로그] 닉네임 변경 기록", "channel_type": "text"
    },
    "log_intro_approval": {
        "type": "channel", "cog_name": "Onboarding", "key": "introduction_channel_id",
        "friendly_name": "[로그] 자기소개 승인 기록", "channel_type": "text"
    },
    "log_intro_rejection": {
        "type": "channel", "cog_name": "Onboarding", "key": "introduction_rejection_log_channel_id",
        "friendly_name": "[로그] 자기소개 거절 기록", "channel_type": "text"
    },
    "log_item_warning_deduct": {
        "type": "channel", "cog_name": "ItemSystem", "key": "log_item_warning_deduct",
        "friendly_name": "[로그] 벌점 차감권 사용 내역", "channel_type": "text"
    },
    "log_item_event_priority": {
        "type": "channel", "cog_name": "ItemSystem", "key": "log_item_event_priority",
        "friendly_name": "[로그] 이벤트 우선권 사용 내역", "channel_type": "text"
    },
    "log_message": {
        "type": "channel", "cog_name": "MessageLogger", "key": "log_channel_message",
        "friendly_name": "[로그] 메시지 (수정/삭제)", "channel_type": "text"
    },
    "log_voice": {
        "type": "channel", "cog_name": "VoiceLogger", "key": "log_channel_voice",
        "friendly_name": "[로그] 음성 채널 (참여/이동/퇴장)", "channel_type": "text"
    },
    "log_member": {
        "type": "channel", "cog_name": "MemberLogger", "key": "log_channel_member",
        "friendly_name": "[로그] 멤버 활동 (역할 부여/닉네임)", "channel_type": "text"
    },
    "log_channel": {
        "type": "channel", "cog_name": "ChannelLogger", "key": "log_channel_channel",
        "friendly_name": "[로그] 채널 관리 (생성/삭제/변경)", "channel_type": "text"
    },
    "log_server": {
        "type": "channel", "cog_name": "ServerLogger", "key": "log_channel_server",
        "friendly_name": "[로그] 서버 및 역할 관리", "channel_type": "text"
    },
    "log_warning": {
        "type": "channel", "cog_name": "WarningSystem", "key": "warning_log_channel_id",
        "friendly_name": "[로그] 벌점 발급 기록", "channel_type": "text"
    },
    "log_daily_check": {
        "type": "channel", "cog_name": "Quests", "key": "log_daily_check_channel_id",
        "friendly_name": "[로그] 출석체크 기록", "channel_type": "text"
    },
    "log_market": {
        "type": "channel", "cog_name": "EconomyCore", "key": "market_log_channel_id",
        "friendly_name": "[로그] 시장 시세 변동", "channel_type": "text"
    },
    "log_coin": {
        "type": "channel", "cog_name": "EconomyCore", "key": "coin_log_channel_id",
        "friendly_name": "[로그] 코인 활동", "channel_type": "text"
    },
    "log_job_advancement": {
        "type": "channel", "cog_name": "LevelSystem", "key": "job_log_channel_id",
        "friendly_name": "[로그] 전직 기록", "channel_type": "text"
    },
    "log_fishing": {
        "type": "channel", "cog_name": "Fishing", "key": "fishing_log_channel_id",
        "friendly_name": "[로그] 낚시 성공 기록", "channel_type": "text"
    },
    "log_item_mine_pass": {
        "type": "channel", "cog_name": "ItemSystem", "key": "log_item_mine_pass",
        "friendly_name": "[로그] 광산 입장권 사용 내역", "channel_type": "text"
    },
    "log_pet_levelup": {
        "type": "channel", "cog_name": "PetSystem", "key": "log_pet_levelup_channel_id",
        "friendly_name": "[로그] 펫 성장 기록", "channel_type": "text"
    },
    "channel_bump_reminder": {
        "type": "channel", "cog_name": "Reminder", "key": "bump_reminder_channel_id",
        "friendly_name": "[알림] Disboard BUMP 채널", "channel_type": "text"
    },
    "channel_dicoall_reminder": {
        "type": "channel", "cog_name": "Reminder", "key": "dicoall_reminder_channel_id",
        "friendly_name": "[알림] Dicoall UP 채널", "channel_type": "text"
    },
    "channel_dissoku_reminder": {
        "type": "channel",
        "cog_name": "Reminder",
        "key": "dissoku_reminder_channel_id",
        "friendly_name": "[알림] ディス速 VOTE 채널",
        "channel_type": "text"
    },
    "channel_weather": {
        "type": "channel", "cog_name": "WorldSystem", "key": "weather_channel_id",
        "friendly_name": "[알림] 날씨 예보 채널", "channel_type": "text"
    },
    "onboarding_private_age_log_channel_id": {
        "type": "channel", "cog_name": "Onboarding", "key": "onboarding_private_age_log_channel_id", 
        "friendly_name": "[온보딩] 비공개 나이 기록 채널", "channel_type": "text"
    },
    "panel_blacksmith": {
        "type": "panel", "cog_name": "Blacksmith", "key": "blacksmith_panel_channel_id",
        "friendly_name": "[게임] 대장간 패널", "channel_type": "text"
    },
    "log_blacksmith_complete": {
        "type": "channel", "cog_name": "Blacksmith", "key": "log_blacksmith_channel_id",
        "friendly_name": "[로그] 대장간 제작 완료", "channel_type": "text"
    },
    "panel_cooking_creation": {
        "type": "panel", "cog_name": "Cooking", "key": "cooking_creation_panel_channel_id",
        "friendly_name": "[게임] 요리 시작 패널", "channel_type": "text"
    },
    "log_cooking_complete": {
        "type": "channel", "cog_name": "Cooking", "key": "log_cooking_complete_channel_id",
        "friendly_name": "[로그] 요리 완성", "channel_type": "text"
    },
    "log_recipe_discovery": {
        "type": "channel", "cog_name": "Cooking", "key": "log_recipe_discovery_channel_id",
        "friendly_name": "[로그] 레시피 발견", "channel_type": "text"
    },
    "log_item_job_reset": {
        "type": "channel", "cog_name": "ItemSystem", "key": "log_item_job_reset",
        "friendly_name": "[로그] 직업 초기화권 사용 내역", "channel_type": "text"
    },
    "panel_friend_invite": {
        "type": "panel", "cog_name": "FriendInvite", "key": "friend_invite_panel_channel_id",
        "friendly_name": "[게임] 친구 초대 패널", "channel_type": "text"
    },
    "log_friend_invite": {
        "type": "channel", "cog_name": "FriendInvite", "key": "friend_invite_log_channel_id",
        "friendly_name": "[로그] 친구 초대 이벤트", "channel_type": "text"
    },
    "panel_incubator": {
        "type": "panel", "cog_name": "PetSystem", "key": "incubator_panel_channel_id",
        "friendly_name": "[게임] 펫 인큐베이터 패널", "channel_type": "text"
    },
    "channel_weekly_boss": {
        "type": "channel", "cog_name": "BossRaid", "key": "weekly_boss_channel_id",
        "friendly_name": "[보스] 주간 보스 채널", "channel_type": "text"
    },
    "channel_monthly_boss": {
        "type": "channel", "cog_name": "BossRaid", "key": "monthly_boss_channel_id",
        "friendly_name": "[보스] 월간 보스 채널", "channel_type": "text"
    },
    "log_boss_events": {
        "type": "channel", "cog_name": "BossRaid", "key": "boss_log_channel_id",
        "friendly_name": "[로그] 보스 이벤트 기록", "channel_type": "text"
    },
}

ADMIN_ACTION_MAP = {
    "status_show": "[현황] 설정 대시보드 표시",
    "server_id_set": "[중요] 서버 ID 설정",
    "panels_regenerate_all": "[패널] 모든 관리 패널 재설치",
    "template_edit": "[템플릿] 임베드 템플릿 편집",
    "request_regenerate_all_game_panels": "[게임] 모든 게임 패널 재설치 요청",
    "roles_sync": "DB同期化",
    "strings_sync": "[UI] 모든 UI 텍스트 DB와 동기화",
    "game_data_reload": "[게임] 게임 데이터 새로고침",
    "stats_set": "[통계] 통계 채널 설정/제거",
    "stats_refresh": "[통계] 모든 통계 채널 새로고침",
    "stats_list": "[통계] 설정된 통계 채널 목록",
    "coin_give": "[코인] 유저에게 코인 지급",
    "coin_take": "[코인] 유저의 코인 차감",
    "xp_give": "[XP] 유저에게 XP 지급",
    "level_set": "[레벨] 유저 레벨 설정",
    "trigger_daily_updates": "[수동] 시세 및 작물 상태 업데이트 즉시 실행",
    "farm_next_day": "[농장] 다음 날로 시간 넘기기 (테스트용)",
    "farm_reset_date": "[농장] 시간을 현재로 초기화 (테스트용)",
    "pet_hatch_now": "[펫] 펫 즉시 부화 (테스트용)",
    "pet_admin_levelup": "[펫] 펫 1레벨업 (테스트용)",
    "pet_level_set": "[펫] 펫 레벨 설정 (테스트용)",
    "exploration_complete_now": "[펫] 펫 탐사 즉시 완료 (테스트용)",
    "boss_spawn_test": "[보스] 강제 소환 (테스트용)",
    "boss_defeat_test": "[보스] 강제 처치 (테스트용)",
}
# --- [관리자용 명령어 끝] ---

ADMIN_ROLE_KEYS = [
    "role_admin_total", "role_staff_village_chief", "role_staff_deputy_chief",
    "role_staff_police", "role_staff_festival", "role_staff_pr",
    "role_staff_design", "role_staff_secretary", "role_staff_newbie_helper",
    "role_approval"
]
STATIC_AUTO_ROLE_PANELS = {
    "panel_roles": {
        "panel_key":
        "panel_roles",
        "embed_key":
        "panel_roles",
        "categories": [
            {
                "id": "notifications",
                "label": "🔔 通知",
                "description": "受け取りたい通知を選択してください。",
                "emoji": "🔔"
            },
            {
                "id": "games",
                "label": "🎮 ゲーム",
                "description": "プレイするゲームを選択してください。",
                "emoji": "🎮"
            },
        ],
        "roles": {
            "notifications": [
                {
                    "role_id_key": "role_notify_voice",
                    "label": "通話募集"
                },
                {
                    "role_id_key": "role_notify_friends",
                    "label": "友達募集"
                },
                {
                    "role_id_key": "role_notify_disboard",
                    "label": "Disboard"
                },
                {
                    "role_id_key": "role_notify_up",
                    "label": "Dicoall"
                },
                # --- ▼▼▼ [추가] ディス速 역할 추가 ▼▼▼ ---
                {
                    "role_id_key": "role_notify_dissoku",
                    "label": "ディス速"
                },
                # --- ▲▲▲ [추가 완료] ▲▲▲ ---
            ],
            "games": [
                { "role_id_key": "role_game_minecraft", "label": "マイクラ-Minecraft" },
                { "role_id_key": "role_game_valorant", "label": "ヴァロ-VALORANT" },
                { "role_id_key": "role_game_overwatch", "label": "オバウォ-Overwatch" },
                { "role_id_key": "role_game_lol", "label": "ロル-League of Legends" },
                { "role_id_key": "role_game_mahjong", "label": "麻雀-Mahjong" },
                { "role_id_key": "role_game_amongus", "label": "アモアス-Among Us" },
                { "role_id_key": "role_game_mh", "label": "モンハン-Monster Hunter" },
                { "role_id_key": "role_game_genshin", "label": "原神-Genshin Impact" },
                { "role_id_key": "role_game_apex", "label": "エペ-Apex Legends" },
                { "role_id_key": "role_game_splatoon", "label": "スプラ-Splatoon" },
                { "role_id_key": "role_game_godfield", "label": "ゴッフィ-God Field" },
                { "role_id_key": "role_platform_steam", "label": "スチーム-Steam" },
                { "role_id_key": "role_platform_smartphone", "label": "スマホ-Smartphone" },
                { "role_id_key": "role_platform_switch", "label": "スイッチ-Switch" },
            ],
        }
    }
}
TICKET_MASTER_ROLES = ["role_staff_village_chief", "role_staff_deputy_chief"]
TICKET_STAFF_GENERAL_ROLES = ["role_approval"]
TICKET_STAFF_SPECIFIC_ROLES = [
    "role_staff_police", "role_staff_festival", "role_staff_pr",
    "role_staff_design", "role_staff_secretary", "role_staff_newbie_helper"
]
TICKET_REPORT_ROLES = ["role_staff_police"]
POLICE_ROLE_KEY = "role_staff_police"
WARNING_THRESHOLDS = [
    { "count": 1, "role_key": "role_warning_level_1" },
    { "count": 2, "role_key": "role_warning_level_2" },
    { "count": 3, "role_key": "role_warning_level_3" },
    { "count": 4, "role_key": "role_warning_level_4" },
]
CUSTOM_EMBED_SENDER_ROLES = [
    "role_admin_total", "role_staff_village_chief", "role_staff_deputy_chief"
]

JOB_SYSTEM_CONFIG = {
    "JOB_ROLE_MAP": {
        "fisherman": "role_job_fisherman",
        "farmer": "role_job_farmer",
        "miner": "role_job_miner",
        "chef": "role_job_chef",
        "master_angler": "role_job_master_angler",
        "master_farmer": "role_job_master_farmer",
        "expert_miner": "role_job_expert_miner",
        "master_chef": "role_job_master_chef"
    },
    "LEVEL_TIER_ROLES": [{
        "level": 150, "role_key": "role_resident_elder"
    }, {
        "level": 100, "role_key": "role_resident_veteran"
    }, {
        "level": 50, "role_key": "role_resident_regular"
    }, {
        "level": 1, "role_key": "role_resident_rookie"
    }]
}

AGE_ROLE_MAPPING = [{
    "key": "role_info_age_00s", "range": [2000, 2100], "name": "00年代生まれ"
}, {
    "key": "role_info_age_90s", "range": [1990, 2000], "name": "90年代生まれ"
}, {
    "key": "role_info_age_80s", "range": [1980, 1990], "name": "80年代生まれ"
}, {
    "key": "role_info_age_70s", "range": [1970, 1980], "name": "70年代生まれ"
}]
GAME_CONFIG = {
    "CURRENCY_ICON": "🪙",
    "FISHING_BITE_REACTION_TIME": 3.0,
    "FISHING_BIG_CATCH_THRESHOLD": 70.0,
    "FISHING_SEA_REQ_TIER": 3,
    "FISHING_WAITING_IMAGE_URL": "https://i.imgur.com/AcLgC2g.gif",
    "RPS_LOBBY_TIMEOUT": 60,
    "RPS_CHOICE_TIMEOUT": 45,
    "RPS_MAX_PLAYERS": 5,
    "SLOT_MAX_ACTIVE": 5,
    "XP_FROM_FISHING": 20,
    "XP_FROM_FARMING": 15,
    "XP_FROM_VOICE": 10,
    "XP_FROM_CHAT": 5,
    "VOICE_TIME_REQUIREMENT_MINUTES": 10,
    "VOICE_REWARD_RANGE": [10, 15],
    "CHAT_MESSAGE_REQUIREMENT": 20,
    "CHAT_REWARD_RANGE": [5, 10],
    "JOB_ADVANCEMENT_LEVELS": [50, 100]
}

PROFILE_RANK_ROLES = [{
    "role_key": "role_staff_village_chief", "priority": 100
}, {
    "role_key": "role_staff_deputy_chief", "priority": 95
}, {
    "role_key": "role_approval", "priority": 90
}, {
    "role_key": "role_premium_booster", "priority": 80
}, {
    "role_key": "role_resident_elder", "priority": 70
}, {
    "role_key": "role_resident_veteran", "priority": 60
}, {
    "role_key": "role_resident_regular", "priority": 50
}, {
    "role_key": "role_resident_rookie", "priority": 10
}]

UI_STRINGS = {
    "commerce": {
        "item_view_desc": "現在の所持金: `{balance}`{currency_icon}\n購入したい商品を選択してください。",
        "wip_category": "このカテゴリの商品は現在準備中です。"
    },
    "profile_view": {
        "base_title": "{user_name}の所持品",
        "tabs": [
            {"key": "info", "title_suffix": " - 情報", "label": "情報", "emoji": "ℹ️"},
            {"key": "item", "title_suffix": " - アイテム", "label": "アイテム", "emoji": "📦"},
            {"key": "gear", "title_suffix": " - 装備", "label": "装備", "emoji": "⚒️"},
            {"key": "pet", "title_suffix": " - ペットアイテム", "label": "ペット", "emoji": "🐾"},
            {"key": "seed", "title_suffix": " - 種", "label": "種", "emoji": "🌱"},
            {"key": "fish", "title_suffix": " - 水槽", "label": "水槽", "emoji": "🐠"},
            {"key": "crop", "title_suffix": " - 作物", "label": "作物", "emoji": "🌾"},
            {"key": "mineral", "title_suffix": " - 鉱物", "label": "鉱物", "emoji": "💎"},
            {"key": "food", "title_suffix": " - 料理", "label": "料理", "emoji": "🍲"},
            {"key": "loot", "title_suffix": " - 戦利品", "label": "戦利品", "emoji": "🏆"}
        ],
        "info_tab": {
            "description": "下のタブを選択して詳細情報を確認してください。",
            "field_balance": "所持金",
            "field_rank": "等級",
            "default_rank_name": "新人住民"
        },
        "item_tab": {
            "no_items": "所持しているアイテムがありません。",
            "use_item_button_label": "アイテムを使用"
        },
        "item_usage_view": {
            "embed_title": "✨ アイテム使用",
            "embed_description": "インベントリから使用するアイテムを選択してください。",
            "select_placeholder": "使用するアイテムを選択...",
            "back_button": "戻る",
            "no_usable_items": "使用できるアイテムがありません。",
            "reason_modal_title": "{item_name} 使用",
            "reason_modal_label": "使用事由（例：イベント名）",
            "reason_modal_placeholder": "どのイベントで使用しますか？",
            "request_success": "✅ 「{item_name}」の使用を要請しました。しばらくすると処理されます。",
            "consume_success": "✅ 「{item_name}」を使用しました。",
            "farm_expand_success": "✅ 農場が1マス拡張されました！（現在の広さ: {plot_count}/25）",
            "farm_expand_fail_max": "❌ 農場はすでに最大サイズ（25マス）です。",
            "farm_expand_fail_no_farm": "❌ まず農場を作成してください。",
            "error_generic": "❌ アイテム使用中にエラーが発生しました。",
            "error_invalid_item": "❌ 無効なアイテム情報です。",
            "error_role_not_found": "❌ アイテムに対応する役職が見つかりません。"
        },
        "gear_tab": { "no_owned_gear": "所持している装備がありません。" },
        "fish_tab": {
            "no_fish": "水槽に魚がいません。",
            "pagination_footer": "ページ {current_page} / {total_pages}"
        },
        "seed_tab": { "no_items": "所持している種がありません。" },
        "crop_tab": { "no_items": "所持している作物がありません。" },
        "mineral_tab": { "no_items": "所持している鉱物がありません。" },
        "food_tab": { "no_items": "所持している料理がありません。" },
        "wip_tab": { "description": "この機能は現在準備中です。" },
        "pagination_buttons": { "prev": "◀", "next": "▶" },
        "gear_select_view": {
            "embed_title": "{category_name} 変更",
            "embed_description": "装着するアイテムを選択してください。",
            "placeholder": "{category_name} 選択...",
            "unequip_prefix": "✋",
            "back_button": "戻る"
        }
    }
}
JOB_ADVANCEMENT_DATA = {
    "50": [
        {
            "job_key": "fisherman", "job_name": "釣り人", "role_key": "role_job_fisherman",
            "description": "魚を釣ることに特化した専門家です。",
            "abilities": [
                {"ability_key": "fish_bait_saver_1", "ability_name": "エサ節約（確率）", "description": "釣りの際、一定確率でエサを消費しません。"},
                {"ability_key": "fish_bite_time_down_1", "ability_name": "食いつき時間短縮", "description": "魚がエサに食いつくまでの時間が全体的に2秒短縮されます。"}
            ]
        },
        {
            "job_key": "farmer", "job_name": "農家", "role_key": "role_job_farmer",
            "description": "作物を育てて収穫することに特化した専門家です。",
            "abilities": [
                {"ability_key": "farm_seed_saver_1", "ability_name": "種節約（確率）", "description": "種を植える際、一定確率で種を消費しません。"},
                {"ability_key": "farm_water_retention_1", "ability_name": "水分維持力UP", "description": "作物が水分をより長く保ち、水やりの間隔が長くなります。"}
            ]
        },
        {
            "job_key": "miner", "job_name": "鉱夫", "role_key": "role_job_miner",
            "description": "鉱物採掘に特化した専門家です。",
            "abilities": [
                {"ability_key": "mine_time_down_1", "ability_name": "迅速な採掘", "description": "鉱石採掘に必要な時間が3秒短縮されます。"},
                {"ability_key": "mine_duration_up_1", "ability_name": "集中探査", "description": "鉱山入場時、15%の確率で制限時間が2倍（20分）に増加します。"}
            ]
        },
        {
            "job_key": "chef", "job_name": "料理人", "role_key": "role_job_chef",
            "description": "様々な材料でおいしい料理を作る料理の専門家です。",
            "abilities": [
                {"ability_key": "cook_ingredient_saver_1", "ability_name": "倹約な腕前（確率）", "description": "料理する際、15%の確率で材料を消費しません。"},
                {"ability_key": "cook_time_down_1", "ability_name": "料理の基本", "description": "すべての料理の所要時間が10%短縮されます。"}
            ]
        }
    ],
    "100": [
        {
            "job_key": "master_angler", "job_name": "太公望", "role_key": "role_job_master_angler",
            "description": "釣りの道を極め、伝説の魚を追い求める者。釣り人の上位職です。", "prerequisite_job": "fisherman",
            "abilities": [
                {"ability_key": "fish_rare_up_2", "ability_name": "レア魚確率UP（大）", "description": "珍しい魚を釣る確率が上昇します。"},
                {"ability_key": "fish_size_up_2", "ability_name": "魚サイズUP（大）", "description": "釣れる魚の平均サイズが大きくなります。"}
            ]
        },
        {
            "job_key": "master_farmer", "job_name": "大農", "role_key": "role_job_master_farmer",
            "description": "農業の真髄を悟り、大地から最大の恵みを得る者。農家の上位職です。", "prerequisite_job": "farmer",
            "abilities": [
                {"ability_key": "farm_yield_up_2", "ability_name": "収穫量UP（大）", "description": "作物を収穫する際の収穫量が大幅に増加します。"},
                {"ability_key": "farm_seed_harvester_2", "ability_name": "種収穫（確率）", "description": "作物収穫時、低確率でその作物の種を1～3個獲得します。"}
            ]
        },
        {
            "job_key": "expert_miner", "job_name": "専門の鉱夫", "role_key": "role_job_expert_miner",
            "description": "鉱脈の流れを読み、珍しい鉱物を見つけ出すベテランです。鉱夫の上位職です。", "prerequisite_job": "miner",
            "abilities": [
                {"ability_key": "mine_rare_up_2", "ability_name": "大当たり発見", "description": "珍しい鉱物を発見する確率が大幅に増加します。"},
                {"ability_key": "mine_double_yield_2", "ability_name": "豊富な鉱脈", "description": "鉱石採掘時、20%の確率で鉱石を2個獲得します。"}
            ]
        },
        {
            "job_key": "master_chef", "job_name": "マスターシェフ", "role_key": "role_job_master_chef",
            "description": "料理の境地に達し、平凡な材料でも最高の味を引き出す者。料理人の上位職です。", "prerequisite_job": "chef",
            "abilities": [
                {"ability_key": "cook_quality_up_2", "ability_name": "職人の腕前", "description": "料理完成時、10%の確率で「特級品」の料理を作ります。特級品はより高く売却できます。"},
                {"ability_key": "cook_double_yield_2", "ability_name": "豊かな食卓", "description": "料理完成時、15%の確率で結果物を2個獲得します。"}
            ]
        }
    ]
}
BOSS_REWARD_TIERS = {
    "weekly": [
        {"percentile": 0.03, "name": "最上位貢献者 (1-3%)",   "coins": [20000, 30000], "xp": [2500, 3500], "rare_item_chance": 1.0},
        {"percentile": 0.10, "name": "上位貢献者 (4-10%)",    "coins": [12000, 18000], "xp": [1500, 2200], "rare_item_chance": 0.75},
        {"percentile": 0.30, "name": "中核貢献者 (11-30%)",   "coins": [7000, 11000],  "xp": [800, 1200],  "rare_item_chance": 0.50},
        {"percentile": 0.50, "name": "優秀貢献者 (31-50%)",   "coins": [4000, 6000],   "xp": [400, 600],   "rare_item_chance": 0.25},
        {"percentile": 0.80, "name": "参加者 (51-80%)",      "coins": [1500, 2500],   "xp": [150, 250],   "rare_item_chance": 0.10},
        {"percentile": 1.01, "name": "一般参加者 (81%以下)","coins": [500, 1000],    "xp": [50, 100],    "rare_item_chance": 0.0}
    ],
    "monthly": [
        {"percentile": 0.03, "name": "最上位貢献者 (1-3%)",   "coins": [100000, 150000], "xp": [10000, 15000], "rare_item_chance": 1.0},
        {"percentile": 0.10, "name": "上位貢献者 (4-10%)",    "coins": [60000, 90000],   "xp": [6000, 9000],   "rare_item_chance": 0.80},
        {"percentile": 0.30, "name": "中核貢献者 (11-30%)",   "coins": [35000, 55000],   "xp": [3000, 5000],   "rare_item_chance": 0.60},
        {"percentile": 0.50, "name": "優秀貢献者 (31-50%)",   "coins": [20000, 30000],   "xp": [1500, 2500],   "rare_item_chance": 0.35},
        {"percentile": 0.80, "name": "参加者 (51-80%)",      "coins": [8000, 12000],    "xp": [800, 1200],    "rare_item_chance": 0.15},
        {"percentile": 1.01, "name": "一般参加者 (81%以下)","coins": [3000, 5000],     "xp": [300, 500],     "rare_item_chance": 0.0}
    ]
}
