# cogs/server/nicknames.py

import discord
from discord.ext import commands
from discord import app_commands, ui
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

logger = logging.getLogger(__name__)

class RejectionReasonModal(ui.Modal, title="거절 사유 입력"):
    reason = ui.TextInput(label="거절 사유", placeholder="거절하는 이유를 구체적으로 입력해주세요.", style=discord.TextStyle.paragraph, required=True, max_length=200)
    async def on_submit(self, interaction: discord.Interaction): await interaction.response.defer()

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

    # ▼▼▼ [핵심 수정] 관리자 처리 시, 신청서를 '수정'하는 방식으로 변경 ▼▼▼
    async def _handle_approval_flow(self, interaction: discord.Interaction, is_approved: bool):
        if not await self._check_permission(interaction):
            return

        lock = self.nicknames_cog.get_user_lock(self.target_member_id)
        if lock.locked():
            await interaction.response.send_message("⏳ 다른 관리자가 이 신청을 처리 중입니다. 잠시 후 다시 시도해주세요.", ephemeral=True)
            return
        
        rejection_reason = None
        if not is_approved:
            modal = RejectionReasonModal()
            await interaction.response.send_modal(modal)
            timed_out = await modal.wait()
            
            if timed_out or not modal.reason.value:
                return
            
            rejection_reason = modal.reason.value
        else:
            await interaction.response.defer() # ephemeral=True 제거

        await lock.acquire()
        try:
            member = interaction.guild.get_member(self.target_member_id)
            if not member:
                await interaction.edit_original_response(content="❌ 오류: 대상 멤버를 서버에서 찾을 수 없습니다.", embed=None, view=None)
                return

            final_name = await self.nicknames_cog.get_final_nickname(member, base_name=self.new_name)
            
            if is_approved:
                try:
                    await member.edit(nick=final_name, reason=f"관리자가 승인 ({interaction.user})")
                except Exception as e:
                    logger.error(f"닉네임 변경 실패: {e}", exc_info=True)
            
            log_embed = self._create_log_embed(member, interaction.user, final_name, is_approved, rejection_reason)
            
            # 신청서 메시지를 결과 로그로 '수정'하고 버튼을 제거
            await interaction.edit_original_response(content="", embed=log_embed, view=None)
        
        finally:
            lock.release()

    def _create_log_embed(self, member: discord.Member, moderator: discord.Member, final_name: str, is_approved: bool, reason: Optional[str]) -> discord.Embed:
        if is_approved:
            embed = discord.Embed(title="✅ 이름 변경 승인", color=discord.Color.green())
            embed.add_field(name="주민", value=member.mention, inline=False)
            embed.add_field(name="기존 이름", value=f"`{self.original_name}`", inline=False)
            embed.add_field(name="새 이름", value=f"`{final_name}`", inline=False)
        else:
            embed = discord.Embed(title="❌ 이름 변경 거절", color=discord.Color.red())
            embed.add_field(name="주민", value=member.mention, inline=False)
            embed.add_field(name="신청한 이름", value=f"`{self.new_name}`", inline=False)
            embed.add_field(name="거절 사유", value=reason or "사유 미입력", inline=False)
        
        embed.add_field(name="담당자", value=moderator.mention, inline=False)
        embed.timestamp = datetime.now(timezone.utc)
        return embed

    @ui.button(label="승인", style=discord.ButtonStyle.success, custom_id="nick_approve")
    async def approve(self, i: discord.Interaction, b: ui.Button): await self._handle_approval_flow(i, is_approved=True)
    @ui.button(label="거절", style=discord.ButtonStyle.danger, custom_id="nick_reject")
    async def reject(self, i: discord.Interaction, b: ui.Button): await self._handle_approval_flow(i, is_approved=False)


class NicknameChangeModal(ui.Modal, title="이름 변경 신청"):
    new_name = ui.TextInput(label="새로운 이름", placeholder="순수 한글 6자 이내로 입력해주세요.", required=True, max_length=6)

    def __init__(self, cog_instance: 'Nicknames'):
        super().__init__()
        self.nicknames_cog = cog_instance

    # ▼▼▼ [핵심 수정] Modal 제출 시, 신청서를 보내고 즉시 패널을 재생성 ▼▼▼
    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        name = self.new_name.value
        
        pattern_str = r"^[\uAC00-\uD7A3]+$"
        if not re.match(pattern_str, name):
            return await i.followup.send("❌ 오류: 이름은 한글로만 구성되어야 합니다.", ephemeral=True)
        
        max_length = 6
        if len(name) > max_length:
            return await i.followup.send(f"❌ 오류: 이름은 최대 {max_length}자까지 가능합니다.", ephemeral=True)
        
        # 1. 신청서 메시지를 현재 채널에 전송
        await set_cooldown(str(i.user.id), "nickname_change")

        embed = discord.Embed(title="📝 이름 변경 신청", color=discord.Color.blue())
        embed.add_field(name="신청자", value=i.user.mention, inline=False).add_field(name="현재 이름", value=i.user.display_name, inline=False).add_field(name="희망 이름", value=name, inline=False)
        
        approval_role_id = get_id("role_approval")
        mention_content = f"<@&{approval_role_id}>" if approval_role_id else ""
        
        view = NicknameApprovalView(i.user, name, self.nicknames_cog)
        await i.channel.send(mention_content, embed=embed, view=view, allowed_mentions=discord.AllowedMentions(roles=True))
        
        # 2. 신청서 전송 후, 즉시 패널을 새로고침하여 맨 아래로 보냄
        await self.nicknames_cog.regenerate_panel(i.channel)
        
        message = await i.followup.send("이름 변경 신청서를 제출했습니다.", ephemeral=True, wait=True)
        await asyncio.sleep(5)
        await message.delete()

class NicknameChangerPanelView(ui.View):
    # ... (이 클래스는 변경사항 없음) ...
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
    # ... (__init__, get_user_lock, calculate_weighted_length, register_persistent_views, cog_load, load_configs 는 변경사항 없음) ...
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.nickname_log_channel_id: Optional[int] = None
        self.approval_role_id: Optional[int] = None
        self.view_instance = None
        self.panel_regeneration_lock = asyncio.Lock()
        self._user_locks: Dict[int, asyncio.Lock] = {}
        logger.info("Nicknames Cog가 성공적으로 초기화되었습니다.")

    def get_user_lock(self, user_id: int) -> asyncio.Lock:
        if user_id not in self._user_locks:
            self._user_locks[user_id] = asyncio.Lock()
        return self._user_locks[user_id]
    
    @staticmethod
    def calculate_weighted_length(name: str) -> int:
        return len(name)

    async def register_persistent_views(self):
        self.view_instance = NicknameChangerPanelView(self)
        await self.view_instance.setup_buttons()
        self.bot.add_view(self.view_instance)

    async def cog_load(self):
        await self.load_configs()

    async def load_configs(self):
        self.nickname_log_channel_id = get_id("nickname_log_channel_id")
        self.approval_role_id = get_id("role_approval")
        logger.info("[Nicknames Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")
        
    # ... (get_final_nickname, update_nickname, on_member_update 함수는 변경사항 없음) ...
    async def get_final_nickname(self, member: discord.Member, base_name: str = "") -> str:
        role_configs = get_config("UI_ROLE_KEY_MAP", {})
        suffix = get_config("NICKNAME_SUFFIX", "") 
        member_role_ids = {role.id for role in member.roles}
        user_prefix_roles = []
        for key, config in role_configs.items():
            role_id = get_id(key)
            if role_id in member_role_ids and config.get("is_prefix"):
                user_prefix_roles.append(config)
        highest_priority_role_config = max(user_prefix_roles, key=lambda r: r.get("priority", 0)) if user_prefix_roles else None
        base = ""
        if base_name.strip():
            base = base_name.strip()
        else:
            current_nick = member.nick or member.name
            base = current_nick
            possible_formats = []
            for cfg in user_prefix_roles:
                symbol = cfg.get("prefix_symbol")
                p_format = cfg.get("prefix_format", "「{symbol}」")
                s_format = cfg.get("suffix", "")
                if symbol:
                    possible_formats.append((p_format.format(symbol=symbol), s_format))
            for prefix_str, suffix_str in sorted(possible_formats, key=lambda x: len(x[0]) + len(x[1]), reverse=True):
                if current_nick.startswith(f"{prefix_str} ") and current_nick.endswith(suffix_str):
                    base = current_nick[len(f"{prefix_str} "):-len(suffix_str)]
                    break
        final_nick = base
        if highest_priority_role_config:
            symbol = highest_priority_role_config.get("prefix_symbol")
            prefix_format = highest_priority_role_config.get("prefix_format", "「{symbol}」")
            suffix = highest_priority_role_config.get("suffix", "")
            if symbol:
                full_prefix = prefix_format.format(symbol=symbol)
                final_nick = f"{full_prefix} {base}{suffix}"
        if len(final_nick) > 32:
            prefix_str = ""
            suffix_str = ""
            if highest_priority_role_config:
                symbol = highest_priority_role_config.get("prefix_symbol")
                p_format = highest_priority_role_config.get("prefix_format", "「{symbol}」")
                s_format = highest_priority_role_config.get("suffix", "")
                if symbol:
                    prefix_str = f"{p_format.format(symbol=symbol)} "
                suffix_str = s_format
            allowed_base_len = 32 - (len(prefix_str) + len(suffix_str))
            base = base[:allowed_base_len]
            final_nick = f"{prefix_str}{base}{suffix_str}"
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
                
    # ▼▼▼ [핵심 수정] regenerate_panel 함수에서 log_embed 인자 제거 ▼▼▼
    async def regenerate_panel(self, channel: discord.TextChannel, panel_key: str = "panel_nicknames") -> bool:
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
                    return False
                    
                embed = discord.Embed.from_dict(embed_data)
                
                if self.view_instance is None:
                    await self.register_persistent_views()
                await self.view_instance.setup_buttons()

                new_panel_message = await channel.send(embed=embed, view=self.view_instance)
                
                if new_panel_message:
                    await save_panel_id(base_panel_key, new_panel_message.id, channel.id)
                    logger.info(f"✅ {panel_key} 패널을 성공적으로 새로 생성/갱신했습니다. (채널: #{channel.name})")
                    return True
                else:
                    logger.error("닉네임 패널 메시지 전송에 실패하여 ID를 저장할 수 없습니다.")
                    return False

            except Exception as e:
                logger.error(f"❌ {panel_key} 패널 재설치 중 오류 발생: {e}", exc_info=True)
                return False

async def setup(bot: commands.Bot):
    await bot.add_cog(Nicknames(bot))
