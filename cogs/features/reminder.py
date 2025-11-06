# cogs/server/reminder.py

import discord
from discord.ext import commands, tasks
import asyncio
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta, timezone

from utils.database import get_id, schedule_reminder, get_due_reminders, deactivate_reminder

logger = logging.getLogger(__name__)

REMINDER_CONFIG = {
    'disboard': {
        'bot_id': 302050872383242240,
        'cooltime': 7200,  # 2시간
        'keyword': "서버 갱신 완료!", # Disboard는 그대로 유지
        'command': "/bump",
        'name': "Disboard BUMP"
    },
    # ▼▼▼ [핵심 수정] dissoku 부분을 dicoall 정보로 변경 ▼▼▼
    'dicoall': {
        'bot_id': 664647740877176832, # Dicoall 봇 ID
        'cooltime': 3600,  # 1시간
        'keyword': "서버가 상단에 표시되었습니다. 🎉", # Dicoall의 응답 메시지 키워드
        'command': "/up",
        'name': "Dicoall UP" # 사용자에게 보여질 이름
    }
    # ▲▲▲ [핵심 수정] 종료 ▲▲▲
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
        self.configs['disboard'] = {
            'channel_id': get_id("bump_reminder_channel_id"),
            'role_id': get_id("bump_reminder_role_id")
        }
        # [수정] dissoku -> dicoall
        self.configs['dicoall'] = {
            'channel_id': get_id("dicoall_reminder_channel_id"),
            'role_id': get_id("dicoall_reminder_role_id")
        }
        logger.info(f"[Reminder] 설정 로드 완료: {self.configs}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self.bot.is_ready() or message.guild is None or not message.embeds:
            return

        # [안정성 강화] 임베드가 비어있을 경우를 대비
        if not message.embeds[0].description:
            return

        embed_description = message.embeds[0].description

        for key, config in REMINDER_CONFIG.items():
            # [안정성 강화] 봇 ID가 일치하는지 먼저 확인
            if message.author.id == config['bot_id'] and config['keyword'] in embed_description:
                await self.schedule_new_reminder(key, message.guild)
                break

    async def schedule_new_reminder(self, reminder_type: str, guild: discord.Guild):
        if not self.configs.get(reminder_type) or not self.configs[reminder_type].get('channel_id') or not self.configs[reminder_type].get('role_id'):
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
                    message = f"⏰ {role.mention} {config['name']} 시간입니다! `{config['command']}`를 입력해주세요!"
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
    await bot.add_cog(Reminder(bot))
