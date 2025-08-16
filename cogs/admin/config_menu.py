# cogs/admin/config_menu.py (Modal 전송 오류 수정 완료)

import discord
from discord.ext import commands
from discord import app_commands, ui
import logging
from typing import List, Dict, Any
from math import ceil

from utils.database import (
    get_embed_from_db, save_embed_to_db,
    get_panel_components_from_db, save_panel_component_to_db
)

logger = logging.getLogger(__name__)

PANEL_KEYS = ["roles", "onboarding", "nicknames", "commerce", "fishing", "profile"]
EMBED_KEYS = [
    "welcome_embed", "farewell_embed", "panel_roles", "panel_onboarding", "panel_nicknames", 
    "panel_commerce", "panel_fishing", "panel_profile", "embed_onboarding_approval", 
    "embed_onboarding_public_welcome", "embed_transfer_confirmation", "log_coin_gain", 
    "log_coin_transfer", "log_coin_admin", "embed_shop_buy", "embed_shop_sell"
]

DEFAULT_EMBED_DATA = { "title": "（タイトル未設定）", "description": "（説明未設定）", "color": 0x5865F2, "footer": {"text": ""}}

class EmbedEditModal(ui.Modal, title="埋め込みメッセージ編集"):
    modal_title = ui.TextInput(label="タイトル", style=discord.TextStyle.short, required=True, max_length=256)
    modal_description = ui.TextInput(label="説明", style=discord.TextStyle.paragraph, required=False, max_length=4000)
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
        except (ValueError, TypeError):
            await interaction.followup.send("❌ 無効な色コードです。`#RRGGBB`の形式で入力してください。", ephemeral=True); return

        embed_data = { "title": self.modal_title.value, "description": self.modal_description.value, "color": color_value, "footer": {"text": self.modal_footer.value} }
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
        self.row.default = str(component_data.get('row', '')) if component_data.get('row') is not None else ''

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        row_val_str = self.row.value
        if row_val_str:
            try:
                row_val = int(row_val_str)
                if not (0 <= row_val <= 4):
                    await interaction.followup.send("❌ 行は0から4までの数字でなければなりません。", ephemeral=True); return
            except ValueError:
                await interaction.followup.send("❌ 行には数字を入力してください。", ephemeral=True); return
        else:
            row_val = self.component_data.get('row', 0)
            
        self.component_data['label'] = self.label.value; self.component_data['emoji'] = self.emoji.value or None; self.component_data['row'] = row_val
        try:
            await save_panel_component_to_db(self.component_data)
            await interaction.followup.send(f"✅ **`{self.component_data['component_key']}`** ボタンを保存しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"버튼 저장 중 오류: {e}", exc_info=True)
            await interaction.followup.send(f"❌ データベースへの保存中にエラーが発生しました。", ephemeral=True)

class ConfigSelect(ui.Select):
    def __init__(self, options: List[discord.SelectOption], placeholder: str):
        super().__init__(placeholder=placeholder, options=options, custom_id=f"config_select_{placeholder[:20]}")

    # [수정] 여기가 문제의 콜백 함수입니다.
    async def callback(self, interaction: discord.Interaction):
        # defer()를 호출하지 않고, 바로 send_modal()을 호출합니다.
        
        selected_value = self.values[0]
        parts = selected_value.split(':')
        
        try:
            if parts[0] == "embed":
                embed_key = parts[1]
                current_data = await get_embed_from_db(embed_key) or DEFAULT_EMBED_DATA
                modal = EmbedEditModal(embed_key, current_data)
                await interaction.response.send_modal(modal) # followup 이 아니라 response 로 보냅니다.
            elif parts[0] == "button":
                panel_key, component_key = parts[1], parts[2]
                components = await get_panel_components_from_db(panel_key)
                if not components:
                     # defer를 안했으므로, 응답이 필요합니다.
                    await interaction.response.send_message("❌ 該当のボタンデータが見つかりません。", ephemeral=True)
                    return

                target_comp = next((c for c in components if c['component_key'] == component_key), None)
                if not target_comp:
                    await interaction.response.send_message("❌ 該当のボタンが見つかりません。", ephemeral=True)
                    return
                
                modal = ButtonEditModal(target_comp)
                await interaction.response.send_modal(modal) # followup 이 아니라 response 로 보냅니다.
        except Exception as e:
            logger.error(f"Config Select 콜백 처리 중 오류: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message("❌処理中にエラーが発生しました。", ephemeral=True)


class ConfigMenuView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    async def initialize(self):
        embed_options = [discord.SelectOption(label=f"埋め込み: {key}", value=f"embed:{key}") for key in EMBED_KEYS]
        button_options = []
        for panel_key in PANEL_KEYS:
            components = await get_panel_components_from_db(panel_key)
            if components:
                for comp in components:
                    if comp.get('component_type') == 'button' and comp.get('component_key'):
                        button_options.append(
                            discord.SelectOption(label=f"ボタン: {panel_key} > {comp.get('label', comp.get('component_key'))}", value=f"button:{panel_key}:{comp['component_key']}")
                        )
        all_options = embed_options + button_options
        if not all_options: return
        chunk_size = 25; total_chunks = ceil(len(all_options) / chunk_size)
        for i in range(total_chunks):
            start = i * chunk_size; end = start + chunk_size; chunk = all_options[start:end]
            placeholder = f"設定する項目を選択 ({i+1}/{total_chunks})"
            self.add_item(ConfigSelect(options=chunk, placeholder=placeholder))

class ConfigMenu(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("ConfigMenu Cog가 성공적으로 초기화되었습니다.")
    @app_commands.command(name="config", description="[管理者] ボットの埋め込みやボタンなどのUIを管理します。")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def open_config_menu(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            view = ConfigMenuView(); await view.initialize()
            await interaction.followup.send("⚙️ 봇 UI 설정 메뉴\n\n수정하고 싶은 임베드나 버튼이 포함된 메뉴를 선택하세요.", view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"❌ 설정 메뉴(/config) 실행 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send("❌ 메뉴를 불러오는 중 오류가 발생했습니다. 로그를 확인해주세요.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ConfigMenu(bot))
