# cogs/features/voice_master.py
"""
음성 채널 자동 생성 및 제어판(Voice Master) 기능을 담당하는 Cog입니다.
제어판은 음성 채널에 연결된 텍스트 채팅 채널에 생성됩니다.
"""
import discord
from discord.ext import commands
from discord import ui
import logging
from typing import Dict, Optional

from utils.database import get_id

logger = logging.getLogger(__name__)

# --- 제어판용 UI 클래스들 ---

class VCEditModal(ui.Modal, title="🔊 ボイスチャンネル設定"):
    name = ui.TextInput(label="チャンネル名", placeholder="新しいチャンネル名を入力してください。", required=False, max_length=100)
    limit = ui.TextInput(label="最大入室人数", placeholder="数字を入力 (例: 5)。0は無制限です。", required=False, max_length=2)
    async def on_submit(self, interaction: discord.Interaction): pass

class VCBlacklistSelect(ui.UserSelect):
    def __init__(self, view_instance: 'ControlPanelView'):
        self.panel_view = view_instance
        super().__init__(placeholder="ブラックリストに追加/削除するメンバーを選択...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        target_member = self.values[0]
        vc = self.panel_view.cog.bot.get_channel(self.panel_view.vc_id)

        if not vc or not isinstance(target_member, discord.Member):
            return await interaction.followup.send("❌ チャンネルまたはメンバーが見つかりませんでした。", ephemeral=True)
        
        # 소유자는 블랙리스트에 추가할 수 없음
        if target_member.id == self.panel_view.owner_id:
            return await interaction.followup.send("❌ チャンネルの所有者をブラックリストに追加することはできません。", ephemeral=True)

        current_overwrite = vc.overwrites_for(target_member)
        
        if current_overwrite.view_channel is False:
            await vc.set_permissions(target_member, overwrite=None, reason=f"{interaction.user.display_name}がブラックリストから解除")
            await interaction.followup.send(f"✅ {target_member.mention} さんをブラックリストから解除しました。", ephemeral=True)
        else:
            await vc.set_permissions(target_member, view_channel=False, reason=f"{interaction.user.display_name}がブラックリストに追加")
            if target_member in vc.members:
                await target_member.move_to(None, reason="ブラックリストに追加されたため")
            await interaction.followup.send(f"✅ {target_member.mention} さんをブラックリストに追加しました。今後このチャンネルは見えなくなります。", ephemeral=True)

        # 드롭다운 메뉴를 다시 버튼으로 되돌리기 위해 View를 새로고침
        await interaction.edit_original_response(view=self.panel_view)

class VCOwnerSelect(ui.UserSelect):
    def __init__(self, view_instance: 'ControlPanelView'):
        self.panel_view = view_instance
        super().__init__(placeholder="新しい所有者を選択してください...", min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        new_owner = self.values[0]

        if new_owner.id == self.panel_view.owner_id:
            await interaction.followup.send("❌ すでにあなたが所有者です。", ephemeral=True)
            return
        
        if new_owner.bot:
            await interaction.followup.send("❌ ボットに所有権を移譲することはできません。", ephemeral=True)
            return

        vc = self.panel_view.cog.bot.get_channel(self.panel_view.vc_id)
        if vc:
            await self.panel_view.cog._transfer_ownership(interaction, vc, new_owner)
        
        await interaction.edit_original_response(view=self.panel_view)


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

    @ui.button(label="設定", style=discord.ButtonStyle.primary, emoji="⚙️", custom_id="vc_text_edit")
    async def edit_channel(self, interaction: discord.Interaction, button: ui.Button):
        vc = self.cog.bot.get_channel(self.vc_id)
        if not vc: return await interaction.response.send_message("❌ チャンネルが見つかりません。", ephemeral=True)
        
        modal = VCEditModal()
        modal.name.default = vc.name.split("︱")[-1].strip()
        modal.limit.default = str(vc.user_limit)
        await interaction.response.send_modal(modal)
        await modal.wait()

        if modal.is_submitted():
            await interaction.response.defer(ephemeral=True)
            vc = self.cog.bot.get_channel(self.vc_id) # 다시 채널 가져오기
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

    @ui.button(label="ブラックリスト", style=discord.ButtonStyle.danger, emoji="🚫", custom_id="vc_text_blacklist")
    async def blacklist_member(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View(timeout=60)
        view.add_item(VCBlacklistSelect(self))
        await interaction.response.send_message("ブラックリストに追加/削除するメンバーを選んでください。", view=view, ephemeral=True)

    @ui.button(label="所有権移譲", style=discord.ButtonStyle.secondary, emoji="👑", custom_id="vc_text_transfer")
    async def transfer_owner(self, interaction: discord.Interaction, button: ui.Button):
        view = ui.View(timeout=60)
        view.add_item(VCOwnerSelect(self))
        await interaction.response.send_message("新しい所有者を選んでください。", view=view, ephemeral=True)


class VoiceMaster(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.creator_channel_ids: Dict[int, int] = {}
        self.temp_channels: Dict[int, Dict] = {}
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
            if any(info['owner_id'] == member.id for info in self.temp_channels.values()): return
            await self._create_temp_channel(member, min_limit)

        if before.channel and before.channel.id in self.temp_channels:
            if len(before.channel.members) == 0:
                await self._delete_temp_channel(before.channel)

    async def _create_temp_channel(self, member: discord.Member, min_limit: int):
        guild = member.guild
        creator_channel = guild.get_channel(list(self.creator_channel_ids.keys())[0])

        try:
            vc_name = f"🔊︱{member.display_name}さんの部屋"
            vc = await guild.create_voice_channel(
                name=vc_name,
                category=creator_channel.category,
                reason=f"{member.display_name}の要請で一時VCを作成"
            )

            await vc.set_permissions(member, manage_channels=True, manage_permissions=True)
            self.temp_channels[vc.id] = {"owner_id": member.id, "min_limit": min_limit}
            logger.info(f"一時チャンネル '{vc.name}' を作成しました。 (所有者: {member.display_name}, 最低人数: {min_limit})")

            embed = discord.Embed(
                title=f"ようこそ、{member.display_name}さん！",
                description=f"ここはあなたのプライベートチャンネルです。\n下のボタンでチャンネルを管理できます。\n\n**ルール:** このチャンネルは最低 **{min_limit}人** が必要です。",
                color=0x7289DA
            )
            view = ControlPanelView(self, member.id, vc.id)
            await vc.send(embed=embed, view=view)

            await member.move_to(vc, reason="作成された一時チャンネルへ自動的に移動")

        except Exception as e:
            logger.error(f"一時チャンネルの作成中に予期せぬエラーが発生しました: {e}", exc_info=True)
            if member.voice: # 만약 유저가 아직 생성 채널에 있다면, 원래 있던 곳으로 돌려보내거나 연결을 끊음
                await member.move_to(None)


    async def _delete_temp_channel(self, vc: discord.VoiceChannel):
        try:
            del self.temp_channels[vc.id]
            await vc.delete(reason="チャンネルに誰もいなくなったため自動削除")
            logger.info(f"一時チャンネル '{vc.name}' を自動削除しました。")
        except KeyError:
            pass # 이미 삭제 처리된 경우 무시
        except Exception as e:
            logger.error(f"一時チャンネルの削除中に予期せぬエラーが発生しました: {e}", exc_info=True)
    
    async def _transfer_ownership(self, interaction: discord.Interaction, vc: discord.VoiceChannel, new_owner: discord.Member):
        info = self.temp_channels.get(vc.id)
        if not info: return await interaction.followup.send("❌ チャンネル情報が見つかりません。", ephemeral=True)
        
        old_owner_id = info['owner_id']
        old_owner = interaction.guild.get_member(old_owner_id)

        try:
            # 기존 소유자의 특별 권한 제거
            if old_owner:
                await vc.set_permissions(old_owner, overwrite=None)
            # 새 소유자에게 특별 권한 부여
            await vc.set_permissions(new_owner, manage_channels=True, manage_permissions=True)

            # 봇 내부 정보 업데이트
            info['owner_id'] = new_owner.id
            
            # 제어판 View 업데이트 (새 소유자로 교체)
            new_view = ControlPanelView(self, new_owner.id, vc.id)
            original_message = await interaction.original_response()
            await original_message.edit(view=new_view)
            
            # DM이 아닌 채널 채팅에 알림
            await vc.send(f"👑 {interaction.user.mention} さんがチャンネルの所有権を {new_owner.mention} さんに移譲しました。")
            await interaction.followup.send("✅ 所有権を正常に移譲しました。", ephemeral=True)

        except Exception as e:
            logger.error(f"所有権の移譲中にエラーが発生しました: {e}", exc_info=True)
            await interaction.followup.send("❌ 所有権の移譲中にエラーが発生しました。", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceMaster(bot))
