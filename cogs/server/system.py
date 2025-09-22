# bot-management/cogs/server/system.py

import discord
from discord.ext import commands
from discord import app_commands, ui
import logging
from typing import Optional, List, Dict, Any
# ▼▼▼ 모든 datetime 관련 import는 여기 한 곳에서만 이루어집니다. ▼▼▼
from datetime import datetime, timezone, timedelta, date
import asyncio
import time
import json

from utils.database import (
    get_config, save_id_to_db, save_config_to_db, get_id,
    get_all_stats_channels, add_stats_channel, remove_stats_channel,
    _channel_id_cache,
    supabase,
    get_all_embeds, get_embed_from_db, save_embed_to_db,
    delete_config_from_db
)
from utils.helpers import calculate_xp_for_level
from utils.ui_defaults import (
    UI_ROLE_KEY_MAP, SETUP_COMMAND_MAP, ADMIN_ROLE_KEYS, 
    ADMIN_ACTION_MAP, UI_STRINGS, JOB_ADVANCEMENT_DATA, PROFILE_RANK_ROLES,
    USABLE_ITEMS, WARNING_THRESHOLDS, JOB_SYSTEM_CONFIG
)

logger = logging.getLogger(__name__)
logger.info("### DIAGNOSTIC LOG: system.py v4.0 (scope fix) LOADED ###")

async def is_admin(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member): return False
    admin_role_ids = {get_id(key) for key in ADMIN_ROLE_KEYS if get_id(key)}
    user_role_ids = {role.id for role in interaction.user.roles}
    if not user_role_ids.intersection(admin_role_ids):
        if interaction.user.id == interaction.guild.owner_id: return True
        raise app_commands.CheckFailure("이 명령어를 실행할 관리자 권한이 없습니다.")
    return True
# ... (TemplateEditModal, EmbedTemplateSelectView 클래스는 이전과 동일하므로 생략) ...
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
    # ... (생략) ...
    
    # setup 함수만 수정된 내용으로 교체
    @admin_group.command(name="setup", description="봇의 모든 설정을 관리합니다.")
    @app_commands.describe(action="실행할 작업을 선택하세요.", channel="[채널/통계] 작업에 필요한 채널을 선택하세요.", role="[역할/통계] 작업에 필요한 역할을 선택하세요.", user="[코인/XP/레벨/펫] 대상을 지정하세요.", amount="[코인/XP] 지급 또는 차감할 수량을 입력하세요.", level="[레벨] 설정할 레벨을 입력하세요.", stat_type="[통계] 표시할 통계 유형을 선택하세요.", template="[통계] 채널 이름 형식을 지정하세요. (예: 👤 유저: {count}명)")
    @app_commands.autocomplete(action=setup_action_autocomplete)
    @app_commands.choices(stat_type=[app_commands.Choice(name="[설정] 전체 멤버 수 (봇 포함)", value="total"), app_commands.Choice(name="[설정] 유저 수 (봇 제외)", value="humans"), app_commands.Choice(name="[설정] 봇 수", value="bots"), app_commands.Choice(name="[설정] 서버 부스트 수", value="boosters"), app_commands.Choice(name="[설정] 특정 역할 멤버 수", value="role"), app_commands.Choice(name="[삭제] 이 채널의 통계 설정 삭제", value="remove")])
    @app_commands.check(is_admin)
    async def setup(self, interaction: discord.Interaction, action: str, channel: Optional[discord.TextChannel | discord.VoiceChannel | discord.ForumChannel] = None, role: Optional[discord.Role] = None, user: Optional[discord.Member] = None, amount: Optional[app_commands.Range[int, 1, None]] = None, level: Optional[app_commands.Range[int, 1, None]] = None, stat_type: Optional[str] = None, template: Optional[str] = None):
        await interaction.response.defer(ephemeral=True)
        
        logger.info(f"[Admin Command] '{interaction.user}' (ID: {interaction.user.id})님이 'setup' 명령어를 실행했습니다. (action: {action})")

        # ... (생략된 다른 action들) ...
        
        if action == "farm_next_day":
            try:
                # ▼▼▼ [핵심 수정] 함수 내 import 제거 ▼▼▼
                current_date_str = get_config("farm_current_date")
                
                if current_date_str:
                    current_date = date.fromisoformat(current_date_str)
                else:
                    current_date = datetime.now(timezone(timedelta(hours=9))).date()

                next_day = current_date + timedelta(days=1)
                await save_config_to_db("farm_current_date", next_day.isoformat())

                await save_config_to_db("config_reload_request", time.time())
                await save_config_to_db("manual_update_request", time.time())
                
                await interaction.followup.send(
                    f"✅ 농장 시간을 다음 날로 변경했습니다.\n"
                    f"**현재 농장 기준일: {next_day.strftime('%Y-%m-%d')}**\n"
                    f"이 날짜를 기준으로 작물 상태 업데이트를 요청했습니다."
                )
            except Exception as e:
                logger.error(f"농장 시간 넘기기 중 오류: {e}", exc_info=True)
                await interaction.followup.send("❌ 농장 시간을 변경하는 중 오류가 발생했습니다.")
        
        # ... (생략된 다른 action들) ...
        else:
            await interaction.followup.send("❌ 알 수 없는 작업입니다. 목록에서 올바른 작업을 선택해주세요.", ephemeral=True)
            
async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))```

이 코드를 적용하고, **GitHub에 push한 뒤 Railway에서 새 버전이 성공적으로 배포되었는지 꼭 확인**하신 후에 다시 한번 명령어를 실행해보시면 이번에는 반드시 해결될 것입니다.
