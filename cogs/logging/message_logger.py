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

    async def cog_load(self):
        await self.load_configs()

    async def load_configs(self):
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

        message = payload.cached_message
        author = message.author if message else "알 수 없음"
        content = message.content if message else "캐시되지 않음 (キャッシュされていません)"
        attachments = message.attachments if message else []
        author_id = message.author.id if message else "알 수 없음"

        if message and message.author.bot: return

        deleter = f"{author.mention if isinstance(author, discord.User) else '작성자'} 본인 (本人)"
        deleter_found = False
        try:
            guild = self.bot.get_guild(payload.guild_id)
            if guild.me.guild_permissions.view_audit_log:
                await asyncio.sleep(1.5)
                async for entry in guild.audit_logs(action=discord.AuditLogAction.message_delete, limit=5, after=datetime.now(timezone.utc) - timedelta(seconds=10)):
                    if entry.target.id == author_id and entry.extra.count >= 1:
                        if entry.user.id != author_id:
                            deleter = entry.user.mention
                        deleter_found = True
                        break
        except discord.Forbidden:
            deleter = "권한 부족 (権限不足)"
        except Exception as e:
            logger.warning(f"메시지 삭제자 확인 중 오류: {e}")
        
        if not deleter_found and not isinstance(author, discord.User):
            deleter = "알 수 없음 (不明)"

        # [수정] description에 줄넘김을 사용하여 정보를 명확하게 분리
        desc = (
            f"**작성자 (作成者):** {author.mention if isinstance(author, discord.User) else '알 수 없음'}\n"
            f"**채널 (チャンネル):** <#{payload.channel_id}>\n"
            f"**삭제한 사람 (削除者):** {deleter}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"**내용 (内容):**\n>>> {content if content else '내용 없음 (内容なし)'}"
        )

        embed = discord.Embed(
            title="메시지 삭제됨 (メッセージ削除)",
            description=desc,
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=f"작성자 ID: {author_id}")

        if attachments:
            files = "\n".join([f"[{att.filename}]({att.url})" for att in attachments])
            embed.add_field(name="첨부 파일 (添付ファイル)", value=files, inline=False)
        
        await log_channel.send(embed=embed)

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot or before.content == after.content or not before.guild or not self.log_channel_id:
            return

        log_channel = await self.get_log_channel()
        if not log_channel: return

        # [수정] description과 필드를 사용하여 정보를 명확하게 분리
        desc = (
            f"**작성자 (作成者):** {after.author.mention}\n"
            f"**채널 (チャンネル):** {after.channel.mention}\n"
            f"**[수정된 메시지로 이동 (メッセージへ移動)]({after.jump_url})**"
        )
        
        embed = discord.Embed(
            title="메시지 수정됨 (メッセージ編集)",
            description=desc,
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc)
        )
        # 수정 전/후 내용은 필드로 분리하여 가독성 확보
        embed.add_field(name="수정 전 (編集前)", value=f"```\n{before.content}\n```" if before.content else "내용 없음", inline=False)
        embed.add_field(name="수정 후 (編集後)", value=f"```\n{after.content}\n```" if after.content else "내용 없음", inline=False)
        embed.set_footer(text=f"작성자 ID: {after.author.id}")
        
        await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(MessageLogger(bot))
