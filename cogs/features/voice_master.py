# cogs/features/voice_master.py
"""
음성 채널 자동 생성 및 관리(Voice Master) 기능을 담당하는 Cog입니다.
"""
import discord
from discord.ext import commands
import logging
from typing import Dict, Optional

from utils.database import get_id

logger = logging.getLogger(__name__)

class VoiceMaster(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.creator_channel_id: Optional[int] = None
        # key: 생성된 임시 채널 ID, value: 채널 소유자 ID
        self.temp_channels: Dict[int, int] = {} 
        logger.info("VoiceMaster Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        await self.load_configs()

    async def load_configs(self):
        """DB에서 '음성 채널 생성' 트리거 채널의 ID를 불러옵니다."""
        self.creator_channel_id = get_id("voice_creator_channel_id")
        logger.info(f"[VoiceMaster] 생성 채널 ID를 로드했습니다: {self.creator_channel_id}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """멤버의 음성 채널 상태 변경을 감지합니다."""
        if member.bot:
            return

        # --- 채널 생성 로직 ---
        # 설정된 '트리거 채널'에 입장했을 때
        if after.channel and after.channel.id == self.creator_channel_id:
            # 이미 자신만의 임시 채널을 가지고 있는지 확인
            for channel_id, owner_id in self.temp_channels.items():
                if owner_id == member.id:
                    owned_channel = self.bot.get_channel(channel_id)
                    if owned_channel: # 채널이 아직 존재하면
                        await member.move_to(owned_channel, reason="이미 소유한 임시 채널로 이동")
                    return # 이미 채널이 있으므로 새로 만들지 않음
            
            await self._create_temp_channel(member)

        # --- 채널 삭제 로직 ---
        # 멤버가 음성 채널을 나갔을 때
        if before.channel:
            # 나간 채널이 우리가 관리하는 임시 채널인지 확인
            if before.channel.id in self.temp_channels:
                # 채널에 아무도 남아있지 않은지 확인
                if len(before.channel.members) == 0:
                    await self._delete_temp_channel(before.channel)

    async def _create_temp_channel(self, member: discord.Member):
        """사용자 지정 임시 음성 채널을 생성하고 멤버를 이동시킵니다."""
        guild = member.guild
        creator_channel = guild.get_channel(self.creator_channel_id)
        
        # 생성될 채널의 권한 설정
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(connect=True, view_channel=True),
            # 채널을 만든 사람에게는 채널 관리 권한을 부여
            member: discord.PermissionOverwrite(
                connect=True,
                speak=True,
                view_channel=True,
                manage_channels=True, # 이름 변경, 인원 제한 등
                manage_permissions=True, # 채널 권한 수정
                move_members=True, # 다른 멤버 이동
            )
        }

        try:
            # 채널 이름 설정
            channel_name = f"『 {member.display_name}の部屋 』"
            
            # 트리거 채널과 같은 카테고리에 채널 생성
            new_channel = await guild.create_voice_channel(
                name=channel_name,
                category=creator_channel.category,
                overwrites=overwrites,
                reason=f"{member.display_name}의 요청으로 임시 채널 생성"
            )

            # 생성된 채널을 관리 목록에 추가
            self.temp_channels[new_channel.id] = member.id
            logger.info(f"임시 채널 '{new_channel.name}'(ID:{new_channel.id})을(를) 생성했습니다. 소유자: {member.display_name}")

            # 멤버를 새로 만든 채널로 이동
            await member.move_to(new_channel, reason="생성된 임시 채널로 자동 이동")

        except discord.Forbidden:
            logger.error("임시 채널 생성 실패: 봇이 채널을 생성하거나 멤버를 이동할 권한이 없습니다.")
        except Exception as e:
            logger.error(f"임시 채널 생성 중 예기치 않은 오류 발생: {e}", exc_info=True)

    async def _delete_temp_channel(self, channel: discord.VoiceChannel):
        """임시 음성 채널을 삭제하고 관리 목록에서 제거합니다."""
        try:
            await channel.delete(reason="채널에 아무도 없어 자동 삭제")
            
            # 관리 목록에서 제거
            if channel.id in self.temp_channels:
                del self.temp_channels[channel.id]
            logger.info(f"임시 채널 '{channel.name}'(ID:{channel.id})을(를) 자동 삭제했습니다.")
        except discord.NotFound:
            # 이미 삭제된 경우를 대비한 예외 처리
            if channel.id in self.temp_channels:
                del self.temp_channels[channel.id]
        except discord.Forbidden:
            logger.error(f"임시 채널 '{channel.name}' 삭제 실패: 봇에게 채널 삭제 권한이 없습니다.")
        except Exception as e:
            logger.error(f"임시 채널 삭제 중 예기치 않은 오류 발생: {e}", exc_info=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceMaster(bot))
