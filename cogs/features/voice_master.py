# cogs/features/voice_master.py
"""
음성 채널 자동 생성 및 제어판(Voice Master) 기능을 담당하는 Cog입니다.
하이브리드 방식으로 메모리와 DB를 함께 사용하여 안정성과 성능을 모두 확보합니다.
"""
import discord
from discord.ext import commands
from discord import ui
import logging
from typing import Dict, Optional, List, Any

from utils.database import get_id, get_all_temp_channels, add_temp_channel, update_temp_channel_owner, remove_temp_channel, remove_multiple_temp_channels
from utils.helpers import get_clean_display_name

logger = logging.getLogger(__name__)

CHANNEL_TYPE_INFO = {
    "plaza":    {"emoji": "⛲", "name_editable": False, "limit_editable": False, "default_name": "みんなの広場"},
    "game":     {"emoji": "🎮", "name_editable": True,  "limit_editable": True,  "default_name": "{member_name}のゲーム部屋"},
    "newbie":   {"emoji": "🪑", "name_editable": False, "limit_editable": True,  "default_name": "新人のベンチ"},
    "vip":      {"emoji": "🏠", "name_editable": True,  "limit_editable": True,  "default_name": "{member_name}のハウス"},
    "normal":   {"emoji": "🍀", "name_editable": True,  "limit_editable": True,  "default_name": "{member_name}の部屋"} # Fallback
}

# ... (VCEditModal 및 Select UI 클래스들은 이전과 동일) ...
class VCEditModal(ui.Modal, title="🔊 ボイスチャンネル設定"):
    def __init__(self, name_editable: bool, limit_editable: bool, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.submitted = False
        if name_editable:
            self.name_input = ui.TextInput(label="チャンネル名", placeholder="新しいチャンネル名を入力してください。", required=False, max_length=80)
            self.add_item(self.name_input)
        if limit_editable:
            self.limit_input = ui.TextInput(label="最大入室人数", placeholder="数字を入力 (例: 5)。0は無制限です。", required=False, max_length=2)
            self.add_item(self.limit_input)

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
                await vc.set_permissions(member, connect=True, reason=f"{interaction.user.display_name}からの招待")
                invited_members.append(member.mention)
        await interaction.followup.send(f"✅ {', '.join(invited_members)} さんをチャンネルに招待しました。", ephemeral=True)
        try: await interaction.delete_original_response()
        except discord.NotFound: pass

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
        try: await interaction.delete_original_response()
        except discord.NotFound: pass

class VCOwnerSelect(ui.UserSelect):
    def __init__(self, panel_view: 'ControlPanelView'):
        self.panel_view = panel_view
        super().__init__(placeholder="新しい所有者を選択してください...", min_values=1, max_values=1)
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        new_owner = self.values[0]
        if not isinstance(new_owner, discord.Member) or new_owner.id == self.panel_view.owner_id or new_owner.bot: return
        vc = self.panel_view.cog.bot.get_channel(self.panel_view.vc_id)
        if vc: await self.panel_view.cog._transfer_ownership(interaction, vc, new_owner)
        try: await interaction.delete_original_response()
        except discord.NotFound: pass


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
        type_info = CHANNEL_TYPE_INFO.get(self.channel_type, CHANNEL_TYPE_INFO["normal"])
        if type_info["name_editable"] or type_info["limit_editable"]:
            self.add_item(ui.Button(label="設定", style=discord.ButtonStyle.primary, emoji="⚙️", custom_id="vc_edit", row=0))
        self.add_item(ui.Button(label="所有権移譲", style=discord.ButtonStyle.secondary, emoji="👑", custom_id="vc_transfer", row=0))
        if self.channel_type == 'vip':
            self.add_item(ui.Button(label="招待", style=discord.ButtonStyle.success, emoji="📨", custom_id="vc_invite", row=1))
            self.add_item(ui.Button(label="追放", style=discord.ButtonStyle.danger, emoji="👢", custom_id="vc_kick", row=1))
        for item in self.children:
            if isinstance(item, ui.Button): item.callback = self.dispatch_button

    async def dispatch_button(self, interaction: discord.Interaction):
        custom_id = interaction.data.get("custom_id")
        dispatch_map = {
            "vc_edit": self.edit_channel, "vc_transfer": self.transfer_owner,
            "vc_invite": self.invite_user, "vc_kick": self.kick_user,
        }
        if callback := dispatch_map.get(custom_id): await callback(interaction)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.cog.bot.get_channel(self.vc_id) is None:
            await interaction.response.send_message("❌ このチャンネルはすでに削除されています。", ephemeral=True, view=None)
            self.stop(); return False
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ このチャンネルの所有者のみが操作できます。", ephemeral=True)
            return False
        return True

    async def edit_channel(self, interaction: discord.Interaction):
        vc = self.cog.bot.get_channel(self.vc_id)
        if not vc: return
        type_info = CHANNEL_TYPE_INFO.get(self.channel_type, CHANNEL_TYPE_INFO["normal"])
        modal = VCEditModal(name_editable=type_info["name_editable"], limit_editable=type_info["limit_editable"])
        if type_info["name_editable"]:
            modal.name_input.default = vc.name.split('꒱')[-1].strip()
        if type_info["limit_editable"]:
            modal.limit_input.default = str(vc.user_limit)
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.submitted:
            vc = self.cog.bot.get_channel(self.vc_id)
            if not vc: return await interaction.followup.send("❌ 処理中にチャンネルが見つからなくなりました。", ephemeral=True)
            new_name = vc.name
            if type_info["name_editable"]:
                emoji = type_info["emoji"]
                base_name = modal.name_input.value or vc.name.split('꒱')[-1].strip()
                new_name = f"・ {emoji} ꒱ {base_name}"
            new_limit = vc.user_limit
            if type_info["limit_editable"]:
                try:
                    new_limit = int(modal.limit_input.value or vc.user_limit)
                    if not (0 <= new_limit <= 99): raise ValueError()
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
            if isinstance(target, discord.Member) and target.id != self.owner_id and overwrite.connect is True
        ]
        if not invited_members: return await interaction.response.send_message("ℹ️ 招待されたメンバーがいません。", ephemeral=True)
        view = ui.View(timeout=180).add_item(VCKickSelect(self, invited_members))
        await interaction.response.send_message("追放するメンバーを選んでください。", view=view, ephemeral=True)

# --- VoiceMaster Cog ---
class VoiceMaster(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.creator_channel_configs: Dict[int, Dict] = {}
        self.temp_channels: Dict[int, Dict[str, Any]] = {} # 메모리 캐시
        logger.info("VoiceMaster Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        await self.load_configs()
        # [수정] 봇 재시작시 View 복구를 위해, on_ready 이후에 동기화 실행
        self.bot.loop.create_task(self.sync_channels_from_db())

    async def load_configs(self):
        self.creator_channel_configs = {
            get_id("vc_creator_channel_id_4p"): {"type": "plaza", "min_limit": 4},
            get_id("vc_creator_channel_id_3p"): {"type": "game", "min_limit": 3},
            get_id("vc_creator_channel_id_newbie"): {"type": "newbie", "min_limit": 1, "required_role_key": "role_resident_rookie", "allowed_role_key": "role_approval"},
            get_id("vc_creator_channel_id_vip"): {"type": "vip", "min_limit": 1, "required_role_key": "role_personal_room_key"},
        }
        self.creator_channel_configs = {k: v for k, v in self.creator_channel_configs.items() if k is not None}
        logger.info(f"[VoiceMaster] 생성 채널 설정을 로드했습니다: {self.creator_channel_configs}")

    # [신규] 봇 재시작 시 DB와 동기화하는 함수
    async def sync_channels_from_db(self):
        await self.bot.wait_until_ready()
        db_channels = await get_all_temp_channels()
        if not db_channels: return

        logger.info(f"[VoiceMaster] DB에서 {len(db_channels)}개의 임시 채널 정보를 발견하여 동기화를 시작합니다.")
        
        zombie_channel_ids = []
        for ch_data in db_channels:
            channel_id = ch_data.get("channel_id")
            guild_id = ch_data.get("guild_id")
            guild = self.bot.get_guild(guild_id)

            if guild and guild.get_channel(channel_id):
                # 채널이 실제로 존재하면 메모리에 로드하고 View를 다시 붙여줌
                self.temp_channels[channel_id] = {
                    "owner_id": ch_data.get("owner_id"),
                    "message_id": ch_data.get("message_id"),
                    "type": ch_data.get("channel_type", "normal")
                }
                view = ControlPanelView(self, ch_data.get("owner_id"), channel_id, ch_data.get("channel_type", "normal"))
                self.bot.add_view(view, message_id=ch_data.get("message_id"))
            else:
                # 채널이 존재하지 않으면 '좀비 데이터'로 간주
                zombie_channel_ids.append(channel_id)

        # '좀비 데이터'를 DB에서 한 번에 삭제
        if zombie_channel_ids:
            await remove_multiple_temp_channels(zombie_channel_ids)
            logger.warning(f"[VoiceMaster] 존재하지 않는 {len(zombie_channel_ids)}개의 '좀비' 채널을 DB에서 정리했습니다.")
        
        logger.info(f"[VoiceMaster] 임시 채널 동기화 완료. (활성: {len(self.temp_channels)} / 정리: {len(zombie_channel_ids)})")


    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot: return

        if after.channel and after.channel.id in self.creator_channel_configs:
            config = self.creator_channel_configs[after.channel.id]
            if any(info.get('owner_id') == member.id for info in self.temp_channels.values()): return
            is_allowed = False
            if allowed_role_key := config.get("allowed_role_key"):
                allowed_role_id = get_id(allowed_role_key)
                if allowed_role_id and allowed_role_id in [r.id for r in member.roles]:
                    is_allowed = True
            if not is_allowed and (required_role_key := config.get("required_role_key")):
                required_role_id = get_id(required_role_key)
                if required_role_id and required_role_id in [r.id for r in member.roles]:
                    is_allowed = True
            if config.get("required_role_key") and not is_allowed:
                try: await member.send(f"❌ 「{after.channel.name}」チャンネルに入るには特別な役割が必要です。")
                except discord.Forbidden: pass
                await member.move_to(None, reason="요구 역할 없음")
                return
            await self._create_temp_channel(member, config)

        if before.channel and before.channel.id in self.temp_channels:
            info = self.temp_channels.get(before.channel.id)
            if info and (not before.channel.members or member.id == info.get("owner_id")):
                await self._delete_temp_channel(before.channel)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        if not isinstance(channel, discord.VoiceChannel): return
        if channel.id in self.temp_channels:
            await remove_temp_channel(channel.id) # DB에서도 삭제
            self.temp_channels.pop(channel.id, None)
            logger.info(f"임시 채널 '{channel.name}'(ID: {channel.id})이 수동으로 삭제되어 내부 데이터와 DB에서 제거합니다.")

    async def _create_temp_channel(self, member: discord.Member, config: Dict):
        guild = member.guild
        channel_type = config.get("type", "normal")
        type_info = CHANNEL_TYPE_INFO.get(channel_type, CHANNEL_TYPE_INFO["normal"])
        try:
            creator_channel = guild.get_channel(next(iter(self.creator_channel_configs)))
            if not creator_channel: return logger.error("VC 생성 채널을 찾을 수 없습니다.")
            clean_member_name = get_clean_display_name(member)
            base_name = type_info["default_name"].format(member_name=clean_member_name)
            vc_name = f"・ {type_info['emoji']} ꒱ {base_name}"
            overwrites = { member: discord.PermissionOverwrite(manage_channels=True, manage_permissions=True, connect=True) }
            if channel_type == 'vip':
                overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=True, connect=False)
            else:
                overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=True)
            vc = await guild.create_voice_channel(name=vc_name, category=creator_channel.category, overwrites=overwrites, reason=f"{member.display_name}の要請")
            embed = discord.Embed(title=f"ようこそ、{get_clean_display_name(member)}さん！", color=0x7289DA).add_field(name="チャンネルタイプ", value=f"`{channel_type.upper()}`", inline=False)
            embed.description = "ここはあなたのプライベートチャンネルです。\n下のボタンでチャンネルを管理できます。"
            view = ControlPanelView(self, member.id, vc.id, channel_type)
            panel_message = await vc.send(embed=embed, view=view)
            
            # [수정] 메모리와 DB에 동시 저장
            self.temp_channels[vc.id] = {"owner_id": member.id, "message_id": panel_message.id, "type": channel_type}
            await add_temp_channel(vc.id, member.id, guild.id, panel_message.id, channel_type)
            
            logger.info(f"'{channel_type}' 타입 임시 채널 '{vc.name}'을 생성하고 DB에 저장했습니다.")
            await member.move_to(vc, reason="생성된 임시 채널로 자동 이동")
        except Exception as e:
            logger.error(f"임시 채널 생성 중 오류: {e}", exc_info=True)
            if member.voice: await member.move_to(None)

    async def _delete_temp_channel(self, vc: discord.VoiceChannel):
        try:
            await vc.delete(reason="채널에 아무도 없거나 소유자가 나갔기 때문에 자동 삭제")
            # [수정] 메모리와 DB에서 동시 삭제
            self.temp_channels.pop(vc.id, None)
            await remove_temp_channel(vc.id)
            logger.info(f"임시 채널 '{vc.name}'을 자동 삭제하고 DB에서 제거했습니다.")
        except discord.NotFound:
            # 채널이 이미 삭제된 경우에도 DB와 메모리 정리를 시도
            self.temp_channels.pop(vc.id, None)
            await remove_temp_channel(vc.id)
        except Exception as e: logger.error(f"임시 채널 '{vc.name}' 삭제 중 오류: {e}", exc_info=True)

    async def _transfer_ownership(self, interaction: discord.Interaction, vc: discord.VoiceChannel, new_owner: discord.Member):
        info = self.temp_channels.get(vc.id)
        if not info: return await interaction.followup.send("❌ チャンネル情報が見つかりません。", ephemeral=True)
        old_owner = interaction.guild.get_member(info['owner_id'])
        try:
            await vc.set_permissions(new_owner, manage_channels=True, manage_permissions=True, connect=True)
            if old_owner: await vc.set_permissions(old_owner, overwrite=None)
            
            # [수정] 메모리와 DB의 소유자 정보 동시 업데이트
            info['owner_id'] = new_owner.id
            await update_temp_channel_owner(vc.id, new_owner.id)
            
            new_view = ControlPanelView(self, new_owner.id, vc.id, info['type'])
            panel_message = await vc.fetch_message(info['message_id'])
            embed = panel_message.embeds[0]
            embed.title = f"ようこそ、{get_clean_display_name(new_owner)}さん！"
            await panel_message.edit(embed=embed, view=new_view)
            await vc.send(f"👑 {get_clean_display_name(interaction.user)}さんがチャンネルの所有権を{new_owner.mention}さんに移譲しました。")
            await interaction.followup.send("✅ 所有権を正常に移譲しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"소유권 이전 중 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 所有権の移譲中にエラーが発生しました。", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceMaster(bot))
