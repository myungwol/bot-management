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

class WarningModal(ui.Modal, title="警告内容の入力"):
    amount = ui.TextInput(label="警告回数", placeholder="付与する警告の回数を数字で入力 (例: 1)", required=True, max_length=2)
    reason = ui.TextInput(label="警告理由", placeholder="警告を発行する理由を具体的に記入してください。", style=discord.TextStyle.paragraph, required=True, max_length=500)

    def __init__(self, cog: 'WarningSystem', target_member: discord.Member):
        super().__init__()
        self.cog = cog
        self.target_member = target_member

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        try:
            amount_val = int(self.amount.value)
            if amount_val <= 0:
                await interaction.followup.send("❌ 警告回数は1以上の自然数を入力してください。", ephemeral=True)
                return
        except (ValueError, TypeError):
            await interaction.followup.send("❌ 警告回数は数字で入力してください。", ephemeral=True)
            return

        # 1. DB에 경고 기록 추가
        await add_warning(
            guild_id=interaction.guild_id,
            user_id=self.target_member.id,
            moderator_id=interaction.user.id,
            reason=self.reason.value,
            amount=amount_val
        )

        # 2. 누적 경고 횟수 확인 및 역할 업데이트
        new_total = await get_total_warning_count(self.target_member.id, interaction.guild_id)
        await self.cog.update_warning_roles(self.target_member, new_total)

        # 3. 로그 채널에 기록
        await self.cog.send_log_message(
            moderator=interaction.user,
            target=self.target_member,
            reason=self.reason.value,
            amount=amount_val,
            new_total=new_total
        )
        
        # 4. 대상자에게 DM 발송
        try:
            dm_embed = discord.Embed(title=f"🚨 {interaction.guild.name}にて警告が付与されました", color=0xED4245)
            dm_embed.add_field(name="理由", value=self.reason.value, inline=False)
            dm_embed.add_field(name="付与された警告回数", value=f"{amount_val}回", inline=True)
            dm_embed.add_field(name="累積警告回数", value=f"{new_total}回", inline=True)
            dm_embed.set_footer(text="ご不明な点がある場合は、お問い合わせチケットをご利用ください。")
            await self.target_member.send(embed=dm_embed)
        except discord.Forbidden:
            logger.warning(f"{self.target_member.display_name}님에게 DM을 보낼 수 없어 경고 알림을 보내지 못했습니다.")
            
        await interaction.followup.send(f"✅ {self.target_member.mention} さんに **{amount_val}回** の警告を正常に付与しました。 (累積: {new_total}回)", ephemeral=True)


class TargetUserSelectView(ui.View):
    def __init__(self, cog: 'WarningSystem'):
        super().__init__(timeout=180)
        self.cog = cog

    @ui.select(cls=ui.UserSelect, placeholder="警告を与えるユーザーを選択してください。")
    async def select_user(self, interaction: discord.Interaction, select: ui.UserSelect):
        target_user = select.values[0]
        if target_user.bot:
            await interaction.response.send_message("❌ ボットには警告を与えられません。", ephemeral=True)
            return
            
        modal = WarningModal(self.cog, target_user)
        await interaction.response.send_modal(modal)
        
        # 이전 메시지(드롭다운) 삭제
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
        # 권한 확인
        if not self.cog.police_role_id or not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("❌ 権限がありません。", ephemeral=True)
            
        if not any(r.id == self.cog.police_role_id for r in interaction.user.roles):
            police_role = interaction.guild.get_role(self.cog.police_role_id)
            role_name = police_role.name if police_role else "警告担当"
            return await interaction.response.send_message(f"❌ この機能は`{role_name}`の役割を持つスタッフのみ使用できます。", ephemeral=True)
            
        view = TargetUserSelectView(self.cog)
        await interaction.response.send_message("警告を与える対象のユーザーを選択してください。", view=view, ephemeral=True)


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
        
        # 1. 이 시스템이 관리하는 모든 경고 역할 ID를 가져옵니다.
        all_warning_role_ids = {get_id(t['role_key']) for t in WARNING_THRESHOLDS if get_id(t['role_key'])}
        
        # 2. 유저가 현재 가지고 있는 경고 역할을 확인합니다.
        current_warning_roles = [role for role in member.roles if role.id in all_warning_role_ids]
        
        # 3. 유저가 받아야 할 새로운 역할을 결정합니다.
        #    (경고 횟수가 높은 순으로 정렬하여 가장 먼저 맞는 조건을 찾음)
        target_role_id = None
        for threshold in sorted(WARNING_THRESHOLDS, key=lambda x: x['count'], reverse=True):
            if total_count >= threshold['count']:
                target_role_id = get_id(threshold['role_key'])
                break
        
        target_role = guild.get_role(target_role_id) if target_role_id else None

        # 4. 역할 추가/제거 로직
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

    async def send_log_message(self, moderator: discord.Member, target: discord.Member, reason: str, amount: int, new_total: int):
        if not self.log_channel_id: return
        log_channel = self.bot.get_channel(self.log_channel_id)
        if not log_channel: return
        
        embed_data = await get_embed_from_db("log_warning")
        if not embed_data: return
        
        embed = format_embed_from_db(embed_data)
        embed.set_author(name=f"{moderator.display_name} → {target.display_name}", icon_url=moderator.display_avatar.url)
        embed.add_field(name="対象者", value=f"{target.mention} (`{target.id}`)", inline=False)
        embed.add_field(name="担当者", value=f"{moderator.mention} (`{moderator.id}`)", inline=False)
        embed.add_field(name="理由", value=reason, inline=False)
        embed.add_field(name="付与回数", value=f"`{amount}`回", inline=True)
        embed.add_field(name="累積回数", value=f"`{new_total}`回", inline=True)
        embed.timestamp = datetime.now(timezone.utc)
        
        await log_channel.send(embed=embed)
        
    async def regenerate_panel(self, channel: Optional[discord.TextChannel] = None, panel_type: str = "warning"):
        target_channel = channel
        if not target_channel:
            if self.panel_channel_id: target_channel = self.bot.get_channel(self.panel_channel_id)
            else: return

        if not target_channel: 
            logger.warning(f"경고 패널 채널(ID: {self.panel_channel_id})을 찾을 수 없어 재생성할 수 없습니다.")
            return False

        # 기존 패널 메시지 삭제
        panel_info = get_panel_id("warning")
        if panel_info and (old_id := panel_info.get('message_id')):
            try:
                old_message = await target_channel.fetch_message(old_id)
                await old_message.delete()
            except (discord.NotFound, discord.Forbidden):
                pass
        
        embed_data = await get_embed_from_db("panel_warning")
        if not embed_data:
            logger.error("DB에서 'panel_warning' 임베드를 찾을 수 없어 패널을 생성할 수 없습니다.")
            return False
            
        embed = discord.Embed.from_dict(embed_data)
        
        if self.view_instance is None:
            self.view_instance = WarningPanelView(self)
        await self.view_instance.setup_buttons()
        
        new_message = await target_channel.send(embed=embed, view=self.view_instance)
        await save_panel_id("warning", new_message.id, target_channel.id)
        logger.info(f"✅ 경고 패널을 성공적으로 새로 생성했습니다. (채널: #{target_channel.name})")
        return True

async def setup(bot: commands.Bot):
    await bot.add_cog(WarningSystem(bot))
