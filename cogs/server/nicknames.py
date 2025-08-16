# cogs/server/nicknames.py (임베드 DB 연동)

import discord
from discord.ext import commands
from discord import app_commands, ui
import re
import asyncio
import time
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] %(message)s')
logger = logging.getLogger(__name__)

from utils.database import (
    get_panel_id, save_panel_id, get_cooldown, set_cooldown, 
    get_id, get_embed_from_db
)

ALLOWED_NICKNAME_PATTERN = re.compile(r"^[a-zA-Z0-9\u3040-\u309F\u30A0-\u30FF\u4e00-\u9faf]+$")
COOLDOWN_SECONDS = 4 * 3600

NICKNAME_PREFIX_HIERARCHY_NAMES = [
    "里長", "助役", "お巡り", "祭りの委員", "広報係", "意匠係", "書記", "役場の職員", "職員",
    "1等級住民", "2等級住民", "3等級住民", "住民"
]

def calculate_weighted_length(name: str) -> int:
    total_length = 0
    kanji_pattern = re.compile(r'[\u4e00-\u9faf]')
    for char in name: total_length += 2 if kanji_pattern.match(char) else 1
    return total_length

class RejectionReasonModal(ui.Modal, title="拒否理由入力"):
    reason = ui.TextInput(label="拒否理由", placeholder="拒否する理由を具体的に入力してください。", style=discord.TextStyle.paragraph, required=True, max_length=200)
    async def on_submit(self, interaction: discord.Interaction): await interaction.response.defer()

class NicknameApprovalView(ui.View):
    def __init__(self, member: discord.Member, new_name: str, cog_instance: 'Nicknames'):
        super().__init__(timeout=None)
        self.target_member_id = member.id; self.new_name = new_name; self.nicknames_cog = cog_instance
    async def _check_permission(self, interaction: discord.Interaction) -> bool:
        approval_role_id = self.nicknames_cog.approval_role_id
        if not approval_role_id or not isinstance(interaction.user, discord.Member) or not any(r.id == approval_role_id for r in interaction.user.roles):
            await interaction.response.send_message("❌ このボタンを押す権限がありません。", ephemeral=True); return False
        return True
    async def _handle_approval_flow(self, interaction: discord.Interaction, is_approved: bool):
        if not await self._check_permission(interaction): return
        member = interaction.guild.get_member(self.target_member_id)
        if not member:
            await interaction.response.send_message("❌ エラー: 対象のメンバーがサーバーに見つかりませんでした。", ephemeral=True)
            try: await interaction.message.delete()
            except discord.NotFound: pass
            return
        rejection_reason = None
        if not is_approved:
            modal = RejectionReasonModal(); await interaction.response.send_modal(modal)
            if await modal.wait(): return
            rejection_reason = modal.reason.value
        else: await interaction.response.defer()
        for item in self.children: item.disabled = True
        try: await interaction.message.edit(content=f"⏳ {interaction.user.mention}さんが処理中...", view=self)
        except (discord.NotFound, discord.HTTPException): pass
        final_name = await self.nicknames_cog.get_final_nickname(member, base_name=self.new_name)
        error_report = ""
        if is_approved:
            try: await member.edit(nick=final_name, reason=f"관리자({interaction.user}) 승인")
            except Exception as e: error_report += f"- 닉네임 변경 실패: `{type(e).__name__}: {e}`\n"
        log_embed = self._create_log_embed(member, interaction.user, final_name, is_approved, rejection_reason)
        try: await self._send_log_message(log_embed, member)
        except Exception as e: error_report += f"- 로그 메시지 전송 실패: `{type(e).__name__}: {e}`\n"
        status_text = "承認" if is_approved else "拒否"
        if error_report: await interaction.followup.send(f"❌ **{status_text} 처리 중 일부 작업에 실패했습니다:**\n{error_report}", ephemeral=True)
        else: await interaction.followup.send(f"✅ {status_text} 処理が正常に完了しました。", ephemeral=True)
        try: await interaction.message.delete()
        except discord.NotFound: pass
    def _create_log_embed(self, member: discord.Member, moderator: discord.Member, final_name: str, is_approved: bool, reason: Optional[str]) -> discord.Embed:
        if is_approved:
            embed = discord.Embed(title="✅ 名前変更のお知らせ (承認)", color=discord.Color.green())
            embed.add_field(name="変更後の名前", value=f"`{final_name}`", inline=True)
        else:
            embed = discord.Embed(title="❌ 名前変更のお知らせ (拒否)", color=discord.Color.red())
            embed.add_field(name="申請した名前", value=f"`{self.new_name}`", inline=True)
            embed.add_field(name="拒否理由", value=reason or "理由未入力", inline=False)
        embed.add_field(name="対象者", value=member.mention, inline=False); embed.add_field(name="処理者", value=moderator.mention, inline=False)
        return embed
    async def _send_log_message(self, result_embed: discord.Embed, target_member: discord.Member):
        if (log_ch_id := self.nicknames_cog.nickname_log_channel_id) and (log_ch := self.nicknames_cog.bot.get_channel(log_ch_id)):
            await log_ch.send(embed=result_embed)
        else: logger.warning("닉네임 로그 채널이 설정되지 않아 로그 메시지를 건너뜁니다.")
    @ui.button(label="承認", style=discord.ButtonStyle.success, custom_id="nick_approve")
    async def approve(self, i: discord.Interaction, b: ui.Button): await self._handle_approval_flow(i, is_approved=True)
    @ui.button(label="拒否", style=discord.ButtonStyle.danger, custom_id="nick_reject")
    async def reject(self, i: discord.Interaction, b: ui.Button): await self._handle_approval_flow(i, is_approved=False)

class NicknameChangeModal(ui.Modal, title="名前変更申請"):
    new_name = ui.TextInput(label="新しい名前", placeholder="絵文字・特殊文字は使用不可。合計8文字まで", required=True, max_length=12)
    def __init__(self, cog_instance: 'Nicknames'): super().__init__(); self.nicknames_cog = cog_instance
    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        name = self.new_name.value
        if not ALLOWED_NICKNAME_PATTERN.match(name): return await i.followup.send("❌ エラー: 名前に絵文字や特殊文字は使用できません。", ephemeral=True)
        if (length := calculate_weighted_length(name)) > 8: return await i.followup.send(f"❌ エラー: 名前の長さがルールを超えています。(現在: **{length}/8**)", ephemeral=True)
        if not self.nicknames_cog.approval_channel_id or not self.nicknames_cog.approval_role_id: return await i.followup.send("エラー: ニックネーム機能が正しく設定されていません。", ephemeral=True)
        if not (ch := i.guild.get_channel(self.nicknames_cog.approval_channel_id)): return await i.followup.send("エラー: 承認チャンネルが見つかりません。", ephemeral=True)
        await set_cooldown(str(i.user.id), "nickname_change", time.time())
        embed = discord.Embed(title="📝 名前変更申請", color=discord.Color.blue())
        embed.add_field(name="申請者", value=i.user.mention, inline=False).add_field(name="現在の名前", value=i.user.display_name, inline=False).add_field(name="希望の名前", value=name, inline=False)
        view = NicknameApprovalView(i.user, name, self.nicknames_cog)
        await ch.send(f"<@&{self.nicknames_cog.approval_role_id}> 新しい名前変更の申請があります。", embed=embed, view=view)
        await i.followup.send("名前の変更申請を提出しました。", ephemeral=True)

class NicknameChangerPanelView(ui.View):
    def __init__(self, cog_instance: 'Nicknames'): super().__init__(timeout=None); self.nicknames_cog = cog_instance
    @ui.button(label="名前変更申請", style=discord.ButtonStyle.primary, custom_id="nickname_change_button_v8")
    async def request_change(self, i: discord.Interaction, b: ui.Button):
        last_time = await get_cooldown(str(i.user.id), "nickname_change")
        if last_time and time.time() - last_time < COOLDOWN_SECONDS:
            rem = COOLDOWN_SECONDS - (time.time() - last_time)
            h, r = divmod(int(rem), 3600); m, _ = divmod(r, 60)
            return await i.response.send_message(f"次の申請まであと {h}時間{m}分 お待ちください。", ephemeral=True)
        await i.response.send_modal(NicknameChangeModal(self.nicknames_cog))

class Nicknames(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_channel_id: Optional[int] = None; self.approval_channel_id: Optional[int] = None
        self.approval_role_id: Optional[int] = None; self.nickname_log_channel_id: Optional[int] = None
        logger.info("Nicknames Cog가 성공적으로 초기화되었습니다.")
    def register_persistent_views(self):
        self.bot.add_view(NicknameChangerPanelView(self))
    async def cog_load(self): await self.load_all_configs()
    async def load_all_configs(self):
        self.panel_channel_id = get_id("nickname_panel_channel_id")
        self.approval_channel_id = get_id("nickname_approval_channel_id")
        self.nickname_log_channel_id = get_id("nickname_log_channel_id")
        self.approval_role_id = get_id("role_approval")
        logger.info("[Nicknames Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")
    async def get_final_nickname(self, member: discord.Member, base_name: str) -> str:
        prefix = None
        base = base_name.strip() or member.name
        nick = f"{prefix}{base}" if prefix else base
        if len(nick) > 32:
            prefix_len = len(prefix) if prefix else 0
            base = base[:32 - prefix_len]; nick = f"{prefix}{base}" if prefix else base
        return nick
    async def update_nickname(self, member: discord.Member, base_name_override: str):
        try:
            final_name = await self.get_final_nickname(member, base_name=base_name_override)
            if member.nick != final_name: await member.edit(nick=final_name, reason="온보딩 완료")
        except discord.Forbidden:
            logger.warning(f"Onboarding: {member.display_name}의 닉네임을 변경할 권한이 없습니다.")
            raise
        except Exception as e:
            logger.error(f"Onboarding: {member.display_name}의 닉네임 업데이트 실패: {e}", exc_info=True)
            raise
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if after.bot or before.roles == after.roles: return
        current_nick = after.nick or after.name
        base_name = current_nick
        new_nick = await self.get_final_nickname(after, base_name=base_name)
        if after.nick != new_nick:
            try: await after.edit(nick=new_nick, reason="역할 변경으로 인한 칭호 업데이트")
            except discord.Forbidden: pass
    async def regenerate_panel(self, channel: Optional[discord.TextChannel] = None):
        target_channel = channel
        if target_channel is None:
            channel_id = get_id("nickname_panel_channel_id")
            if channel_id: target_channel = self.bot.get_channel(channel_id)
            else: logger.info("ℹ️ 닉네임 패널 채널이 설정되지 않아, 자동 생성을 건너뜁니다."); return
        if not target_channel: logger.warning("❌ Nickname panel channel could not be found."); return
        panel_info = get_panel_id("nickname_changer")
        if panel_info and (old_id := panel_info.get('message_id')):
            try:
                old_message = await target_channel.fetch_message(old_id)
                await old_message.delete()
            except (discord.NotFound, discord.Forbidden): pass
            
        embed_data = await get_embed_from_db("panel_nicknames")
        if not embed_data:
            logger.warning("DB에서 'panel_nicknames' 임베드 데이터를 찾을 수 없어, 패널 생성을 건너뜁니다.")
            return
        embed = discord.Embed.from_dict(embed_data)
        
        view = NicknameChangerPanelView(self)
        new_message = await target_channel.send(embed=embed, view=view)
        await save_panel_id("nickname_changer", new_message.id, target_channel.id)
        logger.info(f"✅ 닉네임 패널을 성공적으로 새로 생성했습니다. (채널: #{target_channel.name})")

async def setup(bot: commands.Bot):
    await bot.add_cog(Nicknames(bot))
