# cogs/features/custom_embed.py
import discord
from discord import ui
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional, List, Set

from utils.database import get_id, get_embed_from_db, get_panel_id, save_panel_id, get_panel_components_from_db
from utils.ui_defaults import CUSTOM_EMBED_SENDER_ROLES

logger = logging.getLogger(__name__)

class EmbedCreatorModal(ui.Modal, title="カスタム埋め込み作成"):
    title_input = ui.TextInput(label="タイトル", placeholder="埋め込みのタイトルを入力してください。", required=False, max_length=256)
    description_input = ui.TextInput(label="説明", placeholder="埋め込みの説明文を入力してください。", style=discord.TextStyle.paragraph, required=False, max_length=4000)
    color_input = ui.TextInput(label="色 (16進数コード)", placeholder="例: #5865F2 (空欄の場合はデフォルト色)", required=False, max_length=7)
    image_url_input = ui.TextInput(label="画像URL", placeholder="埋め込みに表示する画像のURLを入力してください。", required=False)
    thumbnail_url_input = ui.TextInput(label="サムネイルURL", placeholder="右上に表示するサムネイル画像のURLを入力してください。", required=False)

    def __init__(self, cog: 'CustomEmbed', existing_embed: Optional[discord.Embed] = None):
        super().__init__()
        self.cog = cog
        self.embed: Optional[discord.Embed] = None

        if existing_embed:
            self.title = "カスタム埋め込み編集"
            self.title_input.default = existing_embed.title
            self.description_input.default = existing_embed.description
            
            # --- [수정된 부분 시작] ---
            # discord.Embed.Empty 대신, 속성의 존재 여부를 직접 확인합니다.
            if existing_embed.color:
                self.color_input.default = str(existing_embed.color)
            if existing_embed.image:
                self.image_url_input.default = existing_embed.image.url
            if existing_embed.thumbnail:
                self.thumbnail_url_input.default = existing_embed.thumbnail.url
            # --- [수정된 부분 끝] ---

    async def on_submit(self, interaction: discord.Interaction):
        if not self.title_input.value and not self.description_input.value and not self.image_url_input.value:
            await interaction.response.send_message("❌ エラー: タイトル、説明、画像URLのいずれか一つは必ず入力してください。", ephemeral=True)
            return

        try:
            color = discord.Color.default()
            if self.color_input.value:
                try:
                    color = discord.Color(int(self.color_input.value.replace("#", ""), 16))
                except ValueError:
                    await interaction.response.send_message("❌ 色コードが無効です。`#RRGGBB`の形式で入力してください。", ephemeral=True)
                    return

            embed = discord.Embed(
                title=self.title_input.value or None,
                description=self.description_input.value or None,
                color=color
            )
            if self.image_url_input.value:
                embed.set_image(url=self.image_url_input.value)
            if self.thumbnail_url_input.value:
                embed.set_thumbnail(url=self.thumbnail_url_input.value)
            
            self.embed = embed
            await interaction.response.defer(ephemeral=True)

        except Exception as e:
            logger.error(f"임베드 생성 중 오류: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ 埋め込みの作成中にエラーが発生しました。", ephemeral=True)

class ChannelSelectView(ui.View):
    def __init__(self, cog: 'CustomEmbed', embed_to_send: discord.Embed):
        super().__init__(timeout=300)
        self.cog = cog
        self.embed_to_send = embed_to_send
        
        channel_select = ui.ChannelSelect(
            placeholder="メッセージを送信するチャンネルを選択...",
            min_values=1, max_values=1,
            channel_types=[discord.ChannelType.text]
        )
        channel_select.callback = self.on_channel_select
        self.add_item(channel_select)

    async def on_channel_select(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        target_channel_id = interaction.data['values'][0]
        channel: discord.TextChannel = interaction.guild.get_channel(int(target_channel_id))

        if not channel:
            return await interaction.followup.send("❌ チャンネルが見つかりませんでした。", ephemeral=True)
        
        if not channel.permissions_for(interaction.guild.me).send_messages or not channel.permissions_for(interaction.guild.me).embed_links:
            return await interaction.followup.send(f"❌ <#{channel.id}> チャンネルにメッセージを送信する権限がありません。", ephemeral=True)

        try:
            await channel.send(embed=self.embed_to_send)
            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(content=f"✅ <#{channel.id}> にメッセージを正常に送信しました。", view=self, embed=None)

        except Exception as e:
            logger.error(f"커스텀 임베드 전송 중 오류: {e}", exc_info=True)
            await interaction.followup.send(f"❌ <#{channel.id}> へのメッセージ送信中にエラーが発生しました。", ephemeral=True)

class CustomEmbedPanelView(ui.View):
    def __init__(self, cog: 'CustomEmbed'):
        super().__init__(timeout=None)
        self.cog = cog

    async def setup_buttons(self):
        self.clear_items()
        components = await get_panel_components_from_db("custom_embed")
        if not components: return
        
        button_info = components[0]
        button = ui.Button(
            label=button_info.get('label', '埋め込み作成'),
            style=discord.ButtonStyle.primary,
            emoji=button_info.get('emoji'),
            custom_id=button_info.get('component_key')
        )
        button.callback = self.on_button_click
        self.add_item(button)

    async def on_button_click(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member) or not any(role.id in self.cog.sender_role_ids for role in interaction.user.roles):
            return await interaction.response.send_message("❌ この機能を使用する権限がありません。", ephemeral=True)
        
        modal = EmbedCreatorModal(self.cog)
        await interaction.response.send_modal(modal)
        await modal.wait()

        if modal.embed:
            view = ChannelSelectView(self.cog, modal.embed)
            await interaction.followup.send("✅ プレビューが作成されました。下のメニューからメッセージを送信するチャンネルを選択してください。", embed=modal.embed, view=view, ephemeral=True)

class CustomEmbed(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_channel_id: Optional[int] = None
        self.sender_role_ids: Set[int] = set()
        self.view_instance: Optional[CustomEmbedPanelView] = None
        logger.info("CustomEmbed Cog가 성공적으로 초기화되었습니다.")

        self.edit_embed_context_menu = app_commands.ContextMenu(
            name="埋め込み編集",
            callback=self.edit_embed_message,
        )
        self.bot.tree.add_command(self.edit_embed_context_menu)

    async def cog_load(self):
        await self.load_configs()
        
    async def register_persistent_views(self):
        self.view_instance = CustomEmbedPanelView(self)
        await self.view_instance.setup_buttons()
        self.bot.add_view(self.view_instance)
        logger.info("✅ 커스텀 임베드 시스템의 영구 View가 성공적으로 등록되었습니다.")
        
    async def load_configs(self):
        self.panel_channel_id = get_id("custom_embed_panel_channel_id")
        self.sender_role_ids = {
            role_id for key in CUSTOM_EMBED_SENDER_ROLES 
            if (role_id := get_id(key)) is not None
        }
        logger.info("[CustomEmbed Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")
        
    async def edit_embed_message(self, interaction: discord.Interaction, message: discord.Message):
        if not isinstance(interaction.user, discord.Member) or not any(role.id in self.sender_role_ids for role in interaction.user.roles):
            return await interaction.response.send_message("❌ この機能を実行する権限がありません。", ephemeral=True)
        
        if message.author.id != self.bot.user.id or not message.embeds:
            return await interaction.response.send_message("❌ Botが送信した埋め込みメッセージでのみ使用できます。", ephemeral=True)
            
        modal = EmbedCreatorModal(self, existing_embed=message.embeds[0])
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        if modal.embed:
            try:
                await message.edit(embed=modal.embed)
                await interaction.followup.send("✅ 埋め込みメッセージを正常に編集しました。", ephemeral=True)
            except Exception as e:
                logger.error(f"임베드 수정 중 오류: {e}", exc_info=True)
                await interaction.followup.send("❌ メッセージの編集中にエラーが発生しました。", ephemeral=True)
                
    async def regenerate_panel(self, channel: discord.TextChannel) -> bool:
        panel_key = "custom_embed"
        embed_key = "panel_custom_embed"

        try:
            panel_info = get_panel_id(panel_key)
            if panel_info and (old_id := panel_info.get('message_id')):
                try:
                    old_message = await channel.fetch_message(old_id)
                    await old_message.delete()
                except (discord.NotFound, discord.Forbidden): pass
            
            embed_data = await get_embed_from_db(embed_key)
            if not embed_data:
                logger.error(f"DB에서 '{embed_key}' 임베드를 찾을 수 없어 패널을 생성할 수 없습니다.")
                return False
                
            embed = discord.Embed.from_dict(embed_data)
            if self.view_instance is None:
                await self.register_persistent_views()
            
            await self.view_instance.setup_buttons()
            new_message = await channel.send(embed=embed, view=self.view_instance)
            await save_panel_id(panel_key, new_message.id, channel.id)
            logger.info(f"✅ 커스텀 임베드 패널을 성공적으로 새로 생성했습니다. (채널: #{channel.name})")
            return True
        except Exception as e:
            logger.error(f"❌ {panel_key} 패널 재설치 중 오류 발생: {e}", exc_info=True)
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(CustomEmbed(bot))
