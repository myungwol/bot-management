# cogs/server/server_setup.py (역할 DB 저장 기능만 남긴 최종본)

import discord
from discord.ext import commands
from discord import app_commands
import logging

# 데이터베이스 함수 임포트
# [수정] save_channel_id_to_db -> save_role_id_to_db 같은 명확한 이름으로 변경 가정
# 만약 utils/database.py에 역할 저장 함수가 save_channel_id_to_db로 되어있다면 그대로 사용
from utils.database import save_channel_id_to_db as save_role_id_to_db

# 로깅 설정
logger = logging.getLogger(__name__)

# 역할 구조 (데이터베이스 키와 실제 역할 이름을 매핑)
ROLE_STRUCTURE = {
    # 'db_key': '실제 역할 이름'
    "staff_mayor": "里長",
    "staff_deputy": "助役",
    "staff_police": "お巡り",
    "staff_festival": "祭りの委員",
    "staff_pr": "広報係",
    "staff_design": "意匠係",
    "staff_clerk": "書記",
    "staff_office": "役場の職員",
    "staff_general": "職員",
    "resident_tier1": "1等級住民",
    "resident_tier2": "2等級住民",
    "resident_tier3": "3等級住民",
    "resident_general": "住民",
    "resident_outsider": "外部の人",
    "info_male": "男性",
    "info_female": "女性",
    "info_private": "非公開",
    "info_age_70s": "70年代生まれ",
    "info_age_80s": "80年代生まれ",
    "info_age_90s": "90年代生まれ",
    "info_age_00s": "00年代生まれ",
    "notify_voice": "通話",
    "notify_friends": "友達",
    "notify_disboard": "ディスボード",
    "notify_up": "アップ",
    "game_minecraft": "マインクラフト",
    "game_valorant": "ヴァロラント",
    "game_overwatch": "オーバーウォッチ",
    "game_lol": "リーグ・オブ・レジェンド",
    "game_mahjong": "麻雀",
    "game_amongus": "アモングアス",
    "game_mh": "モンスターハンター",
    "game_genshin": "原神",
    "game_apex": "エーペックスレジェンズ",
    "game_splatoon": "スプラトゥーン",
    "game_gf": "ゴッドフィールド",
    "platform_steam": "スチーム",
    "platform_smartphone": "スマートフォン",
    "platform_switch": "スイッチ",
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

        # 서버에 있는 모든 역할 목록을 한 번만 가져옴
        server_roles = {role.name: role.id for role in guild.roles}

        for db_key, role_name in ROLE_STRUCTURE.items():
            # 서버 역할 목록에서 이름으로 역할 ID를 찾음
            role_id = server_roles.get(role_name)

            if role_id:
                try:
                    # DB에 역할 ID 저장 (데이터베이스 키 형식에 맞게 'role_' 접두사 추가)
                    full_db_key = f"role_{db_key}"
                    await save_role_id_to_db(full_db_key, role_id)
                    response_messages.append(f"✔️ **{role_name}** 役割をDBに同期しました。(ID: `{role_id}`)\n")
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to save role ID for '{role_name}' to DB: {e}", exc_info=True)
                    response_messages.append(f"❌ **{role_name}** 役割のDB保存中にエラーが発生しました: {e}\n")
                    fail_count += 1
            else:
                # 서버에 해당 이름의 역할이 없는 경우
                response_messages.append(f"⚠️ **{role_name}** 役割がサーバーに見つかりません。スキップします。\n")
                fail_count += 1

        response_messages.append(f"\n✅ 同期完了 (成功: {success_count}件, 失敗/スキップ: {fail_count}件)")
        
        description_content = "".join(response_messages)
        embed = discord.Embed(
            title="⚙️ 役割データベース同期結果",
            description=description_content,
            color=discord.Color.green() if fail_count == 0 else discord.Color.orange()
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"Role DB sync completed for guild {guild.id}. Success: {success_count}, Failed/Skipped: {fail_count}")

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSetup(bot))
