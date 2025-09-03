# main.py (관리 봇)

import discord
from discord.ext import commands import commands, tasks
import os
import asyncio
import logging
import logging.handlers
from datetime import datetime, timezone
from typing import Optional

# [✅ 수정] 두 함수 모두 사용하므로 그대로 둡니다.
from utils.database import load_all_data_from_db, sync_defaults_to_db

# --- 중앙 로깅 설정 ---
# [✅ 가독성 개선] 로그 포맷을 더 간결하고 명확하게 변경합니다.
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(name)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
log_handler = logging.StreamHandler()
log_handler.setFormatter(log_formatter)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
if root_logger.hasHandlers():
    root_logger.handlers.clear()
root_logger.addHandler(log_handler)

# [✅ 가독성 개선] 불필요한 라이브러리의 상세 로그를 비활성화하여 핵심 로그만 볼 수 있도록 합니다.
logging.getLogger('discord').setLevel(logging.WARNING)
logging.getLogger('discord.http').setLevel(logging.WARNING)
logging.getLogger('websockets').setLevel(logging.WARNING)
logging.getLogger('supabase').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# --- 환경 변수 및 인텐트 설정 ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
RAW_TEST_GUILD_ID = os.environ.get('TEST_GUILD_ID')
TEST_GUILD_ID: Optional[int] = None
if RAW_TEST_GUILD_ID:
    try:
        TEST_GUILD_ID = int(RAW_TEST_GUILD_ID)
        logger.info(f"테스트 서버 ID가 '{TEST_GUILD_ID}'(으)로 설정되었습니다.")
    except ValueError:
        logger.error(f"❌ TEST_GUILD_ID 환경 변수가 유효한 숫자가 아닙니다: '{RAW_TEST_GUILD_ID}'")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True
BOT_VERSION = "v2.5-log-cleanup" # 로그 가독성 개선 버전

# --- 커스텀 봇 클래스 ---
class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        # [✅ 핵심] 봇 시작 시, 로컬 기본값(ui_defaults.py 등)을 DB에 먼저 동기화합니다.
        await sync_defaults_to_db()

        # DB 동기화 후, Cog들을 로드합니다.
        await self.load_all_extensions()
        
        cogs_with_persistent_views = [
            "RolePanel", "Onboarding", "Nicknames", "TicketSystem", 
            "CustomEmbed", "ItemSystem", "AnonymousBoard", 
            "WarningSystem", "VoiceMaster"
        ]
        
        registered_views_count = 0
        for cog_name in cogs_with_persistent_views:
            cog = self.get_cog(cog_name)
            if cog and hasattr(cog, 'register_persistent_views'):
                try:
                    await cog.register_persistent_views()
                    registered_views_count += 1
                except Exception as e:
                    logger.error(f"❌ '{cog_name}' Cog의 영구 View 등록 중 오류 발생: {e}", exc_info=True)
        
        if registered_views_count > 0:
            logger.info(f"✅ 총 {registered_views_count}개의 Cog에서 영구 View를 성공적으로 등록했습니다.")

    async def on_ready(self):
        # on_ready로 이동하여 봇이 완전히 준비된 후에 루프를 시작하도록 합니다.
        if not self.refresh_cache_periodically.is_running():
            self.refresh_cache_periodically.start()
            logger.info("✅ 주기적인 DB 캐시 새로고침 루프를 시작합니다.")

    @tasks.loop(minutes=5)
    async def refresh_cache_periodically(self):
        """5분마다 DB에서 최신 설정을 불러와 캐시를 갱신합니다."""
        logger.info("🔄 주기적인 DB 캐시 새로고침을 시작합니다...")
        await load_all_data_from_db()
        logger.info("🔄 주기적인 DB 캐시 새로고침이 완료되었습니다.")

    @refresh_cache_periodically.before_loop
    async def before_refresh_cache(self):
        """봇이 완전히 준비될 때까지 기다립니다."""
        await self.wait_until_ready()

    async def load_all_extensions(self):
        logger.info("------ [ Cog 로드 시작 ] ------")
        cogs_dir = 'cogs'
        if not os.path.isdir(cogs_dir):
            logger.critical(f"❌ Cogs 디렉토리를 찾을 수 없습니다: '{cogs_dir}'")
            return

        loaded_count = 0
        failed_count = 0
        # [✅ 안정성 개선] os.walk를 사용하여 모든 하위 폴더의 Cog를 안정적으로 찾도록 변경합니다.
        for root, dirs, files in os.walk(cogs_dir):
            # __pycache__ 폴더는 탐색에서 제외합니다.
            if '__pycache__' in dirs:
                dirs.remove('__pycache__')
            
            for filename in files:
                if filename.endswith('.py') and not filename.startswith('__'):
                    path = os.path.join(root, filename)
                    # 파일 경로를 모듈 경로로 변환합니다 (e.g., cogs/server/system.py -> cogs.server.system)
                    extension_path = os.path.splitext(path)[0].replace(os.path.sep, '.')
                    
                    try:
                        await self.load_extension(extension_path)
                        logger.info(f" M> Cog 로드 성공: {extension_path}")
                        loaded_count += 1
                    except Exception as e:
                        logger.error(f" M> Cog 로드 실패: {extension_path} | {e}", exc_info=True)
                        failed_count += 1
        
        logger.info(f"------ [ Cog 로드 완료 | 성공: {loaded_count} / 실패: {failed_count} ] ------")

bot = MyBot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
    logger.info("==================================================")
    logger.info(f"✅ {bot.user.name} ({bot.user.id})")
    logger.info(f"✅ 봇 버전: {BOT_VERSION}")
    logger.info(f"✅ 현재 UTC 시간: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("==================================================")
    
    # DB 동기화가 끝난 후, 캐시를 로드합니다.
    await load_all_data_from_db()
    
    logger.info("------ [ 모든 Cog 설정 새로고침 시작 ] ------")
    refreshed_cogs_count = 0
    for cog_name, cog in bot.cogs.items():
        if hasattr(cog, 'load_configs'):
            try: 
                await cog.load_configs()
                refreshed_cogs_count += 1
            except Exception as e: 
                logger.error(f"❌ '{cog_name}' Cog 설정 새로고침 중 오류: {e}", exc_info=True)

    if refreshed_cogs_count > 0:
        logger.info(f"✅ 총 {refreshed_cogs_count}개의 Cog 설정이 새로고침되었습니다.")
    logger.info("------ [ 모든 Cog 설정 새로고침 완료 ] ------")
    
    try:
        if TEST_GUILD_ID:
            guild = discord.Object(id=TEST_GUILD_ID)
            await bot.tree.sync(guild=guild)
            logger.info(f"✅ 테스트 서버({TEST_GUILD_ID})에 슬래시 명령어를 동기화했습니다.")
        else:
            synced = await bot.tree.sync()
            logger.info(f"✅ {len(synced)}개의 슬래시 명령어를 전체 서버에 동기화했습니다.")
    except Exception as e: 
        logger.error(f"❌ 명령어 동기화 중 오류가 발생했습니다: {e}", exc_info=True)

async def main():
    async with bot:
        await bot.start(BOT_TOKEN)

if __name__ == "__main__":
    if BOT_TOKEN is None: 
        logger.critical("❌ BOT_TOKEN 환경 변수가 설정되지 않았습니다. 프로그램을 종료합니다.")
    else:
        try:
            asyncio.run(main())
        except discord.errors.LoginFailure: 
            logger.critical("❌ 봇 토큰이 유효하지 않습니다. 토큰을 다시 확인해주세요.")
        except Exception as e: 
            logger.critical(f"🚨 봇 실행 중 치명적인 오류 발생: {e}", exc_info=True)
