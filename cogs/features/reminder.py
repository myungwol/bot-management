import discord
from discord.ext import commands
import asyncio
import logging
from typing import Optional, Dict

from utils.database import get_id

logger = logging.getLogger(__name__)

REMINDER_CONFIG = {
    'disboard': {
        'bot_id': 302050872383242240,
        'cooltime': 7200,
        'keyword': "表示順をアップしたにゃ！",
        'command': "/bump",
        'name': "Disboard BUMP"
    },
    'dissoku': {
        'bot_id': 603613388292390912,
        'cooltime': 3600,
        'keyword': "サーバーの表示順位をアップしました",
        'command': "/up",
        'name': "Dissoku UP"
    }
}

class Reminder(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.configs: Dict[str, Dict] = {}
        self.is_waiting: Dict[str, bool] = {key: False for key in REMINDER_CONFIG}
        logger.info("Reminder Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        await self.load_configs()

    async def load_configs(self):
        self.configs['disboard'] = {
            'channel_id': get_id("bump_reminder_channel_id"),
            'role_id': get_id("bump_reminder_role_id")
        }
        self.configs['dissoku'] = {
            'channel_id': get_id("dissoku_reminder_channel_id"),
            'role_id': get_id("dissoku_reminder_role_id")
        }
        logger.info(f"[Reminder] 설정 로드 완료: {self.configs}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self.bot.is_ready() or message.guild is None or not message.embeds:
            return

        embed_description = message.embeds[0].description
        if not embed_description:
            return

        for key, config in REMINDER_CONFIG.items():
            if message.author.id == config['bot_id'] and config['keyword'] in embed_description:
                await self.start_reminder(key, message.guild)
                break

    async def start_reminder(self, reminder_type: str, guild: discord.Guild):
        if not self.configs.get(reminder_type) or not self.configs[reminder_type].get('channel_id') or not self.configs[reminder_type].get('role_id'):
            return

        if self.is_waiting[reminder_type]:
            logger.warning(f"이미 {reminder_type} 알림이 대기 중입니다.")
            return

        cooltime = REMINDER_CONFIG[reminder_type]['cooltime']
        name = REMINDER_CONFIG[reminder_type]['name']
        
        logger.info(f"✅ [{guild.name}] 서버에서 {name}을(를) 감지했습니다. {cooltime // 3600}시간 뒤 알림을 설정합니다.")
        self.is_waiting[reminder_type] = True
        asyncio.create_task(self.send_reminder_after_delay(reminder_type, guild))

    async def send_reminder_after_delay(self, reminder_type: str, guild: discord.Guild):
        config = REMINDER_CONFIG[reminder_type]
        await asyncio.sleep(config['cooltime'])

        try:
            await self.load_configs()
            reminder_settings = self.configs.get(reminder_type)
            if not reminder_settings or not reminder_settings.get('channel_id') or not reminder_settings.get('role_id'):
                logger.error(f"알림을 보낼 시점에 {reminder_type}의 설정이 없습니다.")
                return

            channel = guild.get_channel(reminder_settings['channel_id'])
            role = guild.get_role(reminder_settings['role_id'])

            if not channel or not role:
                logger.error(f"{reminder_type} 알림에 필요한 채널/역할을 찾을 수 없습니다.")
                return

            reminder_message = f"⏰ {role.mention} {config['name']} の時間です！ `{config['command']}` をお願いします！"
            await channel.send(reminder_message)
            logger.info(f"✅ [{guild.name}] 서버에 {config['name']} 알림을 보냈습니다.")

        except Exception as e:
            logger.error(f"{config['name']} 알림 전송 중 오류 발생: {e}", exc_info=True)
        finally:
            self.is_waiting[reminder_type] = False

async def setup(bot: commands.Bot):
    await bot.add_cog(Reminder(bot))
