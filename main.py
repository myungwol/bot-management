
# main.py (패널 자동 재생성 기능이 포함된 최종 안정화 버전)

import discord
from discord.ext import commands
import os
import asyncio
import logging

# [수정] 봇 재시작 시 View 복구에 필요한 올바른 함수와 변수를 임포트합니다.
from cogs.server.system import AutoRoleView, STATIC_AUTO_ROLE_PANELS
from utils.database import get_panel_id, get_all_channel_configs

# 로깅 기본 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 봇 기본 설정 ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True # 음성 활동 보상을 위해 추가

class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 모든 채널 설정을 봇 전체에서 접근 가능하도록 캐시할 딕셔너리
        self.channel_configs = {}

    async def setup_hook(self):
        """ 봇이 시작될 때 역할 패널의 View를 다시 로드합니다. """
        logger.info("------ [ 역할 패널 View 재등록 시작 ] ------")
        for panel_key, panel_config in STATIC_AUTO_ROLE_PANELS.items():
            try:
                panel_info = await get_panel_id(panel_key)
                if panel_info and panel_info.get('message_id'):
                    # system.py의 AutoRoleView는 panel_config 전체를 필요로 합니다.
                    view = AutoRoleView(panel_config)
                    self.add_view(view, message_id=panel_info['message_id'])
                    logger.info(f"✅ 역할 패널 View 재등록 성공: '{panel_key}' (ID: {panel_info['message_id']})")
            except Exception as e:
                logger.error(f"❌ '{panel_key}' View 재등록 중 오류: {e}")
        logger.info("------ [ 역할 패널 View 재등록 완료 ] ------")

bot = MyBot(command_prefix="/", intents=intents)

# [복구 및 개선] 봇이 준비되었을 때 모든 패널을 자동으로 재생성하는 함수
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
        # asyncio.gather를 사용하여 모든 패널 재생성 작업을 동시에 실행합니다.
        results = await asyncio.gather(*panel_tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # 어떤 작업에서 오류가 발생했는지 추적하기 위해 더 자세히 로깅할 수 있습니다.
                logger.error(f"❌ 패널 재생성 작업 중 오류 발생: {result}", exc_info=result)
    else:
        logger.info("ℹ️ 재생성할 패널 작업이 없습니다.")
        
    logger.info("------ [ 모든 패널 자동 재생성 완료 ] ------")

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
    
    # DB에서 모든 채널 설정을 한 번만 가져와 봇의 변수에 저장합니다.
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
        try:
            asyncio.run(main())
        except discord.errors.LoginFailure:
            logger.critical("❌ 봇 토큰이 잘못되었습니다. BOT_TOKEN 환경 변수를 확인해주세요.")
        except Exception as e:
            logger.critical(f"🚨 봇 실행 중 치명적인 오류 발생: {e}", exc_info=True)
