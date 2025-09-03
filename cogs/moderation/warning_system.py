# cogs/moderation/warning_system.py
import discord
from discord import ui
from discord.ext import commands
import logging
from typing import Optional, List, Dict
import asyncio
from datetime import datetime, timezone

from utils.database import get_id, save_panel_id, get_panel_id, get_embed_from_db, get_panel_components_from_db, add_warning, get_total_warning_count
from utils.ui_defaults import POLICE_ROLE_KEY, WARNING_THRESHOLDS
from utils.helpers import format_embed_from_db

logger = logging.getLogger(__name__)

class WarningModal(ui.Modal, title="경고 내용 입력"):
    amount = ui.TextInput(label="경고 횟수", placeholder="부여할 경고 횟수를 숫자로 입력 (예: 1)", required=True, max_length=2)
    reason = ui.TextInput(label="경고 사유", placeholder="경고를 발급하는 이유를 구체적으로 기입해주세요.", style=discord.TextStyle.paragraph, required=True, max_length=500)

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

        await add_warning(
            guild_id=interaction.guild_id,
            user_id=self.target_member.id,
            moderator_id=interaction.user.id,
            reason=self.reason.value,
            amount=amount_val
        )

        new_total = await get_total_warning_count(self.target_member.id, interaction.guild_id)
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
            logger.warning(f"{self.target_member.display_name}님에게 DM을 보낼 수 없어 경고 알림을 보내지 못했습니다.")
            
        await interaction.followup.send(f"✅ {self.target_member.mention} 님에게 **{amount_val}회** 의 경고를 성공적으로 부여했습니다. (누적: {new_total}회)", ephemeral=True)


class TargetUserSelectView(ui.View):
    def __init__(self, cog: 'WarningSystem'):
        super().__init__(timeout=180)
        self.cog = cog

    @ui.select(cls=ui.UserSelect, placeholder="경고를 부여할 유저를 선택하세요.")
    async def select_user(self, interaction: discord.Interaction, select: ui.UserSelect):
        target_user = select.values[0]
        if target_user.bot:
            await interaction.response.send_message("❌ 봇에게는 경고를 부여할 수 없습니다.", ephemeral=True)
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

    async def on_button_click(self, interaction: discord.Interaction):
        if not self.cog.police_role_id or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("❌ 권한이 없습니다.", ephemeral=True)
            
        if not any(r.id == self.cog.police_role_id for r in interaction.user.roles):
            police_role = interaction.guild.get_role(self.cog.police_role_id)
            role_name = police_role.name if police_role else "경고 담당"
            return await interaction.response.send_message(f"❌ 이 기능은 `{role_name}` 역할을 가진 스태프만 사용할 수 있습니다.", ephemeral=True)
            
        view = TargetUserSelectView(self.cog)
        await interaction.response.send_message("경고를 부여할 대상을 선택하세요.", view=view, ephemeral=True)


class WarningSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_channel_id: Optional[int] = None
        self.log_channel_id: Optional[int] = None
        self.police_role_id: Optional[int] = None
        self.view_instance: Optional[WarningPanelView] = None
        logger.info("WarningSystem Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        await self.load_configs()
        
    async def register_persistent_views(self):
        self.view_instance = WarningPanelView(self)
        await self.view_instance.setup_buttons()
        self.bot.add_view(self.view_instance)
        logger.info("✅ 경고 시스템의 영구 View가 성공적으로 등록되었습니다.")
        
    async def load_configs(self):
        self.panel_channel_id = get_id("warning_panel_channel_id")
        self.log_channel_id = get_id("warning_log_channel_id")
        self.police_role_id = get_id(POLICE_ROLE_KEY)
        logger.info("[WarningSystem Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")

    async def update_warning_roles(self, member: discord.Member, total_count: int):
        """누적 경고 횟수에 따라 역할을 업데이트합니다."""
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
                await member.add_roles(*roles_to_add, reason=f"누적 경고 {total_count}회 달성")
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason=f"경고 역할 업데이트")
                
        except discord.Forbidden:
            logger.error(f"경고 역할 업데이트 실패: {member.display_name}님의 역할을 변경할 권한이 없습니다.")
        except Exception as e:
            logger.error(f"경고 역할 업데이트 중 오류: {e}", exc_info=True)
            
    async def deduct_warning_points(self, moderator: discord.User, target: discord.Member, amount: int, reason: str) -> bool:
        """아이템 사용 등으로 경고 점수를 차감하고 로그를 남깁니다."""
        try:
            # DB에 음수 값으로 경고 기록을 추가하여 차감을 구현합니다.
            await add_warning(
                guild_id=target.guild.id,
                user_id=target.id,
                moderator_id=moderator.id,
                reason=reason,
                amount=amount  # amount는 음수 값 (예: -1)이어야 합니다.
            )

            # 새로운 누적 경고 횟수를 가져옵니다.
            new_total = await get_total_warning_count(target.id, target.guild.id)
            # 누적 횟수에 따라 역할을 업데이트합니다.
            await self.update_warning_roles(target, new_total)

            # 로그 채널에 메시지를 보냅니다.
            await self.send_log_message(
                moderator=moderator,
                target=target,
                reason=reason,
                amount=amount,
                new_total=new_total
            )
            return True
        except Exception as e:
            logger.error(f"경고 점수 차감 중 오류 발생 (대상: {target.id}): {e}", exc_info=True)
            return False
    
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
        
        await log_channel.send(embed=embed)
        
    # [✅✅✅ 핵심 수정 ✅✅✅]
    # 함수가 panel_key를 인자로 받도록 변경하고, 내부 로직을 수정합니다.
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
                logger.error("DB에서 'panel_warning' 임베드를 찾을 수 없어 패널을 생성할 수 없습니다.")
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
