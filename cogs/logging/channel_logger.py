# cogs/logging/channel_logger.py
import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone, timedelta
import asyncio

from utils.database import get_id

logger = logging.getLogger(__name__)

class ChannelLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_id: int = None

    @commands.Cog.listener()
    async def on_ready(self):
        # [수정] cog_load로 분리
        await self.cog_load()

    async def cog_load(self):
        """설정을 로드하는 헬퍼 함수입니다."""
        self.log_channel_id = get_id("log_channel_channel")
        if self.log_channel_id:
            logger.info(f"[ChannelLogger] 채널 관리 로그 채널이 설정되었습니다: #{self.log_channel_id}")
        else:
            logger.warning("[ChannelLogger] 채널 관리 로그 채널이 설정되지 않았습니다.")


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
    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel):
        log_channel = await self.get_log_channel()
        if not log_channel: return
        
        user = await self.get_audit_log_user(channel.guild, discord.AuditLogAction.channel_create, channel)
        if not user or user.bot: return

        embed = discord.Embed(title="채널 생성됨 (チャンネル作成)", color=discord.Color.green(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="채널 (チャンネル)", value=f"{channel.mention} (`{channel.name}`)", inline=False)
        embed.add_field(name="생성한 사람 (作成者)", value=f"{user.mention} (`{user.id}`)", inline=False)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        log_channel = await self.get_log_channel()
        if not log_channel: return
        
        user = await self.get_audit_log_user(channel.guild, discord.AuditLogAction.channel_delete, channel)
        if not user or user.bot: return
        
        embed = discord.Embed(title="채널 삭제됨 (チャンネル削除)", color=discord.Color.dark_red(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="채널 이름 (チャンネル名)", value=f"`{channel.name}`", inline=False)
        embed.add_field(name="삭제한 사람 (削除者)", value=f"{user.mention} (`{user.id}`)", inline=False)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: discord.abc.GuildChannel, after: discord.abc.GuildChannel):
        log_channel = await self.get_log_channel()
        if not log_channel: return
        
        user = await self.get_audit_log_user(after.guild, discord.AuditLogAction.channel_update, after)
        if not user or user.bot: return

        embed = discord.Embed(title="채널 업데이트됨 (チャンネル更新)", color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
        
        changes = []
        if before.name != after.name:
            changes.append(f"**이름 (名前):** `{before.name}` → `{after.name}`")
        if before.overwrites != after.overwrites:
            changes.append("**권한이 변경되었습니다. (権限が変更されました。)**")
        
        # 텍스트 채널에만 있는 속성 확인
        if isinstance(before, discord.TextChannel) and isinstance(after, discord.TextChannel):
            if before.topic != after.topic:
                # 토픽 내용은 길 수 있으므로 변경 사실만 알림
                changes.append(f"**주제 (トピック):** 주제가 변경되었습니다.")
        
        # 음성 채널에만 있는 속성 확인
        if isinstance(before, discord.VoiceChannel) and isinstance(after, discord.VoiceChannel):
             if before.user_limit != after.user_limit:
                 changes.append(f"**인원 제한 (人数制限):** `{before.user_limit}` → `{after.user_limit}`")


        if changes:
            embed.description = "\n".join(changes)
            embed.add_field(name="채널 (チャンネル)", value=after.mention, inline=False)
            embed.add_field(name="수정한 사람 (編集者)", value=f"{user.mention} (`{user.id}`)", inline=False)
            await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(ChannelLogger(bot))
