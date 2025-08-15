# cogs/server/system.py (수정됨)

import discord
from discord.ext import commands
from discord import app_commands, ui
import logging
from typing import Optional, List, Dict, Any

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] %(message)s')
logger = logging.getLogger(__name__)

# 유틸리티 함수 임포트
from utils.database import (
    get_id, save_id_to_db,
    save_panel_id, get_panel_id, get_embed_from_db
)

# --- 역할 패널 설정 데이터 ---
STATIC_AUTO_ROLE_PANELS = {
    "main_roles": {
        "channel_key": "auto_role_channel_id",
        "embed": {"title": "📜 役割選択", "description": "下のメニューから希望する役割のカテゴリーを選択してください！", "color": 0x5865F2},
        "categories": [
            {"id": "notifications", "label": "通知役割", "emoji": "📢", "description": "サーバーの各種通知に関する役割を選択します。"},
            {"id": "games", "label": "ゲーム役割", "emoji": "🎮", "description": "プレイするゲームに関する役割を選択します。"},
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

class RoleSelectView(ui.View):
    def __init__(self, member: discord.Member, category_roles: List[Dict[str, Any]], category_name: str):
        super().__init__(timeout=300)
        self.member = member
        self.all_category_role_ids = {rid for role in category_roles if (rid := get_id(role.get('role_id_key')))}
        current_user_role_ids = {r.id for r in self.member.roles}
        role_chunks = [category_roles[i:i + 25] for i in range(0, len(category_roles), 25)]
        if not role_chunks: 
            self.add_item(ui.Button(label="設定された役割がありません", disabled=True))
            return
        for i, chunk in enumerate(role_chunks):
            options = [discord.SelectOption(label=info['label'], value=str(rid), description=info.get('description'), default=(rid in current_user_role_ids)) for info in chunk if (rid := get_id(info.get('role_id_key')))]
            if options: 
                self.add_item(ui.Select(placeholder=f"{category_name} 役割選択 ({i+1}/{len(role_chunks)})", min_values=0, max_values=len(options), options=options, custom_id=f"role_select_{i}"))
        update_button = ui.Button(label="役割を更新", style=discord.ButtonStyle.primary, custom_id="update_roles", emoji="✅")
        update_button.callback = self.update_roles_callback
        self.add_item(update_button)

    async def update_roles_callback(self, interaction: discord.Interaction):
        # [수정] 상호작용 실패 오류를 막기 위해 defer()를 추가합니다.
        await interaction.response.defer(ephemeral=True)
        
        selected_ids = {int(value) for item in self.children if isinstance(item, ui.Select) for value in item.values}
        current_ids = {role.id for role in self.member.roles}
        
        to_add_ids = selected_ids - current_ids
        to_remove_ids = (self.all_category_role_ids - selected_ids) & current_ids
        
        try:
            guild = interaction.guild
            if to_add_ids:
                roles_to_add = [r for r_id in to_add_ids if (r := guild.get_role(r_id))]
                if roles_to_add:
                    await self.member.add_roles(*roles_to_add, reason="自動役割選択")
            
            if to_remove_ids:
                roles_to_remove = [r for r_id in to_remove_ids if (r := guild.get_role(r_id))]
                if roles_to_remove:
                    await self.member.remove_roles(*roles_to_remove, reason="自動役割選択")
            
            for item in self.children: 
                item.disabled = True
            
            await interaction.followup.send("✅ 役割が正常に更新されました。", view=self)
            self.stop()
        except Exception as e:
            logger.error(f"역할 업데이트 중 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 処理中にエラーが発生しました。", ephemeral=True)

class AutoRoleView(ui.View):
    def __init__(self, panel_config: dict):
        # timeout=None과 custom_id를 모두 설정해야 영구 View로 제대로 작동합니다.
        super().__init__(timeout=None)
        self.panel_config = panel_config
        options = [discord.SelectOption(label=c['label'], value=c['id'], emoji=c.get('emoji'), description=c.get('description')) for c in self.panel_config.get("categories", [])]
        
        if options:
            # 각 View 컴포넌트에 고유한 custom_id를 부여하는 것이 좋습니다.
            category_select = ui.Select(placeholder="役割のカテゴリーを選択してください...", options=options, custom_id=f"autorole_category_select:{panel_config['channel_key']}")
            category_select.callback = self.category_select_callback
            self.add_item(category_select)

    async def category_select_callback(self, interaction: discord.Interaction):
        # defer의 thinking=True 옵션은 초기 응답이 오래 걸릴 때 유용합니다.
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        category_id = interaction.data['values'][0]
        category_info = next((c for c in self.panel_config.get("categories", []) if c['id'] == category_id), None)
        category_name = category_info['label'] if category_info else category_id.capitalize()
        
        category_roles = self.panel_config.get("roles", {}).get(category_id, [])
        if not category_roles:
            await interaction.followup.send("このカテゴリーには設定された役割がありません。", ephemeral=True)
            return
            
        embed = discord.Embed(title=f"「{category_name}」役割選択", description="下のドロップダウンメニューで希望する役割をすべて選択し、最後に「役割を更新」ボタンを押してください。", color=discord.Color.blue())
        view = RoleSelectView(interaction.user, category_roles, category_name)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

class ServerSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.welcome_channel_id: Optional[int] = None
        self.farewell_channel_id: Optional[int] = None
        self.guest_role_id: Optional[int] = None
        logger.info("ServerSystem Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        # cog_load 시점에서 설정을 불러오도록 변경합니다.
        # on_ready에서 전체 DB 로드 후, 각 cog의 load_all_configs가 다시 호출되어 값을 덮어씁니다.
        await self.load_all_configs()

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
                    except (discord.NotFound, discord.Forbidden): 
                        pass
                
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
            try: 
                await member.add_roles(role, reason="サーバー参加時の初期役割")
            except Exception as e: 
                logger.error(f"'外部の人' 역할 부여에 실패했습니다: {e}")
        
        if self.welcome_channel_id and (ch := self.bot.get_channel(self.welcome_channel_id)):
            if embed_data := await get_embed_from_db('welcome_embed'):
                desc = embed_data.get('description', '').format(member_mention=member.mention, member_name=member.display_name, guild_name=member.guild.name)
                embed = discord.Embed.from_dict({**embed_data, 'description': desc})
                if member.display_avatar: 
                    embed.set_thumbnail(url=member.display_avatar.url)
                try: 
                    await ch.send(f"@everyone, {member.mention}", embed=embed, allowed_mentions=discord.AllowedMentions(everyone=True, users=True))
                except Exception as e: 
                    logger.error(f"환영 메시지 전송에 실패했습니다: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if self.farewell_channel_id and (ch := self.bot.get_channel(self.farewell_channel_id)):
            if embed_data := await get_embed_from_db('farewell_embed'):
                desc = embed_data.get('description', '').format(member_name=member.display_name)
                embed = discord.Embed.from_dict({**embed_data, 'description': desc})
                if member.display_avatar: 
                    embed.set_thumbnail(url=member.display_avatar.url)
                try: 
                    await ch.send(embed=embed)
                except Exception as e: 
                    logger.error(f"작별 메시지 전송에 실패했습니다: {e}")

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
        if not config: 
            await interaction.followup.send("❌ 無効な設定タイプです。", ephemeral=True)
            return
        try:
            db_key, friendly_name = config['key'], config['friendly_name']
            await save_id_to_db(db_key, channel.id)
            logger.info(f"'{db_key}' 설정을 DB에 저장했습니다: {channel.id}")

            if config["type"] == "panel":
                cog_to_run = self.bot.get_cog(config["cog"])
                if not cog_to_run or not hasattr(cog_to_run, 'regenerate_panel'): 
                    await interaction.followup.send(f"❌ '{config['cog']}' Cogが見つからないか、'regenerate_panel' 関数がありません。", ephemeral=True)
                    return
                await cog_to_run.regenerate_panel(channel)
                await interaction.followup.send(f"✅ `{channel.mention}` に **{friendly_name}** を設置しました。", ephemeral=True)
            
            elif config["type"] == "channel":
                target_cog = self.bot.get_cog(config["cog_name"])
                if target_cog and hasattr(target_cog, 'load_all_configs'):
                    # DB에 저장 후, 해당 Cog의 설정을 실시간으로 새로고침합니다.
                    await target_cog.load_all_configs()
                    logger.info(f"✅ '{config['cog_name']}' Cog의 설정을 실시간으로 새로고침했습니다.")
                await interaction.followup.send(f"✅ `{channel.mention}`を**{friendly_name}**として設定しました。", ephemeral=True)

        except Exception as e:
            logger.error(f"통합 설정 명령어({setting_type}) 처리 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 設定中にエラーが発生しました. 詳細はボットのログを確認してください。", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))
