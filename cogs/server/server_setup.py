# cogs/server/server_setup.py (DB 역할 정보 관리 유틸리티 최종본)

import discord
from discord.ext import commands
from discord import app_commands
import logging

from utils.database import save_id_to_db

logger = logging.getLogger(__name__)

# [수정] DB에 저장할 역할 키와 실제 역할 이름의 매핑
ROLE_KEY_MAP = {
    # 관리자/스태프
    "role_admin_total": "里長", # 예시, 실제 역할 이름과 맞추세요
    "role_approval": "公務員",  # 예시
    "role_staff_festival": "祭りの委員",
    # 온보딩
    "role_temp_user": "仮住人",
    "role_guest": "外部の人",
    "role_mention_role_1": "全体通知",
    "role_onboarding_step_1": "온보딩 1단계",
    "role_onboarding_step_2": "온보딩 2단계",
    "role_onboarding_step_3": "온보딩 3단계",
    "role_onboarding_step_4": "온보딩 4단계",
    # 정보
    "role_info_male": "男性",
    "role_info_female": "女性",
    "role_info_age_70s": "70年代生まれ",
    "role_info_age_80s": "80年代生まれ",
    "role_info_age_90s": "90年代生まれ",
    "role_info_age_00s": "00年代生まれ",
    "role_info_age_private": "非公開",
    # 알림
    "role_notify_festival": "祭り",
    "role_notify_voice": "通話",
    "role_notify_friends": "友達",
    "role_notify_disboard": "ディスボード",
    "role_notify_up": "アップ",
    # 게임
    "role_game_minecraft": "マインクラフト",
    "role_game_valorant": "ヴァロラント",
    "role_game_overwatch": "オーバーウォッチ",
    "role_game_lol": "リーグ・オブ・レジェンド",
    "role_game_mahjong": "麻雀",
    "role_game_amongus": "アモングアス",
    "role_game_mh": "モンスターハンター",
    "role_game_genshin": "原神",
    "role_game_apex": "エーペックスレジェンズ",
    "role_game_splatoon": "スプラトゥーン",
    "role_game_gf": "ゴッドフィールド",
    "role_platform_steam": "スチーム",
    "role_platform_smartphone": "スマートフォン",
    "role_platform_switch": "スイッチ",
}

class ServerSetup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("ServerSetup Cog initialized (Role DB Sync Mode).")

    @app_commands.command(name="役割db同期", description="[管理者] サーバーに存在する役割をDBに同期します。")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def sync_roles_to_db(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild
        
        response_messages = ["**[ 役割DB同期 ]**\n"]
        success_count = 0
        fail_count = 0

        server_roles = {role.name: role.id for role in guild.roles}

        for db_key, role_name in ROLE_KEY_MAP.items():
            role_id = server_roles.get(role_name)

            if role_id:
                try:
                    await save_id_to_db(db_key, role_id)
                    response_messages.append(f"✔️ **{role_name}** -> `{db_key}`\n")
                    success_count += 1
                except Exception as e:
                    response_messages.append(f"❌ **{role_name}** DB 저장 오류: {e}\n")
                    fail_count += 1
            else:
                response_messages.append(f"⚠️ **{role_name}** 역할을 찾을 수 없습니다.\n")
                fail_count += 1

        response_messages.append(f"\n✅ 동기화 완료 (성공: {success_count} / 실패: {fail_count})")
        
        description_content = "".join(response_messages)
        embed = discord.Embed(
            title="⚙️ 역할 데이터베이스 동기화 결과",
            description=description_content,
            color=discord.Color.green() if fail_count == 0 else discord.Color.orange()
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"Role DB sync completed. Success: {success_count}, Fail: {fail_count}")

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSetup(bot))
