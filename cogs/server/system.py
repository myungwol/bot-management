# cogs/server/system.py (DB 키 규칙 일치 최종 수정본)

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import logging
import asyncio
from typing import Optional

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# [수정] 새로운 DB 함수 임포트
from utils.database import (
    get_id as get_channel_id, get_role_id,
    save_id_to_db as save_channel_id_to_db,
    save_panel_id, get_panel_id, get_embed_from_db
)

# [수정] DB 키 이름(role_id_key)을 database.py의 get_role_id 함수 규칙에 맞게 변경 (접두사 'role_' 제거)
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
                {"role_id_key": "notify_festival", "label": "祭り", "description": "お祭りやイベント関連の通知を受け取ります。"},
                {"role_id_key": "notify_voice", "label": "通話", "description": "通話募集の通知を受け取ります。"},
                {"role_id_key": "notify_friends", "label": "友達", "description": "友達募集の通知を受け取ります。"},
                {"role_id_key": "notify_disboard", "label": "ディスボード", "description": "Disboard通知を受け取ります。"},
                {"role_id_key": "notify_up", "label": "アップ", "description": "Up通知を受け取ります。"},
            ],
            "games": [
                {"role_id_key": "game_minecraft", "label": "マインクラフト", "description": "マインクラフト関連の募集に参加します。"},
                {"role_id_key": "game_valorant", "label": "ヴァロラント", "description": "ヴァロラント関連の募集に参加します。"},
                {"role_id_key": "game_overwatch", "label": "オーバーウォッチ", "description": "オーバーウォッチ関連の募集に参加します。"},
                {"role_id_key": "game_lol", "label": "リーグ・オブ・レジェンド", "description": "LoL関連の募集に参加します。"},
                {"role_id_key": "game_mahjong", "label": "麻雀", "description": "麻雀関連の募集に参加します。"},
                {"role_id_key": "game_amongus", "label": "アモングアス", "description": "Among Us関連の募集に参加します。"},
                {"role_id_key": "game_mh", "label": "モンスターハンター", "description": "モンハン関連の募集に参加します。"},
                {"role_id_key": "game_genshin", "label": "原神", "description": "原神関連の募集に参加します。"},
                {"role_id_key": "game_apex", "label": "エーペックスレジェンズ", "description": "Apex Legends関連の募集に参加します。"},
                {"role_id_key": "game_splatoon", "label": "スプラトゥーン", "description": "スプラトゥーン関連の募集に参加します。"},
                {"role_id_key": "game_gf", "label": "ゴッドフィールド", "description": "ゴッドフィールド関連の募集に参加します。"},
                {"role_id_key": "platform_steam", "label": "スチーム", "description": "Steamでプレイするゲームの募集に参加します。"},
                {"role_id_key": "platform_smartphone", "label": "スマートフォン", "description": "スマホゲームの募集に参加します。"},
                {"role_id_key": "platform_switch", "label": "スイッチ", "description": "Nintendo Switchゲームの募集に参加します。"},
            ]
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

class ServerSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.welcome_channel_id: Optional[int] = None
        self.farewell_channel_id: Optional[int] = None
        self.temp_user_role_id: Optional[int] = None
        self.counter_configs: list = []
        self.update_tasks: dict[int, asyncio.Task] = {}
        logger.info("ServerSystem Cog initialized.")

    async def cog_load(self):
        await self.load_all_configs()
        self.update_counters_loop.start()

    def cog_unload(self):
        self.update_counters_loop.cancel()
        for task in self.update_tasks.values(): task.cancel()

    async def load_all_configs(self):
        self.welcome_channel_id = get_channel_id("welcome_channel_id")
        self.farewell_channel_id = get_channel_id("farewell_channel_id")
        self.temp_user_role_id = get_role_id("temp_user")
        # counter_configs는 다른 테이블을 사용하므로 그대로 둡니다.
        # self.counter_configs = await get_counter_configs() 
        logger.info("[ServerSystem Cog] Loaded all configurations.")
    
    async def regenerate_panel(self, channel: discord.TextChannel | None = None):
        for panel_key, panel_config in STATIC_AUTO_ROLE_PANELS.items():
            try:
                target_channel = channel
                if target_channel is None:
                    channel_id = get_channel_id(panel_config['channel_key'])
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

            except Exception as e:
                logger.error(f"❌ '{panel_key}' パネルの処理中にエラーが発生しました: {e}", exc_info=True)

    def _schedule_counter_update(self, guild: discord.Guild):
        guild_id = guild.id
        if guild_id in self.update_tasks and not self.update_tasks[guild_id].done(): self.update_tasks[guild_id].cancel()
        self.update_tasks[guild_id] = asyncio.create_task(self.delayed_update(guild))

    async def delayed_update(self, guild: discord.Guild):
        await asyncio.sleep(5)
        # 카운터 기능은 현재 사용하지 않으므로 주석 처리
        # await self.update_all_counters(guild)

    # (카운터 관련 로직은 현재 사용하지 않으므로 주석 처리 또는 삭제 가능)
    # async def update_all_counters(self, guild: discord.Guild): ...
    # @tasks.loop(minutes=10) ...

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

    @app_commands.command(name="setup", description="[管理者] ボットの各種チャンネルを設定またはパネルを設置します。")
    @app_commands.describe(
        setting_type="設定したい項目を選択してください。",
        channel="設定対象のチャンネルを指定してください。"
    )
    @app_commands.choices(setting_type=[
        app_commands.Choice(name="[パネル] 役割パネル", value="panel_roles"),
        app_commands.Choice(name="[パネル] 案内パネル (オンボーディング)", value="panel_onboarding"),
        app_commands.Choice(name="[パネル] 名前変更パネル", value="panel_nicknames"),
        app_commands.Choice(name="[パネル] 商店街パネル (売買)", value="panel_commerce"),
        app_commands.Choice(name="[パネル] 釣り場パネル", value="panel_fishing"),
        app_commands.Choice(name="[パネル] 持ち物パネル", value="panel_profile"),
        app_commands.Choice(name="[チャンネル] 自己紹介承認チャンネル", value="channel_onboarding_approval"),
        app_commands.Choice(name="[チャンネル] 名前変更承認チャンネル", value="channel_nickname_approval"),
        app_commands.Choice(name="[チャンネル] 新規参加者歓迎チャンネル", value="channel_new_welcome"),
        app_commands.Choice(name="[ログ] 名前変更ログ", value="log_nickname"),
        app_commands.Choice(name="[ログ] 釣りログ", value="log_fishing"),
        app_commands.Choice(name="[ログ] コインログ", value="log_coin"),
        app_commands.Choice(name="[ログ] 自己紹介承認ログ", value="log_intro_approval"),
        app_commands.Choice(name="[ログ] 自己紹介拒否ログ", value="log_intro_rejection"),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_unified(self, interaction: discord.Interaction, setting_type: str, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)

        setup_map = {
            "panel_roles": {"type": "panel", "cog": "ServerSystem", "key": "auto_role_channel_id", "friendly_name": "役割パネル"},
            "panel_onboarding": {"type": "panel", "cog": "Onboarding", "key": "onboarding_panel_channel_id", "friendly_name": "案内パネル"},
            "panel_nicknames": {"type": "panel", "cog": "Nicknames", "key": "nickname_panel_channel_id", "friendly_name": "名前変更パネル"},
            "panel_commerce": {"type": "panel", "cog": "Commerce", "key": "commerce_panel_channel_id", "friendly_name": "商店街パネル"},
            "panel_fishing": {"type": "panel", "cog": "Fishing", "key": "fishing_panel_channel_id", "friendly_name": "釣り場パネル"},
            "panel_profile": {"type": "panel", "cog": "UserProfile", "key": "inventory_panel_channel_id", "friendly_name": "持ち物パネル"},
            "channel_onboarding_approval": {"type": "channel", "cog_name": "Onboarding", "key": "onboarding_approval_channel_id", "attr": "approval_channel_id", "friendly_name": "自己紹介承認チャンネル"},
            "channel_nickname_approval": {"type": "channel", "cog_name": "Nicknames", "key": "nickname_approval_channel_id", "attr": "approval_channel_id", "friendly_name": "名前変更承認チャンネル"},
            "channel_new_welcome": {"type": "channel", "cog_name": "Onboarding", "key": "new_welcome_channel_id", "attr": "new_welcome_channel_id", "friendly_name": "新規参加者歓迎チャンネル"},
            "log_nickname": {"type": "channel", "cog_name": "Nicknames", "key": "nickname_log_channel_id", "attr": "nickname_log_channel_id", "friendly_name": "名前変更ログ"},
            "log_fishing": {"type": "channel", "cog_name": "Fishing", "key": "fishing_log_channel_id", "attr": "fishing_log_channel_id", "friendly_name": "釣りログ"},
            "log_coin": {"type": "channel", "cog_name": "EconomyCore", "key": "coin_log_channel_id", "attr": "coin_log_channel_id", "friendly_name": "コインログ"},
            "log_intro_approval": {"type": "channel", "cog_name": "Onboarding", "key": "introduction_channel_id", "attr": "introduction_channel_id", "friendly_name": "自己紹介承認ログ"},
            "log_intro_rejection": {"type": "channel", "cog_name": "Onboarding", "key": "introduction_rejection_log_channel_id", "attr": "rejection_log_channel_id", "friendly_name": "自己紹介拒否ログ"},
        }

        config = setup_map.get(setting_type)
        if not config:
            return await interaction.followup.send("❌ 無効な設定タイプです。", ephemeral=True)

        try:
            if config["type"] == "panel":
                cog_to_run = self.bot.get_cog(config["cog"])
                if not cog_to_run or not hasattr(cog_to_run, 'regenerate_panel'):
                    return await interaction.followup.send(f"❌ '{config['cog']}' Cogが見つからないか、'regenerate_panel' 関数がありません。", ephemeral=True)
                
                await cog_to_run.regenerate_panel(channel)
                await save_channel_id_to_db(config["key"], channel.id)
                await interaction.followup.send(f"✅ `{channel.mention}` に **{config['friendly_name']}** を設置しました。", ephemeral=True)
            
            elif config["type"] == "channel":
                db_key = config["key"]
                cog_name = config["cog_name"]
                attribute_to_set = config.get("attr", db_key)
                
                await save_channel_id_to_db(db_key, channel.id)
                
                target_cog = self.bot.get_cog(cog_name)
                if target_cog:
                    setattr(target_cog, attribute_to_set, channel.id) 
                    logger.info(f"✅ Live updated {cog_name}'s {attribute_to_set} to {channel.id}")
                else:
                    logger.warning(f"Could not find cog {cog_name} to update attribute live.")
                
                await interaction.followup.send(f"✅ `{channel.mention}`を**{config['friendly_name']}**として設定しました。", ephemeral=True)

        except Exception as e:
            logger.error(f"Unified setup command failed for {setting_type}: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 設定中にエラーが発生しました: {e}", ephemeral=True)

    setup_group = app_commands.Group(name="message", description="[管理者] 送信するメッセージの内容を編集します。")
    
    @setup_group.command(name="welcome", description="歓迎メッセージの編集機を作成します。")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_welcome_message(self, i: discord.Interaction, c: discord.TextChannel): await self.create_message_editor(i, c, 'welcome_embed', "歓迎メッセージ")
    
    @setup_group.command(name="farewell", description="お別れメッセージの編集機を作成します。")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_farewell_message(self, i: discord.Interaction, c: discord.TextChannel): await self.create_message_editor(i, c, 'farewell_embed', "お別れメッセージ")
    
    async def create_message_editor(self, i: discord.Interaction, ch: discord.TextChannel, key: str, name: str):
        await i.response.defer(ephemeral=True)
        embed_data = await get_embed_from_db(key) or {"title": f"{name} タイトル", "description": f"{name} の説明を入力してください。"}
        embed = discord.Embed.from_dict(embed_data)
        msg = await ch.send(content=f"**{name} 編集機**", embed=embed)
        await msg.edit(view=EmbedEditorView(msg, key))
        await i.followup.send(f"`{ch.mention}` に {name} 編集機を作成しました。", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))```

---

### 2. `cogs/server/onboarding.py` (수정된 전체 코드)

`get_role_id`와 `get_channel_id`를 호출하는 모든 부분의 키를 새로운 DB 규칙에 맞게 수정했습니다.

```python
# cogs/server/onboarding.py (DB 키 규칙 일치 최종 수정본)

import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
import logging
import re
from datetime import datetime
import time

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# [수정] 새로운 DB 함수 임포트
from utils.database import (
    get_panel_id, save_panel_id, get_channel_id, 
    get_role_id, get_auto_role_mappings, get_cooldown, set_cooldown,
    get_id
)

GUIDE_PAGES = [
    {"type": "info", "title": "🏡 Dico森へようこそ！ ✨", "description": "➡️ 次に進むには、下の「次へ」ボタンを押してください 📩"},
    {"type": "action", "title": "ボット紹介", "description": "**下のボタンを押すと、次の段階である「里の掟」チャンネルを閲覧する権限が付与されます。**", "button_label": "ボットの紹介を確認しました", "role_key": "onboarding_step_1"},
    {"type": "action", "title": "里の掟", "description": "「里の掟」チャンネルが閲覧可能になりました。\n\n## <#1404410157504397322>\n\n上記のチャンネルに移動し、すべての掟をよく確認してください。", "button_label": "掟を確認しました", "role_key": "onboarding_step_2"},
    {"type": "action", "title": "里の地図", "description": "次は、里のチャンネルについての案内です。\n\n## <#1404410171689664552>\n\nですべてのチャンネルの役割を確認してください。", "button_label": "地図を確認しました", "role_key": "onboarding_step_3"},
    {"type": "action", "title": "依頼掲示板", "description": "次は依頼掲示板の確認です。\n\n## <#1404410186562666546>", "button_label": "依頼掲示板を確認しました", "role_key": "onboarding_step_4"},
    {"type": "intro", "title": "住人登録票 (最終段階)", "description": "すべての案内を確認しました！いよいよ最終段階です。\n\n**下のボタンを押して、住人登録票を作成してください。**\n登録票が公務員によって承認されると、正式にすべての場所が利用可能になります。", "rules": "・性別の記載は必須です\n・年齢を非公開にしたい場合は、公務員に個別にご連絡ください\n・名前に特殊文字は使用できません\n・漢字は4文字まで、ひらがな・カタカナ・英数字は合わせて8文字まで可能です\n・不適切な名前は拒否される場合があります\n・未記入の項目がある場合、拒否されることがあります\n・参加経路も必ずご記入ください。（例：Disboard、〇〇からの招待など）"}
]

class RejectionReasonModal(ui.Modal, title="拒否理由入力"):
    reason = ui.TextInput(label="拒否理由", placeholder="拒否する理由を具体的に入力してください。", style=discord.TextStyle.paragraph, required=True, max_length=200)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

class IntroductionModal(ui.Modal, title="住人登録票"):
    name = ui.TextInput(label="名前", placeholder="里で使用する名前を記入してください", required=True, max_length=12)
    age = ui.TextInput(label="年齢", placeholder="例：20代、90年生まれ、30歳、非公開", required=True, max_length=20)
    gender = ui.TextInput(label="性別", placeholder="例：男、女性", required=True, max_length=10)
    hobby = ui.TextInput(label="趣味・好きなこと", placeholder="趣味や好きなことを自由に記入してください", style=discord.TextStyle.paragraph, required=True, max_length=500)
    path = ui.TextInput(label="参加経路", placeholder="例：Disboard、〇〇からの招待など", style=discord.TextStyle.paragraph, required=True, max_length=200)

    def __init__(self, approval_role_id: int):
        super().__init__()
        self.approval_role_id = approval_role_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            onboarding_cog = interaction.client.get_cog("Onboarding")
            if not onboarding_cog or not onboarding_cog.approval_channel_id:
                return await interaction.followup.send("❌ エラー: Onboarding機能が設定されていません。", ephemeral=True)
            approval_channel = interaction.guild.get_channel(onboarding_cog.approval_channel_id)
            if not approval_channel: return await interaction.followup.send("❌ エラー: 承認チャンネルが見つかりません。", ephemeral=True)
            await set_cooldown(f"intro_{interaction.user.id}", time.time())
            
            embed = discord.Embed(title="📝 新しい住人登録票が提出されました", description=f"**作成者:** {interaction.user.mention}", color=discord.Color.blue())
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            embed.add_field(name="名前", value=self.name.value, inline=False)
            embed.add_field(name="年齢", value=self.age.value, inline=False)
            embed.add_field(name="性別", value=self.gender.value, inline=False)
            embed.add_field(name="趣味・好きなこと", value=self.hobby.value, inline=False)
            embed.add_field(name="参加経路", value=self.path.value, inline=False)
            
            await approval_channel.send(
                content=f"<@&{self.approval_role_id}> 新しい住人登録票が提出されました。",
                embed=embed,
                view=ApprovalView(author=interaction.user, original_embed=embed, bot=interaction.client, approval_role_id=self.approval_role_id, auto_role_mappings=onboarding_cog.auto_role_mappings)
            )
            await interaction.followup.send("✅ 住人登録票を公務員に提出しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"Error submitting self-introduction: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 予期せぬエラーが発生しました。", ephemeral=True)

class ApprovalView(ui.View):
    def __init__(self, author: discord.Member, original_embed: discord.Embed, bot: commands.Bot, approval_role_id: int, auto_role_mappings: list):
        super().__init__(timeout=None)
        self.author_id = author.id
        self.original_embed = original_embed
        self.bot = bot
        self.approval_role_id = approval_role_id
        self.auto_role_mappings = auto_role_mappings
        self.rejection_reason: str | None = None

    def _parse_birth_year(self, text: str) -> int | None:
        text = text.strip().lower()
        if "非公開" in text or "ひこうかい" in text: return 0
        era_patterns = {'heisei': r'(?:h|平成)\s*(\d{1,2})', 'showa': r'(?:s|昭和)\s*(\d{1,2})', 'reiwa': r'(?:r|令和)\s*(\d{1,2})'}
        era_start_years = {"heisei": 1989, "showa": 1926, "reiwa": 2019}
        for era, pattern in era_patterns.items():
            match = re.search(pattern, text)
            if match: return era_start_years[era] + int(match.group(1)) - 1
        dai_match = re.search(r'(\d{1,2})\s*代', text)
        if dai_match: return datetime.now().year - (int(dai_match.group(1)) + 5)
        year_match = re.search(r'(\d{2,4})', text)
        if year_match and ("年" in text or "生まれ" in text):
            year = int(year_match.group(1))
            if year < 100: year += 1900 if year > datetime.now().year % 100 else 2000
            return year
        age_match = re.search(r'(\d+)', text)
        if age_match and ("歳" in text or "才" in text): return datetime.now().year - int(age_match.group(1))
        return None

    async def _check_permission(self, interaction: discord.Interaction) -> bool:
        if not self.approval_role_id:
            await interaction.response.send_message("エラー: 承認役割IDが設定されていません。", ephemeral=True)
            return False
        if not isinstance(interaction.user, discord.Member) or not any(role.id == self.approval_role_id for role in interaction.user.roles):
            await interaction.response.send_message("このボタンを押す権限がありません。", ephemeral=True)
            return False
        return True

    async def _handle_approval(self, interaction: discord.Interaction, approved: bool):
        if not await self._check_permission(interaction): return
        
        member = interaction.guild.get_member(self.author_id)
        if not member:
            return await interaction.response.send_message("エラー: 対象のメンバーがサーバーに見つかりませんでした。", ephemeral=True)

        status_text = "承認" if approved else "拒否"
        original_message = interaction.message
        if not approved:
            rejection_modal = RejectionReasonModal()
            await interaction.response.send_modal(rejection_modal)
            if await rejection_modal.wait(): return
            self.rejection_reason = rejection_modal.reason.value
        else:
            await interaction.response.defer()

        for item in self.children: item.disabled = True
        processing_embed = discord.Embed(title=f"⏳ {status_text}処理中...", description=f"{member.mention}さんの住人登録票を処理しています。", color=discord.Color.orange())
        try: await original_message.edit(embed=processing_embed, view=self)
        except (discord.NotFound, discord.HTTPException): pass
        
        try:
            if approved: await self._perform_approval_tasks(interaction, member)
            else: await self._perform_rejection_tasks(interaction, member)
            await interaction.followup.send(f"✅ {status_text}処理が正常に完了しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"Error during approval/rejection tasks: {e}", exc_info=True)
            await interaction.followup.send(f"❌ {status_text}処理中にエラーが発生しました。\n`{e}`", ephemeral=True)
        finally:
            try: await original_message.delete()
            except discord.NotFound: pass

    async def _perform_approval_tasks(self, i: discord.Interaction, member: discord.Member):
        tasks = []; cog = self.bot.get_cog("Onboarding")
        if cog.introduction_channel_id and (ch := i.guild.get_channel(cog.introduction_channel_id)):
            embed = self.original_embed.copy(); embed.title = "ようこそ！新しい仲間です！"; embed.color = discord.Color.green()
            embed.add_field(name="承認した公務員", value=i.user.mention, inline=False)
            tasks.append(ch.send(content=member.mention, embed=embed, allowed_mentions=discord.AllowedMentions(users=True)))
        if cog.new_welcome_channel_id and (ch := i.guild.get_channel(cog.new_welcome_channel_id)):
            tasks.append(self._send_new_welcome_message(member, ch, cog.mention_role_id_1))
        async def send_dm():
            try: await member.send(f"お知らせ：「{i.guild.name}」での住人登録が承認されました。")
            except discord.Forbidden: pass
        tasks.append(send_dm())
        async def update_roles_nick():
            try:
                roles_to_add = []
                if (guest_role_id := get_role_id("guest")) and (role := i.guild.get_role(guest_role_id)): roles_to_add.append(role)
                
                gender_field = next((f for f in self.original_embed.fields if f.name == "性別"), None)
                if gender_field:
                    for rule in self.auto_role_mappings:
                        if any(k.lower() in gender_field.value.lower() for k in rule["keywords"]):
                            if (gender_role_id := get_id(rule["role_id_db_key"])) and (role := i.guild.get_role(gender_role_id)):
                                roles_to_add.append(role); break
                
                age_field = next((f for f in self.original_embed.fields if f.name == "年齢"), None)
                if age_field:
                    year = self._parse_birth_year(age_field.value); key = None
                    if year == 0: key = "info_age_private"
                    elif year:
                        if 1970 <= year <= 1979: key = "info_age_70s"
                        elif 1980 <= year <= 1989: key = "info_age_80s"
                        elif 1990 <= year <= 1999: key = "info_age_90s"
                        elif 2000 <= year <= 2009: key = "info_age_00s"
                    if key and (rid := get_role_id(key)) and (role := i.guild.get_role(rid)): roles_to_add.append(role)
                
                if roles_to_add: await member.add_roles(*list(set(roles_to_add)))
                
                if (temp_role_id := get_role_id("temp_user")) and (role := i.guild.get_role(temp_role_id)) and role in member.roles:
                    await member.remove_roles(role)

                if (nick_cog := self.bot.get_cog("Nicknames")) and (name_field := next((f for f in self.original_embed.fields if f.name == "名前"), None)):
                    await nick_cog.update_nickname(member, base_name_override=name_field.value)
            except Exception as e: logger.error(f"Error updating roles/nick for {member.display_name}: {e}", exc_info=True)
        tasks.append(update_roles_nick())
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _perform_rejection_tasks(self, i: discord.Interaction, member: discord.Member):
        tasks = []; cog = self.bot.get_cog("Onboarding")
        if cog.rejection_log_channel_id and (ch := i.guild.get_channel(cog.rejection_log_channel_id)):
            embed = discord.Embed(title="❌ 住人登録が拒否されました", description=f"**対象者:** {member.mention}", color=discord.Color.red())
            embed.set_thumbnail(url=member.display_avatar.url)
            for f in self.original_embed.fields: embed.add_field(name=f"申請内容「{f.name}」", value=f.value, inline=False)
            embed.add_field(name="拒否理由", value=self.rejection_reason or "理由未入力", inline=False)
            embed.add_field(name="処理者", value=i.user.mention, inline=False)
            tasks.append(ch.send(content=member.mention, embed=embed, allowed_mentions=discord.AllowedMentions(users=True)))
        async def send_dm():
            try: await member.send(f"「{i.guild.name}」での住人登録が拒否されました。\n理由: 「{self.rejection_reason}」\n<#{cog.panel_channel_id}> からやり直してください。")
            except discord.Forbidden: pass
        tasks.append(send_dm())
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_new_welcome_message(self, member: discord.Member, channel: discord.TextChannel, mention_role_id: int):
        mention = f"<@&{mention_role_id}>" if mention_role_id else ""
        content = f"# {member.mention} さんがDico森へ里入りしました！\n## 皆さんで歓迎しましょう！ {mention}"
        desc = ("Dico森は、皆さんの「森での暮らし」をより豊かにするための場所です。\n"
                "**<#1404410186562666546>**で依頼を確認し、里の活動に参加してみましょう。\n"
                "困ったことがあれば、**<#1404410207148445818>**にいる世話役さんに質問してくださいね。")
        embed = discord.Embed(description=desc, color=0xFFFFE0)
        try: await channel.send(content=content, embed=embed, allowed_mentions=discord.AllowedMentions(users=True, roles=True))
        except Exception as e: logger.error(f"Error sending new welcome message: {e}", exc_info=True)

    @ui.button(label='承認', style=discord.ButtonStyle.success, custom_id='approve_button_final')
    async def approve(self, i: discord.Interaction, b: ui.Button): await self._handle_approval(i, approved=True)
    @ui.button(label='拒否', style=discord.ButtonStyle.danger, custom_id='reject_button_final')
    async def reject(self, i: discord.Interaction, b: ui.Button): await self._handle_approval(i, approved=False)

class OnboardingView(ui.View):
    def __init__(self, current_step: int = 0, approval_role_id: int = 0):
        super().__init__(timeout=300); self.current_step = current_step; self.approval_role_id = approval_role_id; self.update_view()
    def update_view(self):
        self.clear_items(); page_data = GUIDE_PAGES[self.current_step]
        if self.current_step > 0:
            prev_button = ui.Button(label="◀ 前へ", style=discord.ButtonStyle.secondary, custom_id="onboarding_prev"); prev_button.callback = self.go_previous; self.add_item(prev_button)
        if page_data["type"] == "info":
            button = ui.Button(label="次へ ▶", style=discord.ButtonStyle.primary, custom_id="onboarding_next"); button.callback = self.go_next; self.add_item(button)
        elif page_data["type"] == "action":
            button = ui.Button(label=page_data.get("button_label", "確認"), style=discord.ButtonStyle.success, custom_id="onboarding_action"); button.callback = self.do_action; self.add_item(button)
        elif page_data["type"] == "intro":
            button = ui.Button(label="住人登録票を作成する", style=discord.ButtonStyle.success, custom_id="onboarding_intro"); button.callback = self.create_introduction; self.add_item(button)
    async def _update_message(self, interaction: discord.Interaction):
        page = GUIDE_PAGES[self.current_step]
        embed = discord.Embed(title=page["title"], description=page["description"], color=discord.Color.purple())
        if GUIDE_GIF_URL: embed.set_image(url=GUIDE_GIF_URL)
        if page.get("rules"): embed.add_field(name="⚠️ ルール", value=page["rules"], inline=False)
        self.update_view(); await interaction.edit_original_response(embed=embed, view=self)
    async def go_previous(self, i: discord.Interaction): await i.response.defer(); self.current_step -= 1; await self._update_message(i)
    async def go_next(self, i: discord.Interaction): await i.response.defer(); self.current_step += 1; await self._update_message(i)
    async def do_action(self, i: discord.Interaction):
        page_data = GUIDE_PAGES[self.current_step]; role_id = get_role_id(page_data.get("role_key"));
        if not role_id or not (role := i.guild.get_role(role_id)): return await i.response.send_message("エラー: 役職が見つかりません。", ephemeral=True)
        try:
            await i.response.defer()
            if role not in i.user.roles: await i.user.add_roles(role)
            self.current_step += 1; await self._update_message(i)
        except discord.Forbidden: await i.followup.send("エラー: 役職を付与する権限がありません。", ephemeral=True)
        except Exception as e: await i.followup.send(f"❌ 予期せぬエラー: {e}", ephemeral=True)
    async def create_introduction(self, interaction: discord.Interaction):
        key = f"intro_{interaction.user.id}"; last_time = await get_cooldown(key)
        if last_time and time.time() - last_time < INTRODUCTION_COOLDOWN_SECONDS:
            remaining = INTRODUCTION_COOLDOWN_SECONDS - (time.time() - last_time)
            return await interaction.response.send_message(f"次の申請まであと {int(remaining/60)}分 お待ちください。", ephemeral=True)
        cog = interaction.client.get_cog("Onboarding")
        await interaction.response.send_modal(IntroductionModal(approval_role_id=cog.approval_role_id if cog else 0))

class OnboardingPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @ui.button(label="里の案内・住人登録を始める", style=discord.ButtonStyle.success, custom_id="start_onboarding_button_final")
    async def start_onboarding(self, interaction: discord.Interaction, button: ui.Button):
        cog = interaction.client.get_cog("Onboarding")
        if not cog: return await interaction.response.send_message("エラー: Onboarding機能が利用できません。", ephemeral=True)
        page = GUIDE_PAGES[0]
        embed = discord.Embed(title=page["title"], description=page["description"], color=discord.Color.purple())
        if GUIDE_GIF_URL: embed.set_image(url=GUIDE_GIF_URL)
        await interaction.response.send_message(embed=embed, view=OnboardingView(approval_role_id=cog.approval_role_id if cog else 0), ephemeral=True)

class Onboarding(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(OnboardingPanelView())
        self.auto_role_mappings: list = []
        self.panel_channel_id: int | None = None; self.approval_channel_id: int | None = None
        self.introduction_channel_id: int | None = None; self.rejection_log_channel_id: int | None = None
        self.new_welcome_channel_id: int | None = None; self.approval_role_id: int | None = None
        self.guest_role_id: int | None = None; self.temp_user_role_id: int | None = None; self.mention_role_id_1: int | None = None
        logger.info("Onboarding Cog initialized.")

    async def cog_load(self):
        await self.load_onboarding_configs()

    async def load_onboarding_configs(self):
        self.auto_role_mappings = get_auto_role_mappings()
        self.panel_channel_id = get_channel_id("onboarding_panel_channel_id")
        self.approval_channel_id = get_channel_id("onboarding_approval_channel_id")
        self.introduction_channel_id = get_channel_id("introduction_channel_id")
        self.rejection_log_channel_id = get_channel_id("introduction_rejection_log_channel_id")
        self.new_welcome_channel_id = get_channel_id("new_welcome_channel_id")
        self.approval_role_id = get_role_id("approval")
        self.guest_role_id = get_role_id("guest")
        self.temp_user_role_id = get_role_id("temp_user")
        self.mention_role_id_1 = get_role_id("mention_role_1")
        logger.info("[Onboarding Cog] Loaded configurations.")
        
    async def regenerate_panel(self, channel: discord.TextChannel | None = None):
        if channel is None:
            if self.panel_channel_id: channel = self.bot.get_channel(self.panel_channel_id)
            else: logger.info("ℹ️ Onboarding panel channel not set, skipping auto-regeneration."); return
        if not channel: logger.warning("❌ Onboarding panel channel could not be found."); return
        
        panel_info = await get_panel_id("onboarding")
        if panel_info and (old_id := panel_info.get('message_id')):
            try:
                message_to_delete = await channel.fetch_message(old_id)
                await message_to_delete.delete()
            except (discord.NotFound, discord.Forbidden): pass
        
        embed = discord.Embed(title="🏡 新米住人の方へ", description="この里へようこそ！\n下のボタンを押して、里での暮らし方を確認し、住人登録を始めましょう。", color=discord.Color.gold())
        msg = await channel.send(embed=embed, view=OnboardingPanelView())
        await save_panel_id("onboarding", msg.id, channel.id)
        logger.info(f"✅ Onboarding panel successfully regenerated in channel {channel.name}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Onboarding(bot))
