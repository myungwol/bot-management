# cogs/server/server_setup.py (유지보수성 및 편의성 대폭 개선 최종본)

import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Literal # [신규] 명령어 선택지를 위해 추가

from utils.database import save_id_to_db, load_all_configs_from_db

logger = logging.getLogger(__name__)

# [개선] DB에 저장할 역할 키와 실제 역할 이름의 매핑 (Cog 외부로 이동하여 가독성 향상)
# 이 딕셔너리는 '/setup roles sync' 명령어에서 사용됩니다.
ROLE_KEY_MAP = {
    # 관리자/스태프
    "role_admin_total": "里長",
    "role_approval": "公務員",
    "role_staff_festival": "祭りの委員",
    # 온보딩
    "role_temp_user": "仮住人",
    "role_guest": "外部の人",
    "role_mention_role_1": "全体通知",
    # ... (다른 모든 역할들)
}

# [신규] '/setup roles set' 명령어의 선택지를 만들기 위해 ROLE_KEY_MAP의 키를 Literal 타입으로 변환
RoleType = Literal[tuple(ROLE_KEY_MAP.keys())]


class ServerSetup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("ServerSetup Cog가 성공적으로 초기화되었습니다.")

    # --- [신규] 명령어 그룹 생성 ---
    # /setup roles sync, /setup roles set 과 같이 명령어를 구조화합니다.
    roles_group = app_commands.Group(name="setup-roles", description="서버의 역할을 데이터베이스와 동기화하거나 개별적으로 설정합니다.")

    # --- [개선] 기존의 전체 동기화 명령어 ---
    @roles_group.command(name="sync", description="[관리자] 서버의 모든 역할을 이름 기준으로 DB와 일괄 동기화합니다.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def sync_roles_to_db(self, interaction: discord.Interaction):
        """
        ROLE_KEY_MAP에 정의된 역할 이름과 일치하는 서버의 역할을 찾아 DB에 일괄 저장합니다.
        초기 설정 시에 매우 유용합니다.
        """
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
        
        # [개선] 결과를 Embed Field로 나누어 표시하여 가독성 향상
        embed = discord.Embed(
            title="⚙️ 역할 데이터베이스 일괄 동기화 결과",
            color=discord.Color.green() if not missing_roles and not error_roles else discord.Color.orange()
        )
        embed.set_footer(text=f"총 {len(ROLE_KEY_MAP)}개 중 성공: {len(synced_roles)} / 실패: {len(missing_roles) + len(error_roles)}")

        if synced_roles:
            embed.add_field(name=f"✅ 성공 ({len(synced_roles)}개)", value="\n".join(synced_roles), inline=False)
        if missing_roles:
            embed.add_field(name=f"⚠️ 역할을 찾을 수 없음 ({len(missing_roles)}개)", value="\n".join(missing_roles), inline=False)
        if error_roles:
            embed.add_field(name=f"❌ DB 저장 오류 ({len(error_roles)}개)", value="\n".join(error_roles), inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)
        logger.info(f"역할 DB 일괄 동기화 완료: 성공 {len(synced_roles)}, 실패 {len(missing_roles) + len(error_roles)}")


    # --- [신규] 개별 역할 설정 명령어 ---
    @roles_group.command(name="set", description="[관리자] 특정 역할 하나를 선택하여 DB에 설정합니다.")
    @app_commands.describe(
        role_type="데이터베이스에 저장할 역할의 종류를 선택하세요.",
        role="서버에 실제 존재하는 역할을 선택하세요."
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    async def set_role_in_db(self, interaction: discord.Interaction, role_type: RoleType, role: discord.Role):
        """
        역할 이름이 바뀌거나 새로 추가되었을 때 코드 수정 없이 DB를 업데이트할 수 있습니다.
        """
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await save_id_to_db(role_type, role.id)
            
            # [개선] 설정이 변경되었으므로, DB 캐시를 다시 로드하여 즉시 반영합니다.
            await load_all_configs_from_db()

            embed = discord.Embed(
                title="✅ 역할 설정 완료",
                description=f"데이터베이스의 `{role_type}` 키에 {role.mention} 역할이 성공적으로 연결되었습니다.",
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            logger.info(f"개별 역할 설정 완료: '{role_type}' -> '{role.name}' ({role.id})")

        except Exception as e:
            logger.error(f"개별 역할 설정 중 오류 발생: {e}", exc_info=True)
            embed = discord.Embed(
                title="❌ 오류 발생",
                description=f"`{role_type}` 역할을 설정하는 중에 오류가 발생했습니다. 봇 로그를 확인해주세요.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSetup(bot))
