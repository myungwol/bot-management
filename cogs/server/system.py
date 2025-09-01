# cogs/server/system.py
import discord
from discord.ext import commands
from discord import app_commands, ui
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import asyncio
import time

from utils.database import (
    get_config, save_id_to_db, save_config_to_db, get_id,
    get_all_stats_channels, add_stats_channel, remove_stats_channel,
    _channel_id_cache,
    update_wallet,
    supabase,
    get_all_embeds, get_embed_from_db, save_embed_to_db
)
from utils.helpers import calculate_xp_for_level
from utils.ui_defaults import (
    UI_ROLE_KEY_MAP, SETUP_COMMAND_MAP, ADMIN_ROLE_KEYS, 
    ADMIN_ACTION_MAP, UI_STRINGS, JOB_ADVANCEMENT_DATA
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------------------------
# [서버 초기화 설정]
# ---------------------------------------------------------------------------------------------

SERVER_STRUCTURE = {
    "・⎯⎯⎯⎯📜 안내소⎯⎯⎯⎯・": [
        "┣ 🚪 ⊹ 입구", "┣ ℹ️ ⊹ 안내소", "┣ 📝 ⊹ 주민 신청", "┣ 📋 ⊹ 주민등록표", "┣ ❌ ⊹ 주민등록 거절", "┗ 📤 ⊹ 출구"
    ],
    "・⎯⎯⎯⎯🏛️ 마을회관⎯⎯⎯⎯・": [
        "┣ 📢 ⊹ 안내 사항", "┣ ⚖️ ⊹ 규칙", "┣ 🗺️ ⊹ 마을 지도", "┣ 🎭 ⊹ 역할 안내", "┣ 👑 ⊹ 직원 안내", "┗ 📬 ⊹ 문의-건의함"
    ],
    "・⎯⎯⎯⎯🎉 축제⎯⎯⎯⎯・": [
        "┣ 🎪 ⊹ 축제 안내", "┣ 🏆 ⊹ 축제 결과", "┣ 🎟️ ⊹ 축제 신청", "┗ 🎠 ⊹ 축제장"
    ],
    "・⎯⎯⎯⎯🚓 경찰서⎯⎯⎯⎯・": [
        "┣ 🚫 ⊹ 블랙리스트", "┣ 📜 ⊹ 벌점 내역", "┣ ✨ ⊹ 벌점 차감소", "┣ 🔨 ⊹ 벌점 주기", "┗ 🚨 ⊹ 신고하기"
    ],
    "・⎯⎯⎯⎯🌿 산책로⎯⎯⎯⎯・": [
        "┣ 🤫 ⊹ 대나무 숲", "┣ ✒️ ⊹ 이름 변경소", "┣ 📥 ⊹ 이름 변경신청", "┣ 🎨 ⊹ 역할 지급소", "┣ 👋 ⊹ 친구 모집", "┣ 🔔 ⊹ 범프", "┣ 🆙 ⊹ 업", "┗ 📈 ⊹ 레벨"
    ],
    "・⎯⎯⎯⎯💬 광장⎯⎯⎯⎯・": [
        "┣ 💬 ⊹ 메인채팅", "┣ 🌱 ⊹ 뉴비채팅", "┣ 📸 ⊹ 사진방", "┣ 🔗 ⊹ 링크방", "┣ 📔 ⊹ 일기장", "┗ 💭 ⊹ 혼잣말"
    ],
    "・⎯⎯⎯⎯🎤 분수대⎯⎯⎯⎯・": [
        "┣ ⛲ ⊹ 분수대 규칙", "┣ 📞 ⊹ 통화모집", "VOICE:🔊 🛠️ ⊹ 분수대 만들기", "VOICE:🔊 🛋️ ⊹ 벤치 만들기"
    ],
    "・⎯⎯⎯⎯🏠 마이룸⎯⎯⎯⎯・": [
        "┣ 📜 ⊹ 마이룸 규칙", "VOICE:🔊 🚪 ⊹ 마이룸 만들기"
    ],
    "・⎯⎯⎯⎯🎮 놀이터⎯⎯⎯⎯・": [
        "┣ 📜 ⊹ 놀이터 규칙", "┣ 💬 ⊹ 게임 채팅", "┣ 🤝 ⊹ 게임 모집", "VOICE:🔊 🕹️ ⊹ 놀이터 만들기"
    ],
    "・⎯⎯⎯⎯💰 은행⎯⎯⎯⎯・": [
        "┣ 📖 ⊹ 은행 가이드", "┣ 🏪 ⊹ 가판대", "┣ 🧾 ⊹ 입금 내역", "┣ 💸 ⊹ 송금하기", "┗ 👤 ⊹ 프로필확인"
    ],
    "・⎯⎯⎯⎯🐾 펫⎯⎯⎯⎯・": ["┗ 🦴 ⊹ (미정)"],
    "・⎯⎯⎯⎯🎣 낚시터⎯⎯⎯⎯・": ["┣ 🌊 ⊹ 바다", "┣ 🏞️ ⊹ 강", "┣ 🪣 ⊹ 살림망", "┗ 🐠 ⊹ 물고기 자랑"],
    "・⎯⎯⎯⎯🌾 농장⎯⎯⎯⎯・": ["┗ 🧑‍🌾 ⊹ 밭 만들기"],
    "・⎯⎯⎯⎯⛏️ 광산⎯⎯⎯⎯・": ["┗ 💎 ⊹ (미정)"],
    "・⎯⎯⎯⎯🔥 대장간⎯⎯⎯⎯・": ["┗ ⚔️ ⊹ (미정)"],
    "・⎯⎯⎯⎯⚗️ 가마솥⎯⎯⎯⎯・": ["┗ 🧪 ⊹ (미정)"],
    "・⎯⎯⎯⎯🔒 로그⎯⎯⎯⎯・": [
        "┣ ⌨️ ⊹ 채팅로그", "┣ 🔊 ⊹ 음성로그", "┣ 👤 ⊹ 멤버로그", "┣ ⚙️ ⊹ 서버로그", "┗ #️⃣ ⊹ 채널로그"
    ]
}

ROLE_STRUCTURE = {
    "💎 관리팀": [
        {"name": "촌장", "color": 0xFFD700}, {"name": "부촌장", "color": 0xC0C0C0}, {"name": "직원", "color": 0xB2B2B2},
        {"name": "경찰관", "color": 0x3498DB}, {"name": "축제 담당", "color": 0xE91E63}, {"name": "홍보 담당", "color": 0x2ECC71},
        {"name": "마을 디자이너", "color": 0x9B59B6}, {"name": "서기", "color": 0x71368A}, {"name": "도우미", "color": 0x1ABC9C},
    ],
    "✨ 특별 역할": [{"name": "후원자", "color": 0xF47FFF}],
    "📈 주민 등급": [
        {"name": "장로", "color": 0x99AAB5}, {"name": "베테랑 주민", "color": 0x607D8B}, {"name": "단골 주민", "color": 0x7289DA},
        {"name": "새내기 주민", "color": 0x979C9F}, {"name": "주민", "color": 0x22A669}, {"name": "여행객", "color": 0x83909F},
    ],
    "🎣 직업 역할": [
        {"name": "강태공", "color": 0x206694}, {"name": "대농", "color": 0x4E2C2C},
        {"name": "낚시꾼", "color": 0xADD8E6}, {"name": "농부", "color": 0x964B00},
    ],
    "🎨 선택 역할": [
        {"name": "음성채팅"}, {"name": "친구찾기"}, {"name": "Disboard"}, {"name": "Up"},
        {"name": "마인크래프트"}, {"name": "발로란트"}, {"name": "오버워치"}, {"name": "리그 오브 레전드"},
        {"name": "마작"}, {"name": "어몽어스"}, {"name": "몬스터 헌터"}, {"name": "원신"},
        {"name": "에이펙스 레전드"}, {"name": "구스구스덕"}, {"name": "Gartic Phone"},
        {"name": "스팀"}, {"name": "스마트폰"}, {"name": "콘솔"},
        {"name": "남성"}, {"name": "여성"}, {"name": "비공개"},
        {"name": "00년대생"}, {"name": "90년대생"}, {"name": "80년대생"}, {"name": "70년대생"},
    ],
    "⚙️ 시스템 역할": [
        {"name": "숲의 요정", "color": 0x2ECC71},
        {"name": "경고 1회", "color": 0xFEE75C}, {"name": "경고 2회", "color": 0xE67E22},
        {"name": "경고 3회", "color": 0xED4245}, {"name": "경고 4회", "color": 0x992D22},
        {"name": "이벤트 우선권"}, {"name": "경고 1회 차감권"}, {"name": "개인 방 열쇠"},
    ]
}

class InitializerConfirmation(ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=60)
        self.value = None
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("명령어를 실행한 유저만 사용할 수 있습니다.", ephemeral=True)
            return False
        return True

    @ui.button(label="실행", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        for child in self.children: child.disabled = True
        self.value = True
        await interaction.response.edit_message(content="⏳ 서버 구조 초기화를 시작합니다... (채널과 역할 개수에 따라 최대 몇 분이 소요될 수 있습니다.)", view=self)
        self.stop()

    @ui.button(label="취소", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        for child in self.children: child.disabled = True
        self.value = False
        await interaction.response.edit_message(content="작업이 취소되었습니다.", view=self)
        self.stop()

async def is_admin(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member): return False
    admin_role_ids = {get_id(key) for key in ADMIN_ROLE_KEYS if get_id(key)}
    user_role_ids = {role.id for role in interaction.user.roles}
    if not user_role_ids.intersection(admin_role_ids):
        if interaction.user.id == interaction.guild.owner_id: return True
        raise app_commands.CheckFailure("이 명령어를 실행할 관리자 권한이 없습니다.")
    return True

class TemplateEditModal(ui.Modal, title="임베드 템플릿 편집"):
    title_input = ui.TextInput(label="제목", placeholder="임베드 제목을 입력하세요.", required=False, max_length=256)
    description_input = ui.TextInput(label="설명", placeholder="임베드 설명을 입력하세요.", style=discord.TextStyle.paragraph, required=False, max_length=4000)
    color_input = ui.TextInput(label="색상 (16진수 코드)", placeholder="예: #5865F2 (비워두면 기본 색상)", required=False, max_length=7)
    image_url_input = ui.TextInput(label="이미지 URL", placeholder="임베드에 표시할 이미지 URL을 입력하세요.", required=False)
    thumbnail_url_input = ui.TextInput(label="썸네일 URL", placeholder="오른쪽 상단에 표시할 썸네일 이미지 URL을 입력하세요.", required=False)

    def __init__(self, existing_embed: discord.Embed):
        super().__init__()
        self.embed: Optional[discord.Embed] = None
        self.title_input.default = existing_embed.title
        self.description_input.default = existing_embed.description
        if existing_embed.color: self.color_input.default = str(existing_embed.color)
        if existing_embed.image and existing_embed.image.url: self.image_url_input.default = existing_embed.image.url
        if existing_embed.thumbnail and existing_embed.thumbnail.url: self.thumbnail_url_input.default = existing_embed.thumbnail.url

    async def on_submit(self, interaction: discord.Interaction):
        if not self.title_input.value and not self.description_input.value and not self.image_url_input.value:
            return await interaction.response.send_message("❌ 제목, 설명, 이미지 URL 중 하나는 반드시 입력해야 합니다.", ephemeral=True)
        try:
            color = discord.Color.default()
            if self.color_input.value: color = discord.Color(int(self.color_input.value.replace("#", ""), 16))
            embed = discord.Embed(title=self.title_input.value or None, description=self.description_input.value or None, color=color)
            if self.image_url_input.value: embed.set_image(url=self.image_url_input.value)
            if self.thumbnail_url_input.value: embed.set_thumbnail(url=self.thumbnail_url_input.value)
            self.embed = embed
            await interaction.response.defer(ephemeral=True)
        except Exception:
            await interaction.response.send_message("❌ 임베드를 만드는 중 오류가 발생했습니다.", ephemeral=True)

class EmbedTemplateSelectView(ui.View):
    def __init__(self, all_embeds: List[Dict[str, Any]]):
        super().__init__(timeout=300)
        self.all_embeds = {e['embed_key']: e['embed_data'] for e in all_embeds}
        options = [discord.SelectOption(label=key, description=data.get('title', '제목 없음')[:100]) for key, data in self.all_embeds.items()]
        for i in range(0, len(options), 25):
            select = ui.Select(placeholder=f"편집할 임베드 템플릿을 선택하세요... ({i//25 + 1})", options=options[i:i+25])
            select.callback = self.select_callback
            self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        embed_key = interaction.data['values'][0]
        embed_data = self.all_embeds.get(embed_key)
        if not embed_data: return await interaction.response.send_message("❌ 템플릿을 찾을 수 없습니다.", ephemeral=True)
        modal = TemplateEditModal(discord.Embed.from_dict(embed_data))
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.embed:
            await save_embed_to_db(embed_key, modal.embed.to_dict())
            for item in self.children: item.disabled = True
            await interaction.edit_original_response(view=self)
            await interaction.followup.send(f"✅ 임베드 템플릿 `{embed_key}`가 성공적으로 업데이트되었습니다.\n`/admin setup`으로 관련 패널을 재설치하면 변경사항이 적용됩니다.", embed=modal.embed, ephemeral=True)

class ServerSystem(commands.Cog):
    admin_group = app_commands.Group(name="admin", description="서버 관리용 명령어입니다.", default_permissions=discord.Permissions(manage_guild=True))

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("System (통합 관리 명령어) Cog가 성공적으로 초기화되었습니다.")

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure): await interaction.response.send_message(f"❌ {error}", ephemeral=True)
        elif isinstance(error, app_commands.MissingPermissions): await interaction.response.send_message(f"❌ 이 명령어를 사용하려면 다음 권한이 필요합니다: `{', '.join(error.missing_permissions)}`", ephemeral=True)
        else:
            logger.error(f"'{interaction.command.qualified_name}' 명령어 처리 중 오류 발생: {error}", exc_info=True)
            if not interaction.response.is_done(): await interaction.response.send_message("❌ 명령어를 처리하는 중 예기치 않은 오류가 발생했습니다.", ephemeral=True)
            else: await interaction.followup.send("❌ 명령어를 처리하는 중 예기치 않은 오류가 발생했습니다.", ephemeral=True)

    async def setup_action_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        choices = []
        for key, name in ADMIN_ACTION_MAP.items():
            if current.lower() in name.lower(): choices.append(app_commands.Choice(name=name, value=key))
        for key, info in SETUP_COMMAND_MAP.items():
            choice_name = f"[채널] {info.get('friendly_name', key)} 설정"
            if current.lower() in choice_name.lower(): choices.append(app_commands.Choice(name=choice_name, value=f"channel_setup:{key}"))
        role_setup_actions = {"role_setup:bump_reminder_role_id": "[알림] Disboard BUMP 알림 역할 설정", "role_setup:dissoku_reminder_role_id": "[알림] Dissoku UP 알림 역할 설정"}
        for key, name in role_setup_actions.items():
            if current.lower() in name.lower(): choices.append(app_commands.Choice(name=name, value=key))
        return sorted(choices, key=lambda c: c.name)[:25]

    @admin_group.command(name="setup", description="봇의 모든 설정을 관리합니다.")
    @app_commands.describe(action="실행할 작업을 선택하세요.", channel="[채널/통계] 작업에 필요한 채널을 선택하세요.", role="[역할/통계] 작업에 필요한 역할을 선택하세요.", user="[코인/XP/레벨] 대상을 지정하세요.", amount="[코인/XP] 지급 또는 차감할 수량을 입력하세요.", level="[레벨] 설정할 레벨을 입력하세요.", stat_type="[통계] 표시할 통계 유형을 선택하세요.", template="[통계] 채널 이름 형식을 지정하세요. (예: 👤 유저: {count}명)")
    @app_commands.autocomplete(action=setup_action_autocomplete)
    @app_commands.choices(stat_type=[app_commands.Choice(name="[설정] 전체 멤버 수 (봇 포함)", value="total"), app_commands.Choice(name="[설정] 유저 수 (봇 제외)", value="humans"), app_commands.Choice(name="[설정] 봇 수", value="bots"), app_commands.Choice(name="[설정] 서버 부스트 수", value="boosters"), app_commands.Choice(name="[설정] 특정 역할 멤버 수", value="role"), app_commands.Choice(name="[삭제] 이 채널의 통계 설정 삭제", value="remove")])
    @app_commands.check(is_admin)
    async def setup(self, interaction: discord.Interaction, action: str, channel: Optional[discord.TextChannel | discord.VoiceChannel | discord.ForumChannel] = None, role: Optional[discord.Role] = None, user: Optional[discord.Member] = None, amount: Optional[app_commands.Range[int, 1, None]] = None, level: Optional[app_commands.Range[int, 1, None]] = None, stat_type: Optional[str] = None, template: Optional[str] = None):
        # ... (기존 setup 명령어 코드는 생략) ...
        pass

    async def log_coin_admin_action(self, admin: discord.Member, target: discord.Member, amount: int, action: str):
        # ... (기존 log_coin_admin_action 코드 생략) ...
        pass

    # --- [일회용 서버 초기화 명령어] ---
    async def perform_server_initialization(self, interaction: discord.Interaction):
        guild = interaction.guild
        results = {
            "created_roles": [], "existing_roles": [], "failed_roles": [],
            "created_categories": [], "existing_categories": [],
            "created_channels": [], "existing_channels": [], "failed_channels": []
        }

        existing_role_names = {r.name for r in guild.roles}
        for category, roles in ROLE_STRUCTURE.items():
            for role_info in roles:
                role_name = role_info["name"]
                if role_name in existing_role_names:
                    results["existing_roles"].append(role_name)
                    continue
                try:
                    color = role_info.get("color", discord.Color.default())
                    await guild.create_role(name=role_name, color=discord.Color(color), reason="서버 초기화")
                    results["created_roles"].append(role_name)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    results["failed_roles"].append(f"{role_name} ({e})")

        existing_categories = {c.name: c for c in guild.categories}
        for category_name, channel_list in SERVER_STRUCTURE.items():
            target_category = existing_categories.get(category_name)
            if not target_category:
                try:
                    target_category = await guild.create_category(category_name, reason="서버 초기화")
                    results["created_categories"].append(category_name)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    results["failed_channels"].append(f"카테고리 '{category_name}' 생성 실패 ({e})")
                    continue
            else:
                results["existing_categories"].append(category_name)

            existing_channels_in_category = {c.name for c in target_category.channels}
            for channel_name in channel_list:
                is_voice = channel_name.startswith("VOICE:")
                if is_voice: channel_name = channel_name.replace("VOICE:", "", 1)
                
                if channel_name in existing_channels_in_category:
                    results["existing_channels"].append(channel_name)
                    continue
                
                try:
                    if is_voice: await target_category.create_voice_channel(name=channel_name, reason="서버 초기화")
                    else: await target_category.create_text_channel(name=channel_name, reason="서버 초기화")
                    results["created_channels"].append(channel_name)
                    await asyncio.sleep(0.5)
                except Exception as e:
                    results["failed_channels"].append(f"채널 '{channel_name}' 생성 실패 ({e})")
        
        embed = discord.Embed(title="✅ 서버 구조 초기화 완료", description="아래는 작업 결과입니다.", color=0x2ECC71)
        
        def add_results_to_embed(field_name: str, items: List[str]):
            if not items: return
            content = "\n".join(f"- {item}" for item in items)
            chunks = [content[i:i+1020] for i in range(0, len(content), 1020)]
            for i, chunk in enumerate(chunks):
                name = f"{field_name} ({i+1})" if len(chunks) > 1 else field_name
                embed.add_field(name=name, value=f"```{chunk}```", inline=False)

        add_results_to_embed("✅ 생성된 역할", results["created_roles"])
        add_results_to_embed("ℹ️ 이미 있던 역할", results["existing_roles"])
        add_results_to_embed("✅ 생성된 카테고리", results["created_categories"])
        add_results_to_embed("✅ 생성된 채널", results["created_channels"])
        add_results_to_embed("ℹ️ 이미 있던 채널", results["existing_channels"])
        
        if results["failed_roles"] or results["failed_channels"]:
            embed.color = 0xED4245
            add_results_to_embed("❌ 실패한 역할 생성", results["failed_roles"])
            add_results_to_embed("❌ 실패한 채널/카테고리 생성", results["failed_channels"])
            
        await interaction.edit_original_response(content=None, embed=embed, view=None)

    @admin_group.command(name="initialize_server", description="[⚠️ 위험] 서버의 모든 역할과 채널을 설정에 맞게 생성합니다.")
    @app_commands.check(is_admin)
    async def initialize_server(self, interaction: discord.Interaction):
        view = InitializerConfirmation(interaction.user.id)
        await interaction.response.send_message(
            "**⚠️ 경고: 이 명령어는 서버의 채널과 역할을 대량으로 생성합니다.**\n"
            "기존에 같은 이름의 채널/역할이 있으면 건너뛰지만, 예기치 않은 변경이 발생할 수 있습니다.\n"
            "**반드시 서버 초기 설정 시에만 한 번 사용하세요.**\n\n"
            "정말로 실행하시겠습니까?",
            view=view, ephemeral=True
        )
        await view.wait()

        if view.value is True:
            await self.perform_server_initialization(interaction)
        else:
            await interaction.edit_original_response(content="작업이 취소되었습니다.", view=None)
            
    # --- [새로운 복구용 명령어] ---
    @admin_group.command(name="fix_missing_roles", description="[복구용] 설정 파일 기준으로 누락된 역할을 모두 생성합니다.")
    @app_commands.check(is_admin)
    async def fix_missing_roles(self, interaction: discord.Interaction):
        """설정 파일(ROLE_STRUCTURE)을 기준으로 서버에 없는 역할만 안전하게 생성합니다."""
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        
        results = {"created": [], "existing": [], "failed": []}
        existing_role_names = {r.name for r in guild.roles}

        for category, roles in ROLE_STRUCTURE.items():
            for role_info in roles:
                role_name = role_info["name"]
                if role_name in existing_role_names:
                    results["existing"].append(role_name)
                    continue
                try:
                    color = role_info.get("color", discord.Color.default())
                    await guild.create_role(name=role_name, color=discord.Color(color), reason="누락된 역할 복구")
                    results["created"].append(role_name)
                    await asyncio.sleep(0.5)  # Discord API Rate Limit 방지
                except Exception as e:
                    results["failed"].append(f"{role_name} ({e})")

        embed = discord.Embed(title="✅ 누락된 역할 복구 완료", description="설정 파일을 기준으로 누락된 역할 생성을 시도했습니다.", color=0x2ECC71)
        
        if results["created"]:
            embed.add_field(name="✅ 새로 생성된 역할", value="```\n- " + "\n- ".join(results["created"]) + "\n```", inline=False)
        if results["existing"]:
            embed.add_field(name="ℹ️ 이미 존재하는 역할 (건너뜀)", value="```\n- " + "\n- ".join(results["existing"]) + "\n```", inline=False)
        if results["failed"]:
            embed.color = 0xED4245
            embed.add_field(name="❌ 생성 실패한 역할", value="```\n- " + "\n- ".join(results["failed"]) + "\n```", inline=False)
        
        if not results["created"] and not results["failed"]:
            embed.description = "모든 역할이 이미 존재하여 새로 생성된 역할이 없습니다."

        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))
