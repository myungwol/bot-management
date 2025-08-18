# cogs/logging/guild_logger.py
import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone

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

    async def get_audit_log_user(self, guild: discord.Guild, action: discord.AuditLogAction, target_id: int) -> str:
        """감사 로그를 확인하여 작업을 수행한 유저를 찾습니다."""
        try:
            if guild.me.guild_permissions.view_audit_log:
                async for entry in guild.audit_logs(action=action, limit=1):
                    if entry.target.id == target_id:
                        # 봇이 한 행동은 무시
                        if entry.user.bot: return None
                        return entry.user.mention
        except discord.Forbidden:
            return "권한 부족 (権限不足)"
        except Exception as e:
            logger.error(f"감사 로그 확인 중 오류: {e}")
        return "알 수 없음 (不明)"

    # --- 채널 관리 로그 ---
    @commands.Cog.listener()
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        log_channel = await self.get_log_channel("channel")
        if not log_channel: return

        user = await self.get_audit_log_user(channel.guild, discord.AuditLogAction.channel_create, channel.id)
        if not user: return

        embed = discord.Embed(title="채널 생성됨 (チャンネル作成)", color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="채널 (チャンネル)", value=f"{channel.mention} (`{channel.name}`)", inline=False)
        embed.add_field(name="생성한 사람 (作成者)", value=user, inline=False)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        log_channel = await self.get_log_channel("channel")
        if not log_channel: return

        user = await self.get_audit_log_user(channel.guild, discord.AuditLogAction.channel_delete, channel.id)
        if not user: return
        
        embed = discord.Embed(title="채널 삭제됨 (チャンネル削除)", color=discord.Color.dark_red(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="채널 이름 (チャンネル名)", value=f"`{channel.name}`", inline=False)
        embed.add_field(name="삭제한 사람 (削除者)", value=user, inline=False)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        log_channel = await self.get_log_channel("channel")
        if not log_channel: return

        user = await self.get_audit_log_user(after.guild, discord.AuditLogAction.channel_update, after.id)
        if not user: return

        embed = discord.Embed(title="채널 업데이트됨 (チャンネル更新)", color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="채널 (チャンネル)", value=f"{after.mention}", inline=False)
        
        if before.name != after.name:
            embed.add_field(name="이름 변경 (名前変更)", value=f"`{before.name}` → `{after.name}`", inline=False)
        
        # 다른 변경사항들 (권한 등) - 더 자세한 로그를 원하면 여기에 추가 가능
        # 이 예제에서는 이름 변경만 기록
        
        # 변경 사항이 있을 때만 로그 전송
        if len(embed.fields) > 1:
            embed.add_field(name="수정한 사람 (編集者)", value=user, inline=False)
            await log_channel.send(embed=embed)

    # --- 역할 관리 로그 ---
    @commands.Cog.listener()
    async def on_guild_role_create(self, role: discord.Role):
        log_channel = await self.get_log_channel("role")
        if not log_channel: return

        user = await self.get_audit_log_user(role.guild, discord.AuditLogAction.role_create, role.id)
        if not user: return

        embed = discord.Embed(title="역할 생성됨 (役職作成)", color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="역할 (役職)", value=f"{role.mention} (`{role.name}`)", inline=False)
        embed.add_field(name="생성한 사람 (作成者)", value=user, inline=False)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_delete(self, role: discord.Role):
        log_channel = await self.get_log_channel("role")
        if not log_channel: return
        
        user = await self.get_audit_log_user(role.guild, discord.AuditLogAction.role_delete, role.id)
        if not user: return

        embed = discord.Embed(title="역할 삭제됨 (役職削除)", color=discord.Color.dark_red(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="역할 이름 (役職名)", value=f"`{role.name}`", inline=False)
        embed.add_field(name="삭제한 사람 (削除者)", value=user, inline=False)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_role_update(self, before: discord.Role, after: discord.Role):
        log_channel = await self.get_log_channel("role")
        if not log_channel: return

        user = await self.get_audit_log_user(after.guild, discord.AuditLogAction.role_update, after.id)
        if not user: return
        
        embed = discord.Embed(title="역할 업데이트됨 (役職更新)", color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="역할 (役職)", value=f"{after.mention}", inline=False)
        
        if before.name != after.name:
            embed.add_field(name="이름 변경 (名前変更)", value=f"`{before.name}` → `{after.name}`", inline=False)
        if before.permissions != after.permissions:
            embed.add_field(name="권한 변경 (権限変更)", value="역할 권한이 변경되었습니다.", inline=False)

        if len(embed.fields) > 1:
            embed.add_field(name="수정한 사람 (編集者)", value=user, inline=False)
            await log_channel.send(embed=embed)

    # --- 서버 관리 로그 ---
    @commands.Cog.listener()
    async def on_guild_update(self, before: discord.Guild, after: discord.Guild):
        log_channel = await self.get_log_channel("server")
        if not log_channel: return

        user = await self.get_audit_log_user(after, discord.AuditLogAction.guild_update, after.id)
        if not user: return

        embed = discord.Embed(title="서버 설정 업데이트됨 (サーバー設定更新)", color=discord.Color.purple(), timestamp=datetime.now(timezone.utc))
        
        if before.name != after.name:
            embed.add_field(name="서버 이름 변경 (サーバー名変更)", value=f"`{before.name}` → `{after.name}`", inline=False)

        if len(embed.fields) > 0:
            embed.add_field(name="수정한 사람 (編集者)", value=user, inline=False)
            await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(GuildLogger(bot))
