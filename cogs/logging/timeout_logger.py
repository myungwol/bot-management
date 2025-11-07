# cogs/logging/timeout_logger.py

import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone, timedelta
import asyncio

from utils.database import get_id

logger = logging.getLogger(__name__)

class TimeoutLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_id: int = None

    async def load_configs(self):
        self.log_channel_id = get_id("log_channel_timeout")
        if self.log_channel_id:
            logger.info(f"[TimeoutLogger] 타임아웃 로그 채널이 설정되었습니다: #{self.log_channel_id}")
        else:
            logger.warning("[TimeoutLogger] 타임아웃 로그 채널이 설정되지 않았습니다.")

    async def get_log_channel(self) -> discord.TextChannel | None:
        if not self.log_channel_id: return None
        return self.bot.get_channel(self.log_channel_id)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # 타임아웃 상태가 실제로 변경되었는지 먼저 확인
        if before.timed_out_until == after.timed_out_until:
            return
            
        log_channel = await self.get_log_channel()
        if not log_channel: return

        # 감사 로그가 기록될 시간을 줌
        await asyncio.sleep(1.5)
        entry = None
        try:
            # 멤버 업데이트 감사 로그를 확인
            async for audit_entry in after.guild.audit_logs(action=discord.AuditLogAction.member_update, limit=5, after=datetime.now(timezone.utc) - timedelta(seconds=5)):
                # 감사 로그의 대상이 일치하고, 실행자가 봇이 아닌지 확인
                if audit_entry.target and audit_entry.target.id == after.id and not audit_entry.user.bot:
                    # [핵심 수정] 변경된 속성 중에 'timed_out_until'이 있는지 정확하게 확인
                    if hasattr(audit_entry.changes.before, 'timed_out_until') and hasattr(audit_entry.changes.after, 'timed_out_until'):
                        entry = audit_entry
                        break # 정확한 로그를 찾았으므로 반복 중단
        except discord.Forbidden:
            logger.warning(f"감사 로그 읽기 권한이 없습니다: {after.guild.name}")
        except Exception as e:
            logger.error(f"'member_update' 감사 로그 확인 중 오류: {e}", exc_info=True)

        # 올바른 감사 로그를 찾지 못했으면 함수 종료
        if not entry:
            return

        # 타임아웃이 새로 적용되었을 때
        if after.timed_out_until is not None:
            embed = discord.Embed(
                title="⏳ 멤버 타임아웃 적용",
                description=f"{after.mention} 님에게 타임아웃이 적용되었습니다.",
                color=discord.Color.yellow(),
                timestamp=entry.created_at
            )
            embed.add_field(name="종료 시각", value=discord.utils.format_dt(after.timed_out_until, style='F'), inline=False)
            if entry.reason:
                embed.add_field(name="사유", value=entry.reason, inline=False)
        # 타임아웃이 해제되었을 때
        else:
            embed = discord.Embed(
                title="✅ 타임아웃 해제",
                description=f"{after.mention} 님의 타임아웃이 해제되었습니다.",
                color=discord.Color.green(),
                timestamp=entry.created_at
            )
        
        embed.set_author(name=f"{after.name} ({after.id})", icon_url=after.display_avatar.url if after.display_avatar else None)
        embed.add_field(name="실행자", value=f"{entry.user.mention} (`{entry.user.id}`)", inline=False)
        await log_channel.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(TimeoutLogger(bot))
