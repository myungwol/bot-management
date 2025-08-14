# utils/database.py (get_auto_role_buttons 복구 최종본)

import os
import discord
from supabase import create_client, AsyncClient
import logging

# [수정] system.py의 AutoRoleView를 가져오기 위해 import 경로 조정
# 이 경로는 cogs/server/system.py 파일의 위치에 따라 정확해야 합니다.
from cogs.server.system import AutoRoleView

# [수정] 실제 존재하는 함수 이름으로 변경
from utils.database import (get_all_channel_configs, 
                           get_all_auto_role_panels, get_auto_role_buttons)

# 로깅 기본 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 봇 기본 설정 ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.message_content = True

class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 봇의 모든 채널 설정을 저장할 딕셔너리 (필요 시 사용)
        self.channel_configs = {}

    async def setup_hook(self):
        """ 봇이 재시작될 때 AutoRoleView를 다시 등록하는 핵심 기능 """
        logger.info("------ [ 자동 역할 패널 View 재등록 시작 ] ------")
        panels = await get_all_auto_role_panels()
        if not panels:
            logger.info("ℹ️ 재등록할 자동 역할 패널이 없습니다.")
        else:
            for panel_config in panels:
                try:
                    buttons_config = await get_auto_role_buttons(panel_config['message_id'])
                    view = AutoRoleView(buttons_config)
                    # message_id를 지정하여 봇에 View를 다시 인식시킴
                    self.add_view(view, message_id=panel_config['message_id'])
                    logger.info(f"✅ 자동 역할 패널 (ID: {panel_config['message_id']})의 View를 재등록했습니다.")
                except Exception as e:
                    logger.error(f"❌ 자동 역할 패널 (ID: {panel_config['message_id']}) 재등록 중 오류: {e}")
        logger.info("------ [ 자동 역할 패널 View 재등록 완료 ] ------")


bot = MyBot(command_prefix="/", intents=intents)

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

    # [수정] 봇 시작 시 모든 채널 설정을 한번만 DB에서 가져와 캐시에 저장
    # database.py의 _cached_channel_configs 변수에 저장됨
    await get_all_channel_configs()
    logger.info("✅ 모든 채널 설정이 캐시되었습니다.")
    
    # [삭제] 더 이상 regenerate_all_panels 함수를 호출하지 않음
    # 패널 생성/관리는 이제 /system setup-panels 명령어로 수행


# [삭제] regenerate_all_panels 함수 전체를 삭제합니다.
# 이 기능은 cogs/server/system.py의 'setup-panels' 명령어로 대체되었습니다.


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
                        logger.error(f'❌ Cog 로드 실패: {folder}/{filename} | 오류: {e}', exc_info=True)
    logger.info("------ [ Cog 로드 완료 ] ------")
# [복구] 자동 역할 버튼 정보를 가져오는 함수
async def get_auto_role_buttons(message_id: int):
    if not supabase: return []
    try:
        response = await supabase.table('auto_roles').select('*').eq('message_id', message_id).execute()
        return response.data if response.data else []
    except Exception as e:
        logger.error(f"[DB Error] get_auto_role_buttons: {e}", exc_info=True)
        return []

async def main():
    async with bot:
        await load_extensions()
        await bot.start(BOT_TOKEN)

if __name__ == "__main__":
    try:
        if BOT_TOKEN is None:
            logger.critical("❌ BOT_TOKEN 환경 변수가 설정되지 않았습니다. Railway의 Variables를 확인해주세요.")
        else:
            asyncio.run(main())
    except discord.errors.LoginFailure:
        logger.critical("❌ 봇 토큰이 잘못되었습니다. Railway의 BOT_TOKEN 환경 변수를 확인해주세요.")
    except Exception as e:
        logger.critical(f"🚨 봇 실행 중 치명적인 오류 발생: {e}", exc_info=True)
