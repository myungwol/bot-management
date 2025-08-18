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
        self.log_channel_id: int | None = None

    @commands.Cog.listener()
    async def cog_load(self):
        """Cog가 로드될 때 로그 채널 ID를 설정합니다."""
        self.log_channel_id = get_id("log_channel_member")
        if self.log_channel_id:
            logger.info(f"[MemberLogger] 멤버 활동 로그 채널이 설정되었습니다: #{self.log_channel_id}")
        else:
            logger.warning("[MemberLogger] 멤버 활동 로그 채널이 설정되지 않았습니다.")


    async def get_log_channel(self) -> discord.TextChannel | None:
        if not self.log_channel_id:
            return None
        return self.bot.get_channel(self.log_channel_id)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.bot: return
        
        log_channel = await self.get_log_channel()
        if not log_channel: return

        # --- 역할 변경 감지 ---
        if before.roles != after.roles:
            await asyncio.sleep(2) # 감사 로그 기록 대기
            moderator = None
            try:
                async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_role_update):
                    if entry.target and entry.target.id == after.id and entry.user and not entry.user.bot:
                        moderator = entry.user
                        break
            except discord.Forbidden:
                 logger.warning(f"[MemberLogger] 감사 로그 읽기 권한이 없습니다: {after.guild.name}")
            except Exception as e:
                logger.error(f"[MemberLogger] 역할 감사 로그 확인 중 오류: {e}", exc_info=True)

            if not moderator:
                logger.warning(f"[MemberLogger] 역할 변경 수행자를 찾지 못했습니다: {after.name}")
                return

            before_roles, after_roles = set(before.roles), set(after.roles)
            added_roles = after_roles - before_roles
            removed_roles = before_roles - after_roles
            
            if added_roles:
                embed = discord.Embed(title="역할 추가됨 (役割付与)", color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
                embed.add_field(name="유저 (ユーザー)", value=after.mention, inline=False)
                embed.add_field(name="추가된 역할 (付与された役割)", value=", ".join([r.mention for r in added_roles]), inline=False)
                embed.add_field(name="수행자 (実行者)", value=moderator.mention, inline=False)
                embed.set_footer(text=f"유저 ID: {after.id}")
                await log_channel.send(embed=embed)
            if removed_roles:
                embed = discord.Embed(title="역할 제거됨 (役割剥奪)", color=discord.Color.dark_red(), timestamp=datetime.now(timezone.utc))
                embed.add_field(name="유저 (ユーザー)", value=after.mention, inline=False)
                embed.add_field(name="제거된 역할 (剥奪された役割)", value=", ".join([r.mention for r in removed_roles]), inline=False)
                embed.add_field(name="수행자 (実行者)", value=moderator.mention, inline=False)
                embed.set_footer(text=f"유저 ID: {after.id}")
                await log_channel.send(embed=embed)

        # --- 닉네임 변경 감지 ---
        elif before.nick != after.nick:
            await asyncio.sleep(2) # 감사 로그 기록 대기
            moderator_obj = None
            is_self = False
            
            try:
                async for entry in after.guild.audit_logs(limit=5, action=discord.AuditLogAction.member_update):
                    # 닉네임 변경 감사 로그인지 정확히 확인
                    if entry.target and entry.target.id == after.id and entry.before.nick != entry.after.nick:
                        if entry.user and not entry.user.bot:
                            moderator_obj = entry.user
                            if moderator_obj.id == after.id:
                                is_self = True
                        break # 관련된 첫 로그를 찾으면 종료
            except discord.Forbidden:
                logger.warning(f"[MemberLogger] 감사 로그 읽기 권한이 없습니다: {after.guild.name}")
            except Exception as e:
                logger.error(f"[MemberLogger] 닉네임 감사 로그 확인 중 오류: {e}", exc_info=True)

            # 감사 로그에 기록이 없는 경우, 본인이 변경한 것으로 간주
            if not moderator_obj:
                is_self = True
            
            moderator_mention = "본인 (本人)" if is_self else moderator_obj.mention
            
            embed = discord.Embed(title="닉네임 변경됨 (ニックネーム変更)", color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
            embed.add_field(name="유저 (ユーザー)", value=after.mention, inline=False)
            embed.add_field(name="변경 전 (変更前)", value=f"`{before.nick or before.display_name}`", inline=True)
            embed.add_field(name="변경 후 (変更後)", value=f"`{after.nick or after.display_name}`", inline=True)
            embed.add_field(name="수행자 (実行者)", value=moderator_mention, inline=False)
            embed.set_footer(text=f"유저 ID: {after.id}")
            await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(MemberLogger(bot))
