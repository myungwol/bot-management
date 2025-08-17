# cogs/features/voice_master.py
"""
음성 채널 자동 생성 및 제어판(Voice Master) 기능을 담당하는 Cog입니다.
채널 타입에 따라 다른 제어판과 권한을 가집니다.
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

class VCInviteSelect(ui.UserSelect):
    def __init__(self, panel_view: 'ControlPanelView'):
        self.panel_view = panel_view
        super().__init__(placeholder="チャンネルに招待するメンバーを選択...", min_values=1, max_values=10)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        vc = self.panel_view.cog.bot.get_channel(self.panel_view.vc_id)
        if not vc: return await interaction.followup.send("❌ チャンネルが見つかりませんでした。", ephemeral=True)

        invited_members = []
        for member in self.values:
            if isinstance(member, discord.Member):
                await vc.set_permissions(member, view_channel=True, reason=f"{interaction.user.display_name}からの招待")
                invited_members.append(member.mention)
        
        await interaction.followup.send(f"✅ {', '.join(invited_members)} さんをチャンネルに招待しました。", ephemeral=True)
        try:
            await interaction.delete_original_response()
        except discord.NotFound:
            pass

class VCKickSelect(ui.Select):
    def __init__(self, panel_view: 'ControlPanelView', invited_members: List[discord.Member]):
        self.panel_view = panel_view
        options = [discord.SelectOption(label=member.display_name, value=str(member.id)) for member in invited_members]
        super().__init__(placeholder="追放するメンバーを選択...", min_values=1, max_values=len(options), options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        vc = self.panel_view.cog.bot.get_channel(self.panel_view.vc_id)
        if not vc or not interaction.guild: return await interaction.followup.send("❌ チャンネルが見つかりませんでした。", ephemeral=True)

        kicked_members = []
        for member_id_str in self.values:
            member = interaction.guild.get_member(int(member_id_str))
            if member:
                await vc.set_permissions(member, overwrite=None, reason=f"{interaction.user.display_name}による追放")
                if member in vc.members:
                    await member.move_to(None, reason="チャンネルから追放されました")
                kicked_members.append(member.mention)
        
        await interaction.followup.send(f"✅ {', '.join(kicked_members)} さんをチャンネルから追放しました。", ephemeral=True)
        try:
            await interaction.delete_original_response()
        except discord.NotFound:
            pass

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
    def __init__(self, cog: 'VoiceMaster', owner_id: int, vc_id: int, channel_type: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.owner_id = owner_id
        self.vc_id = vc_id
        self.channel_type = channel_type
        self.setup_buttons()

    def setup_buttons(self):
        self.clear_items()
        self.add_item(ui.Button(label="設定", style=discord.ButtonStyle.primary, emoji="⚙️", custom_id="vc_edit", row=0))
        self.add_item(ui.Button(label="所有権移譲", style=discord.ButtonStyle.secondary, emoji="👑", custom_id="vc_transfer", row=0))

        if self.channel_type == 'vip':
            self.add_item(ui.Button(label="招待", style=discord.ButtonStyle.success, emoji="📨", custom_id="vc_invite", row=1))
            self.add_item(ui.Button(label="追放", style=discord.ButtonStyle.danger, emoji="👢", custom_id="vc_kick", row=1))

        # 모든 버튼에 하나의 dispatch 콜백을 연결
        for item in self.children:
            if isinstance(item, ui.Button):
                item.callback = self.dispatch_button

    async def dispatch_button(self, interaction: discord.Interaction):
        """버튼 custom_id에 따라 적절한 함수를 호출합니다."""
        custom_id = interaction.data.get("custom_id")
        dispatch_map = {
            "vc_edit": self.edit_channel,
            "vc_transfer": self.transfer_owner,
            "vc_invite": self.invite_user,
            "vc_kick": self.kick_user,
        }
        if callback := dispatch_map.get(custom_id):
            await callback(interaction)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.cog.bot.get_channel(self.vc_id) is None:
            await interaction.response.send_message("❌ このチャンネルはすでに削除されています。", ephemeral=True, view=None)
            self.stop()
            return False
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ このチャンネルの所有者のみが操作できます。", ephemeral=True)
            return False
        return True

    async def edit_channel(self, interaction: discord.Interaction):
        vc = self.cog.bot.get_channel(self.vc_id)
        if not vc: return

        modal = VCEditModal()
        modal.name.default = vc.name.split("︱")[-1].strip()
        modal.limit.default = str(vc.user_limit)
        await interaction.response.send_modal(modal)
        await modal.wait()

        if modal.submitted:
            vc = self.cog.bot.get_channel(self.vc_id) # 최신 상태 다시 가져오기
            if not vc: return await interaction.followup.send("❌ 処理中にチャンネルが見つからなくなりました。", ephemeral=True)

            new_name = f"🔊︱{modal.name.value or vc.name.split('︱')[-1].strip()}"
            try:
                new_limit = int(modal.limit.value or vc.user_limit)
                if not (0 <= new_limit <= 99): raise ValueError()
                info = self.cog.temp_channels.get(self.vc_id, {})
                min_limit = info.get("min_limit", 1)
                if 0 < new_limit < min_limit:
                    return await interaction.followup.send(f"❌ このチャンネルは最低{min_limit}人が必要です。", ephemeral=True)
            except (ValueError, TypeError):
                return await interaction.followup.send("❌ 人数制限は0から99までの数字で入力してください。", ephemeral=True)

            await vc.edit(name=new_name, user_limit=new_limit, reason=f"{interaction.user.display_name}の要請")
            await interaction.followup.send("✅ チャンネル設定を更新しました。", ephemeral=True)
    
    async def transfer_owner(self, interaction: discord.Interaction):
        view = ui.View(timeout=180).add_item(VCOwnerSelect(self))
        await interaction.response.send_message("新しい所有者を選んでください。", view=view, ephemeral=True)
        
    async def invite_user(self, interaction: discord.Interaction):
        view = ui.View(timeout=180).add_item(VCInviteSelect(self))
        await interaction.response.send_message("招待するメンバーを選んでください。", view=view, ephemeral=True)

    async def kick_user(self, interaction: discord.Interaction):
        vc = self.cog.bot.get_channel(self.vc_id)
        if not vc or not interaction.guild: return
        
        invited_members = [
            target for target, overwrite in vc.overwrites.items()
            if isinstance(target, discord.Member) and target.id != self.owner_id and overwrite.view_channel is True
        ]
        if not invited_members:
            return await interaction.response.send_message("ℹ️ 招待されたメンバーがいません。", ephemeral=True)

        view = ui.View(timeout=180).add_item(VCKickSelect(self, invited_members))
        await interaction.response.send_message("追放するメンバーを選んでください。", view=view, ephemeral=True)


# --- VoiceMaster Cog ---

class VoiceMaster(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.creator_channel_configs: Dict[int, Dict] = {}
        self.temp_channels: Dict[int, Dict] = {}
        self.bot.add_view(ControlPanelView(self, 0, 0, "normal")) # 봇 재시작시 View 유지를 위해 등록
        logger.info("VoiceMaster Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        await self.load_configs()

    async def load_configs(self):
        self.creator_channel_configs = {
            get_id("vc_creator_channel_id_3p"): {"type": "normal", "min_limit": 3},
            get_id("vc_creator_channel_id_4p"): {"type": "normal", "min_limit": 4},
            get_id("vc_creator_channel_id_newbie"): {"type": "newbie", "min_limit": 1, "required_role_key": "role_resident_rookie"},
            get_id("vc_creator_channel_id_vip"): {"type": "vip", "min_limit": 1, "required_role_key": "role_personal_room_key"},
        }
        # DB에서 ID를 못가져온 None key는 제거
        self.creator_channel_configs = {k: v for k, v in self.creator_channel_configs.items() if k is not None}
        logger.info(f"[VoiceMaster] 생성 채널 설정을 로드했습니다: {self.creator_channel_configs}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot: return

        # --- 채널 생성 로직 ---
        if after.channel and after.channel.id in self.creator_channel_configs:
            config = self.creator_channel_configs[after.channel.id]

            # 이미 개인 채널을 소유하고 있는지 확인
            if any(info.get('owner_id') == member.id for info in self.temp_channels.values()):
                return

            # 채널 생성에 필요한 역할이 있는지 확인
            if role_key := config.get("required_role_key"):
                role_id = get_id(role_key)
                if not role_id or role_id not in [r.id for r in member.roles]:
                    try:
                        await member.send(f"❌ 「{after.channel.name}」チャンネルに入るには特別な役割が必要です。")
                    except discord.Forbidden:
                        pass # DM 차단 유저
                    await member.move_to(None, reason="요구 역할 없음")
                    return

            await self._create_temp_channel(member, config)

        # --- 채널 삭제 로직 ---
        if before.channel and before.channel.id in self.temp_channels:
            # 채널에 아무도 없으면 삭제
            if not before.channel.members:
                await self._delete_temp_channel(before.channel)

    async def _create_temp_channel(self, member: discord.Member, config: Dict):
        guild = member.guild
        channel_type = config.get("type", "normal")
        min_limit = config.get("min_limit", 1)
        
        try:
            # 설정된 생성 채널 중 하나를 기준으로 카테고리 위치를 정함
            creator_channel = guild.get_channel(next(iter(self.creator_channel_configs)))
            if not creator_channel:
                 logger.error("VC 생성 채널을 찾을 수 없어 카테고리를 지정할 수 없습니다.")
                 return

            vc_name = f"🔊︱{member.display_name}さんの部屋"
            overwrites = { member: discord.PermissionOverwrite(manage_channels=True, manage_permissions=True) }
            
            # VIP 채널은 비공개로, 나머지는 공개로 설정
            if channel_type == 'vip':
                overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=False)
            else:
                overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=True)

            vc = await guild.create_voice_channel(
                name=vc_name, category=creator_channel.category, overwrites=overwrites,
                reason=f"{member.display_name}の要請で{channel_type}VCを作成"
            )

            embed = discord.Embed(title=f"ようこそ、{member.display_name}さん！", color=0x7289DA)
            embed.add_field(name="チャンネルタイプ", value=f"`{channel_type.upper()}`", inline=False)
            if channel_type == 'vip':
                embed.description = "ここはあなただけのプライベートチャンネルです。\n下のボタンでメンバーを招待・管理できます。"
            else:
                embed.description = "ここはあなたのプライベートチャンネルです。\n下のボタンでチャンネルを管理できます。"

            view = ControlPanelView(self, member.id, vc.id, channel_type)
            panel_message = await vc.send(embed=embed, view=view)

            self.temp_channels[vc.id] = {
                "owner_id": member.id, "min_limit": min_limit, "message_id": panel_message.id, "type": channel_type
            }
            logger.info(f"'{channel_type}' 타입 임시 채널 '{vc.name}'을 생성했습니다.")
            
            await member.move_to(vc, reason="생성된 임시 채널로 자동 이동")

        except Exception as e:
            logger.error(f"임시 채널 생성 중 오류: {e}", exc_info=True)
            if member.voice: await member.move_to(None)

    async def _delete_temp_channel(self, vc: discord.VoiceChannel):
        try:
            await vc.delete(reason="채널에 아무도 없어 자동 삭제")
            self.temp_channels.pop(vc.id, None)
            logger.info(f"임시 채널 '{vc.name}'을 자동 삭제했습니다.")
        except discord.NotFound: pass
        except Exception as e: logger.error(f"임시 채널 '{vc.name}' 삭제 중 오류: {e}", exc_info=True)

    async def _transfer_ownership(self, interaction: discord.Interaction, vc: discord.VoiceChannel, new_owner: discord.Member):
        info = self.temp_channels.get(vc.id)
        if not info: return await interaction.followup.send("❌ チャンネル情報が見つかりません。", ephemeral=True)

        old_owner = interaction.guild.get_member(info['owner_id'])
        
        try:
            # 권한 업데이트
            await vc.set_permissions(new_owner, manage_channels=True, manage_permissions=True)
            if old_owner: await vc.set_permissions(old_owner, overwrite=None)
            
            # 봇 내부 정보 업데이트
            info['owner_id'] = new_owner.id
            
            # 새 소유자 정보로 제어판 View 교체
            new_view = ControlPanelView(self, new_owner.id, vc.id, info['type'])
            panel_message = await vc.fetch_message(info['message_id'])
            await panel_message.edit(view=new_view)
            
            await vc.send(f"👑 {interaction.user.mention}さんがチャンネルの所有権を{new_owner.mention}さんに移譲しました。")
            await interaction.followup.send("✅ 所有権を正常に移譲しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"소유권 이전 중 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 所有権の移譲中にエラーが発生しました。", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceMaster(bot))
