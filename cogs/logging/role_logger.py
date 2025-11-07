# cogs/logging/role_logger.py
import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone, timedelta
import asyncio

from utils.database import get_id

logger = logging.getLogger(__name__)

class RoleLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_id: int = None

    async def load_configs(self):
        self.log_channel_id = get_id("log_channel_role")
        if self.log_channel_id:
            logger.info(f"[RoleLogger] 역할 로그 채널이 설정되었습니다: #{self.log_channel_id}")
        else:
            logger.warning("[RoleLogger] 역할 로그 채널이 설정되지 않았습니다.")

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
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.bot or before.roles == after.roles: return
        log_channel = await self.get_log_channel()
        if not log_channel: return
        
        moderator = await self.get_audit_log_user(after.guild, discord.AuditLogAction.member_role_update, after)
        if not moderator: return

        before_roles, after_roles = set(before.roles), set(after.roles)
        added_roles = after_roles - before_roles
        removed_roles = before_roles - after_roles
        
        if added_roles:
            embed = discord.Embed(title="➕ 역할 부여됨", color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
            embed.add_field(name="유저", value=f"{after.mention} (`{after.id}`)", inline=False)
            embed.add_field(name="부여된 역할", value=", ".join([r.mention for r in added_roles]), inline=False)
            embed.add_field(name="실행자", value=f"{moderator.mention} (`{moderator.id}`)", inline=False)
            await log_channel.send(embed=embed)
            
        if removed_roles:
            embed = discord.Embed(title="➖ 역할 제거됨", color=discord.Color.dark_red(), timestamp=datetime.now(timezone.utc))
            embed.add_field(name="유저", value=f"{after.mention} (`{after.id}`)", inline=False)
            embed.add_field(name="제거된 역할", value=", ".join([r.mention for r in removed_roles]), inline=False)
            embed.add_field(name="실행자", value=f"{moderator.mention} (`{moderator.id}`)", inline=False)
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        log_channel = await self.get_log_channel()
        if not log_channel: return
        user = await self.get_audit_log_user(role.guild, discord.AuditLogAction.role_create, role)
        if not user or user.bot: return
        embed = discord.Embed(title="✅ 역할 생성됨", color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="역할", value=f"{role.mention} (`{role.name}`)", inline=False)
        embed.add_field(name="생성자", value=f"{user.mention} (`{user.id}`)", inline=False)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        log_channel = await self.get_log_channel()
        if not log_channel: return
        user = await self.get_audit_log_user(role.guild, discord.AuditLogAction.role_delete, role)
        if not user or user.bot: return
        embed = discord.Embed(title="🗑️ 역할 삭제됨", color=0x992d22, timestamp=datetime.now(timezone.utc))
        embed.add_field(name="역할 이름", value=f"`{role.name}`", inline=False)
        embed.add_field(name="삭제한 사람", value=f"{user.mention} (`{user.id}`)", inline=False)
        await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(RoleLogger(bot))
