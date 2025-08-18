# bot-management/cogs/server/system.py
import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional, List
from datetime import datetime, timezone

from utils.database import (
    get_config, save_id_to_db, save_config_to_db, get_id,
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
        
        # 채널 설정 자동완성 (SETUP_COMMAND_MAP 기반)
        for key, info in setup_map.items():
            type_prefix = "[채널]"
            if "log" in key: type_prefix = "[로그]"
            elif "panel" in key: type_prefix = "[패널]"
            elif "reminder" in key: type_prefix = "[알림]"

            choice_name = f"{type_prefix} {info.get('friendly_name', key)} 설정"
            if current.lower() in choice_name.lower():
                choices.append(app_commands.Choice(name=choice_name, value=f"channel_setup:{key}"))
        
        # 역할 설정 자동완성 (수동)
        role_setup_actions = {
            "role_setup:bump_reminder_role_id": "[알림] Disboard BUMP 알림 역할 설정",
            "role_setup:dissoku_reminder_role_id": "[알림] Dissoku UP 알림 역할 설정",
        }
        for key, name in role_setup_actions.items():
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=key))

        game_panel_actions = {
            "request_regenerate:commerce": "[게임-패널] 상점 패널 재설치 요청",
            "request_regenerate:fishing": "[게임-패널] 낚시터 패널 재설치 요청",
            "request_regenerate:profile": "[게임-패널] 프로필 패널 재설치 요청",
        }
        for key, name in game_panel_actions.items():
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=key))

        panel_actions = {"panels_regenerate_all": "[패널] 모든 관리 패널 재설치"}
        for key, name in panel_actions.items():
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=key))

        role_actions = {"roles_sync": "[역할] 모든 역할 DB와 동기화"}
        for key, name in role_actions.items():
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=key))
        
        stats_actions = {
            "stats_set": "[통계] 통계 채널 설정/제거",
            "stats_refresh": "[통계] 모든 통계 채널 새로고침",
            "stats_list": "[통계] 설정된 통계 채널 목록 보기",
        }
        for key, name in stats_actions.items():
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=key))
        
        return sorted(choices, key=lambda c: c.name)[:25]

    @app_commands.command(name="setup", description="[管理者] ボットのチャンネル、役割、統計など、すべての設定を管理します。")
    @app_commands.describe(
        action="実行するタスクを選択してください。",
        channel="[チャンネル/統計] タスクに必要なチャンネルを選択してください。",
        role="[役割/統計] タスクに必要な役割を選択してください。",
        stat_type="[統計] 表示する統計の種類を選択してください。",
        template="[統計] チャンネル名の形式を指定します (例: 👤 ユーザー: {count}人)"
    )
    @app_commands.autocomplete(action=setup_action_autocomplete)
    @app_commands.choices(stat_type=[
        app_commands.Choice(name="[설정] 전체 멤버 수 (봇 포함)", value="total"),
        app_commands.Choice(name="[설정] 유저 수 (봇 제외)", value="humans"),
        app_commands.Choice(name="[설정] 봇 수", value="bots"),
        app_commands.Choice(name="[설정] 서버 부스트 수", value="boosters"),
        app_commands.Choice(name="[설정] 특정 역할 멤버 수", value="role"),
        app_commands.Choice(name="[삭제] 이 채널의 통계 설정 삭제", value="remove"),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup(self, interaction: discord.Interaction,
                    action: str,
                    channel: Optional[discord.TextChannel | discord.VoiceChannel | discord.ForumChannel] = None,
                    role: Optional[discord.Role] = None,
                    stat_type: Optional[str] = None,
                    template: Optional[str] = None):
        
        await interaction.response.defer(ephemeral=True)

        if action.startswith("request_regenerate:"):
            panel_key = action.split(":", 1)[1]
            db_key = f"panel_regenerate_request_{panel_key}"
            await save_config_to_db(db_key, datetime.now(timezone.utc).timestamp())
            return await interaction.followup.send(
                f"✅ ゲームボットに `{panel_key}` パネルの再設置を要請しました。\n"
                "ゲームボットがオンラインの場合、約10秒以内にパネルが更新されます。",
                ephemeral=True
            )

        elif action.startswith("channel_setup:"):
            setting_key = action.split(":", 1)[1]
            setup_map = get_config("SETUP_COMMAND_MAP", {})
            config = setup_map.get(setting_key)
            if not config:
                return await interaction.followup.send("❌ 無効な設定キーです。", ephemeral=True)
            
            required_channel_type = config.get("channel_type", "text")
            error_msg = None
            if not channel:
                error_msg = f"❌ このタスクを実行するには、「channel」オプションに**{required_channel_type}チャンネル**を指定する必要があります。"
            elif (required_channel_type == "text" and not isinstance(channel, discord.TextChannel)) or \
                 (required_channel_type == "voice" and not isinstance(channel, discord.VoiceChannel)) or \
                 (required_channel_type == "forum" and not isinstance(channel, discord.ForumChannel)):
                error_msg = f"❌ このタスクには**{required_channel_type}チャンネル**が必要です。正しいタイプのチャンネルを選択してください。"
            
            if error_msg:
                return await interaction.followup.send(error_msg, ephemeral=True)

            db_key, friendly_name = config['key'], config['friendly_name']
            await save_id_to_db(db_key, channel.id)

            cog_to_reload = self.bot.get_cog(config["cog_name"])
            if cog_to_reload and hasattr(cog_to_reload, 'load_configs'):
                await cog_to_reload.load_configs()
                logger.info(f"/{interaction.command.name} 명령어로 인해 '{config['cog_name']}' Cog의 설정이 새로고침되었습니다.")
            
            if config.get("type") == "panel":
                if hasattr(cog_to_reload, 'regenerate_panel'):
                    if config["cog_name"] == "TicketSystem":
                        panel_type = setting_key.replace("panel_", "")
                        success = await cog_to_reload.regenerate_panel(channel, panel_type)
                    else:
                        success = await cog_to_reload.regenerate_panel(channel)
                        
                    if success:
                        await interaction.followup.send(f"✅ `{channel.mention}` チャンネルに **{friendly_name}** パネルを正常に設置しました。", ephemeral=True)
                    else:
                        await interaction.followup.send(f"❌ `{channel.mention}` チャンネルへのパネル設置中にエラーが発生しました。詳細はログを確認してください。", ephemeral=True)
                else:
                    await interaction.followup.send(f"⚠️ **{friendly_name}** は設定されましたが、パネルを自動生成する機能が見つかりません。", ephemeral=True)
            else:
                await interaction.followup.send(f"✅ **{friendly_name}** を `{channel.mention}` チャンネルに設定しました。", ephemeral=True)

        elif action.startswith("role_setup:"):
            db_key = action.split(":", 1)[1]
            if not role:
                return await interaction.followup.send("❌ このタスクを実行するには、「role」オプションに役割を指定する必要があります。", ephemeral=True)
            
            friendly_name = "알림 역할"
            for choice in await self.setup_action_autocomplete(interaction, ""):
                if choice.value == action:
                    friendly_name = choice.name.replace(" 설정", "")
            
            await save_id_to_db(db_key, role.id)
            
            cog_to_reload = self.bot.get_cog("Reminder")
            if cog_to_reload and hasattr(cog_to_reload, 'load_configs'):
                await cog_to_reload.load_configs()
            
            await interaction.followup.send(f"✅ **{friendly_name}** を `{role.mention}` 役割に設定しました。", ephemeral=True)

        elif action == "panels_regenerate_all":
            # ... (이하 나머지 코드는 이전과 동일) ...

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))
