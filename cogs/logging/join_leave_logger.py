# cogs/logging/join_leave_logger.py
import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone

from utils.database import get_id

logger = logging.getLogger(__name__)

class JoinLeaveLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_id: int = None

    async def load_configs(self):
        self.log_channel_id = get_id("log_channel_join_leave")
        if self.log_channel_id:
            logger.info(f"[JoinLeaveLogger] 입장/퇴장 로그 채널이 설정되었습니다: #{self.log_channel_id}")
        else:
            logger.warning("[JoinLeaveLogger] 입장/퇴장 로그 채널이 설정되지 않았습니다.")

    async def get_log_channel(self) -> discord.TextChannel | None:
        if not self.log_channel_id: return None
        return self.bot.get_channel(self.log_channel_id)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot: return
        log_channel = await self.get_log_channel()
        if not log_channel: return

        embed = discord.Embed(
            title="📥 멤버 입장",
            description=f"{member.mention} 님이 서버에 참여했습니다.",
            color=discord.Color.green(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=f"{member.name} ({member.id})", icon_url=member.display_avatar.url if member.display_avatar else None)
        embed.add_field(name="계정 생성일", value=discord.utils.format_dt(member.created_at, style='F'))
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.bot: return
        # 추방/차단 로그는 moderation_logger에서 처리하므로, 여기서는 자발적인 퇴장만 기록
        # 간단한 확인을 위해 감사 로그를 잠시 훑어봅니다.
        try:
            async for entry in member.guild.audit_logs(limit=1, actions=[discord.AuditLogAction.kick, discord.AuditLogAction.ban]):
                if entry.target.id == member.id:
                    # 최근 5초 이내에 발생한 관리 기록이 있으면 퇴장 로그를 남기지 않음
                    if (datetime.now(timezone.utc) - entry.created_at).total_seconds() < 5:
                        return
        except discord.Forbidden:
            pass # 권한이 없으면 일단 진행

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
    await bot.add_cog(JoinLeaveLogger(bot))
