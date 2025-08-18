# cogs/logging/member_logger.py
import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone, timedelta
import asyncio

from utils.database import get_id

logger = logging.getLogger(__name__)

class MemberLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_id: int = None

    @commands.Cog.listener()
    async def on_ready(self):
        # [수정] cog_load로 분리
        await self.cog_load()
        
    async def cog_load(self):
        """설정을 로드하는 헬퍼 함수입니다."""
        self.log_channel_id = get_id("log_channel_member")
        if self.log_channel_id:
            logger.info(f"[MemberLogger] 멤버 활동 로그 채널이 설정되었습니다: #{self.log_channel_id}")
        else:
            logger.warning("[MemberLogger] 멤버 활동 로그 채널이 설정되지 않았습니다.")


    async def get_log_channel(self) -> discord.TextChannel | None:
        if not self.log_channel_id: return None
        return self.bot.get_channel(self.log_channel_id)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.bot: return
        log_channel = await self.get_log_channel()
        if not log_channel: return

        await asyncio.sleep(1.5) # 감사 로그 기록을 위한 대기 시간

        # --- 역할 변경 감지 ---
        if before.roles != after.roles:
            moderator = None
            try:
                # [개선] 시간 범위와 limit를 사용해 정확도 향상
                async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_role_update, after=datetime.now(timezone.utc) - timedelta(seconds=5)):
                    # 감사로그의 타겟이 이 멤버가 맞는지, 그리고 수행자가 봇이 아닌지 확인
                    if entry.target.id == after.id and not entry.user.bot:
                        moderator = entry.user
                        break
            except discord.Forbidden:
                logger.warning(f"[{after.guild.name}] 멤버 역할 업데이트 감사 로그 읽기 권한이 없습니다.")
            except Exception as e:
                logger.error(f"멤버 역할 업데이트 감사 로그 확인 중 오류: {e}", exc_info=True)
            
            # [수정] moderator가 사람일 경우에만 로그를 남김 (봇이나 역할 패널 등은 제외)
            if moderator:
                before_roles, after_roles = set(before.roles), set(after.roles)
                added_roles = after_roles - before_roles
                removed_roles = before_roles - after_roles

                if added_roles:
                    embed = discord.Embed(title="역할 추가됨 (役割付与)", color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
                    embed.add_field(name="유저 (ユーザー)", value=f"{after.mention} (`{after.id}`)", inline=False)
                    embed.add_field(name="추가된 역할 (付与された役割)", value=", ".join([r.mention for r in added_roles]), inline=False)
                    embed.add_field(name="수행자 (実行者)", value=f"{moderator.mention} (`{moderator.id}`)", inline=False)
                    await log_channel.send(embed=embed)
                
                if removed_roles:
                    embed = discord.Embed(title="역할 제거됨 (役割剥奪)", color=discord.Color.dark_red(), timestamp=datetime.now(timezone.utc))
                    embed.add_field(name="유저 (ユーザー)", value=f"{after.mention} (`{after.id}`)", inline=False)
                    embed.add_field(name="제거된 역할 (剥奪された役割)", value=", ".join([r.mention for r in removed_roles]), inline=False)
                    embed.add_field(name="수행자 (実行者)", value=f"{moderator.mention} (`{moderator.id}`)", inline=False)
                    await log_channel.send(embed=embed)

        # --- 닉네임 변경 감지 ---
        elif before.nick != after.nick:
            moderator = None
            try:
                # [개선] 시간 범위와 limit를 사용해 정확도 향상
                async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_update, after=datetime.now(timezone.utc) - timedelta(seconds=5)):
                    if entry.target.id == after.id and not entry.user.bot:
                         # 닉네임 변경 감사 로그는 before/after에 nick 속성이 있는지 확인해야 함
                        if hasattr(entry.before, 'nick') and hasattr(entry.after, 'nick'):
                            moderator = entry.user
                            break
            except discord.Forbidden:
                logger.warning(f"[{after.guild.name}] 멤버 닉네임 업데이트 감사 로그 읽기 권한이 없습니다.")
            except Exception as e:
                logger.error(f"멤버 닉네임 업데이트 감사 로그 확인 중 오류: {e}", exc_info=True)

            # [수정] 봇에 의한 변경(예: 접두사 관리)이 아닐 경우에만 로그 기록
            if moderator is None or moderator.id != self.bot.user.id:
                performer_mention = "본인 (本人)"
                if moderator and moderator.id != after.id:
                    performer_mention = f"{moderator.mention} (`{moderator.id}`)"
            
                embed = discord.Embed(title="닉네임 변경됨 (ニックネーム変更)", color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
                embed.add_field(name="유저 (ユーザー)", value=f"{after.mention} (`{after.id}`)", inline=False)
                embed.add_field(name="변경 전 (変更前)", value=f"`{before.nick or before.name}`", inline=True)
                embed.add_field(name="변경 후 (変更後)", value=f"`{after.nick or after.name}`", inline=True)
                embed.add_field(name="수행자 (実行者)", value=performer_mention, inline=False)
                await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(MemberLogger(bot))
