# cogs/features/reminder.py

import discord
from discord.ext import commands, tasks
import logging
from typing import Dict
from datetime import datetime, timedelta, timezone

from utils.database import get_id, schedule_reminder, get_due_reminders, deactivate_reminder

logger = logging.getLogger(__name__)

REMINDER_CONFIG = {
    'disboard': {
        'bot_id': 302050872383242240,
        'cooltime': 7200,
        'keyword': "表示順をアップしたよ",
        'command': "/bump",
        'name': "Disboard BUMP"
    },
    'dicoall': {
        'bot_id': 903541413298450462,
        'cooltime': 3600,
        'keyword': "サーバーが上位に表示されました。",
        'command': "/up",
        'name': "Dicoall UP"
    },
    'dissoku': {
        'bot_id': 761562078095867916,
        'cooltime': 7200,
        'keyword': "をアップしたよ!",
        'command': "/up",
        'name': "ディス速 UP"
    }
}

class Reminder(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.configs: Dict[str, Dict] = {}
        logger.info("Reminder Cog가 성공적으로 초기화되었습니다.")
        self.check_reminders.start()

    async def cog_load(self):
        await self.load_configs()
    
    def cog_unload(self):
        self.check_reminders.cancel()

    async def load_configs(self):
        # get_id 함수는 동기 함수이므로 await를 사용하지 않습니다.
        self.configs['disboard'] = {
            'channel_id': get_id("bump_reminder_channel_id"),
            'role_id': get_id("bump_reminder_role_id")
        }
        self.configs['dicoall'] = {
            'channel_id': get_id("dicoall_reminder_channel_id"),
            'role_id': get_id("dicoall_reminder_role_id")
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

        embed = message.embeds[0]
        
        full_embed_text_parts = []
        if embed.title:
            full_embed_text_parts.append(embed.title)
        if embed.description:
            full_embed_text_parts.append(embed.description)
        for field in embed.fields:
            if field.name:
                full_embed_text_parts.append(field.name)
            if field.value:
                full_embed_text_parts.append(field.value)
        
        full_embed_text = "\n".join(full_embed_text_parts)

        for key, config in REMINDER_CONFIG.items():
            if message.author.id == config['bot_id'] and config['keyword'] in full_embed_text:
                await self.schedule_new_reminder(key, message.guild)
                logger.info(f"[{message.guild.name}] 서버에서 '{config['name']}' 키워드를 감지했습니다. 알림 예약을 시작합니다.")
                break
                
    async def schedule_new_reminder(self, reminder_type: str, guild: discord.Guild):
        if not self.configs.get(reminder_type) or not self.configs[reminder_type].get('channel_id') or not self.configs[reminder_type].get('role_id'):
            logger.warning(f"[{guild.name}] 서버의 {reminder_type} 알림 설정(채널/역할 ID)이 로드되지 않아 스케줄링을 건너뜁니다.")
            return

        config = REMINDER_CONFIG[reminder_type]
        remind_at_time = datetime.now(timezone.utc) + timedelta(seconds=config['cooltime'])
        
        await schedule_reminder(guild.id, reminder_type, remind_at_time)
        logger.info(f"✅ [{guild.name}] 서버의 {config['name']} 알림을 DB에 예약했습니다. (예약 시간: {remind_at_time.strftime('%Y-%m-%d %H:%M:%S')})")

    @tasks.loop(seconds=10.0)
    async def check_reminders(self):
        try:
            due_reminders = await get_due_reminders()
            if not due_reminders:
                return

            for reminder in due_reminders:
                guild = self.bot.get_guild(reminder['guild_id'])
                if not guild:
                    logger.warning(f"알림(ID: {reminder['id']})의 서버(ID: {reminder['guild_id']})를 찾을 수 없어 비활성화합니다.")
                    await deactivate_reminder(reminder['id'])
                    continue

                reminder_type = reminder['reminder_type']
                config = REMINDER_CONFIG.get(reminder_type)
                reminder_settings = self.configs.get(reminder_type)

                if not config or not reminder_settings or not reminder_settings.get('channel_id') or not reminder_settings.get('role_id'):
                    logger.warning(f"알림(ID: {reminder['id']})의 타입({reminder_type})이 유효하지 않거나 설정이 없어 비활성화합니다.")
                    await deactivate_reminder(reminder['id'])
                    continue
                
                channel = guild.get_channel(reminder_settings['channel_id'])
                role = guild.get_role(reminder_settings['role_id'])

                if not channel or not role:
                    logger.warning(f"{reminder_type} 알림(ID: {reminder['id']})에 필요한 채널/역할을 찾을 수 없어 비활성화합니다.")
                    await deactivate_reminder(reminder['id'])
                    continue

                try:
                    message = f"⏰ {role.mention} {config['name']} の時間です！ `{config['command']}` を入力してください！"
                    await channel.send(message, allowed_mentions=discord.AllowedMentions(roles=True))
                    logger.info(f"✅ [{guild.name}] 서버에 {config['name']} 알림을 보냈습니다. (ID: {reminder['id']})")
                except discord.Forbidden:
                    logger.error(f"채널(ID: {channel.id})에 메시지를 보낼 권한이 없습니다.")
                except Exception as e:
                    logger.error(f"알림 메시지 전송 중 오류 발생: {e}", exc_info=True)
                finally:
                    await deactivate_reminder(reminder['id'])
        
        except Exception as e:
            logger.error(f"알림 확인 루프 중 오류 발생: {e}", exc_info=True)

    @check_reminders.before_loop
    async def before_check_reminders(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    cog = Reminder(bot)
    await bot.add_cog(cog)
