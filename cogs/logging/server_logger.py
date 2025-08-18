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
        self.log_channel_id: int | None = None

    @commands.Cog.listener()
    async def cog_load(self):
        """Cog가 로드될 때 로그 채널 ID를 설정합니다."""
        self.log_channel_id = get_id("log_channel_server")
        if self.log_channel_id:
            logger.info(f"[ServerLogger] 서버/역할 로그 채널이 설정되었습니다: #{self.log_channel_id}")
        else:
            logger.warning("[ServerLogger] 서버/역할 로그 채널이 설정되지 않았습니다.")


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
            logger.warning(f"[ServerLogger] 감사 로그에서 수행자를 찾지 못했습니다. Action: {action}, Target ID: {target.id}")
            return None
        except discord.Forbidden:
            logger.warning(f"[ServerLogger] 감사 로그 읽기 권한이 없습니다: {guild.name}")
        except Exception as e:
            logger.error(f"[ServerLogger] {action} 감사 로그 확인 중 오류: {e}", exc_info=True)
        return None

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        log_channel = await self.get_log_channel()
        if not log_channel: return
        user = await self.get_audit_log_user(role.guild, discord.AuditLogAction.role_create, role)
        if not user: return

        embed = discord.Embed(title="역할 생성됨 (役職作成)", color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="역할 (役職)", value=f"{role.mention} (`{role.name}`)", inline=False)
        embed.add_field(name="생성한 사람 (作成者)", value=user.mention, inline=False)
        embed.set_footer(text=f"역할 ID: {role.id}")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        log_channel = await self.get_log_channel()
        if not log_channel: return
        user = await self.get_audit_log_user(role.guild, discord.AuditLogAction.role_delete, role)
        if not user: return

        embed = discord.Embed(title="역할 삭제됨 (役職削除)", color=discord.Color.dark_red(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="역할 이름 (役職名)", value=f"`{role.name}`", inline=False)
        embed.add_field(name="삭제한 사람 (削除者)", value=user.mention, inline=False)
        embed.set_footer(text=f"역할 ID: {role.id}")
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        # 변경점이 없으면 아무것도 하지 않음
        if before.name == after.name and before.permissions == after.permissions and before.color == after.color:
            return

        log_channel = await self.get_log_channel()
        if not log_channel: return
        user = await self.get_audit_log_user(after.guild, discord.AuditLogAction.role_update, after)
        if not user: return
        
        embed = discord.Embed(title="역할 업데이트됨 (役職更新)", color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="역할 (役職)", value=f"{after.mention}", inline=False)
        
        changes = []
        if before.name != after.name:
            changes.append(f"**이름 (名前):** `{before.name}` → `{after.name}`")
        if before.permissions != after.permissions:
            changes.append("**권한이 변경되었습니다. (権限が変更されました。)**")
        if before.color != after.color:
            changes.append(f"**색상 (色):** `{before.color}` → `{after.color}`")

        if changes:
            embed.description = "\n".join(changes)
            embed.add_field(name="수정한 사람 (編集者)", value=user.mention, inline=False)
            embed.set_footer(text=f"역할 ID: {after.id}")
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        # 변경점이 없으면 아무것도 하지 않음
        if before.name == after.name and before.afk_channel == after.afk_channel and before.system_channel == after.system_channel:
             return
        
        log_channel = await self.get_log_channel()
        if not log_channel: return
        user = await self.get_audit_log_user(after, discord.AuditLogAction.guild_update, after)
        if not user: return

        embed = discord.Embed(title="서버 설정 업데이트됨 (サーバー設定更新)", color=discord.Color.purple(), timestamp=datetime.now(timezone.utc))
        
        changes = []
        if before.name != after.name:
            changes.append(f"**서버 이름 (サーバー名):** `{before.name}` → `{after.name}`")
        if before.afk_channel != after.afk_channel:
            before_ch = before.afk_channel.mention if before.afk_channel else '없음'
            after_ch = after.afk_channel.mention if after.afk_channel else '없음'
            changes.append(f"**AFK 채널 (AFKチャンネル):** {before_ch} → {after_ch}")
        if before.system_channel != after.system_channel:
            before_sys_ch = before.system_channel.mention if before.system_channel else '없음'
            after_sys_ch = after.system_channel.mention if after.system_channel else '없음'
            changes.append(f"**시스템 채널 (システムチャンネル):** {before_sys_ch} → {after_sys_ch}")


        if changes:
            embed.description = "\n".join(changes)
            embed.add_field(name="수정한 사람 (編集者)", value=user.mention, inline=False)
            await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerLogger(bot))
