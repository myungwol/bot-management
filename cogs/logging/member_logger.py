# cogs/logging/member_logger.py
import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone
import asyncio

from utils.database import get_id

logger = logging.getLogger(__name__)

class MemberLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_id: int = None

    @commands.Cog.listener()
    async def on_ready(self):
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

        # --- 1. 역할 변경 감지 ---
        if before.roles != after.roles:
            # 감사 로그를 확인하기 전에 충분히 대기
            await asyncio.sleep(2)
            moderator = None
            try:
                async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_role_update):
                    if entry.target.id == after.id and not entry.user.bot:
                        moderator = entry.user
                        break
            except discord.Forbidden: moderator = "권한 부족"
            except Exception: pass

            # 봇이 한 행동이 아니라고 확신할 수 있을 때만 로그 기록
            if isinstance(moderator, discord.Member):
                before_roles, after_roles = set(before.roles), set(after.roles)
                added_roles = after_roles - before_roles
                removed_roles = before_roles - after_roles

                if added_roles:
                    for role in added_roles:
                        embed = discord.Embed(title="역할 추가됨 (役割付与)", color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
                        embed.add_field(name="유저 (ユーザー)", value=after.mention, inline=False)
                        embed.add_field(name="추가된 역할 (付与された役割)", value=role.mention, inline=False)
                        embed.add_field(name="수행자 (実行者)", value=moderator.mention, inline=False)
                        embed.set_author(name=f"{after.display_name} ({after.id})", icon_url=after.display_avatar.url if after.display_avatar else None)
                        await log_channel.send(embed=embed)
                
                if removed_roles:
                    for role in removed_roles:
                        embed = discord.Embed(title="역할 제거됨 (役割剥奪)", color=discord.Color.dark_red(), timestamp=datetime.now(timezone.utc))
                        embed.add_field(name="유저 (ユーザー)", value=after.mention, inline=False)
                        embed.add_field(name="제거된 역할 (剥奪された役割)", value=role.mention, inline=False)
                        embed.add_field(name="수행자 (実行者)", value=moderator.mention, inline=False)
                        embed.set_author(name=f"{after.display_name} ({after.id})", icon_url=after.display_avatar.url if after.display_avatar else None)
                        await log_channel.send(embed=embed)

        # --- 2. 닉네임 변경 감지 ---
        elif before.nick != after.nick:
            await asyncio.sleep(2)
            moderator = "본인 (本人)" # 기본값
            try:
                async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_update):
                    # 닉네임 변경 감사 로그는 target이 명확하므로 바로 사용 가능
                    if entry.target.id == after.id and hasattr(entry.before, 'nick') and hasattr(entry.after, 'nick') and entry.before.nick != entry.after.nick:
                        if not entry.user.bot: # 봇이 한 행동은 제외
                            if entry.user.id != after.id: # 본인이 직접 바꾼게 아니라면
                                moderator = entry.user
                        else:
                            moderator = None # 봇이 한 행동이면 로그 안 남김
                        break
            except discord.Forbidden: moderator = "권한 부족"
            except Exception: pass
            
            if moderator: # moderator가 None이 아닐 경우에만 (봇이 한 행동이 아닐 때)
                embed = discord.Embed(title="닉네임 변경됨 (ニックネーム変更)", color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
                embed.add_field(name="유저 (ユーザー)", value=after.mention, inline=False)
                embed.add_field(name="변경 전 (変更前)", value=f"`{before.nick or before.name}`", inline=True)
                embed.add_field(name="변경 후 (変更後)", value=f"`{after.nick or after.name}`", inline=True)
                embed.add_field(name="수행자 (実行者)", value=moderator.mention if isinstance(moderator, discord.Member) else moderator, inline=False)
                embed.set_author(name=f"{after.display_name} ({after.id})", icon_url=after.display_avatar.url if after.display_avatar else None)
                await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(MemberLogger(bot))
