# cogs/server/nicknames.py

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

logger = logging.getLogger(__name__)

class RejectionReasonModal(ui.Modal, title="拒否事由入力"):
    reason = ui.TextInput(label="拒否事由", placeholder="拒否する理由を具体的に入力してください。", style=discord.TextStyle.paragraph, required=True, max_length=200)
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

    async def _handle_approval_flow(self, interaction: discord.Interaction, is_approved: bool):
        if not await self._check_permission(interaction):
            return

        lock = self.nicknames_cog.get_user_lock(self.target_member_id)
        if lock.locked():
            await interaction.response.send_message("⏳ 他の管理者がこの申請を処理中です。しばらくしてからもう一度お試しください。", ephemeral=True)
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
            await interaction.response.defer(ephemeral=True)

        await lock.acquire()
        try:
            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(content=f"⏳ {interaction.user.mention}さんが処理中...", view=self)
            
            member = interaction.guild.get_member(self.target_member_id)
            if not member:
                await interaction.followup.send("❌ エラー: 対象メンバーをサーバーで見つけられません。", ephemeral=True)
                try:
                    await interaction.message.delete()
                except (discord.NotFound, discord.HTTPException):
                    pass
                return

            # [수정] final_name을 self.new_name으로 직접 사용합니다.
            final_name = self.new_name
            error_report = ""
            if is_approved:
                try:
                    await member.edit(nick=final_name, reason=f"管理者による承認 ({interaction.user})")
                except Exception as e:
                    error_report += f"- ニックネーム変更失敗: `{type(e).__name__}: {e}`\n"
            
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

            status_text = "承認" if is_approved else "拒否"
            if error_report:
                await interaction.followup.send(f"❌ **{status_text}** 処理中に一部の作業に失敗しました:\n{error_report}", ephemeral=True)
            else:
                message = await interaction.followup.send(f"✅ {status_text} 処理が正常に完了しました。", ephemeral=True, wait=True)
                await asyncio.sleep(3)
                await message.delete()
            
            await interaction.delete_original_response()
        
        finally:
            lock.release()

    def _create_log_embed(self, member: discord.Member, moderator: discord.Member, final_name: str, is_approved: bool, reason: Optional[str]) -> discord.Embed:
        if is_approved:
            embed = discord.Embed(title="✅ 名前変更通知 (承認)", color=discord.Color.green())
            embed.add_field(name="メンバー", value=member.mention, inline=False) # '주민' -> 'メンバー'
            embed.add_field(name="以前の名前", value=f"`{self.original_name}`", inline=False)
            embed.add_field(name="新しい名前", value=f"`{final_name}`", inline=False)
            embed.add_field(name="担当者", value=moderator.mention, inline=False)
        else:
            embed = discord.Embed(title="❌ 名前変更通知 (拒否)", color=discord.Color.red())
            embed.add_field(name="メンバー", value=member.mention, inline=False) # '주민' -> 'メンバー'
            embed.add_field(name="以前の名前", value=f"`{self.original_name}`", inline=False)
            embed.add_field(name="申請した名前", value=f"`{self.new_name}`", inline=False)
            embed.add_field(name="拒否事由", value=reason or "事由未入力", inline=False)
            embed.add_field(name="担当者", value=moderator.mention, inline=False)
        return embed

    async def _send_log_message_fallback(self, result_embed: discord.Embed):
        log_channel_id = self.nicknames_cog.nickname_log_channel_id
        if log_channel_id:
            log_channel = self.nicknames_cog.bot.get_channel(log_channel_id)
            if log_channel and isinstance(log_channel, discord.TextChannel):
                await log_channel.send(embed=result_embed)

    @ui.button(label="承認", style=discord.ButtonStyle.success, custom_id="nick_approve")
    async def approve(self, i: discord.Interaction, b: ui.Button): await self._handle_approval_flow(i, is_approved=True)
    @ui.button(label="拒否", style=discord.ButtonStyle.danger, custom_id="nick_reject")
    async def reject(self, i: discord.Interaction, b: ui.Button): await self._handle_approval_flow(i, is_approved=False)

class NicknameChangeModal(ui.Modal, title="名前変更申請"):
    new_name = ui.TextInput(label="新しい名前", placeholder="漢字は2文字、ひらがな/カタカナ/英数字は1文字として計算", required=True, max_length=12)

    def __init__(self, cog_instance: 'Nicknames'):
        super().__init__()
        self.nicknames_cog = cog_instance

    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        name = self.new_name.value
        
        pattern_str = r"^[a-zA-Z0-9\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]+$"
        max_length = int(get_config("NICKNAME_MAX_WEIGHTED_LENGTH", 8))

        if not re.match(pattern_str, name):
            return await i.followup.send("❌ エラー: 名前に絵文字や特殊文字は使用できません。", ephemeral=True)
        
        if (length := self.nicknames_cog.calculate_weighted_length(name)) > max_length:
            return await i.followup.send(f"❌ エラー: 名前の長さがルールを超過しました。(現在: **{length}/{max_length}**)", ephemeral=True)

        if not self.nicknames_cog.approval_channel_id or not self.nicknames_cog.approval_role_id:
            return await i.followup.send("エラー: ニックネーム機能が正しく設定されていません。", ephemeral=True)
        if not (ch := i.guild.get_channel(self.nicknames_cog.approval_channel_id)):
            return await i.followup.send("エラー: 承認チャンネルが見つかりません。", ephemeral=True)
        
        await set_cooldown(i.user.id, "nickname_change") # user.id를 문자열로 변환할 필요가 없습니다.

        embed = discord.Embed(title="📝 名前変更申請", color=discord.Color.blue())
        embed.add_field(name="申請者", value=i.user.mention, inline=False).add_field(name="現在の名前", value=i.user.display_name, inline=False).add_field(name="希望の名前", value=name, inline=False)
        view = NicknameApprovalView(i.user, name, self.nicknames_cog)
        await ch.send(f"<@&{self.nicknames_cog.approval_role_id}> 新しい名前変更申請があります。", embed=embed, view=view, allowed_mentions=discord.AllowedMentions(roles=True))
        
        message = await i.followup.send("名前変更申請書を提出しました。", ephemeral=True, wait=True)
        await asyncio.sleep(5)
        await message.delete()

class NicknameChangerPanelView(ui.View):
    def __init__(self, cog_instance: 'Nicknames'):
        super().__init__(timeout=None)
        self.nicknames_cog = cog_instance
        self.user_locks: Dict[int, asyncio.Lock] = {}

    async def setup_buttons(self):
        self.clear_items()
        components_data = await get_panel_components_from_db('nicknames')
        if not components_data:
            default_button = ui.Button(label="名前変更申請", style=discord.ButtonStyle.primary, custom_id="request_nickname_change")
            default_button.callback = self.request_change
            self.add_item(default_button)
            return
        for comp in components_data:
            if comp.get('component_type') == 'button' and comp.get('component_key'):
                button = ui.Button(label=comp.get('label'), style=discord.ButtonStyle(comp.get('style_value', 1)), emoji=comp.get('emoji'), row=comp.get('row'), custom_id=comp.get('component_key'))
                if comp.get('component_key') == 'request_nickname_change':
                    button.callback = self.request_change
                self.add_item(button)

    async def request_change(self, i: discord.Interaction):
        lock = self.user_locks.setdefault(i.user.id, asyncio.Lock())
        if lock.locked():
            return await i.response.send_message("以前のリクエストを処理中です。", ephemeral=True)
        async with lock:
            cooldown_seconds = int(get_config("NICKNAME_CHANGE_COOLDOWN_SECONDS", 14400))
            last_time = await get_cooldown(i.user.id, "nickname_change")
            utc_now = datetime.now(timezone.utc).timestamp()

            if last_time and utc_now - last_time < cooldown_seconds:
                time_remaining = cooldown_seconds - (utc_now - last_time)
                formatted_time = format_seconds_to_hms(time_remaining)
                message = f"❌ 次の申請まで **{formatted_time}** 残っています。"
                return await i.response.send_message(message, ephemeral=True)
            
            await i.response.send_modal(NicknameChangeModal(self.nicknames_cog))

class Nicknames(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.approval_channel_id: Optional[int] = None
        self.approval_role_id: Optional[int] = None
        self.nickname_log_channel_id: Optional[int] = None
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
        kanji_pattern = re.compile(r'[\u4E00-\u9FAF]')
        for char in name:
            total_length += 2 if kanji_pattern.match(char) else 1
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
        logger.info("[Nicknames Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")

    # [삭제] 칭호(접두사)를 붙이는 get_final_nickname 함수를 제거합니다.
    # [삭제] 역할 변경 시 닉네임을 업데이트하는 on_member_update 리스너를 제거합니다.

    async def update_nickname(self, member: discord.Member, base_name_override: str):
        """자기소개 승인 시 닉네임을 설정하는 함수. 칭호 없이 그대로 설정합니다."""
        try:
            # [수정] 칭호 없이 전달된 이름 그대로 닉네임으로 설정합니다.
            final_name = base_name_override.strip()
            if member.nick != final_name:
                await member.edit(nick=final_name, reason="自己紹介完了による名前設定")
        except discord.Forbidden:
            logger.warning(f"ニックネーム更新: {member.display_name}のニックネームを変更する権限がありません。")
        except Exception as e:
            logger.error(f"ニックネーム更新: {member.display_name}のニックネーム更新中にエラー発生: {e}", exc_info=True)

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
                    logger.error("ニックネームパネルメッセージの送信に失敗し、IDを保存できません。")
                    if log_embed and self.nickname_log_channel_id:
                         if log_channel := self.bot.get_channel(self.nickname_log_channel_id):
                            await log_channel.send(embed=log_embed)
                    return False

            except Exception as e:
                logger.error(f"❌ {panel_key} パネル 재설치 중 오류 발생: {e}", exc_info=True)
                return False

async def setup(bot: commands.Bot):
    await bot.add_cog(Nicknames(bot))
