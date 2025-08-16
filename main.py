# main.py

import discord
from discord.ext import commands
import os
import asyncio
import logging
import logging.handlers  # [신규] 로깅 핸들러 임포트

from utils.database import load_all_data_from_db

# --- [신규] 중앙 로깅 설정 ---
# 1. 로그 포맷터 생성: 로그가 어떤 형식으로 보일지 결정합니다.
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(name)s:%(lineno)d] %(message)s')

# 2. 로그 핸들러 생성: 로그를 어디로 보낼지 결정합니다. (StreamHandler -> 콘솔 화면)
log_handler = logging.StreamHandler()
log_handler.setFormatter(log_formatter)

# 3. 루트 로거 가져오기: 봇의 모든 로거들의 최상위 로거입니다.
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)  # 봇 전체의 기본 로그 레벨을 INFO로 설정

# 4. 기존 핸들러 제거 및 새 핸들러 추가: 중복 로깅을 방지합니다.
if root_logger.hasHandlers():
    root_logger.handlers.clear()
root_logger.addHandler(log_handler)

# 5. 라이브러리 로거 레벨 조정: 너무 많은 로그를 남기는 라이브러리를 조용하게 만듭니다.
logging.getLogger('discord').setLevel(logging.WARNING)
logging.getLogger('discord.http').setLevel(logging.WARNING)
logging.getLogger('websockets').setLevel(logging.WARNING)

# 6. 이 파일에서 사용할 로거 생성
logger = logging.getLogger(__name__)

# --- 환경 변수 로드 ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
TEST_GUILD_ID = os.environ.get('TEST_GUILD_ID')

# --- 봇 인텐트 설정 ---
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True

# --- 커스텀 봇 클래스 ---
class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def setup_hook(self):
        await self.load_all_extensions()
        
        cogs_with_persistent_views = [
            "ServerSystem", "Onboarding", "Nicknames", 
            "UserProfile", "Fishing", "Commerce"
        ]
        
        registered_views = 0
        for cog_name in cogs_with_persistent_views:
            cog = self.get_cog(cog_name)
            if cog and hasattr(cog, 'register_persistent_views'):
                try:
                    await cog.register_persistent_views()
                    logger.info(f"✅ '{cog_name}' Cog의 영구 View가 등록되었습니다.")
                    registered_views += 1
                except Exception as e:
                    logger.error(f"❌ '{cog_name}' Cog의 영구 View 등록 중 오류 발생: {e}", exc_info=True)
        
        logger.info(f"✅ 총 {registered_views}개의 Cog에서 영구 View를 성공적으로 등록했습니다.")

    async def load_all_extensions(self):
        logger.info("------ [ Cog 로드 시작 ] ------")
        cogs_dir = './cogs'
        if not os.path.exists(cogs_dir):
            logger.error(f"Cogs 디렉토리를 찾을 수 없습니다: {cogs_dir}")
            return
            
        for folder in sorted(os.listdir(cogs_dir)):
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

# --- 봇 인스턴스 생성 ---
bot = MyBot(command_prefix="/", intents=intents)

async def regenerate_all_panels():
    logger.info("------ [ 모든 패널 자동 재생성 시작 ] ------")
    regenerated_panels = 0
    for cog_name, cog in bot.cogs.items():
        if hasattr(cog, 'regenerate_panel'):
            try:
                await cog.regenerate_panel()
                regenerated_panels +=1
            except Exception as e:
                logger.error(f"❌ '{cog_name}' 패널 재생성 작업 중 오류 발생: {e}", exc_info=True)
    
    logger.info(f"✅ 총 {regenerated_panels}개의 패널에 대한 재생성 작업이 요청되었습니다.")
    logger.info("------ [ 모든 패널 자동 재생성 완료 ] ------")

@bot.event
async def on_ready():
    logger.info(f'✅ {bot.user.name}(이)가 성공적으로 로그인했습니다.')
    
    await load_all_data_from_db()
    
    logger.info("------ [ 모든 Cog 설정 새로고침 시작 ] ------")
    refreshed_cogs = 0
    for cog_name, cog in bot.cogs.items():
        if hasattr(cog, 'load_configs'):
            try:
                await cog.load_configs()
                refreshed_cogs += 1
            except Exception as e:
                logger.error(f"❌ '{cog_name}' Cog 설정 새로고침 중 오류: {e}", exc_info=True)
    logger.info(f"✅ 총 {refreshed_cogs}개의 Cog 설정이 새로고침되었습니다.")
    logger.info("------ [ 모든 Cog 설정 새로고침 완료 ] ------")

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
        
    await regenerate_all_panels()

async def main():
    async with bot:
        await bot.start(BOT_TOKEN)

if __name__ == "__main__":
    if BOT_TOKEN is None:
        logger.critical("❌ BOT_TOKEN 환경 변수가 설정되지 않았습니다.")
    else:
        try:
            asyncio.run(main())
        except discord.errors.LoginFailure:
            logger.critical("❌ 봇 토큰이 유효하지 않습니다.")
        except Exception as e:
            logger.critical(f"🚨 봇 실행 중 치명적인 오류 발생: {e}", exc_info=True)
