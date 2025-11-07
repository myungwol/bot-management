# cogs/logging/server_logger.py

import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone, timedelta
import asyncio

from utils.database import get_id

logger = logging.getLogger(__name__)

class ServerLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_id: int = None

    async def load_configs(self):
        """main.py의 on_ready 루프에 의해 호출됩니다."""
        self.log_channel_id = get_id("log_channel_server")
        if self.log_channel_id:
            logger.info(f"[ServerLogger] 서버 설정 로그 채널이 설정되었습니다: #{self.log_channel_id}")
        else:
            logger.warning("[ServerLogger] 서버 설정 로그 채널이 설정되지 않았습니다.")

    async def get_log_channel(self) -> discord.TextChannel | None:
        if not self.log_channel_id: return None
        return self.bot.get_channel(self.log_channel_id)
        
    async def get_audit_log_user(self, guild: discord.Guild, action: discord.AuditLogAction, target) -> discord.Member | None:
        await asyncio.sleep(1.5)
        try:
            async for entry in guild.audit_logs(action=action, limit=5, after=datetime.now(timezone.utc) - timedelta(seconds=5)):
                if entry.target and entry.target.id == target.id and not entry.user.bot:
                    return entry.user
        except discord.Forbidden:
            logger.warning(f"감사 로그 읽기 권한이 없습니다: {guild.name}")
        except Exception as e:
            logger.error(f"'{action}' 감사 로그 확인 중 오류: {e}", exc_info=True)
        return None

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        log_channel = await self.get_log_channel()
        if not log_channel: return
        
        user = await self.get_audit_log_user(after, discord.AuditLogAction.guild_update, after)
        if not user or user.bot: return

        embed = discord.Embed(title="⚙️ 서버 설정 변경됨", color=discord.Color.purple(), timestamp=datetime.now(timezone.utc))
        changes = []
        if before.name != after.name:
            changes.append(f"**서버 이름:** `{before.name}` → `{after.name}`")
        if before.afk_channel != after.afk_channel:
            before_afk = before.afk_channel.mention if before.afk_channel else '없음'
            after_afk = after.afk_channel.mention if after.afk_channel else '없음'
            changes.append(f"**잠수 채널:** {before_afk} → {after_afk}")
        if before.afk_timeout != after.afk_timeout:
             changes.append(f"**잠수 시간:** `{before.afk_timeout/60}`분 → `{after.afk_timeout/60}`분")
        if before.system_channel != after.system_channel:
            before_sys = before.system_channel.mention if before.system_channel else '없음'
            after_sys = after.system_channel.mention if after.system_channel else '없음'
            changes.append(f"**시스템 메시지 채널:** {before_sys} → {after_sys}")

        if changes:
            embed.description = "\n".join(changes)
            embed.add_field(name="수정한 사람", value=f"{user.mention} (`{user.id}`)", inline=False)
            await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerLogger(bot))
