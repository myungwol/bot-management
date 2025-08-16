# cogs/admin/embed_manager.py (새 파일)

import discord
from discord.ext import commands
from discord import app_commands, ui
import logging
import json
from typing import List, Optional

from utils.database import get_embed_from_db, save_embed_to_db

logger = logging.getLogger(__name__)

# 봇 전체에서 관리할 임베드 목록
EMBED_KEYS = [
    "welcome_embed", "farewell_embed", "panel_roles", "panel_onboarding",
    "panel_nicknames", "panel_commerce", "panel_fishing", "panel_profile"
]

DEFAULT_EMBED_DATA = {
    "title": "（タイトル未設定）",
    "description": "（説明未設定）",
    "color": 0x5865F2, # Discord Blue
    "footer": {"text": ""}
}

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
            color_value = int(color.lstrip('#'), 16) if color else DEFAULT_EMBED_DATA["color"]
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

class EmbedManager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("EmbedManager Cog가 성공적으로 초기화되었습니다.")

    embed_group = app_commands.Group(name="embed", description="埋め込みメッセージを管理します。")

    async def embed_key_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        return [
            app_commands.Choice(name=key, value=key)
            for key in EMBED_KEYS if current.lower() in key.lower()
        ][:25]

    @embed_group.command(name="set", description="[管理者] 埋め込みメッセージを作成または編集します。")
    @app_commands.describe(embed_key="編集したい埋め込みメッセージを選択してください。")
    @app_commands.autocomplete(embed_key=embed_key_autocomplete)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_embed(self, interaction: discord.Interaction, embed_key: str):
        if embed_key not in EMBED_KEYS:
            await interaction.response.send_message("❌ 無効な埋め込みキーです。リストから選択してください。", ephemeral=True)
            return

        current_data = await get_embed_from_db(embed_key)
        if not current_data:
            current_data = DEFAULT_EMBED_DATA.copy()
            # 기본 설명에 변수 예시 추가
            if "welcome" in embed_key:
                current_data["description"] = "ようこそ、{member_mention}さん！"
            elif "farewell" in embed_key:
                current_data["description"] = "さようなら、{member_name}さん..."
        
        modal = EmbedEditModal(embed_key, current_data)
        await interaction.response.send_modal(modal)

    @embed_group.command(name="view", description="[管理者] 保存されている埋め込みメッセージをプレビューします。")
    @app_commands.describe(embed_key="プレビューしたい埋め込みメッセージを選択してください。")
    @app_commands.autocomplete(embed_key=embed_key_autocomplete)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def view_embed(self, interaction: discord.Interaction, embed_key: str):
        if embed_key not in EMBED_KEYS:
            await interaction.response.send_message("❌ 無効な埋め込みキーです。リストから選択してください。", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        embed_data = await get_embed_from_db(embed_key)
        if not embed_data:
            await interaction.followup.send(f"⚠️ **`{embed_key}`** にはデータが保存されていません。", ephemeral=True)
            return
        
        embed = discord.Embed.from_dict(embed_data)
        await interaction.followup.send(f"プレビュー: **`{embed_key}`**", embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedManager(bot))
