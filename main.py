# main.py (setup_hook 수정 최종본)

import discord
from discord.ext import commands
import os
import asyncio
import logging

# [수정] 새로운 setup_hook에 필요한 올바른 함수와 변수를 임포트합니다.
from cogs.server.system import AutoRoleView, STATIC_AUTO_ROLE_PANELS
from utils.database import (get_all_channel_configs, get_panel_id)

# 로깅 기본 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 봇 기본 설정 ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.message_content = True

class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        """ [변경] 봇이 시작될 때 새로운 방식의 View를 올바르게 다시 로드합니다. """
        logger.info("------ [ 역할 패널 View 재등록 시작 ] ------")
        
        # 1. 코드에 정의된 모든 패널 설정을 반복합니다.
        for panel_key, panel_config in STATIC_AUTO_ROLE_PANELS.items():
            try:
                # 2. DB에서 해당 패널의 메시지 ID를 찾습니다.
                panel_info = await get_panel_id(panel_key)
                if panel_info and panel_info.get('message_id'):
                    # 3. 새로운 방식에 맞게 View를 생성합니다. (전체 설정을 넘겨줍니다)
                    view = AutoRoleView(panel_config)
                    # 4. 해당 메시지 ID에 View를 다시 연결합니다.
                    self.add_view(view, message_id=panel_info['message_id'])
                    logger.info(f"✅ 역할 패널 View 재등록 성공: '{panel_key}' (ID: {panel_info['message_id']})")
            except Exception as e:
                logger.error(f"❌ 역할 패널 '{panel_key}' View 재등록 중 오류: {e}")
        
        logger.info("------ [ 역할 패널 View 재등록 완료 ] ------")

bot = MyBot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
    logger.info(f'✅ {bot.user.name}(이)가 성공적으로 로그인했습니다.')
    logger.info(f'✅ 봇 ID: {bot.user.id}')
    logger.info('------')
    try:
        synced = await bot.tree.sync()
        logger.info(f'✅ {len(synced)}개의 슬래시 명령어를 성공적으로 동기화했습니다.')
    except Exception as e:
        logger.error(f'❌ 명령어 동기화 중 오류가 발생했습니다: {e}')

    await get_all_channel_configs()
    logger.info("✅ 모든 채널 설정이 캐시되었습니다.")

async def load_extensions():
    logger.info("------ [ Cog 로드 시작 ] ------")
    for folder in os.listdir('./cogs'):
        folder_path = os.path.join('cogs', folder)
        if os.path.isdir(folder_path):
            for filename in os.listdir(folder_path):
                if filename.endswith('.py') and not filename.startswith('__'):
                    try:
                        await bot.load_extension(f'cogs.{folder}.{filename[:-3]}')
                        logger.info(f'✅ Cog 로드 성공: {folder}/{filename}')
                    except Exception as e:
                        logger.error(f'❌ Cog 로드 실패: {folder}/{filename} | 오류: {e}', exc_info=True)
    logger.info("------ [ Cog 로드 완료 ] ------")

async def main():
    async with bot:
        await load_extensions()
        await bot.start(BOT_TOKEN)

if __name__ == "__main__":
    try:
        if BOT_TOKEN is None:
            logger.critical("❌ BOT_TOKEN 환경 변수가 설정되지 않았습니다.")
        else:
            asyncio.run(main())
    except discord.errors.LoginFailure:
        logger.critical("❌ 봇 토큰이 잘못되었습니다. BOT_TOKEN 환경 변수를 확인해주세요.")
    except Exception as e:
        logger.critical(f"🚨 봇 실행 중 치명적인 오류 발생: {e}", exc_info=True)
