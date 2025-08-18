# cogs/logging/channel_logger.py
import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone
import asyncio

from utils.database import get_id

logger = logging.getLogger(__name__)

class ChannelLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_id: int = None

    @commands.Cog.listener()
    async def on_ready(self):
        self.log_channel_id = get_id("log_channel_channel")
        if self.log_channel_id:
            logger.info(f"[ChannelLogger] 채널 관리 로그 채널이 설정되었습니다: #{self.log_channel_id}")

    async def get_log_channel(self) -> discord.TextChannel | None:
        if not self.log_channel_id: return None
        return self.bot.get_channel(self.log_channel_id)
        
    async def get_audit_log_user(self, guild: discord.Guild, action: discord.AuditLogAction, target_id: int):
        await asyncio.sleep(1.5) # 감사 로그가 기록될 시간을 기다림
        try:
            async for entry in guild.audit_logs(action=action, limit=1):
                if entry.target.id == target_id and not entry.user.bot:
                    return entry.user
        except discord.Forbidden: return "권한 부족"
        except Exception: return "알 수 없음"
        return "알 수 없음"

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        log_channel = await self.get_log_channel()
        if not log_channel: return
        user = await self.get_audit_log_user(channel.guild, discord.AuditLogAction.channel_create, channel.id)
        if not isinstance(user, discord.Member): return

        embed = discord.Embed(title="채널 생성됨 (チャンネル作成)", color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="채널 (チャンネル)", value=f"{channel.mention} (`{channel.name}`)", inline=False)
        embed.add_field(name="생성한 사람 (作成者)", value=user.mention, inline=False)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        log_channel = await self.get_log_channel()
        if not log_channel: return
        user = await self.get_audit_log_user(channel.guild, discord.AuditLogAction.channel_delete, channel.id)
        if not isinstance(user, discord.Member): return
        
        embed = discord.Embed(title="채널 삭제됨 (チャンネル削除)", color=discord.Color.dark_red(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="채널 이름 (チャンネル名)", value=f"`{channel.name}`", inline=False)
        embed.add_field(name="삭제한 사람 (削除者)", value=user.mention, inline=False)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        log_channel = await self.get_log_channel()
        if not log_channel: return
        user = await self.get_audit_log_user(after.guild, discord.AuditLogAction.channel_update, after.id)
        if not isinstance(user, discord.Member): return

        embed = discord.Embed(title="채널 업데이트됨 (チャンネル更新)", color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
        embed.set_author(name=f"채널: #{after.name} ({after.id})")
        
        changes = []
        if before.name != after.name:
            changes.append(f"**이름 (名前):** `{before.name}` → `{after.name}`")
        if before.overwrites != after.overwrites:
            changes.append("**권한이 변경되었습니다. (権限が変更されました。)**")
        
        if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel):
            if before.topic != after.topic: changes.append(f"**주제 (トピック):** 주제가 변경되었습니다.")

        if changes:
            embed.description = "\n".join(changes)
            embed.add_field(name="수정한 사람 (編集者)", value=user.mention, inline=False)
            embed.add_field(name="채널 (チャンネル)", value=after.mention, inline=False)
            await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(ChannelLogger(bot))
