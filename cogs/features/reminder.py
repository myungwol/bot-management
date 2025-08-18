import discord
from discord.ext import commands, tasks
import asyncio
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta, timezone

# [수정] 새로 만든 DB 함수들을 import
from utils.database import get_id, schedule_reminder, get_due_reminders, deactivate_reminder

logger = logging.getLogger(__name__)

REMINDER_CONFIG = {
    'disboard': {
        'bot_id': 302050872383242240,
        'cooltime': 7200,  # 2시간
        'keyword': "表示順をアップしたにゃ！",
        'command': "/bump",
        'name': "Disboard BUMP"
    },
    'dissoku': {
        'bot_id': 603613388292390912,
        'cooltime': 3600,  # 1시간
        'keyword': "サーバーの表示順位をアップしました",
        'command': "/up",
        'name': "Dissoku UP"
    }
}

class Reminder(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.configs: Dict[str, Dict] = {}
        logger.info("Reminder Cog가 성공적으로 초기화되었습니다.")
        # [수정] cog_load 대신 __init__에서 루프 시작
        self.check_reminders.start()

    # [수정] cog_load는 설정 로드만 담당
    async def cog_load(self):
        await self.load_configs()
    
    def cog_unload(self):
        """Cog가 언로드될 때 루프를 안전하게 중지합니다."""
        self.check_reminders.cancel()

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
                # [수정] asyncio.sleep 대신 DB에 예약
                await self.schedule_new_reminder(key, message.guild)
                break

    async def schedule_new_reminder(self, reminder_type: str, guild: discord.Guild):
        """DB에 새로운 알림을 예약합니다."""
        # 설정이 되어있는지 확인
        if not self.configs.get(reminder_type) or not self.configs[reminder_type].get('channel_id') or not self.configs[reminder_type].get('role_id'):
            return

        config = REMINDER_CONFIG[reminder_type]
        remind_at_time = datetime.now(timezone.utc) + timedelta(seconds=config['cooltime'])
        
        await schedule_reminder(guild.id, reminder_type, remind_at_time)
        logger.info(f"✅ [{guild.name}] 서버의 {config['name']} 알림을 DB에 예약했습니다. (예약 시간: {remind_at_time.strftime('%Y-%m-%d %H:%M:%S')})")

    # [추가] DB를 주기적으로 확인하는 백그라운드 루프
    @tasks.loop(seconds=10.0)
    async def check_reminders(self):
        try:
            due_reminders = await get_due_reminders()
            if not due_reminders:
                return

            logger.info(f"{len(due_reminders)}개의 만료된 알림을 찾았습니다. 전송을 시작합니다.")

            for reminder in due_reminders:
                guild = self.bot.get_guild(reminder['guild_id'])
                if not guild:
                    logger.warning(f"알림(ID: {reminder['id']})의 서버(ID: {reminder['guild_id']})를 찾을 수 없어 비활성화합니다.")
                    await deactivate_reminder(reminder['id'])
                    continue

                reminder_type = reminder['reminder_type']
                config = REMINDER_CONFIG.get(reminder_type)
                reminder_settings = self.configs.get(reminder_type)

                if not config or not reminder_settings:
                    logger.warning(f"알림(ID: {reminder['id']})의 타입({reminder_type})이 유효하지 않아 비활성화합니다.")
                    await deactivate_reminder(reminder['id'])
                    continue
                
                channel = guild.get_channel(reminder_settings['channel_id'])
                role = guild.get_role(reminder_settings['role_id'])

                if not channel or not role:
                    logger.warning(f"{reminder_type} 알림(ID: {reminder['id']})에 필요한 채널/역할을 찾을 수 없어 비활성화합니다.")
                    await deactivate_reminder(reminder['id'])
                    continue

                try:
                    message = f"⏰ {role.mention} {config['name']} の時間です！ `{config['command']}` をお願いします！"
                    await channel.send(message)
                    logger.info(f"✅ [{guild.name}] 서버에 {config['name']} 알림을 보냈습니다. (ID: {reminder['id']})")
                except discord.Forbidden:
                    logger.error(f"채널(ID: {channel.id})에 메시지를 보낼 권한이 없습니다.")
                except Exception as e:
                    logger.error(f"알림 메시지 전송 중 오류 발생: {e}", exc_info=True)
                finally:
                    # 성공하든 실패하든, 다시 보내지 않도록 비활성화
                    await deactivate_reminder(reminder['id'])
        
        except Exception as e:
            logger.error(f"알림 확인 루프 중 오류 발생: {e}", exc_info=True)

    @check_reminders.before_loop
    async def before_check_reminders(self):
        """봇이 준비될 때까지 루프 시작을 기다립니다."""
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(Reminder(bot))
