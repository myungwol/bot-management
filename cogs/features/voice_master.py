# cogs/features/voice_master.py
"""
음성 채널 자동 생성 및 제어판(Voice Master) 기능을 담당하는 Cog입니다.
"""
import discord
from discord.ext import commands
from discord import ui, app_commands
import logging
from typing import Dict, Optional, List, Set

from utils.database import get_id

logger = logging.getLogger(__name__)

# --- 제어판용 UI 클래스들 ---

class VCEditModal(ui.Modal, title="🔊 통화방 설정 변경"):
    name = ui.TextInput(label="채널 이름", placeholder="새로운 채널 이름을 입력하세요.", required=False, max_length=100)
    limit = ui.TextInput(label="인원 제한 (2-99)", placeholder="숫자만 입력하세요 (예: 5). 0은 무제한입니다.", required=False, max_length=2)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        # 여기에 이름과 인원 제한을 변경하는 로직이 들어감 (View에서 처리)

class VCKickModal(ui.Modal, title="🚫 멤버 내보내기"):
    member = ui.TextInput(label="멤버의 이름 또는 아이디", placeholder="내보낼 멤버의 서버 닉네임 또는 Discord 아이디를 입력하세요.", required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

class VCOwnerModal(ui.Modal, title="👑 소유권 이전"):
    member = ui.TextInput(label="멤버의 이름 또는 아이디", placeholder="소유권을 넘겨줄 멤버의 서버 닉네임 또는 Discord 아이디를 입력하세요.", required=True)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)


class ControlPanelView(ui.View):
    def __init__(self, cog: 'VoiceMaster', owner_id: int, vc_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.owner_id = owner_id
        self.vc_id = vc_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # 채널 소유자만 버튼을 누를 수 있도록 확인
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("❌ 이 채널의 소유자만 제어판을 사용할 수 있습니다.", ephemeral=True)
            return False
        return True

    @ui.button(label="설정", style=discord.ButtonStyle.primary, emoji="⚙️", custom_id="vc_edit")
    async def edit_channel(self, interaction: discord.Interaction, button: ui.Button):
        vc = self.cog.bot.get_channel(self.vc_id)
        if not vc: return await interaction.response.send_message("❌ 채널을 찾을 수 없습니다.", ephemeral=True)
        
        modal = VCEditModal()
        modal.name.default = vc.name
        modal.limit.default = str(vc.user_limit)
        await interaction.response.send_modal(modal)
        await modal.wait()

        if modal.is_submitted():
            new_name = modal.name.value or vc.name
            try:
                new_limit_str = modal.limit.value
                new_limit = int(new_limit_str) if new_limit_str else vc.user_limit
                if not (0 <= new_limit <= 99): raise ValueError()
            except (ValueError, TypeError):
                return await interaction.followup.send("❌ 인원 제한은 0에서 99 사이의 숫자여야 합니다.", ephemeral=True)
            
            await vc.edit(name=new_name, user_limit=new_limit, reason=f"{interaction.user}님의 요청")
            await interaction.followup.send("✅ 채널 이름과 인원 제한을 업데이트했습니다.", ephemeral=True)

    @ui.button(label="내보내기", style=discord.ButtonStyle.danger, emoji="🚫", custom_id="vc_kick")
    async def kick_member(self, interaction: discord.Interaction, button: ui.Button):
        modal = VCKickModal()
        await interaction.response.send_modal(modal)
        await modal.wait()

        if modal.is_submitted():
            vc = self.cog.bot.get_channel(self.vc_id)
            if not vc: return await interaction.followup.send("❌ 채널을 찾을 수 없습니다.", ephemeral=True)
            
            target_name = modal.member.value.lower()
            target: discord.Member = None
            for m in vc.members:
                if target_name in m.display_name.lower() or target_name == str(m.id):
                    target = m
                    break
            
            if target and target.id != self.owner_id:
                await target.move_to(None, reason=f"{interaction.user}님이 채널에서 내보냈습니다.")
                await interaction.followup.send(f"✅ {target.display_name} 님을 채널에서 내보냈습니다.", ephemeral=True)
            elif target:
                await interaction.followup.send("❌ 자기 자신을 내보낼 수 없습니다.", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ '{modal.member.value}'님을 현재 채널에서 찾을 수 없습니다.", ephemeral=True)

    @ui.button(label="소유권 이전", style=discord.ButtonStyle.secondary, emoji="👑", custom_id="vc_transfer")
    async def transfer_owner(self, interaction: discord.Interaction, button: ui.Button):
        # ... (소유권 이전 로직 구현)
        await interaction.response.send_message("🚧 기능 준비 중입니다.", ephemeral=True)


class VoiceMaster(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.creator_channel_ids: Dict[int, int] = {} # key: 트리거 채널 ID, value: 최소 인원
        # key: 생성된 임시 VC ID, value: {owner_id, tc_id}
        self.temp_channels: Dict[int, Dict] = {} 
        logger.info("VoiceMaster Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        await self.load_configs()

    async def load_configs(self):
        """DB에서 '음성 채널 생성' 트리거 채널들의 ID를 불러옵니다."""
        creator_3p = get_id("vc_creator_channel_id_3p")
        creator_4p = get_id("vc_creator_channel_id_4p")
        if creator_3p: self.creator_channel_ids[creator_3p] = 3
        if creator_4p: self.creator_channel_ids[creator_4p] = 4
        logger.info(f"[VoiceMaster] 생성 채널 ID를 로드했습니다: {self.creator_channel_ids}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot: return

        # 채널 생성 로직
        if after.channel and after.channel.id in self.creator_channel_ids:
            min_limit = self.creator_channel_ids[after.channel.id]
            # 이미 자신의 임시 채널이 있는지 확인
            if any(info['owner_id'] == member.id for info in self.temp_channels.values()):
                # 소유한 채널로 이동시키는 로직 (생략 가능)
                return
            await self._create_temp_channel(member, min_limit)

        # 채널 삭제 로직
        if before.channel and before.channel.id in self.temp_channels:
            if len(before.channel.members) == 0:
                await self._delete_temp_channel(before.channel)

    async def _create_temp_channel(self, member: discord.Member, limit: int):
        guild = member.guild
        creator_channel = guild.get_channel(list(self.creator_channel_ids.keys())[0]) # 카테고리 참조용

        try:
            # 1. 전용 텍스트 채널(TC) 생성
            tc_overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=False),
                member: discord.PermissionOverwrite(view_channel=True)
            }
            tc_name = f"💬︱{member.display_name}님의-채팅"
            tc = await guild.create_text_channel(
                name=tc_name,
                category=creator_channel.category,
                overwrites=tc_overwrites,
                reason=f"{member.display_name}의 임시 음성 채널용 텍스트 채널"
            )

            # 2. 임시 음성 채널(VC) 생성
            vc_overwrites = {
                guild.default_role: discord.PermissionOverwrite(view_channel=True),
                member: discord.PermissionOverwrite(manage_channels=True, manage_permissions=True)
            }
            vc_name = f"🔊︱{member.display_name}님의-채널"
            vc = await guild.create_voice_channel(
                name=vc_name,
                category=creator_channel.category,
                overwrites=vc_overwrites,
                user_limit=limit, # 초기 인원 제한 설정
                reason=f"{member.display_name}의 요청으로 임시 채널 생성"
            )

            # 3. 생성된 채널 정보 저장
            self.temp_channels[vc.id] = {"owner_id": member.id, "tc_id": tc.id}
            logger.info(f"임시 채널 '{vc.name}'(VC)와 '{tc.name}'(TC)을(를) 생성했습니다.")

            # 4. 제어판 메시지 전송
            embed = discord.Embed(
                title=f"🔊 {member.display_name}님의 통화방 제어판",
                description="아래 버튼을 사용하여 채널을 관리할 수 있습니다.",
                color=0x7289DA
            )
            view = ControlPanelView(self, member.id, vc.id)
            await tc.send(embed=embed, view=view)

            # 5. 멤버를 VC로 이동
            await member.move_to(vc, reason="생성된 임시 채널로 자동 이동")

        except Exception as e:
            logger.error(f"임시 채널 생성 중 예기치 않은 오류 발생: {e}", exc_info=True)

    async def _delete_temp_channel(self, vc: discord.VoiceChannel):
        try:
            info = self.temp_channels.get(vc.id)
            if not info: return

            # 연결된 텍스트 채널(TC) 찾아서 삭제
            if tc := self.bot.get_channel(info['tc_id']):
                await tc.delete(reason="연결된 음성 채널이 비어 자동 삭제")
            
            # 음성 채널(VC) 삭제
            await vc.delete(reason="채널에 아무도 없어 자동 삭제")

            del self.temp_channels[vc.id]
            logger.info(f"임시 채널 '{vc.name}'과 연결된 텍스트 채널을 자동 삭제했습니다.")
        except Exception as e:
            logger.error(f"임시 채널 삭제 중 예기치 않은 오류 발생: {e}", exc_info=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceMaster(bot))
