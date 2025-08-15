# cogs/server/server_setup.py (모든 역할 포함 및 역할 흐름 변경 최종본)

import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Literal

from utils.database import save_id_to_db, load_all_configs_from_db

logger = logging.getLogger(__name__)

# [수정] DB에 저장할 역할 키와 실제 역할 이름의 매핑 (모든 역할 포함)
ROLE_KEY_MAP = {
    # 관리자/스태프
    "role_admin_total": "里長",
    "role_approval": "公務員",
    "role_staff_festival": "祭りの委員",
    
    # 온보딩 및 기본 역할
    "role_guest": "外部の人",       # 서버 참가 시 부여되는 역할
    "role_resident": "住民",       # 자기소개서 승인 후 부여되는 역할
    
    # 알림
    "role_mention_role_1": "全体通知",
    "role_notify_festival": "祭り",
    "role_notify_voice": "通話",
    "role_notify_friends": "友達",
    "role_notify_disboard": "ディスボード",
    "role_notify_up": "アップ",

    # 정보
    "role_info_male": "男性",
    "role_info_female": "女性",
    "role_info_age_70s": "70年代生まれ",
    "role_info_age_80s": "80年代生まれ",
    "role_info_age_90s": "90年代生まれ",
    "role_info_age_00s": "00年代生まれ",
    "role_info_age_private": "非公開",

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

RoleType = Literal[tuple(ROLE_KEY_MAP.keys())]

class ServerSetup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("ServerSetup Cog가 성공적으로 초기화되었습니다.")

    roles_group = app_commands.Group(name="setup-roles", description="서버의 역할을 데이터베이스와 동기화하거나 개별적으로 설정합니다.")

    @roles_group.command(name="sync", description="[管理者] サーバーのすべての役割を名前基準でDBと一括同期します。")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def sync_roles_to_db(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild
        
        synced_roles, missing_roles, error_roles = [], [], []
        server_roles_by_name = {role.name: role.id for role in guild.roles}

        for db_key, role_name in ROLE_KEY_MAP.items():
            role_id = server_roles_by_name.get(role_name)
            if role_id:
                try:
                    await save_id_to_db(db_key, role_id)
                    synced_roles.append(f"・**{role_name}** (`{db_key}`)")
                except Exception as e:
                    error_roles.append(f"・**{role_name}**: `{e}`")
            else:
                missing_roles.append(f"・**{role_name}** (`{db_key}`)")
        
        embed = discord.Embed(
            title="⚙️ 역할 데이터베이스 일괄 동기화 결과",
            color=discord.Color.green() if not missing_roles and not error_roles else discord.Color.orange()
        )
        embed.set_footer(text=f"총 {len(ROLE_KEY_MAP)}개 중 성공: {len(synced_roles)} / 실패: {len(missing_roles) + len(error_roles)}")

        if synced_roles: embed.add_field(name=f"✅ 성공 ({len(synced_roles)}개)", value="\n".join(synced_roles), inline=False)
        if missing_roles: embed.add_field(name=f"⚠️ 역할을 찾을 수 없음 ({len(missing_roles)}개)", value="\n".join(missing_roles), inline=False)
        if error_roles: embed.add_field(name=f"❌ DB 저장 오류 ({len(error_roles)}개)", value="\n".join(error_roles), inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"역할 DB 일괄 동기화 완료: 성공 {len(synced_roles)}, 실패 {len(missing_roles) + len(error_roles)}")

    @roles_group.command(name="set", description="[管理者] 特定の役割一つを選択してDBに設定します。")
    @app_commands.describe(role_type="データベースに保存する役割の種類を選択してください。", role="サーバーに実際に存在する役割を選択してください。")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def set_role_in_db(self, interaction: discord.Interaction, role_type: RoleType, role: discord.Role):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await save_id_to_db(role_type, role.id)
            await load_all_configs_from_db()
            embed = discord.Embed(
                title="✅ 역할 설정 완료",
                description=f"データベースの`{role_type}`キーに{role.mention}役割が正常に連結されました。",
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"개별 역할 설정 중 오류: {e}", exc_info=True)
            embed = discord.Embed(title="❌ 오류 발생", description=f"`{role_type}`役割を設定中にエラーが発生しました。", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSetup(bot))
