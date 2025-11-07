# cogs/logging/ban_logger.py
import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone, timedelta
import asyncio

from utils.database import get_id

logger = logging.getLogger(__name__)

class BanLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_id: int = None

    async def load_configs(self):
        self.log_channel_id = get_id("log_channel_ban")
        if self.log_channel_id:
            logger.info(f"[BanLogger] 차단 로그 채널이 설정되었습니다: #{self.log_channel_id}")
        else:
            logger.warning("[BanLogger] 차단 로그 채널이 설정되지 않았습니다.")

    async def get_log_channel(self) -> discord.TextChannel | None:
        if not self.log_channel_id: return None
        return self.bot.get_channel(self.log_channel_id)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User | discord.Member):
        log_channel = await self.get_log_channel()
        if not log_channel: return
        
        await asyncio.sleep(1.5)
        try:
            async for entry in guild.audit_logs(action=discord.AuditLogAction.ban, limit=5, after=datetime.now(timezone.utc) - timedelta(seconds=5)):
                if entry.target and entry.target.id == user.id and not entry.user.bot:
                    embed = discord.Embed(
                        title="🚫 멤버 차단됨",
                        description=f"{user.mention} 님이 서버에서 차단되었습니다.",
                        color=discord.Color.brand_red(),
                        timestamp=entry.created_at
                    )
                    embed.set_author(name=f"{user.name} ({user.id})", icon_url=user.display_avatar.url if user.display_avatar else None)
                    embed.add_field(name="실행자", value=f"{entry.user.mention} (`{entry.user.id}`)", inline=False)
                    if entry.reason:
                        embed.add_field(name="사유", value=entry.reason, inline=False)
                    await log_channel.send(embed=embed)
                    return
        except discord.Forbidden:
            logger.warning(f"감사 로그 읽기 권한이 없습니다: {guild.name}")
        except Exception as e:
            logger.error(f"'ban' 감사 로그 확인 중 오류: {e}", exc_info=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(BanLogger(bot))
