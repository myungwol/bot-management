# cogs/features/voice_master.py
"""
음성 채널 자동 생성 및 제어판(Voice Master) 기능을 담당하는 Cog입니다.
제어판은 음성 채널에 연결된 텍스트 채팅 채널에 생성됩니다.
"""
import discord
from discord.ext import commands
from discord import ui
import logging
from typing import Dict, Optional, List

from utils.database import get_id

logger = logging.getLogger(__name__)


# --- 모달 및 선택 메뉴 UI 클래스들 ---

class VCEditModal(ui.Modal, title="🔊 ボイスチャンネル設定"):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.submitted = False

    name = ui.TextInput(label="チャンネル名", placeholder="新しいチャンネル名を入力してください。", required=False, max_length=100)
    limit = ui.TextInput(label="最大入室人数", placeholder="数字を入力 (例: 5)。0は無制限です。", required=False, max_length=2)

    async def on_submit(self, interaction: discord.Interaction):
        self.submitted = True
        await interaction.response.defer(ephemeral=True)

# [신규] 블랙리스트에 '추가'할 멤버를 선택하는 드롭다운
class VCAddBlacklistSelect(ui.UserSelect):
    def __init__(self, panel_view: 'ControlPanelView'):
        self.panel_view = panel_view
        super().__init__(placeholder="ブラックリストに追加するメンバーを選択...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        target_member = self.values[0]
        vc = self.panel_view.cog.bot.get_channel(self.panel_view.vc_id)

        if not vc or not isinstance(target_member, discord.Member):
            return await interaction.followup.send("❌ チャンネルまたはメンバーが見つかりませんでした。", ephemeral=True)

        if target_member.id == self.panel_view.owner_id:
            return await interaction.followup.send("❌ チャンネルの所有者をブラックリストに追加することはできません。", ephemeral=True)

        await vc.set_permissions(target_member, view_channel=False, reason=f"{interaction.user.display_name}がブラックリストに追加")
        if target_member in vc.members:
            await target_member.move_to(None, reason="ブラックリストに追加されたため")
        
        await interaction.followup.send(f"✅ {target_member.mention} さんをブラックリストに追加しました。", ephemeral=True)
        try:
            await interaction.delete_original_response()
        except discord.NotFound:
            pass

# [신규] 블랙리스트에서 '해제'할 멤버를 선택하는 드롭다운
class VCRemoveBlacklistSelect(ui.Select):
    def __init__(self, panel_view: 'ControlPanelView', blacklisted_members: List[discord.Member]):
        self.panel_view = panel_view
        options = [
            discord.SelectOption(label=member.display_name, value=str(member.id))
            for member in blacklisted_members
        ]
        super().__init__(placeholder="ブラックリストから解除するメンバーを選択...", min_values=1, max_values=len(options), options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        vc = self.panel_view.cog.bot.get_channel(self.panel_view.vc_id)
        if not vc: return await interaction.followup.send("❌ チャンネルが見つかりませんでした。", ephemeral=True)

        removed_members = []
        for member_id_str in self.values:
            member_id = int(member_id_str)
            target_member = interaction.guild.get_member(member_id)
            if target_member:
                await vc.set_permissions(target_member, overwrite=None, reason=f"{interaction.user.display_name}がブラックリストから解除")
                removed_members.append(target_member.mention)
        
        if removed_members:
            await interaction.followup.send(f"✅ {', '.join(removed_members)} さんをブラックリストから解除しました。", ephemeral=True)
        
        try:
            await interaction.delete_original_response()
        except discord.NotFound:
            pass

# [신규] 새로운 소유자를 선택하는 드롭다운
class VCOwnerSelect(ui.UserSelect):
    def __init__(self, panel_view: 'ControlPanelView'):
        self.panel_view = panel_view
        super().__init__(placeholder="新しい所有者を選択してください...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        new_owner = self.values[0]

        if not isinstance(new_owner, discord.Member): return

        if new_owner.id == self.panel_view.owner_id:
            return await interaction.followup.send("❌ すでにあなたが所有者です。", ephemeral=True)
        if new_owner.bot:
            return await interaction.followup.send("❌ ボットに所有権を移譲することはできません。", ephemeral=True)

        vc = self.panel_view.cog.bot.get_channel(self.panel_view.vc_id)
        if vc:
            await self.panel_view.cog._transfer_ownership(interaction, vc, new_owner)

        try:
            await interaction.delete_original_response()
        except discord.NotFound:
            pass


# --- 메인 제어판 View ---

class ControlPanelView(ui.View):
    def __init__(self, cog: 'VoiceMaster', owner_id: int, vc_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.owner_id = owner_id
        self.vc_id = vc_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.cog.bot.get_channel(self.vc_id) is None:
            await interaction.response.send_message("❌ このチャンネルはすでに削除されています。", ephemeral=True, view=None)
            self.stop()
            return False
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ このチャンネルの所有者のみが操作できます。", ephemeral=True)
            return False
        return True

    @ui.button(label="設定", style=discord.ButtonStyle.primary, emoji="⚙️", custom_id="vc_edit", row=0)
    async def edit_channel(self, interaction: discord.Interaction, button: ui.Button):
        vc = self.cog.bot.get_channel(self.vc_id)
        if not vc: return

        modal = VCEditModal()
        modal.name.default = vc.name.split("︱")[-1].strip()
        modal.limit.default = str(vc.user_limit)
        await interaction.response.send_modal(modal)
        await modal.wait()

        if modal.submitted:
            vc = self.cog.bot.get_channel(self.vc_id)
            if not vc: return await interaction.followup.send("❌ 処理中にチャンネルが見つからなくなりました。", ephemeral=True)

            new_name = f"🔊︱{modal.name.value or vc.name.split('︱')[-1].strip()}"
            try:
                new_limit = int(modal.limit.value or vc.user_limit)
                if not (0 <= new_limit <= 99): raise ValueError()
                info = self.cog.temp_channels.get(self.vc_id, {})
                min_limit = info.get("min_limit", 0)
                if 0 < new_limit < min_limit:
                    return await interaction.followup.send(f"❌ このチャンネルは最低{min_limit}人が必要です。それより少ない人数には設定できません。", ephemeral=True)
            except (ValueError, TypeError):
                return await interaction.followup.send("❌ 人数制限は0から99までの数字で入力してください。", ephemeral=True)

            await vc.edit(name=new_name, user_limit=new_limit, reason=f"{interaction.user.display_name}の要請")
            await interaction.followup.send("✅ チャンネル名と人数制限を更新しました。", ephemeral=True)

    @ui.button(label="ブラックリスト追加", style=discord.ButtonStyle.danger, emoji="🚫", custom_id="vc_add_blacklist", row=1)
    async def add_to_blacklist(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View(timeout=180)
        view.add_item(VCAddBlacklistSelect(self))
        await interaction.response.send_message("ブラックリストに追加するメンバーを選んでください。", view=view, ephemeral=True)

    @ui.button(label="ブラックリスト解除", style=discord.ButtonStyle.secondary, emoji="🛡️", custom_id="vc_remove_blacklist", row=1)
    async def remove_from_blacklist(self, interaction: discord.Interaction, button: ui.Button):
        vc = self.cog.bot.get_channel(self.vc_id)
        if not vc or not interaction.guild: return
        
        blacklisted_members = [
            target for target, overwrite in vc.overwrites.items()
            if isinstance(target, discord.Member) and overwrite.view_channel is False
        ]

        if not blacklisted_members:
            return await interaction.response.send_message("ℹ️ ブラックリストに登録されているメンバーはいません。", ephemeral=True)

        view = ui.View(timeout=180)
        view.add_item(VCRemoveBlacklistSelect(self, blacklisted_members))
        await interaction.response.send_message("ブラックリストから解除するメンバーを選んでください。", view=view, ephemeral=True)

    @ui.button(label="所有権移譲", style=discord.ButtonStyle.secondary, emoji="👑", custom_id="vc_transfer", row=0)
    async def transfer_owner(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View(timeout=180)
        view.add_item(VCOwnerSelect(self))
        await interaction.response.send_message("新しい所有者を選んでください。", view=view, ephemeral=True)


# --- VoiceMaster Cog ---

class VoiceMaster(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.creator_channel_ids: Dict[int, int] = {}
        self.temp_channels: Dict[int, Dict] = {}
        self.bot.add_view(ControlPanelView(self, 0, 0))
        logger.info("VoiceMaster Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        await self.load_configs()

    async def load_configs(self):
        creator_3p = get_id("vc_creator_channel_id_3p")
        creator_4p = get_id("vc_creator_channel_id_4p")
        if creator_3p: self.creator_channel_ids[creator_3p] = 3
        if creator_4p: self.creator_channel_ids[creator_4p] = 4
        logger.info(f"[VoiceMaster] 생성 채널 ID를 로드했습니다: {self.creator_channel_ids}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot: return

        if after.channel and after.channel.id in self.creator_channel_ids:
            min_limit = self.creator_channel_ids[after.channel.id]
            if any(info.get('owner_id') == member.id for info in self.temp_channels.values()):
                return
            await self._create_temp_channel(member, min_limit)

        if before.channel and before.channel.id in self.temp_channels:
            if not before.channel.members:
                await self._delete_temp_channel(before.channel)

    async def _create_temp_channel(self, member: discord.Member, min_limit: int):
        guild = member.guild
        try:
            creator_channel = guild.get_channel(next(iter(self.creator_channel_ids)))
            if not creator_channel:
                 logger.error("VC 생성 채널을 찾을 수 없습니다.")
                 return

            vc_name = f"🔊︱{member.display_name}さんの部屋"
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=True),
                member: discord.PermissionOverwrite(manage_channels=True, manage_permissions=True)
            }
            vc = await guild.create_voice_channel(
                name=vc_name,
                category=creator_channel.category,
                overwrites=overwrites,
                reason=f"{member.display_name}の要請で一時VCを作成"
            )

            embed = discord.Embed(
                title=f"ようこそ、{member.display_name}さん！",
                description=f"ここはあなたのプライベートチャンネルです。\n下のボタンでチャンネルを管理できます。\n\n**ルール:** このチャンネルは最低 **{min_limit}人** が必要です。",
                color=0x7289DA
            )
            view = ControlPanelView(self, member.id, vc.id)
            panel_message = await vc.send(embed=embed, view=view)

            self.temp_channels[vc.id] = {
                "owner_id": member.id,
                "min_limit": min_limit,
                "message_id": panel_message.id
            }
            logger.info(f"一時チャンネル '{vc.name}' を作成しました。 (所有者: {member.display_name})")
            
            await member.move_to(vc, reason="作成された一時チャンネルへ自動的に移動")

        except Exception as e:
            logger.error(f"一時チャンネルの作成中に予期せぬエラーが発生しました: {e}", exc_info=True)
            if member.voice:
                await member.move_to(None)

    async def _delete_temp_channel(self, vc: discord.VoiceChannel):
        try:
            await vc.delete(reason="チャンネルに誰もいなくなったため自動削除")
            self.temp_channels.pop(vc.id, None)
            logger.info(f"一時チャンネル '{vc.name}' を自動削除しました。")
        except discord.NotFound:
            pass
        except Exception as e:
            logger.error(f"一時チャンネル '{vc.name}' 삭제 중 오류 발생: {e}", exc_info=True)

    async def _transfer_ownership(self, interaction: discord.Interaction, vc: discord.VoiceChannel, new_owner: discord.Member):
        info = self.temp_channels.get(vc.id)
        if not info: return await interaction.followup.send("❌ チャンネル情報が見つかりません。", ephemeral=True)

        old_owner = interaction.guild.get_member(info['owner_id'])
        
        try:
            await vc.set_permissions(new_owner, manage_channels=True, manage_permissions=True)
            if old_owner:
                await vc.set_permissions(old_owner, overwrite=None)
            
            info['owner_id'] = new_owner.id
            
            new_view = ControlPanelView(self, new_owner.id, vc.id)
            panel_message = await vc.fetch_message(info['message_id'])
            await panel_message.edit(view=new_view)
            
            await vc.send(f"👑 {interaction.user.mention} さんがチャンネルの所有権を {new_owner.mention} さんに移譲しました。")
            await interaction.followup.send("✅ 所有権を正常に移譲しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"所有権の移譲中にエラーが発生しました: {e}", exc_info=True)
            await interaction.followup.send("❌ 所有権の移譲中にエラーが発生しました。", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceMaster(bot))
