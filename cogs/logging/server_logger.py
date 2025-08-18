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

    @commands.Cog.listener()
    async def on_ready(self):
        # [수정] cog_load로 분리하여 재로딩 시에도 설정이 불러와지도록 개선
        await self.cog_load()

    async def cog_load(self):
        """설정을 로드하는 헬퍼 함수입니다."""
        self.log_channel_id = get_id("log_channel_server")
        if self.log_channel_id:
            logger.info(f"[ServerLogger] 서버/역할 로그 채널이 설정되었습니다: #{self.log_channel_id}")
        else:
            logger.warning("[ServerLogger] 서버/역할 로그 채널이 설정되지 않았습니다.")

    async def get_log_channel(self) -> discord.TextChannel | None:
        if not self.log_channel_id: return None
        return self.bot.get_channel(self.log_channel_id)
        
    async def get_audit_log_user(self, guild: discord.Guild, action: discord.AuditLogAction, target) -> discord.Member | None:
        """
        [개선] 감사 로그 조회 로직을 안정적으로 변경합니다.
        시간 범위와 limit를 사용하여 정확도를 높입니다.
        """
        await asyncio.sleep(1.5) # API 전파 시간 대기
        try:
            # 5초 이내의 로그 5개를 가져와서 확인
            async for entry in guild.audit_logs(action=action, limit=5, after=datetime.now(timezone.utc) - timedelta(seconds=5)):
                if entry.target and entry.target.id == target.id and not entry.user.bot:
                    return entry.user
        except discord.Forbidden:
            logger.warning(f"감사 로그 읽기 권한이 없습니다: {guild.name}")
        except Exception as e:
            logger.error(f"'{action}' 감사 로그 확인 중 오류: {e}", exc_info=True)
        return None

    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        log_channel = await self.get_log_channel()
        if not log_channel: return
        
        user = await self.get_audit_log_user(role.guild, discord.AuditLogAction.role_create, role)
        # [수정] user가 봇이거나 찾지 못한 경우 로그를 남기지 않음
        if not user or user.bot: return

        embed = discord.Embed(title="역할 생성됨 (役職作成)", color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="역할 (役職)", value=f"{role.mention} (`{role.name}`)", inline=False)
        embed.add_field(name="생성한 사람 (作成者)", value=f"{user.mention} (`{user.id}`)", inline=False)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        log_channel = await self.get_log_channel()
        if not log_channel: return
        
        user = await self.get_audit_log_user(role.guild, discord.AuditLogAction.role_delete, role)
        if not user or user.bot: return

        embed = discord.Embed(title="역할 삭제됨 (役職削除)", color=discord.Color.dark_red(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="역할 이름 (役職名)", value=f"`{role.name}`", inline=False)
        embed.add_field(name="삭제한 사람 (削除者)", value=f"{user.mention} (`{user.id}`)", inline=False)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        log_channel = await self.get_log_channel()
        if not log_channel: return
        
        user = await self.get_audit_log_user(after.guild, discord.AuditLogAction.role_update, after)
        if not user or user.bot: return
        
        embed = discord.Embed(title="역할 업데이트됨 (役職更新)", color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="역할 (役職)", value=f"{after.mention}", inline=False)
        
        changes = []
        if before.name != after.name:
            changes.append(f"**이름 (名前):** `{before.name}` → `{after.name}`")
        if before.permissions != after.permissions:
            # 권한 변경은 매우 길어질 수 있으므로, 간단한 알림으로 대체
            changes.append("**권한이 변경되었습니다. (権限が変更されました。)**")
        if before.color != after.color:
            changes.append(f"**색상 (色):** `{before.color}` → `{after.color}`")
        if before.mentionable != after.mentionable:
            changes.append(f"**멘션 가능 (メンション可能):** `{before.mentionable}` → `{after.mentionable}`")

        if changes:
            embed.description = "\n".join(changes)
            embed.add_field(name="수정한 사람 (編集者)", value=f"{user.mention} (`{user.id}`)", inline=False)
            await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        log_channel = await self.get_log_channel()
        if not log_channel: return
        
        user = await self.get_audit_log_user(after, discord.AuditLogAction.guild_update, after)
        if not user or user.bot: return

        embed = discord.Embed(title="서버 설정 업데이트됨 (サーバー設定更新)", color=discord.Color.purple(), timestamp=datetime.now(timezone.utc))
        
        changes = []
        if before.name != after.name:
            changes.append(f"**서버 이름 (サーバー名):** `{before.name}` → `{after.name}`")
        if before.afk_channel != after.afk_channel:
            before_afk = before.afk_channel.mention if before.afk_channel else '없음'
            after_afk = after.afk_channel.mention if after.afk_channel else '없음'
            changes.append(f"**AFK 채널 (AFKチャンネル):** {before_afk} → {after_afk}")
        if before.afk_timeout != after.afk_timeout:
             changes.append(f"**AFK 시간 (AFKタイムアウト):** `{before.afk_timeout/60}`분 → `{after.afk_timeout/60}`분")
        if before.system_channel != after.system_channel:
            before_sys = before.system_channel.mention if before.system_channel else '없음'
            after_sys = after.system_channel.mention if after.system_channel else '없음'
            changes.append(f"**시스템 메시지 채널 (システムメッセージチャンネル):** {before_sys} → {after_sys}")


        if changes:
            embed.description = "\n".join(changes)
            embed.add_field(name="수정한 사람 (編集者)", value=f"{user.mention} (`{user.id}`)", inline=False)
            await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerLogger(bot))
