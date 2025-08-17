# bot-management/main.py

import discord
from discord.ext import commands
import os
import asyncio
import logging
import logging.handlers
from datetime import datetime, timezone

from utils.database import load_all_data_from_db, sync_defaults_to_db

# --- 중앙 로깅 설정 ---
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] %(message)s')
# 로그 파일 핸들러 추가 (옵션): Production 환경에서 로그를 파일로 저장하고 싶을 때 유용
# file_handler = logging.handlers.RotatingFileHandler(
#     filename='discord_bot.log',
#     encoding='utf-8',
#     maxBytes=32 * 1024 * 1024,  # 32 MiB
#     backupCount=5,  # Rotate through 5 files
# )
# file_handler.setFormatter(log_formatter)
# root_logger = logging.getLogger(); root_logger.setLevel(logging.INFO)
# if root_logger.hasHandlers(): root_logger.handlers.clear()
# root_logger.addHandler(log_handler) # 콘솔 핸들러
# root_logger.addHandler(file_handler) # 파일 핸들러 (선택 사항)

# 단일 StreamHandler 사용 (현재 코드 유지)
log_handler = logging.StreamHandler()
log_handler.setFormatter(log_formatter)
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
if root_logger.hasHandlers():
    root_logger.handlers.clear()
root_logger.addHandler(log_handler)

logging.getLogger('discord').setLevel(logging.WARNING)
logging.getLogger('discord.http').setLevel(logging.WARNING)
logging.getLogger('websockets').setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# --- 환경 변수 및 인텐트 설정 ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
RAW_TEST_GUILD_ID = os.environ.get('TEST_GUILD_ID') # 원본 문자열 ID
TEST_GUILD_ID = None
if RAW_TEST_GUILD_ID:
    try:
        TEST_GUILD_ID = int(RAW_TEST_GUILD_ID)
        logger.info(f"TEST_GUILD_ID가 {TEST_GUILD_ID}로 설정되었습니다.")
    except ValueError:
        logger.error(f"❌ TEST_GUILD_ID 환경 변수가 유효한 숫자가 아닙니다: '{RAW_TEST_GUILD_ID}'")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

# [수정] Railway 재배포를 확실히 하기 위해 버전을 올립니다.
BOT_VERSION = "v1.6-true-final-logic"

# --- 커스텀 봇 클래스 ---
class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        # 영구 View 등록 전에 Cog가 완전히 로드되었는지 확인
        await self.load_all_extensions()

        # register_persistent_views를 가진 Cog만 필터링하여 등록
        cogs_with_persistent_views = ["RolePanel", "Onboarding", "Nicknames"]
        registered_views_count = 0 # 이름 충돌 방지를 위해 변수명 변경

        for cog_name in cogs_with_persistent_views:
            cog = self.get_cog(cog_name)
            if cog and hasattr(cog, 'register_persistent_views'):
                try:
                    await cog.register_persistent_views()
                    registered_views_count += 1
                    logger.info(f"✅ '{cog_name}' Cog의 영구 View가 등록되었습니다.")
                except Exception as e:
                    logger.error(f"❌ '{cog_name}' Cog의 영구 View 등록 중 오류 발생: {e}", exc_info=True)
            elif not cog:
                logger.warning(f"⚠️ '{cog_name}' Cog가 로드되지 않았거나 찾을 수 없습니다.")

        logger.info(f"✅ 총 {registered_views_count}개의 Cog에서 영구 View를 성공적으로 등록했습니다.")

    async def load_all_extensions(self):
        logger.info("------ [ Cog 로드 시작 ] ------")
        cogs_dir = './cogs'
        if not os.path.exists(cogs_dir):
            logger.critical(f"❌ Cogs 디렉토리를 찾을 수 없습니다: {cogs_dir}. 봇이 시작되지 못할 수 있습니다."); return
        
        # cogs/server/* 형태의 하위 디렉토리를 로드하기 위함
        loaded_count = 0
        for folder in sorted(os.listdir(cogs_dir)):
            folder_path = os.path.join(cogs_dir, folder)
            if os.path.isdir(folder_path):
                # 하위 디렉토리 내의 Python 파일 탐색
                for filename in os.listdir(folder_path):
                    if filename.endswith('.py') and not filename.startswith('__'):
                        try:
                            # 예: cogs.server.system
                            extension_path = f'cogs.{folder}.{filename[:-3]}'
                            await self.load_extension(extension_path)
                            logger.info(f'✅ Cog 로드 성공: {extension_path}')
                            loaded_count += 1
                        except commands.ExtensionAlreadyLoaded:
                            logger.warning(f'⚠️ Cog가 이미 로드되었습니다: {extension_path}')
                        except commands.ExtensionNotFound:
                            logger.error(f'❌ Cog를 찾을 수 없습니다: {extension_path}. 파일 경로를 확인해주세요.')
                        except commands.NoEntryPointError:
                            logger.error(f'❌ "{extension_path}" Cog에 setup 함수가 없습니다. setup 함수를 정의해주세요.')
                        except Exception as e:
                            logger.error(f'❌ Cog 로드 실패: {extension_path} | {e}', exc_info=True)
        logger.info(f"------ [ {loaded_count}개의 Cog 로드 완료 ] ------")


bot = MyBot(command_prefix="/", intents=intents)

async def regenerate_all_panels():
    """봇 시작 시 모든 패널을 강제로 재생성합니다."""
    logger.info("------ [ 모든 패널 자동 재생성 시작 ] ------")
    regenerated_panels_count = 0 # 이름 충돌 방지를 위해 변수명 변경
    # 패널 재생성을 지원하는 Cog 목록
    panel_cogs = ["RolePanel", "Onboarding", "Nicknames"] 
    
    for cog_name in panel_cogs:
        cog = bot.get_cog(cog_name)
        if cog and hasattr(cog, 'regenerate_panel'):
            try: 
                # regenerate_panel에 channel=None을 넘겨 Cog 내부 로직이 DB에서 채널 ID를 찾도록 함
                await cog.regenerate_panel(channel=None) 
                regenerated_panels_count += 1
            except Exception as e: 
                logger.error(f"❌ '{cog_name}' 패널 재생성 작업 중 오류 발생: {e}", exc_info=True)
        else:
            logger.warning(f"⚠️ '{cog_name}' Cog가 없거나 'regenerate_panel' 메서드를 가지고 있지 않습니다. 스킵합니다.")

    logger.info(f"✅ 총 {regenerated_panels_count}개의 패널에 대한 재생성 작업이 요청되었습니다.")
    logger.info("------ [ 모든 패널 자동 재생성 완료 ] ------")

@bot.event
async def on_ready():
    logger.info("==================================================")
    logger.info(f"✅ {bot.user.name}(이)가 성공적으로 로그인했습니다.")
    logger.info(f"✅ 봇 버전: {BOT_VERSION}")
    logger.info(f"✅ 현재 UTC 시간: {datetime.now(timezone.utc)}")
    logger.info("==================================================")
    
    # DB에서 기본값을 동기화하고 모든 설정을 로드
    await sync_defaults_to_db()
    await load_all_data_from_db()
    
    logger.info("------ [ 모든 Cog 설정 새로고침 시작 ] ------")
    refreshed_cogs_count = 0 # 이름 충돌 방지를 위해 변수명 변경
    for cog_name, cog in bot.cogs.items():
        if hasattr(cog, 'load_configs'):
            try: 
                await cog.load_configs()
                refreshed_cogs_count += 1
                logger.info(f"✅ '{cog_name}' Cog 설정 새로고침 완료.")
            except Exception as e: 
                logger.error(f"❌ '{cog_name}' Cog 설정 새로고침 중 오류: {e}", exc_info=True)
    logger.info(f"✅ 총 {refreshed_cogs_count}개의 Cog 설정이 새로고침되었습니다.")
    logger.info("------ [ 모든 Cog 설정 새로고침 완료 ] ------")
    
    try:
        if TEST_GUILD_ID:
            # TEST_GUILD_ID가 None이 아니고 유효한 정수일 때만 사용
            guild = discord.Object(id=TEST_GUILD_ID)
            await bot.tree.sync(guild=guild)
            logger.info(f'✅ 테스트 서버({TEST_GUILD_ID})에 명령어를 동기화했습니다.')
        else:
            # TEST_GUILD_ID가 없거나 유효하지 않으면 전역 동기화 시도
            synced = await bot.tree.sync()
            logger.info(f'✅ {len(synced)}개의 슬래시 명령어를 전체 서버에 동기화했습니다.')
    except Exception as e: 
        logger.error(f'❌ 명령어 동기화 중 오류가 발생했습니다: {e}', exc_info=True)
    
    # 패널 재생성 (필요에 따라 제어할 수 있도록 추후 옵션화 고려)
    await regenerate_all_panels()

async def main():
    async with bot:
        await bot.start(BOT_TOKEN)

if __name__ == "__main__":
    if BOT_TOKEN is None: 
        logger.critical("❌ BOT_TOKEN 환경 변수가 설정되지 않았습니다. 봇을 실행할 수 없습니다.")
    else:
        try:
            asyncio.run(main())
        except discord.errors.LoginFailure: 
            logger.critical("❌ 봇 토큰이 유효하지 않습니다. 환경 변수 'BOT_TOKEN'을 확인해주세요.")
        except KeyboardInterrupt:
            logger.info("봇이 사용자 요청에 의해 종료됩니다.")
        except Exception as e: 
            logger.critical(f"🚨 봇 실행 중 치명적인 오류 발생: {e}", exc_info=True)
