# cogs/server/system.py

import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional, List

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
    
    # SETUP_COMMAND_MAP을 기반으로 명령어 선택지를 동적으로 생성합니다.
    try:
        from utils.ui_defaults import SETUP_COMMAND_MAP
        setup_choices = []
        for key, info in SETUP_COMMAND_MAP.items():
            name_parts = []
            if info['type'] == 'panel':
                name_parts.append("[パネル]")
            elif 'log' in key:
                name_parts.append("[ログ]")
            else:
                name_parts.append("[チャンネル]")
            
            name_parts.append(info['friendly_name'])
            
            # 한국어 설명이 필요한 경우 추가
            if "환영" in info['friendly_name']:
                name_parts.append("(입장 메시지)")
            elif "메인" in info['friendly_name']:
                name_parts.append("(자기소개 승인 후)")

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
                # [수정] 패널 재생성은 이제 각 기능 Cog가 담당하므로, 해당 Cog를 찾아 실행합니다.
                cog_name_map = {
                    "panel_roles": "RolePanel",
                    "panel_onboarding": "Onboarding",
                    "panel_nicknames": "Nicknames"
                }
                cog_to_run_name = cog_name_map.get(setting_type)
                
                if not cog_to_run_name:
                    await interaction.followup.send(f"❌ 이 패널({friendly_name})을 처리할 Cog를 찾을 수 없습니다.", ephemeral=True); return

                cog_to_run = self.bot.get_cog(cog_to_run_name)
                if not cog_to_run or not hasattr(cog_to_run, 'regenerate_panel'): 
                    await interaction.followup.send(f"❌ '{cog_to_run_name}' Cogが見つからないか、'regenerate_panel' 関数がありません。", ephemeral=True); return
                
                await cog_to_run.regenerate_panel(channel)
                await interaction.followup.send(f"✅ `{channel.mention}` に **{friendly_name}** を設置しました。", ephemeral=True)

            elif config["type"] == "channel":
                # 채널 설정 시 관련 Cog의 설정을 다시 불러오도록 합니다.
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
    # 2. 역할 설정 명령어 (/setup-roles) - server_setup.py에서 이동
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
            # 필드가 너무 많아지는 것을 방지하기 위해, 여러 청크를 하나의 필드로 합칩니다.
            value_str = "\n".join(synced_roles)
            if len(value_str) > 1024:
                value_str = value_str[:1020] + "..."
            embed.add_field(name=f"✅ 成功 ({len(synced_roles)}개)", value=value_str, inline=False)
        if missing_roles:
            value_str = "\n".join(missing_roles)
            if len(value_str) > 1024:
                value_str = value_str[:1020] + "..."
            embed.add_field(name=f"⚠️ 役割が見つかりません ({len(missing_roles)}개)", value=value_str, inline=False)
        if error_roles:
            value_str = "\n".join(error_roles)
            if len(value_str) > 1024:
                value_str = value_str[:1020] + "..."
            embed.add_field(name=f"❌ DB保存エラー ({len(error_roles)}개)", value=value_str, inline=False)

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
            await load_channel_ids_from_db() # 캐시 새로고침
            embed = discord.Embed(title="✅ 役割設定完了", description=f"データベースの`{role_type}`キーに{role.mention}役割が正常に連結されました。", color=discord.Color.blue())
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"개별 역할 설정 중 오류: {e}", exc_info=True)
            embed = discord.Embed(title="❌ エラー発生", description=f"`{role_type}`役割を設定中にエラーが発生しました。", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))
