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
        # 봇 자신의 프로필 업데이트(예: 활동 상태 변경)는 무시
        if before.bot: return
        log_channel = await self.get_log_channel()
        if not log_channel: return

        # 감사 로그를 확인하기 전에 잠시 대기 (API 기록 시간 확보)
        await asyncio.sleep(1.5)
        
        moderator = "알 수 없음"
        
        # 1. 역할 변경 감지
        if before.roles != after.roles:
            try:
                async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update):
                    # 감사 로그의 대상이 해당 멤버이고, 수행자가 봇이 아닐 경우
                    if entry.target.id == after.id and not entry.user.bot:
                        moderator = entry.user
                        break
            except discord.Forbidden: moderator = "권한 부족"
            except Exception: pass # 오류 발생 시 기본값 사용

            # moderator가 None이면 봇이 역할을 변경했거나, 디스코드 자체 기능(온보딩 등)일 가능성이 높음 -> 로그 X
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

        # 2. 닉네임 변경 감지
        elif before.nick != after.nick:
            moderator = "본인 (本人)" # 기본값은 본인
            try:
                async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_update):
                    if entry.target.id == after.id and not entry.user.bot:
                        # 닉네임 변경이 실제로 있었는지 확인
                        if entry.before.nick != entry.after.nick:
                           moderator = entry.user
                        break
            except discord.Forbidden: moderator = "권한 부족"
            except Exception: pass
            
            # 봇이 닉네임을 변경한 경우는 moderator가 "알 수 없음"으로 남게 됨 -> 로그 X
            if isinstance(moderator, discord.Member) or moderator == "본인 (本人)":
                embed = discord.Embed(title="닉네임 변경됨 (ニックネーム変更)", color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
                embed.add_field(name="유저 (ユーザー)", value=after.mention, inline=False)
                embed.add_field(name="변경 전 (変更前)", value=f"`{before.nick or before.name}`", inline=True)
                embed.add_field(name="변경 후 (変更後)", value=f"`{after.nick or after.name}`", inline=True)
                embed.add_field(name="수행자 (実行者)", value=moderator.mention if isinstance(moderator, discord.Member) else moderator, inline=False)
                embed.set_author(name=f"{after.display_name} ({after.id})", icon_url=after.display_avatar.url if after.display_avatar else None)
                await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(MemberLogger(bot))
