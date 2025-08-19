# bot-management/cogs/admin/panel.py (게임 봇 패널 설치 요청 기능)

import discord
from discord.ext import commands
from discord import app_commands
import logging
import time

# [🔴 핵심] 관리 봇의 utils 폴더에서 필요한 것들을 가져옵니다.
# 이 경로가 실제 프로젝트 구조와 맞는지 확인해주세요.
from utils.ui_defaults import SETUP_COMMAND_MAP
from utils.database import supabase, get_id

logger = logging.getLogger(__name__)

# SETUP_COMMAND_MAP에서 'panel' 또는 'channel' 타입인 것들만 필터링하여 선택지로 만듭니다.
# 게임 봇 패널도 여기에 포함됩니다.
panel_choices = [
    app_commands.Choice(name=info["friendly_name"], value=key)
    for key, info in SETUP_COMMAND_MAP.items() 
    if info["type"] in ["panel", "channel"] and "panel" in key
]

class PanelManagement(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("PanelManagement Cog가 성공적으로 초기화되었습니다.")

    panel_group = app_commands.Group(name="panel", description="UI 패널을 관리합니다.")

    @panel_group.command(name="install", description="[관리자] 선택한 패널을 해당 채널에 설치/재설치합니다.")
    @app_commands.describe(panel_key="설치할 패널의 종류를 선택하세요.")
    @app_commands.choices(panel_key=panel_choices) # 동적으로 생성된 선택지 사용
    @app_commands.checks.has_permissions(administrator=True)
    async def install_panel(self, interaction: discord.Interaction, panel_key: app_commands.Choice[str]):
        """
        선택한 패널의 설치/재설치를 요청하는 명령어입니다.
        이 명령어는 DB에 요청만 기록하며, 실제 설치는 각 봇이 담당합니다.
        """
        await interaction.response.defer(ephemeral=True)

        panel_info = SETUP_COMMAND_MAP.get(panel_key.value)
        if not panel_info:
            return await interaction.followup.send("❌ 잘못된 패널 정보입니다.", ephemeral=True)
        
        # 패널이 설치될 채널 ID를 DB에서 가져옵니다.
        channel_id_key = panel_info.get("key")
        channel_id = get_id(channel_id_key)
        if not channel_id or not (channel := self.bot.get_channel(channel_id)):
            return await interaction.followup.send(
                f"⚠️ **{panel_key.name}** 패널의 채널이 아직 설정되지 않았습니다.\n"
                f"`/setup channel` 명령어로 먼저 채널을 설정해주세요.", ephemeral=True)
        
        # DB에 요청을 기록할 키
        db_request_key = f"panel_regenerate_request_{panel_key.value}"
        
        try:
            # 1. DB에 패널 재생성 요청 시간을 기록합니다.
            # 게임 봇과 관리 봇 모두 이 DB 값을 보고 자신의 패널을 생성/업데이트합니다.
            await supabase.table('bot_configs').upsert({
                "config_key": db_request_key,
                "config_value": f'"{time.time()}"'
            }).execute()

            # 2. 만약 이 패널이 '관리 봇'의 기능이라면, 관리 봇이 직접 즉시 설치합니다.
            cog_name = panel_info.get("cog_name")
            target_cog = self.bot.get_cog(cog_name)
            if target_cog and hasattr(target_cog, 'regenerate_panel'):
                # 관리 봇의 regenerate_panel은 panel_key 인자를 받지 않을 수 있으므로, panel_key 없이 호출
                await target_cog.regenerate_panel(channel)
                await interaction.followup.send(
                    f"✅ **{panel_key.name}** 패널을 {channel.mention} 채널에 즉시 재설치했습니다.", ephemeral=True)
            else:
                # 이 패널이 '게임 봇'의 기능이라면, DB 요청만으로 충분합니다.
                await interaction.followup.send(
                    f"✅ **{panel_key.name}** 패널에 대한 재설치 요청을 성공적으로 보냈습니다.\n"
                    f"게임 봇이 곧 해당 채널에 패널을 설치할 것입니다.", ephemeral=True)

        except Exception as e:
            logger.error(f"패널 설치 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send("❌ 패널 설치 중 오류가 발생했습니다.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(PanelManagement(bot))
