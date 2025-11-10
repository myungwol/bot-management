# cogs/logging/invite_logger.py
import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone

from utils.database import get_id

logger = logging.getLogger(__name__)

class InviteLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_id: int = None

    async def load_configs(self):
        self.log_channel_id = get_id("log_channel_invite")
        if self.log_channel_id:
            logger.info(f"[InviteLogger] 초대 추적 로그 채널이 설정되었습니다: #{self.log_channel_id}")
        else:
            logger.warning("[InviteLogger] 초대 추적 로그 채널이 설정되지 않았습니다.")

    async def get_log_channel(self) -> discord.TextChannel | None:
        if not self.log_channel_id: return None
        return self.bot.get_channel(self.log_channel_id)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot: return
        log_channel = await self.get_log_channel()
        if not log_channel: return

        tracker_cog = self.bot.get_cog("InviteTracker")
        if tracker_cog:
            invite = await tracker_cog.get_invite_for_member(member)
            if invite and invite.inviter:
                embed = discord.Embed(
                    title="📨 초대 링크를 통해 참여",
                    description=f"{member.mention} 님이 초대를 통해 서버에 참여했습니다.",
                    color=discord.Color.teal(),
                    timestamp=datetime.now(timezone.utc)
                )
                embed.set_author(name=f"{member.name} ({member.id})", icon_url=member.display_avatar.url if member.display_avatar else None)
                embed.add_field(name="🔗 사용된 코드", value=f"`{invite.code}`", inline=True)
                embed.add_field(name="💌 초대자", value=f"{invite.inviter.mention} (`{invite.inviter.id}`)", inline=True)
                
                await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(InviteLogger(bot))
