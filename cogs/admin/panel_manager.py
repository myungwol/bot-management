# cogs/admin/panel_manager.py (통합 수정)

import discord
from discord.ext import commands
from discord import app_commands, ui
import logging
from typing import List, Literal, Optional

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
        try:
            color_value = int(self.modal_color.value.lstrip('#'), 16) if self.modal_color.value else DEFAULT_EMBED_DATA["color"]
        except ValueError:
            await interaction.followup.send("❌ 無効な色コードです。`#RRGGBB`の形式で入力してください。", ephemeral=True); return
        embed_data = {
            "title": self.modal_title.value, "description": self.modal_description.value,
            "color": color_value, "footer": {"text": self.modal_footer.value}
        }
        try:
            await save_embed_to_db(self.embed_key, embed_data)
            await interaction.followup.send(f"✅ **`{self.embed_key}`** の埋め込みを保存しました。", embed=discord.Embed.from_dict(embed_data), ephemeral=True)
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
            await interaction.followup.send("❌ 行には数字を入力してください。", ephemeral=True); return
        self.component_data['label'] = self.label.value
        self.component_data['emoji'] = self.emoji.value or None
        self.component_data['row'] = row_val
        try:
            await save_panel_component_to_db(self.component_data)
            await interaction.followup.send(f"✅ **`{self.component_data['component_key']}`** ボタンを保存しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"버튼 저장 중 오류: {e}", exc_info=True)
            await interaction.followup.send(f"❌ データベースへの保存中にエラーが発生しました。", ephemeral=True)

class PanelManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("PanelManager Cog가 성공적으로 초기화되었습니다.")

    panel_group = app_commands.Group(name="panel", description="パネルと埋め込みメッセージを管理します。")

    async def panel_key_autocomplete(self, i: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        return [app_commands.Choice(name=k, value=k) for k in PANEL_KEYS if current.lower() in k.lower()]
    async def embed_key_autocomplete(self, i: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        return [app_commands.Choice(name=k, value=k) for k in EMBED_KEYS if current.lower() in k.lower()]

    @panel_group.command(name="edit", description="[管理者] パネルの埋め込みやボタンを編集します。")
    @app_commands.describe(
        edit_target="編集したい対象 (埋め込み or ボタン)",
        panel_key="対象のパネル (ボタン編集時のみ)",
        target_key="編集したい埋め込み/ボタンのキー"
    )
    @app_commands.choices(edit_target=[
        app_commands.Choice(name="埋め込み (Embed)", value="embed"),
        app_commands.Choice(name="ボタン (Button)", value="button"),
    ])
    @app_commands.autocomplete(panel_key=panel_key_autocomplete)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_panel(self, interaction: discord.Interaction, edit_target: str, target_key: str, panel_key: Optional[str] = None):
        if edit_target == "embed":
            if target_key not in EMBED_KEYS:
                await interaction.response.send_message("❌ 無効な埋め込みキーです。", ephemeral=True); return
            current_data = await get_embed_from_db(target_key) or DEFAULT_EMBED_DATA
            await interaction.response.send_modal(EmbedEditModal(target_key, current_data))
        
        elif edit_target == "button":
            if not panel_key:
                await interaction.response.send_message("❌ ボタンを編集するにはパネルを選択する必要があります。", ephemeral=True); return
            components = await get_panel_components_from_db(panel_key)
            if not components or not (target_comp := next((c for c in components if c['component_key'] == target_key), None)):
                await interaction.response.send_message("❌ 該当のボタンが見つかりません。", ephemeral=True); return
            await interaction.response.send_modal(ButtonEditModal(target_comp))

    @panel_group.command(name="style", description="[管理者] パネルのボタンの色を変更します。")
    @app_commands.describe(panel_key="対象のパネル", component_key="編集したいボタン", style="新しい色")
    @app_commands.autocomplete(panel_key=panel_key_autocomplete)
    @app_commands.choices(style=[app_commands.Choice(name=k, value=k) for k in BUTTON_STYLES_MAP.keys()])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def style_button(self, interaction: discord.Interaction, panel_key: str, component_key: str, style: str):
        await interaction.response.defer(ephemeral=True)
        components = await get_panel_components_from_db(panel_key)
        if not components or not (target_comp := next((c for c in components if c['component_key'] == component_key), None)):
            await interaction.followup.send("❌ 該当のボタンが見つかりません。", ephemeral=True); return
        target_comp['style'] = style
        try:
            await save_panel_component_to_db(target_comp)
            await interaction.followup.send(f"✅ **`{component_key}`** ボタンの色を **{style}** に変更しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"버튼 스타일 저장 중 오류: {e}", exc_info=True)
            await interaction.followup.send(f"❌ データベースへの保存中にエラーが発生しました。", ephemeral=True)
            
    @panel_group.command(name="refresh", description="[管理者] パネルを現在のDB設定で再生成します。")
    @app_commands.describe(panel_key="再生成したいパネル")
    @app_commands.autocomplete(panel_key=panel_key_autocomplete)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def refresh_panel(self, interaction: discord.Interaction, panel_key: str):
        await interaction.response.defer(ephemeral=True)
        cog_map = {"onboarding": "Onboarding", "roles": "ServerSystem", "nicknames": "Nicknames", "commerce": "Commerce", "fishing": "Fishing", "profile": "UserProfile"}
        cog_name = cog_map.get(panel_key)
        if not cog_name or not (cog := self.bot.get_cog(cog_name)):
            await interaction.followup.send(f"❌ **`{panel_key}`** に対応するCogが見つかりません。", ephemeral=True); return
        if hasattr(cog, 'regenerate_panel'):
            try:
                await cog.regenerate_panel()
                await interaction.followup.send(f"✅ **`{panel_key}`** パネルを正常に再生成しました。", ephemeral=True)
            except Exception as e:
                logger.error(f"패널 새로고침 중 오류: {e}", exc_info=True)
                await interaction.followup.send(f"❌ パネルの再生成中にエラーが発生しました。", ephemeral=True)
        else:
            await interaction.followup.send(f"❌ **`{cog_name}`** Cogに `regenerate_panel` 関数がありません。", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(PanelManager(bot))
