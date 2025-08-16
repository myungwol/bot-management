# main.py (UI 중앙 관리 시스템 적용)

import discord
from discord.ext import commands
import os
import asyncio
import logging

from utils.database import load_all_configs_from_db
from cogs.server.system import STATIC_AUTO_ROLE_PANELS, AutoRoleView

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] %(message)s')
logger = logging.getLogger(__name__)

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
        # 1. 모든 Cog 확장 파일을 로드합니다.
        await self.load_all_extensions()
        
        # 2. 정적인 자동 역할 View를 등록합니다.
        for panel_key, panel_config in STATIC_AUTO_ROLE_PANELS.items():
            self.add_view(AutoRoleView(panel_config))
        logger.info(f"✅ {len(STATIC_AUTO_ROLE_PANELS)}개의 정적 AutoRoleView가 등록되었습니다.")

        # 3. [수정] 각 기능 패널의 영구 View를 동적으로 등록합니다.
        # ConfigMenu는 이 방식이 아니므로 목록에서 제외합니다.
        cogs_with_persistent_views = ["Onboarding", "Nicknames", "UserProfile", "Fishing", "Commerce"]
        for cog_name in cogs_with_persistent_views:
            cog = self.get_cog(cog_name)
            if cog and hasattr(cog, 'register_persistent_views'):
                await cog.register_persistent_views()
                logger.info(f"✅ '{cog_name}' Cog의 영구 View가 등록되었습니다.")

    async def load_all_extensions(self):
        logger.info("------ [ Cog 로드 시작 ] ------")
        cogs_dir = './cogs'
        if not os.path.exists(cogs_dir):
            logger.error(f"Cogs 디렉토리를 찾을 수 없습니다: {cogs_dir}")
            return
        # [수정] 로드 순서를 정하기 위해 폴더 목록을 정렬합니다. (admin -> economy -> games -> server)
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

bot = MyBot(command_prefix="/", intents=intents)

async def regenerate_all_panels():
    logger.info("------ [ 모든 패널 자동 재생성 시작 ] ------")
    # [수정] 패널 재생성 순서를 제어하기 위해 Cog 목록을 가져와서 처리합니다.
    panel_cogs = ["ServerSystem", "Onboarding", "Nicknames", "Commerce", "Fishing", "UserProfile"]
    for cog_name in panel_cogs:
        cog = bot.get_cog(cog_name)
        if cog and hasattr(cog, 'regenerate_panel'):
            try:
                await cog.regenerate_panel()
            except Exception as e:
                logger.error(f"❌ '{cog_name}' 패널 재생성 작업 중 오류 발생: {e}", exc_info=True)
    logger.info("------ [ 모든 패널 자동 재생성 완료 ] ------")

@bot.event
async def on_ready():
    logger.info(f'✅ {bot.user.name}(이)가 성공적으로 로그인했습니다.')
    
    # 1. DB에서 모든 채널/역할 ID를 캐시로 불러옵니다.
    await load_all_configs_from_db()
    
    # 2. 각 Cog가 캐시된 ID를 자신의 설정으로 불러옵니다.
    logger.info("------ [ 모든 Cog 설정 새로고침 시작 ] ------")
    for cog_name, cog in bot.cogs.items():
        if hasattr(cog, 'load_all_configs'):
            await cog.load_all_configs()
    logger.info("------ [ 모든 Cog 설정 새로고침 완료 ] ------")

    # 3. 슬래시 커맨드를 동기화합니다.
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
    
    # 4. 모든 패널을 재생성합니다.
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
