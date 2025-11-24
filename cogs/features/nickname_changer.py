# cogs/features/nickname_changer.py

import discord
from discord.ext import commands
from discord import ui
import re
import asyncio
from datetime import datetime, timezone
import logging
from typing import Optional, Dict

from utils.database import (
    get_panel_id, save_panel_id, get_cooldown, set_cooldown, 
    get_id, get_embed_from_db, get_panel_components_from_db,
    get_config
)
from utils.helpers import format_embed_from_db, format_seconds_to_hms, has_required_roles
from .prefix_manager import PrefixManager

logger = logging.getLogger(__name__)

class RejectionReasonModal(ui.Modal, title="거절 사유 입력"):
    reason = ui.TextInput(label="거절 사유", placeholder="거절하는 이유를 구체적으로 입력해주세요.", style=discord.TextStyle.paragraph, required=True, max_length=200)
    async def on_submit(self, interaction: discord.Interaction): await interaction.response.defer()

class NicknameApprovalView(ui.View):
    def __init__(self, member: discord.Member, new_name: str, parent_cog: 'NicknameChanger'):
        super().__init__(timeout=None)
        self.target_member_id = member.id
        self.new_name = new_name
        self.parent_cog = parent_cog
        self.original_name = member.display_name
    
    async def _check_permission(self, interaction: discord.Interaction) -> bool:
        required_keys = ["role_approval", "role_staff_village_chief", "role_staff_deputy_chief"]
        return await has_required_roles(interaction, required_keys)

    async def _handle_approval_flow(self, interaction: discord.Interaction, is_approved: bool):
        if not await self._check_permission(interaction): return

        lock = self.parent_cog.get_user_lock(self.target_member_id)
        if lock.locked():
            return await interaction.response.send_message("⏳ 다른 관리자가 처리 중입니다.", ephemeral=True)
        
        rejection_reason = None
        if not is_approved:
            modal = RejectionReasonModal()
            await interaction.response.send_modal(modal)
            if await modal.wait() or not modal.reason.value: return
            rejection_reason = modal.reason.value
        else:
            await interaction.response.defer()

        async with lock:
            member = interaction.guild.get_member(self.target_member_id)
            if not member:
                return await interaction.edit_original_response(content="❌ 대상 멤버를 찾을 수 없습니다.", embed=None, view=None)

            final_name = self.new_name # 기본값은 신청한 이름
            if is_approved:
                prefix_cog: PrefixManager = self.parent_cog.bot.get_cog("PrefixManager")
                if prefix_cog:
                    final_name = await prefix_cog.apply_prefix(member, base_name=self.new_name)
                else:
                    logger.error("PrefixManager Cog를 찾을 수 없어 접두사 적용에 실패했습니다.")
                    try:
                        await member.edit(nick=self.new_name, reason=f"관리자 승인 ({interaction.user})")
                    except Exception as e: logger.error(f"닉네임 변경 실패: {e}", exc_info=True)
            
            log_embed = self._create_log_embed(member, interaction.user, final_name, is_approved, rejection_reason)
            await interaction.edit_original_response(content="", embed=log_embed, view=None)

    def _create_log_embed(self, member, moderator, final_name, is_approved, reason):
        title = "✅ 이름 변경 승인" if is_approved else "❌ 이름 변경 거절"
        color = discord.Color.green() if is_approved else discord.Color.red()
        embed = discord.Embed(title=title, color=color, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="주민", value=member.mention, inline=False)
        if is_approved:
            embed.add_field(name="기존 이름", value=f"`{self.original_name}`", inline=False)
            embed.add_field(name="새 이름", value=f"`{final_name}`", inline=False)
        else:
            embed.add_field(name="신청한 이름", value=f"`{self.new_name}`", inline=False)
            embed.add_field(name="거절 사유", value=reason or "사유 미입력", inline=False)
        embed.add_field(name="담당자", value=moderator.mention, inline=False)
        return embed

    @ui.button(label="승인", style=discord.ButtonStyle.success, custom_id="nick_approve")
    async def approve(self, i: discord.Interaction, b: ui.Button): await self._handle_approval_flow(i, is_approved=True)
    @ui.button(label="거절", style=discord.ButtonStyle.danger, custom_id="nick_reject")
    async def reject(self, i: discord.Interaction, b: ui.Button): await self._handle_approval_flow(i, is_approved=False)

class NicknameChangeModal(ui.Modal, title="이름 변경 신청"):
    # ▼▼▼ [수정 1] 입력 제한을 8자로 변경하고 안내 문구 수정 ▼▼▼
    new_name = ui.TextInput(
        label="새로운 이름", 
        placeholder="한글과 공백 포함 8자 이내로 입력해주세요.", 
        required=True, 
        max_length=8
    )
    
    def __init__(self, parent_cog: 'NicknameChanger'):
        super().__init__(); self.parent_cog = parent_cog
        
    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True); name = self.new_name.value
        
        # ▼▼▼ [수정 2] 정규식을 한글(가-힣) + 공백(\s) 허용으로 변경하고 길이 체크 8자로 수정 ▼▼▼
        if not re.match(r"^[가-힣\s]+$", name) or len(name) > 8:
            return await i.followup.send("❌ 이름은 8자 이내의 한글과 공백으로만 구성되어야 합니다.", ephemeral=True)
        
        await set_cooldown(str(i.user.id), "nickname_change")
        embed = discord.Embed(title="📝 이름 변경 신청", color=discord.Color.blue())
        embed.add_field(name="신청자", value=i.user.mention, inline=False).add_field(name="현재 이름", value=i.user.display_name, inline=False).add_field(name="희망 이름", value=name, inline=False)
        
        mention = f"<@&{rid}>" if (rid := get_id("role_approval")) else ""
        view = NicknameApprovalView(i.user, name, self.parent_cog)
        await i.channel.send(mention, embed=embed, view=view, allowed_mentions=discord.AllowedMentions(roles=True))
        
        await self.parent_cog.regenerate_panel(i.channel)
        msg = await i.followup.send("✅ 이름 변경 신청서를 제출했습니다.", ephemeral=True, wait=True)
        await asyncio.sleep(5); await msg.delete()

class NicknameChangerPanelView(ui.View):
    def __init__(self, parent_cog: 'NicknameChanger'):
        super().__init__(timeout=None); self.parent_cog = parent_cog; self.user_locks = {}
    async def setup_buttons(self):
        self.clear_items(); styles = get_config("DISCORD_BUTTON_STYLES_MAP", {})
        components = await get_panel_components_from_db('nicknames')
        if not components:
            btn = ui.Button(label="이름 변경 신청", style=discord.ButtonStyle.primary, custom_id="request_nickname_change")
            btn.callback = self.request_change; self.add_item(btn); return
        for comp in components:
            if comp.get('component_type') == 'button' and comp.get('component_key'):
                style = styles.get(comp.get('style', 'secondary'), discord.ButtonStyle.secondary)
                btn = ui.Button(label=comp.get('label'), style=style, emoji=comp.get('emoji'), row=comp.get('row'), custom_id=comp.get('component_key'))
                if comp.get('component_key') == 'request_nickname_change': btn.callback = self.request_change
                self.add_item(btn)

    async def request_change(self, i: discord.Interaction):
        lock = self.user_locks.setdefault(i.user.id, asyncio.Lock())
        if lock.locked(): return await i.response.send_message("이전 요청 처리 중입니다.", ephemeral=True)
        async with lock:
            cooldown = int(get_config("NICKNAME_CHANGE_COOLDOWN_SECONDS", 14400))
            last_time = await get_cooldown(str(i.user.id), "nickname_change")
            if last_time and (datetime.now(timezone.utc).timestamp() - last_time) < cooldown:
                remaining = cooldown - (datetime.now(timezone.utc).timestamp() - last_time)
                return await i.response.send_message(f"❌ 다음 신청까지 **{format_seconds_to_hms(remaining)}** 남았습니다.", ephemeral=True)
            await i.response.send_modal(NicknameChangeModal(self.parent_cog))

class NicknameChanger(commands.Cog, name="Nicknames"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot; self.view_instance = None; self._user_locks: Dict[int, asyncio.Lock] = {}
        self.panel_regeneration_lock = asyncio.Lock()
        logger.info("NicknameChanger Cog가 성공적으로 초기화되었습니다.")

    def get_user_lock(self, user_id: int) -> asyncio.Lock:
        return self._user_locks.setdefault(user_id, asyncio.Lock())
    
    async def register_persistent_views(self):
        self.view_instance = NicknameChangerPanelView(self)
        await self.view_instance.setup_buttons()
        self.bot.add_view(self.view_instance)
        logger.info("✅ 닉네임 변경 패널의 영구 View가 성공적으로 등록되었습니다.")

    async def cog_load(self):
        await self.register_persistent_views()

    async def regenerate_panel(self, channel: discord.TextChannel, panel_key: str = "panel_nicknames") -> bool:
        async with self.panel_regeneration_lock:
            base_key, embed_key = "nicknames", "panel_nicknames"
            try:
                if (info := get_panel_id(base_key)) and (old_id := info.get('message_id')):
                    try: await (await channel.fetch_message(old_id)).delete()
                    except (discord.NotFound, discord.Forbidden): pass
                
                embed_data = await get_embed_from_db(embed_key)
                if not embed_data:
                    logger.warning(f"DB에서 '{embed_key}' 임베드를 찾을 수 없어 패널 생성을 건너뜁니다.")
                    return False
                
                if self.view_instance is None: await self.register_persistent_views()
                await self.view_instance.setup_buttons()
                new_msg = await channel.send(embed=discord.Embed.from_dict(embed_data), view=self.view_instance)
                await save_panel_id(base_key, new_msg.id, channel.id)
                logger.info(f"✅ 닉네임 변경 패널을 #{channel.name}에 새로 생성했습니다.")
                return True
            except Exception as e:
                logger.error(f"❌ 닉네임 변경 패널 재설치 중 오류: {e}", exc_info=True)
                return False

async def setup(bot: commands.Bot):
    await bot.add_cog(NicknameChanger(bot))
