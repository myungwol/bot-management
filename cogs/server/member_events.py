# cogs/server/member_events.py

import discord
from discord.ext import commands
import logging
from typing import Optional
from cogs.server.system import format_embed_from_db # format_embed_from_db 함수를 system.py에서 가져옵니다.
from utils.database import get_id, get_embed_from_db

logger = logging.getLogger(__name__)

class MemberEvents(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.welcome_channel_id: Optional[int] = None
        self.farewell_channel_id: Optional[int] = None
        self.guest_role_id: Optional[int] = None
        logger.info("MemberEvents (입장/퇴장) Cog가 성공적으로 초기화되었습니다.")

    # cog가 로드될 때 설정을 불러옵니다.
    async def cog_load(self):
        await self.load_configs()

    # DB에서 채널/역할 ID를 불러와 내부 변수에 저장합니다.
    async def load_configs(self):
        self.welcome_channel_id = get_id("new_welcome_channel_id")
        self.farewell_channel_id = get_id("farewell_channel_id")
        self.guest_role_id = get_id("role_guest")
        logger.info("[MemberEvents Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        # 1. 초기 역할 부여
        if self.guest_role_id and (role := member.guild.get_role(self.guest_role_id)):
            try:
                await member.add_roles(role, reason="サーバー参加時の初期役割")
            except Exception as e:
                logger.error(f"'{self.guest_role_id}' 역할 부여에 실패했습니다: {e}")

        # 2. 환영 메시지 전송
        if self.welcome_channel_id and (ch := self.bot.get_channel(self.welcome_channel_id)):
            embed_data = await get_embed_from_db('welcome_embed')
            if embed_data:
                embed = format_embed_from_db(embed_data, member_mention=member.mention, member_name=member.display_name, guild_name=member.guild.name)
                if member.display_avatar:
                    embed.set_thumbnail(url=member.display_avatar.url)
                
                try:
                    await ch.send(f"ようこそ、{member.mention}さん！", embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
                except Exception as e:
                    logger.error(f"환영 메시지 전송에 실패했습니다: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if self.farewell_channel_id and (ch := self.bot.get_channel(self.farewell_channel_id)):
            embed_data = await get_embed_from_db('farewell_embed')
            if embed_data:
                embed = format_embed_from_db(embed_data, member_name=member.display_name)
                if member.display_avatar:
                    embed.set_thumbnail(url=member.display_avatar.url)
                
                try:
                    await ch.send(embed=embed)
                except Exception as e:
                    logger.error(f"작별 메시지 전송에 실패했습니다: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(MemberEvents(bot))
