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

    # ▼▼▼ [핵심 수정] 올바르고 안전한 Lock 관리 로직으로 최종 수정 ▼▼▼
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
            
            # 모달이 취소되었거나 내용이 없으면 잠금을 걸지 않고 그대로 종료합니다.
            if timed_out or not modal.reason.value:
                return
            
            rejection_reason = modal.reason.value
        else:
            # 승인 시에는 모달이 없으므로 defer를 먼저 호출합니다.
            await interaction.response.defer(ephemeral=True)

        # 실제 처리를 시작하기 직전에 잠금을 획득합니다.
        await lock.acquire()
        try:
            # 버튼을 비활성화하고 처리 중 메시지를 표시합니다.
            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(content=f"⏳ {interaction.user.mention}님이 처리 중...", view=self)
            
            member = interaction.guild.get_member(self.target_member_id)
            if not member:
                # defer가 호출되었으므로 followup을 사용합니다.
                await interaction.followup.send("❌ 오류: 대상 멤버를 서버에서 찾을 수 없습니다.", ephemeral=True)
                try:
                    await interaction.message.delete()
                except (discord.NotFound, discord.HTTPException):
                    pass
                return

            final_name = await self.nicknames_cog.get_final_nickname(member, base_name=self.new_name)
            error_report = ""
            if is_approved:
                try:
                    await member.edit(nick=final_name, reason=f"관리자가 승인 ({interaction.user})")
                except Exception as e:
                    error_report += f"- 닉네임 변경 실패: `{type(e).__name__}: {e}`\n"
            
            log_embed = self._create_log_embed(member, interaction.user, final_name, is_approved, rejection_reason)
            
            original_panel_channel_id = get_id("nickname_panel_channel_id")
            if original_panel_channel_id:
                original_panel_channel = self.nicknames_cog.bot.get_channel(original_panel_channel_id)
                if original_panel_channel and isinstance(original_panel_channel, discord.TextChannel):
                    await self.nicknames_cog.regenerate_panel(
                        original_panel_channel, 
                        panel_key="panel_nicknames", 
                        log_embed=log_embed
                    )
                else:
                    await self._send_log_message_fallback(log_embed)
            else:
                await self._send_log_message_fallback(log_embed)

            status_text = "승인" if is_approved else "거절"
            if error_report:
                await interaction.followup.send(f"❌ **{status_text}** 처리 중 일부 작업에 실패했습니다:\n{error_report}", ephemeral=True)
            else:
                message = await interaction.followup.send(f"✅ {status_text} 처리가 정상적으로 완료되었습니다.", ephemeral=True, wait=True)
                await asyncio.sleep(3)
                await message.delete()
            
            await interaction.delete_original_response()
        
        finally:
            # 이 함수가 어떤 경로로 종료되든, Lock은 반드시 해제됩니다.
            lock.release()
    # ▲▲▲ [핵심 수정] ▲▲▲

    def _create_log_embed(self, member: discord.Member, moderator: discord.Member, final_name: str, is_approved: bool, reason: Optional[str]) -> discord.Embed:
        if is_approved:
            embed = discord.Embed(title="✅ 이름 변경 알림 (승인)", color=discord.Color.green())
            embed.add_field(name="주민", value=member.mention, inline=False)
            embed.add_field(name="기존 이름", value=f"`{self.original_name}`", inline=False)
            embed.add_field(name="새 이름", value=f"`{final_name}`", inline=False)
            embed.add_field(name="담당자", value=moderator.mention, inline=False)
        else:
            embed = discord.Embed(title="❌ 이름 변경 알림 (거절)", color=discord.Color.red())
            embed.add_field(name="주민", value=member.mention, inline=False)
            embed.add_field(name="기존 이름", value=f"`{self.original_name}`", inline=False)
            embed.add_field(name="신청한 이름", value=f"`{self.new_name}`", inline=False)
            embed.add_field(name="거절 사유", value=reason or "사유 미입력", inline=False)
            embed.add_field(name="담당자", value=moderator.mention, inline=False)
        return embed

    async def _send_log_message_fallback(self, result_embed: discord.Embed):
        log_channel_id = self.nicknames_cog.nickname_log_channel_id
        if log_channel_id:
            log_channel = self.nicknames_cog.bot.get_channel(log_channel_id)
            if log_channel and isinstance(log_channel, discord.TextChannel):
                await log_channel.send(embed=result_embed)

    @ui.button(label="승인", style=discord.ButtonStyle.success, custom_id="nick_approve")
    async def approve(self, i: discord.Interaction, b: ui.Button): await self._handle_approval_flow(i, is_approved=True)
    @ui.button(label="거절", style=discord.ButtonStyle.danger, custom_id="nick_reject")
    async def reject(self, i: discord.Interaction, b: ui.Button): await self._handle_approval_flow(i, is_approved=False)

class NicknameChangeModal(ui.Modal, title="이름 변경 신청"):
    # UI 입력 필드: 최대 길이를 6으로, 안내 문구를 새로운 규칙으로 변경
    new_name = ui.TextInput(
        label="새로운 이름", 
        placeholder="순수 한글 6자 이내로 입력해주세요.", 
        required=True, 
        max_length=6
    )

    def __init__(self, cog_instance: 'Nicknames'):
        super().__init__()
        self.nicknames_cog = cog_instance

    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        name = self.new_name.value
        
        # 검증 로직 1: 순수 한글로만 이루어져 있는지 확인
        # ^[...]+$ : 처음부터 끝까지 [] 안의 문자로만 1번 이상 반복
        # \uAC00-\uD7A3 : 한글 음절 범위
        pattern_str = r"^[\uAC00-\uD7A3]+$"
        if not re.match(pattern_str, name):
            return await i.followup.send("❌ 오류: 이름은 한글로만 구성되어야 합니다. (공백, 특수문자, 영문, 숫자 불가)", ephemeral=True)
        
        # 검증 로직 2: 이름 길이를 6자로 제한 (단순 길이 비교)
        max_length = 6
        if len(name) > max_length:
            return await i.followup.send(f"❌ 오류: 이름은 최대 {max_length}자까지 가능합니다. (현재: {len(name)}자)", ephemeral=True)

        # --- 이하 로직은 기존과 동일 ---
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
        self._user_locks: Dict[int, asyncio.Lock] = {}
        logger.info("Nicknames Cog가 성공적으로 초기화되었습니다.")

    def get_user_lock(self, user_id: int) -> asyncio.Lock:
        if user_id not in self._user_locks:
            self._user_locks[user_id] = asyncio.Lock()
        return self._user_locks[user_id]
    
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
        role_configs = get_config("UI_ROLE_KEY_MAP", {})

        # 1. 유저가 가진 is_prefix 역할들 중 가장 우선순위 높은 역할 찾기
        member_role_ids = {role.id for role in member.roles}
        user_prefix_roles = []
        for key, config in role_configs.items():
            role_id = get_id(key)
            if role_id in member_role_ids and config.get("is_prefix"):
                user_prefix_roles.append(config)
        
        highest_priority_role_config = max(user_prefix_roles, key=lambda r: r.get("priority", 0)) if user_prefix_roles else None

        # 2. 순수 이름(base_name) 결정
        base = ""
        if base_name.strip():
            base = base_name.strip()
        else:
            current_nick = member.nick or member.name
            base = current_nick
            # 현재 닉네임에서 모든 가능한 접두사/접미사 형식을 제거하여 순수 이름 추출
            # 가장 긴 형식부터 제거해야 짧은 형식이 먼저 제거되는 오류를 막을 수 있음
            possible_formats = []
            for cfg in user_prefix_roles:
                symbol = cfg.get("prefix_symbol")
                p_format = cfg.get("prefix_format", "「{symbol}」")
                s_format = cfg.get("suffix", "")
                if symbol:
                    possible_formats.append((p_format.format(symbol=symbol), s_format))
            
            # 가장 긴 접두사+접미사 조합부터 확인
            for prefix_str, suffix_str in sorted(possible_formats, key=lambda x: len(x[0]) + len(x[1]), reverse=True):
                if current_nick.startswith(f"{prefix_str} ") and current_nick.endswith(suffix_str):
                    base = current_nick[len(f"{prefix_str} "):-len(suffix_str)]
                    break

        # 3. 최종 닉네임 조립
        final_nick = base
        if highest_priority_role_config:
            symbol = highest_priority_role_config.get("prefix_symbol")
            prefix_format = highest_priority_role_config.get("prefix_format", "「{symbol}」") # 기본값
            suffix = highest_priority_role_config.get("suffix", "") # 기본값
            if symbol:
                full_prefix = prefix_format.format(symbol=symbol)
                final_nick = f"{full_prefix} {base}{suffix}"

        # 4. 디스코드 32자 길이 제한 처리
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
