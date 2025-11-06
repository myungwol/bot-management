# cogs/logging/voice_logger.py
import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone

from utils.database import get_id

logger = logging.getLogger(__name__)

class VoiceLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_id: int = None

    async def load_configs(self):
        """main.py의 on_ready 루프에 의해 호출됩니다."""
        self.log_channel_id = get_id("log_channel_voice")
        if self.log_channel_id:
            logger.info(f"[VoiceLogger] 음성 로그 채널이 설정되었습니다: #{self.log_channel_id}")
        else:
            logger.warning("[VoiceLogger] 음성 로그 채널이 설정되지 않았습니다.")

    async def get_log_channel(self) -> discord.TextChannel | None:
        if not self.log_channel_id: return None
        channel = self.bot.get_channel(self.log_channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot or not self.log_channel_id or before.channel == after.channel:
            return
        log_channel = await self.get_log_channel()
        if not log_channel: return

        embed = None
        if before.channel is None and after.channel is not None:
            embed = discord.Embed(
                title="음성 채널 참여",
                description=f"{member.mention} 님이 **`{after.channel.name}`** 채널에 참여했습니다.",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_author(name=f"{member.display_name} ({member.id})", icon_url=member.display_avatar.url if member.display_avatar else None)
        elif before.channel is not None and after.channel is None:
            embed = discord.Embed(
                title="음성 채널 퇴장",
                description=f"{member.mention} 님이 **`{before.channel.name}`** 채널에서 나갔습니다.",
                color=discord.Color.dark_grey(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_author(name=f"{member.display_name} ({member.id})", icon_url=member.display_avatar.url if member.display_avatar else None)
        elif before.channel is not None and after.channel is not None:
            embed = discord.Embed(
                title="음성 채널 이동",
                description=f"{member.mention} 님이 채널을 이동했습니다.",
                color=discord.Color.blue(),
                timestamp=datetime.now(timezone.utc)
            )
            embed.add_field(name="기존 채널", value=f"`{before.channel.name}`", inline=False)
            embed.add_field(name="새로운 채널", value=f"`{after.channel.name}`", inline=False)
            embed.set_author(name=f"{member.display_name} ({member.id})", icon_url=member.display_avatar.url if member.display_avatar else None)
        
        if embed:
            await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceLogger(bot))
