# cogs/server/stats_updater.py
import discord
from discord.ext import commands, tasks
import logging
# [수정] 타입 힌트를 사용하기 위해 typing 라이브러리 import
from typing import Optional

from utils.database import get_all_stats_channels

logger = logging.getLogger(__name__)

class StatsUpdater(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.update_stats_loop.start()
        logger.info("StatsUpdater Cog가 성공적으로 초기화되고, 통계 업데이트 루프가 시작되었습니다.")

    def cog_unload(self):
        self.update_stats_loop.cancel()
        logger.info("통계 업데이트 루프가 중지되었습니다.")

    @tasks.loop(minutes=10)
    async def update_stats_loop(self):
        try:
            configs = await get_all_stats_channels()
            if not configs:
                return

            # [개선] 봇이 여러 서버에 있을 경우를 대비해 서버별로 처리
            for guild in self.bot.guilds:
                guild_configs = [c for c in configs if c.get("guild_id") == guild.id]
                if not guild_configs:
                    continue

                for config in guild_configs:
                    stat_type = config.get("stat_type")
                    template = config.get("channel_name_template")
                    channel_id = config.get("channel_id")
                    
                    if not all([stat_type, template, channel_id]):
                        continue

                    count = 0
                    if stat_type == "total":
                        count = guild.member_count
                    elif stat_type == "humans":
                        count = len([m for m in guild.members if not m.bot])
                    elif stat_type == "bots":
                        count = len([m for m in guild.members if m.bot])
                    elif stat_type == "boosters":
                        count = guild.premium_subscription_count
                    elif stat_type == "role":
                        if role_id := config.get("role_id"):
                            if role := guild.get_role(role_id):
                                count = len(role.members)
                            else:
                                logger.warning(f"통계 업데이트: 역할 ID({role_id})를 찾을 수 없습니다.")
                    
                    try:
                        new_name = template.format(count=count)
                        if channel := guild.get_channel(channel_id): # get_channel은 빠르므로 루프 내에서 사용
                            if channel.name != new_name:
                                await channel.edit(name=new_name, reason="서버 통계 자동 업데이트")
                        else:
                            logger.warning(f"통계 업데이트: 채널 ID({channel_id})를 찾을 수 없습니다.")
                    except KeyError:
                         logger.error(f"통계 채널({channel_id})의 이름 형식('{template}')에 '{count}' 플레이스홀더가 없습니다.")
                    except Exception as e:
                        logger.error(f"통계 채널({channel_id}) 이름 업데이트 중 오류 발생: {e}")

        except Exception as e:
            logger.error(f"통계 업데이트 루프 중 최상위 오류 발생: {e}", exc_info=True)

    @update_stats_loop.before_loop
    async def before_update_stats_loop(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(StatsUpdater(bot))
