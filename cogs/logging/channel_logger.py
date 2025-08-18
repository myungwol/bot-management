# cogs/logging/channel_logger.py
import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone, timedelta
import asyncio

from utils.database import get_id

logger = logging.getLogger(__name__)

class ChannelLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_id: int | None = None

    @commands.Cog.listener()
    async def cog_load(self):
        """Cog가 로드될 때 로그 채널 ID를 설정합니다."""
        self.log_channel_id = get_id("log_channel_channel")
        if self.log_channel_id:
            logger.info(f"[ChannelLogger] 채널 관리 로그 채널이 설정되었습니다: #{self.log_channel_id}")
        else:
            logger.warning("[ChannelLogger] 채널 관리 로그 채널이 설정되지 않았습니다.")

    async def get_log_channel(self) -> discord.TextChannel | None:
        if not self.log_channel_id:
            return None
        return self.bot.get_channel(self.log_channel_id)

    async def get_audit_log_user(self, guild: discord.Guild, action: discord.AuditLogAction, target) -> discord.Member | None:
        """감사 로그를 통해 작업을 수행한 사용자를 찾습니다."""
        await asyncio.sleep(2)  # 감사 로그 기록 대기
        try:
            # 경쟁 상태를 피하기 위해 최근 5개의 로그를 확인
            async for entry in guild.audit_logs(action=action, limit=5, after=datetime.now(timezone.utc) - timedelta(seconds=10)):
                if entry.target and entry.target.id == target.id and entry.user and not entry.user.bot:
                    return entry.user
            logger.warning(f"[ChannelLogger] 감사 로그에서 수행자를 찾지 못했습니다. Action: {action}, Target ID: {target.id}")
            return None
        except discord.Forbidden:
            logger.warning(f"[ChannelLogger] 감사 로그 읽기 권한이 없습니다: {guild.name}")
        except Exception as e:
            logger.error(f"[ChannelLogger] {action} 감사 로그 확인 중 오류: {e}", exc_info=True)
        return None

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        log_channel = await self.get_log_channel()
        if not log_channel: return

        user = await self.get_audit_log_user(channel.guild, discord.AuditLogAction.channel_create, channel)
        if not user: return  # 봇이 생성했거나, 감사 로그를 찾지 못한 경우

        embed = discord.Embed(title="채널 생성됨 (チャンネル作成)", color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="채널 (チャンネル)", value=f"{channel.mention} (`{channel.name}`)", inline=False)
        embed.add_field(name="생성한 사람 (作成者)", value=user.mention, inline=False)
        embed.set_footer(text=f"채널 ID: {channel.id}")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        log_channel = await self.get_log_channel()
        if not log_channel: return

        user = await self.get_audit_log_user(channel.guild, discord.AuditLogAction.channel_delete, channel)
        if not user: return

        embed = discord.Embed(title="채널 삭제됨 (チャンネル削除)", color=discord.Color.dark_red(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="채널 이름 (チャンネル名)", value=f"`{channel.name}`", inline=False)
        embed.add_field(name="삭제한 사람 (削除者)", value=user.mention, inline=False)
        embed.set_footer(text=f"채널 ID: {channel.id}")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        log_channel = await self.get_log_channel()
        if not log_channel: return
        
        # 이름, 주제, 권한 등 유의미한 변경이 있을 때만 감사 로그 조회
        if before.name == after.name and before.overwrites == after.overwrites and \
           (not (isinstance(before, discord.TextChannel) and before.topic != after.topic)):
            return

        user = await self.get_audit_log_user(after.guild, discord.AuditLogAction.channel_update, after)
        if not user: return

        embed = discord.Embed(title="채널 업데이트됨 (チャンネル更新)", color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="채널 (チャンネル)", value=after.mention, inline=False)
        
        changes = []
        if before.name != after.name:
            changes.append(f"**이름 (名前):** `{before.name}` → `{after.name}`")
        if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel) and before.topic != after.topic:
             changes.append(f"**주제 (トピック):** 주제가 변경되었습니다.") # 내용은 너무 길 수 있으므로 변경 사실만 알림
        if before.overwrites != after.overwrites:
            changes.append("**권한이 변경되었습니다. (権限が変更されました。)**")

        if changes:
            embed.description = "\n".join(changes)
            embed.add_field(name="수정한 사람 (編集者)", value=user.mention, inline=False)
            embed.set_footer(text=f"채널 ID: {after.id}")
            await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(ChannelLogger(bot))
