# cogs/server/system.py
"""
서버 관리와 관련된 모든 통합 명령어를 단일 /setup 명령어로 담당하는 Cog입니다.
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional, List

from utils.database import (
    get_config, save_id_to_db, save_config_to_db,
    get_all_stats_channels, add_stats_channel, remove_stats_channel
)
from utils.ui_defaults import UI_ROLE_KEY_MAP

logger = logging.getLogger(__name__)

class ServerSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("System (통합 관리 명령어) Cog가 성공적으로 초기화되었습니다.")

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(f"❌ このコマンドを使用するには、次の権限が必要です: `{', '.join(error.missing_permissions)}`", ephemeral=True)
        else:
            logger.error(f"'{interaction.command.qualified_name}'コマンドの処理中にエラーが発生しました: {error}", exc_info=True)
            if interaction.response.is_done():
                await interaction.followup.send("❌ コマンドの処理中に予期せぬエラーが発生しました。", ephemeral=True)
            else:
                await interaction.response.send_message("❌ コマンドの処理中に予期せぬエラーが発生しました。", ephemeral=True)

    async def setup_action_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        setup_map = get_config("SETUP_COMMAND_MAP", {})
        choices = []
        for key, info in setup_map.items():
            type_prefix = "[채널/패널]"
            if info.get('channel_type') == 'voice': type_prefix = "[음성채널]"
            elif info.get('channel_type') == 'forum': type_prefix = "[포럼]"
            elif info.get('channel_type') == 'category': type_prefix = "[카테고리]"

            choice_name = f"{type_prefix} {info.get('friendly_name', key)} 설정"
            if current.lower() in choice_name.lower():
                choices.append(app_commands.Choice(name=choice_name, value=f"channel_setup:{key}"))

        role_actions = { "roles_sync": "[역할] 모든 역할 DB와 동기화" }
        for key, name in role_actions.items():
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=key))
        
        stats_actions = { "stats_set": "[통계] 통계 채널 설정/제거", "stats_refresh": "[통계] 모든 통계 채널 새로고침", "stats_list": "[통계] 설정된 통계 채널 목록 보기",}
        for key, name in stats_actions.items():
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=key))

        return sorted(choices, key=lambda c: c.name)[:25]

    @app_commands.command(name="setup", description="[管理者] ボットのチャンネル、役割、統計など、すべての設定を管理します。")
    @app_commands.describe(
        action="実行するタスクを選択してください。",
        channel="[チャンネル/統計] タスクに必要なチャンネルを選択してください。",
        role="[統計] '特定の役割の人数'を選択した場合に必要な役割です。",
        stat_type="[統計] 表示する統計の種類を選択してください。",
        template="[統計] チャンネル名の形式を指定します (例: 👤 ユーザー: {count}人)"
    )
    @app_commands.autocomplete(action=setup_action_autocomplete)
    @app_commands.choices(stat_type=[
        app_commands.Choice(name="[設定] 全メンバー数 (ボット含む)", value="total"),
        app_commands.Choice(name="[設定] ユーザー数 (ボット除く)", value="humans"),
        app_commands.Choice(name="[設定] ボット数", value="bots"),
        app_commands.Choice(name="[設定] サーバーブースト数", value="boosters"),
        app_commands.Choice(name="[設定] 特定の役割の人数", value="role"),
        app_commands.Choice(name="[削除] このチャンネルの統計設定を削除", value="remove"),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup(self, interaction: discord.Interaction,
                    action: str,
                    # [수정] 타입 힌트를 원래대로 되돌림
                    channel: Optional[discord.TextChannel | discord.VoiceChannel] = None,
                    role: Optional[discord.Role] = None,
                    stat_type: Optional[str] = None,
                    template: Optional[str] = None):
        
        await interaction.response.defer(ephemeral=True)

        if action.startswith("channel_setup:"):
            setting_key = action.split(":", 1)[1]
            setup_map = get_config("SETUP_COMMAND_MAP", {})
            config = setup_map.get(setting_key)
            if not config: return await interaction.followup.send("❌ 無効な設定キーです。", ephemeral=True)

            required_channel_type = config.get("channel_type", "text")
            error_msg = None
            if not channel:
                error_msg = f"❌ このタスクを実行するには、「channel」オプションに**{required_channel_type}チャンネル**を指定する必要があります。"
            # [수정] 문법 오류가 있던 부분을 올바르게 수정
            elif (required_channel_type == "text" and not isinstance(channel, discord.TextChannel)) or \
                 (required_channel_type == "voice" and not isinstance(channel, discord.VoiceChannel)):
                error_msg = f"❌ このタスクには**{required_channel_type}チャンネル**が必要です。正しいタイプのチャンネルを選択してください。"
            
            if error_msg: return await interaction.followup.send(error_msg, ephemeral=True)

            db_key, friendly_name = config['key'], config['friendly_name']
            await save_id_to_db(db_key, channel.id)
            
            cog_to_reload = self.bot.get_cog(config["cog_name"])
            if cog_to_reload and hasattr(cog_to_reload, 'load_configs'):
                await cog_to_reload.load_configs()

            if config["type"] == "panel" and hasattr(cog_to_reload, 'regenerate_panel'):
                await cog_to_reload.regenerate_panel(channel)
                await interaction.followup.send(f"✅ `{channel.mention}` チャンネルに **{friendly_name}** パネルを正常に設置しました。", ephemeral=True)
            else:
                await interaction.followup.send(f"✅ **{friendly_name}** を `{channel.mention}` チャンネルに設定しました。", ephemeral=True)

        elif action == "roles_sync":
            role_name_map = {key: info["name"] for key, info in UI_ROLE_KEY_MAP.items()}
            await save_config_to_db("ROLE_KEY_MAP", role_name_map)
            synced_roles, missing_roles, error_roles = [], [], []
            server_roles_by_name = {r.name: r.id for r in interaction.guild.roles}
            for db_key, role_info in UI_ROLE_KEY_MAP.items():
                role_name = role_info.get('name')
                if not role_name: continue
                if role_id := server_roles_by_name.get(role_name):
                    try:
                        await save_id_to_db(db_key, role_id)
                        synced_roles.append(f"・**{role_name}** (`{db_key}`)")
                    except Exception as e: error_roles.append(f"・**{role_name}**: `{e}`")
                else: missing_roles.append(f"・**{role_name}** (`{db_key}`)")
            
            embed = discord.Embed(title="⚙️ 役割データベースの完全同期結果", color=0x2ECC71)
            embed.set_footer(text=f"合計 {len(UI_ROLE_KEY_MAP)}個中 成功: {len(synced_roles)} / 失敗: {len(missing_roles) + len(error_roles)}")
            if synced_roles:
                full_text = "\n".join(synced_roles)
                for i in range(0, len(full_text), 1024):
                    chunk = full_text[i:i+1024]
                    embed.add_field(name=f"✅ 同期成功 (部分 {i//1024 + 1})", value=chunk, inline=False)
            if missing_roles:
                embed.color = 0xFEE75C
                embed.add_field(name=f"⚠️ サーバーに該当の役割なし ({len(missing_roles)}個)", value="\n".join(missing_roles)[:1024], inline=False)
            if error_roles:
                embed.color = 0xED4245
                embed.add_field(name=f"❌ DB保存エラー ({len(error_roles)}個)", value="\n".join(error_roles)[:1024], inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)

        elif action == "stats_set":
            if not channel or not isinstance(channel, discord.VoiceChannel):
                return await interaction.followup.send("❌ このタスクを実行するには、「channel」オプションにボイスチャンネルを指定する必要があります。", ephemeral=True)
            if not stat_type:
                return await interaction.followup.send("❌ このタスクを実行するには、「stat_type」オプションを選択する必要があります。", ephemeral=True)
            if stat_type == "remove":
                await remove_stats_channel(channel.id)
                await interaction.followup.send(f"✅ `{channel.name}` チャンネルの統計設定を削除しました。", ephemeral=True)
            else:
                current_template = template or f"名前: {{count}}"
                if "{count}" not in current_template:
                    return await interaction.followup.send("❌ 名前形式(`template`)には必ず`{count}`を含める必要があります。", ephemeral=True)
                if stat_type == "role" and not role:
                    return await interaction.followup.send("❌ '特定の役割の人数'を選択した場合は、「role」オプションを指定する必要があります。", ephemeral=True)
                role_id = role.id if role else None
                await add_stats_channel(channel.id, interaction.guild_id, stat_type, current_template, role_id)
                stats_cog = self.bot.get_cog("StatsUpdater")
                if stats_cog and hasattr(stats_cog.update_stats_loop, 'restart'): stats_cog.update_stats_loop.restart()
                await interaction.followup.send(f"✅ `{channel.name}` チャンネルに統計設定を追加/修正しました。", ephemeral=True)

        elif action == "stats_refresh":
            stats_cog = self.bot.get_cog("StatsUpdater")
            if stats_cog and hasattr(stats_cog.update_stats_loop, 'restart'):
                stats_cog.update_stats_loop.restart()
                await interaction.followup.send("✅ すべての統計チャンネルの更新を要求しました。", ephemeral=True)
            else: await interaction.followup.send("❌ 統計更新機能が見つかりません。", ephemeral=True)

        elif action == "stats_list":
            configs = await get_all_stats_channels()
            guild_configs = [c for c in configs if c.get('guild_id') == interaction.guild_id]
            if not guild_configs: return await interaction.followup.send("ℹ️ 設定された統計チャンネルはありません。", ephemeral=True)
            embed = discord.Embed(title="📊 設定された統計チャンネル一覧", color=0x3498DB)
            description = []
            for config in guild_configs:
                ch = self.bot.get_channel(config['channel_id'])
                ch_mention = f"<#{ch.id}>" if ch else f"削除されたチャンネル({config['channel_id']})"
                description.append(f"**チャンネル:** {ch_mention}\n**種類:** `{config['stat_type']}`\n**名前形式:** `{config['channel_name_template']}`")
            embed.description = "\n\n".join(description)
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        else: await interaction.followup.send("❌ 不明なタスクです。リストから正しいタスクを選択してください。", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))
