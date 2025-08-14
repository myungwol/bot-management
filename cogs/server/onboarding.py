# cogs/server/onboarding.py (자동 재생성 기능이 적용된 최종본)

import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
import logging
import re
from datetime import datetime
import time

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 데이터베이스 함수 임포트
from utils.database import (
    get_panel_id, save_panel_id, get_channel_id_from_db, 
    get_role_id, get_auto_role_mappings, get_cooldown, set_cooldown
)

# 설정값
INTRODUCTION_COOLDOWN_SECONDS = 10 * 60
GUIDE_GIF_URL = "https://media.discordapp.net/attachments/1402228452106436689/1404406045635252266/welcome.gif?ex=689b128d&is=6899c10d&hm=e0226740554e16e44a6d8034c99c247ac174c38f53ea998aa0de600153e1c495&="
GUIDE_PAGES = [
    {"type": "info", "title": "🏡 Dico森へようこそ！ ✨", "description": "➡️ 次に進むには、下の「次へ」ボタンを押してください 📩"},
    {"type": "action", "title": "ボット紹介", "description": "**下のボタンを押すと、次の段階である「里の掟」チャンネルを閲覧する権限が付与されます。**", "button_label": "ボットの紹介を確認しました", "role_key": "role_onboarding_step_1"},
    {"type": "action", "title": "里の掟", "description": "「里の掟」チャンネルが閲覧可能になりました。\n\n## <#1404410157504397322>\n\n上記のチャンネルに移動し、すべての掟をよく確認してください。", "button_label": "掟を確認しました", "role_key": "role_onboarding_step_2"},
    {"type": "action", "title": "里の地図", "description": "次は、里のチャンネルについての案内です。\n\n## <#1404410171689664552>\n\nですべてのチャンネルの役割を確認してください。", "button_label": "地図を確認しました", "role_key": "role_onboarding_step_3"},
    {"type": "action", "title": "依頼掲示板", "description": "次は依頼掲示板の確認です。\n\n## <#1404410186562666546>", "button_label": "依頼掲示板を確認しました", "role_key": "role_onboarding_step_4"},
    {"type": "intro", "title": "住人登録票 (最終段階)", "description": "すべての案内を確認しました！いよいよ最終段階です。\n\n**下のボタンを押して、住人登録票を作成してください。**\n登録票が公務員によって承認されると、正式にすべての場所が利用可能になります。", "rules": "・性別の記載は必須です\n・年齢を非公開にしたい場合は、公務員に個別にご連絡ください\n・名前に特殊文字は使用できません\n・漢字は4文字まで、ひらがな・カタカナ・英数字は合わせて8文字まで可能です\n・不適切な名前は拒否される場合があります\n・未記入の項目がある場合、拒否されることがあります\n・参加経路も必ずご記入ください。（例：Disboard、〇〇からの招待など）"}
]

# --- View / Modal 클래스들 (이전과 동일) ---
# ... (RejectionReasonModal, IntroductionModal, ApprovalView, OnboardingView, OnboardingPanelView 클래스는 이전과 동일)

# --- 메인 Cog 클래스 ---
class Onboarding(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(OnboardingPanelView())
        # ApprovalView는 동적으로 생성되므로, __init__에서 더 이상 add_view할 필요가 없습니다.
        # self.bot.add_view(ApprovalView(...)) -> 이 줄은 삭제하거나 주석 처리하는 것이 좋습니다.
        self.auto_role_mappings: list = []
        self.panel_channel_id: int | None = None
        self.approval_channel_id: int | None = None
        self.introduction_channel_id: int | None = None
        self.rejection_log_channel_id: int | None = None
        self.new_welcome_channel_id: int | None = None
        self.approval_role_id: int | None = None
        self.guest_role_id: int | None = None
        self.temp_user_role_id: int | None = None
        self.mention_role_id_1: int | None = None
        logger.info("Onboarding Cog initialized.")

    async def cog_load(self):
        await self.load_onboarding_configs()

    async def load_onboarding_configs(self):
        self.auto_role_mappings = get_auto_role_mappings()
        self.panel_channel_id = await get_channel_id_from_db("onboarding_panel_channel_id")
        self.approval_channel_id = await get_channel_id_from_db("onboarding_approval_channel_id")
        self.introduction_channel_id = await get_channel_id_from_db("introduction_channel_id")
        self.rejection_log_channel_id = await get_channel_id_from_db("introduction_rejection_log_channel_id")
        self.new_welcome_channel_id = await get_channel_id_from_db("new_welcome_channel_id")
        self.approval_role_id = get_role_id("approval_role")
        self.guest_role_id = get_role_id("guest_role")
        self.temp_user_role_id = get_role_id("temp_user_role")
        self.mention_role_id_1 = get_role_id("mention_role_1")
        logger.info("[Onboarding Cog] Loaded configurations.")

    # [수정] main.py와 호환되도록 자동 재생성 함수로 변경
    async def regenerate_panel(self):
        # cog_load에서 불러온 채널 ID를 사용합니다.
        if self.panel_channel_id and (channel := self.bot.get_channel(self.panel_channel_id)):
            old_id = await get_panel_id("onboarding")
            if old_id:
                try:
                    old_message = await channel.fetch_message(old_id)
                    await old_message.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass # 메시지가 없으면 그냥 넘어감
            
            embed = discord.Embed(title="🏡 新米住人の方へ", description="この里へようこそ！\n下のボタンを押して、里での暮らし方を確認し、住人登録を始めましょう。", color=discord.Color.gold())
            msg = await channel.send(embed=embed, view=OnboardingPanelView())
            await save_panel_id("onboarding", msg.id)
            logger.info(f"✅ Onboarding panel auto-regenerated in channel {channel.name}")
        else:
            logger.info("ℹ️ Onboarding panel channel not set, skipping auto-regeneration.")

    @app_commands.command(name="オンボーディングパネル設置", description="서버 안내와 자기소개를 통합한 패널을 설치합니다.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_onboarding_panel_command(self, interaction: discord.Interaction):
        if self.panel_channel_id is None:
            return await interaction.response.send_message("오류: 패널 설치 채널이 DB에 설정되어 있지 않습니다.", ephemeral=True)
        if interaction.channel.id != self.panel_channel_id:
            return await interaction.response.send_message(f"이 명령어는 <#{self.panel_channel_id}> 채널에서만 사용할 수 있습니다.", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        try:
            # 이제 이 명령어는 자동 재생성 함수를 호출하기만 하면 됩니다.
            await self.regenerate_panel()
            await interaction.followup.send("온보딩 패널을 성공적으로 설치/재설치했습니다.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error during onboarding panel setup command: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 패널 설치 중 오류가 발생했습니다: {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Onboarding(bot))
