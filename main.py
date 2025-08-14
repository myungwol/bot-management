# main.py (최종 수정본 - 기억 복구 기능 추가)

import discord
from discord.ext import commands
import os
import asyncio
import logging

# [수정] system.py의 AutoRoleView를 가져오기 위해 import 경로 조정
from cogs.server.system import AutoRoleView
from utils.database import (get_channel_id_from_db, get_all_channel_configs, 
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

    async def setup_hook(self):
        """ 봇이 시작될 때 뷰(View)를 다시 로드하는 중요한 부분 """
        logger.info("------ [ 自動役割パネルの再生成開始 ] ------")
        panels = await get_all_auto_role_panels()
        if not panels:
            logger.info("ℹ️ 再生成する自動役割パネルがありません。")
        else:
            for panel_config in panels:
                try:
                    buttons_config = await get_auto_role_buttons(panel_config['message_id'])
                    view = AutoRoleView(buttons_config)
                    self.add_view(view, message_id=panel_config['message_id'])
                    logger.info(f"✅ 自動役割パネル (ID: {panel_config['message_id']}) のViewを再登録しました。")
                except Exception as e:
                    logger.error(f"❌ 自動役割パネル (ID: {panel_config['message_id']}) の再生成中にエラー: {e}")
        logger.info("------ [ 自動役割パネルの再生成完了 ] ------")

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

    await get_all_channel_configs()
    logger.info("✅ 모든 채널 설정이 캐시되었습니다.")
    
    await regenerate_all_panels()

async def regenerate_all_panels():
    """DB에 저장된 채널 ID를 기반으로 모든 등록된 패널 메시지를 재생성합니다."""
    logger.info("------ [ すべてのパネル再生成開始 ] ------")
    panel_tasks = []
    
    panel_configs = {
        "Commerce": "commerce_panel_channel_id",
        "Nicknames": "nickname_panel_channel_id",
        "Onboarding": "onboarding_panel_channel_id",
        "Fishing": "fishing_panel_channel_id",
        "UserProfile": "inventory_panel_channel_id",
    }

    panel_regeneration_map = {
        "Commerce": "regenerate_commerce_panel",
        "Nicknames": "regenerate_panel",
        "Onboarding": "regenerate_onboarding_panel",
        "Fishing": "regenerate_fishing_panel",
        "UserProfile": "regenerate_inventory_panel",
    }

    for cog_name, channel_key in panel_configs.items():
        cog = bot.get_cog(cog_name)
        channel_id = await get_channel_id_from_db(channel_key)
        
        if cog and channel_id:
            channel = bot.get_channel(channel_id)
            if channel:
                regen_func_name = panel_regeneration_map.get(cog_name)
                if hasattr(cog, regen_func_name):
                    regen_func = getattr(cog, regen_func_name)
                    panel_tasks.append(regen_func(channel))
                    logger.info(f"🔄 {cog_name} パネル再生中: {channel.name}")
            else:
                logger.warning(f"❌ {cog_name} パネルチャンネルが見つかりません: {channel_id}")
        elif not channel_id:
            logger.info(f"⚠️ {cog_name} パネルチャンネルIDがDBに設定されていません。")

    if panel_tasks:
        await asyncio.gather(*panel_tasks, return_exceptions=True)
    else:
        logger.info("ℹ️ 再生成するパネル作業がありません。")
    logger.info("------ [ すべてのパネル再生成完了 ] ------")

async def load_extensions():
    logger.info("------ [ Cog ロード開始 ] ------")
    for folder in os.listdir('./cogs'):
        folder_path = os.path.join('cogs', folder)
        if os.path.isdir(folder_path):
            for filename in os.listdir(folder_path):
                if filename.endswith('.py') and not filename.startswith('__'):
                    try:
                        await bot.load_extension(f'cogs.{folder}.{filename[:-3]}')
                        logger.info(f'✅ Cog ロード成功: {folder}/{filename}')
                    except Exception as e:
                        logger.error(f'❌ Cog ロード失敗: {folder}/{filename} | エラー: {e}', exc_info=True)
    logger.info("------ [ Cog ロード完了 ] ------")

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
