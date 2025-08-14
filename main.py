# main.py (수정 제안본)

import discord
from discord.ext import commands
import os
import asyncio
import logging

# system.py의 AutoRoleView를 가져오기 위해 import 경로 조정
from cogs.server.system import AutoRoleView
from utils.database import (get_all_channel_configs_as_dict, # 수정: 딕셔너리로 한번에 가져오는 함수
                           get_all_auto_role_panels, get_auto_role_buttons)

# 로깅 기본 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 봇 기본 설정 ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.message_content = True # on_message 이벤트를 위해 추가

class MyBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 봇의 모든 채널 설정을 저장할 딕셔너리
        self.channel_configs = {}

    async def setup_hook(self):
        """ 봇이 시작될 때 뷰(View)를 다시 로드하는 중요한 부분 """
        logger.info("------ [ 자동 역할 패널 재생성 시작 ] ------")
        panels = await get_all_auto_role_panels()
        if not panels:
            logger.info("ℹ️ 재생성할 자동 역할 패널이 없습니다.")
        else:
            for panel_config in panels:
                try:
                    # 패널에 속한 버튼 정보들을 가져옵니다.
                    buttons_config = await get_auto_role_buttons(panel_config['message_id'])
                    # 가져온 버튼 정보로 View를 생성합니다.
                    view = AutoRoleView(buttons_config)
                    # 생성된 View를 봇에 다시 등록합니다. message_id를 꼭 지정해야 합니다.
                    self.add_view(view, message_id=panel_config['message_id'])
                    logger.info(f"✅ 자동 역할 패널 (ID: {panel_config['message_id']})의 View를 재등록했습니다.")
                except Exception as e:
                    logger.error(f"❌ 자동 역할 패널 (ID: {panel_config['message_id']}) 재생성 중 오류: {e}")
        logger.info("------ [ 자동 역할 패널 재생성 완료 ] ------")

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

    # [수정] 봇 시작 시 모든 채널 설정을 한번만 DB에서 가져와 봇 인스턴스에 저장
    bot.channel_configs = await get_all_channel_configs_as_dict()
    if bot.channel_configs:
        logger.info("✅ 모든 채널 설정이 캐시되었습니다.")
    else:
        logger.warning("⚠️ DB에서 채널 설정을 가져오지 못했거나 설정이 없습니다.")
    
    # [수정] 캐시된 채널 설정을 인자로 전달하여 패널 재생성 함수 호출
    await regenerate_all_panels(bot.channel_configs)

async def regenerate_all_panels(channel_configs: dict):
    """
    각 Cog에 정의된 정보를 기반으로 모든 패널 메시지를 재생성합니다.
    [수정] 더 이상 main.py에 패널 정보를 하드코딩하지 않습니다.
    """
    logger.info("------ [ 모든 기능 패널 재생성 시작 ] ------")
    panel_tasks = []

    # 봇에 로드된 모든 Cog를 순회합니다.
    for cog_name, cog in bot.cogs.items():
        # [개선] 각 Cog가 패널 재생성에 필요한 정보를 스스로 갖도록 설계
        # 예를 들어, Cog 내에 `get_panel_info` 라는 함수가 있는지 확인
        if not hasattr(cog, 'get_panel_info'):
            continue

        panel_info = cog.get_panel_info()
        channel_key = panel_info.get("channel_key")
        regenerate_func_name = panel_info.get("regenerate_func_name")

        if not channel_key or not regenerate_func_name:
            continue
            
        # [수정] DB를 다시 조회하는 대신, on_ready에서 캐시한 설정값을 사용
        channel_id = channel_configs.get(channel_key)
        
        if channel_id:
            channel = bot.get_channel(channel_id)
            if channel:
                # Cog에 패널 재생성 함수가 있는지 확인
                if hasattr(cog, regenerate_func_name):
                    regen_func = getattr(cog, regenerate_func_name)
                    # 재생성 작업을 비동기 태스크 목록에 추가
                    panel_tasks.append(regen_func(channel))
                    logger.info(f"🔄 '{cog_name}'의 패널을 '{channel.name}' 채널에 재생성 준비 완료.")
                else:
                    logger.warning(f"❓ '{cog_name}' Cog에 '{regenerate_func_name}' 함수가 정의되지 않았습니다.")
            else:
                logger.warning(f"❌ '{cog_name}'의 패널 채널을 찾을 수 없습니다 (ID: {channel_id}). 서버에서 삭제되었을 수 있습니다.")
        else:
            logger.info(f"ℹ️ '{cog_name}'의 패널 채널 ID가 DB에 설정되지 않았습니다 (Key: {channel_key}).")

    if panel_tasks:
        # asyncio.gather를 사용하여 모든 패널 재생성 작업을 동시에 실행
        results = await asyncio.gather(*panel_tasks, return_exceptions=True)
        
        # [수정] gather 결과를 확인하여 실패한 작업을 로깅
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                # 어떤 태스크에서 에러가 났는지 식별하기 위해 추가적인 정보가 필요할 수 있습니다.
                # 여기서는 간단히 에러 내용만 로깅합니다.
                logger.error(f"❌ 패널 재생성 작업 중 오류 발생: {result}", exc_info=result)
    else:
        logger.info("ℹ️ 재생성할 패널 작업이 없습니다.")
        
    logger.info("------ [ 모든 기능 패널 재생성 완료 ] ------")

async def load_extensions():
    logger.info("------ [ Cog 로드 시작 ] ------")
    # ./cogs 디렉토리의 모든 하위 폴더를 순회
    for folder in os.listdir('./cogs'):
        folder_path = os.path.join('cogs', folder)
        if os.path.isdir(folder_path):
            # 하위 폴더 내의 파이썬 파일을 순회
            for filename in os.listdir(folder_path):
                if filename.endswith('.py') and not filename.startswith('__'):
                    try:
                        # f'cogs.폴더명.파일명' 형태로 확장자를 로드
                        await bot.load_extension(f'cogs.{folder}.{filename[:-3]}')
                        logger.info(f'✅ Cog 로드 성공: {folder}/{filename}')
                    except Exception as e:
                        logger.error(f'❌ Cog 로드 실패: {folder}/{filename} | 오류: {e}', exc_info=True)
    logger.info("------ [ Cog 로드 완료 ] ------")

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
