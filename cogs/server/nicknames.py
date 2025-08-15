# cogs/server/nicknames.py (명령어 통합 최종본)

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
        await interaction.response.defer()

class NicknameApprovalView(ui.View):
    def __init__(self, member: discord.Member, new_name: str, bot: commands.Bot, approval_role_id: int):
        super().__init__(timeout=None)
        self.target_member = member; self.new_name = new_name; self.bot = bot
        self.original_name = member.display_name; self.approval_role_id = approval_role_id

    async def _check_permission(self, i: discord.Interaction) -> bool:
        if not self.approval_role_id or not isinstance(i.user, discord.Member) or not any(r.id == self.approval_role_id for r in i.user.roles):
            await i.response.send_message("このボタンを押す権限がありません。", ephemeral=True)
            return False
        return True

    async def _send_result_and_refresh(self, result_embed: discord.Embed):
        cog = self.bot.get_cog("Nicknames")
        if not cog: return

        # 1. 로그 메시지 전송 (지정된 로그 채널이 있으면 그곳으로, 없으면 패널 채널로)
        log_channel_id = cog.nickname_log_channel_id or cog.panel_and_result_channel_id
        if log_channel_id and (log_ch := self.bot.get_channel(log_channel_id)):
            try:
                await log_ch.send(content=self.target_member.mention, embed=result_embed, allowed_mentions=discord.AllowedMentions(users=True))
            except Exception as e:
                logger.error(f"Failed to send nickname result log: {e}", exc_info=True)

        # 2. 패널 자동 재생성 (별도의 로그 채널을 사용하지 않을 경우에만, 패널을 맨 아래로 내리기 위해)
        if not cog.nickname_log_channel_id:
            if cog.panel_and_result_channel_id and (panel_ch := self.bot.get_channel(cog.panel_and_result_channel_id)):
                try:
                    await cog.regenerate_panel(panel_ch)
                except Exception as e:
                    logger.error(f"Failed to regenerate nickname panel after result: {e}", exc_info=True)


    @ui.button(label="承認", style=discord.ButtonStyle.success)
    async def approve(self, i: discord.Interaction, b: ui.Button):
        if not await self._check_permission(i): return
        await i.response.defer(); [item.disable() for item in self.children]
        try: await i.edit_original_response(view=self)
        except discord.NotFound: pass
        
        final_name = self.new_name
        try:
            cog = self.bot.get_cog("Nicknames")
            final_name = await cog.get_final_nickname(self.target_member, base_name_override=self.new_name)
            await self.target_member.edit(nick=final_name)
        except Exception as e: return await i.followup.send(f"ニックネームの変更中にエラー: {e}", ephemeral=True)
            
        embed = discord.Embed(title="✅ 名前変更のお知らせ (承認)", color=discord.Color.green())
        embed.add_field(name="対象者", value=self.target_member.mention, inline=False)
        embed.add_field(name="変更後の名前", value=f"`{final_name}`", inline=True)
        embed.add_field(name="承認者", value=f"{i.user.mention} (公務員)", inline=False)
        await self._send_result_and_refresh(embed)
        try: await i.message.delete()
        except discord.NotFound: pass

    @ui.button(label="拒否", style=discord.ButtonStyle.danger)
    async def reject(self, i: discord.Interaction, b: ui.Button):
        if not await self._check_permission(i): return
        modal = RejectionReasonModal(); await i.response.send_modal(modal)
        if await modal.wait(): return
        [item.disable() for item in self.children]
        try: await i.message.edit(view=self)
        except discord.NotFound: pass
        embed = discord.Embed(title="❌ 名前変更のお知らせ (拒否)", color=discord.Color.red())
        embed.add_field(name="対象者", value=self.target_member.mention, inline=False)
        embed.add_field(name="申請した名前", value=f"`{self.new_name}`", inline=True)
        embed.add_field(name="拒否理由", value=modal.reason.value, inline=False)
        embed.add_field(name="処理者", value=f"{i.user.mention} (公務員)", inline=False)
        await self._send_result_and_refresh(embed)
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
        if not cog or not cog.approval_channel_id or not cog.approval_role_id: return await i.followup.send("エラー: ニックネーム機能が正しく設定されていません。", ephemeral=True)
        if not (ch := i.guild.get_channel(cog.approval_channel_id)): return await i.followup.send("エラー: 承認チャンネルが見つかりません。", ephemeral=True)
        await set_cooldown(str(i.user.id), time.time())
        embed = discord.Embed(title="📝 名前変更申請", color=discord.Color.blue())
        embed.add_field(name="申請者", value=i.user.mention, inline=False).add_field(name="現在の名前", value=i.user.display_name, inline=False).add_field(name="希望の名前", value=name, inline=False)
        await ch.send(f"<@&{self.approval_role_id}> 新しい名前変更の申請があります。", embed=embed, view=NicknameApprovalView(i.user, name, i.client, self.approval_role_id))
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

# --- 메인 Cog 클래스 ---
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
