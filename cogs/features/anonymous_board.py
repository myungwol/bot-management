# cogs/features/anonymous_board.py
import discord
from discord import ui
from discord.ext import commands
import logging
import asyncio
from datetime import datetime, timezone
from typing import Optional

from utils.database import (
    get_id, add_anonymous_message, get_embed_from_db, 
    get_panel_id, save_panel_id, get_panel_components_from_db,
    has_posted_anonymously_today
)
from utils.helpers import format_embed_from_db

logger = logging.getLogger(__name__)

class AnonymousModal(ui.Modal, title="匿名メッセージ作成"):
    content = ui.TextInput(
        label="内容",
        placeholder="ここにあなたのメッセージを書いてください...",
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
            # 1. DB에 메시지 기록
            await add_anonymous_message(interaction.guild_id, interaction.user.id, self.content.value)

            # 2. 공개 채널에 전송할 익명 임베드 준비
            embed_data = await get_embed_from_db("anonymous_message")
            anonymous_embed = None
            if embed_data:
                anonymous_embed = format_embed_from_db(embed_data)
                anonymous_embed.description = self.content.value
                anonymous_embed.timestamp = datetime.now(timezone.utc)
            
            # 3. 패널 재생성 함수를 호출하여 로그와 패널을 함께 보냅니다.
            await self.cog.regenerate_panel(interaction.channel, last_anonymous_embed=anonymous_embed)
            
            # 4. 사용자에게 성공 메시지 전송 (5초 후 삭제)
            message = await interaction.followup.send("✅ あなたの匿名の声が届けられました。", ephemeral=True, wait=True)
            await asyncio.sleep(5)
            await message.delete()

        except Exception as e:
            logger.error(f"익명 메시지 제출 중 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ メッセージの投稿中にエラーが発生しました。", ephemeral=True)

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
            await interaction.response.send_message("❌ 本日の匿名投稿は既に完了しています。明日になると再度投稿できます。", ephemeral=True)
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
            return self.bot.get_channel(self.panel_channel_id)
        return None
        
    # [✅✅✅ 핵심 수정 ✅✅✅]
    # 패널 재생성 로직을 변경하여 로그와 패널이 거의 동시에 나타나도록 합니다.
    async def regenerate_panel(self, channel: Optional[discord.TextChannel] = None, panel_key: str = "panel_anonymous_board", last_anonymous_embed: Optional[discord.Embed] = None) -> bool:
        target_channel = channel or self.panel_channel
        if not target_channel:
            return False

        base_panel_key = panel_key.replace("panel_", "")
        embed_key = panel_key

        try:
            # 1. 이전 패널 메시지를 먼저 삭제합니다.
            panel_info = get_panel_id(base_panel_key)
            if panel_info and (old_id := panel_info.get('message_id')):
                try:
                    old_message = await target_channel.fetch_message(old_id)
                    await old_message.delete()
                except (discord.NotFound, discord.Forbidden): pass
            
            # 2. 새로운 패널 임베드와 View를 준비합니다.
            embed_data = await get_embed_from_db(embed_key)
            if not embed_data:
                logger.error(f"DB에서 '{embed_key}' 임베드를 찾을 수 없어 패널을 생성할 수 없습니다.")
                return False
            embed = discord.Embed.from_dict(embed_data)

            if self.view_instance is None:
                await self.register_persistent_views()
            await self.view_instance.setup_buttons()

            # 3. 새로운 로그 메시지(익명 글)와 새로운 패널을 거의 동시에 보냅니다.
            #    asyncio.gather를 사용하여 두 작업을 병렬로 실행 요청합니다.
            tasks = []
            if last_anonymous_embed:
                tasks.append(target_channel.send(embed=last_anonymous_embed))
            
            tasks.append(target_channel.send(embed=embed, view=self.view_instance))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # 4. 패널 메시지의 ID를 DB에 저장합니다.
            #    gather의 결과에서 패널 메시지를 찾아 ID를 저장합니다.
            new_panel_message = None
            for result in results:
                if isinstance(result, discord.Message) and result.view is not None:
                    new_panel_message = result
                    break
            
            if new_panel_message:
                await save_panel_id(base_panel_key, new_panel_message.id, target_channel.id)
                logger.info(f"✅ 익명 게시판 패널을 성공적으로 새로 생성/갱신했습니다. (채널: #{target_channel.name})")
                return True
            else:
                logger.error("패널 메시지 전송에 실패하여 ID를 저장할 수 없습니다.")
                return False
            
        except Exception as e:
            logger.error(f"❌ {panel_key} 패널 재설치 중 오류 발생: {e}", exc_info=True)
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(AnonymousBoard(bot))
