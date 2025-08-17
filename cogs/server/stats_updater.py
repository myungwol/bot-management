# cogs/server/stats_updater.py
"""
서버 통계(유저 수 등)를 주기적으로 업데이트하여 채널 이름에 표시하는 Cog입니다.
"""
import discord
from discord.ext import commands, tasks
import logging
from typing import Optional

from utils.database import get_all_stats_channels

logger = logging.getLogger(__name__)

class StatsUpdater(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.update_stats_loop.start()
        logger.info("StatsUpdater Cog가 성공적으로 초기화되고, 통계 업데이트 루프가 시작되었습니다.")

    def cog_unload(self):
        """Cog가 언로드될 때 루프를 안전하게 중지합니다."""
        self.update_stats_loop.cancel()
        logger.info("통계 업데이트 루프가 중지되었습니다.")

    @tasks.loop(minutes=10)
    async def update_stats_loop(self):
        """10분마다 실행되는 메인 루프. 설정된 모든 통계 채널을 업데이트합니다."""
        try:
            configs = await get_all_stats_channels()
            if not configs:
                return # 설정된 채널이 없으면 아무것도 하지 않음

            # 서버(Guild) 객체를 가져옵니다.
            # 여러 서버를 지원하려면 이 부분을 수정해야 합니다.
            if not self.bot.guilds:
                logger.warning("통계 업데이트: 봇이 속한 서버가 없어 스킵합니다.")
                return
            guild = self.bot.guilds[0]

            for config in configs:
                stat_type = config.get("stat_type")
                template = config.get("channel_name_template")
                channel_id = config.get("channel_id")
                
                count = 0
                # 통계 유형에 따라 인원수 계산
                if stat_type == "total":
                    count = guild.member_count
                elif stat_type == "humans":
                    count = len([m for m in guild.members if not m.bot])
                elif stat_type == "bots":
                    count = len([m for m in guild.members if m.bot])
                elif stat_type == "boosters":
                    count = guild.premium_subscription_count
                elif stat_type == "role":
                    role_id = config.get("role_id")
                    if role_id:
                        role = guild.get_role(role_id)
                        if role:
                            count = len(role.members)
                        else:
                            logger.warning(f"통계 업데이트: 역할 ID({role_id})를 찾을 수 없습니다.")
                
                new_name = template.format(count=count)
                
                channel = self.bot.get_channel(channel_id)
                if channel:
                    if channel.name != new_name:
                        await channel.edit(name=new_name, reason="서버 통계 자동 업데이트")
                else:
                    logger.warning(f"통계 업데이트: 채널 ID({channel_id})를 찾을 수 없습니다.")

        except Exception as e:
            logger.error(f"통계 업데이트 루프 중 오류 발생: {e}", exc_info=True)

    @update_stats_loop.before_loop
    async def before_update_stats_loop(self):
        """루프가 시작되기 전에 봇이 준비될 때까지 기다립니다."""
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(StatsUpdater(bot))
