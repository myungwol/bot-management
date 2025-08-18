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

        # --- [진단] 이벤트 발생 로그 ---
        logger.info(f"[진단] on_member_update: {after.name} | Nick: {before.nick != after.nick} | Roles: {before.roles != after.roles}")

        # --- 역할 변경 감지 ---
        if before.roles != after.roles:
            await asyncio.sleep(2)
            moderator = None
            try:
                async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_role_update):
                    if entry.target.id == after.id:
                        logger.info(f"[진단/역할] 감사 로그 발견: 대상={entry.target}, 수행자={entry.user}, 봇={entry.user.bot}")
                        if not entry.user.bot:
                            moderator = entry.user
                            break # 사람을 찾으면 바로 중지
            except Exception as e:
                logger.error(f"[진단/역할] 감사 로그 확인 중 오류: {e}")

            if moderator:
                before_roles, after_roles = set(before.roles), set(after.roles)
                added_roles = after_roles - before_roles
                removed_roles = before_roles - after_roles
                if added_roles:
                    # ... 로그 생성 로직 ...
                    embed = discord.Embed(title="역할 추가됨 (役割付与)", color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
                    embed.add_field(name="유저 (ユーザー)", value=after.mention, inline=False)
                    embed.add_field(name="추가된 역할 (付与された役割)", value=", ".join([r.mention for r in added_roles]), inline=False)
                    embed.add_field(name="수행자 (実行者)", value=moderator.mention, inline=False)
                    await log_channel.send(embed=embed)
                if removed_roles:
                    # ... 로그 생성 로직 ...
                    embed = discord.Embed(title="역할 제거됨 (役割剥奪)", color=discord.Color.dark_red(), timestamp=datetime.now(timezone.utc))
                    embed.add_field(name="유저 (ユーザー)", value=after.mention, inline=False)
                    embed.add_field(name="제거된 역할 (剥奪された役割)", value=", ".join([r.mention for r in removed_roles]), inline=False)
                    embed.add_field(name="수행자 (実行者)", value=moderator.mention, inline=False)
                    await log_channel.send(embed=embed)
            else:
                 logger.info(f"[진단/역할] 수행자를 찾지 못했거나 봇의 행동이므로 로그를 남기지 않습니다.")


        # --- 닉네임 변경 감지 ---
        elif before.nick != after.nick:
            await asyncio.sleep(2)
            moderator = "본인 (本人)"
            try:
                async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_update):
                    if entry.target.id == after.id and hasattr(entry.before, 'nick') and hasattr(entry.after, 'nick') and entry.before.nick != entry.after.nick:
                        logger.info(f"[진단/닉네임] 감사 로그 발견: 대상={entry.target}, 수행자={entry.user}, 봇={entry.user.bot}")
                        if not entry.user.bot:
                            if entry.user.id != after.id: moderator = entry.user
                        else:
                            moderator = None # 봇이 한 행동이면 None
                        break
            except Exception as e:
                logger.error(f"[진단/닉네임] 감사 로그 확인 중 오류: {e}")

            if moderator:
                embed = discord.Embed(title="닉네임 변경됨 (ニックネーム変更)", color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
                embed.add_field(name="유저 (ユーザー)", value=after.mention, inline=False)
                embed.add_field(name="변경 전 (変更前)", value=f"`{before.nick or before.name}`", inline=True)
                embed.add_field(name="변경 후 (変更後)", value=f"`{after.nick or after.name}`", inline=True)
                embed.add_field(name="수행자 (実行者)", value=moderator.mention if isinstance(moderator, discord.Member) else moderator, inline=False)
                await log_channel.send(embed=embed)
            else:
                logger.info(f"[진단/닉네임] 수행자를 찾지 못했거나 봇의 행동이므로 로그를 남기지 않습니다.")

async def setup(bot: commands.Bot):
    await bot.add_cog(MemberLogger(bot))
