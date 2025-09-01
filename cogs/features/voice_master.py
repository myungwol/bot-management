# cogs/features/voice_master.py
"""
음성 채널 자동 생성 및 제어판(Voice Master) 기능을 담당하는 Cog입니다.
하이브리드 방식으로 메모리와 DB를 함께 사용하여 안정성과 성능을 모두 확보합니다.
"""
import discord
from discord.ext import commands
from discord import ui
import logging
from typing import Dict, Optional, List, Any, Set
import asyncio
import time

from utils.database import get_id, get_all_temp_channels, add_temp_channel, update_temp_channel_owner, remove_temp_channel, remove_multiple_temp_channels, get_config
from utils.helpers import get_clean_display_name
from utils.ui_defaults import ADMIN_ROLE_KEYS

logger = logging.getLogger(__name__)

# 채널 타입별 기본 설정값
CHANNEL_TYPE_INFO = {
    "분수대":    {"emoji": "⛲", "name_editable": False, "limit_editable": True,  "default_name": "모두의 분수대", "min_limit": 4},
    "놀이터":     {"emoji": "🎮", "name_editable": True,  "limit_editable": True,  "default_name": "게임 채널", "min_limit": 3},
    "벤치":   {"emoji": "🪑", "name_editable": False, "limit_editable": True,  "default_name": "새내기의 벤치", "min_limit": 4},
    "마이룸":      {"emoji": "🏠", "name_editable": True,  "limit_editable": True,  "default_name": "{member_name}님의 마이룸"},
    "normal":   {"emoji": "🔊", "name_editable": True,  "limit_editable": True,  "default_name": "{member_name}님의 채널"} # Fallback
}


class VCEditModal(ui.Modal, title="🔊 음성 채널 설정"):
    def __init__(self, name_editable: bool, limit_editable: bool, current_name: str, current_limit: int):
        super().__init__()
        self.submitted = False
        if name_editable:
            self.name_input = ui.TextInput(label="채널 이름", placeholder="새로운 채널 이름을 입력하세요.", default=current_name, required=False, max_length=80)
            self.add_item(self.name_input)
        if limit_editable:
            self.limit_input = ui.TextInput(label="최대 입장 인원 (0은 무제한)", placeholder="숫자를 입력하세요 (예: 5)", default=str(current_limit), required=False, max_length=2)
            self.add_item(self.limit_input)
    async def on_submit(self, interaction: discord.Interaction):
        self.submitted = True
        await interaction.response.defer(ephemeral=True)

class VCInviteSelect(ui.UserSelect):
    def __init__(self, panel_view: 'ControlPanelView'):
        self.panel_view = panel_view
        super().__init__(placeholder="채널에 초대할 멤버를 선택하세요...", min_values=1, max_values=10)
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        vc = self.panel_view.cog.bot.get_channel(self.panel_view.vc_id)
        if not vc:
            msg = await interaction.followup.send("❌ 채널을 찾을 수 없습니다.", ephemeral=True)
            asyncio.create_task(msg.delete(delay=5))
            return
        invited_members = [m.mention for m in self.values if isinstance(m, discord.Member)]
        for member in self.values:
            if isinstance(member, discord.Member):
                await vc.set_permissions(member, connect=True, reason=f"{interaction.user.display_name}의 초대")
        msg = await interaction.followup.send(f"✅ {', '.join(invited_members)} 님을 채널에 초대했습니다.", ephemeral=True)
        asyncio.create_task(msg.delete(delay=5))
        try: await interaction.delete_original_response()
        except discord.NotFound: pass

class VCKickSelect(ui.Select):
    def __init__(self, panel_view: 'ControlPanelView', invited_members: List[discord.Member]):
        self.panel_view = panel_view
        options = [discord.SelectOption(label=member.display_name, value=str(member.id)) for member in invited_members]
        super().__init__(placeholder="추방할 멤버를 선택하세요...", min_values=1, max_values=len(options), options=options)
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        vc = self.panel_view.cog.bot.get_channel(self.panel_view.vc_id)
        if not vc or not interaction.guild:
            msg = await interaction.followup.send("❌ 채널을 찾을 수 없습니다.", ephemeral=True)
            asyncio.create_task(msg.delete(delay=5))
            return
        kicked_members = []
        for member_id_str in self.values:
            member = interaction.guild.get_member(int(member_id_str))
            if member:
                await vc.set_permissions(member, overwrite=None, reason=f"{interaction.user.display_name}에 의한 추방")
                if member in vc.members: await member.move_to(None, reason="채널에서 추방됨")
                kicked_members.append(member.mention)
        msg = await interaction.followup.send(f"✅ {', '.join(kicked_members)} 님을 채널에서 내보냈습니다.", ephemeral=True)
        asyncio.create_task(msg.delete(delay=5))
        try: await interaction.delete_original_response()
        except discord.NotFound: pass

class VCAddBlacklistSelect(ui.UserSelect):
    def __init__(self, panel_view: 'ControlPanelView'):
        self.panel_view = panel_view
        super().__init__(placeholder="블랙리스트에 추가할 멤버를 선택하세요...", min_values=1, max_values=10)
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        vc = self.panel_view.cog.bot.get_channel(self.panel_view.vc_id)
        if not vc:
            msg = await interaction.followup.send("❌ 채널을 찾을 수 없습니다.", ephemeral=True)
            asyncio.create_task(msg.delete(delay=5))
            return
        blacklisted = []
        for member in self.values:
            if isinstance(member, discord.Member) and member.id != self.panel_view.owner_id:
                await vc.set_permissions(member, view_channel=False, reason=f"{interaction.user.display_name}에 의한 블랙리스트 추가")
                if member in vc.members: await member.move_to(None, reason="블랙리스트에 추가됨")
                blacklisted.append(member.mention)
        msg = await interaction.followup.send(f"✅ {', '.join(blacklisted)} 님을 블랙리스트에 추가했습니다.", ephemeral=True)
        asyncio.create_task(msg.delete(delay=5))
        try: await interaction.delete_original_response()
        except discord.NotFound: pass

class VCRemoveBlacklistSelect(ui.Select):
    def __init__(self, panel_view: 'ControlPanelView', blacklisted_members: List[discord.Member]):
        self.panel_view = panel_view
        options = [discord.SelectOption(label=member.display_name, value=str(member.id)) for member in blacklisted_members]
        super().__init__(placeholder="블랙리스트에서 해제할 멤버를 선택하세요...", min_values=1, max_values=len(options), options=options)
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        vc = self.panel_view.cog.bot.get_channel(self.panel_view.vc_id)
        if not vc or not interaction.guild:
            msg = await interaction.followup.send("❌ 채널을 찾을 수 없습니다.", ephemeral=True)
            asyncio.create_task(msg.delete(delay=5))
            return
        removed = []
        for member_id_str in self.values:
            member = interaction.guild.get_member(int(member_id_str))
            if member:
                await vc.set_permissions(member, overwrite=None, reason=f"{interaction.user.display_name}에 의한 블랙리스트 해제")
                removed.append(member.mention)
        msg = await interaction.followup.send(f"✅ {', '.join(removed)} 님을 블랙리스트에서 해제했습니다.", ephemeral=True)
        asyncio.create_task(msg.delete(delay=5))
        try: await interaction.delete_original_response()
        except discord.NotFound: pass

class VCOwnerSelect(ui.UserSelect):
    def __init__(self, panel_view: 'ControlPanelView'):
        self.panel_view = panel_view
        super().__init__(placeholder="새로운 소유자를 선택해주세요...", min_values=1, max_values=1)
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
        self.cog = cog; self.owner_id = owner_id; self.vc_id = vc_id; self.channel_type = channel_type
        self.setup_buttons()
    def setup_buttons(self):
        self.clear_items()
        type_info = CHANNEL_TYPE_INFO.get(self.channel_type, CHANNEL_TYPE_INFO["normal"])
        if type_info["name_editable"] or type_info["limit_editable"]:
            self.add_item(ui.Button(label="설정", style=discord.ButtonStyle.primary, emoji="⚙️", custom_id="vc_edit", row=0))
        if self.channel_type != '마이룸':
            self.add_item(ui.Button(label="소유권 이전", style=discord.ButtonStyle.secondary, emoji="👑", custom_id="vc_transfer", row=0))
        if self.channel_type == '마이룸':
            self.add_item(ui.Button(label="초대", style=discord.ButtonStyle.success, emoji="📨", custom_id="vc_invite", row=1))
            self.add_item(ui.Button(label="내보내기", style=discord.ButtonStyle.danger, emoji="👢", custom_id="vc_kick", row=1))
        elif self.channel_type in ['분수대', '놀이터', '벤치']:
            self.add_item(ui.Button(label="블랙리스트 추가", style=discord.ButtonStyle.danger, emoji="🚫", custom_id="vc_add_blacklist", row=0))
            self.add_item(ui.Button(label="블랙리스트 해제", style=discord.ButtonStyle.secondary, emoji="🛡️", custom_id="vc_remove_blacklist", row=1))
        for item in self.children:
            if isinstance(item, ui.Button): item.callback = self.dispatch_button
    async def dispatch_button(self, interaction: discord.Interaction):
        custom_id = interaction.data.get("custom_id"); dispatch_map = { "vc_edit": self.edit_channel, "vc_transfer": self.transfer_owner, "vc_invite": self.invite_user, "vc_kick": self.kick_user, "vc_add_blacklist": self.add_to_blacklist, "vc_remove_blacklist": self.remove_from_blacklist }
        if callback := dispatch_map.get(custom_id): await callback(interaction)
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        vc = self.cog.bot.get_channel(self.vc_id)
        if not vc: self.stop(); return False
        is_admin = any(role.id in self.cog.admin_role_ids for role in interaction.user.roles)
        if interaction.user.id == self.owner_id or is_admin:
            return True
        else:
            await interaction.response.send_message("❌ 이 채널의 소유자 또는 관리자만 조작할 수 있습니다.", ephemeral=True)
            return False

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item):
        if isinstance(error, discord.NotFound): await interaction.response.send_message("❌ 이 채널은 이미 삭제되었거나, 메시지를 찾을 수 없습니다.", ephemeral=True); self.stop()
        else: logger.error(f"ControlPanelView에서 오류 발생: {error}", exc_info=True)
    async def edit_channel(self, interaction: discord.Interaction):
        vc = self.cog.bot.get_channel(self.vc_id)
        if not vc: return
        type_info = CHANNEL_TYPE_INFO.get(self.channel_type, CHANNEL_TYPE_INFO["normal"])
        current_name = vc.name.split('⊹')[-1].strip()
        modal = VCEditModal(name_editable=type_info["name_editable"], limit_editable=type_info["limit_editable"], current_name=current_name, current_limit=vc.user_limit)
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.submitted:
            vc = self.cog.bot.get_channel(self.vc_id)
            if not vc:
                msg = await interaction.followup.send("❌ 처리 중 채널을 찾을 수 없게 되었습니다.", ephemeral=True)
                asyncio.create_task(msg.delete(delay=5))
                return
            new_name, new_limit = vc.name, vc.user_limit
            if type_info["name_editable"]:
                base_name = modal.name_input.value if hasattr(modal, 'name_input') and modal.name_input.value else current_name
                new_name = f"{type_info['emoji']} ⊹ {base_name.strip()}"
            if type_info["limit_editable"] and hasattr(modal, 'limit_input') and modal.limit_input.value:
                try: 
                    new_limit = int(modal.limit_input.value)
                    if not (0 <= new_limit <= 99):
                        raise ValueError("인원 제한은 0에서 99 사이여야 합니다.")
                    min_limit = type_info.get("min_limit", 0)
                    if new_limit != 0 and new_limit < min_limit:
                        msg = await interaction.followup.send(f"❌ 이 채널의 최소 인원은 {min_limit}명입니다. {min_limit}명 이상으로 설정하거나 0(무제한)으로 설정해주세요.", ephemeral=True)
                        asyncio.create_task(msg.delete(delay=5))
                        return
                except ValueError: 
                    msg = await interaction.followup.send("❌ 인원 제한은 0에서 99 사이의 숫자로 입력해주세요.", ephemeral=True)
                    asyncio.create_task(msg.delete(delay=5))
                    return
            await vc.edit(name=new_name, user_limit=new_limit, reason=f"{interaction.user.display_name}의 요청")
            msg = await interaction.followup.send("✅ 채널 설정을 업데이트했습니다.", ephemeral=True)
            asyncio.create_task(msg.delete(delay=5))
    async def transfer_owner(self, interaction: discord.Interaction):
        view = ui.View(timeout=180).add_item(VCOwnerSelect(self)); await interaction.response.send_message("새로운 소유자를 선택해주세요.", view=view, ephemeral=True)
    async def invite_user(self, interaction: discord.Interaction):
        view = ui.View(timeout=180).add_item(VCInviteSelect(self)); await interaction.response.send_message("초대할 멤버를 선택해주세요.", view=view, ephemeral=True)
    async def kick_user(self, interaction: discord.Interaction):
        vc = self.cog.bot.get_channel(self.vc_id)
        if not vc or not interaction.guild: return
        invited_members = [ target for target, overwrite in vc.overwrites.items() if isinstance(target, discord.Member) and target.id != self.owner_id and overwrite.connect is True ]
        if not invited_members: return await interaction.response.send_message("ℹ️ 초대된 멤버가 없습니다.", ephemeral=True)
        view = ui.View(timeout=180).add_item(VCKickSelect(self, invited_members)); await interaction.response.send_message("내보낼 멤버를 선택해주세요.", view=view, ephemeral=True)
    async def add_to_blacklist(self, interaction: discord.Interaction):
        view = ui.View(timeout=180).add_item(VCAddBlacklistSelect(self)); await interaction.response.send_message("블랙리스트에 추가할 멤버를 선택해주세요.", view=view, ephemeral=True)
    async def remove_from_blacklist(self, interaction: discord.Interaction):
        vc = self.cog.bot.get_channel(self.vc_id)
        if not vc or not interaction.guild: return
        blacklisted_members = [target for target, overwrite in vc.overwrites.items() if isinstance(target, discord.Member) and overwrite.view_channel is False]
        if not blacklisted_members: return await interaction.response.send_message("ℹ️ 블랙리스트에 등록된 멤버가 없습니다.", ephemeral=True)
        view = ui.View(timeout=180).add_item(VCRemoveBlacklistSelect(self, blacklisted_members)); await interaction.response.send_message("블랙리스트에서 해제할 멤버를 선택해주세요.", view=view, ephemeral=True)

class VoiceMaster(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.creator_channel_configs: Dict[int, Dict] = {}
        self.temp_channels: Dict[int, Dict[str, Any]] = {}
        self.user_channel_map: Dict[int, int] = {}
        self.active_creations: Set[int] = set()
        self.vc_creation_cooldowns: Dict[int, float] = {}
        self.admin_role_ids: List[int] = []
        self.default_category_id: Optional[int] = None
        logger.info("VoiceMaster Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        await self.load_configs()
        self.bot.loop.create_task(self.sync_channels_from_db())

    async def reload_configs(self):
        """데이터베이스에서 최신 설정을 다시 로드하여 Cog에 적용합니다."""
        logger.info("[VoiceMaster] 설정(Config)을 실시간으로 다시 로드합니다...")
        await self.load_configs()
        logger.info(f"[VoiceMaster] 설정 리로드 완료. 현재 인식된 생성 채널: {list(self.creator_channel_configs.keys())}")
        
    async def load_configs(self):
        """Cog의 메모리에 DB로부터 설정값들을 로드합니다."""
        self.creator_channel_configs = {
            get_id("vc_creator_channel_id_4p"): {"type": "분수대"},
            get_id("vc_creator_channel_id_3p"): {"type": "놀이터"},
            get_id("vc_creator_channel_id_벤치"): {"type": "벤치", "required_role_key": "role_resident_rookie"},
            get_id("vc_creator_channel_id_마이룸"): {"type": "마이룸", "required_role_key": "role_personal_room_key"},
        }
        self.creator_channel_configs = {k: v for k, v in self.creator_channel_configs.items() if k is not None}
        self.admin_role_ids = [role_id for key in ADMIN_ROLE_KEYS if (role_id := get_id(key)) is not None]
        self.default_category_id = get_id("temp_vc_category_id")
        logger.info(f"[VoiceMaster] 생성 채널 설정을 로드했습니다: {self.creator_channel_configs}")

    async def sync_channels_from_db(self):
        await self.bot.wait_until_ready()
        db_channels = await get_all_temp_channels()
        if not db_channels: return
        logger.info(f"[VoiceMaster] DB에서 {len(db_channels)}개의 임시 채널 정보를 발견하여 동기화를 시작합니다.")
        zombie_channel_ids = []
        for ch_data in db_channels:
            channel_id, owner_id, message_id = ch_data.get("channel_id"), ch_data.get("owner_id"), ch_data.get("message_id")
            guild = self.bot.get_guild(ch_data.get("guild_id"))
            if guild and guild.get_channel(channel_id):
                self.temp_channels[channel_id] = { "owner_id": owner_id, "message_id": message_id, "type": ch_data.get("channel_type", "normal") }
                self.user_channel_map[owner_id] = channel_id
                view = ControlPanelView(self, owner_id, channel_id, ch_data.get("channel_type", "normal"))
                self.bot.add_view(view, message_id=message_id)
            else:
                zombie_channel_ids.append(channel_id)
        if zombie_channel_ids: await remove_multiple_temp_channels(zombie_channel_ids)
        logger.info(f"[VoiceMaster] 임시 채널 동기화 완료. (활성: {len(self.temp_channels)} / 정리: {len(zombie_channel_ids)})")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot or before.channel == after.channel: return
        try:
            # 채널 삭제 로직을 생성 로직보다 먼저 실행
            if before.channel and before.channel.id in self.temp_channels:
                await self._delete_temp_channel(before.channel)

            # 채널 생성 로직
            if after.channel and after.channel.id in self.creator_channel_configs:
                if member.id in self.active_creations: return
                if member.id in self.user_channel_map:
                    try: await member.send("❌ 개인 음성 채널은 한 번에 하나만 소유할 수 있습니다. 이전 채널이 삭제 처리 중일 수 있으니 잠시 후 다시 시도해주세요.")
                    except discord.Forbidden: pass
                    return await member.move_to(None, reason="이미 다른 개인 채널을 소유 중")
                
                cooldown_seconds = 60
                now = time.monotonic()
                if (now - self.vc_creation_cooldowns.get(member.id, 0)) < cooldown_seconds:
                    remaining = cooldown_seconds - (now - self.vc_creation_cooldowns.get(member.id, 0))
                    try: await member.send(f"❌ 음성 채널 생성은 {cooldown_seconds}초에 한 번만 가능합니다. {int(remaining)+1}초 후에 다시 시도해주세요.")
                    except discord.Forbidden: pass
                    return await member.move_to(None, reason="VC 생성 쿨타임")
                
                self.active_creations.add(member.id)
                self.vc_creation_cooldowns[member.id] = now
                await self._create_temp_channel_flow(member, self.creator_channel_configs[after.channel.id], after.channel)
                self.active_creations.discard(member.id)

            # 채널 입장 시 조건 확인 및 강제 퇴장 로직
            if after.channel and after.channel.id in self.temp_channels:
                channel_info = self.temp_channels.get(after.channel.id)
                if not channel_info: return
                channel_type = channel_info.get("type")
                if channel_type == "벤치":
                    is_owner = member.id == channel_info.get("owner_id")
                    is_admin = any(role.id in self.admin_role_ids for role in member.roles)
                    if not (is_owner or is_admin):
                        required_role_id = get_id("role_resident_rookie")
                        has_role = required_role_id in {r.id for r in member.roles}
                        if not has_role:
                            try:
                                role_name_map = get_config("ROLE_KEY_MAP", {})
                                role_name = role_name_map.get("role_resident_rookie", "새내기 주민")
                                await member.send(f"❌ '{after.channel.name}' 채널에 입장하려면 '{role_name}' 역할이 필요합니다.")
                            except discord.Forbidden: pass
                            await member.move_to(None, reason="벤치 채널 입장 조건 미충족")
                            return
        
        except Exception as e:
            self.active_creations.discard(member.id)
            logger.critical(f"🚨 on_voice_state_update 이벤트 처리 중 치명적인 오류: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        if channel.id in self.temp_channels:
            await self._cleanup_channel_data(channel.id)

    async def _cleanup_channel_data(self, channel_id: int):
        info = self.temp_channels.pop(channel_id, None)
        if info and (owner_id := info.get("owner_id")):
            self.user_channel_map.pop(owner_id, None)
        await remove_temp_channel(channel_id)

    async def _create_temp_channel_flow(self, member: discord.Member, config: Dict, creator_channel: discord.VoiceChannel):
        required_role_key = config.get("required_role_key")
        if required_role_key:
            required_role_id = get_id(required_role_key)
            if not required_role_id:
                logger.error(f"'{required_role_key}'에 해당하는 역할 ID를 DB에서 찾을 수 없습니다. 관리자 명령어로 역할을 설정해주세요.")
                try: await member.send(f"죄송합니다. '{creator_channel.name}' 채널 생성에 필요한 역할 설정이 완료되지 않았습니다. 서버 관리자에게 문의해주세요.")
                except discord.Forbidden: pass
                await member.move_to(None, reason="필요 역할 미설정 오류")
                return
            if required_role_id not in {r.id for r in member.roles}:
                role_name_map = get_config("ROLE_KEY_MAP", {})
                role_name = role_name_map.get(required_role_key, "필수")
                logger.info(f"{member.display_name}님이 '{role_name}' 역할이 없어 '{creator_channel.name}' 채널 생성에 실패했습니다.")
                try: await member.send(f"❌ '{creator_channel.name}' 채널을 생성하려면 '{role_name}' 역할이 필요합니다.")
                except discord.Forbidden: pass
                await member.move_to(None, reason="요구 역할 없음")
                return
        
        vc: Optional[discord.VoiceChannel] = None
        try:
            vc = await self._create_discord_channel(member, config, creator_channel)
            panel_message = await self._send_control_panel(vc, member, config.get("type", "normal"))
            await add_temp_channel(vc.id, member.id, member.guild.id, panel_message.id, config.get("type", "normal"))
            self.temp_channels[vc.id] = {"owner_id": member.id, "message_id": panel_message.id, "type": config.get("type", "normal")}
            self.user_channel_map[member.id] = vc.id
            await member.move_to(vc)
        except Exception as e:
            logger.error(f"임시 채널 생성 플로우 중 오류: {e}", exc_info=True)
            if vc:
                try: await vc.delete(reason="생성 과정 오류로 인한 자동 삭제")
                except discord.NotFound: pass
            try: await member.send("죄송합니다, 음성 채널을 만드는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")
            except discord.Forbidden: pass
            if member.voice and member.voice.channel == creator_channel:
                 await member.move_to(None, reason="임시 채널 생성 오류")

    async def _create_discord_channel(self, member: discord.Member, config: Dict, creator_channel: discord.VoiceChannel) -> discord.VoiceChannel:
        guild = member.guild
        channel_type = config.get("type", "normal")
        type_info = CHANNEL_TYPE_INFO.get(channel_type, CHANNEL_TYPE_INFO["normal"])
        target_category = creator_channel.category or (guild.get_channel(self.default_category_id) if self.default_category_id else None)
        user_limit = 4 if channel_type == '벤치' else 0
        base_name = type_info["default_name"].format(member_name=get_clean_display_name(member))
        
        if not type_info["name_editable"]:
            channels_in_category = target_category.voice_channels if target_category else guild.voice_channels
            prefix_to_check = f"{type_info['emoji']} ⊹ {base_name}"
            existing_numbers = []
            for ch in channels_in_category:
                if ch.name.startswith(prefix_to_check):
                    suffix = ch.name.replace(prefix_to_check, "").strip()
                    if suffix.startswith('-') and suffix[1:].isdigit():
                        existing_numbers.append(int(suffix[1:]))
            next_number = max(existing_numbers) + 1 if existing_numbers else 1
            if next_number > 1: base_name = f"{base_name}-{next_number}"

        vc_name = f"{type_info['emoji']} ⊹ {base_name}"
        overwrites = self._get_permission_overwrites(guild, member, channel_type)
        
        position: Optional[int] = None
        if target_category:
            sorted_channels = sorted(target_category.voice_channels, key=lambda c: c.position)
            all_benches = [ch for ch in sorted_channels if '🪑' in ch.name]
            all_fountains = [ch for ch in sorted_channels if '⛲' in ch.name]
            if channel_type == '벤치':
                if all_benches: position = all_benches[-1].position + 1
                elif all_fountains: position = all_fountains[0].position
            elif channel_type == '분수대':
                if all_fountains: position = all_fountains[-1].position + 1
                elif all_benches: position = all_benches[-1].position + 1
        
        return await guild.create_voice_channel(name=vc_name, category=target_category, overwrites=overwrites, user_limit=user_limit, position=position, reason=f"{member.display_name}의 요청")

    def _get_permission_overwrites(self, guild: discord.Guild, owner: discord.Member, channel_type: str) -> Dict:
        overwrites = {owner: discord.PermissionOverwrite(connect=True)}
        if channel_type in ['마이룸']:
            overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=True, connect=False)
        else:
            overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=True, connect=True)
        if channel_type == '벤치':
            overwrites[guild.default_role] = discord.PermissionOverwrite(view_channel=True, connect=False)
            if (role_id := get_id("role_resident_rookie")) and (role := guild.get_role(role_id)):
                 overwrites[role] = discord.PermissionOverwrite(connect=True)
            for admin_role_id in self.admin_role_ids:
                if admin_role := guild.get_role(admin_role_id):
                    overwrites[admin_role] = discord.PermissionOverwrite(connect=True)
        return overwrites

    async def _send_control_panel(self, vc: discord.VoiceChannel, owner: discord.Member, channel_type: str) -> discord.Message:
        embed = discord.Embed(
            title=f"환영합니다, {get_clean_display_name(owner)}님!", 
            description="이곳은 당신의 개인 채널입니다.\n아래 버튼으로 채널을 관리할 수 있습니다.",
            color=0x7289DA
        ).add_field(name="채널 타입", value=f"`{channel_type.upper()}`", inline=False)
        view = ControlPanelView(self, owner.id, vc.id, channel_type)
        return await vc.send(f"{owner.mention}", embed=embed, view=view)

    async def _delete_temp_channel(self, vc: discord.VoiceChannel):
        await asyncio.sleep(1)
        try:
            vc_refreshed = self.bot.get_channel(vc.id)
            if vc_refreshed and vc.id in self.temp_channels and not vc_refreshed.members:
                await vc_refreshed.delete(reason="채널이 비어 자동 삭제됨")
                logger.info(f"임시 채널 '{vc_refreshed.name}'을(를) 자동 삭제했습니다.")
                await self._cleanup_channel_data(vc_refreshed.id)
        except discord.NotFound:
            logger.warning(f"삭제하려던 임시 채널(ID: {vc.id})을 찾을 수 없습니다. 데이터만 정리합니다.")
            await self._cleanup_channel_data(vc.id)
        except Exception as e:
            logger.error(f"임시 채널 '{vc.name}' 삭제 중 오류: {e}", exc_info=True)

    async def _transfer_ownership(self, interaction: discord.Interaction, vc: discord.VoiceChannel, new_owner: discord.Member):
        info = self.temp_channels.get(vc.id)
        if not info or not interaction.guild:
            msg = await interaction.followup.send("❌ 채널 정보를 찾을 수 없습니다.", ephemeral=True)
            asyncio.create_task(msg.delete(delay=5))
            return
        old_owner = interaction.guild.get_member(info['owner_id'])
        try:
            overwrites = vc.overwrites
            overwrites[new_owner] = discord.PermissionOverwrite(connect=True)
            if old_owner and old_owner in overwrites: del overwrites[old_owner]
            await vc.edit(overwrites=overwrites, reason=f"소유권 이전: {old_owner.display_name if old_owner else '알 수 없음'} -> {new_owner.display_name}")
            await update_temp_channel_owner(vc.id, new_owner.id)
            self.temp_channels[vc.id]['owner_id'] = new_owner.id
            if old_owner: self.user_channel_map.pop(old_owner.id, None)
            self.user_channel_map[new_owner.id] = vc.id
            panel_message = await vc.fetch_message(info['message_id'])
            embed = panel_message.embeds[0]; embed.title = f"환영합니다, {get_clean_display_name(new_owner)}님!"
            await panel_message.edit(content=f"{new_owner.mention}", embed=embed, view=ControlPanelView(self, new_owner.id, vc.id, info['type']))
            await vc.send(f"👑 {interaction.user.mention}님이 채널 소유권을 {new_owner.mention}님에게 이전했습니다.")
            msg = await interaction.followup.send("✅ 소유권을 성공적으로 이전했습니다.", ephemeral=True)
            asyncio.create_task(msg.delete(delay=5))
        except Exception as e:
            logger.error(f"소유권 이전 중 오류: {e}", exc_info=True)
            msg = await interaction.followup.send("❌ 소유권 이전 중 오류가 발생했습니다.", ephemeral=True)
            asyncio.create_task(msg.delete(delay=5))

async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceMaster(bot))
