# cogs/logging/leave_logger.py

import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone
import asyncio

from utils.database import get_id

logger = logging.getLogger(__name__)

class LeaveLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_id: int = None

    async def load_configs(self):
        self.log_channel_id = get_id("log_channel_leave")
        if self.log_channel_id:
            logger.info(f"[LeaveLogger] 퇴장 로그 채널이 설정되었습니다: #{self.log_channel_id}")
        else:
            logger.warning("[LeaveLogger] 퇴장 로그 채널이 설정되지 않았습니다.")

    async def get_log_channel(self) -> discord.TextChannel | None:
        if not self.log_channel_id: return None
        return self.bot.get_channel(self.log_channel_id)

    # ▼▼▼ [수정] on_member_remove 리스너 전체를 아래 코드로 교체 ▼▼▼
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.bot: return
        
        # 다른 로거가 처리할 시간을 주기 위해 잠시 대기
        await asyncio.sleep(2)

        # 만약 멤버가 최근에 추방/차단되었다면, 로그를 남기지 않고 종료
        if hasattr(self.bot, 'recently_moderated_users') and member.id in self.bot.recently_moderated_users:
            return

        log_channel = await self.get_log_channel()
        if not log_channel: return

        embed = discord.Embed(
            title="📤 멤버 퇴장",
            description=f"{member.mention} 님이 서버에서 나갔습니다.",
            color=discord.Color.dark_grey(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=f"{member.name} ({member.id})", icon_url=member.display_avatar.url if member.display_avatar else None)
        await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(LeaveLogger(bot))
