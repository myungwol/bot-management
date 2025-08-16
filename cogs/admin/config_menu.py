# cogs/admin/config_menu.py (치명적 오류 수정 완료)

import discord
from discord.ext import commands
from discord import app_commands, ui
import logging
from typing import List, Dict, Any

from utils.database import (
    get_embed_from_db, save_embed_to_db,
    get_panel_components_from_db, save_panel_component_to_db
)

logger = logging.getLogger(__name__)

# 설정 가능한 패널과 임베드의 키 목록
PANEL_KEYS = ["onboarding", "nicknames", "commerce", "fishing", "profile"]
EMBED_KEYS = [
    "welcome_embed", "farewell_embed", 
    "panel_onboarding", "panel_roles", "panel_nicknames", 
    "panel_commerce", "panel_fishing", "panel_profile",
    "onboarding_step_0", "onboarding_step_1", "onboarding_step_2",
    "onboarding_step_3", "onboarding_step_4", "onboarding_step_5"
]
# [수정] 아래 맵은 다른 파일에서 임포트하므로 여기서는 제거합니다.
# BUTTON_STYLES_MAP = { ... }

# 기본 임베드 데이터
DEFAULT_EMBED_DATA = { "title": "（タイトル未設定）", "description": "（説明未設定）", "color": 0x5865F2, "footer": {"text": ""}}


# 임베드 수정을 위한 팝업(Modal) 클래스
class EmbedEditModal(ui.Modal, title="埋め込みメッセージ編集"):
    modal_title = ui.TextInput(label="タイトル", style=discord.TextStyle.short, required=True, max_length=256)
    modal_description = ui.TextInput(label="説明", style=discord.TextStyle.paragraph, required=True, max_length=4000)
    modal_color = ui.TextInput(label="色コード (例: #5865F2)", style=discord.TextStyle.short, required=False, max_length=7)
    modal_footer = ui.TextInput(label="フッターテキスト", style=discord.TextStyle.short, required=False, max_length=2048)

    def __init__(self, embed_key: str, current_data: dict):
        super().__init__()
        self.embed_key = embed_key
        self.modal_title.default = current_data.get("title", "")
        self.modal_description.default = current_data.get("description", "")
        self.modal_color.default = f"#{current_data.get('color', 0):06x}".upper() if current_data.get('color') else ""
        self.modal_footer.default = current_data.get("footer", {}).get("text", "")

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        color = self.modal_color.value
        try:
            color_value = int(color.lstrip('#'), 16) if color else 0x5865F2
        except ValueError:
            await interaction.followup.send("❌ 無効な色コードです。`#RRGGBB`の形式で入力してください。", ephemeral=True)
            return

        embed_data = {
            "title": self.modal_title.value,
            "description": self.modal_description.value,
            "color": color_value,
            "footer": {"text": self.modal_footer.value}
        }

        try:
            await save_embed_to_db(self.embed_key, embed_data)
            preview_embed = discord.Embed.from_dict(embed_data)
            await interaction.followup.send(f"✅ **`{self.embed_key}`** の埋め込みを正常に保存しました。\nプレビュー:", embed=preview_embed, ephemeral=True)
        except Exception as e:
            logger.error(f"임베드 저장 중 오류: {e}", exc_info=True)
            await interaction.followup.send(f"❌ データベースへの保存中にエラーが発生しました。", ephemeral=True)


# 버튼 수정을 위한 팝업(Modal) 클래스
class ButtonEditModal(ui.Modal, title="ボタン編集"):
    label = ui.TextInput(label="ボタンのテキスト", style=discord.TextStyle.short, required=True, max_length=80)
    emoji = ui.TextInput(label="絵文字", style=discord.TextStyle.short, required=False, max_length=50)
    row = ui.TextInput(label="行 (0-4, 空白で自動)", style=discord.TextStyle.short, required=False, max_length=1)

    def __init__(self, component_data: dict):
        super().__init__()
        self.component_data = component_data
        self.label.default = component_data.get('label')
        self.emoji.default = component_data.get('emoji')
        self.row.default = str(component_data.get('row', '')) if component_data.get('row') is not None else ''


    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        row_val_str = self.row.value
        
        # 행(row) 값 유효성 검사
        if row_val_str:
            try:
                row_val = int(row_val_str)
                if not (0 <= row_val <= 4):
                    await interaction.followup.send("❌ 行は0から4までの数字でなければなりません。", ephemeral=True)
                    return
            except ValueError:
                await interaction.followup.send("❌ 行には数字を入力してください。", ephemeral=True)
                return
        else:
            # 사용자가 값을 비워두면 기존 값을 유지하거나 기본값(0)을 사용
            row_val = self.component_data.get('row', 0)
            
        self.component_data['label'] = self.label.value
        self.component_data['emoji'] = self.emoji.value or None
        self.component_data['row'] = row_val

        try:
            await save_panel_component_to_db(self.component_data)
            await interaction.followup.send(f"✅ **`{self.component_data['component_key']}`** ボタンを保存しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"버튼 저장 중 오류: {e}", exc_info=True)
            await interaction.followup.send(f"❌ データベースへの保存中にエラーが発生しました。", ephemeral=True)


# 설정 메뉴의 드롭다운 선택지를 처리하는 클래스
class ConfigSelect(ui.Select):
    def __init__(self, options: List[discord.SelectOption]):
        super().__init__(placeholder="設定する項目を選択してください...", options=options, custom_id="config_main_select")

    async def callback(self, interaction: discord.Interaction):
        # 원본은 thinking=True 때문에 modal이 즉시 표시되지 않으므로 defer()만 호출
        await interaction.response.defer(ephemeral=True)

        selected_value = self.values[0]
        parts = selected_value.split(':')
        
        # 임베드 수정 선택 시
        if parts[0] == "embed":
            embed_key = parts[1]
            current_data = await get_embed_from_db(embed_key) or DEFAULT_EMBED_DATA
            modal = EmbedEditModal(embed_key, current_data)
            await interaction.followup.send_modal(modal) # defer 후에는 followup.send_modal 사용

        # 버튼 수정 선택 시
        elif parts[0] == "button":
            panel_key = parts[1]
            component_key = parts[2]
            
            components = await get_panel_components_from_db(panel_key)
            target_comp = next((c for c in components if c['component_key'] == component_key), None)

            if not target_comp:
                await interaction.followup.send("❌ 該当のボタンが見つかりません。ボットを再起動するとリストが更新される場合があります。", ephemeral=True)
                return
            
            modal = ButtonEditModal(target_comp)
            await interaction.followup.send_modal(modal) # defer 후에는 followup.send_modal 사용


# 설정 메뉴의 전체 View 클래스
class ConfigMenuView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    # [수정] View가 생성된 후, 비동기적으로 DB에서 데이터를 가져와 Select 메뉴를 만드는 메서드
    async def initialize(self):
        # 1. 임베드 옵션 생성
        embed_options = [discord.SelectOption(label=f"埋め込み: {key}", value=f"embed:{key}") for key in EMBED_KEYS]
        
        # 2. 버튼 옵션 비동기적으로 생성
        button_options = []
        for panel_key in PANEL_KEYS:
            components = await get_panel_components_from_db(panel_key)
            if components:
                for comp in components:
                    # component_key가 있는 버튼만 메뉴에 추가
                    if comp.get('component_type') == 'button' and comp.get('component_key'):
                        button_options.append(
                            discord.SelectOption(label=f"ボタン: {panel_key} > {comp.get('label', comp.get('component_key'))}", value=f"button:{panel_key}:{comp['component_key']}")
                        )

        # 3. 옵션들을 합치고 Select 메뉴를 View에 추가
        # 옵션이 25개를 초과할 경우를 대비하여 분리할 수 있지만, 지금은 합쳐서 하나로 만듭니다.
        all_options = (embed_options + button_options)[:25] # 디스코드 Select Option은 최대 25개
        
        if all_options:
            self.add_item(ConfigSelect(options=all_options))
        else:
            # 설정할 항목이 하나도 없을 경우의 처리
            # 이 경우는 거의 없지만, 안정성을 위해 추가
            pass


# 실제 Cog 클래스
class ConfigMenu(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # 클래스 이름을 파일 이름과 맞추기 위해 PanelManager에서 ConfigMenu로 변경
        logger.info("ConfigMenu Cog가 성공적으로 초기화되었습니다.")

    @app_commands.command(name="config", description="[管理者] ボットの埋め込みやボタンなどのUIを管理します。")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def open_config_menu(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        try:
            # 1. View 인스턴스 생성
            view = ConfigMenuView()
            # 2. 비동기적으로 Select 메뉴 초기화
            await view.initialize()
            
            await interaction.followup.send("⚙️ 봇 UI 설정 메뉴", view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"❌ 설정 메뉴(/config) 실행 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send("❌ 메뉴를 불러오는 중 오류가 발생했습니다. 로그를 확인해주세요.", ephemeral=True)


async def setup(bot: commands.Bot):
    # Cog 클래스 이름 변경에 맞춰 수정
    await bot.add_cog(ConfigMenu(bot))
