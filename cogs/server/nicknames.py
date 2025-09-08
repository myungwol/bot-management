# cogs/server/nicknames.py

import discord
from discord.ext import commands
from discord import app_commands, ui
import re
import asyncio
from datetime import datetime, timezone
import logging
from typing import Optional, Dict, Set

from utils.database import (
    get_panel_id, save_panel_id, get_cooldown, set_cooldown, 
    get_id, get_embed_from_db, get_panel_components_from_db,
    get_config
)
from utils.helpers import format_embed_from_db, format_seconds_to_hms, has_required_roles

logger = logging.getLogger(__name__)

# 이제 모달은 잠금 해제 책임을 가지지 않고, 데이터 처리만 담당합니다.
class RejectionReasonModal(ui.Modal, title="거절 사유 입력"):
    reason = ui.TextInput(label="거절 사유", placeholder="거절하는 이유를 구체적으로 입력해주세요.", style=discord.TextStyle.paragraph, required=True, max_length=200)

    def __init__(self, view: 'NicknameApprovalView'):
        super().__init__()
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        # 이 모달은 이제 잠금을 직접 해제하지 않습니다.
        # 대신, 부모 View의 _handle_approval_flow 함수를 호출하여 후속 처리를 위임합니다.
        await self.view._handle_approval_flow(interaction, is_approved=False, reason=self.reason.value)

class NicknameApprovalView(ui.View):
    def __init__(self, member: discord.Member, new_name: str, cog_instance: 'Nicknames'):
        super().__init__(timeout=None)
        self.target_member_id = member.id
        self.new_name = new_name
        self.nicknames_cog = cog_instance
        self.original_name = member.display_name
    
    async def _check_permission(self, interaction: discord.Interaction) -> bool:
        required_keys = ["role_approval", "role_staff_village_chief", "role_staff_deputy_chief"]
        return await has_required_roles(interaction, required_keys)
    
    def _create_log_embed(self, member, moderator, final_name, is_approved, reason=None):
        # (변경 없음)
        if is_approved:
            embed = discord.Embed(title="✅ 이름 변경 알림 (승인)", color=discord.Color.green())
            embed.add_field(name="주민", value=member.mention, inline=False).add_field(name="기존 이름", value=f"`{self.original_name}`", inline=False).add_field(name="새 이름", value=f"`{final_name}`", inline=False).add_field(name="담당자", value=moderator.mention, inline=False)
        else:
            embed = discord.Embed(title="❌ 이름 변경 알림 (거절)", color=discord.Color.red())
            embed.add_field(name="주민", value=member.mention, inline=False).add_field(name="기존 이름", value=f"`{self.original_name}`", inline=False).add_field(name="신청한 이름", value=f"`{self.new_name}`", inline=False).add_field(name="거절 사유", value=reason or "사유 미입력", inline=False).add_field(name="담당자", value=moderator.mention, inline=False)
        return embed

    async def _handle_approval_flow(self, interaction: discord.Interaction, is_approved: bool, reason: Optional[str] = None):
        """승인/거절 로직을 처리하는 중앙 함수"""
        message_id = interaction.message.id
        try:
            # 모달에서 호출된 경우 이미 defer되었을 수 있으므로 확인
            if not interaction.response.is_done():
                await interaction.response.defer()

            for item in self.children: item.disabled = True
            await interaction.message.edit(content=f"⏳ {interaction.user.mention}님이 처리 중...", view=self)

            member = interaction.guild.get_member(self.target_member_id)
            if not member:
                await interaction.followup.send("❌ 대상 멤버를 찾을 수 없습니다.", ephemeral=True)
                await interaction.message.delete()
                return

            final_name = self.new_name
            if is_approved:
                final_name = await self.nicknames_cog.get_final_nickname(member, base_name=self.new_name)
                await member.edit(nick=final_name, reason=f"관리자가 승인 ({interaction.user})")

            log_embed = self._create_log_embed(member, interaction.user, final_name, is_approved, reason)
            if self.nicknames_cog.nickname_log_channel_id:
                log_channel = self.nicknames_cog.bot.get_channel(self.nicknames_cog.nickname_log_channel_id)
                if log_channel: await log_channel.send(embed=log_embed)

            status_text = "승인" if is_approved else "거절"
            await interaction.followup.send(f"✅ {status_text} 처리가 완료되었습니다.", ephemeral=True)
            await interaction.message.delete()
        finally:
            # 이 함수가 끝나면 잠금을 해제
            logger.info(f"[NICKNAME_HANDLER] 처리 완료, 잠금 해제 시도 (Message ID: {message_id})")
            self.nicknames_cog.locked_requests.discard(message_id)

    @ui.button(label="승인", style=discord.ButtonStyle.success, custom_id="nick_approve")
    async def approve(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check_permission(interaction): return
        message_id = interaction.message.id
        if message_id in self.nicknames_cog.locked_requests:
            return await interaction.response.send_message("⏳ 다른 관리자가 이 신청을 처리 중입니다.", ephemeral=True)
        
        self.nicknames_cog.locked_requests.add(message_id)
        logger.info(f"[NICKNAME_BUTTON] 승인 버튼 클릭, Message ID {message_id} 잠금.")
        await self._handle_approval_flow(interaction, is_approved=True)

    @ui.button(label="거절", style=discord.ButtonStyle.danger, custom_id="nick_reject")
    async def reject(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check_permission(interaction): return
        message_id = interaction.message.id
        if message_id in self.nicknames_cog.locked_requests:
            return await interaction.response.send_message("⏳ 다른 관리자가 이 신청을 처리 중입니다.", ephemeral=True)
        
        self.nicknames_cog.locked_requests.add(message_id)
        logger.info(f"[NICKNAME_BUTTON] 거절 버튼 클릭, Message ID {message_id} 잠금.")
        
        # Failsafe 타이머 시작! 모달 타임아웃(180초)보다 5초 길게 설정
        asyncio.create_task(self.nicknames_cog._unlock_failsafe(message_id, delay=185))
        
        modal = RejectionReasonModal(self)
        await interaction.response.send_modal(modal)

# --- 이하 NicknameChangeModal, NicknameChangerPanelView 는 변경 없음 ---
class NicknameChangeModal(ui.Modal, title="이름 변경 신청"):
    new_name = ui.TextInput(label="새로운 이름", placeholder="이모티콘, 특수문자 사용 불가. 한글 4자/영문 8자까지", required=True, max_length=12)

    def __init__(self, cog_instance: 'Nicknames'):
        super().__init__()
        self.nicknames_cog = cog_instance

    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        name = self.new_name.value
        
        pattern_str = r"^[a-zA-Z0-9\uAC00-\uD7A3]+$"
        max_length = int(get_config("NICKNAME_MAX_WEIGHTED_LENGTH", 8))

        if not re.match(pattern_str, name):
            return await i.followup.send("❌ 오류: 이름에 이모티콘이나 특수문자는 사용할 수 없습니다.", ephemeral=True)
        
        if (length := self.nicknames_cog.calculate_weighted_length(name)) > max_length:
            return await i.followup.send(f"❌ 오류: 이름 길이가 규칙을 초과했습니다. (현재: **{length}/{max_length}**)", ephemeral=True)

        if not self.nicknames_cog.approval_channel_id or not self.nicknames_cog.approval_role_id:
            return await i.followup.send("오류: 닉네임 기능이 올바르게 설정되지 않았습니다.", ephemeral=True)
        if not (ch := i.guild.get_channel(self.nicknames_cog.approval_channel_id)):
            return await i.followup.send("오류: 승인 채널을 찾을 수 없습니다.", ephemeral=True)
        
        await set_cooldown(str(i.user.id), "nickname_change")

        embed = discord.Embed(title="📝 이름 변경 신청", color=discord.Color.blue())
        embed.add_field(name="신청자", value=i.user.mention, inline=False).add_field(name="현재 이름", value=i.user.display_name, inline=False).add_field(name="희망 이름", value=name, inline=False)
        view = NicknameApprovalView(i.user, name, self.nicknames_cog)
        await ch.send(f"<@&{self.nicknames_cog.approval_role_id}> 새로운 이름 변경 신청이 있습니다.", embed=embed, view=view, allowed_mentions=discord.AllowedMentions(roles=True))
        
        message = await i.followup.send("이름 변경 신청서를 제출했습니다.", ephemeral=True, wait=True)
        await asyncio.sleep(5)
        await message.delete()

class NicknameChangerPanelView(ui.View):
    def __init__(self, cog_instance: 'Nicknames'):
        super().__init__(timeout=None)
        self.nicknames_cog = cog_instance
        self.user_locks: Dict[int, asyncio.Lock] = {}

    async def setup_buttons(self):
        self.clear_items()
        button_styles = get_config("DISCORD_BUTTON_STYLES_MAP", {})
        components_data = await get_panel_components_from_db('nicknames')
        if not components_data:
            default_button = ui.Button(label="이름 변경 신청", style=discord.ButtonStyle.primary, custom_id="request_nickname_change")
            default_button.callback = self.request_change
            self.add_item(default_button)
            return
        for comp in components_data:
            if comp.get('component_type') == 'button' and comp.get('component_key'):
                style_key = comp.get('style', 'secondary')
                button = ui.Button(label=comp.get('label'), style=button_styles.get(style_key, discord.ButtonStyle.secondary), emoji=comp.get('emoji'), row=comp.get('row'), custom_id=comp.get('component_key'))
                if comp.get('component_key') == 'request_nickname_change':
                    button.callback = self.request_change
                self.add_item(button)

    async def request_change(self, i: discord.Interaction):
        lock = self.user_locks.setdefault(i.user.id, asyncio.Lock())
        if lock.locked():
            return await i.response.send_message("이전 요청을 처리 중입니다.", ephemeral=True)
        async with lock:
            try:
                cooldown_seconds = int(get_config("NICKNAME_CHANGE_COOLDOWN_SECONDS", 14400))
            except (ValueError, TypeError):
                cooldown_seconds = 14400
                logger.warning("NICKNAME_CHANGE_COOLDOWN_SECONDS 설정값이 숫자가 아니므로 기본값(14400)을 사용합니다.")
            
            last_time = await get_cooldown(str(i.user.id), "nickname_change")
            utc_now = datetime.now(timezone.utc).timestamp()

            if last_time and utc_now - last_time < cooldown_seconds:
                time_remaining = cooldown_seconds - (utc_now - last_time)
                formatted_time = format_seconds_to_hms(time_remaining)
                message = f"❌ 다음 신청까지 **{formatted_time}** 남았습니다."
                return await i.response.send_message(message, ephemeral=True)
            
            await i.response.send_modal(NicknameChangeModal(self.nicknames_cog))


class Nicknames(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.approval_channel_id: Optional[int] = None
        self.approval_role_id: Optional[int] = None
        self.nickname_log_channel_id: Optional[int] = None
        self.master_role_id: Optional[int] = None
        self.vice_master_role_id: Optional[int] = None
        self.view_instance = None
        self.panel_regeneration_lock = asyncio.Lock()
        self.locked_requests: Set[int] = set()
        logger.info("Nicknames Cog가 성공적으로 초기화되었습니다.")

    async def _unlock_failsafe(self, message_id: int, delay: int):
        """지정된 시간 후에도 잠금이 해제되지 않았으면 강제로 해제합니다."""
        await asyncio.sleep(delay)
        if message_id in self.locked_requests:
            logger.warning(f"[NICKNAME_FAILSAFE] ⚠️ 타임아웃된 요청을 강제 해제합니다 (Message ID: {message_id})")
            self.locked_requests.discard(message_id)
            
    # --- 이하 나머지 함수들은 변경 없음 ---
    @staticmethod
    def calculate_weighted_length(name: str) -> int:
        total_length = 0
        pattern = re.compile(r'[\uAC00-\uD7A3]')
        for char in name:
            total_length += 2 if pattern.match(char) else 1
        return total_length

    async def register_persistent_views(self):
        self.view_instance = NicknameChangerPanelView(self)
        await self.view_instance.setup_buttons()
        self.bot.add_view(self.view_instance)

    async def cog_load(self):
        await self.load_configs()

    async def load_configs(self):
        self.approval_channel_id = get_id("nickname_approval_channel_id")
        self.nickname_log_channel_id = get_id("nickname_log_channel_id")
        self.approval_role_id = get_id("role_approval")
        self.master_role_id = get_id("role_staff_village_chief")
        self.vice_master_role_id = get_id("role_staff_deputy_chief")
        logger.info("[Nicknames Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")

    async def get_final_nickname(self, member: discord.Member, base_name: str = "") -> str:
        prefix_hierarchy = get_config("NICKNAME_PREFIX_HIERARCHY", [])
        prefix = None
        member_role_names = {role.name for role in member.roles}
        
        for prefix_name in prefix_hierarchy:
            if prefix_name in member_role_names:
                prefix = f"『 {prefix_name} 』"
                break
        
        if base_name.strip():
            base = base_name.strip()
        else:
            current_nick = member.nick or member.name
            base = current_nick
            for p_name in prefix_hierarchy:
                prefix_to_check = f"『 {p_name} 』"
                if current_nick.startswith(prefix_to_check):
                    base = re.sub(rf"^{re.escape(prefix_to_check)}\s*", "", current_nick)
                    break
        
        final_nick = f"{prefix} {base}" if prefix else base
        if len(final_nick) > 32:
            prefix_len = len(prefix) if prefix else 0
            allowed_base_len = 32 - (prefix_len + 1) if prefix else 32
            base = base[:allowed_base_len]
            final_nick = f"{prefix} {base}" if prefix else base
        return final_nick

    async def update_nickname(self, member: discord.Member, base_name_override: str):
        try:
            final_name = await self.get_final_nickname(member, base_name=base_name_override)
            if member.nick != final_name:
                await member.edit(nick=final_name, reason="온보딩 완료 또는 닉네임 승인")
        except discord.Forbidden:
            logger.warning(f"닉네임 업데이트: {member.display_name}의 닉네임을 변경할 권한이 없습니다.")
        except Exception as e:
            logger.error(f"닉네임 업데이트: {member.display_name}의 닉네임 업데이트 중 오류 발생: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if after.bot or before.roles == after.roles:
            return
        new_nick = await self.get_final_nickname(after, base_name="")
        if after.nick != new_nick:
            try:
                await after.edit(nick=new_nick, reason="역할 변경으로 인한 칭호 자동 업데이트")
            except discord.Forbidden:
                pass

    async def regenerate_panel(self, channel: discord.TextChannel, panel_key: str = "panel_nicknames", log_embed: Optional[discord.Embed] = None) -> bool:
        async with self.panel_regeneration_lock:
            base_panel_key = panel_key.replace("panel_", "")
            embed_key = panel_key

            try:
                panel_info = get_panel_id(base_panel_key)
                if panel_info and (old_id := panel_info.get('message_id')):
                    try:
                        old_message = await channel.fetch_message(old_id)
                        await old_message.delete()
                    except (discord.NotFound, discord.Forbidden): pass
                
                embed_data = await get_embed_from_db(embed_key)
                if not embed_data:
                    logger.warning(f"DB에서 '{embed_key}' 임베드 데이터를 찾을 수 없어, 패널 생성을 건너뜁니다.")
                    if log_embed and self.nickname_log_channel_id:
                        if log_channel := self.bot.get_channel(self.nickname_log_channel_id):
                            await log_channel.send(embed=log_embed)
                    return False
                    
                embed = discord.Embed.from_dict(embed_data)
                if self.view_instance is None:
                    await self.register_persistent_views()

                await self.view_instance.setup_buttons()

                if log_embed:
                    await channel.send(embed=log_embed)
                
                new_panel_message = await channel.send(embed=embed, view=self.view_instance)
                
                if new_panel_message:
                    await save_panel_id(base_panel_key, new_panel_message.id, channel.id)
                    logger.info(f"✅ {panel_key} 패널을 성공적으로 새로 생성/갱신했습니다. (채널: #{channel.name})")
                    return True
                else:
                    logger.error("닉네임 패널 메시지 전송에 실패하여 ID를 저장할 수 없습니다.")
                    if log_embed and self.nickname_log_channel_id:
                         if log_channel := self.bot.get_channel(self.nickname_log_channel_id):
                            await log_channel.send(embed=log_embed)
                    return False

            except Exception as e:
                logger.error(f"❌ {panel_key} 패널 재설치 중 오류 발생: {e}", exc_info=True)
                return False

async def setup(bot: commands.Bot):
    await bot.add_cog(Nicknames(bot))
