# cogs/moderation/warning_system.py

import discord
from discord import ui
from discord.ext import commands
import logging
from typing import Optional, List, Dict
import asyncio
from datetime import datetime, timezone

from utils.database import get_id, save_panel_id, get_panel_id, get_embed_from_db, get_panel_components_from_db, supabase
from utils.ui_defaults import POLICE_ROLE_KEY, WARNING_THRESHOLDS
# ▼▼▼ [핵심 수정] has_required_roles 함수를 import 합니다. ▼▼▼
from utils.helpers import format_embed_from_db, has_required_roles

logger = logging.getLogger(__name__)

# --- 다른 클래스들은 변경사항이 없으므로 생략합니다 ---
class WarningModal(ui.Modal, title="경고 내용 입력"):
    amount = ui.TextInput(label="경고 횟수", placeholder="부여할 경고 횟수를 숫자로 입력 (예: 1)", required=True, max_length=2)
    reason = ui.TextInput(label="경고 사유", placeholder="경고을 발급하는 이유를 구체적으로 기입해주세요.", style=discord.TextStyle.paragraph, required=True, max_length=500)

    def __init__(self, cog: 'WarningSystem', target_member: discord.Member):
        super().__init__()
        self.cog = cog
        self.target_member = target_member

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            amount_val = int(self.amount.value)
            if amount_val <= 0:
                await interaction.followup.send("❌ 경고 횟수는 1 이상의 자연수를 입력해주세요.", ephemeral=True)
                return
        except (ValueError, TypeError):
            await interaction.followup.send("❌ 경고 횟수는 숫자로 입력해주세요.", ephemeral=True)
            return

        try:
            rpc_params = {
                'p_guild_id': interaction.guild_id,
                'p_user_id': self.target_member.id,
                'p_moderator_id': interaction.user.id,
                'p_reason': self.reason.value,
                'p_amount': amount_val
            }
            response = await supabase.rpc('add_warning_and_get_total', rpc_params).execute()
            new_total = response.data
        except Exception as e:
            logger.error(f"add_warning_and_get_total RPC 호출 실패: {e}", exc_info=True)
            await interaction.followup.send("❌ 경고 처리 중 데이터베이스 오류가 발생했습니다.", ephemeral=True)
            return

        await self.cog.update_warning_roles(self.target_member, new_total)

        await self.cog.send_log_message(
            moderator=interaction.user,
            target=self.target_member,
            reason=self.reason.value,
            amount=amount_val,
            new_total=new_total
        )
        
        try:
            dm_embed = discord.Embed(title=f"🚨 {interaction.guild.name}에서 경고가 부여되었습니다", color=0xED4245)
            dm_embed.add_field(name="사유", value=self.reason.value, inline=False)
            dm_embed.add_field(name="부여된 경고 횟수", value=f"{amount_val}회", inline=True)
            dm_embed.add_field(name="누적 경고 횟수", value=f"{new_total}회", inline=True)
            dm_embed.set_footer(text="궁금한 점이 있다면 문의 티켓을 이용해주세요.")
            await self.target_member.send(embed=dm_embed)
        except discord.Forbidden:
            logger.warning(f"{self.target_member.display_name}님에게 DM을 보낼 수 없어 벌점 알림을 보내지 못했습니다.")
            
        await interaction.followup.send(f"✅ {self.target_member.mention} 님에게 **{amount_val}회** 의 경고를 성공적으로 부여했습니다. (누적: {new_total}회)", ephemeral=True)


class TargetUserSelectView(ui.View):
    def __init__(self, cog: 'WarningSystem'):
        super().__init__(timeout=180)
        self.cog = cog

    @ui.select(cls=ui.UserSelect, placeholder="경고를 부여할 유저를 선택하세요.")
    async def select_user(self, interaction: discord.Interaction, select: ui.UserSelect):
        target_user = select.values[0]
        if target_user.bot:
            await interaction.response.send_message("❌ 봇에게는 경고을 부여할 수 없습니다.", ephemeral=True)
            return
            
        modal = WarningModal(self.cog, target_user)
        await interaction.response.send_modal(modal)
        
        try:
            await interaction.delete_original_response()
        except (discord.NotFound, discord.HTTPException):
            pass

class WarningPanelView(ui.View):
    def __init__(self, cog: 'WarningSystem'):
        super().__init__(timeout=None)
        self.cog = cog
    
    async def setup_buttons(self):
        self.clear_items()
        components = await get_panel_components_from_db("warning")
        if not components: return
        
        button_info = components[0]
        button = ui.Button(
            label=button_info.get('label'),
            style=discord.ButtonStyle.danger,
            emoji=button_info.get('emoji'),
            custom_id=button_info.get('component_key')
        )
        button.callback = self.on_button_click
        self.add_item(button)

    # ▼▼▼ [핵심 수정] 권한 확인 로직을 중앙 함수 호출로 변경 ▼▼▼
    async def on_button_click(self, interaction: discord.Interaction):
        required_keys = [POLICE_ROLE_KEY, "role_staff_village_chief", "role_staff_deputy_chief"]
        error_message = "❌ 이 기능은 `대표`, `부대표`, `포장 관리팀` 역할만 사용할 수 있습니다."
        
        if not await has_required_roles(interaction, required_keys, error_message):
            return

        view = TargetUserSelectView(self.cog)
        await interaction.response.send_message("벌점을 부여할 대상을 선택하세요.", view=view, ephemeral=True)
    # ▲▲▲ [핵심 수정] ▲▲▲

class WarningSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_channel_id: Optional[int] = None
        self.log_channel_id: Optional[int] = None
        self.police_role_id: Optional[int] = None
        self.master_role_id: Optional[int] = None
        self.vice_master_role_id: Optional[int] = None
        self.view_instance: Optional[WarningPanelView] = None
        logger.info("WarningSystem Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        await self.load_configs()
        
    async def register_persistent_views(self):
        self.view_instance = WarningPanelView(self)
        await self.view_instance.setup_buttons()
        self.bot.add_view(self.view_instance)
        logger.info("✅ 벌점 시스템의 영구 View가 성공적으로 등록되었습니다.")
        
    async def load_configs(self):
        self.panel_channel_id = get_id("warning_panel_channel_id")
        self.log_channel_id = get_id("warning_log_channel_id")
        self.police_role_id = get_id(POLICE_ROLE_KEY)
        self.master_role_id = get_id("role_staff_village_chief")
        self.vice_master_role_id = get_id("role_staff_deputy_chief")
        logger.info("[WarningSystem Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")

    async def update_warning_roles(self, member: discord.Member, total_count: int):
        """누적 벌점 횟수에 따라 역할을 업데이트합니다."""
        guild = member.guild
        
        all_warning_role_ids = {get_id(t['role_key']) for t in WARNING_THRESHOLDS if get_id(t['role_key'])}
        current_warning_roles = [role for role in member.roles if role.id in all_warning_role_ids]
        
        target_role_id = None
        for threshold in sorted(WARNING_THRESHOLDS, key=lambda x: x['count'], reverse=True):
            if total_count >= threshold['count']:
                target_role_id = get_id(threshold['role_key'])
                break
        
        target_role = guild.get_role(target_role_id) if target_role_id else None

        try:
            roles_to_add = []
            roles_to_remove = []

            if target_role and target_role not in current_warning_roles:
                roles_to_add.append(target_role)

            for role in current_warning_roles:
                if not target_role or role.id != target_role.id:
                    roles_to_remove.append(role)
            
            if roles_to_add:
                await member.add_roles(*roles_to_add, reason=f"누적 벌점 {total_count}회 달성")
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason=f"벌점 역할 업데이트")
                
        except discord.Forbidden:
            logger.error(f"벌점 역할 업데이트 실패: {member.display_name}님의 역할을 변경할 권한이 없습니다.")
        except Exception as e:
            logger.error(f"벌점 역할 업데이트 중 오류: {e}", exc_info=True)

    async def send_log_message(self, moderator: discord.Member, target: discord.Member, reason: str, amount: int, new_total: int):
        if not self.log_channel_id: return
        log_channel = self.bot.get_channel(self.log_channel_id)
        if not log_channel: return
        
        embed_data = await get_embed_from_db("log_warning")
        if not embed_data: return
        
        embed = format_embed_from_db(embed_data)
        embed.set_author(name=f"{moderator.display_name} → {target.display_name}", icon_url=moderator.display_avatar.url)
        embed.add_field(name="대상자", value=f"{target.mention} (`{target.id}`)", inline=False)
        embed.add_field(name="담당자", value=f"{moderator.mention} (`{moderator.id}`)", inline=False)
        embed.add_field(name="사유", value=reason, inline=False)
        embed.add_field(name="부여 횟수", value=f"`{amount}`회", inline=True)
        embed.add_field(name="누적 횟수", value=f"`{new_total}`회", inline=True)
        embed.timestamp = datetime.now(timezone.utc)
        
        await log_channel.send(
            content=f"||{target.mention}||", 
            embed=embed, 
            allowed_mentions=discord.AllowedMentions(users=True)
        )
        
    async def regenerate_panel(self, channel: discord.TextChannel, panel_key: str = "panel_warning") -> bool:
        base_panel_key = panel_key.replace("panel_", "") # "warning"
        embed_key = panel_key # "panel_warning"

        if not channel:
            logger.warning(f"경고 패널 채널을 찾을 수 없어 재생성할 수 없습니다.")
            return False

        try:
            panel_info = get_panel_id(base_panel_key)
            if panel_info and (old_id := panel_info.get('message_id')):
                try:
                    old_message = await channel.fetch_message(old_id)
                    await old_message.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass
            
            embed_data = await get_embed_from_db(embed_key)
            if not embed_data:
                logger.error(f"DB에서 '{embed_key}' 임베드를 찾을 수 없어 패널을 생성할 수 없습니다.")
                return False
                
            embed = discord.Embed.from_dict(embed_data)
            
            if self.view_instance is None:
                self.view_instance = WarningPanelView(self)
            await self.view_instance.setup_buttons()
            
            new_message = await channel.send(embed=embed, view=self.view_instance)
            await save_panel_id(base_panel_key, new_message.id, channel.id)
            logger.info(f"✅ 경고 패널을 성공적으로 새로 생성했습니다. (채널: #{channel.name})")
            return True
        except Exception as e:
            logger.error(f"❌ {panel_key} 패널 재설치 중 오류 발생: {e}", exc_info=True)
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(WarningSystem(bot))
