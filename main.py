# main.py

import discord
from discord.ext import commands
import os
import asyncio

# utils 폴더에서 데이터베이스 함수 임포트
from utils.database import get_channel_id_from_db, get_all_channel_configs

# --- 봇 기본 설정 ---
# 봇 토큰은 환경 변수에서 안전하게 가져옵니다.
BOT_TOKEN = os.environ['BOT_TOKEN']

# 필요한 인텐트 설정
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True

# 봇 인스턴스 생성
bot = commands.Bot(command_prefix="/", intents=intents)

# --- 봇 이벤트 ---
@bot.event
async def on_ready():
    """
    봇이 Discord에 성공적으로 로그인했을 때 호출됩니다.
    슬래시 명령어 동기화 및 패널 재생성 작업을 수행합니다.
    """
    print(f'✅ {bot.user.name}(이)가 성공적으로 로그인했습니다.')
    print(f'✅ 봇 ID: {bot.user.id}')
    print('------')
    try:
        synced = await bot.tree.sync()
        print(f'✅ {len(synced)}개의 슬래시 명령어를 성공적으로 동기화했습니다.')
    except Exception as e:
        print(f'❌ 명령어 동기화 중 오류가 발생했습니다: {e}')

    # 모든 채널 설정을 미리 캐시 (성능 최적화)
    await get_all_channel_configs()
    print("✅ 모든 채널 설정이 캐시되었습니다.")

    # 모든 패널 메시지를 재생성 (봇 재시작 시 기존 패널이 사라지는 것을 방지)
    await regenerate_all_panels()

# --- Cog 로드 함수 ---
async def load_extensions():
    """
    'cogs' 폴더 내의 모든 Cog를 로드합니다.
    """
    print("------ [ Cog ロード開始 ] ------")
    for folder in os.listdir('./cogs'):
        folder_path = os.path.join('cogs', folder)
        if os.path.isdir(folder_path):
            for filename in os.listdir(folder_path):
                if filename.endswith('.py') and not filename.startswith('__'):
                    try:
                        await bot.load_extension(f'cogs.{folder}.{filename[:-3]}')
                        print(f'✅ Cog ロード成功: {folder}/{filename}')
                    except Exception as e:
                        print(f'❌ Cog ロード失敗: {folder}/{filename} | エラー: {e}')
    print("------ [ Cog ロード完了 ] ------")

# --- 모든 패널을 재생성하는 함수 (봇 시작 시 호출) ---
async def regenerate_all_panels():
    """
    Supabase에 저장된 채널 ID를 기반으로 모든 등록된 패널 메시지를 재생성합니다.
    """
    print("------ [ すべてのパネル再生成開始 ] ------")
    panel_tasks = [] # 병렬 실행을 위한 태스크 리스트

    # DB에서 각 패널의 채널 ID를 가져옵니다 (캐시된 값 사용)
    COMMERCE_PANEL_CHANNEL_ID = await get_channel_id_from_db("commerce_panel_channel_id")
    NICKNAME_PANEL_CHANNEL_ID = await get_channel_id_from_db("nickname_panel_channel_id")
    ONBOARDING_PANEL_CHANNEL_ID = await get_channel_id_from_db("onboarding_panel_channel_id")
    FISHING_PANEL_CHANNEL_ID = await get_channel_id_from_db("fishing_panel_channel_id")
    INVENTORY_PANEL_CHANNEL_ID = await get_channel_id_from_db("inventory_panel_channel_id")

    # 각 Cog에 접근하여 패널 재생성 함수 호출
    commerce_cog = bot.get_cog("Commerce")
    if commerce_cog and COMMERCE_PANEL_CHANNEL_ID:
        channel = bot.get_channel(COMMERCE_PANEL_CHANNEL_ID)
        if channel:
            panel_tasks.append(commerce_cog.regenerate_commerce_panel(channel))
            print(f"🔄 Commerce パネル再生中: {channel.name}")
        else:
            print(f"❌ Commerce パネルチャンネルが見つかりません: {COMMERCE_PANEL_CHANNEL_ID}")
    elif not COMMERCE_PANEL_CHANNEL_ID:
        print("⚠️ Commerce パネルチャンネルIDがDBに設定されていません。")

    nicknames_cog = bot.get_cog("Nicknames")
    if nicknames_cog and NICKNAME_PANEL_CHANNEL_ID:
        channel = bot.get_channel(NICKNAME_PANEL_CHANNEL_ID)
        if channel:
            panel_tasks.append(nicknames_cog.regenerate_panel(channel))
            print(f"🔄 Nickname パネル再生中: {channel.name}")
        else:
            print(f"❌ Nickname パネルチャンネルが見つかりません: {NICKNAME_PANEL_CHANNEL_ID}")
    elif not NICKNAME_PANEL_CHANNEL_ID:
        print("⚠️ Nickname パネルチャンネルIDがDBに設定されていません。")

    onboarding_cog = bot.get_cog("Onboarding")
    if onboarding_cog and ONBOARDING_PANEL_CHANNEL_ID:
        channel = bot.get_channel(ONBOARDING_PANEL_CHANNEL_ID)
        if channel:
            panel_tasks.append(onboarding_cog.regenerate_onboarding_panel(channel))
            print(f"🔄 Onboarding パネル再生中: {channel.name}")
        else:
            print(f"❌ Onboarding パネルチャンネルが見つかりません: {ONBOARDING_PANEL_CHANNEL_ID}")
    elif not ONBOARDING_PANEL_CHANNEL_ID:
        print("⚠️ Onboarding パネルチャンネルIDがDBに設定されていません。")

    fishing_cog = bot.get_cog("Fishing")
    if fishing_cog and FISHING_PANEL_CHANNEL_ID:
        channel = bot.get_channel(FISHING_PANEL_CHANNEL_ID)
        if channel:
            panel_tasks.append(fishing_cog.regenerate_fishing_panel(channel))
            print(f"🔄 Fishing パネル再生中: {channel.name}")
        else:
            print(f"❌ Fishing パネルチャンネルが見つかりません: {FISHING_PANEL_CHANNEL_ID}")
    elif not FISHING_PANEL_CHANNEL_ID:
        print("⚠️ Fishing パネルチャンネルIDがDBに設定されていません。")

    user_profile_cog = bot.get_cog("UserProfile")
    if user_profile_cog and INVENTORY_PANEL_CHANNEL_ID:
        channel = bot.get_channel(INVENTORY_PANEL_CHANNEL_ID)
        if channel:
            panel_tasks.append(user_profile_cog.regenerate_inventory_panel(channel))
            print(f"🔄 Inventory パネル再生中: {channel.name}")
        else:
            print(f"❌ Inventory パネルチャンネルが見つかりません: {INVENTORY_PANEL_CHANNEL_ID}")
    elif not INVENTORY_PANEL_CHANNEL_ID:
        print("⚠️ Inventory パネルチャンネルIDがDBに設定されていません。")

    if panel_tasks:
        results = await asyncio.gather(*panel_tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                print(f"❌ パネル再生中にエラー発生 (タスク {i+1}): {type(result).__name__} - {result}")
                import traceback
                traceback.print_exception(type(result), result, result.__traceback__)
    else:
        print("ℹ️ 再生成するパネル作業がありません。")
    print("------ [ すべてのパネル再生成完了 ] ------")

# --- 메인 실행 함수 ---
async def main():
    """
    봇의 비동기 메인 실행 함수입니다.
    Cog 로드, keep-alive 서버 시작, 봇 로그인 등을 처리합니다.
    """
    async with bot:
        await load_extensions() # Cog 로드
        print("✅ Keep-alive ウェブサーバーがバックグラウンドで実行中です。")
        await bot.start(BOT_TOKEN) # 봇 로그인 및 실행

# --- 프로그램 시작점 ---
if __name__ == "__main__":
    asyncio.run(main())
