# main.py (명령어 최소화 및 안정성 개선 버전)

import discord
from discord.ext import commands
import os
import asyncio
import logging

# Cog 및 유틸리티 함수 임포트
from cogs.server.system import AutoRoleView, STATIC_AUTO_ROLE_PANELS
from utils.database import load_all_configs_from_db, get_id

# 로깅 기본 설정
# 파일 이름, 함수 이름, 줄 번호를 포함하여 더 상세한 로그를 기록합니다.
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] %(message)s')
logger = logging.getLogger(__name__)

# --- 봇 기본 설정 ---
# Railway 환경 변수에서 토큰을 안전하게 불러옵니다.
BOT_TOKEN = os.environ.get('BOT_TOKEN')
# 개발 및 테스트를 위한 서버 ID (환경 변수에서 설정 가능)
TEST_GUILD_ID = os.environ.get('TEST_GUILD_ID')

# 봇이 필요로 하는 권한(Intents) 설정
intents = discord.Intents.default()
intents.members = True          # 서버 멤버 관련 이벤트 (역할 지급 등)
intents.message_content = True  # 메시지 내용 (현재는 슬래시 명령어가 기본이므로 필수 아님)
intents.voice_states = True     # 음성 채널 활동 감지 (음성 활동 보상 등)

class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        """ 봇이 Discord API에 연결될 때 호출되는 비동기 초기화 함수입니다. """
        # 모든 주요 로직은 on_ready에서 실행되므로 여기서는 비워둡니다.
        pass

# 봇 인스턴스 생성
bot = MyBot(command_prefix="/", intents=intents)

# --- 패널 자동 재생성 기능 ---
async def regenerate_all_panels():
    """ DB에 저장된 정보를 바탕으로 모든 동적 패널(메시지)을 다시 생성하거나 업데이트합니다. """
    logger.info("------ [ 모든 패널 자동 재생성 시작 ] ------")
    panel_tasks = []
    
    # 로드된 모든 Cog를 순회하며 'regenerate_panel' 함수가 있는지 확인합니다.
    for cog_name, cog in bot.cogs.items():
        if hasattr(cog, 'regenerate_panel'):
            try:
                # 각 Cog의 패널 재생성 함수를 비동기 작업 목록에 추가합니다.
                panel_tasks.append(cog.regenerate_panel())
                logger.info(f"🔄 '{cog_name}'의 패널 재생성 작업을 준비합니다.")
            except Exception as e:
                logger.error(f"❌ '{cog_name}'의 패널 재생성 준비 중 오류 발생: {e}")

    # 준비된 모든 패널 재생성 작업을 동시에 실행합니다.
    if panel_tasks:
        results = await asyncio.gather(*panel_tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ 패널 재생성 작업 중 오류 발생: {result}", exc_info=result)
    else:
        logger.info("ℹ️ 재생성할 패널 작업이 없습니다.")
        
    logger.info("------ [ 모든 패널 자동 재생성 완료 ] ------")

# --- 봇 이벤트 핸들러 ---
@bot.event
async def on_ready():
    """ 봇이 성공적으로 로그인하고 모든 준비를 마쳤을 때 호출됩니다. """
    logger.info(f'✅ {bot.user.name}(이)가 성공적으로 로그인했습니다.')
    logger.info(f'✅ 봇 ID: {bot.user.id}')
    logger.info('------')

    # 1. DB에서 모든 설정(채널/역할 ID)을 불러와 메모리에 캐싱합니다. (가장 먼저 실행)
    await load_all_configs_from_db()

    # 2. 슬래시 명령어를 Discord 서버와 동기화합니다.
    try:
        if TEST_GUILD_ID:
            # 테스트 서버 ID가 지정된 경우, 해당 서버에만 즉시 명령어를 동기화하여 개발 속도를 높입니다.
            guild = discord.Object(id=int(TEST_GUILD_ID))
            await bot.tree.sync(guild=guild)
            logger.info(f'✅ 테스트 서버({TEST_GUILD_ID})에 명령어를 동기화했습니다.')
        else:
            # 전체 서버에 명령어를 동기화합니다.
            synced = await bot.tree.sync()
            logger.info(f'✅ {len(synced)}개의 슬래시 명령어를 전체 서버에 동기화했습니다.')
    except Exception as e:
        logger.error(f'❌ 명령어 동기화 중 오류가 발생했습니다: {e}')
    
    # 3. DB 정보를 바탕으로 모든 패널을 다시 생성합니다.
    await regenerate_all_panels()

    # 4. 봇이 재시작되어도 기존 역할 패널 버튼이 계속 작동하도록 View를 다시 등록합니다.
    logger.info("------ [ 역할 패널 View 재등록 시작 ] ------")
    for panel_key, panel_config in STATIC_AUTO_ROLE_PANELS.items():
        try:
            # DB 캐시에서 메시지 ID를 가져옵니다.
            message_id = get_id(f"panel_{panel_key}_message_id")
            if message_id:
                view = AutoRoleView(panel_config)
                bot.add_view(view, message_id=message_id)
                logger.info(f"✅ 역할 패널 View 재등록 성공: '{panel_key}' (ID: {message_id})")
        except Exception as e:
            logger.error(f"❌ '{panel_key}' View 재등록 중 오류: {e}")
    logger.info("------ [ 역할 패널 View 재등록 완료 ] ------")


# --- Cog 로딩 함수 ---
async def load_extensions():
    """ './cogs' 폴더 내의 모든 Cog를 재귀적으로 찾아 로드합니다. """
    logger.info("------ [ Cog 로드 시작 ] ------")
    cogs_dir = './cogs'
    if not os.path.exists(cogs_dir):
        logger.error(f"Cogs 디렉토리를 찾을 수 없습니다: {cogs_dir}")
        return
        
    for folder in os.listdir(cogs_dir):
        folder_path = os.path.join(cogs_dir, folder)
        if os.path.isdir(folder_path):
            for filename in os.listdir(folder_path):
                if filename.endswith('.py') and not filename.startswith('__'):
                    try:
                        extension_path = f'cogs.{folder}.{filename[:-3]}'
                        await bot.load_extension(extension_path)
                        logger.info(f'✅ Cog 로드 성공: {extension_path}')
                    except Exception as e:
                        logger.error(f'❌ Cog 로드 실패: {extension_path} | {e}', exc_info=True)
    logger.info("------ [ Cog 로드 완료 ] ------")

# --- 메인 실행 함수 ---
async def main():
    async with bot:
        # 봇을 시작하기 전에 반드시 Cog를 먼저 로드해야 합니다.
        await load_extensions()
        await bot.start(BOT_TOKEN)

if __name__ == "__main__":
    if BOT_TOKEN is None:
        logger.critical("❌ BOT_TOKEN 환경 변수가 설정되지 않았습니다. Railway 프로젝트 변수를 확인해주세요.")
    else:
        try:
            asyncio.run(main())
        except discord.errors.LoginFailure:
            logger.critical("❌ 봇 토큰이 유효하지 않습니다. BOT_TOKEN 환경 변수를 다시 확인해주세요.")
        except Exception as e:
            logger.critical(f"🚨 봇 실행 중 치명적인 오류 발생: {e}", exc_info=True)
