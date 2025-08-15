# cogs/server/system.py (DB 자동 로딩 방식 적용 최종본)

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import logging
import asyncio
from typing import Optional

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from utils.database import (
    get_id, save_id_to_db,
    save_panel_id, get_panel_id, get_embed_from_db
)

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
                {"role_id_key": "role_mention_role_1", "label": "サーバー全体通知", "description": "サーバーの重要なお知らせを受け取ります。"},
                {"role_id_key": "role_notify_festival", "label": "祭り", "description": "お祭りやイベント関連の通知を受け取ります。"},
                {"role_id_key": "role_notify_voice", "label": "通話", "description": "通話募集の通知を受け取ります。"},
                {"role_id_key": "role_notify_friends", "label": "友達", "description": "友達募集の通知を受け取ります。"},
                {"role_id_key": "role_notify_disboard", "label": "ディスボード", "description": "Disboard通知を受け取ります。"},
                {"role_id_key": "role_notify_up", "label": "アップ", "description": "Up通知を受け取ります。"},
            ],
            "games": [
                {"role_id_key": "role_game_minecraft", "label": "マインクラフト", "description": "マインクラフト関連の募集に参加します。"},
                {"role_id_key": "role_game_valorant", "label": "ヴァロラント", "description": "ヴァロラント関連の募集に参加します。"},
                {"role_id_key": "role_game_overwatch", "label": "オーバーウォッチ", "description": "オーバーウォッチ関連の募集に参加します。"},
                {"role_id_key": "role_game_lol", "label": "リーグ・オブ・レジェンド", "description": "LoL関連の募集に参加します。"},
                {"role_id_key": "role_game_mahjong", "label": "麻雀", "description": "麻雀関連の募集に参加します。"},
                {"role_id_key": "role_game_amongus", "label": "アモングアス", "description": "Among Us関連の募集に参加します。"},
                {"role_id_key": "role_game_mh", "label": "モンスターハンター", "description": "モンハン関連の募集に参加します。"},
                {"role_id_key": "role_game_genshin", "label": "原神", "description": "原神関連の募集に参加します。"},
                {"role_id_key": "role_game_apex", "label": "エーペックスレジェンズ", "description": "Apex Legends関連の募集に参加します。"},
                {"role_id_key": "role_game_splatoon", "label": "スプラトゥーン", "description": "スプラトゥーン関連の募集に参加します。"},
                {"role_id_key": "role_game_gf", "label": "ゴッドフィールド", "description": "ゴッドフィールド関連の募集に参加します。"},
                {"role_id_key": "role_platform_steam", "label": "スチーム", "description": "Steamでプレイするゲームの募集に参加します。"},
                {"role_id_key": "role_platform_smartphone", "label": "スマートフォン", "description": "スマホゲームの募集に参加します。"},
                {"role_id_key": "role_platform_switch", "label": "スイッチ", "description": "Nintendo Switchゲームの募集に参加します。"},
            ]
        }
    }
}

class EphemeralRoleSelectView(ui.View):
    def __init__(self, member: discord.Member, category_roles: list, all_category_role_ids: set[int]):
        super().__init__(timeout=180)
        self.member = member; self.all_category_role_ids = all_category_role_ids
        current_user_role_ids = {r.id for r in self.member.roles}
        options = [discord.SelectOption(label=info['label'], value=str(rid), description=info.get('description'), default=(rid in current_user_role_ids)) for info in category_roles if (rid := get_id(info['role_id_key']))]
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
        all_ids = {get_id(r['role_id_key']) for r in category_roles if get_id(r['role_id_key'])}
        embed = discord.Embed(title=f"「{category_id.capitalize()}」役割選択", description="下のドロップダウンメニューで希望する役割をすべて選択してください。", color=discord.Color.blue())
        await i.followup.send(embed=embed, view=EphemeralRoleSelectView(i.user, category_roles, all_ids), ephemeral=True)

class ServerSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.welcome_channel_id: Optional[int] = None
        self.farewell_channel_id: Optional[int] = None
        self.temp_user_role_id: Optional[int] = None
        logger.info("ServerSystem Cog initialized.")

    async def cog_load(self):
        await self.load_all_configs()

    async def load_all_configs(self):
        self.welcome_channel_id = get_id("welcome_channel_id")
        self.farewell_channel_id = get_id("farewell_channel_id")
        self.temp_user_role_id = get_id("role_temp_user")
        logger.info("[ServerSystem Cog] Loaded configurations.")
    
    async def regenerate_panel(self, channel: discord.TextChannel | None = None):
        for panel_key, panel_config in STATIC_AUTO_ROLE_PANELS.items():
            try:
                target_channel = channel
                if target_channel is None:
                    channel_id = get_id(panel_config['channel_key'])
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

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if self.farewell_channel_id and (ch := self.bot.get_channel(self.farewell_channel_id)):
            if embed_data := await get_embed_from_db('farewell_embed'):
                embed_data['description'] = embed_data.get('description', '').format(member_name=member.display_name)
                embed = discord.Embed.from_dict(embed_data)
                if member.display_avatar: embed.set_thumbnail(url=member.display_avatar.url)
                try: await ch.send(embed=embed)
                except Exception as e: logger.error(f"お別れメッセージの送信に失敗しました: {e}")

    @app_commands.command(name="setup", description="[管理者] ボットの各種チャンネルを設定またはパネルを設置します。")
    @app_commands.describe(setting_type="設定したい項目を選択してください。", channel="設定対象のチャンネルを指定してください。")
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
                
                await save_id_to_db(config["key"], channel.id)
                await cog_to_run.regenerate_panel(channel)
                await interaction.followup.send(f"✅ `{channel.mention}` に **{config['friendly_name']}** を設置しました。", ephemeral=True)
            
            elif config["type"] == "channel":
                db_key = config["key"]
                cog_name = config["cog_name"]
                attribute_to_set = config.get("attr", db_key)
                
                await save_id_to_db(db_key, channel.id)
                
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

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))
