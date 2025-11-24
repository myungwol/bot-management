# cogs/server/reminder.py

import discord
from discord.ext import commands, tasks
import asyncio
import logging
from typing import Optional, Dict
from datetime import datetime, timedelta, timezone
import re

from utils.database import get_id, schedule_reminder, get_due_reminders, deactivate_reminder, get_embed_from_db, supabase, set_reminder_message_id
from utils.helpers import format_embed_from_db

logger = logging.getLogger(__name__)

REMINDER_CONFIG = {
    'disboard': {
        'bot_id': 302050872383242240, 'cooltime': 7200, 'keyword': "서버 갱신 완료!",
        'command': "/bump", 'name': "Disboard BUMP", 'confirmation_embed_key': "embed_reminder_confirmation_disboard"
    },
    'dicoall': {
        'bot_id': 664647740877176832, 'cooltime': 3600, 'keyword': "서버가 상단에 표시되었습니다.",
        'command': "/up", 'name': "Dicoall UP", 'confirmation_embed_key': "embed_reminder_confirmation_dicoall"
    }
}

class Reminder(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.configs: Dict[str, Dict] = {}
        logger.info("Reminder Cog가 성공적으로 초기화되었습니다.")
        self.check_reminders.start()

    async def cog_load(self):
        # on_ready에서 load_configs를 호출하므로 여기서 호출할 필요가 없습니다.
        pass
    
    def cog_unload(self):
        self.check_reminders.cancel()

    async def load_configs(self):
        # ▼▼▼ [핵심 수정] 키 이름을 system.py의 설정 명령어와 일치시켰습니다. ▼▼▼
        self.configs['disboard'] = {
            'channel_id': get_id("bump_reminder_channel_id"), 
            'role_id': get_id("bump_reminder_role_id")  # 기존: role_notify_disboard -> 수정: bump_reminder_role_id
        }
        self.configs['dicoall'] = {
            'channel_id': get_id("dicoall_reminder_channel_id"), 
            'role_id': get_id("dicoall_reminder_role_id") # 기존: role_notify_up -> 수정: dicoall_reminder_role_id
        }
        # ▲▲▲ [수정 완료] ▲▲▲
        logger.info(f"[Reminder] 설정 로드 완료: {self.configs}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not self.bot.is_ready() or message.guild is None or not message.embeds or not message.embeds[0].description:
            return

        embed_description = message.embeds[0].description

        for key, config in REMINDER_CONFIG.items():
            if message.author.id == config['bot_id'] and config['keyword'] in embed_description:
                
                try:
                    response = await supabase.table('reminders').select('reminder_message_id') \
                        .eq('guild_id', message.guild.id) \
                        .eq('reminder_type', key) \
                        .not_.is_('reminder_message_id', 'null') \
                        .order('created_at', desc=True).limit(1).execute()
                    
                    if response and response.data:
                        record = response.data[0]
                        if msg_id := record.get('reminder_message_id'):
                            original_reminder_msg = await message.channel.fetch_message(msg_id)
                            await original_reminder_msg.delete()
                except discord.NotFound:
                    pass 
                except Exception as e:
                    logger.warning(f"이전 알림 메시지 삭제 중 오류: {e}")
                
                user_mention = self.find_user_mention_in_embed(embed_description)
                confirmation_msg = await self.send_confirmation_message(key, config.get('confirmation_embed_key'), message.channel, user_mention)
                confirmation_msg_id = confirmation_msg.id if confirmation_msg else None
                await self.schedule_new_reminder(key, message.guild, confirmation_msg_id)
                break

    def find_user_mention_in_embed(self, description: str) -> str:
        match = re.search(r'<@!?(\d+)>', description)
        return match.group(0) if match else "누군가"

    async def send_confirmation_message(self, reminder_type: str, embed_key: str, channel: discord.TextChannel, user_mention: str) -> Optional[discord.Message]:
        if not embed_key: return None
        embed_data = await get_embed_from_db(embed_key)
        if not embed_data: return None
        reminder_name = REMINDER_CONFIG.get(reminder_type, {}).get("name", "알 수 없는 작업")
        embed = format_embed_from_db(embed_data, user_mention=user_mention, reminder_name=reminder_name)
        try:
            return await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"확인 메시지 전송 중 오류: {e}", exc_info=True)
            return None

    async def schedule_new_reminder(self, reminder_type: str, guild: discord.Guild, confirmation_message_id: Optional[int] = None):
        config = REMINDER_CONFIG[reminder_type]
        remind_at_time = datetime.now(timezone.utc) + timedelta(seconds=config['cooltime'])
        await schedule_reminder(guild.id, reminder_type, remind_at_time, confirmation_message_id)
        logger.info(f"✅ [{guild.name}] 서버의 {config['name']} 알림을 DB에 예약했습니다. (예약 시간: {remind_at_time.strftime('%Y-%m-%d %H:%M:%S')})")

    @tasks.loop(seconds=10.0)
    async def check_reminders(self):
        try:
            due_reminders = await get_due_reminders()
            if not due_reminders: return

            for reminder in due_reminders:
                guild = self.bot.get_guild(reminder['guild_id'])
                if not guild:
                    await deactivate_reminder(reminder['id']); continue

                reminder_type = reminder['reminder_type']
                config = REMINDER_CONFIG.get(reminder_type)
                reminder_settings = self.configs.get(reminder_type)

                # 설정값 검증 강화 및 로그 추가
                if not config:
                    logger.warning(f"알림 타입 '{reminder_type}'에 대한 내부 설정(REMINDER_CONFIG)이 없습니다.")
                    await deactivate_reminder(reminder['id']); continue
                
                if not reminder_settings:
                    logger.warning(f"알림 타입 '{reminder_type}'에 대한 서버 설정(self.configs)이 로드되지 않았습니다.")
                    await deactivate_reminder(reminder['id']); continue

                channel_id = reminder_settings.get('channel_id')
                role_id = reminder_settings.get('role_id')

                if not channel_id or not role_id:
                    logger.warning(f"'{reminder_type}' 알림을 위한 채널 ID 또는 역할 ID가 설정되지 않았습니다. (Ch: {channel_id}, Role: {role_id})")
                    await deactivate_reminder(reminder['id']); continue
                
                channel = guild.get_channel(channel_id)
                role = guild.get_role(role_id)
                
                if not channel:
                    logger.warning(f"설정된 알림 채널(ID: {channel_id})을 찾을 수 없습니다.")
                    await deactivate_reminder(reminder['id']); continue
                if not role:
                    logger.warning(f"설정된 알림 역할(ID: {role_id})을 찾을 수 없습니다.")
                    await deactivate_reminder(reminder['id']); continue

                if confirmation_msg_id := reminder.get('confirmation_message_id'):
                    try:
                        old_confirmation_msg = await channel.fetch_message(confirmation_msg_id)
                        await old_confirmation_msg.delete()
                    except discord.NotFound: pass
                    except Exception as e: logger.error(f"이전 확인 메시지(ID: {confirmation_msg_id}) 삭제 중 오류 발생: {e}", exc_info=True)

                try:
                    embed_key = f"embed_reminder_{reminder_type}"
                    embed_data = await get_embed_from_db(embed_key)
                    if embed_data:
                        embed = format_embed_from_db(embed_data)
                        reminder_msg = await channel.send(content=role.mention, embed=embed, allowed_mentions=discord.AllowedMentions(roles=True))
                        await set_reminder_message_id(reminder['id'], reminder_msg.id)
                        logger.info(f"✅ [{guild.name}] 서버에 {config['name']} 알림을 보냈습니다. (ID: {reminder['id']}, MsgID: {reminder_msg.id})")
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
