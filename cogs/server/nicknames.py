# cogs/server/nicknames.py (최종 수정본 - 쿨타임 로직 수정)

import discord
from discord.ext import commands
from discord import app_commands, ui
import re
from datetime import timedelta
import time
import logging

# 로깅 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

from utils.database import (get_panel_id, save_panel_id, get_cooldown, set_cooldown, 
                           get_channel_id_from_db, get_role_id, save_channel_id_to_db)

ALLOWED_NICKNAME_PATTERN = re.compile(r"^[a-zA-Z0-9\u3040-\u309F\u30A0-\u30FF\u4e00-\u9faf]+$")

def calculate_weighted_length(name: str) -> int:
    total_length = 0
    kanji_pattern = re.compile(r'[\u4e00-\u9faf]')
    for char in name:
        if kanji_pattern.match(char): total_length += 2
        else: total_length += 1
    return total_length

NICKNAME_PREFIX_HIERARCHY_NAMES = [
    "里長", "助役", "お巡り", "祭りの委員", "広報係", "意匠係", "書記", "役場の職員", "職員",
    "1等級住民", "2等級住民", "3等級住民", "住民"
]
COOLDOWN_SECONDS = 4 * 3600

class RejectionReasonModal(ui.Modal, title="拒否理由入力"):
    reason = ui.TextInput(label="拒否理由", placeholder="拒否する理由を具体的に入力してください。", style=discord.TextStyle.paragraph, required=True, max_length=200)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

class NicknameApprovalView(ui.View):
    def __init__(self, member: discord.Member, new_name: str, bot: commands.Bot, approval_role_id: int):
        super().__init__(timeout=None)
        self.target_member = member
        self.new_name = new_name
        self.bot = bot
        self.original_name = member.display_name
        self.approval_role_id = approval_role_id

    async def _check_permission(self, interaction: discord.Interaction) -> bool:
        if not self.approval_role_id:
            await interaction.response.send_message("エラー: 承認役割IDが設定されていません。", ephemeral=True)
            return False
        if not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message("この操作はサーバー内でのみ実行できます。", ephemeral=True)
            return False
        if not any(role.id == self.approval_role_id for role in interaction.user.roles):
            await interaction.response.send_message("このボタンを押す権限がありません。", ephemeral=True)
            return False
        return True

    async def _send_result_and_refresh(self, result_embed: discord.Embed):
        nicknames_cog = self.bot.get_cog("Nicknames")
        if not nicknames_cog or not nicknames_cog.panel_and_result_channel_id: 
            logger.error("Nicknames Cog or result channel ID not found.")
            return
        result_channel = self.bot.get_channel(nicknames_cog.panel_and_result_channel_id)
        if result_channel:
            try:
                await result_channel.send(content=self.target_member.mention, embed=result_embed, allowed_mentions=discord.AllowedMentions(users=True))
                await nicknames_cog.regenerate_panel(result_channel)
            except Exception as e:
                logger.error(f"Failed to send result or regenerate panel: {e}", exc_info=True)

    @ui.button(label="承認", style=discord.ButtonStyle.success, custom_id="nick_approve_v8")
    async def approve(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check_permission(interaction): return
        await interaction.response.defer()
        for item in self.children: item.disabled = True
        try: await interaction.edit_original_response(view=self)
        except discord.NotFound: pass
        try:
            nicknames_cog = self.bot.get_cog("Nicknames")
            if not nicknames_cog: raise RuntimeError("Nicknames Cog not found.")
            await nicknames_cog.update_nickname(self.target_member, base_name_override=self.new_name, force_update=True)
            updated_member = await interaction.guild.fetch_member(self.target_member.id)
            final_name = updated_member.display_name
        except Exception as e:
            await interaction.followup.send(f"ニックネームの変更中にエラー: {e}", ephemeral=True)
            return
        result_embed = discord.Embed(title="✅ 名前変更のお知らせ (承認)", color=discord.Color.green())
        result_embed.add_field(name="対象者", value=self.target_member.mention, inline=False)
        result_embed.add_field(name="変更前の名前", value=f"`{self.original_name}`", inline=True)
        result_embed.add_field(name="変更後の名前", value=f"`{final_name}`", inline=True)
        result_embed.set_footer(text=f"承認者: {interaction.user.display_name} (公務員)")
        await self._send_result_and_refresh(result_embed)
        try: await interaction.message.delete()
        except discord.NotFound: pass

    @ui.button(label="拒否", style=discord.ButtonStyle.danger, custom_id="nick_reject_v8")
    async def reject(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check_permission(interaction): return
        modal = RejectionReasonModal()
        await interaction.response.send_modal(modal)
        if await modal.wait(): return
        for item in self.children: item.disabled = True
        try: await interaction.message.edit(view=self)
        except discord.NotFound: pass
        result_embed = discord.Embed(title="❌ 名前変更のお知らせ (拒否)", color=discord.Color.red())
        result_embed.add_field(name="対象者", value=self.target_member.mention, inline=False)
        result_embed.add_field(name="申請した名前", value=f"`{self.new_name}`", inline=True)
        result_embed.add_field(name="現在の名前", value=f"`{self.original_name}`", inline=True)
        result_embed.add_field(name="拒否理由", value=modal.reason.value, inline=False)
        result_embed.set_footer(text=f"処理者: {interaction.user.display_name} (公務員)")
        await self._send_result_and_refresh(result_embed)
        try: await interaction.message.delete()
        except discord.NotFound: pass

class NicknameChangeModal(ui.Modal, title="名前変更申請"):
    new_name = ui.TextInput(label="新しい名前", placeholder="絵文字・特殊文字は使用不可。合計8文字まで", required=True, max_length=12)
    def __init__(self, approval_role_id: int):
        super().__init__()
        self.approval_role_id = approval_role_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        new_name_value = self.new_name.value
        if not ALLOWED_NICKNAME_PATTERN.match(new_name_value):
            return await interaction.followup.send("❌ エラー: 名前に絵文字や特殊文字は使用できません。", ephemeral=True)
        weighted_length = calculate_weighted_length(new_name_value)
        if weighted_length > 8:
            error_message = f"❌ エラー: 名前の長さがルールを超えています。\nルール: 合計8文字まで (漢字は2文字として計算)\n現在の文字数: **{weighted_length}/8**"
            return await interaction.followup.send(error_message, ephemeral=True)

        nicknames_cog = interaction.client.get_cog("Nicknames")
        if not nicknames_cog or not nicknames_cog.approval_channel_id or not nicknames_cog.approval_role_id:
            return await interaction.followup.send("エラー: ニックネーム機能が正しく設定されていません。管理者が設定を確認してください。", ephemeral=True)
        approval_channel = interaction.guild.get_channel(nicknames_cog.approval_channel_id)
        if not approval_channel:
            return await interaction.followup.send("エラー: 承認チャンネルが見つかりません。", ephemeral=True)
        
        # [핵심] 신청서가 정상적으로 제출된 이 시점에 쿨타임을 적용
        await set_cooldown(str(interaction.user.id), time.time())
        
        embed = discord.Embed(title="📝 名前変更申請", color=discord.Color.blue())
        embed.add_field(name="申請者", value=interaction.user.mention, inline=False)
        embed.add_field(name="現在の名前", value=interaction.user.display_name, inline=False)
        embed.add_field(name="希望の名前", value=new_name_value, inline=False)
        await approval_channel.send(
            content=f"<@&{self.approval_role_id}> 新しい名前変更の申請があります。",
            embed=embed,
            view=NicknameApprovalView(member=interaction.user, new_name=new_name_value, bot=interaction.client, approval_role_id=self.approval_role_id)
        )
        await interaction.followup.send("名前の変更申請を提出しました。", ephemeral=True)

class NicknameChangerPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @ui.button(label="名前変更申請", style=discord.ButtonStyle.primary, custom_id="nickname_change_button_v8")
    async def request_change(self, interaction: discord.Interaction, button: ui.Button):
        user_id_str = str(interaction.user.id)
        last_request_time = await get_cooldown(user_id_str)
        if last_request_time and time.time() - last_request_time < COOLDOWN_SECONDS:
            remaining_time = COOLDOWN_SECONDS - (time.time() - last_request_time)
            hours, remainder = divmod(int(remaining_time), 3600)
            minutes, seconds = divmod(remainder, 60)
            if hours > 0: remaining_td_str = f"{hours}時間{minutes}分"
            elif minutes > 0: remaining_td_str = f"{minutes}分{seconds}秒"
            else: remaining_td_str = f"{seconds}秒"
            return await interaction.response.send_message(f"次の申請まであと {remaining_td_str} お待ちください。", ephemeral=True)
        
        nicknames_cog = interaction.client.get_cog("Nicknames")
        if not nicknames_cog or not nicknames_cog.approval_role_id:
            return await interaction.response.send_message("エラー: ニックネーム変更機能が設定されていません。管理者が設定を確認してください。", ephemeral=True)
        
        # [수정] 버튼 클릭 시점에서는 쿨타임을 적용하지 않음
        await interaction.response.send_modal(NicknameChangeModal(approval_role_id=nicknames_cog.approval_role_id))

class Nicknames(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(NicknameChangerPanelView())
        self.panel_and_result_channel_id: int | None = None
        self.approval_channel_id: int | None = None
        self.approval_role_id: int | None = None
        logger.info("Nicknames Cog initialized.")

    async def cog_load(self):
        await self.load_nickname_channel_configs()

    async def load_nickname_channel_configs(self):
        self.panel_and_result_channel_id = await get_channel_id_from_db("nickname_panel_channel_id")
        self.approval_channel_id = await get_channel_id_from_db("nickname_approval_channel_id")
        self.approval_role_id = get_role_id("approval_role")
        logger.info(f"[Nicknames Cog] Loaded PANEL_AND_RESULT_CHANNEL_ID: {self.panel_and_result_channel_id}")
        logger.info(f"[Nicknames Cog] Loaded APPROVAL_CHANNEL_ID: {self.approval_channel_id}")
        logger.info(f"[Nicknames Cog] Loaded APPROVAL_ROLE_ID: {self.approval_role_id}")

    async def update_nickname(self, member: discord.Member, base_name_override: str = None, force_update: bool = False):
        if member.bot or member.id == member.guild.owner_id or member.guild.me.top_role <= member.top_role: return
        chosen_prefix_name = None
        for role_name_in_hierarchy in NICKNAME_PREFIX_HIERARCHY_NAMES:
            if discord.utils.get(member.roles, name=role_name_in_hierarchy):
                chosen_prefix_name = role_name_in_hierarchy
                break
        base_name = base_name_override
        if base_name is None:
            current_display_name = member.nick or member.name
            match = re.match(r"^『([^』]+)』\s*(.*)$", current_display_name)
            if match: base_name = match.group(2).strip()
            else: base_name = current_display_name.strip()
        if not base_name: base_name = member.name
        new_nickname = f"『{chosen_prefix_name}』{base_name}" if chosen_prefix_name else base_name
        if len(new_nickname) > 32:
            prefix_len = len(f"『{chosen_prefix_name}』") if chosen_prefix_name else 0
            max_base_len = 32 - prefix_len
            base_name = base_name[:max_base_len]
            new_nickname = f"『{chosen_prefix_name}』{base_name}" if chosen_prefix_name else base_name
        if force_update or member.nick != new_nickname:
            try:
                await member.edit(nick=new_nickname)
                logger.info(f"Updated nickname for {member.display_name} to '{new_nickname}'. (Forced: {force_update})")
            except discord.Forbidden: logger.warning(f"Failed to update nickname for {member.name}: Missing Permissions.")
            except Exception as e: logger.error(f"Error during nickname change for {member.name}: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if after.bot: return
        if before.nick != after.nick:
            await self.update_nickname(after, force_update=True)
        elif before.roles != after.roles:
            await self.update_nickname(after)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot: return
        await asyncio.sleep(2)
        await self.update_nickname(member)

    async def regenerate_panel(self, channel: discord.TextChannel):
        old_id = await get_panel_id("nickname_changer")
        if old_id:
            try:
                old_message = await channel.fetch_message(old_id)
                await old_message.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                logger.warning(f"Could not delete old nickname panel message {old_id}: {e}")
        embed = discord.Embed(title="📝 名前変更案内", description="サーバーで使用する名前を変更したい場合は、下のボタンを押して申請してください。", color=discord.Color.blurple())
        msg = await channel.send(embed=embed, view=NicknameChangerPanelView())
        await save_panel_id("nickname_changer", msg.id)
        logger.info(f"Nickname panel regenerated in channel {channel.name} with new message ID: {msg.id}")

    nick_setup_group = app_commands.Group(name="nick-setup", description="ニックネーム機能のチャンネルなどを設定します。")
    @nick_setup_group.command(name="channels", description="[管理者専用] ニックネーム機能に必要なチャンネルを設定します。")
    @app_commands.describe(panel_channel="パネルを設置するチャンネル", approval_channel="申請を承認/拒否するチャンネル")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_channels(self, interaction: discord.Interaction, panel_channel: discord.TextChannel, approval_channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        await save_channel_id_to_db("nickname_panel_channel_id", panel_channel.id)
        await save_channel_id_to_db("nickname_approval_channel_id", approval_channel.id)
        await self.load_nickname_channel_configs()
        await interaction.followup.send(f"✅ ニックネーム機能のチャンネルが設定されました。\n- **パネル設置チャンネル:** {panel_channel.mention}\n- **申請承認チャンネル:** {approval_channel.mention}\n\n次に `{panel_channel.mention}` で `/名前変更パネル設置` コマンドを実行してください。")

    @app_commands.command(name="名前変更パネル設置", description="ニックネーム変更申請パネルを設置します。")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_nickname_panel_command(self, i: discord.Interaction):
        if self.panel_and_result_channel_id is None:
            return await i.response.send_message("エラー: まず `/nick-setup channels` コマンドでパネル設置チャンネルを設定してください。", ephemeral=True)
        if i.channel.id != self.panel_and_result_channel_id:
            return await i.response.send_message(f"このコマンドは<#{self.panel_and_result_channel_id}>でのみ使用できます。", ephemeral=True)
        await i.response.defer(ephemeral=True)
        try:
            await self.regenerate_panel(i.channel)
            await i.followup.send("名前変更パネルを正常に設置しました。", ephemeral=True)
        except Exception as e:
            logger.error("Error during nickname panel setup command.", exc_info=True)
            await i.followup.send(f"❌ パネル設置中にエラーが発生しました: {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    cog = Nicknames(bot)
    await bot.add_cog(cog)
