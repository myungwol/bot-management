# cogs/logging/member_logger.py
import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone

from utils.database import get_id

logger = logging.getLogger(__name__)

class MemberLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_id: int = None

    @commands.Cog.listener()
    async def on_ready(self):
        await self.load_configs()

    async def load_configs(self):
        self.log_channel_id = get_id("log_channel_member")
        if self.log_channel_id:
            logger.info(f"[MemberLogger] 멤버 활동 로그 채널이 설정되었습니다: #{self.log_channel_id}")

    async def get_log_channel(self) -> discord.TextChannel | None:
        if not self.log_channel_id: return None
        return self.bot.get_channel(self.log_channel_id)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.bot or not self.log_channel_id: return
        log_channel = await self.get_log_channel()
        if not log_channel: return

        moderator = None
        # 역할 변경과 닉네임 변경은 감사 로그 액션이 다름
        audit_action = None
        if before.roles != after.roles:
            audit_action = discord.AuditLogAction.member_role_update
        elif before.nick != after.nick:
            audit_action = discord.AuditLogAction.member_update

        if audit_action:
            try:
                async for entry in after.guild.audit_logs(limit=1, action=audit_action):
                    if entry.target.id == after.id and not entry.user.bot:
                        moderator = entry.user
                        break
            except discord.Forbidden: moderator = "권한 부족"
            except Exception as e: logger.error(f"멤버 업데이트 감사 로그 확인 중 오류: {e}")

        # 1. 닉네임 변경 감지
        if before.nick != after.nick:
            embed = discord.Embed(title="닉네임 변경됨 (ニックネーム変更)", color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
            embed.set_author(name=f"{after.display_name} ({after.id})", icon_url=after.display_avatar.url if after.display_avatar else None)
            embed.add_field(name="유저 (ユーザー)", value=after.mention, inline=False)
            embed.add_field(name="변경 전 (変更前)", value=f"`{before.nick or before.name}`", inline=True)
            embed.add_field(name="변경 후 (変更後)", value=f"`{after.nick or after.name}`", inline=True)
            if moderator:
                embed.add_field(name="수행자 (実行者)", value=moderator.mention if isinstance(moderator, discord.Member) else str(moderator), inline=False)
            await log_channel.send(embed=embed)

        # 2. 역할 변경 감지
        if before.roles != after.roles:
            before_roles, after_roles = set(before.roles), set(after.roles)
            added_roles = after_roles - before_roles
            removed_roles = before_roles - after_roles

            if added_roles:
                for role in added_roles:
                    embed = discord.Embed(title="역할 추가됨 (役割付与)", color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
                    embed.set_author(name=f"{after.display_name} ({after.id})", icon_url=after.display_avatar.url if after.display_avatar else None)
                    embed.add_field(name="유저 (ユーザー)", value=after.mention, inline=False)
                    embed.add_field(name="추가된 역할 (付与された役割)", value=role.mention, inline=False)
                    if moderator:
                        embed.add_field(name="수행자 (実行者)", value=moderator.mention if isinstance(moderator, discord.Member) else str(moderator), inline=False)
                    await log_channel.send(embed=embed)

            if removed_roles:
                for role in removed_roles:
                    embed = discord.Embed(title="역할 제거됨 (役割剥奪)", color=discord.Color.dark_red(), timestamp=datetime.now(timezone.utc))
                    embed.set_author(name=f"{after.display_name} ({after.id})", icon_url=after.display_avatar.url if after.display_avatar else None)
                    embed.add_field(name="유저 (ユーザー)", value=after.mention, inline=False)
                    embed.add_field(name="제거된 역할 (剥奪された役割)", value=role.mention, inline=False)
                    if moderator:
                        embed.add_field(name="수행자 (実行者)", value=moderator.mention if isinstance(moderator, discord.Member) else str(moderator), inline=False)
                    await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(MemberLogger(bot))
