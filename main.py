# main.py (패널 자동 재생성 기능 복구 최종본)

import discord
from discord.ext import commands
import os
import asyncio
import logging

# [수정] 봇 재시작 시 View 복구에 필요한 부분만 임포트
from cogs.server.system import AutoRoleView, STATIC_AUTO_ROLE_PANELS
from utils.database import get_panel_id, get_all_channel_configs

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 모든 채널 설정을 캐시할 딕셔너리
        self.channel_configs = {}

    async def setup_hook(self):
        logger.info("------ [ 역할 패널 View 재등록 시작 ] ------")
        for panel_key, panel_config in STATIC_AUTO_ROLE_PANELS.items():
            try:
                panel_info = await get_panel_id(panel_key)
                if panel_info and panel_info.get('message_id'):
                    view = AutoRoleView(panel_config)
                    self.add_view(view, message_id=panel_info['message_id'])
                    logger.info(f"✅ 역할 패널 View 재등록 성공: '{panel_key}'")
            except Exception as e:
                logger.error(f"❌ '{panel_key}' View 재등록 중 오류: {e}")
        logger.info("------ [ 역할 패널 View 재등록 완료 ] ------")

bot = MyBot(command_prefix="/", intents=intents)

# [복구] 봇이 준비되었을 때 모든 패널을 자동으로 재생성하는 함수
async def regenerate_all_panels():
    logger.info("------ [ 모든 패널 자동 재생성 시작 ] ------")
    panel_tasks = []
    
    # 봇에 로드된 모든 Cog를 순회합니다.
    for cog_name, cog in bot.cogs.items():
        # 만약 Cog에 'regenerate_panel' 이라는 이름의 함수가 있다면, 실행 대상으로 간주합니다.
        if hasattr(cog, 'regenerate_panel'):
            try:
                # 'regenerate_panel' 함수를 비동기 태스크 목록에 추가합니다.
                panel_tasks.append(cog.regenerate_panel())
                logger.info(f"🔄 '{cog_name}'의 패널 재생성 작업을 준비합니다.")
            except Exception as e:
                logger.error(f"❌ '{cog_name}'의 패널 재생성 준비 중 오류 발생: {e}")

    if panel_tasks:
        # asyncio.gather를 사용하여 모든 패널 재생성 작업을 동시에 실행
        results = await asyncio.gather(*panel_tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"❌ 패널 재생성 작업 중 오류 발생: {result}", exc_info=result)
    else:
        logger.info("ℹ️ 재생성할 패널 작업이 없습니다.")
        
    logger.info("------ [ 모든 패널 자동 재생성 완료 ] ------")

@bot.event
async def on_ready():
    logger.info(f'✅ {bot.user.name} 로그인 성공')
    logger.info(f'✅ 봇 ID: {bot.user.id}')
    try:
        synced = await bot.tree.sync()
        logger.info(f'✅ {len(synced)}개의 슬래시 명령어 동기화 완료')
    except Exception as e:
        logger.error(f'❌ 명령어 동기화 오류: {e}')
    
    # DB에서 모든 채널 설정을 한 번만 가져와 봇의 변수에 저장
    bot.channel_configs = await get_all_channel_configs()
    logger.info("✅ 모든 채널 설정 캐시 완료.")

    # [복구] 봇이 준비되면, 패널 자동 재생성 함수를 호출합니다.
    await regenerate_all_panels()

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
                        logger.error(f'❌ Cog 로드 실패: {folder}/{filename} | {e}', exc_info=True)
    logger.info("------ [ Cog 로드 완료 ] ------")

async def main():
    async with bot:
        await load_extensions()
        await bot.start(BOT_TOKEN)

if __name__ == "__main__":
    if BOT_TOKEN is None:
        logger.critical("❌ BOT_TOKEN 환경 변수가 설정되지 않았습니다.")
    else:
        asyncio.run(main())
