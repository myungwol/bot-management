# cogs/logging/kick_logger.py

import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone, timedelta
import asyncio

from utils.database import get_id

logger = logging.getLogger(__name__)

class KickLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_id: int = None

    async def load_configs(self):
        self.log_channel_id = get_id("log_channel_kick")
        if self.log_channel_id:
            logger.info(f"[KickLogger] 추방 로그 채널이 설정되었습니다: #{self.log_channel_id}")
        else:
            logger.warning("[KickLogger] 추방 로그 채널이 설정되지 않았습니다.")

    async def get_log_channel(self) -> discord.TextChannel | None:
        if not self.log_channel_id: return None
        return self.bot.get_channel(self.log_channel_id)

    # ▼▼▼ [수정] on_member_remove 리스너 전체를 아래 코드로 교체 ▼▼▼
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        log_channel = await self.get_log_channel()
        if not log_channel: return
        
        await asyncio.sleep(1.5) # 감사 로그가 기록될 시간을 줍니다.
        try:
            async for entry in member.guild.audit_logs(action=discord.AuditLogAction.kick, limit=5, after=datetime.now(timezone.utc) - timedelta(seconds=5)):
                # 감사 로그의 대상이 일치하고, 실행자가 봇이 아닌 경우에만 기록
                if entry.target and entry.target.id == member.id and not entry.user.bot:
                    # 임시 캐시에 유저 ID를 추가하여 leave_logger가 중복 기록하는 것을 방지
                    self.bot.recently_moderated_users.add(member.id)
                    
                    embed = discord.Embed(
                        title="👢 멤버 추방됨",
                        description=f"{member.mention} 님이 서버에서 추방되었습니다.",
                        color=0xFFA500, # Orange
                        timestamp=entry.created_at
                    )
                    embed.set_author(name=f"{member.name} ({member.id})", icon_url=member.display_avatar.url if member.display_avatar else None)
                    embed.add_field(name="실행자", value=f"{entry.user.mention} (`{entry.user.id}`)", inline=False)
                    if entry.reason:
                        embed.add_field(name="사유", value=entry.reason, inline=False)
                    await log_channel.send(embed=embed)
                    
                    # 10초 후에 캐시에서 ID를 자동으로 제거
                    async def remove_from_cache():
                        await asyncio.sleep(10)
                        self.bot.recently_moderated_users.discard(member.id)
                    asyncio.create_task(remove_from_cache())
                    
                    return # 로그를 기록했으므로 함수 종료
        except discord.Forbidden:
            logger.warning(f"감사 로그 읽기 권한이 없습니다: {member.guild.name}")
        except Exception as e:
            logger.error(f"'kick' 감사 로그 확인 중 오류: {e}", exc_info=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(KickLogger(bot))
