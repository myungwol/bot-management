# cogs/server/system.py (모든 기능 포함, 생략 없는 최종본)

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import logging
import asyncio
from typing import Optional

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 데이터베이스 함수 임포트
from utils.database import (
    get_counter_configs, get_channel_id_from_db, get_role_id,
    save_panel_id, get_panel_id, delete_panel_id,
    add_auto_role_panel, delete_auto_role_panel,
    delete_all_buttons_for_panel,
    save_embed_to_db, get_embed_from_db,
    save_channel_id_to_db
)

# --- 코드 기반 패널 데이터 구조 ---
STATIC_AUTO_ROLE_PANELS = {
    "main_roles": {
        "channel_key": "auto_role_channel_id",
        "embed": {"title": "📜 役割選択", "description": "下のボタンを押して、希望する役割のカテゴリーを選択してください！", "color": 0x5865F2},
        "categories": [
            {"id": "notifications", "label": "通知役割", "emoji": "📢"},
            {"id": "games", "label": "ゲーム役割", "emoji": "🎮"},
        ],
        "roles": {
            "notifications": [
                {"role_id_key": "mention_role_1", "label": "サーバー全体通知", "description": "サーバーの重要なお知らせを受け取ります。"},
            ],
            "games": []
        }
    }
}

# --- View / Modal 정의 ---
class EphemeralRoleSelectView(ui.View):
    def __init__(self, member: discord.Member, category_roles: list, all_category_role_ids: set[int]):
        super().__init__(timeout=180)
        self.member = member; self.all_category_role_ids = all_category_role_ids
        current_user_role_ids = {r.id for r in self.member.roles}
        options = [discord.SelectOption(label=info['label'], value=str(rid), description=info.get('description'), default=(rid in current_user_role_ids)) for info in category_roles if (rid := get_role_id(info['role_id_key']))]
        self.role_select = ui.Select(placeholder="希望する役割をすべて選択してください...", min_values=0, max_values=len(options) or 1, options=options)
        self.role_select.callback = self.select_callback; self.add_item(self.role_select)
    async def select_callback(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        selected_ids = {int(rid) for rid in self.role_select.values}; current_ids = {r.id for r in i.user.roles}
        to_add_ids = selected_ids - current_ids; to_remove_ids = (self.all_category_role_ids - selected_ids) & current_ids
        try:
            if to_add := [i.guild.get_role(rid) for rid in to_add_ids if i.guild.get_role(rid)]: await i.user.add_roles(*to_add)
            if to_remove := [i.guild.get_role(rid) for rid in to_remove_ids if i.guild.get_role(rid)]: await i.user.remove_roles(*to_remove)
            self.role_select.disabled = True; await i.edit_original_response(content="✅ 役割が正常に更新されました。", view=self); self.stop()
        except Exception as e: logger.error(f"ドロップダウン役割処理エラー: {e}"); await i.followup.send("❌ エラーが発生しました。", ephemeral=True)

class AutoRoleView(ui.View):
    def __init__(self, panel_config: dict):
        super().__init__(timeout=None); self.panel_config = panel_config
        for category in self.panel_config.get("categories", []):
            button = ui.Button(label=category['label'], emoji=category.get('emoji'), style=discord.ButtonStyle.secondary, custom_id=f"category_select:{category['id']}")
            button.callback = self.category_button_callback; self.add_item(button)
    async def category_button_callback(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True); category_id = i.data['custom_id'].split(':')[1]
        category_roles = self.panel_config.get("roles", {}).get(category_id, [])
        if not category_roles: return await i.followup.send("選択したカテゴリーに設定された役割がありません。", ephemeral=True)
        all_ids = {get_role_id(r['role_id_key']) for r in category_roles if get_role_id(r['role_id_key'])}
        embed = discord.Embed(title=f"「{category_id.capitalize()}」役割選択", description="下のドロップダウンメニューで希望する役割をすべて選択してください。", color=discord.Color.blue())
        await i.followup.send(embed=embed, view=EphemeralRoleSelectView(i.user, category_roles, all_ids), ephemeral=True)

class EmbedEditModal(ui.Modal, title="埋め込み内容編集"):
    def __init__(self, embed: discord.Embed):
        super().__init__(); self.embed = embed
        self.embed_title = ui.TextInput(label="タイトル", default=embed.title, required=False, max_length=256)
        self.embed_description = ui.TextInput(label="説明 (\\n = 改行)", style=discord.TextStyle.paragraph, default=embed.description, required=False, max_length=4000)
        self.add_item(self.embed_title); self.add_item(self.embed_description)
    async def on_submit(self, i: discord.Interaction):
        self.embed.title = self.embed_title.value; self.embed.description = self.embed_description.value.replace('\\n', '\n')
        await i.response.edit_message(embed=self.embed)

class EmbedEditorView(ui.View):
    def __init__(self, message: discord.Message, embed_key: str):
        super().__init__(timeout=None); self.message = message; self.embed_key = embed_key
    @ui.button(label="タイトル/説明を編集", emoji="✍️")
    async def edit_content(self, i: discord.Interaction, b: ui.Button): await i.response.send_modal(EmbedEditModal(self.message.embeds[0]))
    @ui.button(label="DBに保存", style=discord.ButtonStyle.success, emoji="💾")
    async def save_to_db(self, i: discord.Interaction, b: ui.Button):
        await i.response.defer(ephemeral=True); await save_embed_to_db(self.embed_key, self.message.embeds[0].to_dict())
        await i.followup.send(f"✅ DBに「{self.embed_key}」キーで保存しました。", ephemeral=True)
    @ui.button(label="編集機を削除", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_editor(self, i: discord.Interaction, b: ui.Button): await self.message.delete(); self.stop()

# --- メイン Cog クラス ---
class ServerSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.welcome_channel_id: Optional[int] = None
        self.farewell_channel_id: Optional[int] = None
        self.temp_user_role_id: Optional[int] = None
        self.counter_configs = []
        self.update_tasks: dict[int, asyncio.Task] = {}
        logger.info("ServerSystem Cog initialized.")

    async def cog_load(self):
        await self.load_all_configs()
        self.update_counters_loop.start()

    def cog_unload(self):
        self.update_counters_loop.cancel()
        for task in self.update_tasks.values(): task.cancel()

    async def load_all_configs(self):
        self.welcome_channel_id = await get_channel_id_from_db("welcome_channel_id")
        self.farewell_channel_id = await get_channel_id_from_db("farewell_channel_id")
        self.temp_user_role_id = get_role_id("temp_user_role")
        self.counter_configs = await get_counter_configs()
        logger.info("[ServerSystem Cog] Loaded all configurations.")
    
    async def regenerate_panel(self, channel: discord.TextChannel | None = None):
        for panel_key, panel_config in STATIC_AUTO_ROLE_PANELS.items():
            try:
                target_channel = channel
                if target_channel is None:
                    channel_id = self.bot.channel_configs.get(panel_config['channel_key'])
                    if not channel_id or not (target_channel := self.bot.get_channel(channel_id)):
                        logger.info(f"ℹ️ '{panel_key}' パネルチャンネルがDBに設定されていないため、スキップします。")
                        continue
                
                embed = discord.Embed.from_dict(panel_config['embed'])
                view = AutoRoleView(panel_config)
                panel_info = await get_panel_id(panel_key)
                message_id = panel_info.get('message_id') if panel_info else None
                
                live_message = None
                if message_id:
                    try:
                        live_message = await target_channel.fetch_message(message_id)
                        await live_message.edit(embed=embed, view=view)
                        logger.info(f"✅ '{panel_key}' パネルを更新しました。")
                    except discord.NotFound:
                        live_message = None
                
                if not live_message:
                    new_message = await target_channel.send(embed=embed, view=view)
                    await save_panel_id(panel_key, new_message.id, target_channel.id)
                    logger.info(f"✅ '{panel_key}' パネルを新規作成しました。")
                    await add_auto_role_panel(new_message.id, target_channel.guild.id, target_channel.id, embed.title, embed.description)
                    await delete_all_buttons_for_panel(new_message.id)

            except Exception as e:
                logger.error(f"❌ '{panel_key}' パネルの処理中にエラーが発生しました: {e}", exc_info=True)

    def _schedule_counter_update(self, guild: discord.Guild):
        guild_id = guild.id
        if guild_id in self.update_tasks and not self.update_tasks[guild_id].done(): self.update_tasks[guild_id].cancel()
        self.update_tasks[guild_id] = asyncio.create_task(self.delayed_update(guild))

    async def delayed_update(self, guild: discord.Guild):
        await asyncio.sleep(5)
        await self.update_all_counters(guild)

    async def update_all_counters(self, guild: discord.Guild):
        if not guild or not (guild_configs := [c for c in self.counter_configs if c['guild_id'] == guild.id]): return
        all_m, human_m, bot_m, boost_c = len(guild.members), len([m for m in guild.members if not m.bot]), len([m for m in guild.members if m.bot]), guild.premium_subscription_count
        for config in guild_configs:
            if not (channel := guild.get_channel(config['channel_id'])): continue
            c_type = config['counter_type']; count = 0
            if c_type == 'total': count = all_m
            elif c_type == 'members': count = human_m
            elif c_type == 'bots': count = bot_m
            elif c_type == 'boosters': count = boost_c
            elif c_type == 'role' and (role := guild.get_role(config['role_id'])): count = len(role.members)
            if channel.name != (new_name := config['format_string'].format(count)):
                try: await channel.edit(name=new_name, reason="カウンター自動更新")
                except Exception as e: logger.error(f"カウンターチャンネル {channel.id} の更新に失敗しました: {e}"); break

    @tasks.loop(minutes=10)
    async def update_counters_loop(self):
        for guild in self.bot.guilds: await self.update_all_counters(guild)

    @update_counters_loop.before_loop
    async def before_update_counters_loop(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot: return
        if self.temp_user_role_id and (role := member.guild.get_role(self.temp_user_role_id)):
            try: await member.add_roles(role)
            except Exception as e: logger.error(f"一時的な役割の付与に失敗しました: {e}")
        if self.welcome_channel_id and (ch := self.bot.get_channel(self.welcome_channel_id)):
            if embed_data := await get_embed_from_db('welcome_embed'):
                desc = embed_data.get('description', '').format(member_mention=member.mention, member_name=member.display_name, guild_name=member.guild.name)
                embed_data['description'] = desc; embed = discord.Embed.from_dict(embed_data)
                if member.display_avatar: embed.set_thumbnail(url=member.display_avatar.url)
                try: await ch.send(f"@everyone, {member.mention}", embed=embed, allowed_mentions=discord.AllowedMentions(everyone=True, users=True))
                except Exception as e: logger.error(f"歓迎メッセージの送信に失敗しました: {e}")
        self._schedule_counter_update(member.guild)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if self.farewell_channel_id and (ch := self.bot.get_channel(self.farewell_channel_id)):
            if embed_data := await get_embed_from_db('farewell_embed'):
                embed_data['description'] = embed_data.get('description', '').format(member_name=member.display_name)
                embed = discord.Embed.from_dict(embed_data)
                if member.display_avatar: embed.set_thumbnail(url=member.display_avatar.url)
                try: await ch.send(embed=embed)
                except Exception as e: logger.error(f"お別れメッセージの送信に失敗しました: {e}")
        self._schedule_counter_update(member.guild)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles != after.roles or before.premium_since != after.premium_since:
            self._schedule_counter_update(after.guild)

    setup_group = app_commands.Group(name="setup", description="[管理者] ボットの主要機能を設定します。")
    @setup_group.command(name="panel", description="指定されたチャンネルに機能パネルを設置します。")
    @app_commands.describe(channel="パネルを設置するチャンネル", panel_type="設置するパネルの種類")
    @app_commands.choices(panel_type=[
        app_commands.Choice(name="役割パネル", value="roles"),
        app_commands.Choice(name="案内パネル (オンボーディング)", value="onboarding"),
        app_commands.Choice(name="名前変更パネル", value="nicknames"),
        app_commands.Choice(name="商店街パネル (売買)", value="commerce"),
        app_commands.Choice(name="釣り場パネル", value="fishing"),
        app_commands.Choice(name="持ち物パネル", value="profile"),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_panel(self, interaction: discord.Interaction, channel: discord.TextChannel, panel_type: str):
        await interaction.response.defer(ephemeral=True)
        panel_map = {
            "roles": {"cog": "ServerSystem", "key": "auto_role_channel_id"},
            "onboarding": {"cog": "Onboarding", "key": "onboarding_panel_channel_id"},
            "nicknames": {"cog": "Nicknames", "key": "nickname_panel_channel_id"},
            "commerce": {"cog": "Commerce", "key": "commerce_panel_channel_id"},
            "fishing": {"cog": "Fishing", "key": "fishing_panel_channel_id"},
            "profile": {"cog": "UserProfile", "key": "inventory_panel_channel_id"},
        }
        config = panel_map.get(panel_type)
        if not config: return await interaction.followup.send("❌ 無効なパネルタイプです。", ephemeral=True)
        cog_to_run = self.bot.get_cog(config["cog"])
        if not cog_to_run or not hasattr(cog_to_run, 'regenerate_panel'):
            return await interaction.followup.send(f"❌ '{config['cog']}' Cogが見つからないか、'regenerate_panel' 関数がありません。", ephemeral=True)
        try:
            await cog_to_run.regenerate_panel(channel)
            await save_channel_id_to_db(config["key"], channel.id)
            self.bot.channel_configs[config["key"]] = channel.id
            await interaction.followup.send(f"✅ `{channel.mention}` に **{panel_type}** パネルを設置しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"Panel setup command failed for {panel_type}: {e}", exc_info=True)
            await interaction.followup.send(f"❌ パネル設置中にエラーが発生しました: {e}", ephemeral=True)

    @setup_group.command(name="welcome-message", description="歓迎メッセージの編集機を作成します。")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_welcome_message(self, i: discord.Interaction, c: discord.TextChannel): await self.create_message_editor(i, c, 'welcome_embed', "歓迎メッセージ")
    @setup_group.command(name="farewell-message", description="お別れメッセージの編集機を作成します。")
    @app_c
