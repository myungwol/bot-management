# cogs/server/system.py
import discord
from discord.ext import commands
from discord import app_commands, ui
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import asyncio
import time

from utils.database import (
    get_config, save_id_to_db, save_config_to_db, get_id,
    get_all_stats_channels, add_stats_channel, remove_stats_channel,
    _channel_id_cache,
    update_wallet,
    supabase,
    get_all_embeds, get_embed_from_db, save_embed_to_db
)
from utils.helpers import calculate_xp_for_level
from utils.ui_defaults import UI_ROLE_KEY_MAP, SETUP_COMMAND_MAP, ADMIN_ROLE_KEYS

logger = logging.getLogger(__name__)

async def is_admin(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member):
        return False
    
    admin_role_ids = {get_id(key) for key in ADMIN_ROLE_KEYS if get_id(key)}
    user_role_ids = {role.id for role in interaction.user.roles}
    
    if not user_role_ids.intersection(admin_role_ids):
        if interaction.user.id == interaction.guild.owner_id:
            return True
        raise app_commands.CheckFailure("このコマンドを実行するための管理者権限がありません。")
    return True

# --- [신규 추가] 임베드 템플릿 수정을 위한 UI 클래스 ---
class TemplateEditModal(ui.Modal, title="埋め込みテンプレート編集"):
    title_input = ui.TextInput(label="タイトル", placeholder="埋め込みのタイトルを入力してください。", required=False, max_length=256)
    description_input = ui.TextInput(label="説明", placeholder="埋め込みの説明文を入力してください。", style=discord.TextStyle.paragraph, required=False, max_length=4000)
    color_input = ui.TextInput(label="色 (16進数コード)", placeholder="例: #5865F2 (空欄の場合はデフォルト色)", required=False, max_length=7)
    image_url_input = ui.TextInput(label="画像URL", placeholder="埋め込みに表示する画像のURLを入力してください。", required=False)
    thumbnail_url_input = ui.TextInput(label="サムネイルURL", placeholder="右上に表示するサムネイル画像のURLを入力してください。", required=False)

    def __init__(self, existing_embed: discord.Embed):
        super().__init__()
        self.embed: Optional[discord.Embed] = None
        self.title_input.default = existing_embed.title
        self.description_input.default = existing_embed.description
        if existing_embed.color: self.color_input.default = str(existing_embed.color)
        if existing_embed.image and existing_embed.image.url: self.image_url_input.default = existing_embed.image.url
        if existing_embed.thumbnail and existing_embed.thumbnail.url: self.thumbnail_url_input.default = existing_embed.thumbnail.url

    async def on_submit(self, interaction: discord.Interaction):
        if not self.title_input.value and not self.description_input.value and not self.image_url_input.value:
            return await interaction.response.send_message("❌ タイトル、説明、画像URLのいずれか一つは必ず入力してください。", ephemeral=True)
        try:
            color = discord.Color.default()
            if self.color_input.value:
                color = discord.Color(int(self.color_input.value.replace("#", ""), 16))
            
            embed = discord.Embed(
                title=self.title_input.value or None,
                description=self.description_input.value or None,
                color=color
            )
            if self.image_url_input.value: embed.set_image(url=self.image_url_input.value)
            if self.thumbnail_url_input.value: embed.set_thumbnail(url=self.thumbnail_url_input.value)
            self.embed = embed
            await interaction.response.defer(ephemeral=True)
        except Exception:
            await interaction.response.send_message("❌ 埋め込みの作成中にエラーが発生しました。", ephemeral=True)

class EmbedTemplateSelectView(ui.View):
    def __init__(self, all_embeds: List[Dict[str, Any]]):
        super().__init__(timeout=300)
        self.all_embeds = {e['embed_key']: e['embed_data'] for e in all_embeds}
        
        options = [
            discord.SelectOption(label=key, description=data.get('title', 'タイトルなし')[:100])
            for key, data in self.all_embeds.items()
        ]
        
        for i in range(0, len(options), 25):
            select = ui.Select(placeholder=f"編集する埋め込みテンプレートを選択... ({i//25 + 1})", options=options[i:i+25])
            select.callback = self.select_callback
            self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        embed_key = interaction.data['values'][0]
        embed_data = self.all_embeds.get(embed_key)
        if not embed_data:
            return await interaction.response.send_message("❌ テンプレートが見つかりませんでした。", ephemeral=True)

        existing_embed = discord.Embed.from_dict(embed_data)
        modal = TemplateEditModal(existing_embed)
        await interaction.response.send_modal(modal)
        await modal.wait()

        if modal.embed:
            new_embed_data = modal.embed.to_dict()
            await save_embed_to_db(embed_key, new_embed_data)
            
            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(view=self)
            
            await interaction.followup.send(
                f"✅ 埋め込みテンプレート`{embed_key}`が正常に更新されました。\n"
                "`/admin setup`で関連パネルを再設置すると、変更が反映されます。",
                embed=modal.embed,
                ephemeral=True
            )

class ServerSystem(commands.Cog):
    admin_group = app_commands.Group(
        name="admin",
        description="サーバー管理用のコマンドです。",
        default_permissions=discord.Permissions(manage_guild=True)
    )

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("System (통합 관리 명령어) Cog가 성공적으로 초기화되었습니다。")

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            await interaction.response.send_message(f"❌ {error}", ephemeral=True)
        elif isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(f"❌ このコマンドを使用するには、次の権限が必要です: `{', '.join(error.missing_permissions)}`", ephemeral=True)
        else:
            logger.error(f"'{interaction.command.qualified_name}'コマンドの処理中にエラーが発生しました: {error}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ コマンドの処理中に予期せぬエラーが発生しました。", ephemeral=True)
            else:
                await interaction.followup.send("❌ コマンドの処理中に予期せぬエラーが発生しました。", ephemeral=True)

    async def setup_action_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        choices = []
        for key, info in SETUP_COMMAND_MAP.items():
            choice_name = f"{info.get('friendly_name', key)} 設定"
            if current.lower() in choice_name.lower():
                choices.append(app_commands.Choice(name=choice_name, value=f"channel_setup:{key}"))
        
        role_setup_actions = {
            "role_setup:bump_reminder_role_id": "[알림] Disboard BUMP 알림 역할 설정",
            "role_setup:dissoku_reminder_role_id": "[알림] Dissoku UP 알림 역할 설정",
        }
        for key, name in role_setup_actions.items():
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=key))

        panel_actions = {"panels_regenerate_all": "[패널] 모든 관리 패널 재설치"}
        for key, name in panel_actions.items():
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=key))
                
        template_actions = {"template_edit": "[テンプレート] 埋め込みテンプレートを編集"}
        for key, name in template_actions.items():
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=key))

        game_panel_actions = {"request_regenerate_all_game_panels": "[ゲーム] 全パネルの一括再設置要請"}
        for key, name in game_panel_actions.items():
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

    @admin_group.command(
        name="setup",
        description="ボットのチャンネル、役割、統計など、すべての設定を管理します。"
    )
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
    @app_commands.check(is_admin)
    async def setup(self, interaction: discord.Interaction,
                    action: str,
                    channel: Optional[discord.TextChannel | discord.VoiceChannel | discord.ForumChannel] = None,
                    role: Optional[discord.Role] = None,
                    stat_type: Optional[str] = None,
                    template: Optional[str] = None):
        
        await interaction.response.defer(ephemeral=True)

        if action == "template_edit":
            all_embeds = await get_all_embeds()
            if not all_embeds:
                return await interaction.followup.send("❌ DBに編集可能な埋め込みテンプレートがありません。", ephemeral=True)
            
            view = EmbedTemplateSelectView(all_embeds)
            await interaction.followup.send("編集したい埋め込みテンプレートを下のメニューから選択してください。", view=view, ephemeral=True)

        elif action == "request_regenerate_all_game_panels":
            game_panel_keys = [key for key, info in SETUP_COMMAND_MAP.items() if "[게임]" in info.get("friendly_name", "")]
            if not game_panel_keys:
                return await interaction.followup.send("❌ 設定ファイルにゲームパネルが見つかりません。", ephemeral=True)
            
            timestamp = datetime.now(timezone.utc).timestamp()
            tasks = []
            for panel_key in game_panel_keys:
                db_key = f"panel_regenerate_request_{panel_key}"
                tasks.append(save_config_to_db(db_key, timestamp))
            
            await asyncio.gather(*tasks)
            
            return await interaction.followup.send(
                f"✅ {len(game_panel_keys)}個のゲームパネルに一括で再設置を要請しました。\n"
                "ゲームボットがオンラインの場合、約10秒以内にパネルが更新されます。",
                ephemeral=True
            )

        elif action.startswith("channel_setup:"):
            setting_key = action.split(":", 1)[1]
            config = SETUP_COMMAND_MAP.get(setting_key)
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
            
            save_success = await save_id_to_db(db_key, channel.id)
            if not save_success:
                return await interaction.followup.send(f"❌ **{friendly_name}** 設定中、DB保存に失敗しました。Supabase RLSポリシーを確認してください。", ephemeral=True)

            cog_to_reload = self.bot.get_cog(config["cog_name"])
            if cog_to_reload and hasattr(cog_to_reload, 'load_configs'):
                await cog_to_reload.load_configs()

            if config.get("type") == "panel":
                if hasattr(cog_to_reload, 'regenerate_panel'):
                    success = False
                    # [✅✅✅ 핵심 수정 ✅✅✅]
                    # cog의 regenerate_panel 함수를 호출할 때, 설정 키(setting_key)를 명확하게 전달합니다.
                    # 이로써 각 cog가 어떤 패널을 생성해야 하는지 정확히 알 수 있습니다.
                    if config["cog_name"] == "TicketSystem":
                        panel_type = setting_key.replace("panel_", "")
                        success = await cog_to_reload.regenerate_panel(channel, panel_type=panel_type)
                    else:
                        success = await cog_to_reload.regenerate_panel(channel, panel_key=setting_key)
                        
                    if success:
                        await interaction.followup.send(f"✅ `{channel.mention}` チャンネルに **{friendly_name}** パネルを正常に設置しました。", ephemeral=True)
                    else:
                        await interaction.followup.send(f"❌ `{channel.mention}` チャンネルへのパネル設置中にエラーが発生しました。", ephemeral=True)
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
                    friendly_name = choice.name.replace(" 設定", "")
            
            save_success = await save_id_to_db(db_key, role.id)
            if not save_success:
                 return await interaction.followup.send(f"❌ **{friendly_name}** 設定中、DB保存に失敗しました。Supabase RLSポリシーを確認してください。", ephemeral=True)

            cog_to_reload = self.bot.get_cog("Reminder")
            if cog_to_reload and hasattr(cog_to_reload, 'load_configs'):
                await cog_to_reload.load_configs()
            
            await interaction.followup.send(f"✅ **{friendly_name}** を `{role.mention}` 役割に設定しました。", ephemeral=True)

        elif action == "panels_regenerate_all":
            setup_map = get_config("SETUP_COMMAND_MAP", {})
            success_list, failure_list = [], []

            await interaction.followup.send("⏳ すべてのパネルの再設置を開始します...", ephemeral=True)

            for key, info in setup_map.items():
                if info.get("type") == "panel":
                    friendly_name = info.get("friendly_name", key)
                    try:
                        cog_name, channel_db_key = info.get("cog_name"), info.get("key")
                        if not all([cog_name, channel_db_key]):
                            failure_list.append(f"・`{friendly_name}`: 設定情報が不完全です。")
                            continue
                        cog = self.bot.get_cog(cog_name)
                        if not cog or not hasattr(cog, 'regenerate_panel'):
                            failure_list.append(f"・`{friendly_name}`: Cogが見つからないか、再生成機能がありません。")
                            continue
                        channel_id = get_id(channel_db_key)
                        if not channel_id or not (target_channel := self.bot.get_channel(channel_id)):
                            failure_list.append(f"・`{friendly_name}`: チャンネルが設定されていないか、見つかりません。")
                            continue
                        
                        success = False
                        if cog_name == "TicketSystem":
                            panel_type = key.replace("panel_", "")
                            success = await cog.regenerate_panel(target_channel, panel_type=panel_type)
                        else:
                            success = await cog.regenerate_panel(target_channel, panel_key=key)
                        
                        if success: success_list.append(f"・`{friendly_name}` → <#{target_channel.id}>")
                        else: failure_list.append(f"・`{friendly_name}`: 再生成中に不明なエラーが発生しました。")

                    except Exception as e:
                        logger.error(f"'{friendly_name}' 패널 일괄 재설치 중 오류: {e}", exc_info=True)
                        failure_list.append(f"・`{friendly_name}`: スクリプトエラー発生。")

            embed = discord.Embed(title="⚙️ すべてのパネルの再設置結果", color=0x3498DB, timestamp=discord.utils.utcnow())
            if success_list: embed.add_field(name="✅ 成功", value="\n".join(success_list), inline=False)
            if failure_list:
                embed.color = 0xED4245
                embed.add_field(name="❌ 失敗", value="\n".join(failure_list), inline=False)
            
            await interaction.edit_original_response(content="すべてのパネルの再設置が完了しました。", embed=embed)

        elif action == "roles_sync":
            role_name_map = {key: info["name"] for key, info in UI_ROLE_KEY_MAP.items()}
            await save_config_to_db("ROLE_KEY_MAP", role_name_map)
            
            synced_roles, missing_roles, error_roles = [], [], []
            server_roles_by_name = {r.name: r.id for r in interaction.guild.roles}
            
            for db_key, role_info in UI_ROLE_KEY_MAP.items():
                if not (role_name := role_info.get('name')): continue
                if role_id := server_roles_by_name.get(role_name):
                    if await save_id_to_db(db_key, role_id): synced_roles.append(f"・`{role_name}`")
                    else: error_roles.append(f"・`{role_name}`: DB 저장 실패")
                else: missing_roles.append(f"・`{role_name}`")
            
            embed = discord.Embed(title="⚙️ 役割データベースの完全同期結果", color=0x2ECC71)
            embed.set_footer(text=f"合計 {len(UI_ROLE_KEY_MAP)}個中 | 成功: {len(synced_roles)} / 失敗: {len(missing_roles) + len(error_roles)}")

            if synced_roles: embed.add_field(name=f"✅ 同期成功 ({len(synced_roles)}個)", value="\n".join(synced_roles)[:1024], inline=False)
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
                current_template = template or f"정보: {{count}}"
                if "{count}" not in current_template:
                    return await interaction.followup.send("❌ 名前形式(`template`)には必ず`{count}`を含める必要があります。", ephemeral=True)
                if stat_type == "role" and not role:
                    return await interaction.followup.send("❌ '特定の役割の人数'を選択した場合は、「role」オプションを指定する必要があります。", ephemeral=True)
                
                await add_stats_channel(channel.id, interaction.guild_id, stat_type, current_template, role.id if role else None)
                
                if (stats_cog := self.bot.get_cog("StatsUpdater")) and hasattr(stats_cog, 'update_stats_loop') and stats_cog.update_stats_loop.is_running():
                    stats_cog.update_stats_loop.restart()
                
                await interaction.followup.send(f"✅ `{channel.name}` チャンネルに統計設定を追加/修正しました。まもなく更新されます。", ephemeral=True)

        elif action == "stats_refresh":
            if (stats_cog := self.bot.get_cog("StatsUpdater")) and hasattr(stats_cog, 'update_stats_loop') and stats_cog.update_stats_loop.is_running():
                stats_cog.update_stats_loop.restart()
                await interaction.followup.send("✅ すべての統計チャンネルの更新を要求しました。", ephemeral=True)
            else:
                await interaction.followup.send("❌ 統計更新機能が見つからないか、実行中ではありません。", ephemeral=True)

        elif action == "stats_list":
            configs = await get_all_stats_channels()
            guild_configs = [c for c in configs if c.get('guild_id') == interaction.guild_id]
            if not guild_configs:
                return await interaction.followup.send("ℹ️ 設定された統計チャンネルはありません。", ephemeral=True)
            
            embed = discord.Embed(title="📊 設定された統計チャンネル一覧", color=0x3498DB)
            description = []
            for config in guild_configs:
                ch_mention = f"<#{config['channel_id']}>" if self.bot.get_channel(config['channel_id']) else f"削除されたチャンネル({config['channel_id']})"
                role_info = ""
                if config['stat_type'] == 'role' and config.get('role_id'):
                    role_obj = interaction.guild.get_role(config['role_id'])
                    role_info = f"\n**対象役割:** {role_obj.mention if role_obj else '不明な役割'}"
                description.append(f"**チャンネル:** {ch_mention}\n**種類:** `{config['stat_type']}`{role_info}\n**名前形式:** `{config['channel_name_template']}`")
            
            embed.description = "\n\n".join(description)
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        else:
            await interaction.followup.send("❌ 不明なタスクです。リストから正しいタスクを選択してください。", ephemeral=True)

    @admin_group.command(name="status", description="ボットの現在の設定状態を一覧で表示します。")
    @app_commands.check(is_admin)
    async def status(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        embed = discord.Embed(title="⚙️ サーバー設定 現況ダッシュボード", color=0x3498DB)
        embed.set_footer(text=f"最終確認: {discord.utils.format_dt(discord.utils.utcnow(), style='F')}")

        channel_lines = []
        for key, info in sorted(SETUP_COMMAND_MAP.items(), key=lambda item: item[1]['friendly_name']):
            channel_id = _channel_id_cache.get(info['key'])
            status_emoji = "✅" if channel_id else "❌"
            channel_mention = f"<#{channel_id}>" if channel_id else "未設定"
            channel_lines.append(f"{status_emoji} **{info['friendly_name']}**: {channel_mention}")
        
        full_channel_text = "\n".join(channel_lines)
        chunk_size = 1024
        for i in range(0, len(full_channel_text), chunk_size):
            chunk = full_channel_text[i:i+chunk_size]
            field_name = "チャンネル設定" if i == 0 else "チャンネル設定 (続き)"
            embed.add_field(name=f"**{field_name}**", value=chunk, inline=False)

        role_lines = []
        for key, info in sorted(UI_ROLE_KEY_MAP.items(), key=lambda item: item[1]['priority'], reverse=True):
            if info.get('priority', 0) > 0:
                role_id = _channel_id_cache.get(key)
                status_emoji = "✅" if role_id else "❌"
                role_mention = f"<@&{role_id}>" if role_id else f"`{info['name']}` (未設定)"
                role_lines.append(f"{status_emoji} **{info['name']}**: {role_mention if role_id else '未設定'}")
        
        if role_lines:
            embed.add_field(name="**主要な役割設定**", value="\n".join(role_lines)[:1024], inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

    async def log_coin_admin_action(self, admin: discord.Member, target: discord.Member, amount: int, action: str):
        log_channel_id = get_id("coin_log_channel_id")
        if not log_channel_id or not (log_channel := self.bot.get_channel(log_channel_id)):
            logger.warning("コイン管理ログチャンネルが設定されていないか、見つかりません。")
            return

        currency_icon = get_config("GAME_CONFIG", {}).get("CURRENCY_ICON", "🪙")
        action_color = 0x3498DB if amount > 0 else 0xE74C3C
        amount_str = f"+{amount:,}" if amount > 0 else f"{amount:,}"
        
        embed = discord.Embed(
            description=f"⚙️ {admin.mention}さんが{target.mention}さんのコインを`{amount_str}`{currency_icon}だけ**{action}**しました。",
            color=action_color
        )
        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            logger.error(f"管理者のコイン操作ログ送信に失敗しました: {e}", exc_info=True)

    @admin_group.command(name="コイン付与", description="[管理者専用] 特定のユーザーにコインを付与します。")
    @app_commands.describe(user="コインを付与するユーザー", amount="付与するコインの量")
    @app_commands.check(is_admin)
    async def give_coin(self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 1, None]):
        await interaction.response.defer(ephemeral=True)
        currency_icon = get_config("GAME_CONFIG", {}).get("CURRENCY_ICON", "🪙")
        
        result = await update_wallet(user, amount)
        if result:
            await self.log_coin_admin_action(interaction.user, user, amount, "付与")
            await interaction.followup.send(f"✅ {user.mention}さんへ `{amount:,}`{currency_icon}を付与しました。")
        else:
            await interaction.followup.send("❌ コイン付与中にエラーが発生しました。")
    
    @admin_group.command(name="コイン削減", description="[管理者専用] 特定のユーザーのコインを削減します。")
    @app_commands.describe(user="コインを削減するユーザー", amount="削減するコインの量")
    @app_commands.check(is_admin)
    async def take_coin(self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 1, None]):
        await interaction.response.defer(ephemeral=True)
        currency_icon = get_config("GAME_CONFIG", {}).get("CURRENCY_ICON", "🪙")

        result = await update_wallet(user, -amount)
        if result:
            await self.log_coin_admin_action(interaction.user, user, -amount, "削減")
            await interaction.followup.send(f"✅ {user.mention}さんの残高から `{amount:,}`{currency_icon}を削減しました。")
        else:
            await interaction.followup.send("❌ コイン削減中にエラーが発生しました。")
            
    async def _trigger_level_up_events(self, user: discord.Member, result_data: Dict[str, Any]):
        if not result_data or not result_data.get('leveled_up'):
            return
        new_level = result_data.get('new_level')
        if not new_level:
            return
        logger.info(f"유저 {user.display_name}(ID: {user.id})가 레벨 {new_level}(으)로 변경되어, 레벨업 이벤트를 트리거합니다.")
        game_config = get_config("GAME_CONFIG", {})
        job_advancement_levels = game_config.get("JOB_ADVANCEMENT_LEVELS", [])
        timestamp = time.time()
        
        if new_level in job_advancement_levels:
            await save_config_to_db(f"job_advancement_request_{user.id}", {"level": new_level, "timestamp": timestamp})
            logger.info(f"유저가 전직 가능 레벨({new_level})에 도달하여 DB에 전직 요청을 기록했습니다.")

        await save_config_to_db(f"level_tier_update_request_{user.id}", {"level": new_level, "timestamp": timestamp})
        logger.info(f"유저의 레벨이 변경되어 DB에 등급 역할 업데이트 요청을 기록했습니다.")

    async def _update_user_xp_and_level(self, user: discord.Member, xp_to_add: int = 0, source: str = 'admin', exact_level: Optional[int] = None) -> tuple[int, int]:
        res = await supabase.table('user_levels').select('level, xp').eq('user_id', user.id).maybe_single().execute()
        
        if res and res.data:
            current_data = res.data
        else:
            current_data = {'level': 1, 'xp': 0}

        current_level, current_xp = current_data['level'], current_data['xp']
        
        new_total_xp = current_xp
        leveled_up = False

        if exact_level is not None:
            new_level = exact_level
            new_total_xp = calculate_xp_for_level(new_level)
            if new_level > current_level:
                leveled_up = True
        else:
            new_total_xp += xp_to_add
            if xp_to_add > 0:
                await supabase.table('xp_logs').insert({'user_id': user.id, 'source': source, 'xp_amount': xp_to_add}).execute()
            
            new_level = current_level
            # [개선] 레벨업 공식을 사용하여 다음 레벨까지 필요한 총 경험치량과 비교
            while new_total_xp >= calculate_xp_for_level(new_level + 1):
                new_level += 1
            
            if new_level > current_level:
                leveled_up = True
        
        await supabase.table('user_levels').upsert({
            'user_id': user.id,
            'level': new_level,
            'xp': new_total_xp
        }).execute()
        
        if leveled_up:
            await self._trigger_level_up_events(user, {"leveled_up": True, "new_level": new_level})
            
        return new_level, new_total_xp

    @admin_group.command(name="xp부여", description="[관리자 전용] 특정 유저에게 XP를 부여합니다.")
    @app_commands.describe(user="XP를 부여할 유저", amount="부여할 XP 양")
    @app_commands.check(is_admin)
    async def give_xp(self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 1, None]):
        await interaction.response.defer(ephemeral=True)
        try:
            new_level, _ = await self._update_user_xp_and_level(user, xp_to_add=amount, source='admin')
            await interaction.followup.send(f"✅ {user.mention}님에게 XP `{amount}`를 부여했습니다. (현재 레벨: {new_level})")
        except Exception as e:
            logger.error(f"XP 부여 중 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ XP 부여 중 오류가 발생했습니다.")

    @admin_group.command(name="레벨설정", description="[관리자 전용] 특정 유저의 레벨을 강제로 설정합니다.")
    @app_commands.describe(user="레벨을 설정할 유저", level="설정할 레벨")
    @app_commands.check(is_admin)
    async def set_level(self, interaction: discord.Interaction, user: discord.Member, level: app_commands.Range[int, 1, None]):
        await interaction.response.defer(ephemeral=True)
        try:
            await self._update_user_xp_and_level(user, exact_level=level)
            await interaction.followup.send(f"✅ {user.mention}님의 레벨을 **{level}**로 설정했습니다。")
        except Exception as e:
            logger.error(f"레벨 설정 중 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ レベル設定中にエラーが発生しました。")
            
async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))
