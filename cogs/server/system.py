# cogs/server/system.py (버튼 방식 최종본)

import discord
from discord.ext import commands
from discord import app_commands, ui
import logging
from typing import Optional, List, Dict, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] %(message)s')
logger = logging.getLogger(__name__)

from utils.database import get_id, save_panel_id, get_panel_id, get_embed_from_db

STATIC_AUTO_ROLE_PANELS = {
    "main_roles": {
        "channel_key": "auto_role_channel_id",
        "embed": {"title": "📜 役割選択", "description": "下のメニューから希望する役割のカテゴリーを選択してください！", "color": 0x5865F2},
        "categories": [
            {"id": "notifications", "label": "通知役割", "emoji": "📢", "description": "サーバーの各種通知に関する役割を選択します。"},
            {"id": "games", "label": "ゲーム役割", "emoji": "🎮", "description": "プレイするゲームに関する役割を選択します。"},
        ],
        "roles": { "notifications": [ {"role_id_key": "role_mention_role_1", "label": "サーバー全体通知"}, {"role_id_key": "role_notify_voice", "label": "通話"}, {"role_id_key": "role_notify_friends", "label": "友達"}, {"role_id_key": "role_notify_festival", "label": "祭り"}, {"role_id_key": "role_notify_disboard", "label": "ディスボード"}, {"role_id_key": "role_notify_up", "label": "アップ"}], "games": [ {"role_id_key": "role_game_minecraft", "label": "マインクラフト"}, {"role_id_key": "role_game_valorant", "label": "ヴァロラント"}, {"role_id_key": "role_game_overwatch", "label": "オーバーウォッチ"}, {"role_id_key": "role_game_lol", "label": "リーグ・オブ・レジェンド"}, {"role_id_key": "role_game_mahjong", "label": "麻雀"}, {"role_id_key": "role_game_amongus", "label": "アモングアス"}, {"role_id_key": "role_game_mh", "label": "モンスターハンター"}, {"role_id_key": "role_game_genshin", "label": "原神"}, {"role_id_key": "role_game_apex", "label": "エーペックスレジェンズ"}, {"role_id_key": "role_game_splatoon", "label": "スプラトゥーン"}, {"role_id_key": "role_game_gf", "label": "ゴッドフィールド"}, {"role_id_key": "role_platform_steam", "label": "スチーム"}, {"role_id_key": "role_platform_smartphone", "label": "スマートフォン"}, {"role_id_key": "role_platform_switch", "label": "スイッチ"}]}}}

# 버튼 방식 UI를 위한 View 클래스
class RoleSelectView(ui.View):
    def __init__(self, member: discord.Member, category_roles: List[Dict[str, Any]], category_name: str):
        super().__init__(timeout=300) # 5분 후 비활성화
        self.member = member
        self.all_category_role_ids = {rid for role in category_roles if (rid := get_id(role.get('role_id_key')))}
        
        current_user_role_ids = {r.id for r in self.member.roles}
        role_chunks = [category_roles[i:i + 25] for i in range(0, len(category_roles), 25)]

        if not role_chunks or not self.all_category_role_ids:
            self.add_item(ui.Button(label="設定された役割がありません", disabled=True))
            return

        for i, chunk in enumerate(role_chunks):
            options = [discord.SelectOption(label=info['label'], value=str(rid), description=info.get('description'), default=(rid in current_user_role_ids)) for info in chunk if (rid := get_id(info.get('role_id_key')))]
            if options:
                self.add_item(ui.Select(placeholder=f"{category_name} 役割選択 ({i+1}/{len(role_chunks)})", min_values=0, max_values=len(options), options=options, custom_id=f"role_select_dynamic_{i}"))

    @ui.button(label="役割を更新", style=discord.ButtonStyle.primary, custom_id="update_roles_button_final", emoji="✅", row=4)
    async def update_roles_callback(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        selected_ids = {int(value) for item in self.children if isinstance(item, ui.Select) for value in item.values}
        current_ids = {role.id for role in self.member.roles}
        
        to_add_ids = selected_ids - current_ids
        to_remove_ids = (self.all_category_role_ids - selected_ids) & current_ids
        
        try:
            guild = interaction.guild
            if to_add_ids:
                roles_to_add = [r for r_id in to_add_ids if (r := guild.get_role(r_id))]
                if roles_to_add: await self.member.add_roles(*roles_to_add, reason="自動役割選択")
            if to_remove_ids:
                roles_to_remove = [r for r_id in to_remove_ids if (r := guild.get_role(r_id))]
                if roles_to_remove: await self.member.remove_roles(*roles_to_remove, reason="自動役割選択")

            button.disabled = True
            for item in self.children:
                if isinstance(item, ui.Select): item.disabled = True
            
            await interaction.edit_original_response(content="✅ 役割が正常に更新されました。", view=self)
            self.stop()
        except Exception as e:
            logger.error(f"역할 업데이트 콜백 중 오류: {e}", exc_info=True)
            await interaction.edit_original_response(content="❌ 処理中にエラーが発生しました。", view=None)

# 패널에 붙어있는 메인 View 클래스
class AutoRoleView(ui.View):
    def __init__(self, panel_config: dict):
        super().__init__(timeout=None)
        self.panel_config = panel_config
        # 임시 View의 참조를 저장할 변수
        self.active_select_view = None
        
        options = [discord.SelectOption(label=c['label'], value=c['id'], emoji=c.get('emoji'), description=c.get('description')) for c in self.panel_config.get("categories", [])]
        if options:
            select = ui.Select(placeholder="役割のカテゴリーを選択してください...", options=options, custom_id=f"autorole_category_select:{panel_config.get('channel_key', 'default')}")
            select.callback = self.category_select_callback
            self.add_item(select)

    async def category_select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        category_id = interaction.data['values'][0]
        category_info = next((c for c in self.panel_config.get("categories", []) if c['id'] == category_id), None)
        category_name = category_info['label'] if category_info else category_id.capitalize()
        category_roles = self.panel_config.get("roles", {}).get(category_id, [])

        if not category_roles:
            await interaction.followup.send("このカテゴリーには設定された役割がありません。", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"「{category_name}」役割選択",
            description="下のドロップダウンメニューで希望する役割をすべて選択し、最後に「役割を更新」ボタンを押してください。",
            color=discord.Color.blue()
        )
        
        # 생성된 임시 View를 클래스 변수에 저장하여 참조가 사라지는 것을 방지합니다.
        self.active_select_view = RoleSelectView(interaction.user, category_roles, category_name)
        await interaction.followup.send(embed=embed, view=self.active_select_view, ephemeral=True)


class ServerSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.welcome_channel_id: Optional[int] = None
        self.farewell_channel_id: Optional[int] = None
        self.guest_role_id: Optional[int] = None
        logger.info("ServerSystem Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self): await self.load_all_configs()
    async def load_all_configs(self):
        self.welcome_channel_id = get_id("new_welcome_channel_id")
        self.farewell_channel_id = get_id("farewell_channel_id")
        self.guest_role_id = get_id("role_guest")
        logger.info("[ServerSystem Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")
    
    async def regenerate_panel(self, channel: Optional[discord.TextChannel] = None):
        for panel_key, panel_config in STATIC_AUTO_ROLE_PANELS.items():
            try:
                target_channel = channel
                if target_channel is None:
                    channel_id = get_id(panel_config['channel_key'])
                    if not channel_id or not (target_channel := self.bot.get_channel(channel_id)):
                        logger.info(f"ℹ️ '{panel_key}' 패널 채널이 DB에 설정되지 않아 생성을 건너뜁니다.")
                        continue
                panel_info = get_panel_id(panel_key)
                if panel_info and (old_id := panel_info.get('message_id')):
                    try:
                        old_message = await target_channel.fetch_message(old_id)
                        await old_message.delete()
                    except (discord.NotFound, discord.Forbidden): pass
                embed = discord.Embed.from_dict(panel_config['embed'])
                view = AutoRoleView(panel_config)
                new_message = await target_channel.send(embed=embed, view=view)
                await save_panel_id(panel_key, new_message.id, target_channel.id)
                logger.info(f"✅ '{panel_key}' 패널을 성공적으로 새로 생성했습니다. (채널: #{target_channel.name})")
            except Exception as e:
                logger.error(f"❌ '{panel_key}' 패널 처리 중 오류가 발생했습니다: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot: return
        if self.guest_role_id and (role := member.guild.get_role(self.guest_role_id)):
            try: await member.add_roles(role, reason="サーバー参加時の初期役割")
            except Exception as e: logger.error(f"'外部の人' 역할 부여에 실패했습니다: {e}")
        if self.welcome_channel_id and (ch := self.bot.get_channel(self.welcome_channel_id)):
            if embed_data := await get_embed_from_db('welcome_embed'):
                desc = embed_data.get('description', '').format(member_mention=member.mention, member_name=member.display_name, guild_name=member.guild.name)
                embed = discord.Embed.from_dict({**embed_data, 'description': desc})
                if member.display_avatar: embed.set_thumbnail(url=member.display_avatar.url)
                try: await ch.send(f"@everyone, {member.mention}", embed=embed, allowed_mentions=discord.AllowedMentions(everyone=True, users=True))
                except Exception as e: logger.error(f"환영 메시지 전송에 실패했습니다: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if self.farewell_channel_id and (ch := self.bot.get_channel(self.farewell_channel_id)):
            if embed_data := await get_embed_from_db('farewell_embed'):
                desc = embed_data.get('description', '').format(member_name=member.display_name)
                embed = discord.Embed.from_dict({**embed_data, 'description': desc})
                if member.display_avatar: embed.set_thumbnail(url=member.display_avatar.url)
                try: await ch.send(embed=embed)
                except Exception as e: logger.error(f"작별 메시지 전송에 실패했습니다: {e}")

    @app_commands.command(name="setup", description="[管理者] ボットの各種チャンネルを設定またはパネルを設置します。")
    @app_commands.describe(setting_type="設定したい項目を選択してください。", channel="設定対象のチャンネルを指定してください。")
    @app_commands.choices(setting_type=[
        app_commands.Choice(name="[パネル] 役割パネル", value="panel_roles"), app_commands.Choice(name="[パネル] 案内パネル (オンボーディング)", value="panel_onboarding"),
        app_commands.Choice(name="[パネル] 名前変更パネル", value="panel_nicknames"), app_commands.Choice(name="[パネル] 商店街パネル (売買)", value="panel_commerce"),
        app_commands.Choice(name="[パネル] 釣り場パネル", value="panel_fishing"), app_commands.Choice(name="[パネル] 持ち物パネル", value="panel_profile"),
        app_commands.Choice(name="[チャンネル] 自己紹介承認チャンネル", value="channel_onboarding_approval"), app_commands.Choice(name="[チャンネル] 名前変更承認チャンネル", value="channel_nickname_approval"),
        app_commands.Choice(name="[チャンネル] 新規参加者歓迎チャンネル", value="channel_new_welcome"), app_commands.Choice(name="[ログ] 名前変更ログ", value="log_nickname"),
        app_commands.Choice(name="[ログ] 釣りログ", value="log_fishing"), app_commands.Choice(name="[ログ] コインログ", value="log_coin"),
        app_commands.Choice(name="[ログ] 自己紹介承認ログ", value="log_intro_approval"), app_commands.Choice(name="[ログ] 自己紹介拒否ログ", value="log_intro_rejection"),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_unified(self, interaction: discord.Interaction, setting_type: str, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True, thinking=True)
        setup_map = {
            "panel_roles": {"type": "panel", "cog": "ServerSystem", "key": "auto_role_channel_id", "friendly_name": "役割パネル"},
            "panel_onboarding": {"type": "panel", "cog": "Onboarding", "key": "onboarding_panel_channel_id", "friendly_name": "案内パネル"},
            "panel_nicknames": {"type": "panel", "cog": "Nicknames", "key": "nickname_panel_channel_id", "friendly_name": "名前変更パネル"},
            "panel_commerce": {"type": "panel", "cog": "Commerce", "key": "commerce_panel_channel_id", "friendly_name": "商店街パネル"},
            "panel_fishing": {"type": "panel", "cog": "Fishing", "key": "fishing_panel_channel_id", "friendly_name": "釣り場パネル"},
            "panel_profile": {"type": "panel", "cog": "UserProfile", "key": "inventory_panel_channel_id", "friendly_name": "持ち物パネル"},
            "channel_onboarding_approval": {"type": "channel", "cog_name": "Onboarding", "key": "onboarding_approval_channel_id", "friendly_name": "自己紹介承認チャンネル"},
            "channel_nickname_approval": {"type": "channel", "cog_name": "Nicknames", "key": "nickname_approval_channel_id", "friendly_name": "名前変更承認チャンネル"},
            "channel_new_welcome": {"type": "channel", "cog_name": "ServerSystem", "key": "new_welcome_channel_id", "friendly_name": "新規参加者歓迎チャンネル"},
            "log_nickname": {"type": "channel", "cog_name": "Nicknames", "key": "nickname_log_channel_id", "friendly_name": "名前変更ログ"},
            "log_fishing": {"type": "channel", "cog_name": "Fishing", "key": "fishing_log_channel_id", "friendly_name": "釣りログ"},
            "log_coin": {"type": "channel", "cog_name": "EconomyCore", "key": "coin_log_channel_id", "friendly_name": "コインログ"},
            "log_intro_approval": {"type": "channel", "cog_name": "Onboarding", "key": "introduction_channel_id", "friendly_name": "自己紹介承認ログ"},
            "log_intro_rejection": {"type": "channel", "cog_name": "Onboarding", "key": "introduction_rejection_log_channel_id", "friendly_name": "自己紹介拒否ログ"},
        }
        config = setup_map.get(setting_type)
        if not config: await interaction.followup.send("❌ 無効な設定タイプです。", ephemeral=True); return
        try:
            db_key, friendly_name = config['key'], config['friendly_name']
            await save_id_to_db(db_key, channel.id)
            logger.info(f"'{db_key}' 설정을 DB에 저장했습니다: {channel.id}")
            if config["type"] == "panel":
                cog_to_run = self.bot.get_cog(config["cog"])
                if not cog_to_run or not hasattr(cog_to_run, 'regenerate_panel'): await interaction.followup.send(f"❌ '{config['cog']}' Cogが見つからないか、'regenerate_panel' 関数がありません。", ephemeral=True); return
                await cog_to_run.regenerate_panel(channel)
                await interaction.followup.send(f"✅ `{channel.mention}` に **{friendly_name}** を設置しました。", ephemeral=True)
            elif config["type"] == "channel":
                target_cog = self.bot.get_cog(config["cog_name"])
                if target_cog and hasattr(target_cog, 'load_all_configs'):
                    await target_cog.load_all_configs()
                    logger.info(f"✅ '{config['cog_name']}' Cog의 설정을 실시간으로 새로고침했습니다.")
                await interaction.followup.send(f"✅ `{channel.mention}`を**{friendly_name}**として設定しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"통합 설정 명령어({setting_type}) 처리 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 設定中にエラーが発生しました. 詳細はボットのログを確認してください。", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))
