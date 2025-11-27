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

class EmbedCreatorModal(ui.Modal, title="커스텀 임베드 작성"):
    title_input = ui.TextInput(label="제목", placeholder="임베드 제목을 입력하세요.", required=False, max_length=256)
    description_input = ui.TextInput(label="설명", placeholder="임베드 설명을 입력하세요.", style=discord.TextStyle.paragraph, required=False, max_length=4000)
    color_input = ui.TextInput(label="색상 (16진수 코드)", placeholder="예: #5865F2 (비워두면 기본 색상)", required=False, max_length=7)
    image_url_input = ui.TextInput(label="이미지 URL", placeholder="임베드에 표시할 이미지 URL을 입력하세요.", required=False)
    thumbnail_url_input = ui.TextInput(label="썸네일 URL", placeholder="오른쪽 상단에 표시할 썸네일 이미지 URL을 입력하세요.", required=False)

    def __init__(self, cog: 'CustomEmbed', existing_embed: Optional[discord.Embed] = None):
        super().__init__()
        self.cog = cog
        self.embed: Optional[discord.Embed] = None

        if existing_embed:
            self.title = "커스텀 임베드 편집"
            self.title_input.default = existing_embed.title
            self.description_input.default = existing_embed.description
            
            if existing_embed.color:
                self.color_input.default = str(existing_embed.color)
            if existing_embed.image:
                self.image_url_input.default = existing_embed.image.url
            if existing_embed.thumbnail:
                self.thumbnail_url_input.default = existing_embed.thumbnail.url

    async def on_submit(self, interaction: discord.Interaction):
        if not self.title_input.value and not self.description_input.value and not self.image_url_input.value:
            await interaction.response.send_message("❌ 오류: 제목, 설명, 이미지 URL 중 하나는 반드시 입력해야 합니다.", ephemeral=True)
            return

        try:
            color = discord.Color.default()
            if self.color_input.value:
                try:
                    color = discord.Color(int(self.color_input.value.replace("#", ""), 16))
                except ValueError:
                    await interaction.response.send_message("❌ 색상 코드가 유효하지 않습니다. `#RRGGBB` 형식으로 입력해주세요.", ephemeral=True)
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
                await interaction.response.send_message("❌ 임베드를 만드는 중 오류가 발생했습니다.", ephemeral=True)

class ChannelSelectView(ui.View):
    def __init__(self, cog: 'CustomEmbed', embed_to_send: discord.Embed):
        super().__init__(timeout=300)
        self.cog = cog
        self.embed_to_send = embed_to_send
        
        channel_select = ui.ChannelSelect(
            placeholder="메시지를 보낼 채널을 선택하세요...",
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
            return await interaction.followup.send("❌ 채널을 찾을 수 없습니다.", ephemeral=True)
        
        if not channel.permissions_for(interaction.guild.me).send_messages or not channel.permissions_for(interaction.guild.me).embed_links:
            return await interaction.followup.send(f"❌ <#{channel.id}> 채널에 메시지를 보낼 권한이 없습니다.", ephemeral=True)

        try:
            await channel.send(embed=self.embed_to_send)
            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(content=f"✅ <#{channel.id}> 채널에 메시지를 성공적으로 보냈습니다.", view=self, embed=None)

        except Exception as e:
            logger.error(f"커스텀 임베드 전송 중 오류: {e}", exc_info=True)
            await interaction.followup.send(f"❌ <#{channel.id}> 채널에 메시지를 보내는 중 오류가 발생했습니다.", ephemeral=True)

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
            label=button_info.get('label', '임베드 작성'),
            style=discord.ButtonStyle.primary,
            emoji=button_info.get('emoji'),
            custom_id=button_info.get('component_key')
        )
        button.callback = self.on_button_click
        self.add_item(button)

    async def on_button_click(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("❌ 멤버 정보를 확인할 수 없습니다.", ephemeral=True)

        # [수정] 관리자 권한(Administrator)이 있거나, 허용된 역할이 있거나, 서버 소유자인 경우 통과
        is_admin = interaction.user.guild_permissions.administrator
        has_role = any(role.id in self.cog.sender_role_ids for role in interaction.user.roles)
        is_owner = interaction.user.id == interaction.guild.owner_id

        if not (is_admin or has_role or is_owner):
            return await interaction.response.send_message("❌ 이 기능을 사용할 권한이 없습니다.", ephemeral=True)
        
        modal = EmbedCreatorModal(self.cog)
        await interaction.response.send_modal(modal)
        await modal.wait()

        if modal.embed:
            view = ChannelSelectView(self.cog, modal.embed)
            await interaction.followup.send("✅ 미리보기가 만들어졌습니다. 아래 메뉴에서 메시지를 보낼 채널을 선택하세요.", embed=modal.embed, view=view, ephemeral=True)

class CustomEmbed(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_channel_id: Optional[int] = None
        self.sender_role_ids: Set[int] = set()
        self.view_instance: Optional[CustomEmbedPanelView] = None
        logger.info("CustomEmbed Cog가 성공적으로 초기화되었습니다.")

        self.edit_embed_context_menu = app_commands.ContextMenu(
            name="임베드 편집",
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
        try:
            if not isinstance(interaction.user, discord.Member):
                return await interaction.response.send_message("❌ 멤버 정보를 확인할 수 없습니다.", ephemeral=True)

            # [수정] 관리자 권한(Administrator)이 있거나, 허용된 역할이 있거나, 서버 소유자인 경우 통과
            is_admin = interaction.user.guild_permissions.administrator
            has_role = any(role.id in self.sender_role_ids for role in interaction.user.roles)
            is_owner = interaction.user.id == interaction.guild.owner_id

            if not (is_admin or has_role or is_owner):
                return await interaction.response.send_message("❌ 이 기능을 실행할 권한이 없습니다.", ephemeral=True)
            
            if message.author.id != self.bot.user.id or not message.embeds:
                return await interaction.response.send_message("❌ 봇이 보낸 임베드 메시지에만 사용할 수 있습니다.", ephemeral=True)
                
            modal = EmbedCreatorModal(self, existing_embed=message.embeds[0])
            await interaction.response.send_modal(modal)
            await modal.wait()
            
            if modal.embed:
                await message.edit(embed=modal.embed)
                await interaction.followup.send("✅ 임베드 메시지를 성공적으로 수정했습니다.", ephemeral=True)

        except discord.errors.NotFound as e:
            if e.code == 10062:
                logger.warning(f"임베드 편집 상호작용 타임아웃: {interaction.user}")
                try:
                    await interaction.followup.send("⏳ 처리 시간이 초과되었습니다.", ephemeral=True)
                except: pass
            else:
                logger.error(f"임베드 편집 중 NotFound 오류: {e}", exc_info=True)

        except Exception as e:
            logger.error(f"임베드 편집 중 오류: {e}", exc_info=True)
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ 메시지를 수정하는 중 오류가 발생했습니다.", ephemeral=True)
            else:
                await interaction.followup.send("❌ 메시지를 수정하는 중 오류가 발생했습니다.", ephemeral=True)

    async def regenerate_panel(self, channel: discord.TextChannel, panel_key: str = None) -> bool:
        current_panel_key = "custom_embed"
        embed_key = "panel_custom_embed"

        try:
            panel_info = get_panel_id(current_panel_key)
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
            await save_panel_id(current_panel_key, new_message.id, channel.id)
            logger.info(f"✅ 커스텀 임베드 패널을 성공적으로 새로 생성했습니다. (채널: #{channel.name})")
            return True
        except Exception as e:
            logger.error(f"❌ {current_panel_key} 패널 재설치 중 오류 발생: {e}", exc_info=True)
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(CustomEmbed(bot))
