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
from utils.helpers import format_embed_from_db, has_required_roles

logger = logging.getLogger(__name__)

class WarningModal(ui.Modal):
    """경고 부여를 위한 Modal"""
    amount = ui.TextInput(label="경고 횟수", placeholder="부여할 경고 횟수를 숫자로 입력 (예: 1)", required=True, max_length=2)
    reason = ui.TextInput(label="경고 사유", placeholder="경고를 발급하는 이유를 구체적으로 기입해주세요.", style=discord.TextStyle.paragraph, required=True, max_length=500)

    def __init__(self, cog: 'WarningSystem', target_member: discord.Member):
        super().__init__(title="경고 내용 입력")
        self.cog = cog
        self.target_member = target_member

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            amount_val = int(self.amount.value)
            if amount_val <= 0:
                return await interaction.followup.send("❌ 경고 횟수는 1 이상의 자연수를 입력해주세요.", ephemeral=True)
        except (ValueError, TypeError):
            return await interaction.followup.send("❌ 경고 횟수는 숫자로 입력해주세요.", ephemeral=True)

        new_total = await self.cog.process_warning(interaction, self.target_member, amount_val, self.reason.value, 'issue')
        if new_total is None: return

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

class WarningDeductModal(ui.Modal):
    """경고 차감을 위한 Modal"""
    amount = ui.TextInput(label="차감할 경고 횟수", placeholder="차감할 경고 횟수를 숫자로 입력 (예: 1)", required=True, max_length=2)
    reason = ui.TextInput(label="차감 사유", placeholder="경고를 차감하는 이유를 구체적으로 기입해주세요.", style=discord.TextStyle.paragraph, required=True, max_length=500)

    def __init__(self, cog: 'WarningSystem', target_member: discord.Member):
        super().__init__(title="경고 차감 내용 입력")
        self.cog = cog
        self.target_member = target_member

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            amount_val = int(self.amount.value)
            if amount_val <= 0:
                return await interaction.followup.send("❌ 차감할 횟수는 1 이상의 자연수를 입력해주세요.", ephemeral=True)
        except (ValueError, TypeError):
            return await interaction.followup.send("❌ 차감할 횟수는 숫자로 입력해주세요.", ephemeral=True)

        new_total = await self.cog.process_warning(interaction, self.target_member, -amount_val, self.reason.value, 'deduct')
        if new_total is None: return

        try:
            dm_embed = discord.Embed(title=f"✅ {interaction.guild.name}에서 경고가 차감되었습니다", color=0x2ECC71)
            dm_embed.add_field(name="사유", value=self.reason.value, inline=False)
            dm_embed.add_field(name="차감된 경고 횟수", value=f"{amount_val}회", inline=True)
            dm_embed.add_field(name="현재 누적 경고", value=f"{new_total}회", inline=True)
            await self.target_member.send(embed=dm_embed)
        except discord.Forbidden:
            pass # 차감은 굳이 DM 실패를 알릴 필요 없음
            
        await interaction.followup.send(f"✅ {self.target_member.mention} 님의 경고를 **{amount_val}회** 성공적으로 차감했습니다. (현재: {new_total}회)", ephemeral=True)

class TargetUserSelectView(ui.View):
    def __init__(self, cog: 'WarningSystem', action_type: str):
        super().__init__(timeout=180)
        self.cog = cog
        self.action_type = action_type # 'issue' 또는 'deduct'

    @ui.select(cls=ui.UserSelect, placeholder="대상을 선택하세요.")
    async def select_user(self, interaction: discord.Interaction, select: ui.UserSelect):
        target_user = select.values[0]
        if target_user.bot:
            return await interaction.response.send_message("❌ 봇은 대상이 될 수 없습니다.", ephemeral=True)
        
        if self.action_type == 'issue':
            modal = WarningModal(self.cog, target_user)
        else: # 'deduct'
            modal = WarningDeductModal(self.cog, target_user)
            
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
        
        button_styles = { "danger": discord.ButtonStyle.danger, "success": discord.ButtonStyle.success }
        
        for comp in sorted(components, key=lambda x: x.get('order_in_row', 0)):
            button = ui.Button(
                label=comp.get('label'),
                style=button_styles.get(comp.get('style'), discord.ButtonStyle.secondary),
                emoji=comp.get('emoji'),
                custom_id=comp.get('component_key')
            )
            button.callback = self.on_button_click
            self.add_item(button)

    async def on_button_click(self, interaction: discord.Interaction):
        required_keys = [POLICE_ROLE_KEY, "role_staff_village_chief", "role_staff_deputy_chief"]
        error_message = "❌ 이 기능은 `대표`, `부대표`, `포장 관리팀` 역할만 사용할 수 있습니다."
        
        if not await has_required_roles(interaction, required_keys, error_message):
            return
            
        action_type = 'issue' if interaction.data['custom_id'] == 'issue_warning_button' else 'deduct'
        view = TargetUserSelectView(self.cog, action_type)
        await interaction.response.send_message(f"벌점을 {'부여' if action_type == 'issue' else '차감'}할 대상을 선택하세요.", view=view, ephemeral=True)

class WarningSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.view_instance: Optional[WarningPanelView] = None
        logger.info("WarningSystem Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        await self.register_persistent_views()
        
    async def register_persistent_views(self):
        self.view_instance = WarningPanelView(self)
        await self.view_instance.setup_buttons()
        self.bot.add_view(self.view_instance)
        logger.info("✅ 벌점 시스템의 영구 View가 성공적으로 등록되었습니다.")
        
    async def process_warning(self, interaction: discord.Interaction, target_member: discord.Member, amount: int, reason: str, action_type: str) -> Optional[int]:
        """경고 부여/차감 공통 로직"""
        try:
            rpc_params = {
                'p_guild_id': interaction.guild_id,
                'p_user_id': target_member.id,
                'p_moderator_id': interaction.user.id,
                'p_reason': reason,
                'p_amount': amount # 차감 시 음수값이 전달됨
            }
            response = await supabase.rpc('add_warning_and_get_total', rpc_params).execute()
            new_total = response.data
        except Exception as e:
            logger.error(f"add_warning_and_get_total RPC 호출 실패: {e}", exc_info=True)
            await interaction.followup.send("❌ 경고 처리 중 데이터베이스 오류가 발생했습니다.", ephemeral=True)
            return None

        await self.update_warning_roles(target_member, new_total)
        await self.send_log_message(interaction.user, target_member, reason, amount, new_total, action_type)
        return new_total

    async def update_warning_roles(self, member: discord.Member, total_count: int):
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
            roles_to_remove = list(current_warning_roles)

            if target_role:
                if target_role in roles_to_remove:
                    roles_to_remove.remove(target_role)
                if target_role not in member.roles:
                    roles_to_add.append(target_role)
            
            if roles_to_add:
                await member.add_roles(*roles_to_add, reason=f"누적 벌점 {total_count}회 도달")
            if roles_to_remove:
                await member.remove_roles(*roles_to_remove, reason=f"벌점 역할 업데이트")
                
        except discord.Forbidden:
            logger.error(f"벌점 역할 업데이트 실패: {member.display_name}님의 역할을 변경할 권한이 없습니다.")
        except Exception as e:
            logger.error(f"벌점 역할 업데이트 중 오류: {e}", exc_info=True)

    async def send_log_message(self, moderator: discord.Member, target: discord.Member, reason: str, amount: int, new_total: int, action_type: str):
        log_channel_id = get_id("warning_log_channel_id")
        if not log_channel_id: return
        log_channel = self.bot.get_channel(log_channel_id)
        if not log_channel: return
        
        embed_key = "log_warning" if action_type == 'issue' else "log_warning_deduct"
        embed_data = await get_embed_from_db(embed_key)
        if not embed_data: return
        
        embed = format_embed_from_db(embed_data)
        embed.set_author(name=f"{moderator.display_name} → {target.display_name}", icon_url=moderator.display_avatar.url)
        embed.add_field(name="대상자", value=f"{target.mention} (`{target.id}`)", inline=False)
        embed.add_field(name="담당자", value=f"{moderator.mention} (`{moderator.id}`)", inline=False)
        embed.add_field(name="사유", value=reason, inline=False)
        
        amount_field_name = "부여 횟수" if action_type == 'issue' else "차감 횟수"
        embed.add_field(name=amount_field_name, value=f"`{abs(amount)}`회", inline=True)
        embed.add_field(name="누적 횟수", value=f"`{new_total}`회", inline=True)
        embed.timestamp = datetime.now(timezone.utc)
        
        await log_channel.send(content=f"||{target.mention}||", embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
        
    async def regenerate_panel(self, channel: discord.TextChannel, panel_key: str = "panel_warning") -> bool:
        base_panel_key = "warning"
        embed_key = "panel_warning"

        if not channel:
            return False

        try:
            panel_info = get_panel_id(base_panel_key)
            if panel_info and (old_id := panel_info.get('message_id')):
                try:
                    old_message = await channel.fetch_message(old_id)
                    await old_message.delete()
                except (discord.NotFound, discord.Forbidden): pass
            
            embed_data = await get_embed_from_db(embed_key)
            if not embed_data:
                logger.error(f"DB에서 '{embed_key}' 임베드를 찾을 수 없어 패널을 생성할 수 없습니다.")
                return False
                
            embed = discord.Embed.from_dict(embed_data)
            
            if self.view_instance is None:
                await self.register_persistent_views() # View가 없다면 여기서 등록
            else:
                 await self.view_instance.setup_buttons() # 이미 있다면 버튼만 새로고침
            
            new_message = await channel.send(embed=embed, view=self.view_instance)
            await save_panel_id(base_panel_key, new_message.id, channel.id)
            logger.info(f"✅ 경고 패널을 성공적으로 새로 생성했습니다. (채널: #{channel.name})")
            return True
        except Exception as e:
            logger.error(f"❌ {panel_key} 패널 재설치 중 오류 발생: {e}", exc_info=True)
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(WarningSystem(bot))
