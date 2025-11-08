# cogs/features/voice_master.py
"""
음성 채널 자동 생성 및 제어판(Voice Master) 기능을 담당하는 Cog입니다.
"""
import discord
from discord.ext import commands
from discord import ui
import logging
from typing import Dict, Optional, Any, Set
import asyncio
import time

# ▼▼▼ [핵심 수정] 누락된 함수들을 import 목록에 추가합니다. ▼▼▼
from utils.database import (
    get_id, get_all_temp_channels, add_temp_channel, 
    update_temp_channel_owner, remove_temp_channel, remove_multiple_temp_channels
)
from utils.helpers import get_clean_display_name
from utils.ui_defaults import ADMIN_ROLE_KEYS
# ▲▲▲ [수정 완료] ▲▲▲

logger = logging.getLogger(__name__)

CHANNEL_TYPE_INFO = {
    "mixer":  {"emoji": "🧊", "name_editable": False, "limit_editable": False, "default_name": "소형 믹서", "user_limit": 1},
    "line":   {"emoji": "🔧", "name_editable": False, "limit_editable": False, "default_name": "미니 라인", "user_limit": 2},
    "sample": {"emoji": "⚙️", "name_editable": False, "limit_editable": False, "default_name": "샘플 룸",  "user_limit": 3},
    "game":   {"emoji": "🔫", "name_editable": True,  "limit_editable": False, "default_name": "{member_name}의 게임방", "user_limit": 0}
}

# ▼▼▼ [추가] 채널 자동 정렬 순서를 정의합니다. ▼▼▼
CHANNEL_SORT_ORDER = ["mixer", "line", "sample"]


class VCEditModal(ui.Modal, title="게임방 이름 변경"):
    name_input = ui.TextInput(label="채널 이름", placeholder="새로운 채널 이름을 입력하세요.", required=True, max_length=80)
    def __init__(self, current_name: str):
        super().__init__(); self.name_input.default = current_name; self.submitted = False
    async def on_submit(self, interaction: discord.Interaction):
        self.submitted = True; await interaction.response.defer(ephemeral=True)

class VCOwnerSelect(ui.UserSelect):
    def __init__(self, panel_view: 'ControlPanelView'):
        self.panel_view = panel_view; super().__init__(placeholder="새로운 소유자를 선택해주세요...", min_values=1, max_values=1)
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
        self.cog, self.owner_id, self.vc_id, self.channel_type = cog, owner_id, vc_id, channel_type
        self.setup_buttons()
    def setup_buttons(self):
        self.clear_items()
        self.add_item(ui.Button(label="이름 변경", style=discord.ButtonStyle.primary, emoji="✏️", custom_id="vc_edit"))
        self.add_item(ui.Button(label="소유권 이전", style=discord.ButtonStyle.secondary, emoji="👑", custom_id="vc_transfer"))
        for item in self.children:
            if isinstance(item, ui.Button): item.callback = self.dispatch_button
    async def dispatch_button(self, interaction: discord.Interaction):
        custom_id = interaction.data.get("custom_id")
        if custom_id == "vc_edit": await self.edit_channel(interaction)
        elif custom_id == "vc_transfer": await self.transfer_owner(interaction)
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not (vc := self.cog.bot.get_channel(self.vc_id)): self.stop(); return False
        is_admin = any(role.id in self.cog.admin_role_ids for role in interaction.user.roles)
        if interaction.user.id == self.owner_id or is_admin: return True
        await interaction.response.send_message("❌ 이 채널의 소유자 또는 관리자만 조작할 수 있습니다.", ephemeral=True)
        return False
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: ui.Item):
        logger.error(f"ControlPanelView에서 오류 발생: {error}", exc_info=True)
    async def edit_channel(self, interaction: discord.Interaction):
        vc = self.cog.bot.get_channel(self.vc_id);
        if not vc: return
        current_name = vc.name.split('ㆍ')[-1].strip(); modal = VCEditModal(current_name=current_name)
        await interaction.response.send_modal(modal); await modal.wait()
        if modal.submitted:
            if not (vc := self.cog.bot.get_channel(self.vc_id)): return
            type_info = CHANNEL_TYPE_INFO["game"]
            new_name = f"{type_info['emoji']}ㆍ{modal.name_input.value.strip()}"
            await vc.edit(name=new_name, reason=f"{interaction.user.display_name}의 요청")
            msg = await interaction.followup.send("✅ 채널 이름을 업데이트했습니다.", ephemeral=True); asyncio.create_task(msg.delete(delay=5))
    async def transfer_owner(self, interaction: discord.Interaction):
        view = ui.View(timeout=180).add_item(VCOwnerSelect(self))
        await interaction.response.send_message("새로운 소유자를 선택해주세요.", view=view, ephemeral=True)

class VoiceMaster(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.creator_channel_configs: Dict[int, Dict] = {}
        self.temp_channels: Dict[int, Dict[str, Any]] = {}
        self.user_channel_map: Dict[int, int] = {}
        self.active_creations: Set[int] = set()
        
        # ▼▼▼ [추가] 쿨타임 저장을 위한 딕셔너리 ▼▼▼
        self.vc_creation_cooldowns: Dict[int, float] = {}
        
        self.admin_role_ids: List[int] = []
        self.default_category_id: Optional[int] = None
        logger.info("VoiceMaster Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        await self.load_configs(); self.bot.loop.create_task(self.sync_channels_from_db())

    async def load_configs(self):
        self.creator_channel_configs = {
            get_id("vc_creator_mixer"): {"type": "mixer"}, get_id("vc_creator_line"): {"type": "line"},
            get_id("vc_creator_sample"): {"type": "sample"}, get_id("vc_creator_game"): {"type": "game"},
        }
        self.creator_channel_configs = {k: v for k, v in self.creator_channel_configs.items() if k is not None}
        self.admin_role_ids = [role_id for key in ADMIN_ROLE_KEYS if (role_id := get_id(key)) is not None]
        self.default_category_id = get_id("temp_vc_category_id")
        logger.info(f"[VoiceMaster] 생성 채널 설정을 로드했습니다: {self.creator_channel_configs}")

    async def sync_channels_from_db(self):
        await self.bot.wait_until_ready()
        db_channels = await get_all_temp_channels();
        if not db_channels: return
        logger.info(f"[VoiceMaster] DB에서 {len(db_channels)}개의 임시 채널 정보를 발견하여 동기화를 시작합니다.")
        zombie_channel_ids = []
        for ch_data in db_channels:
            channel_id, owner_id = ch_data.get("channel_id"), ch_data.get("owner_id")
            guild = self.bot.get_guild(ch_data.get("guild_id"))
            if guild and guild.get_channel(channel_id):
                self.temp_channels[channel_id] = ch_data; self.user_channel_map[owner_id] = channel_id
                if ch_data.get("channel_type") == "game":
                    self.bot.add_view(ControlPanelView(self, owner_id, channel_id, "game"), message_id=ch_data.get("message_id"))
            else: zombie_channel_ids.append(channel_id)
        if zombie_channel_ids: await remove_multiple_temp_channels(zombie_channel_ids)
        logger.info(f"[VoiceMaster] 임시 채널 동기화 완료. (활성: {len(self.temp_channels)} / 정리: {len(zombie_channel_ids)})")

    # ▼▼▼ on_voice_state_update 함수 전체를 교체합니다. ▼▼▼
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot or before.channel == after.channel: return
        
        try:
            # 채널 퇴장 시 삭제 로직
            if before.channel and before.channel.id in self.temp_channels:
                await self._delete_temp_channel(before.channel)

            # 채널 생성 로직
            if after.channel and after.channel.id in self.creator_channel_configs:
                if member.id in self.active_creations: return
                
                # --- ▼▼▼ [핵심 수정] 개수 제한 제거 및 쿨타임 적용 ▼▼▼
                
                # 1. 쿨타임(60초)을 확인합니다.
                cooldown_seconds = 60
                now = time.monotonic()
                last_creation_time = self.vc_creation_cooldowns.get(member.id, 0)

                if (now - last_creation_time) < cooldown_seconds:
                    remaining = int(cooldown_seconds - (now - last_creation_time)) + 1
                    try:
                        await member.send(f"❌ 음성 채널 생성은 {cooldown_seconds}초에 한 번만 가능합니다. {remaining}초 후에 다시 시도해주세요.")
                    except discord.Forbidden:
                        pass
                    await member.move_to(None, reason=f"음성 채널 생성 쿨타임 ({remaining}초 남음)")
                    return
                
                # 2. '이미 채널을 소유하고 있는지' 확인하는 로직을 삭제했습니다.
                
                # 3. 쿨타임을 갱신합니다.
                self.vc_creation_cooldowns[member.id] = now

                # --- ▲▲▲ [수정 완료] ▲▲▲

                self.active_creations.add(member.id)
                await self._create_temp_channel_flow(member, self.creator_channel_configs[after.channel.id], after.channel)
                self.active_creations.discard(member.id)
        
        except Exception as e:
            self.active_creations.discard(member.id)
            logger.error(f"on_voice_state_update 이벤트 처리 중 오류: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        if channel.id in self.temp_channels: await self._cleanup_channel_data(channel.id)

    async def _cleanup_channel_data(self, channel_id: int):
        info = self.temp_channels.pop(channel_id, None)
        if info and (owner_id := info.get("owner_id")): self.user_channel_map.pop(owner_id, None)
        await remove_temp_channel(channel_id)

    # ▼▼▼ [핵심 수정 1/2] 속도 개선을 위해 작업 순서를 변경합니다. ▼▼▼
    async def _create_temp_channel_flow(self, member: discord.Member, config: Dict, creator_channel: discord.VoiceChannel):
        vc: Optional[discord.VoiceChannel] = None
        try:
            # 1. 채널을 먼저 생성합니다.
            vc = await self._create_discord_channel(member, config, creator_channel)
            
            # 2. 사용자를 즉시 이동시켜 대기 시간을 최소화합니다.
            await member.move_to(vc)

            # 3. 사용자 이동 후, 나머지 작업을 처리합니다.
            channel_type = config.get("type")
            message_id = None
            if channel_type == "game":
                panel_message = await self._send_control_panel(vc, member)
                message_id = panel_message.id

            await add_temp_channel(vc.id, member.id, member.guild.id, message_id, channel_type)
            self.temp_channels[vc.id] = {"owner_id": member.id, "message_id": message_id, "type": channel_type}
            self.user_channel_map[member.id] = vc.id

        except Exception as e:
            logger.error(f"임시 채널 생성 플로우 중 오류: {e}", exc_info=True)
            if vc: await vc.delete(reason="생성 과정 오류")
            # 사용자가 이미 이동했을 수 있으므로, 생성 채널에 남아있는지 확인하는 대신 오류 발생 시 연결을 끊습니다.
            if member.voice: await member.move_to(None, reason="임시 채널 생성 오류")

    # ▼▼▼ [핵심 수정] 정렬 로직을 최종적으로 수정합니다. ▼▼▼
    async def _create_discord_channel(self, member: discord.Member, config: Dict, creator_channel: discord.VoiceChannel) -> discord.VoiceChannel:
        guild = member.guild
        channel_type = config.get("type")
        type_info = CHANNEL_TYPE_INFO[channel_type]
        target_category = creator_channel.category or (guild.get_channel(self.default_category_id) if self.default_category_id else None)
        
        # 이름 생성
        if not type_info["name_editable"]:
            base_name = type_info["default_name"]
            vc_name = f"{type_info['emoji']}₊꒱ {base_name} 사용 중"
        else:
            base_name = type_info["default_name"].format(member_name=get_clean_display_name(member))
            vc_name = f"{type_info['emoji']}ㆍ{base_name}"
            
        # --- 최종 위치 계산 로직 ---
        
        final_position = creator_channel.position + 1 # 기본 위치 (게임방 또는 fallback)

        # 고정 채널(믹서, 라인, 샘플룸)에만 정렬 로직 적용
        if channel_type in CHANNEL_SORT_ORDER:
            # 기준점: '샘플룸 생성' 채널. 모든 임시 채널은 이 채널 아래에 정렬됩니다.
            anchor_ch_id = get_id("vc_creator_sample")
            anchor_ch = guild.get_channel(anchor_ch_id) if anchor_ch_id else creator_channel
            
            if anchor_ch:
                # 기준점의 현재 위치
                base_position = anchor_ch.position
                
                # 현재 생성된 각 채널 타입의 개수를 정확히 셉니다.
                mixer_count = sum(1 for tc in self.temp_channels.values() if tc.get("type") == "mixer")
                line_count = sum(1 for tc in self.temp_channels.values() if tc.get("type") == "line")
                
                # 생성하려는 채널 타입에 따라 삽입할 위치를 결정합니다.
                if channel_type == "mixer":
                    # 믹서는 항상 기준점 바로 아래에 삽입됩니다.
                    final_position = base_position + 1
                elif channel_type == "line":
                    # 라인은 모든 믹서 채널들 다음에 삽입됩니다.
                    final_position = base_position + 1 + mixer_count
                elif channel_type == "sample":
                    # 샘플룸은 모든 믹서와 라인 채널들 다음에 삽입됩니다.
                    final_position = base_position + 1 + mixer_count + line_count
        
        # --- 위치 계산 로직 종료 ---

        return await guild.create_voice_channel(
            name=vc_name, 
            category=target_category, 
            user_limit=type_info["user_limit"],
            position=final_position,
            reason=f"{member.display_name}의 요청"
        )

    async def _send_control_panel(self, vc: discord.VoiceChannel, owner: discord.Member) -> discord.Message:
        embed = discord.Embed(title=f"환영합니다, {get_clean_display_name(owner)}님!", description="이곳은 당신의 개인 채널입니다.\n아래 버튼으로 채널을 관리할 수 있습니다.", color=0x7289DA)
        view = ControlPanelView(self, owner.id, vc.id, "game"); return await vc.send(f"{owner.mention}", embed=embed, view=view, allowed_mentions=discord.AllowedMentions(users=True))

    async def _delete_temp_channel(self, vc: discord.VoiceChannel):
        await asyncio.sleep(1)
        try:
            vc_refreshed = self.bot.get_channel(vc.id)
            if vc_refreshed and vc.id in self.temp_channels and not vc_refreshed.members:
                await vc_refreshed.delete(reason="채널이 비어 자동 삭제됨")
                await self._cleanup_channel_data(vc_refreshed.id)
        except discord.NotFound: await self._cleanup_channel_data(vc.id)
        except Exception as e: logger.error(f"임시 채널 '{vc.name}' 삭제 중 오류: {e}", exc_info=True)

    async def _transfer_ownership(self, interaction: discord.Interaction, vc: discord.VoiceChannel, new_owner: discord.Member):
        info = self.temp_channels.get(vc.id);
        if not info or not interaction.guild: return
        old_owner_id = info['owner_id']
        try:
            await update_temp_channel_owner(vc.id, new_owner.id)
            self.temp_channels[vc.id]['owner_id'] = new_owner.id; self.user_channel_map.pop(old_owner_id, None); self.user_channel_map[new_owner.id] = vc.id
            panel_message = await vc.fetch_message(info['message_id']); embed = panel_message.embeds[0]
            embed.title = f"환영합니다, {get_clean_display_name(new_owner)}님!"
            await panel_message.edit(content=f"{new_owner.mention}", embed=embed, view=ControlPanelView(self, new_owner.id, vc.id, "game"))
            await vc.send(f"👑 {interaction.user.mention}님이 채널 소유권을 {new_owner.mention}님에게 이전했습니다.")
            msg = await interaction.followup.send("✅ 소유권을 성공적으로 이전했습니다.", ephemeral=True); asyncio.create_task(msg.delete(delay=5))
        except Exception as e: logger.error(f"소유권 이전 중 오류: {e}", exc_info=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceMaster(bot))
