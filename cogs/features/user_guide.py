# cogs/features/user_guide.py

import discord
from discord import ui
from discord.ext import commands
import logging
from typing import Optional, Dict, List, Any
import asyncio
from datetime import datetime
import re

from utils.database import get_id, save_panel_id, get_panel_id, get_embed_from_db, get_panel_components_from_db, get_config
from utils.helpers import format_embed_from_db, has_required_roles
from utils.ui_defaults import AGE_ROLE_MAPPING_BY_YEAR

logger = logging.getLogger(__name__)

# --- Forward declaration ---
class GuideThreadView:
    pass

class GuideApprovalView(ui.View):
    def __init__(self, cog: 'UserGuide', target_user_id: int, submitted_data: dict):
        super().__init__(timeout=None)
        self.cog = cog
        self.target_user_id = target_user_id
        self.submitted_data = submitted_data

    async def _check_permission(self, interaction: discord.Interaction) -> bool:
        required_keys = [
            "role_staff_team_info", "role_staff_team_newbie",
            "role_staff_leader_info", "role_staff_leader_newbie",
            "role_staff_deputy_manager", "role_staff_general_manager",
            "role_staff_deputy_chief", "role_staff_village_chief"
        ]
        error_message = "❌ 안내팀 또는 뉴비 관리팀 스태프만 수락할 수 있습니다."
        return await has_required_roles(interaction, required_keys, error_message)

    # ▼▼▼ [신규] 공개 자기소개 메시지를 보내는 별도 함수 ▼▼▼
    async def _send_public_introduction(self, approver: discord.Member, member: discord.Member):
        try:
            channel_id = self.cog.public_intro_channel_id
            if not channel_id:
                logger.warning("공개 자기소개 채널이 설정되지 않아 메시지를 보낼 수 없습니다.")
                return

            channel = self.cog.bot.get_channel(channel_id)
            if not channel:
                logger.warning(f"공개 자기소개 채널(ID: {channel_id})을 찾을 수 없습니다.")
                return
            
            embed_data = await get_embed_from_db("guide_public_introduction")
            if not embed_data:
                logger.warning("DB에서 'guide_public_introduction' 임베드 템플릿을 찾을 수 없습니다.")
                return

            embed = format_embed_from_db(
                embed_data,
                member_mention=member.mention,
                submitted_name=self.submitted_data['name'],
                submitted_birth_year=str(self.submitted_data['birth_year']),
                submitted_gender=self.submitted_data['gender'],
                submitted_join_path=self.submitted_data['join_path'],
                approver_mention=approver.mention
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            
            await channel.send(content=member.mention, embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
        except Exception as e:
            logger.error(f"공개 자기소개 메시지 전송 중 오류 발생: {e}", exc_info=True)
    # ▲▲▲ [신규 함수 완료] ▲▲▲

    @ui.button(label="수락", style=discord.ButtonStyle.success, emoji="✅", custom_id="guide_approve_button")
    async def approve(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check_permission(interaction):
            return

        await interaction.response.defer(ephemeral=True)
        member = interaction.guild.get_member(self.target_user_id)
        
        if not member:
            await interaction.followup.send("❌ 대상 유저를 찾을 수 없습니다. 서버를 나간 것 같습니다.", ephemeral=True)
            return

        # 1. 역할 부여
        roles_to_add = []
        gender_text = self.submitted_data['gender'].strip().lower()
        if any(k in gender_text for k in ['남자', '남성', '남']):
            if (rid := get_id("role_info_male")) and (r := member.guild.get_role(rid)): roles_to_add.append(r)
        elif any(k in gender_text for k in ['여자', '여성', '여']):
            if (rid := get_id("role_info_female")) and (r := member.guild.get_role(rid)): roles_to_add.append(r)
        
        birth_year = self.submitted_data['birth_year']
        year_mapping = next((item for item in AGE_ROLE_MAPPING_BY_YEAR if item["year"] == birth_year), None)
        if year_mapping:
            if (rid := get_id(year_mapping['key'])) and (r := member.guild.get_role(rid)): roles_to_add.append(r)

        if (guest_rid := get_id("role_guest")) and (guest_role := member.guild.get_role(guest_rid)):
            if guest_role in member.roles: await member.remove_roles(guest_role, reason="안내 가이드 승인")
        
        if (rookie_rid := get_id("role_resident_rookie")) and (rookie_role := member.guild.get_role(rookie_rid)):
            roles_to_add.append(rookie_role)

        if roles_to_add:
            await member.add_roles(*roles_to_add, reason="안내 가이드 승인")

        # 2. 닉네임 변경
        try:
            prefix_cog = self.cog.bot.get_cog("PrefixManager")
            if prefix_cog:
                await prefix_cog.apply_prefix(member, base_name=self.submitted_data['name'])
            else:
                await member.edit(nick=self.submitted_data['name'], reason="안내 가이드 승인 (PrefixManager 없음)")
        except Exception as e:
            logger.error(f"가이드 승인 중 닉네임 변경 실패: {e}", exc_info=True)

        # ▼▼▼ [핵심 추가] 공개 자기소개 보내기 함수 호출 ▼▼▼
        await self._send_public_introduction(interaction.user, member)
        # ▲▲▲ [추가 완료] ▲▲▲

        # 3. 피드백
        button.disabled = True
        button.label = "승인 완료"
        
        original_embed = interaction.message.embeds[0]
        original_embed.color = discord.Color.green()
        original_embed.set_footer(text=f"✅ {interaction.user.display_name} 님에 의해 승인됨")
        
        await interaction.message.edit(embed=original_embed, view=self)
        await interaction.followup.send(f"✅ {member.mention}님의 자기소개를 승인하고, 공개 채널에 소개글을 게시했습니다.", ephemeral=True)
        await interaction.channel.send(f"🎉 {member.mention}님의 자기소개가 승인되었습니다! 이제 서버의 모든 채널을 이용할 수 있습니다.")


class IntroductionFormModal(ui.Modal, title="자기소개서 작성"):
    name = ui.TextInput(label="이름", placeholder="서버에서 사용할 이름을 알려주세요.", required=True, max_length=12)
    birth_year_str = ui.TextInput(label="출생년도 (YYYY)", placeholder="예: 1998, 2005 (4자리로 입력)", required=True, min_length=4, max_length=4)
    gender = ui.TextInput(label="성별", placeholder="성별을 알려주세요.", required=True, max_length=10)
    join_path = ui.TextInput(label="가입 경로", placeholder="어떻게 우리 서버를 알게 되셨나요?", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, cog: 'UserGuide'):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            year = int(self.birth_year_str.value)
            current_year = datetime.now().year
            if not (1950 <= year <= current_year - 13):
                await interaction.followup.send("❌ 유효하지 않은 출생년도입니다. (만 13세 이상)", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("❌ 출생년도는 4자리 숫자로 입력해주세요.", ephemeral=True)
            return

        submitted_data = {
            "name": self.name.value,
            "birth_year": int(self.birth_year_str.value),
            "gender": self.gender.value,
            "join_path": self.join_path.value
        }
        
        approval_embed = discord.Embed(
            title="📝 자기소개서 제출됨",
            description=f"{interaction.user.mention}님이 자기소개서를 제출했습니다.\n아래 내용을 확인 후 `수락` 버튼을 눌러주세요.",
            color=discord.Color.yellow()
        )
        approval_embed.add_field(name="신청 이름", value=self.name.value, inline=True)
        approval_embed.add_field(name="출생년도", value=self.birth_year_str.value, inline=True)
        approval_embed.add_field(name="성별", value=self.gender.value, inline=True)
        approval_embed.add_field(name="가입 경로", value=self.join_path.value, inline=False)
        approval_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar)
        
        approval_view = GuideApprovalView(self.cog, interaction.user.id, submitted_data)
        
        # ▼▼▼ [핵심 수정] 언급할 역할을 "안내해주세요" 역할로 변경 ▼▼▼
        notify_role_id = get_id("role_notify_guide_approval")
        mention_str = f"<@&{notify_role_id}>" if notify_role_id else "스태프 여러분,"
        # ▲▲▲ [수정 완료] ▲▲▲
        
        await interaction.channel.send(
            content=mention_str,
            embed=approval_embed,
            view=approval_view,
            allowed_mentions=discord.AllowedMentions(roles=True)
        )

        await interaction.followup.send("✅ 자기소개서를 제출했습니다. 스태프 확인 후 역할이 지급됩니다.", ephemeral=True)


class UserGuide(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_channel_id: Optional[int] = None
        self.public_intro_channel_id: Optional[int] = None # [추가]
        self.view_instance: Optional[UserGuidePanelView] = None
        self.guide_thread_view_instance: Optional[GuideThreadView] = None
        self.active_guide_threads: Dict[int, int] = {}
        logger.info("UserGuide Cog가 성공적으로 초기화되었습니다.")
        
    async def cog_load(self): 
        await self.load_configs()
        
    async def register_persistent_views(self):
        self.view_instance = UserGuidePanelView(self)
        await self.view_instance.setup_buttons()
        self.bot.add_view(self.view_instance)
        
        self.guide_thread_view_instance = GuideThreadView(self)
        self.bot.add_view(self.guide_thread_view_instance)
        
        self.bot.add_view(GuideApprovalView(self, 0, {}))
        
        logger.info("✅ 신규 유저 안내 시스템의 영구 View 3개가 성공적으로 등록되었습니다.")
        
    async def load_configs(self): 
        self.panel_channel_id = get_id("user_guide_panel_channel_id")
        self.public_intro_channel_id = get_id("introduction_public_channel_id") # [추가]
        logger.info("[UserGuide Cog] DB로부터 설정을 로드했습니다.")
        
    # (나머지 UserGuide Cog의 함수들은 이전과 동일하게 유지)
    # ...
    
async def setup(bot: commands.Bot):
    await bot.add_cog(UserGuide(bot))
