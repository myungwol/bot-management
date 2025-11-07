# cogs/server/reminder.py

import discord
from discord.ext import commands, tasks
import asyncio
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta, timezone
import re

from utils.database import get_id, schedule_reminder, get_due_reminders, deactivate_reminder, get_embed_from_db
from utils.helpers import format_embed_from_db

logger = logging.getLogger(__name__)

REMINDER_CONFIG = {
    'disboard': {
        'bot_id': 302050872383242240,
        'cooltime': 7200,
        'keyword': "서버 갱신 완료!",
        'command': "/bump",
        'name': "Disboard BUMP",
        'confirmation_embed_key': "embed_reminder_confirmation_disboard" # [추가] Disboard 전용 확인 임베드 키
    },
    'dicoall': {
        'bot_id': 664647740877176832,
        'cooltime': 3600,
        'keyword': "서버가 상단에 표시되었습니다.",
        'command': "/up",
        'name': "Dicoall UP",
        'confirmation_embed_key': "embed_reminder_confirmation_dicoall" # [추가] Dicoall 전용 확인 임베드 키
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
        self.configs['disboard'] = {
            'channel_id': get_id("bump_reminder_channel_id"),
            'role_id': get_id("role_notify_disboard")
        }
        self.configs['dicoall'] = {
            'channel_id': get_id("dicoall_reminder_channel_id"),
            'role_id': get_id("role_notify_up")
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
                # 1. 기존 알림 메시지 삭제
                if (channel_id := self.configs.get(key, {}).get('channel_id')) and (channel := self.bot.get_channel(channel_id)):
                    try:
                        async for old_msg in channel.history(limit=50):
                            if old_msg.author.id == self.bot.user.id and old_msg.embeds:
                                embed_title = old_msg.embeds[0].title or ""
                                if config['name'].split(' ')[0] in embed_title:
                                    await old_msg.delete()
                                    break
                    except Exception as e:
                        logger.warning(f"이전 알림 메시지 삭제 중 오류: {e}")

                # 2. 확인 메시지 전송
                user_mention = self.find_user_mention_in_embed(embed_description)
                # [수정] 설정에 정의된 전용 임베드 키를 사용
                confirmation_embed_key = config.get('confirmation_embed_key')
                if confirmation_embed_key:
                    await self.send_confirmation_message(key, confirmation_embed_key, message.channel, user_mention)

                # 3. 다음 알림 예약
                await self.schedule_new_reminder(key, message.guild)
                break

    def find_user_mention_in_embed(self, description: str) -> str:
        match = re.search(r'<@!?(\d+)>', description)
        return match.group(0) if match else "누군가"

    # [수정] 함수 인자에 embed_key 추가
    async def send_confirmation_message(self, reminder_type: str, embed_key: str, channel: discord.TextChannel, user_mention: str):
        embed_data = await get_embed_from_db(embed_key)
        if not embed_data: return

        reminder_name = REMINDER_CONFIG.get(reminder_type, {}).get("name", "알 수 없는 작업")
        embed = format_embed_from_db(embed_data, user_mention=user_mention, reminder_name=reminder_name)
        
        try:
            confirmation_msg = await channel.send(embed=embed)
            await asyncio.sleep(60)
            await confirmation_msg.delete()
        except discord.NotFound:
            pass
        except Exception as e:
            logger.error(f"확인 메시지 전송/삭제 중 오류: {e}", exc_info=True)

    async def schedule_new_reminder(self, reminder_type: str, guild: discord.Guild):
        config = REMINDER_CONFIG[reminder_type]
        remind_at_time = datetime.now(timezone.utc) + timedelta(seconds=config['cooltime'])
        await schedule_reminder(guild.id, reminder_type, remind_at_time)
        logger.info(f"✅ [{guild.name}] 서버의 {config['name']} 알림을 DB에 예약했습니다. (예약 시간: {remind_at_time.strftime('%Y-%m-%d %H:%M:%S')})")

    @tasks.loop(seconds=10.0)
    async def check_reminders(self):
        try:
            due_reminders = await get_due_reminders()
            if not due_reminders: return

            for reminder in due_reminders:
                guild = self.bot.get_guild(reminder['guild_id'])
                if not guild:
                    await deactivate_reminder(reminder['id'])
                    continue

                reminder_type = reminder['reminder_type']
                config = REMINDER_CONFIG.get(reminder_type)
                reminder_settings = self.configs.get(reminder_type)

                if not config or not reminder_settings or not reminder_settings.get('channel_id') or not reminder_settings.get('role_id'):
                    await deactivate_reminder(reminder['id'])
                    continue
                
                channel = guild.get_channel(reminder_settings['channel_id'])
                role = guild.get_role(reminder_settings['role_id'])
                if not channel or not role:
                    await deactivate_reminder(reminder['id'])
                    continue

                try:
                    embed_key = f"embed_reminder_{reminder_type}"
                    embed_data = await get_embed_from_db(embed_key)
                    if embed_data:
                        embed = format_embed_from_db(embed_data)
                        await channel.send(content=role.mention, embed=embed, allowed_mentions=discord.AllowedMentions(roles=True))
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
