# main.py (관리 봇)

import discord
from discord.ext import commands
import os
import asyncio
import logging
import logging.handlers
from datetime import datetime, timezone
from typing import Optional
from discord.ext import commands, tasks
from utils.database import load_all_data_from_db, sync_defaults_to_db

# --- 중앙 로깅 설정 ---
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(name)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
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
BOT_VERSION = "v2.6-stability-hotfix"

# --- 커스텀 봇 클래스 ---
class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.recently_moderated_users = set()

    async def setup_hook(self):
        # 1. DB에 기본값을 동기화하고, 동시에 로컬 캐시를 채웁니다.
        await sync_defaults_to_db()
        # 2. DB에서 값을 읽어와 로컬 캐시를 '업데이트'합니다. (덮어쓰기 X)
        await load_all_data_from_db()

        # 3. 모든 기능(Cogs) 로드
        await self.load_all_extensions()
        
        # 4. 영구 View 등록
        cogs_with_persistent_views = [
            "RolePanel", "Onboarding", "Nicknames", "TicketSystem", 
            "CustomEmbed", "ItemSystem", "AnonymousBoard", 
            "WarningSystem", "VoiceMaster", "StickyEmbed"
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

    @tasks.loop(minutes=5)
    async def refresh_cache_periodically(self):
        logger.info("🔄 주기적인 DB 캐시 새로고침을 시작합니다...")
        await load_all_data_from_db()
        logger.info("🔄 주기적인 DB 캐시 새로고침이 완료되었습니다.")

    async def load_all_extensions(self):
        logger.info("------ [ Cog 로드 시작 ] ------")
        cogs_dir = 'cogs'
        loaded_count, failed_count = 0, 0
        for root, dirs, files in os.walk(cogs_dir):
            if '__pycache__' in dirs:
                dirs.remove('__pycache__')
            
            for filename in files:
                if filename.endswith('.py') and not filename.startswith('__'):
                    extension_path = os.path.join(root, filename).replace(os.path.sep, '.')[:-3]
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
    
    # 캐시가 완전히 준비된 후에, 각 Cog가 필요한 설정을 불러오도록 합니다.
    logger.info("------ [ 모든 Cog 설정 로드 시작 ] ------")
    for cog_name, cog in bot.cogs.items():
        if hasattr(cog, 'load_configs'):
            try: 
                await cog.load_configs()
            except Exception as e: 
                logger.error(f"❌ '{cog_name}' Cog 설정 로드 중 오류: {e}", exc_info=True)
    logger.info("------ [ 모든 Cog 설정 로드 완료 ] ------")

    # 주기적 캐시 새로고침 루프를 시작합니다.
    if not bot.refresh_cache_periodically.is_running():
        bot.refresh_cache_periodically.start()
        logger.info("✅ 주기적인 DB 캐시 새로고침 루프를 시작합니다.")

    # 슬래시 명령어를 동기화합니다.
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
