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
        'confirmation_embed_key': "embed_reminder_confirmation_disboard"
    },
    'dicoall': {
        'bot_id': 664647740877176832,
        'cooltime': 3600,
        'keyword': "서버가 상단에 표시되었습니다.",
        'command': "/up",
        'name': "Dicoall UP",
        'confirmation_embed_key': "embed_reminder_confirmation_dicoall"
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
                
                # ▼▼▼ [핵심 추가] 이전 알림 메시지를 찾아 삭제하는 로직 ▼▼▼
                try:
                    # 현재 활성화된 알림 중, 방금 보냈던 알림 메시지 ID를 찾습니다.
                    response = await supabase.table('reminders').select('id, reminder_message_id') \
                        .eq('guild_id', message.guild.id) \
                        .eq('reminder_type', key) \
                        .eq('is_active', True) \
                        .not_.is_('reminder_message_id', 'null') \
                        .order('created_at', desc=True).limit(1).single().execute()
                    
                    if response and response.data and (msg_id := response.data.get('reminder_message_id')):
                        original_reminder_msg = await message.channel.fetch_message(msg_id)
                        await original_reminder_msg.delete()
                except discord.NotFound:
                    pass # 이미 삭제된 경우
                except Exception as e:
                    logger.warning(f"이전 알림 메시지(ID: {msg_id}) 삭제 중 오류: {e}")
                # ▲▲▲ [추가 완료] ▲▲▲

                # 1. 확인 메시지 전송 및 ID 저장
                # (기존 코드와 동일)
                user_mention = self.find_user_mention_in_embed(embed_description)
                confirmation_embed_key = config.get('confirmation_embed_key')
                confirmation_msg = None
                if confirmation_embed_key:
                    confirmation_msg = await self.send_confirmation_message(key, confirmation_embed_key, message.channel, user_mention)

                # 2. 다음 알림 예약 (확인 메시지 ID와 함께)
                # (기존 코드와 동일)
                confirmation_msg_id = confirmation_msg.id if confirmation_msg else None
                await self.schedule_new_reminder(key, message.guild, confirmation_msg_id)
                break

    def find_user_mention_in_embed(self, description: str) -> str:
        match = re.search(r'<@!?(\d+)>', description)
        return match.group(0) if match else "누군가"

    async def send_confirmation_message(self, reminder_type: str, embed_key: str, channel: discord.TextChannel, user_mention: str) -> Optional[discord.Message]:
        embed_data = await get_embed_from_db(embed_key)
        if not embed_data: return None

        reminder_name = REMINDER_CONFIG.get(reminder_type, {}).get("name", "알 수 없는 작업")
        embed = format_embed_from_db(embed_data, user_mention=user_mention, reminder_name=reminder_name)
        
        try:
            # [수정] 메시지를 보내고, 메시지 객체를 반환 (더 이상 여기서 삭제하지 않음)
            confirmation_msg = await channel.send(embed=embed)
            return confirmation_msg
        except Exception as e:
            logger.error(f"확인 메시지 전송 중 오류: {e}", exc_info=True)
            return None

    # [수정] confirmation_message_id 인자 추가
    async def schedule_new_reminder(self, reminder_type: str, guild: discord.Guild, confirmation_message_id: Optional[int] = None):
        config = REMINDER_CONFIG[reminder_type]
        remind_at_time = datetime.now(timezone.utc) + timedelta(seconds=config['cooltime'])
        # [수정] DB에 저장할 때 확인 메시지 ID도 함께 전달
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

                # ▼▼▼ [핵심 수정] 새 알림을 보내기 전, 이전 확인 메시지 삭제 ▼▼▼
                if confirmation_msg_id := reminder.get('confirmation_message_id'):
                    try:
                        # 히스토리에서 메시지를 찾는 대신, ID로 직접 가져와서 삭제
                        old_confirmation_msg = await channel.fetch_message(confirmation_msg_id)
                        await old_confirmation_msg.delete()
                    except discord.NotFound:
                        pass # 이미 삭제된 경우 괜찮음
                    except discord.Forbidden:
                        logger.warning(f"채널(ID: {channel.id})에서 이전 확인 메시지(ID: {confirmation_msg_id})를 삭제할 권한이 없습니다.")
                    except Exception as e:
                        logger.error(f"이전 확인 메시지(ID: {confirmation_msg_id}) 삭제 중 오류 발생: {e}", exc_info=True)
                # ▲▲▲ [핵심 수정] 완료 ▲▲▲

                try:
                    embed_key = f"embed_reminder_{reminder_type}"
                    embed_data = await get_embed_from_db(embed_key)
                    if embed_data:
                        embed = format_embed_from_db(embed_data)
                        
                        # ▼▼▼ [핵심 수정] 메시지를 변수에 저장하고, ID를 DB에 업데이트 ▼▼▼
                        reminder_msg = await channel.send(content=role.mention, embed=embed, allowed_mentions=discord.AllowedMentions(roles=True))
                        
                        # DB에 메시지 ID를 기록
                        await supabase.table('reminders').update({
                            "reminder_message_id": reminder_msg.id
                        }).eq('id', reminder['id']).execute()
                        # ▲▲▲ [수정 완료] ▲▲▲

                        logger.info(f"✅ [{guild.name}] 서버에 {config['name']} 알림을 보냈습니다. (ID: {reminder['id']}, MsgID: {reminder_msg.id})")

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
