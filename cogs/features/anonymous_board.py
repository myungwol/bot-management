
# cogs/features/anonymous_board.py
import discord
from discord import ui
from discord.ext import commands
import logging
import asyncio
from datetime import datetime, timezone

from utils.database import get_id, get_cooldown, set_cooldown, add_anonymous_message, get_embed_from_db, get_panel_id, save_panel_id, get_panel_components_from_db
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

            # 2. 공개 채널에 익명 임베드 전송
            embed_data = await get_embed_from_db("anonymous_message")
            if embed_data and self.cog.panel_channel:
                embed = format_embed_from_db(embed_data)
                embed.description = self.content.value
                embed.timestamp = datetime.now(timezone.utc)
                await self.cog.panel_channel.send(embed=embed)
            
            # 3. 쿨다운 설정
            await set_cooldown(str(interaction.user.id), "anonymous_post")

            # 4. 패널 재생성
            await self.cog.regenerate_panel()
            
            # 5. 사용자에게 성공 메시지 전송 (5초 후 삭제)
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
        # 쿨다운 (하루에 한 번) 체크 - 86400초 = 24시간
        cooldown_seconds = 86400
        last_time = await get_cooldown(str(interaction.user.id), "anonymous_post")
        utc_now = datetime.now(timezone.utc).timestamp()

        if last_time and utc_now - last_time < cooldown_seconds:
            rem = cooldown_seconds - (utc_now - last_time)
            h, r = divmod(int(rem), 3600)
            m, s = divmod(r, 60)
            await interaction.response.send_message(f"❌ 次の投稿まであと {h}時間{m}分{s}秒 お待ちください。", ephemeral=True)
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
        
    async def regenerate_panel(self, channel: Optional[discord.TextChannel] = None) -> bool:
        target_channel = channel or self.panel_channel
        if not target_channel:
            return False

        panel_key = "anonymous_board"
        embed_key = "panel_anonymous_board"

        try:
            panel_info = get_panel_id(panel_key)
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
            new_message = await target_channel.send(embed=embed, view=self.view_instance)
            await save_panel_id(panel_key, new_message.id, target_channel.id)
            logger.info(f"✅ 익명 게시판 패널을 성공적으로 새로 생성했습니다. (채널: #{target_channel.name})")
            return True
        except Exception as e:
            logger.error(f"❌ {panel_key} 패널 재설치 중 오류 발생: {e}", exc_info=True)
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(AnonymousBoard(bot))
