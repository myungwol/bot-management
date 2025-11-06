# cogs/features/anonymous_board.py
import discord
from discord import ui
from discord.ext import commands
import logging
import asyncio
from datetime import datetime, timezone, timedelta
# ▼▼▼ [핵심 수정] 누락되었던 Optional을 import 합니다. ▼▼▼
from typing import Optional

from utils.database import (
    get_id, add_anonymous_message, get_embed_from_db,
    get_panel_id, save_panel_id, get_panel_components_from_db,
    has_posted_anonymously_today
)
from utils.helpers import format_embed_from_db, format_seconds_to_hms

logger = logging.getLogger(__name__)

# 한국 시간대(KST)를 나타내는 timezone 객체
KST = timezone(timedelta(hours=9))

class AnonymousModal(ui.Modal, title="익명 메시지 작성"):
    content = ui.TextInput(
        label="내용",
        placeholder="이곳에 메시지를 작성해주세요...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1500
    )

    def __init__(self, cog: 'AnonymousBoard'):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        try:
            await add_anonymous_message(interaction.guild_id, interaction.user.id, self.content.value)

            embed_data = await get_embed_from_db("anonymous_message")
            anonymous_embed = None
            if embed_data:
                anonymous_embed = format_embed_from_db(embed_data)
                anonymous_embed.description = self.content.value
                anonymous_embed.timestamp = datetime.now(timezone.utc)
            
            # [수정] 익명 메시지를 보낼 채널을 interaction.channel 대신 self.cog.panel_channel로 명시합니다.
            target_channel = self.cog.panel_channel or interaction.channel
            await self.cog.regenerate_panel(target_channel, last_anonymous_embed=anonymous_embed)
            
            message = await interaction.followup.send("✅ 당신의 익명 메시지가 성공적으로 전달되었습니다.", ephemeral=True, wait=True)
            await asyncio.sleep(5)
            await message.delete()

        except Exception as e:
            logger.error(f"익명 메시지 제출 중 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 메시지를 투고하는 중 오류가 발생했습니다.", ephemeral=True)

class AnonymousPanelView(ui.View):
    def __init__(self, cog: 'AnonymousBoard'):
        super().__init__(timeout=None)
        self.cog = cog

    async def setup_buttons(self):
        self.clear_items()
        components = await get_panel_components_from_db("anonymous_board")
        if not components: return
        
        button_info = components[0]
        button = ui.Button(
            label=button_info.get('label'),
            style=discord.ButtonStyle.secondary,
            emoji=button_info.get('emoji'),
            custom_id=button_info.get('component_key')
        )
        button.callback = self.on_button_click
        self.add_item(button)

    async def on_button_click(self, interaction: discord.Interaction):
        already_posted = await has_posted_anonymously_today(interaction.user.id)
        
        if already_posted:
            now_kst = datetime.now(KST)
            tomorrow_kst = now_kst.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            time_remaining_seconds = (tomorrow_kst - now_kst).total_seconds()
            formatted_time = format_seconds_to_hms(time_remaining_seconds)
            
            await interaction.response.send_message(f"❌ 오늘은 이미 글을 작성했습니다. 다음 작성까지 **{formatted_time}** 남았습니다.", ephemeral=True)
            return
            
        await interaction.response.send_modal(AnonymousModal(self.cog))

class AnonymousBoard(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_channel_id: Optional[int] = None
        self.view_instance: Optional[AnonymousPanelView] = None
        logger.info("AnonymousBoard Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        await self.load_configs()
        
    async def register_persistent_views(self):
        self.view_instance = AnonymousPanelView(self)
        await self.view_instance.setup_buttons()
        self.bot.add_view(self.view_instance)
        logger.info("✅ 익명 게시판의 영구 View가 성공적으로 등록되었습니다.")
        
    async def load_configs(self):
        self.panel_channel_id = get_id("anonymous_board_channel_id")
        logger.info("[AnonymousBoard Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")
        
    @property
    def panel_channel(self) -> Optional[discord.TextChannel]:
        if self.panel_channel_id:
            channel = self.bot.get_channel(self.panel_channel_id)
            if isinstance(channel, discord.TextChannel):
                return channel
        return None
        
    async def regenerate_panel(self, channel: Optional[discord.TextChannel] = None, panel_key: str = "panel_anonymous_board", last_anonymous_embed: Optional[discord.Embed] = None) -> bool:
        target_channel = channel or self.panel_channel
        if not target_channel:
            logger.warning("익명 게시판 패널을 재생성할 대상 채널을 찾을 수 없습니다.")
            return False

        base_panel_key = panel_key.replace("panel_", "")
        embed_key = panel_key

        try:
            panel_info = get_panel_id(base_panel_key)
            if panel_info and (old_id := panel_info.get('message_id')):
                try:
                    old_message = await target_channel.fetch_message(old_id)
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

            if last_anonymous_embed:
                await target_channel.send(embed=last_anonymous_embed)
            
            new_panel_message = await target_channel.send(embed=embed, view=self.view_instance)
            
            await save_panel_id(base_panel_key, new_panel_message.id, target_channel.id)
            logger.info(f"✅ 익명 게시판 패널을 성공적으로 새로 생성/갱신했습니다. (채널: #{target_channel.name})")
            return True
            
        except Exception as e:
            logger.error(f"❌ {panel_key} 패널 재설치 중 오류 발생: {e}", exc_info=True)
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(AnonymousBoard(bot))
