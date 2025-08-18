
# cogs/logging/message_logger.py
import discord
from discord.ext import commands
import logging
from datetime import datetime, timezone, timedelta

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
        if not self.log_channel_id:
            return None
        
        channel = self.bot.get_channel(self.log_channel_id)
        if isinstance(channel, discord.TextChannel):
            return channel
        return None

    # --- 메시지 삭제 로그 ---
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        # 봇이 보낸 메시지이거나, DM이거나, 로그 채널이 설정되지 않았으면 무시
        if message.author.bot or not message.guild or not self.log_channel_id:
            return

        log_channel = await self.get_log_channel()
        if not log_channel:
            return

        # 누가 삭제했는지 확인 (Audit Log)
        deleter = "알 수 없음 (不明)"
        # 봇에 '감사 로그 보기' 권한이 있어야 작동
        try:
            async for entry in message.guild.audit_logs(action=discord.AuditLogAction.message_delete, limit=5):
                # 시간, 대상, 채널이 일치하는 로그를 찾음
                if entry.target.id == message.author.id and entry.extra.channel.id == message.channel.id:
                    # 너무 오래된 로그는 무시 (5초 이내)
                    if (datetime.now(timezone.utc) - entry.created_at).total_seconds() < 5:
                        deleter = entry.user.mention
                        break
        except discord.Forbidden:
            deleter = "권한 부족 (権限不足)"
        except Exception as e:
            logger.warning(f"메시지 삭제자 확인 중 오류: {e}")

        embed = discord.Embed(
            title="메시지 삭제됨 (メッセージ削除)",
            description=f"**내용 (内容):**\n>>> {message.content if message.content else '내용 없음 (内容なし)'}",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="작성자 (作成者)", value=message.author.mention, inline=True)
        embed.add_field(name="채널 (チャンネル)", value=message.channel.mention, inline=True)
        embed.add_field(name="삭제한 사람 (削除者)", value=deleter, inline=True)
        embed.set_footer(text=f"작성자 ID: {message.author.id}")

        # 첨부 파일이 있었다면 로그에 추가
        if message.attachments:
            files = "\n".join([f"[{att.filename}]({att.url})" for att in message.attachments])
            embed.add_field(name="첨부 파일 (添付ファイル)", value=files, inline=False)
        
        await log_channel.send(embed=embed)

    # --- 메시지 수정 로그 ---
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        # 봇이 보낸 메시지이거나, 내용이 같거나(임베드 생성 등), DM이거나, 로그 채널이 없으면 무시
        if before.author.bot or before.content == after.content or not before.guild or not self.log_channel_id:
            return

        log_channel = await self.get_log_channel()
        if not log_channel:
            return

        embed = discord.Embed(
            title="메시지 수정됨 (メッセージ編集)",
            description=f"[수정된 메시지로 이동 (メッセージへ移動)]({after.jump_url})",
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.add_field(name="작성자 (作成者)", value=after.author.mention, inline=True)
        embed.add_field(name="채널 (チャンネル)", value=after.channel.mention, inline=True)
        embed.add_field(name="수정 전 (編集前)", value=f"```\n{before.content}\n```" if before.content else "내용 없음", inline=False)
        embed.add_field(name="수정 후 (編集後)", value=f"```\n{after.content}\n```" if after.content else "내용 없음", inline=False)
        embed.set_footer(text=f"작성자 ID: {after.author.id}")
        
        await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(MessageLogger(bot))
