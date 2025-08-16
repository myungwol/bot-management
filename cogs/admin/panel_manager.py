# cogs/admin/config_menu.py (새 파일)

import discord
from discord.ext import commands
from discord import app_commands, ui
import logging
from typing import List, Dict, Any, Literal

from utils.database import (
    get_embed_from_db, save_embed_to_db,
    get_panel_components_from_db, save_panel_component_to_db
)

logger = logging.getLogger(__name__)

PANEL_KEYS = ["onboarding", "roles", "nicknames", "commerce", "fishing", "profile"]
EMBED_KEYS = [
    "welcome_embed", "farewell_embed", 
    "panel_onboarding", "panel_roles", "panel_nicknames", 
    "panel_commerce", "panel_fishing", "panel_profile",
    "onboarding_step_0", "onboarding_step_1", "onboarding_step_2",
    "onboarding_step_3", "onboarding_step_4", "onboarding_step_5"
]
BUTTON_STYLES_MAP = {
    "primary": discord.ButtonStyle.primary, "secondary": discord.ButtonStyle.secondary,
    "success": discord.ButtonStyle.success, "danger": discord.ButtonStyle.danger,
}
DEFAULT_EMBED_DATA = { "title": "（タイトル未設定）", "description": "（説明未設定）", "color": 0x5865F2, "footer": {"text": ""}}

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
        self.modal_color.default = f"#{current_data.get('color', 0):06x}" if current_data.get('color') else ""
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

class ButtonEditModal(ui.Modal, title="ボタン編集"):
    label = ui.TextInput(label="ボタンのテキスト", style=discord.TextStyle.short, required=True, max_length=80)
    emoji = ui.TextInput(label="絵文字", style=discord.TextStyle.short, required=False, max_length=50)
    row = ui.TextInput(label="行 (0-4, 空白で自動)", style=discord.TextStyle.short, required=False, max_length=1)

    def __init__(self, component_data: dict):
        super().__init__()
        self.component_data = component_data
        self.label.default = component_data.get('label')
        self.emoji.default = component_data.get('emoji')
        self.row.default = str(component_data.get('row', ''))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            row_val = int(self.row.value) if self.row.value else self.component_data.get('row', 0)
            if not (0 <= row_val <= 4):
                await interaction.followup.send("❌ 行は0から4までの数字でなければなりません。", ephemeral=True); return
        except ValueError:
            await interaction.followup.send("❌ 行には数字を入力してください。", ephemeral=True)
            return
            
        self.component_data['label'] = self.label.value
        self.component_data['emoji'] = self.emoji.value or None
        self.component_data['row'] = row_val

        try:
            await save_panel_component_to_db(self.component_data)
            await interaction.followup.send(f"✅ **`{self.component_data['component_key']}`** ボタンを保存しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"버튼 저장 중 오류: {e}", exc_info=True)
            await interaction.followup.send(f"❌ データベースへの保存中にエラーが発生しました。", ephemeral=True)

class ConfigMenuView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(PanelSelect())

    @discord.ui.select(placeholder="設定する項目を選択してください...", custom_id="config_menu_select", options=[
        discord.SelectOption(label=f"埋め込み: {key}", value=f"embed:{key}") for key in EMBED_KEYS
    ] + [
        discord.SelectOption(label=f"ボタン: {panel}:{comp['component_key']}", value=f"button:{panel}:{comp['component_key']}")
        for panel in PANEL_KEYS for comp in (asyncio.run(get_panel_components_from_db(panel)) or [])
    ])
    async def select_callback(self, interaction: discord.Interaction, select: ui.Select):
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        selected = select.values[0]
        target_type, target_key, sub_key = selected.split(':') if ":" in selected else (selected.split(':')[0], selected.split(':')[1], None)

        if target_type == "embed":
            current_data = await get_embed_from_db(target_key) or DEFAULT_EMBED_DATA
            modal = EmbedEditModal(target_key, current_data)
            await interaction.response.send_modal(modal)
            
        elif target_type == "button":
            panel_key = target_key # select.values[0].split(':')[1]
            component_key = sub_key # select.values[0].split(':')[2]
            
            components = await get_panel_components_from_db(panel_key)
            if not components or not (target_comp := next((c for c in components if c['component_key'] == component_key), None)):
                await interaction.followup.send("❌ 該当のボタンが見つかりません。", ephemeral=True)
                return
            modal = ButtonEditModal(target_comp)
            await interaction.response.send_modal(modal)

class PanelManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("PanelManager Cog가 성공적으로 초기화되었습니다.")

    @app_commands.command(name="manager", description="[管理者] 봇의 모든 UI 설정을 관리합니다.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def open_config_menu(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        # 모든 설정 요소들을 보여주는 ConfigMenuView를 생성합니다.
        view = ConfigMenuView()
        
        # ConfigMenuView가 제대로 생성되었는지 확인합니다.
        if view is None:
            logger.error("❌ ConfigMenuView 초기화 실패")
            await interaction.followup.send("❌ 오류가 발생했습니다. 봇 개발자에게 문의해주세요.", ephemeral=True)
            return

        # 사용자에게 ConfigMenuView를 전송합니다.
        try:
            await interaction.followup.send("⚙️ 봇 설정メニュー", view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"❌ ConfigMenuView 전송 실패: {e}", exc_info=True)
            await interaction.followup.send("❌ 오류가 발생했습니다。봇 개발자에게 문의해주세요.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(PanelManager(bot))
