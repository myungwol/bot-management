# cogs/server/server_setup.py

import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import List
from math import ceil

from utils.database import save_id_to_db, load_channel_ids_from_db, get_config

logger = logging.getLogger(__name__)

class ServerSetup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("ServerSetup Cog가 성공적으로 초기화되었습니다.")

    roles_group = app_commands.Group(name="setup-roles", description="サーバーの役割をデータベースと同期したり、個別に設定します。")

    @roles_group.command(name="sync", description="[管理者] サーバーのすべての役割を名前基準でDBと一括同期します。")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def sync_roles_to_db(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild
        
        # [수정] DB에서 역할 키 맵을 불러옵니다.
        role_key_map = get_config("ROLE_KEY_MAP", {})
        if not role_key_map:
            await interaction.followup.send("❌ `ROLE_KEY_MAP` 설정이 데이터베이스에 없습니다. 관리자에게 문의하세요.", ephemeral=True)
            return

        synced_roles, missing_roles, error_roles = [], [], []
        server_roles_by_name = {role.name: role.id for role in guild.roles}
        
        # [수정] 새로운 역할 맵 구조에 맞게 반복문 변경
        for db_key, role_name in role_key_map.items():
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
            title="⚙️ 役割データベース一括同期の結果",
            color=discord.Color.green() if not missing_roles and not error_roles else discord.Color.orange()
        )
        embed.set_footer(text=f"총 {len(role_key_map)}개 중 성공: {len(synced_roles)} / 실패: {len(missing_roles) + len(error_roles)}")

        CHUNK_SIZE = 20
        if synced_roles:
            for i in range(0, len(synced_roles), CHUNK_SIZE):
                chunk = synced_roles[i:i + CHUNK_SIZE]
                embed.add_field(name=f"✅ 成功 ({len(synced_roles)}개)", value="\n".join(chunk), inline=False)
        if missing_roles:
            for i in range(0, len(missing_roles), CHUNK_SIZE):
                chunk = missing_roles[i:i + CHUNK_SIZE]
                embed.add_field(name=f"⚠️ 役割が見つかりません ({len(missing_roles)}개)", value="\n".join(chunk), inline=False)
        if error_roles:
            embed.add_field(name=f"❌ DB保存エラー ({len(error_roles)}개)", value="\n".join(error_roles), inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    async def role_type_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        role_key_map = get_config("ROLE_KEY_MAP", {})
        keys = role_key_map.keys()
        filtered_keys = [key for key in keys if current.lower() in key.lower()]
        return [app_commands.Choice(name=key, value=key) for key in filtered_keys[:25]]

    @roles_group.command(name="set", description="[管理者] 特定の役割一つを選択してDBに設定します。")
    @app_commands.describe(role_type="データベースに保存する役割の種類を入力してください。", role="サーバーに実際に存在する役割を選択してください。")
    @app_commands.autocomplete(role_type=role_type_autocomplete)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def set_role_in_db(self, interaction: discord.Interaction, role_type: str, role: discord.Role):
        role_key_map = get_config("ROLE_KEY_MAP", {})
        if role_type not in role_key_map:
            await interaction.response.send_message(f"❌ 「{role_type}」は無効な役割タイプです。リストから選択してください。", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await save_id_to_db(role_type, role.id)
            await load_channel_ids_from_db()
            embed = discord.Embed(title="✅ 役割設定完了", description=f"データベースの`{role_type}`キーに{role.mention}役割が正常に連結されました。", color=discord.Color.blue())
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"개별 역할 설정 중 오류: {e}", exc_info=True)
            embed = discord.Embed(title="❌ エラー発生", description=f"`{role_type}`役割を設定中にエラーが発生しました。", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSetup(bot))
