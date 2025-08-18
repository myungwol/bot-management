# cogs/logging/guild_logger.py
import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone
import asyncio

from utils.database import get_id

logger = logging.getLogger(__name__)

class GuildLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.channel_log_id: int = None
        self.role_log_id: int = None
        self.server_log_id: int = None

    @commands.Cog.listener()
    async def on_ready(self):
        await self.load_configs()

    async def load_configs(self):
        self.channel_log_id = get_id("log_channel_channel")
        self.role_log_id = get_id("log_channel_role")
        self.server_log_id = get_id("log_channel_server")
        logger.info("[GuildLogger] 길드 관련 로그 채널 설정을 로드했습니다.")

    async def get_log_channel(self, log_type: str) -> discord.TextChannel | None:
        log_id = getattr(self, f"{log_type}_log_id", None)
        if not log_id: return None
        channel = self.bot.get_channel(log_id)
        if isinstance(channel, discord.TextChannel): return channel
        return None

    async def get_audit_log_user(self, guild: discord.Guild, action: discord.AuditLogAction, target_id: int):
        await asyncio.sleep(1.5) # 감사 로그 기록 대기
        try:
            if guild.me.guild_permissions.view_audit_log:
                async for entry in guild.audit_logs(action=action, limit=1):
                    if entry.target.id == target_id and not entry.user.bot:
                        return entry.user
        except Exception as e:
            logger.error(f"감사 로그 확인 중 오류: {e}")
        return None

    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        log_ch = await self.get_log_channel("channel")
        if not log_ch: return
        user = await self.get_audit_log_user(channel.guild, discord.AuditLogAction.channel_create, channel.id)
        if not user: return
        embed = discord.Embed(title="チャンネル作成", color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="チャンネル", value=f"{channel.mention} (`{channel.name}`)", inline=False)
        embed.add_field(name="作成者", value=user.mention, inline=False)
        await log_ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        log_ch = await self.get_log_channel("channel")
        if not log_ch: return
        user = await self.get_audit_log_user(channel.guild, discord.AuditLogAction.channel_delete, channel.id)
        if not user: return
        embed = discord.Embed(title="チャンネル削除", color=discord.Color.dark_red(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="チャンネル名", value=f"`{channel.name}`", inline=False)
        embed.add_field(name="削除者", value=user.mention, inline=False)
        await log_ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        log_ch = await self.get_log_channel("channel")
        if not log_ch: return
        user = await self.get_audit_log_user(after.guild, discord.AuditLogAction.channel_update, after.id)
        if not user: return
        embed = discord.Embed(title="チャンネル更新", color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
        embed.set_author(name=f"チャンネル: #{after.name} ({after.id})")
        changes = []
        if before.name != after.name: changes.append(f"**名前:** `{before.name}` → `{after.name}`")
        if before.overwrites != after.overwrites: changes.append("**権限が変更されました。**")
        if changes:
            embed.description = "\n".join(changes)
            embed.add_field(name="編集者", value=user.mention, inline=False)
            embed.add_field(name="チャンネル", value=after.mention, inline=False)
            await log_ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        log_ch = await self.get_log_channel("role")
        if not log_ch: return
        user = await self.get_audit_log_user(role.guild, discord.AuditLogAction.role_create, role.id)
        if not user: return
        embed = discord.Embed(title="役職作成", color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="役職", value=f"{role.mention} (`{role.name}`)", inline=False)
        embed.add_field(name="作成者", value=user.mention, inline=False)
        await log_ch.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: disco
