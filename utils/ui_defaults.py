# bot-management/utils/ui_defaults.py
"""
봇이 사용하는 모든 UI 요소 및 핵심 매핑 데이터의 기본값을 정의하는 파일입니다.
봇이 시작될 때 이 파일의 데이터가 Supabase 데이터베이스에 동기화됩니다.
"""

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 1. 역할 키 맵 (Role Key Map)
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
UI_ROLE_KEY_MAP = {
    # --- [핵심] 접두사 역할 및 우선순위 ---
    "role_admin_total": {
        "name": "숲의 요정",
        "is_prefix": True,
        "priority": 100
    },
    "role_staff_village_chief": {
        "name": "촌장",
        "is_prefix": True,
        "priority": 90
    },
    "role_staff_deputy_chief": {
        "name": "부촌장",
        "is_prefix": True,
        "priority": 85
    },
    "role_approval": {
        "name": "직원",
        "is_prefix": True,
        "priority": 60
    },
    "role_premium_booster": {
        "name": "후원자",
        "is_prefix": True,
        "priority": 55
    },
    "role_resident_elder": {
        "name": "장로",
        "is_prefix": True,
        "priority": 50
    },
    "role_job_master_angler": {
        "name": "강태공",
        "is_prefix": True,
        "priority": 16
    },
    "role_job_master_farmer": {
        "name": "대농",
        "is_prefix": True,
        "priority": 16
    },
    "role_job_fisherman": {
        "name": "낚시꾼",
        "is_prefix": True,
        "priority": 15
    },
    "role_job_farmer": {
        "name": "농부",
        "is_prefix": True,
        "priority": 15
    },
    "role_resident": {
        "name": "주민",
        "is_prefix": True,
        "priority": 10
    },
    "role_guest": {
        "name": "여행객",
        "is_prefix": True,
        "priority": 5
    },
    "role_resident_veteran": {
        "name": "베테랑",
        "is_prefix": True,
        "priority": 0
    },
    "role_resident_regular": {
        "name": "단골",
        "is_prefix": True,
        "priority": 0
    },
    "role_resident_rookie": {
        "name": "새내기",
        "is_prefix": True,
        "priority": 0
    },

    # --- 그 외 접두사가 아닌 역할들 ---
    "role_staff_police": {
        "name": "경찰관",
        "is_prefix": False,
        "priority": 0
    },
    "role_staff_festival": {
        "name": "축제 담당",
        "is_prefix": False,
        "priority": 0
    },
    "role_staff_pr": {
        "name": "홍보 담당",
        "is_prefix": False,
        "priority": 0
    },
    "role_staff_design": {
        "name": "디자이너",
        "is_prefix": False,
        "priority": 0
    },
    "role_staff_secretary": {
        "name": "서기",
        "is_prefix": False,
        "priority": 0
    },
    "role_staff_newbie_helper": {
        "name": "도우미",
        "is_prefix": False,
        "priority": 0
    },

    # --- 온보딩/역할 패널 구분선 역할 ---
    "role_onboarding_step_1": {
        "name": "════════════게임════════════",
        "is_prefix": False,
        "priority": 0
    },
    "role_onboarding_step_2": {
        "name": "════════════알림════════════",
        "is_prefix": False,
        "priority": 0
    },
    "role_onboarding_step_3": {
        "name": "════════════정보════════════",
        "is_prefix": False,
        "priority": 0
    },
    "role_onboarding_step_4": {
        "name": "════════════등급════════════",
        "is_prefix": False,
        "priority": 0
    },
    "role_warning_separator": {
        "name": "════════════벌점════════════",
        "is_prefix": False,
        "priority": 0
    },
    "role_shop_separator": {
        "name": "════════════상점════════════",
        "is_prefix": False,
        "priority": 0
    },

    # --- 개인 정보 역할 (성별, 연령대) ---
    "role_info_male": {
        "name": "남성",
        "is_prefix": False,
        "priority": 0
    },
    "role_info_female": {
        "name": "여성",
        "is_prefix": False,
        "priority": 0
    },
    "role_info_age_private": {
        "name": "비공개",
        "is_prefix": False,
        "priority": 0
    },
    "role_info_age_70s": {
        "name": "70년생",
        "is_prefix": False,
        "priority": 0
    },
    "role_info_age_80s": {
        "name": "80년생",
        "is_prefix": False,
        "priority": 0
    },
    "role_info_age_90s": {
        "name": "90년생",
        "is_prefix": False,
        "priority": 0
    },
    "role_info_age_00s": {
        "name": "00년생",
        "is_prefix": False,
        "priority": 0
    },

    # --- 상점/아이템 역할 ---
    "role_personal_room_key": {
        "name": "마이룸 열쇠",
        "is_prefix": False,
        "priority": 0
    },
    "role_item_warning_deduct": {
        "name": "벌점 1회 차감권",
        "is_prefix": False,
        "priority": 0
    },
    "role_item_event_priority": {
        "name": "이벤트 우선 참여권",
        "is_prefix": False,
        "priority": 0
    },
    "role_item_farm_expansion": {
        "name": "밭 확장 허가증",
        "is_prefix": False,
        "priority": 0
    },

    # --- 알림 역할 ---
    "role_notify_voice": {
        "name": "통화 모집",
        "is_prefix": False,
        "priority": 0
    },
    "role_notify_friends": {
        "name": "친구 모집",
        "is_prefix": False,
        "priority": 0
    },
    "role_notify_disboard": {
        "name": "Disboard",
        "is_prefix": False,
        "priority": 0
    },
    "role_notify_up": {
        "name": "Up",
        "is_prefix": False,
        "priority": 0
    },

    # --- 게임/플랫폼 역할 ---
    "role_game_minecraft": {
        "name": "마인크래프트",
        "is_prefix": False,
        "priority": 0
    },
    "role_game_valorant": {
        "name": "발로란트",
        "is_prefix": False,
        "priority": 0
    },
    "role_game_overwatch": {
        "name": "오버워치",
        "is_prefix": False,
        "priority": 0
    },
    "role_game_lol": {
        "name": "리그 오브 레전드",
        "is_prefix": False,
        "priority": 0
    },
    "role_game_mahjong": {
        "name": "마작",
        "is_prefix": False,
        "priority": 0
    },
    "role_game_amongus": {
        "name": "어몽어스",
        "is_prefix": False,
        "priority": 0
    },
    "role_game_mh": {
        "name": "몬스터 헌터",
        "is_prefix": False,
        "priority": 0
    },
    "role_game_genshin": {
        "name": "원신",
        "is_prefix": False,
        "priority": 0
    },
    "role_game_apex": {
        "name": "에이펙스 레전드",
        "is_prefix": False,
        "priority": 0
    },
    "role_game_gf": {
        "name": "갈틱폰",
        "is_prefix": False,
        "priority": 0
    },
    "role_platform_steam": {
        "name": "스팀",
        "is_prefix": False,
        "priority": 0
    },
    "role_platform_PC": {
        "name": "PC",
        "is_prefix": False,
        "priority": 0
    },
    "role_platform_smartphone": {
        "name": "스마트폰",
        "is_prefix": False,
        "priority": 0
    },
    "role_platform_switch": {
        "name": "콘솔",
        "is_prefix": False,
        "priority": 0
    },

    # --- 벌점 역할 ---
    "role_warning_level_1": {
        "name": "벌점 1회",
        "is_prefix": False,
        "priority": 0
    },
    "role_warning_level_2": {
        "name": "벌점 2회",
        "is_prefix": False,
        "priority": 0
    },
    "role_warning_level_3": {
        "name": "벌점 3회",
        "is_prefix": False,
        "priority": 0
    },
    "role_warning_level_4": {
        "name": "벌점 4회",
        "is_prefix": False,
        "priority": 0
    },
}
ONBOARDING_CHOICES = {
    "gender": [{
        "label": "남성",
        "value": "남성"
    }, {
        "label": "여성",
        "value": "여성"
    }],
    "birth_year_groups": {
        "2000s": [{
            "label": f"{year}년생",
            "value": str(year)
        } for year in range(2009, 1999, -1)],
        "1990s": [{
            "label": f"{year}년생",
            "value": str(year)
        } for year in range(1999, 1989, -1)],
        "1980s": [{
            "label": f"{year}년생",
            "value": str(year)
        } for year in range(1989, 1979, -1)],
        "1970s": [{
            "label": f"{year}년생",
            "value": str(year)
        } for year in range(1979, 1969, -1)],
        "private": [{
            "label": "비공개",
            "value": "비공개"
        }]
    }
}
# [✅✅✅ 핵심 수정 ✅✅✅] 중복 정의를 제거하고, 벌점 차감권의 타입을 변경했습니다.
USABLE_ITEMS = {
    "role_item_warning_deduct": {
        "name": "벌점 1회 차감권",
        "type": "deduct_warning",
        "value": -1,
        "description": "누적된 벌점을 1회 차감합니다.",
        "log_channel_key": "log_item_warning_deduct",
        "log_embed_key": "log_item_use_warning_deduct"
    },
    "role_item_event_priority": {
        "name": "이벤트 우선 참여권",
        "type": "consume_with_reason",
        "description": "이벤트 참가 신청 시 우선권을 행사합니다.",
        "log_channel_key": "log_item_event_priority",
        "log_embed_key": "log_item_use_event_priority"
    },
    "role_item_farm_expansion": {
        "name": "밭 확장 허가증",
        "type": "farm_expansion",
        "description": "자신의 농장을 1칸 확장합니다."
    }
}
UI_EMBEDS = {
    "onboarding_guide_server": {
        "title": "① 서버에 오신 것을 환영합니다!",
        "description":
        "이곳은 게임을 하거나, 이야기를 나누며 자유롭게 지낼 수 있는 공간입니다.\n모두가 쾌적하게 지낼 수 있도록 몇 가지 안내와 규칙이 있습니다.\n\n아래 '다음' 버튼을 눌러 안내를 읽어주세요.",
        "color": 0x5865F2,
        "footer": {
            "text": "1/7 단계"
        }
    },
    "onboarding_guide_bots": {
        "title": "② 봇 소개",
        "description":
        "이 서버에는 생활을 편리하게 해주는 여러 봇이 있습니다.\n\n- **관리 봇**: 역할 부여나 닉네임 변경 등 서버 관리 전반을 담당합니다.\n- **게임 봇**: 낚시, 농장, 카지노 등 미니게임을 즐길 수 있습니다.\n\n각 기능은 해당 채널의 '패널'을 통해 이용할 수 있습니다.",
        "color": 0x5865F2,
        "footer": {
            "text": "2/7 단계"
        }
    },
    "onboarding_guide_rules": {
        "title": "③ 서버 규칙",
        "description":
        "모두가 즐겁게 지내기 위해 다음 규칙을 지켜주세요.\n\n- **존중**: 다른 멤버를 존중하고, 비방이나 괴롭힘은 금지입니다.\n- **안전**: 개인정보 공개나 부적절한 콘텐츠 게시는 금지입니다.\n- **신고**: 문제가 발생하면 즉시 <#채널ID>를 통해 관리자에게 신고해주세요.\n\n자세한 내용은 <#채널ID>에서 확인할 수 있습니다.",
        "color": 0x5865F2,
        "footer": {
            "text": "3/7 단계"
        }
    },
    "onboarding_guide_channels": {
        "title": "④ 주요 채널 소개",
        "description":
        "서버에는 다양한 목적의 채널이 있습니다.\n\n- <#채널ID>: 메인 잡담 공간입니다.\n- <#채널ID>: 음성 채널에 참여하여 대화를 즐길 수 있습니다.\n- <#채널ID>: 함께 게임할 친구를 찾을 수 있습니다.\n\n다양한 채널이 있으니, 자유롭게 둘러보세요!",
        "color": 0x5865F2,
        "footer": {
            "text": "4/7 단계"
        }
    },
    "onboarding_guide_roles": {
        "title": "⑤ 역할 받기",
        "description":
        "자신의 프로필을 꾸미기 위해 <#채널ID>에서 역할을 받아보세요.\n\n- **게임**: 플레이하는 게임이나 플랫폼을 선택할 수 있습니다.\n- **알림**: 특정 활동(음성채팅 시작 등)에 대한 알림을 받을지 선택할 수 있습니다.\n- **정보**: 자신의 성별이나 나이대 등을 다른 멤버에게 표시할 수 있습니다.",
        "color": 0x5865F2,
        "footer": {
            "text": "5/7 단계"
        }
    },
    "onboarding_guide_staff": {
        "title": "⑥ 스태프 소개",
        "description":
        "어려운 일이 있다면 아래 스태프에게 문의하세요.\n\n- **촌장/부촌장**: 서버의 최고 책임자입니다.\n- **마을사무소 직원**: 서버 운영 전반을 지원합니다.\n- **경찰관**: 규칙 위반 대응 및 분쟁 중재를 담당합니다.\n\n스태프 목록은 <#채널ID>에서 확인할 수 있습니다.",
        "color": 0x5865F2,
        "footer": {
            "text": "6/7 단계"
        }
    },
    "onboarding_guide_intro": {
        "title": "⑦ 주민 등록증 작성",
        "description":
        "마지막으로, 자기소개인 '주민 등록증'을 작성해봅시다!\n\n아래 버튼을 눌러 당신의 이름, 취미 등을 기입해주세요.\n제출 후, 마을사무소 직원이 확인하고 승인하면 정식 주민으로 인정됩니다.",
        "color": 0x5865F2,
        "footer": {
            "text": "7/7 단계"
        }
    },
    "welcome_embed": {
        "title": "🎉 {guild_name}에 오신 것을 환영합니다!",
        "description":
        "{member_mention}님, 안녕하세요!\n\n우선, 서버 안내를 읽고 자기소개를 작성해주세요.",
        "color": 0x3498DB
    },
    "farewell_embed": {
        "title": "👋 다음에 또 만나요",
        "description": "**{member_name}**님이 마을을 떠났습니다.",
        "color": 0x99AAB5
    },
    "panel_roles": {
        "title": "📖 역할 부여",
        "description": "아래 메뉴에서 카테고리를 선택하고, 자신에게 필요한 역할을 받아가세요.",
        "color": 0x5865F2
    },
    "panel_onboarding": {
        "title": "📝 마을사무소・안내소",
        "description": "처음 오신 분은 먼저 '안내 읽기' 버튼을 눌러 서버 이용 방법을 확인해주세요.",
        "color": 0x5865F2
    },
    "embed_onboarding_approval": {
        "title": "📝 새로운 주민 등록 신청",
        "description": "{member_mention}님이 주민 등록증을 제출했습니다.",
        "color": 0xE67E22
    },
    "panel_nicknames": {
        "title": "✒️ 이름 변경",
        "description": "마을에서 사용할 이름을 변경하고 싶다면, 아래 버튼을 통해 신청해주세요.",
        "color": 0x5865F2
    },
    "embed_main_chat_welcome": {
        "description": "🎉 {member_mention}님이 새로운 주민이 되었습니다! 앞으로 잘 부탁드립니다!",
        "color": 0x2ECC71
    },
    "panel_warning": {
        "title": "🚨 벌점 관리 패널",
        "description":
        "서버 규칙을 위반한 유저에게 아래 버튼을 통해 벌점을 부여할 수 있습니다.\n\n**이 기능은 `경찰관`만 사용할 수 있습니다.**",
        "color": 15548997
    },
    "log_warning": {
        "title": "🚨 벌점 발급 알림",
        "color": 15548997
    },
    "dm_onboarding_approved": {
        "title": "✅ 주민 등록 완료 알림",
        "description": "'{guild_name}' 서버의 주민 등록이 승인되었습니다.\n앞으로 잘 부탁드립니다!",
        "color": 3066993
    },
    "dm_onboarding_rejected": {
        "title": "❌ 주민 등록 거절 알림",
        "description": "죄송합니다. '{guild_name}' 서버의 주민 등록이 거절되었습니다.",
        "color": 15548997
    },
    "panel_anonymous_board": {
        "title": "🤫 익명의 소리",
        "description":
        "누구에게도 알려지지 않은 당신의 생각이나 마음을 공유해보세요.\n아래 버튼을 눌러 하루에 한 번 메시지를 작성 할 수 있습니다.\n\n**※모든 메시지는 서버 관리자가 기록 및 확인하고 있으며, 문제 발생 시 작성자를 특정하여 조치합니다.**",
        "color": 4342323
    },
    "anonymous_message": {
        "title": "익명의 메시지가 도착했습니다",
        "color": 16777215
    },
    "panel_custom_embed": {
        "title": "📢 커스텀 메시지 전송 패널",
        "description":
        "아래 버튼을 눌러 지정한 채널에 봇이 임베드 메시지를 전송합니다.\n\n**이 기능은 특정 역할을 가진 스태프만 사용할 수 있습니다.**",
        "color": 0x34495E
    },
    "log_job_advancement": {
        "title":
        "🎉 새로운 전직자!",
        "description":
        "{user_mention}님이 드디어 새로운 길을 선택했습니다.",
        "color":
        0xFFD700,
        "fields": [{
            "name": "직업",
            "value": "```\n{job_name}\n```",
            "inline": True
        }, {
            "name": "선택한 능력",
            "value": "```\n{ability_name}\n```",
            "inline": True
        }],
        "footer": {
            "text": "앞으로의 활약을 기대합니다!"
        }
    },
    "panel_commerce": {
        "title":
        "🏪 구매함 & 판매함",
        "description":
        "> 아이템을 사거나, 잡은 물고기 등을 팔 수 있습니다.",
        "color":
        0x5865F2,
        "fields": [{
            "name": "📢 오늘의 주요 시세 변동",
            "value": "{market_updates}",
            "inline": False
        }]
    },
    "panel_fishing_river": {
        "title": "🏞️ 강의 낚시터",
        "description": "> 강가에서 여유롭게 낚시를 즐겨보세요.\n> 아래 버튼을 눌러 낚시를 시작합니다.",
        "color": 0x5865F2
    },
    "panel_fishing_sea": {
        "title": "🌊 바다의 낚시터",
        "description": "> 넓은 바다에서 월척의 꿈을 쫓아보세요!\n> 아래 버튼을 눌러 낚시를 시작합니다.",
        "color": 0x3498DB
    },
    "panel_atm": {
        "title": "🏧 ATM",
        "description": "> 아래 버튼으로 다른 주민에게 코인을 보낼 수 있습니다.",
        "color": 0x2ECC71
    },
    "panel_profile": {
        "title": "📦 소지품",
        "description": "> 자신의 소지금, 아이템, 장비 등을 확인할 수 있습니다.",
        "color": 0x5865F2
    },
    "panel_dice_game": {
        "title": "🎲 주사위 게임",
        "description":
        "> 운을 시험해보시겠어요?\n> 아래 버튼으로 게임을 시작하고, 10코인 단위로 베팅할 수 있습니다.",
        "color": 0xE91E63
    },
    "log_dice_game_win": {
        "title":
        "🎉 **주사위 게임 승리!** 🎉",
        "description":
        "**{user_mention}** 님이 예측에 성공했습니다!\n> ✨ **`+{reward_amount:,}`** {currency_icon} 를 획득했습니다!",
        "color":
        0x2ECC71,
        "fields": [{
            "name": "베팅액",
            "value": "`{bet_amount:,}` {currency_icon}",
            "inline": True
        }, {
            "name": "선택한 숫자 / 결과",
            "value": "`{chosen_number}` / `🎲 {dice_result}`",
            "inline": True
        }]
    },
    "log_dice_game_lose": {
        "title":
        "💧 **주사위 게임 패배** 💧",
        "description":
        "**{user_mention}** 님은 예측에 실패하여 **`{bet_amount:,}`** {currency_icon} 를 잃었습니다.",
        "color":
        0xE74C3C,
        "fields": [{
            "name": "베팅액",
            "value": "`{bet_amount:,}` {currency_icon}",
            "inline": True
        }, {
            "name": "선택한 숫자 / 결과",
            "value": "`{chosen_number}` / `🎲 {dice_result}`",
            "inline": True
        }]
    },
    "panel_slot_machine": {
        "title": "🎰 슬롯머신",
        "description":
        "> 오늘의 운세를 시험해보세요!\n> 아래 버튼으로 게임을 시작하고, 100코인 단위로 베팅할 수 있습니다.",
        "color": 0xFF9800
    },
    "log_slot_machine_win": {
        "title":
        "🎉 **슬롯머신 잭팟!** 🎉",
        "description":
        "**{user_mention}** 님이 멋지게 그림을 맞췄습니다!\n> 💰 **`+{payout_amount:,}`** {currency_icon} 를 획득했습니다!",
        "color":
        0x4CAF50,
        "fields": [{
            "name": "베팅액",
            "value": "`{bet_amount:,}` {currency_icon}",
            "inline": True
        }, {
            "name": "결과 / 족보",
            "value": "**{result_text}**\n`{payout_name}` (`x{payout_rate}`)",
            "inline": True
        }]
    },
    "log_slot_machine_lose": {
        "title":
        "💧 **슬롯머신** 💧",
        "description":
        "**{user_mention}** 님은 **`{bet_amount:,}`** {currency_icon} 를 잃었습니다.\n> 다음 행운을 빌어요!",
        "color":
        0xF44336,
        "fields": [{
            "name": "베팅액",
            "value": "`{bet_amount:,}` {currency_icon}",
            "inline": True
        }, {
            "name": "결과",
            "value": "**{result_text}**",
            "inline": True
        }]
    },
    "panel_rps_game": {
        "title": "✊✌️✋ 가위바위보 방",
        "description":
        "> 다른 주민과 가위바위보 승부!\n> 아래 버튼을 눌러 방을 만들고, 참가자와 승부할 수 있습니다.",
        "color": 0x9B59B6
    },
    "log_rps_game_end": {
        "title":
        "🏆 **가위바위보 승부 종료!** 🏆",
        "description":
        "**{winner_mention}** 님이 최종 승자가 되었습니다!",
        "color":
        0xFFD700,
        "fields": [{
            "name": "💰 총상금",
            "value": "> **`{total_pot:,}`** {currency_icon}",
            "inline": False
        }, {
            "name": "베팅액 (1인당)",
            "value": "`{bet_amount:,}` {currency_icon}",
            "inline": True
        }, {
            "name": "👥 참가자",
            "value": "{participants_list}",
            "inline": False
        }]
    },
    "panel_tasks": {
        "title": "✅ 오늘의 할 일",
        "description": "> 아래 버튼을 눌러 매일 출석 보상을 받거나 퀘스트를 확인할 수 있습니다!",
        "color": 0x4CAF50
    },
    "log_daily_check": {
        "title": "✅ 출석 체크 완료",
        "description":
        "{user_mention}님이 출석하고 **`{reward}`**{currency_icon}을 받았습니다.",
        "color": 0x8BC34A
    },
    "panel_farm_creation": {
        "title": "🌾 나만의 농장 만들기!",
        "description":
        "> 아래 버튼을 눌러 당신만의 농장(개인 스레드)을 만듭니다.\n> 자신만의 공간에서 작물을 키워보세요!",
        "color": 0x8BC34A
    },
    "farm_thread_welcome": {
        "title": "{user_name}님의 농장",
        "description":
        "환영합니다! 이곳은 당신만의 농장입니다.\n\n**시작하는 법:**\n1. 먼저 상점에서 '나무 괭이'와 '씨앗'을 구매합니다.\n2. 아래 버튼으로 밭을 갈고 씨앗을 심어보세요!",
        "color": 0x4CAF50
    },
    "log_coin_gain": {
        "title":
        "🪙 코인 획득 알림",
        "description":
        "{user_mention}님이 활동 보상으로 코인을 획득했습니다.",
        "color":
        0x2ECC71,
        "fields": [{
            "name": "획득자",
            "value": "{user_mention}",
            "inline": True
        }, {
            "name": "획득 코인",
            "value": "+{amount}{currency_icon}",
            "inline": True
        }],
        "footer": {
            "text": "축하합니다!"
        }
    },
    "log_coin_transfer": {
        "title": "💸 송금 완료 알림",
        "description":
        "**보낸 사람:** {sender_mention}\n**받은 사람:** {recipient_mention}\n\n**금액:** `{amount}`{currency_icon}",
        "color": 0x3498DB
    },
    "log_coin_admin": {
        "description":
        "⚙️ {admin_mention}님이 {target_mention}님의 코인을 `{amount}`{currency_icon} 만큼 **{action}**했습니다.",
        "color": 0x3498DB
    },
    "embed_weather_forecast": {
        "title": "{emoji} 오늘의 날씨 예보",
        "description": "오늘의 날씨는 「**{weather_name}**」입니다!\n\n> {description}",
        "color": "{color}",
        "fields": [{
            "name": "💡 오늘의 팁",
            "value": "> {tip}",
            "inline": False
        }],
        "footer": {
            "text": "날씨는 매일 자정에 바뀝니다."
        }
    },
    "log_whale_catch": {
        "title":
        "🐋 이달의 주인을 잡다! 🐋",
        "description":
        "이번 달, 단 한 번만 모습을 드러낸다는 환상의 **고래**가 **{user_mention}**님의 손에 잡혔습니다!\n\n거대한 그림자는 다음 달까지 다시 깊은 바닷속으로 모습을 감춥니다...",
        "color":
        "0x206694",
        "fields": [{
            "name": "잡힌 주인",
            "value":
            "{emoji} **{name}**\n**크기**: `{size}`cm\n**가치**: `{value}`{currency_icon}",
            "inline": False
        }],
        "footer": {
            "text": "다음 달의 도전자여, 오라!"
        }
    },
    "embed_whale_reset_announcement": {
        "title": "🐋 바다에서 온 소문...",
        "description":
        "이번 달, 바다 깊은 곳에서 거대한 무언가를 목격했다는 소문이 돌고 있다...\n아무래도 실력 좋은 낚시꾼을 기다리고 있는 것 같다.",
        "color": 0x3498DB,
        "footer": {
            "text": "이달의 주인이 바다로 돌아왔습니다."
        }
    },
    "log_item_use_warning_deduct": {
        "title": "🎫 벌점 차감권 사용 알림",
        "color": 3066993
    },  # 초록색
    "log_item_use_event_priority": {
        "title": "✨ 이벤트 우선권 사용 알림",
        "color": 16776960
    },  # 노란색
    "panel_champion_board": {
        "title":
        "🏆 종합 챔피언 보드 🏆",
        "description":
        "각 분야에서 가장 빛나는 종합 1위 주민을 소개합니다!\n아래 버튼으로 자신의 상태를 확인하거나 상세 랭킹을 볼 수 있습니다.",
        "color":
        0xFFD700,
        "fields": [{
            "name": "👑 종합 레벨",
            "value": "{level_champion}",
            "inline": False
        }, {
            "name": "🎙️ 음성 채팅",
            "value": "{voice_champion}",
            "inline": False
        }, {
            "name": "💬 채팅",
            "value": "{chat_champion}",
            "inline": False
        }, {
            "name": "🎣 낚시",
            "value": "{fishing_champion}",
            "inline": False
        }, {
            "name": "🌾 수확",
            "value": "{harvest_champion}",
            "inline": False
        }],
        "footer": {
            "text": "매주 월요일 0시에 갱신됩니다."
        }
    }
}

UI_PANEL_COMPONENTS = [
    {
        "component_key": "start_onboarding_guide",
        "panel_key": "onboarding",
        "component_type": "button",
        "label": "안내 읽기",
        "style": "success",
        "emoji": "📖",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "request_nickname_change",
        "panel_key": "nicknames",
        "component_type": "button",
        "label": "이름 변경 신청",
        "style": "primary",
        "emoji": "✒️",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "issue_warning_button",
        "panel_key": "warning",
        "component_type": "button",
        "label": "벌점 발급하기",
        "style": "danger",
        "emoji": "🚨",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "post_anonymous_message_button",
        "panel_key": "anonymous_board",
        "component_type": "button",
        "label": "익명으로 작성하기",
        "style": "secondary",
        "emoji": "✍️",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "create_custom_embed",
        "panel_key": "custom_embed",
        "component_type": "button",
        "label": "임베드 메시지 작성",
        "style": "primary",
        "emoji": "✉️",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "open_shop",
        "panel_key": "commerce",
        "component_type": "button",
        "label": "구매함 (아이템 구매)",
        "style": "success",
        "emoji": "🏪",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "open_market",
        "panel_key": "commerce",
        "component_type": "button",
        "label": "판매함 (아이템 판매)",
        "style": "danger",
        "emoji": "📦",
        "row": 0,
        "order_in_row": 1
    },
    {
        "component_key": "open_inventory",
        "panel_key": "profile",
        "component_type": "button",
        "label": "소지품 보기",
        "style": "primary",
        "emoji": "📦",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "start_fishing_river",
        "panel_key": "panel_fishing_river",
        "component_type": "button",
        "label": "강에서 낚시하기",
        "style": "primary",
        "emoji": "🏞️",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "start_fishing_sea",
        "panel_key": "panel_fishing_sea",
        "component_type": "button",
        "label": "바다에서 낚시하기",
        "style": "secondary",
        "emoji": "🌊",
        "row": 0,
        "order_in_row": 1
    },
    {
        "component_key": "start_transfer",
        "panel_key": "atm",
        "component_type": "button",
        "label": "코인 보내기",
        "style": "success",
        "emoji": "💸",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "start_dice_game",
        "panel_key": "panel_dice_game",
        "component_type": "button",
        "label": "주사위 게임 시작",
        "style": "primary",
        "emoji": "🎲",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "start_slot_machine",
        "panel_key": "panel_slot_machine",
        "component_type": "button",
        "label": "슬롯머신 플레이",
        "style": "success",
        "emoji": "🎰",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "create_rps_room",
        "panel_key": "panel_rps_game",
        "component_type": "button",
        "label": "방 만들기",
        "style": "secondary",
        "emoji": "✊",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "do_daily_check",
        "panel_key": "panel_tasks",
        "component_type": "button",
        "label": "출석 체크",
        "style": "success",
        "emoji": "✅",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "open_quests",
        "panel_key": "panel_tasks",
        "component_type": "button",
        "label": "퀘스트 확인",
        "style": "primary",
        "emoji": "📜",
        "row": 0,
        "order_in_row": 1
    },
    {
        "component_key": "create_farm",
        "panel_key": "panel_farm_creation",
        "component_type": "button",
        "label": "농장 만들기",
        "style": "success",
        "emoji": "🌱",
        "row": 0,
        "order_in_row": 0
    },
]
SETUP_COMMAND_MAP = {
    "panel_roles": {
        "type": "panel",
        "cog_name": "RolePanel",
        "key": "auto_role_channel_id",
        "friendly_name": "역할 자동부여 패널",
        "channel_type": "text"
    },
    "panel_onboarding": {
        "type": "panel",
        "cog_name": "Onboarding",
        "key": "onboarding_panel_channel_id",
        "friendly_name": "서버 안내 패널",
        "channel_type": "text"
    },
    "panel_nicknames": {
        "type": "panel",
        "cog_name": "Nicknames",
        "key": "nickname_panel_channel_id",
        "friendly_name": "닉네임 변경 패널",
        "channel_type": "text"
    },
    "panel_level_check": {
        "type": "panel",
        "cog_name": "LevelSystem",
        "key": "level_check_panel_channel_id",
        "friendly_name": "[게임] 레벨 확인 패널",
        "channel_type": "text"
    },
    "channel_job_advancement": {
        "type": "channel",
        "cog_name": "LevelSystem",
        "key": "job_advancement_channel_id",
        "friendly_name": "[채널] 전직소",
        "channel_type": "text"
    },
    "panel_anonymous_board": {
        "type": "panel",
        "cog_name": "AnonymousBoard",
        "key": "anonymous_board_channel_id",
        "friendly_name": "[패널] 익명 게시판",
        "channel_type": "text"
    },
    "panel_warning": {
        "type": "panel",
        "cog_name": "WarningSystem",
        "key": "warning_panel_channel_id",
        "friendly_name": "[패널] 벌점 관리",
        "channel_type": "text"
    },
    "panel_custom_embed": {
        "type": "panel",
        "cog_name": "CustomEmbed",
        "key": "custom_embed_panel_channel_id",
        "friendly_name": "[패널] 커스텀 임베드 전송",
        "channel_type": "text"
    },
    "panel_commerce": {
        "type": "panel",
        "cog_name": "Commerce",
        "key": "commerce_panel_channel_id",
        "friendly_name": "[게임] 상점 패널",
        "channel_type": "text"
    },
    "panel_fishing_river": {
        "type": "panel",
        "cog_name": "Fishing",
        "key": "river_fishing_panel_channel_id",
        "friendly_name": "[게임] 강 낚시터 패널",
        "channel_type": "text"
    },
    "panel_fishing_sea": {
        "type": "panel",
        "cog_name": "Fishing",
        "key": "sea_fishing_panel_channel_id",
        "friendly_name": "[게임] 바다 낚시터 패널",
        "channel_type": "text"
    },
    "panel_profile": {
        "type": "panel",
        "cog_name": "UserProfile",
        "key": "profile_panel_channel_id",
        "friendly_name": "[게임] 프로필 패널",
        "channel_type": "text"
    },
    "panel_atm": {
        "type": "panel",
        "cog_name": "Atm",
        "key": "atm_panel_channel_id",
        "friendly_name": "[게임] ATM 패널",
        "channel_type": "text"
    },
    "panel_dice_game": {
        "type": "panel",
        "cog_name": "DiceGame",
        "key": "dice_game_panel_channel_id",
        "friendly_name": "[게임] 주사위 게임 패널",
        "channel_type": "text"
    },
    "panel_slot_machine": {
        "type": "panel",
        "cog_name": "SlotMachine",
        "key": "slot_machine_panel_channel_id",
        "friendly_name": "[게임] 슬롯머신 패널",
        "channel_type": "text"
    },
    "panel_rps_game": {
        "type": "panel",
        "cog_name": "RPSGame",
        "key": "rps_game_panel_channel_id",
        "friendly_name": "[게임] 가위바위보 패널",
        "channel_type": "text"
    },
    "panel_tasks": {
        "type": "panel",
        "cog_name": "Quests",
        "key": "tasks_panel_channel_id",
        "friendly_name": "[게임] 일일 게시판 패널",
        "channel_type": "text"
    },
    "panel_farm_creation": {
        "type": "panel",
        "cog_name": "Farm",
        "key": "farm_creation_panel_channel_id",
        "friendly_name": "[게임] 농장 생성 패널",
        "channel_type": "text"
    },
    "panel_inquiry": {
        "type": "panel",
        "cog_name": "TicketSystem",
        "key": "inquiry_panel_channel_id",
        "friendly_name": "[티켓] 문의/건의 패널",
        "channel_type": "text"
    },
    "panel_report": {
        "type": "panel",
        "cog_name": "TicketSystem",
        "key": "report_panel_channel_id",
        "friendly_name": "[티켓] 유저 신고 패널",
        "channel_type": "text"
    },
    "channel_new_welcome": {
        "type": "channel",
        "cog_name": "MemberEvents",
        "key": "new_welcome_channel_id",
        "friendly_name": "신규 멤버 환영 채널",
        "channel_type": "text"
    },
    "channel_farewell": {
        "type": "channel",
        "cog_name": "MemberEvents",
        "key": "farewell_channel_id",
        "friendly_name": "멤버 퇴장 안내 채널",
        "channel_type": "text"
    },
    "channel_main_chat": {
        "type": "channel",
        "cog_name": "Onboarding",
        "key": "main_chat_channel_id",
        "friendly_name": "메인 채팅 채널 (자기소개 승인 후 안내)",
        "channel_type": "text"
    },
    "channel_onboarding_approval": {
        "type": "channel",
        "cog_name": "Onboarding",
        "key": "onboarding_approval_channel_id",
        "friendly_name": "자기소개 승인/거절 채널",
        "channel_type": "text"
    },
    "channel_nickname_approval": {
        "type": "channel",
        "cog_name": "Nicknames",
        "key": "nickname_approval_channel_id",
        "friendly_name": "닉네임 변경 승인 채널",
        "channel_type": "text"
    },
    "channel_vc_creator_3p": {
        "type": "channel",
        "cog_name": "VoiceMaster",
        "key": "vc_creator_channel_id_3p",
        "friendly_name": "음성 채널 자동 생성 (게임)",
        "channel_type": "voice"
    },
    "channel_vc_creator_4p": {
        "type": "channel",
        "cog_name": "VoiceMaster",
        "key": "vc_creator_channel_id_4p",
        "friendly_name": "음성 채널 자동 생성 (광장)",
        "channel_type": "voice"
    },
    "channel_vc_creator_newbie": {
        "type": "channel",
        "cog_name": "VoiceMaster",
        "key": "vc_creator_channel_id_벤치",
        "friendly_name": "[음성 채널] 뉴비 전용 생성기",
        "channel_type": "voice"
    },
    "channel_vc_creator_vip": {
        "type": "channel",
        "cog_name": "VoiceMaster",
        "key": "vc_creator_channel_id_마이룸",
        "friendly_name": "[음성 채널] VIP 전용 생성기",
        "channel_type": "voice"
    },
    "log_nickname": {
        "type": "channel",
        "cog_name": "Nicknames",
        "key": "nickname_log_channel_id",
        "friendly_name": "[로그] 닉네임 변경 기록",
        "channel_type": "text"
    },
    "log_intro_approval": {
        "type": "channel",
        "cog_name": "Onboarding",
        "key": "introduction_channel_id",
        "friendly_name": "[로그] 자기소개 승인 기록",
        "channel_type": "text"
    },
    "log_intro_rejection": {
        "type": "channel",
        "cog_name": "Onboarding",
        "key": "introduction_rejection_log_channel_id",
        "friendly_name": "[로그] 자기소개 거절 기록",
        "channel_type": "text"
    },
    "log_item_warning_deduct": {
        "type": "channel",
        "cog_name": "ItemSystem",
        "key": "log_item_warning_deduct",
        "friendly_name": "[로그] 벌점 차감권 사용 내역",
        "channel_type": "text"
    },
    "log_item_event_priority": {
        "type": "channel",
        "cog_name": "ItemSystem",
        "key": "log_item_event_priority",
        "friendly_name": "[로그] 이벤트 우선권 사용 내역",
        "channel_type": "text"
    },
    "log_message": {
        "type": "channel",
        "cog_name": "MessageLogger",
        "key": "log_channel_message",
        "friendly_name": "[로그] 메시지 (수정/삭제)",
        "channel_type": "text"
    },
    "log_voice": {
        "type": "channel",
        "cog_name": "VoiceLogger",
        "key": "log_channel_voice",
        "friendly_name": "[로그] 음성 채널 (참여/이동/퇴장)",
        "channel_type": "text"
    },
    "log_member": {
        "type": "channel",
        "cog_name": "MemberLogger",
        "key": "log_channel_member",
        "friendly_name": "[로그] 멤버 활동 (역할 부여/닉네임)",
        "channel_type": "text"
    },
    "log_channel": {
        "type": "channel",
        "cog_name": "ChannelLogger",
        "key": "log_channel_channel",
        "friendly_name": "[로그] 채널 관리 (생성/삭제/변경)",
        "channel_type": "text"
    },
    "log_server": {
        "type": "channel",
        "cog_name": "ServerLogger",
        "key": "log_channel_server",
        "friendly_name": "[로그] 서버 및 역할 관리",
        "channel_type": "text"
    },
    "log_warning": {
        "type": "channel",
        "cog_name": "WarningSystem",
        "key": "warning_log_channel_id",
        "friendly_name": "[로그] 벌점 발급 기록",
        "channel_type": "text"
    },
    "log_daily_check": {
        "type": "channel",
        "cog_name": "Quests",
        "key": "log_daily_check_channel_id",
        "friendly_name": "[로그] 출석체크 기록",
        "channel_type": "text"
    },
    "log_market": {
        "type": "channel",
        "cog_name": "EconomyCore",
        "key": "market_log_channel_id",
        "friendly_name": "[로그] 시장 시세 변동",
        "channel_type": "text"
    },
    "log_coin": {
        "type": "channel",
        "cog_name": "EconomyCore",
        "key": "coin_log_channel_id",
        "friendly_name": "[로그] 코인 활동",
        "channel_type": "text"
    },
    "log_job_advancement": {
        "type": "channel",
        "cog_name": "LevelSystem",
        "key": "job_log_channel_id",
        "friendly_name": "[로그] 전직 기록",
        "channel_type": "text"
    },
    "log_fishing": {
        "type": "channel",
        "cog_name": "Fishing",
        "key": "fishing_log_channel_id",
        "friendly_name": "[로그] 낚시 성공 기록",
        "channel_type": "text"
    },
    "channel_bump_reminder": {
        "type": "channel",
        "cog_name": "Reminder",
        "key": "bump_reminder_channel_id",
        "friendly_name": "[알림] Disboard BUMP 채널",
        "channel_type": "text"
    },
    "channel_dissoku_reminder": {
        "type": "channel",
        "cog_name": "Reminder",
        "key": "dissoku_reminder_channel_id",
        "friendly_name": "[알림] Dissoku UP 채널",
        "channel_type": "text"
    },
    "channel_weather": {
        "type": "channel",
        "cog_name": "WorldSystem",
        "key": "weather_channel_id",
        "friendly_name": "[알림] 날씨 예보 채널",
        "channel_type": "text"
    },
}
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
                "label": "🔔 알림",
                "description": "받고 싶은 알림을 선택하세요.",
                "emoji": "🔔"
            },
            {
                "id": "games",
                "label": "🎮 게임",
                "description": "플레이하는 게임을 선택하세요.",
                "emoji": "🎮"
            },
        ],
        "roles": {
            "notifications": [
                {
                    "role_id_key": "role_notify_voice",
                    "label": "통화 모집"
                },
                {
                    "role_id_key": "role_notify_friends",
                    "label": "친구 모집"
                },
                {
                    "role_id_key": "role_notify_disboard",
                    "label": "Disboard"
                },
                {
                    "role_id_key": "role_notify_up",
                    "label": "Up"
                },
            ],
            "games": [
                {
                    "role_id_key": "role_game_minecraft",
                    "label": "마인크래프트"
                },
                {
                    "role_id_key": "role_game_valorant",
                    "label": "발로란트"
                },
                {
                    "role_id_key": "role_game_overwatch",
                    "label": "오버워치"
                },
                {
                    "role_id_key": "role_game_lol",
                    "label": "리그 오브 레전드"
                },
                {
                    "role_id_key": "role_game_mahjong",
                    "label": "마작"
                },
                {
                    "role_id_key": "role_game_amongus",
                    "label": "어몽어스"
                },
                {
                    "role_id_key": "role_game_mh",
                    "label": "몬스터 헌터"
                },
                {
                    "role_id_key": "role_game_genshin",
                    "label": "원신"
                },
                {
                    "role_id_key": "role_game_apex",
                    "label": "에이펙스 레전드"
                },
                {
                    "role_id_key": "role_game_ggd",
                    "label": "구스구스덕"
                },
                {
                    "role_id_key": "role_game_gf",
                    "label": "갈틱폰"
                },
                {
                    "role_id_key": "role_platform_steam",
                    "label": "스팀"
                },
                {
                    "role_id_key": "role_platform_PC",
                    "label": "PC"
                },
                {
                    "role_id_key": "role_platform_smartphone",
                    "label": "스마트폰"
                },
                {
                    "role_id_key": "role_platform_console",
                    "label": "콘솔"
                },
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
    {
        "count": 1,
        "role_key": "role_warning_level_1"
    },
    {
        "count": 2,
        "role_key": "role_warning_level_2"
    },
    {
        "count": 3,
        "role_key": "role_warning_level_3"
    },
    {
        "count": 4,
        "role_key": "role_warning_level_4"
    },
]
CUSTOM_EMBED_SENDER_ROLES = [
    "role_admin_total", "role_staff_village_chief", "role_staff_deputy_chief"
]
JOB_SYSTEM_CONFIG = {
    "JOB_ROLE_MAP": {
        "fisherman": "role_job_fisherman",
        "farmer": "role_job_farmer",
        "master_angler": "role_job_master_angler",
        "master_farmer": "role_job_master_farmer"
    },
    "LEVEL_TIER_ROLES": [{
        "level": 150,
        "role_key": "role_resident_elder"
    }, {
        "level": 100,
        "role_key": "role_resident_veteran"
    }, {
        "level": 50,
        "role_key": "role_resident_regular"
    }, {
        "level": 1,
        "role_key": "role_resident_rookie"
    }]
}
AGE_ROLE_MAPPING = [{
    "key": "role_info_age_00s",
    "range": [2000, 2100],
    "name": "00년생"
}, {
    "key": "role_info_age_90s",
    "range": [1990, 2000],
    "name": "90년생"
}, {
    "key": "role_info_age_80s",
    "range": [1980, 1990],
    "name": "80년생"
}, {
    "key": "role_info_age_70s",
    "range": [1970, 1980],
    "name": "70년생"
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
ADMIN_ACTION_MAP = {
    "status_show": "[현황] 설정 대시보드 표시",
    "server_id_set": "[중요] 서버 ID 설정",
    "panels_regenerate_all": "[패널] 모든 관리 패널 재설치",
    "template_edit": "[템플릿] 임베드 템플릿 편집",
    "request_regenerate_all_game_panels": "[게임] 모든 게임 패널 재설치 요청",
    "roles_sync": "[역할] 모든 역할 DB와 동기화",
    "strings_sync": "[UI] 모든 UI 텍스트 DB와 동기화",
    "game_data_reload": "[게임] 게임 데이터 새로고침",
    "stats_set": "[통계] 통계 채널 설정/제거",
    "stats_refresh": "[통계] 모든 통계 채널 새로고침",
    "stats_list": "[통계] 설정된 통계 채널 목록",
    "coin_give": "[코인] 유저에게 코인 지급",
    "coin_take": "[코인] 유저의 코인 차감",
    "xp_give": "[XP] 유저에게 XP 지급",
    "level_set": "[레벨] 유저 레벨 설정",
}

PROFILE_RANK_ROLES = [{
    "role_key": "role_staff_village_chief",
    "priority": 100
}, {
    "role_key": "role_staff_deputy_chief",
    "priority": 95
}, {
    "role_key": "role_approval",
    "priority": 90
}, {
    "role_key": "role_premium_booster",
    "priority": 80
}, {
    "role_key": "role_resident_elder",
    "priority": 70
}, {
    "role_key": "role_resident_veteran",
    "priority": 60
}, {
    "role_key": "role_resident_regular",
    "priority": 50
}, {
    "role_key": "role_resident_rookie",
    "priority": 10
}]

UI_STRINGS = {
    "commerce": {
        "item_view_desc":
        "현재 소지금: `{balance}`{currency_icon}\n구매하고 싶은 상품을 선택하세요.",
        "wip_category": "이 카테고리의 상품은 현재 준비 중입니다."
    },
    "profile_view": {
        "base_title":
        "{user_name}의 소지품",
        "tabs": [{
            "key": "info",
            "title_suffix": " - 정보",
            "label": "정보",
            "emoji": "ℹ️"
        }, {
            "key": "item",
            "title_suffix": " - 아이템",
            "label": "아이템",
            "emoji": "📦"
        }, {
            "key": "gear",
            "title_suffix": " - 장비",
            "label": "장비",
            "emoji": "⚒️"
        }, {
            "key": "fish",
            "title_suffix": " - 어항",
            "label": "어항",
            "emoji": "🐠"
        }, {
            "key": "seed",
            "title_suffix": " - 씨앗",
            "label": "씨앗",
            "emoji": "🌱"
        }, {
            "key": "crop",
            "title_suffix": " - 작물",
            "label": "작물",
            "emoji": "🌾"
        }],
        "info_tab": {
            "description": "아래 탭을 선택하여 상세 정보를 확인하세요.",
            "field_balance": "소지금",
            "field_rank": "등급",
            "default_rank_name": "새내기 주민"
        },
        "item_tab": {
            "no_items": "보유 중인 아이템이 없습니다.",
            "use_item_button_label": "아이템 사용"
        },
        "item_usage_view": {
            "embed_title": "✨ 아이템 사용",
            "embed_description": "인벤토리에서 사용할 아이템을 선택해주세요.",
            "select_placeholder": "사용할 아이템을 선택하세요...",
            "back_button": "뒤로",
            "no_usable_items": "사용할 수 있는 아이템이 없습니다.",
            "reason_modal_title": "{item_name} 사용",
            "reason_modal_label": "사용 사유 (예: 이벤트 이름)",
            "reason_modal_placeholder": "어떤 이벤트에 사용하시나요?",
            "request_success": "✅ '{item_name}' 사용을 요청했습니다. 잠시 후 처리됩니다.",
            "consume_success": "✅ '{item_name}'을(를) 사용했습니다.",
            "farm_expand_success":
            "✅ 농장이 1칸 확장되었습니다! (현재 크기: {plot_count}/25)",
            "farm_expand_fail_max": "❌ 농장이 이미 최대 크기(25칸)입니다.",
            "farm_expand_fail_no_farm": "❌ 농장을 먼저 만들어주세요.",
            "error_generic": "❌ 아이템을 사용하는 중 오류가 발생했습니다.",
            "error_invalid_item": "❌ 잘못된 아이템 정보입니다.",
            "error_role_not_found": "❌ 아이템에 해당하는 역할을 찾을 수 없습니다."
        },
        "gear_tab": {
            "no_owned_gear": "보유 중인 장비가 없습니다."
        },
        "fish_tab": {
            "no_fish": "어항에 물고기가 없습니다.",
            "pagination_footer": "페이지 {current_page} / {total_pages}"
        },
        "seed_tab": {
            "no_items": "보유 중인 씨앗이 없습니다."
        },
        "crop_tab": {
            "no_items": "보유 중인 작물이 없습니다."
        },
        "wip_tab": {
            "description": "이 기능은 현재 준비 중입니다."
        },
        "pagination_buttons": {
            "prev": "◀",
            "next": "▶"
        },
        "gear_select_view": {
            "embed_title": "{category_name} 변경",
            "embed_description": "장착할 아이템을 선택하세요.",
            "placeholder": "{category_name} 선택...",
            "unequip_prefix": "✋",
            "back_button": "뒤로"
        }
    }
}
JOB_ADVANCEMENT_DATA = {
    "50": [{
        "job_key":
        "fisherman",
        "job_name":
        "낚시꾼",
        "role_key":
        "role_job_fisherman",
        "description":
        "물고기를 낚는 데 특화된 전문가입니다.",
        "abilities": [{
            "ability_key": "fish_bait_saver_1",
            "ability_name": "미끼 절약 (확률)",
            "description": "낚시할 때 일정 확률로 미끼를 소모하지 않습니다."
        }, {
            "ability_key": "fish_bite_time_down_1",
            "ability_name": "입질 시간 단축",
            "description": "물고기가 미끼를 무는 데 걸리는 시간이 전체적으로 2초 단축됩니다."
        }]
    }, {
        "job_key":
        "farmer",
        "job_name":
        "농부",
        "role_key":
        "role_job_farmer",
        "description":
        "작물을 키우고 수확하는 데 특화된 전문가입니다.",
        "abilities": [{
            "ability_key": "farm_seed_saver_1",
            "ability_name": "씨앗 절약 (확률)",
            "description": "씨앗을 심을 때 일정 확률로 씨앗을 소모하지 않습니다."
        }, {
            "ability_key": "farm_water_retention_1",
            "ability_name": "수분 유지력 UP",
            "description": "작물이 수분을 더 오래 머금어 물을 주는 간격이 길어집니다."
        }]
    }],
    "100": [{
        "job_key":
        "master_angler",
        "job_name":
        "강태공",
        "role_key":
        "role_job_master_angler",
        "description":
        "낚시의 길을 통달하여 전설의 물고기를 쫓는 자. 낚시꾼의 상위 직업입니다.",
        "prerequisite_job":
        "fisherman",
        "abilities": [{
            "ability_key": "fish_rare_up_2",
            "ability_name": "희귀어 확률 UP (대)",
            "description": "희귀한 물고기를 낚을 확률이 상승합니다."
        }, {
            "ability_key": "fish_size_up_2",
            "ability_name": "물고기 크기 UP (대)",
            "description": "낚는 물고기의 평균 크기가 커집니다."
        }]
    }, {
        "job_key":
        "master_farmer",
        "job_name":
        "대농",
        "role_key":
        "role_job_master_farmer",
        "description":
        "농업의 정수를 깨달아 대지로부터 최대의 은혜를 얻는 자. 농부의 상위 직업입니다.",
        "prerequisite_job":
        "farmer",
        "abilities": [{
            "ability_key": "farm_yield_up_2",
            "ability_name": "수확량 UP (대)",
            "description": "작물을 수확할 때의 수확량이 대폭 증가합니다."
        }, {
            "ability_key": "farm_growth_speed_up_2",
            "ability_name": "성장 속도 UP (대)",
            "description": "작물의 성장 시간이 단축됩니다."
        }]
    }]
}
