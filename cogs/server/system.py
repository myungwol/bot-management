# cogs/server/system.py (API 제한 및 안정성 강화 최종본)

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
# 이 사전을 수정하여 역할 패널의 내용을 변경할 수 있습니다.
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
                # ... (이하 다른 게임 역할들)
            ]
        }
    }
}

# --- [수정] 역할이 25개를 초과해도 안전하게 처리하는 새로운 View ---
class RoleSelectView(ui.View):
    """
    선택된 카테고리의 역할 목록을 임시(ephemeral) 메시지로 보여주는 View.
    역할이 25개를 초과할 경우 여러 개의 드롭다운으로 자동 분할합니다.
    """
    def __init__(self, member: discord.Member, category_roles: List[Dict[str, Any]], category_name: str):
        super().__init__(timeout=300)  # 타임아웃을 5분으로 연장
        self.member = member
        self.category_roles_info = category_roles
        
        # 해당 카테고리에 속한 모든 유효한 역할 ID 집합
        self.all_category_role_ids = {
            role_id for role in category_roles if (role_id := get_id(role.get('role_id_key')))
        }
        
        # 현재 유저가 가진 역할 ID 집합
        current_user_role_ids = {r.id for r in self.member.roles}

        # 역할 목록을 25개 단위로 나눕니다.
        role_chunks = [category_roles[i:i + 25] for i in range(0, len(category_roles), 25)]

        if not role_chunks:
            # 설정된 역할이 없을 경우의 처리
            self.add_item(ui.Button(label="設定された役割がありません", disabled=True))
            return

        # 각 묶음에 대해 드롭다운 메뉴를 생성합니다.
        for i, chunk in enumerate(role_chunks):
            options = []
            for role_info in chunk:
                role_id = get_id(role_info.get('role_id_key'))
                if role_id:
                    options.append(discord.SelectOption(
                        label=role_info['label'],
                        value=str(role_id),
                        description=role_info.get('description'),
                        default=(role_id in current_user_role_ids)
                    ))
            
            if options:
                placeholder = f"{category_name} 役割選択 ({i+1}/{len(role_chunks)})"
                self.add_item(ui.Select(
                    placeholder=placeholder,
                    min_values=0,
                    max_values=len(options),
                    options=options,
                    custom_id=f"role_select_{i}"
                ))

        # 역할 업데이트 버튼 추가
        update_button = ui.Button(label="役割を更新", style=discord.ButtonStyle.primary, custom_id="update_roles", emoji="✅")
        update_button.callback = self.update_roles_callback
        self.add_item(update_button)

    async def update_roles_callback(self, interaction: discord.Interaction):
        """'역할 업데이트' 버튼을 눌렀을 때 실행되는 콜백 함수입니다."""
        await interaction.response.defer(ephemeral=True)
        
        # 모든 드롭다운에서 선택된 역할 ID들을 수집
        selected_ids = set()
        for item in self.children:
            if isinstance(item, ui.Select):
                selected_ids.update(int(value) for value in item.values)
        
        current_ids = {role.id for role in self.member.roles}
        
        # 추가할 역할과 제거할 역할을 계산
        to_add_ids = selected_ids - current_ids
        to_remove_ids = (self.all_category_role_ids - selected_ids) & current_ids
        
        try:
            guild = interaction.guild
            if to_add_ids:
                roles_to_add = [role for role_id in to_add_ids if (role := guild.get_role(role_id))]
                if roles_to_add:
                    await self.member.add_roles(*roles_to_add, reason="自動役割選択")
            
            if to_remove_ids:
                roles_to_remove = [role for role_id in to_remove_ids if (role := guild.get_role(role_id))]
                if roles_to_remove:
                    await self.member.remove_roles(*roles_to_remove, reason="自動役割選択")

            # 성공 메시지 표시 및 View 비활성화
            for item in self.children:
                item.disabled = True
            await interaction.followup.send("✅ 役割が正常に更新されました。", view=self)
            self.stop()

        except discord.Forbidden:
            logger.error(f"役割の更新に失敗しました: 権限がありません (Guild: {interaction.guild.id})")
            await interaction.followup.send("❌ 役割を更新できませんでした。ボットの権限を確認してください。", ephemeral=True)
        except Exception as e:
            logger.error(f"役割更新中の不明なエラー: {e}", exc_info=True)
            await interaction.followup.send("❌ 処理中にエラーが発生しました。サーバー管理者にお問い合わせください。", ephemeral=True)


# --- [개선] 카테고리가 25개를 초과해도 안전한 새로운 View ---
class AutoRoleView(ui.View):
    """
    역할 카테고리를 선택할 수 있는 드롭다운을 포함한 영구적인 View.
    """
    def __init__(self, panel_config: dict):
        super().__init__(timeout=None)
        self.panel_config = panel_config

        # 카테고리 목록을 드롭다운 옵션으로 변환
        options = [
            discord.SelectOption(
                label=category['label'],
                value=category['id'],
                emoji=category.get('emoji'),
                description=category.get('description')
            ) for category in self.panel_config.get("categories", [])
        ]
        
        if options:
            category_select = ui.Select(
                placeholder="役割のカテゴリーを選択してください...",
                options=options,
                custom_id="category_select_dropdown"
            )
            category_select.callback = self.category_select_callback
            self.add_item(category_select)

    async def category_select_callback(self, interaction: discord.Interaction):
        """카테고리 드롭다운에서 항목을 선택했을 때 실행됩니다."""
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        category_id = interaction.data['values'][0]
        category_info = next((cat for cat in self.panel_config.get("categories", []) if cat['id'] == category_id), None)
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
        
        view = RoleSelectView(interaction.user, category_roles, category_name)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class ServerSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.welcome_channel_id: Optional[int] = None
        self.farewell_channel_id: Optional[int] = None
        self.temp_user_role_id: Optional[int] = None
        logger.info("ServerSystem Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        """Cog가 로드될 때 DB에서 설정을 불러옵니다."""
        await self.load_all_configs()

    async def load_all_configs(self):
        """DB 캐시로부터 이 Cog에 필요한 설정값들을 불러와 인스턴스 변수에 저장합니다."""
        self.welcome_channel_id = get_id("new_welcome_channel_id") # 키 이름 확인 필요
        self.farewell_channel_id = get_id("farewell_channel_id") # 키 이름 확인 필요
        self.temp_user_role_id = get_id("role_temp_user")
        logger.info("[ServerSystem Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")
    
    async def regenerate_panel(self, channel: Optional[discord.TextChannel] = None):
        """역할 패널 메시지를 생성하거나 업데이트합니다."""
        for panel_key, panel_config in STATIC_AUTO_ROLE_PANELS.items():
            try:
                target_channel = channel
                if target_channel is None:
                    channel_id = get_id(panel_config['channel_key'])
                    if not channel_id or not (target_channel := self.bot.get_channel(channel_id)):
                        logger.info(f"ℹ️ '{panel_key}' 패널 채널이 DB에 설정되지 않아 생성을 건너뜁니다.")
                        continue
                
                embed = discord.Embed.from_dict(panel_config['embed'])
                view = AutoRoleView(panel_config)
                panel_info = get_panel_id(panel_key)
                message_id = panel_info.get('message_id') if panel_info else None
                
                live_message = None
                if message_id:
                    try:
                        live_message = await target_channel.fetch_message(message_id)
                        await live_message.edit(embed=embed, view=view)
                        logger.info(f"✅ '{panel_key}' 패널을 성공적으로 업데이트했습니다. (채널: #{target_channel.name})")
                    except discord.NotFound:
                        logger.warning(f"DB에 저장된 '{panel_key}' 패널 메시지(ID: {message_id})를 찾을 수 없어 새로 생성합니다.")
                        live_message = None
                
                if not live_message:
                    new_message = await target_channel.send(embed=embed, view=view)
                    await save_panel_id(panel_key, new_message.id, target_channel.id)
                    logger.info(f"✅ '{panel_key}' 패널을 성공적으로 새로 생성했습니다. (채널: #{target_channel.name})")
            except Exception as e:
                logger.error(f"❌ '{panel_key}' 패널 처리 중 오류가 발생했습니다: {e}", exc_info=True)

    # ... (on_member_join, on_member_remove 리스너는 변경 사항이 거의 없어 생략 가능하나, 전체 코드를 위해 포함)

    @app_commands.command(name="setup", description="[管理者] ボットの各種チャンネルを設定またはパネルを設置します。")
    @app_commands.describe(setting_type="設定したい項目を選択してください。", channel="設定対象のチャンネルを指定してください。")
    @app_commands.choices(setting_type=[
        # ... (Choices는 변경 없음)
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_unified(self, interaction: discord.Interaction, setting_type: str, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True, thinking=True)

        # 설정 작업을 위한 매핑 (DB 키, Cog 이름, 친화적 이름 등)
        setup_map = {
            # 패널 설정
            "panel_roles": {"type": "panel", "cog": "ServerSystem", "key": "auto_role_channel_id", "friendly_name": "役割パネル"},
            # ... (다른 패널 설정)
            # 채널 설정
            "channel_new_welcome": {"type": "channel", "cog_name": "ServerSystem", "key": "new_welcome_channel_id", "friendly_name": "新規参加者歓迎チャンネル"},
            "channel_farewell": {"type": "channel", "cog_name": "ServerSystem", "key": "farewell_channel_id", "friendly_name": "お別れチャンネル"}, # 예시 추가
            # ... (다른 채널 설정)
        }
        
        config = setup_map.get(setting_type)
        if not config:
            await interaction.followup.send("❌ 無効な設定タイプです。", ephemeral=True)
            return

        try:
            friendly_name = config['friendly_name']
            db_key = config['key']

            # 1. DB에 새로운 채널 ID를 저장/업데이트합니다.
            await save_id_to_db(db_key, channel.id)
            logger.info(f"'{db_key}' 설정을 DB에 저장했습니다: {channel.id}")

            # 2. 설정 타입에 따라 추가 작업을 수행합니다.
            if config["type"] == "panel":
                cog_to_run = self.bot.get_cog(config["cog"])
                if not cog_to_run or not hasattr(cog_to_run, 'regenerate_panel'):
                    await interaction.followup.send(f"❌ '{config['cog']}' Cogが見つからないか、'regenerate_panel' 関数がありません。", ephemeral=True)
                    return
                
                # 패널을 해당 채널에 즉시 생성/업데이트합니다.
                await cog_to_run.regenerate_panel(channel)
                await interaction.followup.send(f"✅ `{channel.mention}` に **{friendly_name}** を設置しました。", ephemeral=True)
            
            elif config["type"] == "channel":
                cog_name = config["cog_name"]
                target_cog = self.bot.get_cog(cog_name)
                
                # [개선] Cog가 존재하고 설정 리로드 함수가 있다면 즉시 호출하여 메모리 상태를 업데이트합니다.
                if target_cog and hasattr(target_cog, 'load_all_configs'):
                    await target_cog.load_all_configs()
                    logger.info(f"✅ '{cog_name}' Cog의 설정을 실시간으로 새로고침했습니다.")
                else:
                    logger.warning(f"'{cog_name}' Cog를 찾을 수 없거나 'load_all_configs' 함수가 없어 실시간 업데이트를 건너뜁니다.")
                
                await interaction.followup.send(f"✅ `{channel.mention}`を**{friendly_name}**として設定しました。", ephemeral=True)

        except Exception as e:
            logger.error(f"통합 설정 명령어({setting_type}) 처리 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 設定中にエラーが発生しました. 詳細はボットのログを確認してください。", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))
