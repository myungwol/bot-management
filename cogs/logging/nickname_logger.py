# cogs/logging/nickname_logger.py
import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone, timedelta
import asyncio

from utils.database import get_id

logger = logging.getLogger(__name__)

class NicknameLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_id: int = None

    async def load_configs(self):
        self.log_channel_id = get_id("log_channel_nickname")
        if self.log_channel_id:
            logger.info(f"[NicknameLogger] 별명 로그 채널이 설정되었습니다: #{self.log_channel_id}")
        else:
            logger.warning("[NicknameLogger] 별명 로그 채널이 설정되지 않았습니다.")

    async def get_log_channel(self) -> discord.TextChannel | None:
        if not self.log_channel_id: return None
        return self.bot.get_channel(self.log_channel_id)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.bot or before.nick == after.nick: return
        log_channel = await self.get_log_channel()
        if not log_channel: return
        
        await asyncio.sleep(1.5)
        moderator = None
        try:
            async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_update, after=datetime.now(timezone.utc) - timedelta(seconds=5)):
                if entry.target.id == after.id and not entry.user.bot and hasattr(entry.before, 'nick') and hasattr(entry.after, 'nick'):
                    moderator = entry.user
                    break
        except discord.Forbidden:
            logger.warning(f"[{after.guild.name}] 멤버 닉네임 업데이트 감사 로그 읽기 권한이 없습니다.")
        except Exception as e:
            logger.error(f"멤버 닉네임 업데이트 감사 로그 확인 중 오류: {e}", exc_info=True)

        # 봇 자신이 변경한 경우는 로그를 남기지 않음
        if moderator and moderator.id == self.bot.user.id:
            return

        performer_mention = "본인"
        if moderator and moderator.id != after.id:
            performer_mention = f"{moderator.mention} (`{moderator.id}`)"
            
        embed = discord.Embed(title="✒️ 별명 변경됨", color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="유저", value=f"{after.mention} (`{after.id}`)", inline=False)
        embed.add_field(name="변경 전", value=f"`{before.nick or before.name}`", inline=True)
        embed.add_field(name="변경 후", value=f"`{after.nick or after.name}`", inline=True)
        embed.add_field(name="실행자", value=performer_mention, inline=False)
        await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(NicknameLogger(bot))
