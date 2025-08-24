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
import asyncio

from utils.database import get_id, get_all_temp_channels, add_temp_channel, update_temp_channel_owner, remove_temp_channel, remove_multiple_temp_channels, get_config
from utils.helpers import get_clean_display_name
from utils.ui_defaults import ADMIN_ROLE_KEYS

logger = logging.getLogger(__name__)

# 채널 타입별 기본 설정값
CHANNEL_TYPE_INFO = {
    "plaza":    {"emoji": "⛲", "name_editable": False, "limit_editable": True,  "default_name": "みんなの広場"},
    "game":     {"emoji": "🎮", "name_editable": True,  "limit_editable": True,  "default_name": "プレイ中のゲーム名に変更してください"},
    "newbie":   {"emoji": "🪑", "name_editable": False, "limit_editable": True,  "default_name": "新人のベンチ"},
    "vip":      {"emoji": "🏠", "name_editable": True,  "limit_editable": True,  "default_name": "{member_name}のハウス"},
    "normal":   {"emoji": "🔊", "name_editable": True,  "limit_editable": True,  "default_name": "{member_name}の部屋"} # Fallback
}

class VCEditModal(ui.Modal, title="🔊 ボイスチャンネル設定"):
    def __init__(self, name_editable: bool, limit_editable: bool, current_name: str, current_limit: int):
        super().__init__()
        self.submitted = False
        if name_editable:
            self.name_input = ui.TextInput(label="チャンネル名", placeholder="新しいチャンネル名を入力してください。", default=current_name, required=False, max_length=80)
            self.add_item(self.name_input)
        if limit_editable:
            self.limit_input = ui.TextInput(label="最大入室人数", placeholder="数字を入力 (例: 5)。0は無制限です。", default=str(current_limit), required=False, max_length=2)
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
        invited_members = [m.mention for m in self.values if isinstance(m, discord.Member)]
        for member in self.values:
            if isinstance(member, discord.Member):
                await vc.set_permissions(member, connect=True, reason=f"{interaction.user.display_name}からの招待")
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
                if member in vc.members: await member.move_to(None, reason="チャンネルから追放されました")
                kicked_members.append(member.mention)
        await interaction.followup.send(f"✅ {', '.join(kicked_members)} さんをチャンネルから追放しました。", ephemeral=True)
        try: await interaction.delete_original_response()
        except discord.NotFound: pass

class VCAddBlacklistSelect(ui.UserSelect):
    def __init__(self, panel_view: 'ControlPanelView'):
        self.panel_view = panel_view
        super().__init__(placeholder="ブラックリストに追加するメンバーを選択...", min_values=1, max_values=10)
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        vc = self.panel_view.cog.bot.get_channel(self.panel_view.vc_id)
        if not vc: return await interaction.followup.send("❌ チャンネルが見つかりませんでした。", ephemeral=True)
        blacklisted = []
        for member in self.values:
            if isinstance(member, discord.Member) and member.id != self.panel_view.owner_id:
                await vc.set_permissions(member, connect=False, reason=f"{interaction.user.display_name}によるブラックリスト追加")
                if member in vc.members: await member.move_to(None, reason="ブラックリストに追加されました")
                blacklisted.append(member.mention)
        await interaction.followup.send(f"✅ {', '.join(blacklisted)} さんをブラックリストに追加しました。", ephemeral=True)
        try: await interaction.delete_original_response()
        except discord.NotFound: pass

class VCRemoveBlacklistSelect(ui.Select):
    def __init__(self, panel_view: 'ControlPanelView', blacklisted_members: List[discord.Member]):
        self.panel_view = panel_view
        options = [discord.SelectOption(label=member.display_name, value=str(member.id)) for member in blacklisted_members]
        super().__init__(placeholder="ブラックリストから解除するメンバーを選択...", min_values=1, max_values=len(options), options=options)
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        vc = self.panel_view.cog.bot.get_channel(self.panel_view.vc_id)
        if not vc or not interaction.guild: return await interaction.followup.send("❌ チャンネルが見つかりませんでした。", ephemeral=True)
        removed = []
        for member_id_str in self.values:
            member = interaction.guild.get_member(int(member_id_str))
            if member:
                await vc.set_permissions(member, overwrite=None, reason=f"{interaction.user.display_name}によるブラックリスト解除")
                removed.append(member.mention)
        await interaction.followup.send(f"✅ {', '.join(removed)} さんをブラックリストから解除しました。", ephemeral=True)
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
        if self.channel_type != 'vip':
            self.add_item(ui.Button(label="所有権移譲", style=discord.ButtonStyle.secondary, emoji="👑", custom_id="vc_transfer", row=0))
        if self.channel_type == 'vip':
            self.add_item(ui.Button(label="招待", style=discord.ButtonStyle.success, emoji="📨", custom_id="vc_invite", row=1))
            self.add_item(ui.Button(label="追放", style=discord.ButtonStyle.danger, emoji="👢", custom_id="vc_kick", row=1))
        elif self.channel_type in ['plaza', 'game']:
            self.add_item(ui.Button(label="ブラックリスト追加", style=discord.ButtonStyle.danger, emoji="🚫", custom_id="vc_add_blacklist", row=0))
            self.add_item(ui.Button(label="ブラックリスト解除", style=discord.ButtonStyle.secondary, emoji="🛡️", custom_id="vc_remove_blacklist", row=1))
        for item in self.children:
            if isinstance(item, ui.Button): item.callback = self.dispatch_button
    async def dispatch_button(self, interaction: discord.Interaction):
        custom_id = interaction.data.get("custom_id")
        dispatch_map = { "vc_edit": self.edit_channel, "vc_transfer": self.transfer_owner, "vc_invite": self.invite_user, "vc_kick": self.kick_user, "vc_add_blacklist": self.add_to_blacklist, "vc_remove_blacklist": self.remove_from_blacklist }
        if callback := dispatch_map.get(custom_id): await callback(interaction)
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        vc = self.cog.bot.get_channel(self.vc_id)
        if not vc: self.stop(); return False
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ このチャンネルの所有者のみが操作できます。", ephemeral=True)
            return False
        return True
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item):
        if isinstance(error, discord.NotFound): await interaction.response.send_message("❌ このチャンネルはすでに削除されています。", ephemeral=True); self.stop()
        else: logger.error(f"ControlPanelView에서 오류 발생: {error}", exc_info=True)
    async def edit_channel(self, interaction: discord.Interaction):
        vc = self.cog.bot.get_channel(self.vc_id)
        if not vc: return
        type_info = CHANNEL_TYPE_INFO.get(self.channel_type, CHANNEL_TYPE_INFO["normal"])
        modal = VCEditModal(
            name_editable=type_info["name_editable"], 
            limit_editable=type_info["limit_editable"],
            current_name=vc.name.split('꒱')[-1].strip(),
            current_limit=vc.user_limit
        )
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.submitted:
            vc = self.cog.bot.get_channel(self.vc_id)
            if not vc: return await interaction.followup.send("❌ 処理中にチャンネルが見つからなくなりました。", ephemeral=True)
            
            new_name = vc.name
            if type_info["name_editable"]:
                emoji = type_info["emoji"]
                base_name = modal.name_input.value if hasattr(modal, 'name_input') else vc.name.split('꒱')[-1].strip()
                new_name = f"・ {emoji} ꒱ {base_name.strip()}"

            new_limit = vc.user_limit
            if type_info["limit_editable"] and hasattr(modal, 'limit_input') and modal.limit_input.value:
                try:
                    new_limit = int(modal.limit_input.value)
                    if not (0 <= new_limit <= 99): raise ValueError()
                except (ValueError, TypeError): return await interaction.followup.send("❌ 人数制限は0から99までの数字で入力してください。", ephemeral=True)
            
            await vc.edit(name=new_name, user_limit=new_limit, reason=f"{interaction.user.display_name}の要請")
            await interaction.followup.send("✅ チャンネル設定を更新しました。", ephemeral=True)

    async def transfer_owner(self, interaction: discord.Interaction):
        view = ui.View(timeout=180).add_item(VCOwnerSelect(self)); await interaction.response.send_message("新しい所有者を選んでください。", view=view, ephemeral=True)
    async def invite_user(self, interaction: discord.Interaction):
        view = ui.View(timeout=180).add_item(VCInviteSelect(self)); await interaction.response.send_message("招待するメンバーを選んでください。", view=view, ephemeral=True)
    async def kick_user(self, interaction: discord.Interaction):
        vc = self.cog.bot.get_channel(self.vc_id)
        if not vc or not interaction.guild: return
        invited_members = [ target for target, overwrite in vc.overwrites.items() if isinstance(target, discord.Member) and target.id != self.owner_id and overwrite.connect is True ]
        if not invited_members: return await interaction.response.send_message("ℹ️ 招待されたメンバーがいません。", ephemeral=True)
        view = ui.View(timeout=180).add_item(VCKickSelect(self, invited_members)); await interaction.response.send_message("追放するメンバーを選んでください。", view=view, ephemeral=True)
    async def add_to_blacklist(self, interaction: discord.Interaction):
        view = ui.View(timeout=180).add_item(VCAddBlacklistSelect(self)); await interaction.response.send_message("ブラックリストに追加するメンバーを選んでください。", view=view, ephemeral=True)
    async def remove_from_blacklist(self, interaction: discord.Interaction):
        vc = self.cog.bot.get_channel(self.vc_id)
        if not vc or not interaction.guild: return
        blacklisted_members = [target for target, overwrite in vc.overwrites.items() if isinstance(target, discord.Member) and overwrite.connect is False]
        if not blacklisted_members: return await interaction.response.send_message("ℹ️ ブラックリストに登録されているメンバーはいません。", ephemeral=True)
        view = ui.View(timeout=180).add_item(VCRemoveBlacklistSelect(self, blacklisted_members)); await interaction.response.send_message("ブラックリストから解除するメンバーを選んでください。", view=view, ephemeral=True)

class VoiceMaster(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.creator_channel_configs: Dict[int, Dict] = {}
        self.temp_channels: Dict[int, Dict[str, Any]] = {}
        self.admin_role_ids: List[int] = []
        self.default_category_id: Optional[int] = None
        # [개선] 유저별 채널 생성 쿨다운을 위한 딕셔너리
        self.vc_creation_cooldowns: Dict[int, float] = {}
        logger.info("VoiceMaster Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        await self.load_configs()
        self.bot.loop.create_task(self.sync_channels_from_db())

    async def load_configs(self):
        self.creator_channel_configs = {
            get_id("vc_creator_channel_id_4p"): {"type": "plaza"},
            get_id("vc_creator_channel_id_3p"): {"type": "game"},
            get_id("vc_creator_channel_id_newbie"): {"type": "newbie", "required_role_key": "role_resident_rookie"},
            get_id("vc_creator_channel_id_vip"): {"type": "vip", "required_role_key": "role_personal_room_key"},
        }
        self.creator_channel_configs = {k: v for k, v in self.creator_channel_configs.items() if k is not None}
        self.admin_role_ids = [role_id for key in ADMIN_ROLE_KEYS if (role_id := get_id(key)) is not None]
        self.default_category_id = get_id("temp_vc_category_id")
        logger.info(f"[VoiceMaster] 생성 채널 설정을 로드했습니다: {list(self.creator_channel_configs.keys())}")
        logger.info(f"[VoiceMaster] {len(self.admin_role_ids)}개의 관리자 역할을 로드했습니다.")
        if self.default_category_id:
            logger.info(f"[VoiceMaster] 기본 생성 카테고리를 로드했습니다: {self.default_category_id}")

    async def sync_channels_from_db(self):
        await self.bot.wait_until_ready()
        db_channels = await get_all_temp_channels()
        if not db_channels: return
        logger.info(f"[VoiceMaster] DB에서 {len(db_channels)}개의 임시 채널 정보를 발견하여 동기화를 시작합니다.")
        zombie_channel_ids = []
        for ch_data in db_channels:
            channel_id, guild_id, message_id = ch_data.get("channel_id"), ch_data.get("guild_id"), ch_data.get("message_id")
            if not message_id:
                zombie_channel_ids.append(channel_id)
                continue
            guild = self.bot.get_guild(guild_id)
            if guild and guild.get_channel(channel_id):
                self.temp_channels[channel_id] = { "owner_id": ch_data.get("owner_id"), "message_id": message_id, "type": ch_data.get("channel_type", "normal") }
                view = ControlPanelView(self, ch_data.get("owner_id"), channel_id, ch_data.get("channel_type", "normal"))
                self.bot.add_view(view, message_id=message_id)
            else:
                zombie_channel_ids.append(channel_id)
        if zombie_channel_ids: await remove_multiple_temp_channels(zombie_channel_ids); logger.warning(f"[VoiceMaster] 존재하지 않거나 데이터가 불완전한 {len(zombie_channel_ids)}개의 채널을 DB에서 정리했습니다.")
        logger.info(f"[VoiceMaster] 임시 채널 동기화 완료. (활성: {len(self.temp_channels)} / 정리: {len(zombie_channel_ids)})")

    async def schedule_channel_check_and_delete(self, channel: discord.VoiceChannel):
        await asyncio.sleep(1)
        try:
            refreshed_channel = channel.guild.get_channel(channel.id)
            if refreshed_channel and not refreshed_channel.members:
                await self._delete_temp_channel(refreshed_channel)
        except discord.NotFound:
            await self._cleanup_channel_data(channel.id)
        except Exception as e:
            logger.error(f"채널 체크 및 삭제 스케줄링 중 오류 발생: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        try:
            if member.bot or before.channel == after.channel: return

            # --- 채널 생성 로직 ---
            if after.channel and after.channel.id in self.creator_channel_configs:
                # [개선] 채널 생성 쿨다운 (60초) 체크
                cooldown_seconds = 60
                now = asyncio.get_event_loop().time()
                last_creation_time = self.vc_creation_cooldowns.get(member.id, 0)
                
                if (now - last_creation_time) < cooldown_seconds:
                    remaining = cooldown_seconds - (now - last_creation_time)
                    try:
                        await member.send(f"❌ ボイスチャンネルの作成は{cooldown_seconds}秒に一回だけ可能です。あと {int(remaining)}秒 お待ちください。")
                    except discord.Forbidden: pass
                    await member.move_to(None, reason="VC 생성 쿨타임")
                    return
                
                self.vc_creation_cooldowns[member.id] = now
                await self._create_temp_channel_flow(member, self.creator_channel_configs[after.channel.id], after.channel)

            # --- 채널 삭제 로직 ---
            if before.channel and before.channel.id in self.temp_channels:
                if not before.channel.members:
                    self.bot.loop.create_task(self.schedule_channel_check_and_delete(before.channel))
        
        except Exception as e:
            logger.critical(f"🚨 on_voice_state_update 이벤트 처리 중 치명적인 오류 발생! (유저: {member.id}, 이전 채널: {before.channel.id if before.channel else 'None'}, 이후 채널: {after.channel.id if after.channel else 'None'})", exc_info=True)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        if not isinstance(channel, discord.VoiceChannel): return
        if channel.id in self.temp_channels:
            await self._cleanup_channel_data(channel.id)
            logger.info(f"임시 채널 '{channel.name}'(ID: {channel.id})이 수동으로 삭제되어 내부 데이터와 DB에서 제거합니다.")

    async def _cleanup_channel_data(self, channel_id: int):
        self.temp_channels.pop(channel_id, None)
        await remove_temp_channel(channel_id)

    async def _create_temp_channel_flow(self, member: discord.Member, config: Dict, creator_channel: discord.VoiceChannel):
        # [개선] 채널 생성 전 사전 조건 확인
        member_role_ids = {r.id for r in member.roles}
        is_master = any(role_id in member_role_ids for role_id in [get_id("role_staff_village_chief"), get_id("role_staff_deputy_chief")])

        if not is_master and any(info.get('owner_id') == member.id for info in self.temp_channels.values()):
            try: await member.send("❌ 個人ボイスチャンネルは一度に一つしか所有できません。")
            except discord.Forbidden: pass
            await member.move_to(None, reason="이미 다른 개인 채널을 소유 중")
            return

        required_role_key = config.get("required_role_key")
        if not is_master and required_role_key:
            required_role_id = get_id(required_role_key)
            if not required_role_id or required_role_id not in member_role_ids:
                role_name_map = get_config("ROLE_KEY_MAP", {})
                role_name = role_name_map.get(required_role_key, "特定")
                try: await member.send(f"❌ 「{creator_channel.name}」チャンネルに入るには「{role_name}」の役割が必要です。")
                except discord.Forbidden: pass
                await member.move_to(None, reason="요구 역할 없음")
                return
        
        # [개선] 오류 처리를 위한 롤백 기능 추가
        vc: Optional[discord.VoiceChannel] = None
        try:
            vc = await self._create_discord_channel(member, config, creator_channel)
            panel_message = await self._send_control_panel(vc, member, config.get("type", "normal"))
            
            await add_temp_channel(vc.id, member.id, member.guild.id, panel_message.id, config.get("type", "normal"))
            self.temp_channels[vc.id] = {"owner_id": member.id, "message_id": panel_message.id, "type": config.get("type", "normal")}
            logger.info(f"'{config.get('type', 'normal')}' 타입 임시 채널 '{vc.name}'을(를) 생성 및 DB에 저장했습니다.")
            await member.move_to(vc, reason="생성된 임시 채널로 자동 이동")

        except Exception as e:
            logger.error(f"임시 채널 생성 플로우 중 치명적 오류 발생: {e}", exc_info=True)
            if vc:
                logger.warning(f"오류로 인해 방금 생성된 음성 채널 '{vc.name}'(ID: {vc.id})을(를) 삭제합니다.")
                try: await vc.delete(reason="생성 과정 오류로 인한 자동 삭제")
                except discord.NotFound: pass
                except Exception as del_e: logger.error(f"오류 롤백 중 채널 삭제 실패: {del_e}", exc_info=True)
            
            try: await member.send("申し訳ありません、ボイスチャンネルの作成中にエラーが発生しました。しばらくしてからもう一度お試しください。")
            except discord.Forbidden: pass
            
            if member.voice and member.voice.channel == creator_channel:
                 await member.move_to(None, reason="임시 채널 생성 오류")

    async def _create_discord_channel(self, member: discord.Member, config: Dict, creator_channel: discord.VoiceChannel) -> discord.VoiceChannel:
        guild = member.guild
        channel_type = config.get("type", "normal")
        type_info = CHANNEL_TYPE_INFO.get(channel_type, CHANNEL_TYPE_INFO["normal"])
        target_category = creator_channel.category or (guild.get_channel(self.default_category_id) if self.default_category_id else None)
        user_limit = 4 if channel_type == 'newbie' else 0
        base_name = type_info["default_name"].format(member_name=get_clean_display_name(member))
        
        if not type_info["name_editable"]:
            channels_in_category = target_category.voice_channels if target_category else guild.voice_channels
            prefix_to_check = f"・ {type_info['emoji']} ꒱ {base_name}"
            existing_numbers = {int(ch.name.split('-')[-1]) for ch in channels_in_category if ch.name.startswith(prefix_to_check) and ch.name.split('-')[-1].isdigit()}
            next_number = 1
            while next_number in existing_numbers: next_number += 1
            if next_number > 1: base_name = f"{base_name}-{next_number}"

        vc_name = f"・ {type_info['emoji']} ꒱ {base_name}"
        overwrites = self._get_permission_overwrites(guild, member, config, channel_type)
        
        return await guild.create_voice_channel(name=vc_name, category=target_category, overwrites=overwrites, user_limit=user_limit, reason=f"{member.display_name}の要請")

    def _get_permission_overwrites(self, guild: discord.Guild, owner: discord.Member, config: Dict, channel_type: str) -> Dict:
        overwrites = {owner: discord.PermissionOverwrite(manage_channels=True, manage_permissions=True, connect=True)}
        if channel_type in ['vip', 'newbie']:
            overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=True, connect=False)
        else:
            overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=True, connect=True)
        if channel_type == 'newbie':
            if (role_id := get_id(config.get("required_role_key"))) and (role := guild.get_role(role_id)):
                 overwrites[role] = discord.PermissionOverwrite(connect=True)
            for admin_role_id in self.admin_role_ids:
                if admin_role := guild.get_role(admin_role_id):
                    overwrites[admin_role] = discord.PermissionOverwrite(connect=True)
        return overwrites

    async def _send_control_panel(self, vc: discord.VoiceChannel, owner: discord.Member, channel_type: str) -> discord.Message:
        embed = discord.Embed(
            title=f"ようこそ、{get_clean_display_name(owner)}さん！", 
            description="ここはあなたのプライベートチャンネルです。\n下のボタンでチャンネルを管理できます。",
            color=0x7289DA
        ).add_field(name="チャンネルタイプ", value=f"`{channel_type.upper()}`", inline=False)
        view = ControlPanelView(self, owner.id, vc.id, channel_type)
        return await vc.send(f"{owner.mention}", embed=embed, view=view)

    async def _delete_temp_channel(self, vc: discord.VoiceChannel):
        vc_id = vc.id
        try:
            await vc.delete(reason="채널이 비어서 자동 삭제")
            logger.info(f"임시 채널 '{vc.name}'을 자동 삭제했습니다.")
        except discord.NotFound:
            logger.warning(f"임시 채널 '{vc.name}'은(는) 이미 삭제되었습니다.")
        except Exception as e:
            logger.error(f"임시 채널 '{vc.name}' 삭제 중 오류 발생: {e}", exc_info=True)
        finally:
            await self._cleanup_channel_data(vc_id)

    async def _transfer_ownership(self, interaction: discord.Interaction, vc: discord.VoiceChannel, new_owner: discord.Member):
        info = self.temp_channels.get(vc.id)
        if not info or not interaction.guild: return await interaction.followup.send("❌ チャンネル情報が見つかりません。", ephemeral=True)
        
        old_owner = interaction.guild.get_member(info['owner_id'])
        try:
            await vc.set_permissions(new_owner, manage_channels=True, manage_permissions=True, connect=True)
            if old_owner: await vc.set_permissions(old_owner, overwrite=None)
            
            await update_temp_channel_owner(vc.id, new_owner.id)
            self.temp_channels[vc.id]['owner_id'] = new_owner.id
            
            new_view = ControlPanelView(self, new_owner.id, vc.id, info['type'])
            try:
                panel_message = await vc.fetch_message(info['message_id'])
                embed = panel_message.embeds[0]
                embed.title = f"ようこそ、{get_clean_display_name(new_owner)}さん！"
                await panel_message.edit(content=f"{new_owner.mention}", embed=embed, view=new_view)
            except discord.NotFound:
                logger.warning(f"채널 {vc.id}의 제어판 메시지를 찾을 수 없어 새로 생성합니다.")
                panel_message = await self._send_control_panel(vc, new_owner, info['type'])
                await supabase.table('temp_voice_channels').update({'message_id': panel_message.id}).eq('channel_id', vc.id).execute()
                self.temp_channels[vc.id]['message_id'] = panel_message.id

            await vc.send(f"👑 {interaction.user.mention}さんがチャンネルの所有権を{new_owner.mention}さんに移譲しました。")
            await interaction.followup.send("✅ 所有権を正常に移譲しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"소유권 이전 중 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 所有権の移譲中にエラーが発生しました。", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceMaster(bot))
