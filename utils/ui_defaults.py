# bot-management/utils/ui_defaults.py
"""
봇이 사용하는 모든 UI 요소 및 핵심 매핑 데이터의 기본값을 정의하는 파일입니다.
봇이 시작될 때 이 파일의 데이터가 Supabase 데이터베이스에 동기화됩니다.
"""

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 1. 역할 키 맵 (Role Key Map)
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
UI_ROLE_KEY_MAP = {
    # --- 최상위 관리 역할 ---
    "role_staff_village_chief": {"name": "『 🧩：대표 』", "is_prefix": False, "priority": 90},
    "role_staff_deputy_chief": {"name": "『 🌷：부 대 표 』", "is_prefix": False, "priority": 85},
    
    # ▼▼▼ [수정] 팀장 역할 그룹 추가 ▼▼▼
    "role_staff_leader_machine": {"name": "『 🍫：기 계 공 정 팀 장 』", "is_prefix": False, "priority": 71},
    "role_staff_leader_syrup": {"name": "『 🍯：시 럽 공 정 팀 장 』", "is_prefix": False, "priority": 70},
    "role_staff_leader_packaging": {"name": "『 🫙：포 장 관 리 팀 장 』", "is_prefix": False, "priority": 70},
    "role_staff_leader_cream": {"name": "『 🍦：크 림 조 립 팀 장 』", "is_prefix": False, "priority": 70},
    "role_staff_leader_dough": {"name": "『 🍥：반 죽 제 조 팀 장 』", "is_prefix": False, "priority": 70},
    # ▲▲▲ [수정 완료] ▲▲▲

    # --- 최상위 접두사 역할 ---
    "role_admin_total": {"name": "『 ⭐：엔지니어 』", "is_prefix": True, "priority": 100, "prefix_symbol": "🌙", "prefix_format": "𐐪{symbol}𐑂", "suffix": " ⸝⁺⊹"},
    
    
    # --- 스태프 접두사 역할 ---
    "role_staff_pr": {"name": "『 🍯：시 럽 공 정 팀 』", "is_prefix": True, "priority": 61, "prefix_symbol": "🍯", "prefix_format": "𐐪{symbol}𐑂", "suffix": " ⸝⁺⊹"},
    "role_staff_police": {"name": "『 🫙：포 장 관 리 팀 』", "is_prefix": True, "priority": 61, "prefix_symbol": "🫙", "prefix_format": "𐐪{symbol}𐑂", "suffix": " ⸝⁺⊹"},
    "role_staff_festival": {"name": "『 🍦：크 림 조 립 팀 』", "is_prefix": True, "priority": 61, "prefix_symbol": "🍦", "prefix_format": "𐐪{symbol}𐑂", "suffix": " ⸝⁺⊹"},
    "role_staff_newbie_helper": {"name": "『 🍥：반 죽 제 조 팀 』", "is_prefix": True, "priority": 61, "prefix_symbol": "🍥", "prefix_format": "𐐪{symbol}𐑂", "suffix": " ⸝⁺⊹"},

    "role_approval": {"name": "『🧺：바구니 』", "is_prefix": False, "priority": 60},

    # --- 일반 접두사 역할 (우선순위 순) ---
    "role_premium_booster": {"name": "『 🍩：도넛』", "is_prefix": True, "priority": 55, "prefix_symbol": "🍩", "prefix_format": "〚{symbol}〛", "suffix": " ⸝⁺⊹"},
    "role_resident_elder": {"name": "장로", "is_prefix": True, "priority": 50, "prefix_symbol": "📜", "prefix_format": "「{symbol}」", "suffix": " ⸝⁺⊹"},
    
    # --- 직업 접두사 역할 ---
    "role_job_master_chef": {"name": "마스터 셰프", "is_prefix": True, "priority": 16, "prefix_symbol": "‍🍳", "prefix_format": "「{symbol}」", "suffix": " ⸝⁺⊹"},
    "role_job_master_angler": {"name": "강태공", "is_prefix": True, "priority": 16, "prefix_symbol": "🏆", "prefix_format": "「{symbol}」", "suffix": " ⸝⁺⊹"},
    "role_job_master_farmer": {"name": "대농", "is_prefix": True, "priority": 16, "prefix_symbol": "👑", "prefix_format": "「{symbol}」", "suffix": " ⸝⁺⊹"},
    "role_job_expert_miner": {"name": "전문 광부", "is_prefix": True, "priority": 16, "prefix_symbol": "💎", "prefix_format": "「{symbol}」", "suffix": " ⸝⁺⊹"},
    "role_job_chef": {"name": "요리사", "is_prefix": True, "priority": 15, "prefix_symbol": "🍳", "prefix_format": "「{symbol}」", "suffix": " ⸝⁺⊹"},
    "role_job_fisherman": {"name": "낚시꾼", "is_prefix": True, "priority": 15, "prefix_symbol": "🎣", "prefix_format": "「{symbol}」", "suffix": " ⸝⁺⊹"},
    "role_job_farmer": {"name": "농부", "is_prefix": True, "priority": 15, "prefix_symbol": "🌾", "prefix_format": "「{symbol}」", "suffix": " ⸝⁺⊹"},
    "role_job_miner": {"name": "광부", "is_prefix": True, "priority": 15, "prefix_symbol": "⛏️", "prefix_format": "「{symbol}」", "suffix": " ⸝⁺⊹"},
    
    # --- 등급 접두사 역할 (우선순위 순) ---
    "role_resident": {"name": "주민", "is_prefix": True, "priority": 10, "prefix_symbol": "💌", "prefix_format": "「{symbol}」", "suffix": " ⸝⁺⊹"},
    "role_resident_veteran": {"name": "베테랑", "is_prefix": True, "priority": 4, "prefix_symbol": "veterαn", "prefix_format": "「{symbol}」", "suffix": " ⸝⁺⊹"},
    "role_resident_regular": {"name": "『 🍪：쿠키 』", "is_prefix": True, "priority": 3, "prefix_symbol": "🍪", "prefix_format": "『{symbol}』", "suffix": " ⸝⁺⊹"},
    "role_resident_rookie": {"name": "『 🧈：버터 』", "is_prefix": True, "priority": 2, "prefix_symbol": "🧈", "prefix_format": "「{symbol}」", "suffix": " ⸝⁺⊹"},
    "role_guest": {"name": "『 🌾：밀가루 』", "is_prefix": True, "priority": 1, "prefix_symbol": "🌾", "prefix_format": "『{symbol}』", "suffix": " ⸝⁺⊹"},

    # ▼▼▼ [추가] 부스트 보상 역할 10개 ▼▼▼
    "role_boost_ticket_1": {"name": "♡。💌：역할선택권 1 ໒꒱", "is_prefix": False, "priority": 0},
    "role_boost_ticket_2": {"name": "♡。💌：역할선택권 2 ໒꒱", "is_prefix": False, "priority": 0},
    "role_boost_ticket_3": {"name": "♡。💌：역할선택권 3 ໒꒱", "is_prefix": False, "priority": 0},
    "role_boost_ticket_4": {"name": "♡。💌：역할선택권 4 ໒꒱", "is_prefix": False, "priority": 0},
    "role_boost_ticket_5": {"name": "♡。💌：역할선택권 5 ໒꒱", "is_prefix": False, "priority": 0},
    "role_boost_ticket_6": {"name": "♡。💌：역할선택권 6 ໒꒱", "is_prefix": False, "priority": 0},
    "role_boost_ticket_7": {"name": "♡。💌：역할선택권 7 ໒꒱", "is_prefix": False, "priority": 0},
    "role_boost_ticket_8": {"name": "♡。💌：역할선택권 8 ໒꒱", "is_prefix": False, "priority": 0},
    "role_boost_ticket_9": {"name": "♡。💌：역할선택권 9 ໒꒱", "is_prefix": False, "priority": 0},
    "role_boost_ticket_10": {"name": "♡。💌：역할선택권 10 ໒꒱", "is_prefix": False, "priority": 0},
    # ▲▲▲ [추가 완료] ▲▲▲
    
    # --- 그 외 접두사가 아닌 역할들 (우선순위 0) ---
    "role_info_male": {"name": "『 👦：남자 』", "is_prefix": False, "priority": 0},
    "role_info_female": {"name": "『 👧：여자 』", "is_prefix": False, "priority": 0},
    "role_info_age_private": {"name": "비공개", "is_prefix": False, "priority": 0},
    "role_info_age_70s": {"name": "70", "is_prefix": False, "priority": 0},
    "role_info_age_80s": {"name": "『 🥪：𝟏𝟗𝟖𝟎 』", "is_prefix": False, "priority": 0},
    "role_info_age_90s": {"name": "『 🥨：𝟏𝟗𝟗𝟎 』", "is_prefix": False, "priority": 0},
    "role_info_age_00s": {"name": "『 🥐：𝟐𝟎𝟎𝟎 』", "is_prefix": False, "priority": 0},
    "role_personal_room_key": {"name": "마이룸 열쇠", "is_prefix": False, "priority": 0},
    "role_notify_dding": {"name": "⊹ ₊ 띵 동 .ᐟ ⊹", "is_prefix": False, "priority": 0},
    "role_notify_welcome": {"name": "˗ˏˋ    환 영 합 니 다 .ᐟ  ˊˎ˗", "is_prefix": False, "priority": 0},
    "role_notify_disboard": {"name": "『 🍨 : 공장 홍보대사 』", "is_prefix": False, "priority": 0},
    "role_notify_ask": {"name": "『 🍳：에 스 크 알 림 』", "is_prefix": False, "priority": 0},
    "role_notify_up": {"name": "『 🍭 : 공장 업 』", "is_prefix": False, "priority": 0},
    "role_game_tft": {"name": "ʚ ♟️：롤토체스 ɞ", "is_prefix": False, "priority": 0},
    "role_game_lol": {"name": "ʚ ⚔️：리그오브레전드 ɞ", "is_prefix": False, "priority": 0},
    "role_game_valorant": {"name": "ʚ 🔫：발로란트 ɞ", "is_prefix": False, "priority": 0},
    "role_game_overwatch": {"name": "ʚ ⏰：오버워치 ɞ", "is_prefix": False, "priority": 0},
    "role_game_lostark": {"name": "ʚ ⏰：로스트아크 ɞ", "is_prefix": False, "priority": 0},
    "role_game_minecraft": {"name": "ʚ ⛏️：마인크래프트 ɞ", "is_prefix": False, "priority": 0},
    "role_game_zombi": {"name": "ʚ 🧟‍♂️：좀비고등학교 ɞ", "is_prefix": False, "priority": 0},
    "role_platform_steam": {"name": "ʚ 🎮：스팀 게임 ɞ", "is_prefix": False, "priority": 0},
    "role_platform_smartphone": {"name": "ʚ 🎮：모바일 게임 ɞ", "is_prefix": False, "priority": 0},
    "role_platform_switch": {"name": "ʚ 🎮：기타 게임 ɞ", "is_prefix": False, "priority": 0},
    "role_warning_level_1": {"name": "『 🚫：경고 1 』", "is_prefix": False, "priority": 0},
    "role_warning_level_2": {"name": "『 🚫：경고 2 』", "is_prefix": False, "priority": 0},
    "role_warning_level_3": {"name": "『 🚫：경고 3 』", "is_prefix": False, "priority": 0},
    "role_warning_level_4": {"name": "벌점 4회", "is_prefix": False, "priority": 0},
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
    },
    "item_mine_pass": {
        "name": "광산 입장권",
        "type": "mine_entry",
        "description": "광산에 10분 동안 입장할 수 있는 티켓입니다.",
        "log_channel_key": "log_item_mine_pass",
        "log_embed_key": "log_item_use_mine_pass"
    },
    "item_job_reset_ticket": {
        "name": "직업 초기화권",
        "type": "job_reset",
        "description": "자신의 직업을 초기화하고, 레벨에 맞는 전직을 다시 진행할 수 있습니다. (레벨은 유지됩니다)",
        "log_channel_key": "log_item_job_reset",
        "log_embed_key": "log_item_use_job_reset"
    },
    # [추가] 보물 상자를 사용 가능한 아이템으로 등록합니다.
    "item_weekly_boss_chest": {
        "name": "주간 보스 보물 상자",
        "type": "open_chest",
        "description": "주간 보스를 처치하고 얻은 전리품 상자. 무엇이 들어있을까?"
    },
    "item_monthly_boss_chest": {
        "name": "월간 보스 보물 상자",
        "type": "open_chest",
        "description": "월간 보스를 처치하고 얻은 희귀한 전리품 상자. 무엇이 들어있을까?"
    }
}

UI_EMBEDS = {
    "onboarding_guide_server": {
        "title": "",
        "description":
        "## 🏡✨ 𝗗𝗜𝘀𝗰𝗼𝗿𝗱 𝗩𝗶𝗹𝗹𝗮𝗴𝗲에 오신 것을 환영합니다! ✨🏡\n> ### 어서 오세요, 새로운 이웃님! 저희는 '마을'을 콘셉트로 한 특별한 커뮤니티입니다.\n> ### 이곳에서 당신은 마을의 소중한 주민이 되어, 즐겁고 아늑한 시간을 보낼 수 있습니다.\n## ✨ 마을에서 즐길 수 있는 것들 ✨\n### 1. 아늑한 마을 생활 🏡\n- 따뜻한 차 한잔과 함께 일상을 공유하거나, 소소한 이야기를 나누며 편안한 시간을 보내보세요.\n- 서로를 존중하는 따뜻하고 활기찬 분위기가 가득한 곳이랍니다.\n### 2. 다 함께 즐기는 게임 🎮\n- 좋아하는 게임을 같이 플레이하며 새로운 친구를 사귀어보는 건 어떠세요?\n- 다양한 게임 채널에서 마음껏 즐기며 잊지 못할 추억을 만들어봐요.\n### 3. 마을의 오리지널 봇 🤖\n- 마을 전용 오리지널 봇으로 더욱 다채로운 활동을 즐길 수 있어요.\n- 봇을 통해 여러 미니게임을 플레이하며 재화를 모으고, 그 재화로 특별한 아이템을 구매하는 즐거움을 꼭 경험해보세요!\n### 마을에 입주하신 것을 진심으로 환영합니다! 💖\n### 앞으로 잘 부탁드립니다.\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n아래 '다음' 버튼을 눌러 안내를 읽어주세요.",
        "color": 0x5865F2,
        "footer": {
            "text": "1/7 단계"
        }
    },
    "onboarding_guide_bots": {
        "title": "",
        "description":
        "## ✨ 마을의 두 요정 소개 ✨\n> ### 마을 주민들이 즐겁고 편리하게 생활할 수 있도록, 두 요정이 언제나 함께하고 있어요.\n## 🌙 관리 요정 『츠키』\n- 주민들의 서버 생활을 더욱 편리하게 만들어주는 든든한 요정이에요.\n## ⭐ 게임 요정 『호시』\n- 마을의 모든 즐거움을 책임지는 게임 전문가랍니다. 도박, 대전, 낚시, 농사, 채광, 요리, 펫, 전직 등 다양한 활동으로 재화를 모으고, 모은 재화로 상점에서 특별한 아이템을 구매하는 즐거움을 꼭 경험해보세요!\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n아래 '다음' 버튼을 눌러 안내를 읽어주세요.",
        "color": 0x5865F2,
        "footer": {
            "text": "2/7 단계"
        }
    },
    "onboarding_guide_rules": {
        "title": "",
        "description":
        "## 📜 마을의 규칙을 꼭 읽어주세요! 📜\n> ### 우리 마을의 모든 주민들이 즐겁고 평화롭게 지내기 위한 약속이에요.\n### 📜 규칙 채널 확인 안내\n- 규칙 채널에는 마을의 법과 질서를 지키기 위한 중요한 내용들이 담겨 있어요.\n- 모든 주민분들이 서로를 존중하고 배려하며 즐거운 시간을 보낼 수 있도록, 아래 규칙 채널의 내용을 잠시 시간을 내어 꼼꼼히 읽어주세요.\n### <#1412052221209608273>\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n아래 '다음' 버튼을 눌러 안내를 읽어주세요.",
        "color": 0x5865F2,
        "footer": {
            "text": "3/7 단계"
        }
    },
    "onboarding_guide_channels": {
        "title": "",
        "description":
        "## 🗺️ 마을 지도를 확인하고 둘러보세요! 🗺️\n> ### 🗺️ 마을의 어떤 장소에서 무엇을 할 수 있는지, 한눈에 알아보세요!\n### 마을 지도 확인 안내\n- 마을의 이곳저곳을 둘러보며 새로운 이웃들과 즐거운 추억을 만들어갈 준비를 해보아요.\n- 마을 지도 채널은 우리 마을의 다양한 채널에 대한 소개와 이용 방법을 안내하는 곳이에요.\n- 어떤 곳에서 이야기를 나누고, 어디서 게임을 즐길 수 있는지 궁금하다면 아래 마을 지도 채널을 펼쳐보세요!\n### <#1412052225710096555>\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n아래 '다음' 버튼을 눌러 안내를 읽어주세요.",
        "color": 0x5865F2,
        "footer": {
            "text": "4/7 단계"
        }
    },
    "onboarding_guide_roles": {
        "title": "",
        "description":
        "## 🎭 마을의 역할들을 미리 만나보세요! 🎭\n> ### 우리 마을에는 저마다의 개성과 이야기를 가진 역할들이 존재해요.\n### 🎭 역할 소개 확인 안내\n- 각 역할에 따라 참여할 수 있는 특별한 게임이나 채널이 달라지기도 한답니다.\n- 자신에게 어울리는 역할은 무엇일지 상상해보며, 앞으로의 마을 생활을 더욱 기대해보세요!\n- 아래 역할 소개 채널은 마을의 다양한 역할들이 각각 어떤 의미를 가지고, 어떤 활동을 하는지 설명해주는 곳이에요.\n### <#1412052229405409400>\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n아래 '다음' 버튼을 눌러 안내를 읽어주세요.",
        "color": 0x5865F2,
        "footer": {
            "text": "5/7 단계"
        }
    },
    "onboarding_guide_staff": {
        "title": "",
        "description":
        "## 🏢 마을 사무소의 직원들을 소개합니다! 🏢\n> ### 마을에 어려움이 생기거나 궁금한 점이 있다면, 언제든지 사무소의 직원들을 찾아주세요!\n### 🏢 직원 소개 확인 안내\n- 든든한 직원들이 있기에 우리 마을은 언제나 평화롭고 즐겁답니다!\n- 도움이 필요하거나 건의할 사항이 있다면 언제든지 직원들을 호출해주세요. 친절하게 안내해 드릴 거예요.\n- 아래 직원 소개 채널에서는 마을을 위해 힘써주시는 촌장님과 부촌장님, 직원(관리자)들을 만날 수 있어요.\n### <#1412052233121431642>\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n아래 '다음' 버튼을 눌러 안내를 읽어주세요.",
        "color": 0x5865F2,
        "footer": {
            "text": "6/7 단계"
        }
    },
    "onboarding_guide_intro": {
        "title": "",
        "description":
        "## 마지막으로, 자기소개인 '주민 등록증'을 작성해봅시다!\n### 주민등록 규칙\n- 성별 공개는 필수입니다.\n- 이름에 특수문자, 이모티콘, 공백은 사용할 수 없습니다.\n- 이름은 최대 8글자로 한글은 2글자, 영문, 숫자는 1글자로 취급됩니다.\n- 부적절한 닉네임은 승인되지 않습니다.\n- 모든 항목을 정확하게 기입해 주십시오. (미기입시 거부될 수 있습니다.)\n- 참여 경로를 꼭 기입해 주시기 바랍니다. (예: Disboard, 〇〇님으로부터의 초대 등)\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n제출 후, 직원이 확인하고 승인하면 정식 주민으로 인정됩니다.",
        "color": 0x5865F2,
        "footer": {
            "text": "7/7 단계"
        }
    },
    "welcome_embed": {
        "description":
        " \n<a:newheart_01:1427212124588998706>  。 ⁠<#1419879548744634371> - 자기소개 작성\n. ╰─➤ 이름 / 나이 / 성별 / 경로\n\n<a:newheart_02:1427212125981511723>  。 ⁠<#1419879548744634374> - 경로 인증\n. ╰─➤ 링크 화면 캡처 후 사진 첨부\n\n<a:newheart_03:1427212127977865286>  。⁠<#1419879549847736361> - 서버 규칙\n. ╰─➤규칙 미숙지로 인한 불이익은 본인의 책임입니다.\n\n<a:newheart_05:1427212131677241354>  。⁠<#1419879548744634375>\n. ╰─➤ <@&1419879547318435996> 멘션해서 도움 요청하기!\n\n<a:newheart_06:1427212133036199987> 。주의해주세요!\n. ╰─➤ 비협조적인 태도는 조치 대상입니다.",
        "color": 0x3498DB,
        "image": {
            "url": "https://media.discordapp.net/attachments/1094374688098107472/1436296497653092442/40543999f1170af27547039756523174.jpg?ex=690f16da&is=690dc55a&hm=d302c335467234af5cda13da1213360ceb4748174824a2f83ffaff88f7accefc&=&format=webp"
        }
    },
    "farewell_embed": {
        "description":
        "## 👋 다음에 또 만나요\n### **{member_name}**님이 마을을 떠났습니다.\n### 함께했던 모든 순간에 감사드립니다.\n### 앞으로의 여정에 행운이 가득하기를 바랍니다.",
        "color": 0x99AAB5
    },
    "panel_notification_roles": {
        "description": "### <a:123:1436399569804984320> 선택역할\n\n<a:loverh01:1427211866081591347> <@&1419879547251200057>\n╰─➤ 마음이 담긴 연락을 받아볼 수 있어요.\n\n<a:loverh04:1427212010633957447> <@&1419879547251200056>\n╰─➤ 가장 먼저 유저들과 대화할 수 있어요.\n\n<a:loverh08:1427212016753573996> <@&1419879547251200054>\n╰─➤ <#1419879550644387861>\n\n<a:loverh03:1427212009052704799> <@&1419879547251200055>\n╰─➤ <#1419879551772659764>\n\n<a:loverh07:1427212015084113993> <@&1436037451314495498>\n╰─➤ <#1430188707452948723>",
        "color": 0x5865F2
    },
    "panel_game_roles": {
        "title": "🎮 게임 역할 부여",
        "description": "아래 메뉴에서 플레이하는 게임 역할을 선택하여 파티원을 찾아보세요!",
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
    # ▼▼▼▼▼ [수정] "panel_nicknames"의 description 내용을 교체합니다. ▼▼▼▼▼
    "panel_nicknames": {
        "title": "✒️ 이름 변경",
        "description": "### 아래 버튼을 통해 공장에서 사용할 이름을 변경할 수 있습니다.\n- 신청서가 제출되면 이 채널에 관리자용 승인 메시지가 나타납니다.\n- 이름은 **순수 한글**로만 만들 수 있습니다. (공백, 특수문자, 영문, 숫자 불가)\n- 이름은 **최대 6자**까지 가능합니다.\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n제출 후, 관리자가 확인하고 승인하면 이름이 변경됩니다.",
        "color": 0x5865F2
    },
    "embed_main_chat_welcome": {
        "title": "",
        "description": "### 새로운 이웃이 생겼어요! 다 함께 따뜻한 인사를 나눠주세요. :sparkling_heart:\n**마을에서의 생활이 더욱 즐거워질 수 있도록,**\n**몇 가지 유용한 안내판을 준비했어요. :map:**\n### ┃ :house_with_garden: 마을 적응이 어렵나요?\n　╰─➤ 도움이 필요하다면 언제든 {staff_role_mention}님을 찾아주세요!\n### ┃ :black_nib: 새로운 이름이 필요하세요?\n　╰─➤{nickname_channel_mention} 채널에서 멋진 이름으로 바꿀 수 있어요.\n### ┃ :bell: 알림을 받고 싶으신가요?\n　╰─➤{role_channel_mention}에서 개성 있는 역할을 받아보세요.\n### ┃ :love_letter: 좋은 생각이 떠올랐나요?\n　╰─➤{inquiry_channel_mention}에 소중한 의견을 남겨주세요.\n### ┃ :fairy: 마을의 요정(봇)이 궁금하세요?\n　╰─➤ {bot_guide_channel_mention} 채널에서 사용법을 확인해 주세요.\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n### ┃:circus_tent: 현재 진행 중인 마을 축제!\n　╰─➤{festival_channel_mention}을 확인해 주세요.\n⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯",
        "color": 0x2ECC71
    },
    "panel_warning": {
        "title": "🚨 경고 관리 패널",
        "description":
        "서버 규칙을 위반한 유저에게 아래 버튼을 통해 벌점을 부여할 수 있습니다.\n\n**이 기능은 `포장 관리팀`만 사용할 수 있습니다.**",
        "color": 15548997
    },
    "log_warning": {
        "title": "🚨 경고 발급 알림",
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
        "{user_mention}님이 활동 보상로 코인을 획득했습니다.",
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
    },
    "log_item_use_event_priority": {
        "title": "✨ 이벤트 우선권 사용 알림",
        "color": 16776960
    },
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
        }, {
            "name": "⛏️ 채광",
            "value": "{mining_champion}",
            "inline": False
        }],
        "footer": {
            "text": "매일 00:05 KST에 갱신됩니다."
        }
    },
    "panel_mining": {
        "title": "⛏️ 광산 입구",
        "description": "> 광산에 들어가려면 '광산 입장권'이 필요합니다.\n> 입장권은 상점에서 구매할 수 있습니다.",
        "color": 0x607D8B
    },
    "mine_thread_welcome": {
        "title": "{user_name}님의 광산 채굴",
        "description": "환영합니다! 이 광산은 10분 동안 유지됩니다.\n\n아래 '광석 찾기' 버튼을 눌러 주변을 탐색하세요.\n탐색 및 채굴에는 약간의 시간이 소요됩니다.",
        "color": 0x607D8B
    },
    "log_item_use_mine_pass": {
        "title": "🎟️ 광산 입장권 사용 알림",
        "color": 0x607D8B
    },
    "panel_blacksmith": {
        "title": "🛠️ 대장간",
        "description": "> 각종 도구를 업그레이드하여 성능을 향상시킬 수 있습니다.\n> 업그레이드에는 재료와 시간, 코인이 필요합니다.",
        "color": 0x964B00
    },
    "panel_trade": {
        "title": "🤝 거래소",
        "description": "> 다른 유저와 아이템을 교환하거나 우편을 보낼 수 있습니다.",
        "color": 0x3498DB
    },
    "log_trade_success": {
        "title": "✅ 거래 성사",
        "description": "{user1_mention}님과 {user2_mention}님의 거래가 성공적으로 완료되었습니다.",
        "color": 0x2ECC71,
        "footer": {
            "text": "거래세: {commission}{currency_icon}"
        }
    },
    "dm_new_mail": {
        "title": "📫 새로운 우편 도착",
        "description": "{sender_name}님으로부터 새로운 우편이 도착했습니다.\n`/거래소` 패널의 우편함에서 확인해주세요.",
        "color": 0x3498DB
    },
    "log_new_mail": {
        "title": "📫 새로운 우편 도착",
        "description": "{sender_mention}님이 {recipient_mention}님에게 우편을 보냈습니다.",
        "color": 0x3498DB
    },
    "log_blacksmith_complete": {
        "title": "🎉 도구 업그레이드 완료!",
        "description": "{user_mention}님의 **{tool_name}** 업그레이드가 완료되었습니다! 인벤토리를 확인해주세요.",
        "color": 0xFFD700
    },
    "log_mining_result": {
        "title": "⛏️ 광산 탐사 결과",
        "description": "{user_mention}님의 탐사가 종료되었습니다.",
        "color": 0x607D8B,
        "fields": [
            {
                "name": "사용한 장비",
                "value": "`{pickaxe_name}`",
                "inline": True
            },
            {
                "name": "채굴한 광물",
                "value": "{mined_ores}",
                "inline": False
            }
        ]
    },
    "panel_cooking_creation": {
        "title": "🍲 나만의 부엌 만들기!",
        "description": "> 아래 버튼을 눌러 당신만의 부엌(개인 스레드)을 만듭니다.\n> 가마솥을 설치하고 다양한 요리에 도전해보세요!",
        "color": 15105078
    },
    "cooking_thread_welcome": {
        "title": "{user_name}님의 부엌",
        "description": "환영합니다! 이곳은 당신만의 요리 공간입니다.\n\n**시작하는 법:**\n1. 먼저 상점에서 '가마솥'을 구매합니다.\n2. 아래 메뉴에서 가마솥을 선택하고 재료를 넣어 요리를 시작해보세요!",
        "color": 15105078
    },
    "log_cooking_complete": {
        "title": "🎉 요리 완성!",
        "description": "{user_mention}님의 **{recipe_name}** 요리가 완성되었습니다! 부엌을 확인해주세요.",
        "color": 16766720
    },
    "log_recipe_discovery": {
        "title": "🎉 새로운 레시피 발견!",
        "description": "**{user_mention}**님이 새로운 요리 **'{recipe_name}'**의 레시피를 최초로 발견했습니다!",
        "color": 0xFFD700,
        "fields": [
            {
                "name": "📜 레시피",
                "value": "```{ingredients_str}```",
                "inline": False
            }
        ]
    },
    "log_item_use_job_reset": {
        "title": "📜 직업 초기화권 사용 알림",
        "description": "{user_mention}님이 직업을 초기화하고 새로운 여정을 시작합니다.",
        "color": 0x9B59B6
    },
    "panel_friend_invite": {
        "title": "💌 친구 초대 이벤트!",
        "description": "서버에 친구를 초대하고 특별한 보상을 받아가세요!\n\n> 아래 버튼을 눌러 당신만의 **영구 초대 코드**를 확인하거나 생성하세요.\n> 친구가 이 코드로 서버에 들어와 **'주민'이 되면**, 당신에게 **500코인**이 지급됩니다!\n\n**[이벤트 방식]**\n- 코드는 만료되거나 사용 횟수 제한이 없습니다.\n- 이미 코드가 있다면 버튼을 눌러도 새 코드가 생성되지 않고 기존 코드를 알려줍니다.\n- 보상은 초대한 친구가 서버의 정식 주민이 되었을 때 지급됩니다.",
        "color": 0x5865F2,
        "footer": {
            "text": "친구와 함께 즐거운 마을 생활을!"
        }
    },
    "log_friend_invite_success": {
        "title": "🎉 새로운 주민 탄생! (친구 초대)",
        "description": "{new_member_mention}님이 {inviter_mention}님의 초대로 마을에 합류하고, 드디어 정식 주민이 되었습니다!",
        "color": 0x3498DB,
        "fields": [{
            "name": "💌 초대한 사람",
            "value": "{inviter_mention}",
            "inline": True
        }, {
            "name": "🎁 새로 온 주민",
            "value": "{new_member_mention}",
            "inline": True
        }, {
            "name": "💰 지급된 보상",
            "value": "`500`{currency_icon}",
            "inline": False
        }, {
            "name": "🏆 총 초대 횟수",
            "value": "**{invite_count}**명",
            "inline": False
        }],
        "footer": {
            "text": "친구 초대 이벤트"
        }
    },
    "panel_incubator": {
        "title": "🥚 펫 인큐베이터",
        "description": "> 보유하고 있는 알을 부화기에 넣어 펫을 얻을 수 있습니다.\n> 부화에는 시간이 필요하며, 알을 오래 품을수록 더 좋은 능력치를 가질 수 있습니다.",
        "color": 0x7289DA
    },
    "panel_pet_exploration": {
        "title": "🏕️ 펫 탐사",
        "description": "펫을 보내 보상을 얻어오세요!\n\n> 각 지역은 펫의 레벨 제한이 있으며, 레벨이 높을수록 더 좋은 보상을 얻을 수 있는 지역에 도전할 수 있습니다.",
        "color": 0x7289DA,
        "fields": [
            {
                "name": "🔥 불 슬라임의 둥지",
                "value": "> 요구 레벨: **Lv.1**",
                "inline": True
            },
            {
                "name": "💧 물 슬라임의 둥지",
                "value": "> 요구 레벨: **Lv.10**",
                "inline": True
            },
            {
                "name": "⚡ 전기 슬라임의 둥지",
                "value": "> 요구 레벨: **Lv.20**",
                "inline": True
            },
            {
                "name": "🌿 풀 슬라임의 둥지",
                "value": "> 요구 레벨: **Lv.30**",
                "inline": True
            },
            {
                "name": "✨ 빛 슬라임의 둥지",
                "value": "> 요구 레벨: **Lv.40**",
                "inline": True
            },
            {
                "name": "🌑 어둠 슬라임의 둥지",
                "value": "> 요구 레벨: **Lv.50**",
                "inline": True
            }
        ]
    },
    "panel_pet_pvp": {
        "title": "⚔️ 펫 대전장",
        "description": "> 다른 유저의 펫과 실력을 겨뤄보세요!\n> 아래 버튼을 눌러 대결할 상대를 찾을 수 있습니다.",
        "color": 0xC27C0E,
        "footer": { "text": "도전 신청에는 5분의 재사용 대기시간이 적용됩니다." }
    },
    "log_pet_pvp_result": {
        "title": "🏆 펫 대전 종료! 🏆",
        "description": "**{winner_mention}**님의 펫 **'{winner_pet_name}'**(이)가 치열한 전투 끝에 승리했습니다!",
        "color": 0xFFD700,
        "fields": [
            { "name": "👑 승자", "value": "{winner_mention}", "inline": True },
            { "name": "💧 패자", "value": "{loser_mention}", "inline": True }
        ]
    },
    # ▼▼▼▼▼ [추가] 경고 차감 로그 임베드 ▼▼▼▼▼
    "log_warning_deduct": {
        "title": "✅ 경고 차감 알림",
        "color": 3066993
    },
    "embed_reminder_disboard": {
        "title": "⏰ Disboard BUMP 시간입니다!",
        "description": "서버를 홍보할 시간입니다!\n아래 명령어를 입력해주세요.\n\n> `/bump`",
        "color": 0x5865F2,
        "footer": { "text": "2시간마다 BUMP가 가능합니다." }
    },
    "embed_reminder_dicoall": {
        "title": "⏰ Dicoall UP 시간입니다!",
        "description": "서버 순위를 올릴 시간입니다!\n아래 명령어를 입력해주세요.\n\n> `/up`",
        "color": 0x2ECC71,
        "footer": { "text": "1시간마다 UP이 가능합니다." }
    },
    "embed_reminder_confirmation_disboard": {
        "title": "서버 갱신 완료!",
        "description": "DISBOARD에서 확인해 주세요!\n[DISBOARD](https://disboard.org/ko/server/1419879546752077867)",
        "color": 0x5865F2
    },
    "embed_reminder_confirmation_dicoall": {
        "title": "서버 갱신 완료!",
        "description": "DICOALL에서 확인해 주세요!\n[DICOALL](https://kr.dicoall.com/server/1419879546752077867)",
        "color": 0x2ECC71
    },
    # ▼▼▼ [추가] 새로운 티켓 패널 및 관리자 신청 관련 임베드 ▼▼▼
    "panel_ticket_main": {
        "title": "📨 고객 지원 센터",
        "description": "서버 이용 중 궁금한 점, 불편한 점이 있거나 새로운 아이디어가 있다면 언제든지 찾아주세요.\n\n> **문의/건의**: 서버 운영, 이벤트, 봇 기능 등 궁금한 점이나 건의사항을 보냅니다.\n> **신고**: 서버 규칙 위반 사례를 목격했거나 유저 간 분쟁 발생 시 제보합니다.\n> **관리자 신청**: 공장을 위해 함께 일하고 싶다면 관리자(스태프)로 지원할 수 있습니다.",
        "color": 0x5865F2,
        "footer": { "text": "아래 버튼을 눌러 티켓을 생성해주세요." }
    },
    "embed_ticket_staff_application": {
        "title": "📝 새로운 관리자 지원서",
        "description": "{member_mention}님이 서버의 새로운 관리자로 지원했습니다.",
        "color": 0xFEE75C
    },
    # ▼▼▼ [추가] 부스트 감사 DM 임베드 ▼▼▼
    "dm_boost_reward": {
        "title": "───────────── · · ୨୧ · · ─────────────",
        "description": "**{member_name}** 님\n공장의 **도넛**이 되신 것을 환영합니다.\n\n공장의 도넛이 된 {member_name} 님을 위한 선물!\n\n### ꒰ 부스트 혜택 ꒱\nA. <@&1426938324546879608> 역할 <a:newheart_01:1427212124588998706>\n\nB. 멤버 목록 상단 배치\n\nC. 부스트 전용 괄호 및 이모지 변경\n\nD. 이벤트 진행시 혜택 지급\n\nE. <@&1419879547171508264> \n╰ ⁠：<#1419879550191534181> 중 선택 - ( 준 비 중 )\n\nF. 바구니에 담길 수 있는 특별 권한\n╰ ⁠：바구니 선택 가능",
        "color": 0xF47FFF,
    },
    # ▲▲▲ [추가 완료] ▲▲▲

    # ... (기존의 모든 다른 UI_EMBEDS 내용은 그대로 유지) ...
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
        "label": "경고 부여",
        "style": "danger",
        "emoji": "🚨",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "deduct_warning_button",
        "panel_key": "warning",
        "component_type": "button",
        "label": "경고 차감",
        "style": "success",
        "emoji": "✅",
        "row": 0,
        "order_in_row": 1
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
    {
        "component_key": "enter_mine",
        "panel_key": "panel_mining",
        "component_type": "button",
        "label": "입장하기",
        "style": "secondary",
        "emoji": "⛏️",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "create_friend_invite",
        "panel_key": "friend_invite",
        "component_type": "button",
        "label": "초대 코드 만들기",
        "style": "success",
        "emoji": "💌",
        "row": 0,
        "order_in_row": 0
    },
    # ▼▼▼ [추가] 새로운 티켓 패널 버튼 3개 ▼▼▼
    {
        "component_key": "ticket_create_inquiry",
        "panel_key": "ticket_main",
        "component_type": "button",
        "label": "문의/건의",
        "style": "primary",
        "emoji": "📨",
        "row": 0,
        "order_in_row": 0
    },
    {
        "component_key": "ticket_create_report",
        "panel_key": "ticket_main",
        "component_type": "button",
        "label": "신고",
        "style": "danger",
        "emoji": "🚨",
        "row": 0,
        "order_in_row": 1
    },
    {
        "component_key": "ticket_create_application",
        "panel_key": "ticket_main",
        "component_type": "button",
        "label": "관리자 신청",
        "style": "success",
        "emoji": "✨",
        "row": 0,
        "order_in_row": 2
    },
]
SETUP_COMMAND_MAP = {
    "panel_notification_roles": {
        "type": "panel",
        "cog_name": "RolePanel",
        "key": "notification_role_panel_channel_id", # DB에 채널 ID를 저장할 새로운 키
        "friendly_name": "[패널] 알림 역할 자동부여",
        "channel_type": "text"
    },
    # ▼▼▼ [추가] 게임 역할 패널 설치 정보 ▼▼▼
    "panel_game_roles": {
        "type": "panel",
        "cog_name": "RolePanel",
        "key": "game_role_panel_channel_id", # DB에 채널 ID를 저장할 새로운 키
        "friendly_name": "[패널] 게임 역할 자동부여",
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
    "panel_mining": {
        "type": "panel",
        "cog_name": "Mining",
        "key": "mining_panel_channel_id",
        "friendly_name": "[게임] 광산 패널",
        "channel_type": "text"
    },
    "panel_trade": {
        "type": "panel",
        "cog_name": "Trade",
        "key": "trade_panel_channel_id",
        "friendly_name": "[게임] 거래소 패널",
        "channel_type": "text"
    },
    "panel_pet_exploration": {
        "type": "panel",
        "cog_name": "Exploration",
        "key": "exploration_panel_channel_id",
        "friendly_name": "[게임] 펫 탐사 패널",
        "channel_type": "text"
    },
    "panel_pet_pvp": {
        "type": "panel",
        "cog_name": "PetPvP",
        "key": "pet_pvp_panel_channel_id",
        "friendly_name": "[게임] 펫 대전장 패널",
        "channel_type": "text"
    },
    "log_trade": {
        "type": "channel",
        "cog_name": "Trade",
        "key": "trade_log_channel_id",
        "friendly_name": "[로그] 거래 기록",
        "channel_type": "text"
    },
    # ▼▼▼ [수정] 기존 티켓 패널 설정을 새로운 통합 패널로 변경 ▼▼▼
    "panel_ticket_main": {
        "type": "panel",
        "cog_name": "TicketSystem",
        "key": "ticket_main_panel_channel_id",
        "friendly_name": "[패널] 통합 티켓 시스템",
        "channel_type": "text"
    },
    "log_staff_application": {
        "type": "channel",
        "cog_name": "TicketSystem",
        "key": "staff_application_log_channel_id",
        "friendly_name": "[로그] 관리자 지원서 기록",
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
    # ▼▼▼ [추가] 새로운 음성 채널 생성기 설정 4개를 추가합니다. ▼▼▼
    "channel_vc_creator_mixer": {
        "type": "channel",
        "cog_name": "VoiceMaster",
        "key": "vc_creator_mixer",
        "friendly_name": "[음성] 소형믹서 생성",
        "channel_type": "voice"
    },
    "channel_vc_creator_line": {
        "type": "channel",
        "cog_name": "VoiceMaster",
        "key": "vc_creator_line",
        "friendly_name": "[음성] 미니라인 생성",
        "channel_type": "voice"
    },
    "channel_vc_creator_sample": {
        "type": "channel",
        "cog_name": "VoiceMaster",
        "key": "vc_creator_sample",
        "friendly_name": "[음성] 샘플룸 생성",
        "channel_type": "voice"
    },
    "channel_vc_creator_game": {
        "type": "channel",
        "cog_name": "VoiceMaster",
        "key": "vc_creator_game",
        "friendly_name": "[음성] 게임방 생성",
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
        "friendly_name": "[로그] 음성 채널 활동",
        "channel_type": "text"
    },
    "log_join": {
        "type": "channel",
        "cog_name": "JoinLogger",
        "key": "log_channel_join",
        "friendly_name": "[로그] 서버 입장",
        "channel_type": "text"
    },
    "log_leave": {
        "type": "channel",
        "cog_name": "LeaveLogger",
        "key": "log_channel_leave",
        "friendly_name": "[로그] 서버 퇴장",
        "channel_type": "text"
    },
    "log_kick": {
        "type": "channel",
        "cog_name": "KickLogger",
        "key": "log_channel_kick",
        "friendly_name": "[로그] 서버 추방",
        "channel_type": "text"
    },
    "log_ban": {
        "type": "channel",
        "cog_name": "BanLogger",
        "key": "log_channel_ban",
        "friendly_name": "[로그] 서버 차단",
        "channel_type": "text"
    },
    "log_timeout": {
        "type": "channel",
        "cog_name": "TimeoutLogger",
        "key": "log_channel_timeout",
        "friendly_name": "[로그] 타임아웃",
        "channel_type": "text"
    },
    "log_role": {
        "type": "channel",
        "cog_name": "RoleLogger",
        "key": "log_channel_role",
        "friendly_name": "[로그] 역할 (변경/부여/제거)",
        "channel_type": "text"
    },
    "log_nickname": {
        "type": "channel",
        "cog_name": "NicknameLogger",
        "key": "log_channel_nickname",
        "friendly_name": "[로그] 별명 변경",
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
        "friendly_name": "[로그] 서버 설정 변경",
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
    "log_item_mine_pass": {
        "type": "channel",
        "cog_name": "ItemSystem",
        "key": "log_item_mine_pass",
        "friendly_name": "[로그] 광산 입장권 사용 내역",
        "channel_type": "text"
    },
    "log_pet_levelup": {
        "type": "channel",
        "cog_name": "PetSystem",
        "key": "log_pet_levelup_channel_id",
        "friendly_name": "[로그] 펫 성장 기록",
        "channel_type": "text"
    },
    "channel_bump_reminder": {
        "type": "channel",
        "cog_name": "Reminder",
        "key": "bump_reminder_channel_id",
        "friendly_name": "[알림] Disboard BUMP 채널",
        "channel_type": "text"
    },
    # ▼▼▼ [핵심 수정] dissoku -> dicoall 로 변경 ▼▼▼
    "channel_dicoall_reminder": {
        "type": "channel",
        "cog_name": "Reminder",
        "key": "dicoall_reminder_channel_id",
        "friendly_name": "[알림] Dicoall UP 채널",
        "channel_type": "text"
    },
    "channel_weather": {
        "type": "channel",
        "cog_name": "WorldSystem",
        "key": "weather_channel_id",
        "friendly_name": "[알림] 날씨 예보 채널",
        "channel_type": "text"
    },
    "onboarding_private_age_log_channel_id": {
        "type": "channel", 
        "cog_name": "Onboarding", 
        "key": "onboarding_private_age_log_channel_id", 
        "friendly_name": "[온보딩] 비공개 나이 기록 채널", 
        "channel_type": "text"
    },
    "panel_blacksmith": {
        "type": "panel",
        "cog_name": "Blacksmith",
        "key": "blacksmith_panel_channel_id",
        "friendly_name": "[게임] 대장간 패널",
        "channel_type": "text"
    },
    "log_blacksmith_complete": {
        "type": "channel",
        "cog_name": "Blacksmith",
        "key": "log_blacksmith_channel_id",
        "friendly_name": "[로그] 대장간 제작 완료",
        "channel_type": "text"
    },
    "panel_cooking_creation": {
        "type": "panel",
        "cog_name": "Cooking",
        "key": "cooking_creation_panel_channel_id",
        "friendly_name": "[게임] 요리 시작 패널",
        "channel_type": "text"
    },
    "log_cooking_complete": {
        "type": "channel",
        "cog_name": "Cooking",
        "key": "log_cooking_complete_channel_id",
        "friendly_name": "[로그] 요리 완성",
        "channel_type": "text"
    },
    # [추가] 레시피 발견 로그 채널 설정
    "log_recipe_discovery": {
        "type": "channel",
        "cog_name": "Cooking",
        "key": "log_recipe_discovery_channel_id",
        "friendly_name": "[로그] 레시피 발견",
        "channel_type": "text"
    },
    "log_item_job_reset": {
        "type": "channel",
        "cog_name": "ItemSystem",
        "key": "log_item_job_reset",
        "friendly_name": "[로그] 직업 초기화권 사용 내역",
        "channel_type": "text"
    },
    "panel_friend_invite": {
        "type": "panel",
        "cog_name": "FriendInvite",
        "key": "friend_invite_panel_channel_id",
        "friendly_name": "[게임] 친구 초대 패널",
        "channel_type": "text"
    },
    "log_friend_invite": {
        "type": "channel",
        "cog_name": "FriendInvite",
        "key": "friend_invite_log_channel_id",
        "friendly_name": "[로그] 친구 초대 이벤트",
        "channel_type": "text"
    },
    # ▼▼▼ [추가] 이 부분을 추가해주세요 ▼▼▼
    "log_boost": {
        "type": "channel",
        "cog_name": "MemberEvents",
        "key": "boost_log_channel_id",
        "friendly_name": "[로그] 서버 부스트 활동",
        "channel_type": "text"
    },
    "panel_incubator": {
        "type": "panel",
        "cog_name": "PetSystem",
        "key": "incubator_panel_channel_id",
        "friendly_name": "[게임] 펫 인큐베이터 패널",
        "channel_type": "text"
    },
    "channel_weekly_boss": {
        "type": "channel",
        "cog_name": "BossRaid", # 게임 봇의 Cog 이름과 일치해야 함
        "key": "weekly_boss_channel_id",
        "friendly_name": "[보스] 주간 보스 채널",
        "channel_type": "text"
    },
    "channel_monthly_boss": {
        "type": "channel",
        "cog_name": "BossRaid", # 게임 봇의 Cog 이름과 일치해야 함
        "key": "monthly_boss_channel_id",
        "friendly_name": "[보스] 월간 보스 채널",
        "channel_type": "text"
    },
    "log_boss_events": {
        "type": "channel",
        "cog_name": "BossRaid", # 게임 봇의 Cog 이름과 일치해야 함
        "key": "boss_log_channel_id",
        "friendly_name": "[로그] 보스 이벤트 기록",
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
    # ▼▼▼ [수정] 알림 역할 패널 설정 ▼▼▼
    "panel_notification_roles": {
        "panel_key": "panel_notification_roles",
        "embed_key": "panel_notification_roles",
        "categories": [
            {
                "id": "notifications",
                "label": "🔔 알림",
                "description": "받고 싶은 알림을 선택하세요.",
                "emoji": "🔔"
            }
        ],
        "roles": {
            "notifications": [
                { "role_id_key": "role_notify_dding", "label": "⊹ ₊ 띵 동 .ᐟ ⊹" },
                { "role_id_key": "role_notify_welcome", "label": "˗ˏˋ    환 영 합 니 다 .ᐟ  ˊˎ˗" },
                { "role_id_key": "role_notify_ask", "label": "『 🍳：에 스 크 알 림 』" },
                { "role_id_key": "role_notify_disboard", "label": "『 🍨 : 공장 홍보대사 』" },
                { "role_id_key": "role_notify_up", "label": "『 🍭 : 공장 업 』" },
            ]
        }
    },
    # ▼▼▼ [추가] 게임 역할 패널 설정 ▼▼▼
    "panel_game_roles": {
        "panel_key": "panel_game_roles",
        "embed_key": "panel_game_roles",
        "categories": [
            {
                "id": "games",
                "label": "🎮 게임",
                "description": "플레이하는 게임을 선택하세요.",
                "emoji": "🎮"
            }
        ],
        "roles": {
            "games": [
                { "role_id_key": "role_game_tft", "label": "롤토체스" },
                { "role_id_key": "role_game_lol", "label": "리그오브레전드" },
                { "role_id_key": "role_game_valorant", "label": "발로란트" },
                { "role_id_key": "role_game_overwatch", "label": "오버워치" },
                { "role_id_key": "role_game_lostark", "label": "로스트아크" },
                { "role_id_key": "role_game_minecraft", "label": "마인크래프트" },
                { "role_id_key": "role_game_zombi", "label": "좀비고등학교" },
                { "role_id_key": "role_platform_steam", "label": "스팀 게임" },
                { "role_id_key": "role_platform_smartphone", "label": "모바일 게임" },
                { "role_id_key": "role_platform_switch", "label": "기타 게임" },
            ]
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
# ▼▼▼ [핵심 수정] JOB_SYSTEM_CONFIG에 요리사 직업 매핑 추가 ▼▼▼
JOB_SYSTEM_CONFIG = {
    "JOB_ROLE_MAP": {
        "fisherman": "role_job_fisherman",
        "farmer": "role_job_farmer",
        "miner": "role_job_miner",
        "chef": "role_job_chef", # [추가]
        "master_angler": "role_job_master_angler",
        "master_farmer": "role_job_master_farmer",
        "expert_miner": "role_job_expert_miner",
        "master_chef": "role_job_master_chef" # [추가]
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
# ▲▲▲ [핵심 수정] 종료 ▲▲▲
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
    "trigger_daily_updates": "[수동] 시세 및 작물 상태 업데이트 즉시 실행",
    "farm_next_day": "[농장] 다음 날로 시간 넘기기 (테스트용)",
    "farm_reset_date": "[농장] 시간을 현재로 초기화 (테스트용)",
    "pet_hatch_now": "[펫] 펫 즉시 부화 (테스트용)",
    "pet_admin_levelup": "[펫] 펫 1레벨업 (테스트용)",
    "pet_level_set": "[펫] 펫 레벨 설정 (테스트용)", # <--- 이 줄을 추가하세요.
    "exploration_complete_now": "[펫] 펫 탐사 즉시 완료 (테스트용)",
    "boss_spawn_test": "[보스] 강제 소환 (테스트용)",
    "boss_defeat_test": "[보스] 강제 처치 (테스트용)",
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
            "key": "info", "title_suffix": " - 정보", "label": "정보", "emoji": "ℹ️"
        }, {
            "key": "item", "title_suffix": " - 아이템", "label": "아이템", "emoji": "📦"
        }, {
            "key": "ticket", "title_suffix": " - 입장권", "label": "입장권", "emoji": "🎟️"
        }, {
            "key": "gear", "title_suffix": " - 장비", "label": "장비", "emoji": "⚒️"
        }, {
            "key": "fish", "title_suffix": " - 어항", "label": "어항", "emoji": "🐠"
        }, {
            "key": "seed", "title_suffix": " - 씨앗", "label": "씨앗", "emoji": "🌱"
        }, {
            "key": "crop", "title_suffix": " - 작물", "label": "작물", "emoji": "🌾"
        }, {
            "key": "mineral", "title_suffix": " - 광물", "label": "광물", "emoji": "💎"
        }, {
            "key": "food", "title_suffix": " - 음식", "label": "음식", "emoji": "🍲"
        }, {
            "key": "loot", "title_suffix": " - 전리품", "label": "전리품", "emoji": "🏆"
        }, {
            "key": "pet", "title_suffix": " - 펫 아이템", "label": "펫 아이템", "emoji": "🐾"
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
        "mineral_tab": {
            "no_items": "보유 중인 광물이 없습니다."
        },
        "food_tab": {
            "no_items": "보유 중인 음식이 없습니다."
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
    "50": [
        {
            "job_key": "fisherman",
            "job_name": "낚시꾼",
            "role_key": "role_job_fisherman",
            "description": "물고기를 낚는 데 특화된 전문가입니다.",
            "abilities": [
                {"ability_key": "fish_bait_saver_1", "ability_name": "미끼 절약 (확률)", "description": "낚시할 때 일정 확률로 미끼를 소모하지 않습니다."},
                {"ability_key": "fish_bite_time_down_1", "ability_name": "입질 시간 단축", "description": "물고기가 미끼를 무는 데 걸리는 시간이 전체적으로 2초 단축됩니다."}
            ]
        },
        {
            "job_key": "farmer",
            "job_name": "농부",
            "role_key": "role_job_farmer",
            "description": "작물을 키우고 수확하는 데 특화된 전문가입니다.",
            "abilities": [
                {"ability_key": "farm_seed_saver_1", "ability_name": "씨앗 절약 (확률)", "description": "씨앗을 심을 때 일정 확률로 씨앗을 소모하지 않습니다."},
                {"ability_key": "farm_water_retention_1", "ability_name": "수분 유지력 UP", "description": "작물이 수분을 더 오래 머금어 물을 주는 간격이 길어집니다."}
            ]
        },
        {
            "job_key": "miner",
            "job_name": "광부",
            "role_key": "role_job_miner",
            "description": "광물 채굴에 특화된 전문가입니다.",
            "abilities": [
                {"ability_key": "mine_time_down_1", "ability_name": "신속한 채굴", "description": "광석 채굴에 필요한 시간이 3초 단축됩니다."},
                {"ability_key": "mine_duration_up_1", "ability_name": "집중 탐사", "description": "광산 입장 시 15% 확률로 제한 시간이 2배(20분)로 늘어납니다."}
            ]
        },
        {
            "job_key": "chef",
            "job_name": "요리사",
            "role_key": "role_job_chef",
            "description": "다양한 재료로 맛있는 음식을 만드는 요리의 전문가입니다.",
            "abilities": [
                {"ability_key": "cook_ingredient_saver_1", "ability_name": "알뜰한 손맛 (확률)", "description": "요리할 때 15% 확률로 재료를 소모하지 않습니다."},
                {"ability_key": "cook_time_down_1", "ability_name": "요리의 기본", "description": "모든 요리의 소요 시간이 10% 단축됩니다."}
            ]
        }
    ],
    "100": [
        {
            "job_key": "master_angler",
            "job_name": "강태공",
            "role_key": "role_job_master_angler",
            "description": "낚시의 길을 통달하여 전설의 물고기를 쫓는 자. 낚시꾼의 상위 직업입니다.",
            "prerequisite_job": "fisherman",
            "abilities": [
                {"ability_key": "fish_rare_up_2", "ability_name": "희귀어 확률 UP (대)", "description": "희귀한 물고기를 낚을 확률이 상승합니다."},
                {"ability_key": "fish_size_up_2", "ability_name": "물고기 크기 UP (대)", "description": "낚는 물고기의 평균 크기가 커집니다."}
            ]
        },
        {
            "job_key": "master_farmer",
            "job_name": "대농",
            "role_key": "role_job_master_farmer",
            "description": "농업의 정수를 깨달아 대지로부터 최대의 은혜를 얻는 자. 농부의 상위 직업입니다.",
            "prerequisite_job": "farmer",
            "abilities": [
                {"ability_key": "farm_yield_up_2", "ability_name": "수확량 UP (대)", "description": "작물을 수확할 때의 수확량이 대폭 증가합니다."},
                {"ability_key": "farm_seed_harvester_2", "ability_name": "씨앗 수확 (확률)", "description": "작물 수확 시 낮은 확률로 해당 작물의 씨앗을 1~3개 획득합니다."}
            ]
        },
        {
            "job_key": "expert_miner",
            "job_name": "전문 광부",
            "role_key": "role_job_expert_miner",
            "description": "광맥의 흐름을 읽어 희귀한 광물을 찾아내는 베테랑입니다. 광부의 상위 직업입니다.",
            "prerequisite_job": "miner",
            "abilities": [
                {"ability_key": "mine_rare_up_2", "ability_name": "노다지 발견", "description": "희귀한 광물을 발견할 확률이 대폭 증가합니다."},
                {"ability_key": "mine_double_yield_2", "ability_name": "풍부한 광맥", "description": "광석 채굴 시 20% 확률로 광석을 2개 획득합니다."}
            ]
        },
        {
            # [수정] '마스터 셰프' 능력 최종 수정본
            "job_key": "master_chef",
            "job_name": "마스터 셰프",
            "role_key": "role_job_master_chef",
            "description": "요리의 경지에 이르러 평범한 재료로도 최고의 맛을 이끌어내는 자. 요리사의 상위 직업입니다.",
            "prerequisite_job": "chef",
            "abilities": [
                {
                    "ability_key": "cook_quality_up_2",
                    "ability_name": "장인의 솜씨",
                    "description": "요리 완성 시 10% 확률로 '특상품' 요리를 만듭니다. 특상품은 더 비싸게 판매할 수 있습니다."
                },
                {
                    "ability_key": "cook_double_yield_2",
                    "ability_name": "풍성한 식탁",
                    "description": "요리 완성 시 15% 확률로 결과물을 2개 획득합니다."
                }
            ]
        }
    ]
}
BOSS_REWARD_TIERS = {
    "weekly": [
        {"percentile": 0.03, "name": "최상위 기여자 (1-3%)",   "coins": [20000, 30000], "xp": [2500, 3500], "rare_item_chance": 1.0},
        {"percentile": 0.10, "name": "상위 기여자 (4-10%)",    "coins": [12000, 18000], "xp": [1500, 2200], "rare_item_chance": 0.75},
        {"percentile": 0.30, "name": "핵심 기여자 (11-30%)",   "coins": [7000, 11000],  "xp": [800, 1200],  "rare_item_chance": 0.50},
        {"percentile": 0.50, "name": "우수 기여자 (31-50%)",   "coins": [4000, 6000],   "xp": [400, 600],   "rare_item_chance": 0.25},
        {"percentile": 0.80, "name": "참여자 (51-80%)",      "coins": [1500, 2500],   "xp": [150, 250],   "rare_item_chance": 0.10},
        # --- ▼▼▼▼▼ 핵심 수정 시작 ▼▼▼▼▼ ---
        # 1.0 대신 1.01로 수정하여 100% 순위의 유저도 포함되도록 합니다.
        {"percentile": 1.01, "name": "단순 참여자 (81% 이하)","coins": [500, 1000],    "xp": [50, 100],    "rare_item_chance": 0.0}
        # --- ▲▲▲▲▲ 핵심 수정 종료 ▲▲▲▲▲ ---
    ],
    "monthly": [
        {"percentile": 0.03, "name": "최상위 기여자 (1-3%)",   "coins": [100000, 150000], "xp": [10000, 15000], "rare_item_chance": 1.0},
        {"percentile": 0.10, "name": "상위 기여자 (4-10%)",    "coins": [60000, 90000],   "xp": [6000, 9000],   "rare_item_chance": 0.80},
        {"percentile": 0.30, "name": "핵심 기여자 (11-30%)",   "coins": [35000, 55000],   "xp": [3000, 5000],   "rare_item_chance": 0.60},
        {"percentile": 0.50, "name": "우수 기여자 (31-50%)",   "coins": [20000, 30000],   "xp": [1500, 2500],   "rare_item_chance": 0.35},
        {"percentile": 0.80, "name": "참여자 (51-80%)",      "coins": [8000, 12000],    "xp": [800, 1200],    "rare_item_chance": 0.15},
        # --- ▼▼▼▼▼ 핵심 수정 시작 ▼▼▼▼▼ ---
        {"percentile": 1.01, "name": "단순 참여자 (81% 이하)","coins": [3000, 5000],     "xp": [300, 500],     "rare_item_chance": 0.0}
        # --- ▲▲▲▲▲ 핵심 수정 종료 ▲▲▲▲▲ ---
    ]
}
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 5. 티켓 시스템 역할 그룹 (Ticket System Role Groups)
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# ▼▼▼ [수정] 티켓 시스템 역할 그룹 전체를 아래 내용으로 교체 ▼▼▼
TICKET_MASTER_ROLES = ["role_staff_village_chief", "role_staff_deputy_chief"]
TICKET_REPORT_ROLES = ["role_staff_police"]

# 문의/건의 시 '특정 담당 관리자에게'를 선택했을 때 표시될 팀장 역할 목록
TICKET_LEADER_ROLES = [
    "role_staff_leader_machine",
    "role_staff_leader_syrup",
    "role_staff_leader_packaging",
    "role_staff_leader_cream",
    "role_staff_leader_dough"
]
# ▼▼▼ [추가] 이 부분을 추가해주세요 ▼▼▼
# '모든 부서 관리자에게' 선택 시 멘션될 역할 목록
TICKET_DEPARTMENT_MANAGERS = [
    "role_staff_village_chief",
    "role_staff_deputy_chief",
    "role_approval" # '바구니' 역할
]
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# ▼▼▼ [핵심] 관리자 신청 부서 정보 ▼▼▼
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
TICKET_APPLICATION_DEPARTMENTS = {
#    "pr": {
#        "label": "홍보",
#        "description": "SNS, 서버 홍보 등 대외 활동을 담당합니다.",
#        "emoji": "🍯",
#        "team_role_key": "role_staff_pr",
#        "leader_role_key": "role_staff_leader_syrup"
#    },
    "newbie": {
        "label": "안내/뉴관",
        "description": "새로운 베이커리의 적응을 돕고 서버를 안내합니다.",
        "emoji": "🍥",
        "team_role_key": "role_staff_newbie_helper",
        "leader_role_key": "role_staff_leader_dough"
    },
#    "police": {
#        "label": "보안",
#        "description": "서버 내 규칙 위반을 단속하고 분쟁을 중재합니다.",
#        "emoji": "🫙",
#        "team_role_key": "role_staff_police",
#        "leader_role_key": "role_staff_leader_packaging"
#    },
    "festival": {
        "label": "기획/내전",
        "description": "다양한 서버 이벤트와 내전(게임)을 기획하고 진행합니다.",
        "emoji": "🍦",
        "team_role_key": "role_staff_festival",
        "leader_role_key": "role_staff_leader_cream"
    }
}


# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
