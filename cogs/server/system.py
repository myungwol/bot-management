# cogs/server/system.py

import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional, List

# [수정] format_embed_from_db 함수가 이 파일에 더 이상 없습니다.
from utils.database import get_id, save_id_to_db, load_channel_ids_from_db, get_config

logger = logging.getLogger(__name__)

# --- ServerSystem Cog ---
class ServerSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("System (Admin Commands) Cog가 성공적으로 초기화되었습니다.")

    # ==============================================================================
    # 1. 통합 설정 명령어 (/setup)
    # ==============================================================================
    
    try:
        from utils.ui_defaults import SETUP_COMMAND_MAP
        setup_choices = []
        for key, info in SETUP_COMMAND_MAP.items():
            name_parts = []
            if info['type'] == 'panel': name_parts.append("[パネル]")
            elif 'log' in key: name_parts.append("[ログ]")
            else: name_parts.append("[チャンネル]")
            name_parts.append(info['friendly_name'])
            if "환영" in info['friendly_name']: name_parts.append("(입장 메시지)")
            elif "메인" in info['friendly_name']: name_parts.append("(자기소개 승인 후)")
            setup_choices.append(app_commands.Choice(name=" ".join(name_parts), value=key))
    except ImportError:
        setup_choices = []
        logger.error("ui_defaults.py에서 SETUP_COMMAND_MAP을 가져오는 데 실패했습니다.")

    @app_commands.command(name="setup", description="[管理者] ボットの各種チャンネルを設定またはパネルを設置します。")
    @app_commands.describe(setting_type="設定したい項目を選択してください。", channel="設定対象のチャンネルを指定してください。")
    @app_commands.choices(setting_type=setup_choices)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_unified(self, interaction: discord.Interaction, setting_type: str, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True, thinking=True)
        setup_map = get_config("SETUP_COMMAND_MAP", {})
        if not setup_map:
            await interaction.followup.send("❌ 설정 맵(`SETUP_COMMAND_MAP`)을 찾을 수 없습니다. 봇 관리자에게 문의하세요.", ephemeral=True)
            return
        config = setup_map.get(setting_type)
        if not config: await interaction.followup.send("❌ 無効な設定タイプです。", ephemeral=True); return
        try:
            db_key, friendly_name = config['key'], config['friendly_name']
            await save_id_to_db(db_key, channel.id)
            if config["type"] == "panel":
                cog_to_run = self.bot.get_cog(config["cog"])
                if not cog_to_run or not hasattr(cog_to_run, 'regenerate_panel'): 
                    await interaction.followup.send(f"❌ '{config['cog']}' Cogが見つからないか、'regenerate_panel' 関数がありません。", ephemeral=True); return
                await cog_to_run.regenerate_panel(channel)
                await interaction.followup.send(f"✅ `{channel.mention}` に **{friendly_name}** を設置しました。", ephemeral=True)
            elif config["type"] == "channel":
                target_cog_name = config.get("cog_name")
                if target_cog_name:
                    target_cog = self.bot.get_cog(target_cog_name)
                    if target_cog and hasattr(target_cog, 'load_configs'): 
                        await target_cog.load_configs()
                        logger.info(f"'{target_cog_name}' Cog의 설정을 새로고침했습니다.")
                await interaction.followup.send(f"✅ `{channel.mention}`を**{friendly_name}**として設定しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"통합 설정 명령어({setting_type}) 처리 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 設定中にエラーが発生しました. 詳細はボットのログを確認してください。", ephemeral=True)

    # ==============================================================================
    # 2. 역할 설정 명령어 (/setup-roles)
    # ==============================================================================
    
    roles_group = app_commands.Group(name="setup-roles", description="サーバーの役割をデータベースと同期したり、個別に設定します。")

    @roles_group.command(name="sync", description="[管理者] サーバーのすべての役割を名前基準でDBと一括同期します。")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def sync_roles_to_db(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild
        role_key_map = get_config("ROLE_KEY_MAP", {})
        if not role_key_map:
            await interaction.followup.send("❌ `ROLE_KEY_MAP` 설정이 데이터베이스에 없습니다. 관리자에게 문의하세요.", ephemeral=True)
            return
        synced_roles, missing_roles, error_roles = [], [], []
        server_roles_by_name = {role.name: role.id for role in guild.roles}
        for db_key, role_name in role_key_map.items():
            role_id = server_roles_by_name.get(role_name)
            if role_id:
                try:
                    await save_id_to_db(db_key, role_id)
                    synced_roles.append(f"・**{role_name}** (`{db_key}`)")
                except Exception as e: error_roles.append(f"・**{role_name}**: `{e}`")
            else: missing_roles.append(f"・**{role_name}** (`{db_key}`)")
        embed = discord.Embed(title="⚙️ 役割データベース一括同期の結果", color=discord.Color.green() if not missing_roles and not error_roles else discord.Color.orange())
        embed.set_footer(text=f"총 {len(role_key_map)}개 중 성공: {len(synced_roles)} / 실패: {len(missing_roles) + len(error_roles)}")
        if synced_roles:
            value_str = "\n".join(synced_roles); embed.add_field(name=f"✅ 成功 ({len(synced_roles)}개)", value=value_str[:1024], inline=False)
        if missing_roles:
            value_str = "\n".join(missing_roles); embed.add_field(name=f"⚠️ 役割が見つかりません ({len(missing_roles)}개)", value=value_str[:1024], inline=False)
        if error_roles:
            value_str = "\n".join(error_roles); embed.add_field(name=f"❌ DB保存エラー ({len(error_roles)}개)", value=value_str[:1024], inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def role_type_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        role_key_map = get_config("ROLE_KEY_MAP", {})
        keys = list(role_key_map.keys())
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
    await bot.add_cog(ServerSystem(bot))
