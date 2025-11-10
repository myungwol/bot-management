# cogs/features/user_guide.py

import discord
from discord import ui
from discord.ext import commands
import logging
from typing import Optional
import asyncio

from utils.database import get_id, save_panel_id, get_panel_id, get_embed_from_db, get_panel_components_from_db
from utils.helpers import format_embed_from_db

logger = logging.getLogger(__name__)

class UserGuidePanelView(ui.View):
    """신규 유저 안내 패널에 표시될 View"""
    def __init__(self, cog: 'UserGuide'):
        super().__init__(timeout=None)
        self.cog = cog

    async def setup_buttons(self):
        """DB 설정에 따라 버튼을 동적으로 생성합니다."""
        self.clear_items()
        components_data = await get_panel_components_from_db('user_guide')
        if not components_data:
            # DB에 정보가 없을 경우의 기본 버튼
            button = ui.Button(label="안내 시작하기", style=discord.ButtonStyle.success, custom_id="start_user_guide")
        else:
            comp = components_data[0]
            button = ui.Button(
                label=comp.get('label'),
                style=discord.ButtonStyle.success, # 스타일은 success로 고정하거나 DB에서 가져올 수 있습니다.
                emoji=comp.get('emoji'),
                custom_id=comp.get('component_key')
            )
        
        button.callback = self.start_guide_callback
        self.add_item(button)

    async def start_guide_callback(self, interaction: discord.Interaction):
        """'안내 시작하기' 버튼을 눌렀을 때 실행될 로직"""
        # '반죽제조팀' 역할 가져오기
        staff_role_id = get_id("role_staff_newbie_helper")
        if not staff_role_id or not (staff_role := interaction.guild.get_role(staff_role_id)):
            await interaction.response.send_message("❌ 죄송합니다. 현재 안내를 담당할 스태프 역할이 지정되지 않았습니다.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            # 비공개 스레드 생성
            thread_name = f"👋ㅣ{interaction.user.display_name}님의-안내"
            thread = await interaction.channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.private_thread,
                reason=f"{interaction.user.display_name}님의 신규 유저 안내"
            )

            # 스레드에 환영 메시지 전송
            embed_data = await get_embed_from_db("embed_user_guide_welcome")
            if embed_data:
                embed = format_embed_from_db(
                    embed_data,
                    member_name=interaction.user.display_name,
                    staff_role_mention=staff_role.mention
                )
                
                content = f"{interaction.user.mention} {staff_role.mention}"
                await thread.send(content=content, embed=embed, allowed_mentions=discord.AllowedMentions(users=True, roles=True))
            
            # 사용자에게 스레드 생성 알림
            msg = await interaction.followup.send(f"✅ 안내를 위한 비공개 스레드를 생성했습니다: {thread.mention}", ephemeral=True, wait=True)
            await asyncio.sleep(10) # 10초 후 자동 삭제
            await msg.delete()

        except Exception as e:
            logger.error(f"유저 안내 스레드 생성 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send("❌ 스레드를 생성하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.", ephemeral=True)


class UserGuide(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_channel_id: Optional[int] = None
        self.view_instance: Optional[UserGuidePanelView] = None
        logger.info("UserGuide Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        await self.load_configs()

    async def register_persistent_views(self):
        """봇 재시작 시에도 View가 동작하도록 등록합니다."""
        self.view_instance = UserGuidePanelView(self)
        await self.view_instance.setup_buttons()
        self.bot.add_view(self.view_instance)
        logger.info("✅ 신규 유저 안내 시스템의 영구 View가 성공적으로 등록되었습니다.")
        
    async def load_configs(self):
        """DB에서 설정을 불러옵니다."""
        self.panel_channel_id = get_id("user_guide_panel_channel_id")
        logger.info("[UserGuide Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")
        
    async def regenerate_panel(self, channel: discord.TextChannel, panel_key: str = "panel_user_guide") -> bool:
        """패널 메시지를 (재)생성합니다."""
        base_panel_key = panel_key.replace("panel_", "")
        embed_key = panel_key

        try:
            # 기존 패널 메시지 삭제
            panel_info = get_panel_id(base_panel_key)
            if panel_info and (old_id := panel_info.get('message_id')):
                try:
                    old_message = await channel.fetch_message(old_id)
                    await old_message.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass
            
            # 새 패널 메시지 생성
            embed_data = await get_embed_from_db(embed_key)
            if not embed_data:
                logger.warning(f"DB에서 '{embed_key}' 임베드 데이터를 찾을 수 없어, 패널 생성을 건너뜁니다.")
                return False
                
            embed = discord.Embed.from_dict(embed_data)
            
            if self.view_instance is None:
                await self.register_persistent_views()
            
            await self.view_instance.setup_buttons()
            new_message = await channel.send(embed=embed, view=self.view_instance)
            await save_panel_id(base_panel_key, new_message.id, channel.id)
            logger.info(f"✅ {panel_key} 패널을 성공적으로 새로 생성했습니다. (채널: #{channel.name})")
            return True
        except Exception as e:
            logger.error(f"❌ {panel_key} 패널 재설치 중 오류 발생: {e}", exc_info=True)
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(UserGuide(bot))
