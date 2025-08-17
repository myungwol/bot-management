# cogs/server/member_events.py
"""
서버 멤버의 입장 및 퇴장 이벤트를 처리하는 Cog입니다.
- 새로운 멤버가 서버에 참여하면 환영 메시지를 보내고 초기 역할을 부여합니다.
- 멤버가 서버에서 나가면 작별 메시지를 보냅니다.
"""
import discord
from discord.ext import commands
import logging
from typing import Optional

from utils.helpers import format_embed_from_db
from utils.database import get_id, get_embed_from_db

logger = logging.getLogger(__name__)

class MemberEvents(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.welcome_channel_id: Optional[int] = None
        self.farewell_channel_id: Optional[int] = None
        self.guest_role_id: Optional[int] = None
        logger.info("MemberEvents (입장/퇴장) Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        """Cog가 로드될 때 DB에서 설정을 불러옵니다."""
        await self.load_configs()

    async def load_configs(self):
        """데이터베이스에서 채널 및 역할 ID 설정을 불러와 Cog의 상태를 업데이트합니다."""
        self.welcome_channel_id = get_id("new_welcome_channel_id")
        self.farewell_channel_id = get_id("farewell_channel_id")
        self.guest_role_id = get_id("role_guest")
        logger.info("[MemberEvents Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """멤버가 서버에 참여했을 때 호출되는 이벤트 리스너입니다."""
        if member.bot:
            return

        # 1. 초기 '손님' 역할 부여
        if self.guest_role_id:
            guest_role = member.guild.get_role(self.guest_role_id)
            if guest_role:
                try:
                    await member.add_roles(guest_role, reason="서버 참여 시 초기 역할 부여")
                except discord.Forbidden:
                    logger.error(f"'{member.display_name}'님에게 '손님' 역할을 부여하지 못했습니다. 봇의 역할이 '손님' 역할보다 낮거나 권한이 부족합니다.")
                except Exception as e:
                    logger.error(f"'{self.guest_role_id}' 역할 부여 중 예기치 않은 오류 발생: {e}", exc_info=True)
            else:
                logger.warning(f"DB에 설정된 '손님' 역할 ID({self.guest_role_id})를 서버에서 찾을 수 없습니다.")

        # 2. 환영 메시지 전송
        if not self.welcome_channel_id:
            return

        try:
            channel = await self.bot.fetch_channel(self.welcome_channel_id)
            embed_data = await get_embed_from_db('welcome_embed')
            
            if embed_data:
                embed = format_embed_from_db(
                    embed_data,
                    member_mention=member.mention,
                    member_name=member.display_name, # 예전 시스템 호환용
                    guild_name=member.guild.name
                )
                if member.display_avatar:
                    embed.set_thumbnail(url=member.display_avatar.url)
                
                await channel.send(
                    f"ようこそ、{member.mention}さん！",
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions(users=True)
                )
        except discord.NotFound:
            logger.error(f"환영 메시지 전송 실패: 설정된 채널 ID({self.welcome_channel_id})를 찾을 수 없습니다.")
        except discord.Forbidden:
            logger.error(f"환영 메시지 전송 실패: 채널({self.welcome_channel_id})에 메시지를 보낼 권한이 없습니다.")
        except Exception as e:
            logger.error(f"환영 메시지 전송 중 예기치 않은 오류 발생: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """멤버가 서버를 떠났을 때 호출되는 이벤트 리스너입니다."""
        if member.bot:
            return
            
        if not self.farewell_channel_id:
            return

        try:
            # 신뢰성 있는 fetch_channel 사용
            channel = await self.bot.fetch_channel(self.farewell_channel_id)
            embed_data = await get_embed_from_db('farewell_embed')

            if embed_data:
                # [수정] member.display_name (닉네임)과 member.name (고유 아이디)을 모두 전달
                embed = format_embed_from_db(
                    embed_data,
                    member_display_name=member.display_name,
                    member_username=member.name
                )
                if member.display_avatar:
                    embed.set_thumbnail(url=member.display_avatar.url)
                
                await channel.send(embed=embed)
        except discord.NotFound:
            logger.error(f"퇴장 메시지 전송 실패: 설정된 채널 ID({self.farewell_channel_id})를 찾을 수 없습니다.")
        except discord.Forbidden:
            logger.error(f"퇴장 메시지 전송 실패: 채널({self.farewell_channel_id})을 보거나 메시지를 보낼 권한이 없습니다.")
        except Exception as e:
            logger.error(f"퇴장 메시지 전송 중 예기치 않은 오류 발생: {e}", exc_info=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(MemberEvents(bot))
