# main.py (수정 없음, 기존 코드 유지)

import discord
from discord.ext import commands
import os
import asyncio
import logging

# Cog 및 유틸리티 함수 임포트
from cogs.server.system import AutoRoleView, STATIC_AUTO_ROLE_PANELS
from utils.database import load_all_configs_from_db, get_id

# 로깅 기본 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] %(message)s')
logger = logging.getLogger(__name__)

# --- 봇 기본 설정 ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
TEST_GUILD_ID = os.environ.get('TEST_GUILD_ID')

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        # 봇 시작 전에 모든 Cog를 로드합니다.
        await self.load_all_extensions()
        
        # 봇이 재시작되어도 기존 View들이 계속 작동하도록 등록합니다.
        # 이 작업은 setup_hook에서, 봇이 Discord에 연결되기 전에 수행하는 것이 더 안정적입니다.
        logger.info("------ [ 영구 View 재등록 시작 ] ------")
        cogs_to_setup_views = ["Onboarding", "Nicknames", "UserProfile", "Fishing", "Commerce"]
        for cog_name in cogs_to_setup_views:
            cog = self.get_cog(cog_name)
            if cog and hasattr(cog, 'register_persistent_views'):
                cog.register_persistent_views()
                logger.info(f"✅ '{cog_name}' Cog의 영구 View가 등록되었습니다.")
        
        # main.py에서 직접 AutoRoleView를 등록하는 로직
        for panel_key, panel_config in STATIC_AUTO_ROLE_PANELS.items():
            # on_ready 이전에 DB 캐시가 없을 수 있으므로, 여기서는 뷰만 등록합니다.
            # 실제 메시지 ID 연결은 on_ready에서 이루어집니다.
            self.add_view(AutoRoleView(panel_config))
            logger.info(f"✅ 역할 패널 View 준비 완료: '{panel_key}'")


    async def load_all_extensions(self):
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
                            await self.load_extension(extension_path)
                            logger.info(f'✅ Cog 로드 성공: {extension_path}')
                        except Exception as e:
                            logger.error(f'❌ Cog 로드 실패: {extension_path} | {e}', exc_info=True)
        logger.info("------ [ Cog 로드 완료 ] ------")


# 봇 인스턴스 생성
bot = MyBot(command_prefix="/", intents=intents)

# --- 패널 자동 재생성 기능 ---
async def regenerate_all_panels():
    """ DB에 저장된 정보를 바탕으로 모든 동적 패널(메시지)을 다시 생성하거나 업데이트합니다. """
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
        for result in results:
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

    # 2. 각 Cog에 DB 설정값을 다시 로드하도록 알립니다.
    logger.info("------ [ 모든 Cog 설정 새로고침 시작 ] ------")
    for cog_name, cog in bot.cogs.items():
        if hasattr(cog, 'load_all_configs'):
            await cog.load_all_configs()
    logger.info("------ [ 모든 Cog 설정 새로고침 완료 ] ------")


    # 3. 슬래시 명령어를 Discord 서버와 동기화합니다.
    try:
        if TEST_GUILD_ID:
            guild = discord.Object(id=int(TEST_GUILD_ID))
            await bot.tree.sync(guild=guild)
            logger.info(f'✅ 테스트 서버({TEST_GUILD_ID})에 명령어를 동기화했습니다.')
        else:
            synced = await bot.tree.sync()
            logger.info(f'✅ {len(synced)}개의 슬래시 명령어를 전체 서버에 동기화했습니다.')
    except Exception as e:
        logger.error(f'❌ 명령어 동기화 중 오류가 발생했습니다: {e}')
    
    # 4. DB 정보를 바탕으로 모든 패널을 다시 생성합니다.
    await regenerate_all_panels()

    # 5. AutoRoleView에 메시지 ID를 연결합니다.
    logger.info("------ [ 역할 패널 View 메시지 ID 연결 시작 ] ------")
    for panel_key, panel_config in STATIC_AUTO_ROLE_PANELS.items():
        try:
            message_id = get_id(f"panel_{panel_key}_message_id")
            if message_id:
                # 이미 setup_hook에서 View 객체는 등록되었으므로, 여기서는 message_id만 확인합니다.
                logger.info(f"✅ 역할 패널 View와 메시지 ID 연결 확인: '{panel_key}' (ID: {message_id})")
        except Exception as e:
            logger.error(f"❌ '{panel_key}' View 메시지 ID 연결 중 오류: {e}")
    logger.info("------ [ 역할 패널 View 메시지 ID 연결 완료 ] ------")


# --- 메인 실행 함수 ---
async def main():
    async with bot:
        # setup_hook이 내부적으로 Cog 로드를 처리하므로, 여기서는 bot.start만 호출합니다.
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
