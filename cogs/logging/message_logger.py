# cogs/logging/message_logger.py
import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone, timedelta
import asyncio

from utils.database import get_id

logger = logging.getLogger(__name__)

class MessageLogger(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_id: int = None

    async def load_configs(self):
        """main.py의 on_ready 루프에 의해 호출됩니다."""
        self.log_channel_id = get_id("log_channel_message")
        if self.log_channel_id:
            logger.info(f"[MessageLogger] 메시지 로그 채널이 설정되었습니다: #{self.log_channel_id}")
        else:
            logger.warning("[MessageLogger] 메시지 로그 채널이 설정되지 않았습니다.")

    async def get_log_channel(self) -> discord.TextChannel | None:
        if not self.log_channel_id: return None
        channel = self.bot.get_channel(self.log_channel_id)
        if isinstance(channel, discord.TextChannel): return channel
        return None

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        if not payload.guild_id or not self.log_channel_id: return
        log_channel = await self.get_log_channel()
        if not log_channel: return

        author, author_id, deleter = None, None, None
        
        try:
            guild = self.bot.get_guild(payload.guild_id)
            if guild and guild.me.guild_permissions.view_audit_log:
                await asyncio.sleep(1.5)
                async for entry in guild.audit_logs(action=discord.AuditLogAction.message_delete, limit=1, after=datetime.now(timezone.utc) - timedelta(seconds=5)):
                    if entry.extra.channel.id == payload.channel_id and isinstance(entry.target, discord.Member):
                        author, author_id, deleter = entry.target, entry.target.id, entry.user
                        break
        except discord.Forbidden:
            logger.warning(f"감사 로그 읽기 권한이 없어 삭제자를 추적할 수 없습니다: {guild.name}")
        except Exception as e:
            logger.error(f"메시지 삭제 감사 로그 확인 중 오류: {e}", exc_info=True)

        message = payload.cached_message
        if message:
            if not author:
                author, author_id = message.author, message.author.id
            if author.bot: return
            
        if deleter:
            final_deleter_str = f"{author.mention if author else '작성자'} 본인" if deleter.id == author_id else deleter.mention
        elif author:
            final_deleter_str = f"{author.mention} 본인"
        else:
            final_deleter_str = "알 수 없음"

        content = message.content if message else "캐시되지 않음"
        attachments = message.attachments if message else []
        
        desc = (
            f"**작성자:** {author.mention if author else '알 수 없음'}\n"
            f"**채널:** <#{payload.channel_id}>\n"
            f"**삭제한 사람:** {final_deleter_str}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"**내용:**\n>>> {content if content else '내용 없음'}"
        )
        embed = discord.Embed(title="메시지 삭제됨", description=desc, color=discord.Color.red(), timestamp=datetime.now(timezone.utc))
        embed.set_footer(text=f"작성자 ID: {author_id if author_id else '알 수 없음'}")
        if attachments:
            embed.add_field(name="첨부 파일", value="\n".join([f"[{att.filename}]({att.url})" for att in attachments]), inline=False)
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or before.content == after.content or not before.guild or not self.log_channel_id:
            return
        log_channel = await self.get_log_channel()
        if not log_channel: return
        desc = (
            f"**작성자:** {after.author.mention}\n"
            f"**채널:** {after.channel.mention}\n"
            f"**[수정된 메시지로 이동]({after.jump_url})**"
        )
        embed = discord.Embed(title="메시지 수정됨", description=desc, color=discord.Color.gold(), timestamp=datetime.now(timezone.utc))
        embed.add_field(name="수정 전", value=f"```\n{before.content}\n```" if before.content else "내용 없음", inline=False)
        embed.add_field(name="수정 후", value=f"```\n{after.content}\n```" if after.content else "내용 없음", inline=False)
        embed.set_footer(text=f"작성자 ID: {after.author.id}")
        await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(MessageLogger(bot))
