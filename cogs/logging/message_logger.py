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

        # --- [수정] 정보 수집 및 삭제자 추적 로직 전체 변경 ---
        author = None
        author_id = None
        deleter = None
        
        # 1. 감사 로그에서 정보 찾아보기 (가장 정확함)
        try:
            guild = self.bot.get_guild(payload.guild_id)
            if guild and guild.me.guild_permissions.view_audit_log:
                await asyncio.sleep(1.5) # 감사 로그 기록 대기
                async for entry in guild.audit_logs(action=discord.AuditLogAction.message_delete, limit=1, after=datetime.now(timezone.utc) - timedelta(seconds=5)):
                    # 감사 로그의 extra 정보에서 채널 ID가 일치하고, 대상이 멤버 객체일 때
                    if entry.extra.channel.id == payload.channel_id and isinstance(entry.target, discord.Member):
                        author = entry.target
                        author_id = entry.target.id
                        deleter = entry.user
                        break
        except discord.Forbidden:
            logger.warning(f"감사 로그 읽기 권한이 없어 삭제자를 추적할 수 없습니다: {guild.name}")
        except Exception as e:
            logger.error(f"메시지 삭제 감사 로그 확인 중 오류: {e}", exc_info=True)

        # 2. 감사 로그에서 못 찾았을 경우, 캐시된 메시지 확인
        message = payload.cached_message
        if message:
            # 감사 로그에서 작성자를 못 찾았을 때만 캐시 정보 사용
            if not author:
                author = message.author
                author_id = message.author.id
            # 봇 메시지는 무시
            if author.bot: return
            
        # 3. 최종적으로 삭제자 판별
        if deleter:
            # 감사 로그에서 찾은 삭제자가 작성자와 같으면 '본인'으로 표시
            if deleter.id == author_id:
                final_deleter_str = f"{author.mention if author else '작성자'} 본인 (本人)"
            else:
                final_deleter_str = deleter.mention
        elif author:
            # 감사 로그에 기록이 없으면 대부분 본인이 삭제한 경우
            final_deleter_str = f"{author.mention} 본인 (本人)"
        else:
            final_deleter_str = "알 수 없음 (不明)"

        # --- 정보 조합 끝 ---

        content = message.content if message else "캐시되지 않음 (キャッシュされていません)"
        attachments = message.attachments if message else []
        
        desc = (
            f"**작성자 (作成者):** {author.mention if author else '알 수 없음'}\n"
            f"**채널 (チャンネル):** <#{payload.channel_id}>\n"
            f"**삭제한 사람 (削除者):** {final_deleter_str}\n"
            f"━━━━━━━━━━━━━━━━\n"
            f"**내용 (内容):**\n>>> {content if content else '내용 없음 (内容なし)'}"
        )

        embed = discord.Embed(
            title="메시지 삭제됨 (メッセージ削除)",
            description=desc,
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text=f"작성자 ID: {author_id if author_id else '알 수 없음'}")

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
        embed.add_field(name="수정 전 (編集前)", value=f"```\n{before.content}\n```" if before.content else "내용 없음", inline=False)
        embed.add_field(name="수정 후 (編集後)", value=f"```\n{after.content}\n```" if after.content else "내용 없음", inline=False)
        embed.set_footer(text=f"작성자 ID: {after.author.id}")
        
        await log_channel.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(MessageLogger(bot))
