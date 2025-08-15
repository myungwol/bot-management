# cogs/server/nicknames.py (버튼 비활성화 오류 수정 최종본)

import discord
from discord.ext import commands
from discord import app_commands, ui
import re
from datetime import timedelta
import time
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 데이터베이스 함수 임포트
from utils.database import (
    get_panel_id, save_panel_id, get_cooldown, set_cooldown, 
    get_channel_id_from_db, get_role_id, save_channel_id_to_db
)

# 설정값
ALLOWED_NICKNAME_PATTERN = re.compile(r"^[a-zA-Z0-9\u3040-\u309F\u30A0-\u30FF\u4e00-\u9faf]+$")
NICKNAME_PREFIX_HIERARCHY_NAMES = [
    "里長", "助役", "お巡り", "祭りの委員", "広報係", "意匠係", "書記", "役場の職員", "職員",
    "1等級住民", "2等級住民", "3等級住民", "住民"
]
COOLDOWN_SECONDS = 4 * 3600

def calculate_weighted_length(name: str) -> int:
    total_length = 0
    kanji_pattern = re.compile(r'[\u4e00-\u9faf]')
    for char in name:
        if kanji_pattern.match(char): total_length += 2
        else: total_length += 1
    return total_length

# --- View / Modal 클래스들 ---
class RejectionReasonModal(ui.Modal, title="拒否理由入力"):
    reason = ui.TextInput(label="拒否理由", placeholder="拒否する理由を具体的に入力してください。", style=discord.TextStyle.paragraph, required=True, max_length=200)
    async def on_submit(self, interaction: discord.Interaction):
        # [수정] 거절 사유 제출 시에는 defer()만 호출하고 followup은 reject 함수에서 처리
        await interaction.response.defer()

class NicknameApprovalView(ui.View):
    def __init__(self, member: discord.Member, new_name: str, bot: commands.Bot, approval_role_id: int):
        super().__init__(timeout=None)
        self.target_member_id = member.id
        self.new_name = new_name
        self.bot = bot
        self.approval_role_id = approval_role_id

    async def _check_permission(self, i: discord.Interaction) -> bool:
        if not self.approval_role_id or not isinstance(i.user, discord.Member) or not any(r.id == self.approval_role_id for r in i.user.roles):
            await i.response.send_message("このボタンを押す権한がありません。", ephemeral=True)
            return False
        return True

    async def _send_log_message(self, result_embed: discord.Embed, target_member: discord.Member):
        cog = self.bot.get_cog("Nicknames")
        if not cog or not cog.nickname_log_channel_id:
            logger.warning("Nickname log channel is not set. Skipping log message.")
            return

        if (log_ch := self.bot.get_channel(cog.nickname_log_channel_id)):
            try:
                await log_ch.send(content=target_member.mention, embed=result_embed, allowed_mentions=discord.AllowedMentions(users=True))
            except Exception as e:
                logger.error(f"Failed to send nickname result log: {e}", exc_info=True)

    @ui.button(label="承認", style=discord.ButtonStyle.success)
    async def approve(self, i: discord.Interaction, b: ui.Button):
        if not await self._check_permission(i): return
        await i.response.defer()

        member = i.guild.get_member(self.target_member_id)
        if not member:
            await i.followup.send("エラー: 対象のメンバーがサーバーに見つかりませんでした。", ephemeral=True)
            try: await i.message.delete()
            except discord.NotFound: pass
            return
            
        # [수정된 부분] item.disable() -> item.disabled = True
        for item in self.children:
            item.disabled = True
        try: await i.edit_original_response(view=self)
        except discord.NotFound: pass
        
        try:
            cog = self.bot.get_cog("Nicknames")
            final_name = await cog.get_final_nickname(member, base_name_override=self.new_name)
            await member.edit(nick=final_name)
        except Exception as e:
            await i.followup.send(f"ニックネームの変更中にエラーが発生しました: {e}", ephemeral=True)
            return
            
        embed = discord.Embed(title="✅ 名前変更のお知らせ (承認)", color=discord.Color.green())
        embed.add_field(name="対象者", value=member.mention, inline=False)
        embed.add_field(name="変更後の名前", value=f"`{final_name}`", inline=True)
        embed.add_field(name="承認者", value=f"{i.user.mention} (公務員)", inline=False)
        
        await self._send_log_message(embed, target_member=member)
        try: await i.message.delete()
        except discord.NotFound: pass

    @ui.button(label="拒否", style=discord.ButtonStyle.danger)
    async def reject(self, i: discord.Interaction, b: ui.Button):
        if not await self._check_permission(i): return

        member = i.guild.get_member(self.target_member_id)
        if not member:
            await i.response.send_message("エラー: 対象のメンバーがサーバーに見つかりませんでした。", ephemeral=True)
            try: await i.message.delete()
            except discord.NotFound: pass
            return

        modal = RejectionReasonModal(); await i.response.send_modal(modal)
        # modal.wait()는 modal이 닫힐 때까지 기다림
        timed_out = await modal.wait()
        if timed_out or modal.reason.value is None:
            # 타임아웃 되거나 모달이 그냥 닫히면 아무것도 안 함
            return
        
        # [수정된 부분] item.disable() -> item.disabled = True
        for item in self.children:
            item.disabled = True
        try: await i.edit_original_response(view=self)
        except discord.NotFound: pass
        
        embed = discord.Embed(title="❌ 名前変更のお知らせ (拒否)", color=discord.Color.red())
        embed.add_field(name="対象者", value=member.mention, inline=False)
        embed.add_field(name="申請した名前", value=f"`{self.new_name}`", inline=True)
        embed.add_field(name="拒否理由", value=modal.reason.value, inline=False)
        embed.add_field(name="処理者", value=f"{i.user.mention} (公務員)", inline=False)
        
        await self._send_log_message(embed, target_member=member)
        try: await i.message.delete()
        except discord.NotFound: pass

class NicknameChangeModal(ui.Modal, title="名前変更申請"):
    new_name = ui.TextInput(label="新しい名前", placeholder="絵文字・特殊文字は使用不可。合計8文字まで", required=True, max_length=12)
    def __init__(self, approval_role_id: int): super().__init__(); self.approval_role_id = approval_role_id
    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        name = self.new_name.value
        if not ALLOWED_NICKNAME_PATTERN.match(name): return await i.followup.send("❌ エラー: 名前に絵文字や特殊文字は使用できません。", ephemeral=True)
        if (length := calculate_weighted_length(name)) > 8: return await i.followup.send(f"❌ エラー: 名前の長さがルールを超えています。(現在: **{length}/8**)", ephemeral=True)
        
        cog = i.client.get_cog("Nicknames")
        if not cog or not cog.approval_channel_id or not cog.approval_role_id:
            return await i.followup.send("エラー: ニックネーム機能が正しく設定されていません。", ephemeral=True)
        if not (ch := i.guild.get_channel(cog.approval_channel_id)):
            return await i.followup.send("エラー: 承認チャンネルが見つかりません。", ephemeral=True)
            
        await set_cooldown(str(i.user.id), time.time())
        embed = discord.Embed(title="📝 名前変更申請", color=discord.Color.blue())
        embed.add_field(name="申請者", value=i.user.mention, inline=False).add_field(name="現在の名前", value=i.user.display_name, inline=False).add_field(name="希望の名前", value=name, inline=False)
        
        applicant_member = i.guild.get_member(i.user.id)
        if not applicant_member:
             return await i.followup.send("エラー: 申請者情報を見つけられません。", ephemeral=True)

        await ch.send(f"<@&{self.approval_role_id}> 新しい名前変更の申請があります。", embed=embed, view=NicknameApprovalView(applicant_member, name, i.client, self.approval_role_id))
        await i.followup.send("名前の変更申請を提出しました。", ephemeral=True)

class NicknameChangerPanelView(ui.View):
    def __init__(self): super().__init__(timeout=None)
    @ui.button(label="名前変更申請", style=discord.ButtonStyle.primary, custom_id="nickname_change_button_v8")
    async def request_change(self, i: discord.Interaction, b: ui.Button):
        last_time = await get_cooldown(str(i.user.id))
        if last_time and time.time() - last_time < COOLDOWN_SECONDS:
            remaining = COOLDOWN_SECONDS - (time.time() - last_time)
            h, rem = divmod(int(remaining), 3600); m, _ = divmod(rem, 60)
            return await i.response.send_message(f"次の申請まであと {h}時間{m}分 お待ちください。", ephemeral=True)
        cog = i.client.get_cog("Nicknames")
        if not cog or not cog.approval_role_id: return await i.response.send_message("エラー: 機能が設定されていません。", ephemeral=True)
        await i.response.send_modal(NicknameChangeModal(approval_role_id=cog.approval_role_id))

# --- メイン Cog 클래스 ---
class Nicknames(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot; self.bot.add_view(NicknameChangerPanelView())
        self.panel_and_result_channel_id: int | None = None
        self.approval_channel_id: int | None = None
        self.approval_role_id: int | None = None
        self.nickname_log_channel_id: int | None = None
        logger.info("Nicknames Cog initialized.")
        
    async def cog_load(self): await self.load_nickname_channel_configs()
    
    async def load_nickname_channel_configs(self):
        self.panel_and_result_channel_id = await get_channel_id_from_db("nickname_panel_channel_id")
        self.approval_channel_id = await get_channel_id_from_db("nickname_approval_channel_id")
        self.nickname_log_channel_id = await get_channel_id_from_db("nickname_log_channel_id")
        self.approval_role_id = get_role_id("approval_role")
        logger.info(f"[Nicknames Cog] Loaded Configs: Panel={self.panel_and_result_channel_id}, Approval={self.approval_channel_id}, Log={self.nickname_log_channel_id}")
        
    async def get_final_nickname(self, member: discord.Member, base_name: str) -> str:
        prefix = next((p for p in NICKNAME_PREFIX_HIERARCHY_NAMES if discord.utils.get(member.roles, name=p)), None)
        base = base_name.strip() or member.name
        nick = f"『{prefix}』{base}" if prefix else base
        if len(nick) > 32:
            prefix_len = len(f"『{prefix}』") if prefix else 0
            base = base[:32 - prefix_len]
            nick = f"『{prefix}』{base}" if prefix else base
        return nick
        
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if after.bot or before.roles == after.roles: return
        base_name = (after.nick or after.name).split('』')[-1].strip()
        new_nick = await self.get_final_nickname(after, base_name)
        if after.nick != new_nick:
            try: await after.edit(nick=new_nick)
            except discord.Forbidden: pass
            
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot: return; await asyncio.sleep(2)
        new_nick = await self.get_final_nickname(member, member.name)
        if member.nick != new_nick:
            try: await member.edit(nick=new_nick)
            except discord.Forbidden: pass
            
    async def regenerate_panel(self, channel: discord.TextChannel | None = None):
        if channel is None:
            if self.panel_and_result_channel_id: channel = self.bot.get_channel(self.panel_and_result_channel_id)
            else: logger.info("ℹ️ Nickname panel channel not set, skipping auto-regeneration."); return
        if not channel: logger.warning("❌ Nickname panel channel could not be found."); return
        
        panel_info = await get_panel_id("nickname_changer")
        if panel_info and (old_id := panel_info.get('message_id')):
            try:
                message_to_delete = await channel.fetch_message(old_id)
                await message_to_delete.delete()
            except (discord.NotFound, discord.Forbidden):
                pass
            
        embed = discord.Embed(title="📝 名前変更案内", description="サーバーで使用する名前を変更したい場合は、下のボタンを押して申請してください。", color=discord.Color.blurple())
        msg = await channel.send(embed=embed, view=NicknameChangerPanelView())
        await save_panel_id("nickname_changer", msg.id, channel.id)
        logger.info(f"✅ Nickname panel successfully regenerated in channel {channel.name}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Nicknames(bot))
