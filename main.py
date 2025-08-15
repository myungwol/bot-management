# main.py (DB 자동 로딩 기능이 적용된 최종 안정화 버전)

import discord
from discord.ext import commands
import os
import asyncio
import logging

# [수정] 새로운 DB 자동 로딩 함수 임포트
from cogs.server.system import AutoRoleView, STATIC_AUTO_ROLE_PANELS
from utils.database import get_panel_id, load_all_configs_from_db, get_id

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
        # [삭제] 이제 channel_configs는 utils/database.py의 _cached_ids가 대체합니다.
        # self.channel_configs = {}

    async def setup_hook(self):
        """ 봇이 시작될 때 역할 패널의 View를 다시 로드합니다. """
        # [수정] Cog 로딩 이후에 설정값이 로드되므로 on_ready에서 처리하도록 로직 이동
        pass

bot = MyBot(command_prefix="/", intents=intents)

# [복구 및 개선] 봇이 준비되었을 때 모든 패널을 자동으로 재생성하는 함수
async def regenerate_all_panels():
    logger.info("------ [ 모든 패널 자동 재생성 시작 ] ------")
    panel_tasks = []
    
    for cog_name, cog in bot.cogs.items():
        if hasattr(cog, 'regenerate_panel'):
            try:
                panel_tasks.append(cog.regenerate_panel())
                logger.info(f"🔄 '{cog_name}'의 패널 재생성 작업을 준비합니다.")
            except Exception as e:
                logger.error(f"❌ '{cog_name}'의 패널 재생성 준비 중 오류 발생: {e}")

    if panel_tasks:
        results = await asyncio.gather(*panel_tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ 패널 재생성 작업 중 오류 발생: {result}", exc_info=result)
    else:
        logger.info("ℹ️ 재생성할 패널 작업이 없습니다.")
        
    logger.info("------ [ 모든 패널 자동 재생성 완료 ] ------")

@bot.event
async def on_ready():
    logger.info(f'✅ {bot.user.name}(이)가 성공적으로 로그인했습니다.')
    logger.info(f'✅ 봇 ID: {bot.user.id}')
    logger.info('------')

    # [수정] 1. DB에서 모든 역할/채널 ID를 불러와 캐시에 저장합니다. (가장 먼저 실행)
    await load_all_configs_from_db()

    try:
        synced = await bot.tree.sync()
        logger.info(f'✅ {len(synced)}개의 슬래시 명령어를 성공적으로 동기화했습니다.')
    except Exception as e:
        logger.error(f'❌ 명령어 동기화 중 오류가 발생했습니다: {e}')
    
    # [수정] 2. 봇이 준비되면, 패널 자동 재생성 함수를 호출합니다.
    await regenerate_all_panels()

    # [수정] 3. View 재등록 로직을 on_ready로 이동 (모든 설정 로드 이후)
    logger.info("------ [ 역할 패널 View 재등록 시작 ] ------")
    # panel_data 테이블 대신 channel_configs 테이블에서 직접 message_id를 찾습니다.
    for panel_key, panel_config in STATIC_AUTO_ROLE_PANELS.items():
        try:
            # get_panel_id 대신 새로운 get_id 함수 사용
            message_id = get_id(f"panel_{panel_key}_message_id")
            if message_id:
                view = AutoRoleView(panel_config)
                bot.add_view(view, message_id=message_id)
                logger.info(f"✅ 역할 패널 View 재등록 성공: '{panel_key}' (ID: {message_id})")
        except Exception as e:
            logger.error(f"❌ '{panel_key}' View 재등록 중 오류: {e}")
    logger.info("------ [ 역할 패널 View 재등록 완료 ] ------")


async def load_extensions():
    logger.info("------ [ Cog 로드 시작 ] ------")
    cogs_dir = './cogs'
    if not os.path.exists(cogs_dir):
        logger.error(f"Cogs directory not found at {cogs_dir}")
        return
        
    for folder in os.listdir(cogs_dir):
        folder_path = os.path.join(cogs_dir, folder)
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
        # [수정] 봇 시작 전에 Cog를 먼저 로드해야 on_ready에서 cogs 목록을 순회할 수 있습니다.
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
