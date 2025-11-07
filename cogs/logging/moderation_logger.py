# cogs/logging/moderation_logger.py
import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone, timedelta
import asyncio

from utils.database import get_id

logger = logging.getLogger(__name__)

class ModerationLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_id: int = None

    async def load_configs(self):
        self.log_channel_id = get_id("log_channel_moderation")
        if self.log_channel_id:
            logger.info(f"[ModerationLogger] 관리 활동 로그 채널이 설정되었습니다: #{self.log_channel_id}")
        else:
            logger.warning("[ModerationLogger] 관리 활동 로그 채널이 설정되지 않았습니다.")

    async def get_log_channel(self) -> discord.TextChannel | None:
        if not self.log_channel_id: return None
        return self.bot.get_channel(self.log_channel_id)

    async def get_audit_log_entry(self, guild: discord.Guild, target_id: int, action: discord.AuditLogAction):
        await asyncio.sleep(1.5)
        try:
            async for entry in guild.audit_logs(action=action, limit=5, after=datetime.now(timezone.utc) - timedelta(seconds=5)):
                if entry.target and entry.target.id == target_id and not entry.user.bot:
                    return entry
        except discord.Forbidden:
            logger.warning(f"감사 로그 읽기 권한이 없습니다: {guild.name}")
        except Exception as e:
            logger.error(f"'{action}' 감사 로그 확인 중 오류: {e}", exc_info=True)
        return None

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        log_channel = await self.get_log_channel()
        if not log_channel: return
        
        entry = await self.get_audit_log_entry(member.guild, member.id, discord.AuditLogAction.kick)
        if not entry: return

        embed = discord.Embed(
            title="👢 멤버 추방됨",
            description=f"{member.mention} 님이 서버에서 추방되었습니다.",
            color=0xFFA500, # Orange
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=f"{member.name} ({member.id})", icon_url=member.display_avatar.url if member.display_avatar else None)
        embed.add_field(name="실행자", value=f"{entry.user.mention} (`{entry.user.id}`)", inline=False)
        if entry.reason:
            embed.add_field(name="사유", value=entry.reason, inline=False)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User | discord.Member):
        log_channel = await self.get_log_channel()
        if not log_channel: return
        
        entry = await self.get_audit_log_entry(guild, user.id, discord.AuditLogAction.ban)
        if not entry: return

        embed = discord.Embed(
            title="🚫 멤버 차단됨",
            description=f"{user.mention} 님이 서버에서 차단되었습니다.",
            color=0xFF0000, # Red
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_author(name=f"{user.name} ({user.id})", icon_url=user.display_avatar.url if user.display_avatar else None)
        embed.add_field(name="실행자", value=f"{entry.user.mention} (`{entry.user.id}`)", inline=False)
        if entry.reason:
            embed.add_field(name="사유", value=entry.reason, inline=False)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.timed_out_until == after.timed_out_until: return
        log_channel = await self.get_log_channel()
        if not log_channel: return

        entry = await self.get_audit_log_entry(after.guild, after.id, discord.AuditLogAction.member_update)
        if not entry: return

        # 타임아웃이 적용되었을 때
        if after.timed_out_until is not None:
            embed = discord.Embed(
                title="⏳ 멤버 타임아웃",
                description=f"{after.mention} 님에게 타임아웃이 적용되었습니다.",
                color=0xFFFF00, # Yellow
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_author(name=f"{after.name} ({after.id})", icon_url=after.display_avatar.url if after.display_avatar else None)
            embed.add_field(name="실행자", value=f"{entry.user.mention} (`{entry.user.id}`)", inline=False)
            embed.add_field(name="종료 시각", value=discord.utils.format_dt(after.timed_out_until, style='F'), inline=False)
            if entry.reason:
                embed.add_field(name="사유", value=entry.reason, inline=False)
            await log_channel.send(embed=embed)
        # 타임아웃이 해제되었을 때
        else:
            embed = discord.Embed(
                title="✅ 타임아웃 해제",
                description=f"{after.mention} 님의 타임아웃이 해제되었습니다.",
                color=0x00FF00, # Green
                timestamp=datetime.now(timezone.utc)
            )
            embed.set_author(name=f"{after.name} ({after.id})", icon_url=after.display_avatar.url if after.display_avatar else None)
            embed.add_field(name="실행자", value=f"{entry.user.mention} (`{entry.user.id}`)", inline=False)
            await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(ModerationLogger(bot))
