# cogs/features/user_guide.py

import discord
from discord import ui
from discord.ext import commands
import logging
from typing import Optional, Dict, List, Any
import asyncio

from utils.database import get_id, save_panel_id, get_panel_id, get_embed_from_db, get_panel_components_from_db
from utils.helpers import format_embed_from_db

logger = logging.getLogger(__name__)

# --- Forward declaration for type hinting ---
class InteractiveGuideView:
    pass

# 자기소개서 작성을 위한 Modal 클래스
class IntroductionFormModal(ui.Modal, title="자기소개서 작성"):
    name = ui.TextInput(label="이름", placeholder="마을에서 사용할 이름을 알려주세요.", required=True)
    age = ui.TextInput(label="나이", placeholder="나이를 알려주세요.", required=True)
    gender = ui.TextInput(label="성별", placeholder="성별을 알려주세요.", required=True, max_length=10)
    join_path = ui.TextInput(label="가입 경로", placeholder="어떻게 우리 마을을 알게 되셨나요?", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, guide_view: InteractiveGuideView):
        super().__init__()
        self.guide_view = guide_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("✅ 자기소개서를 제출했습니다. 감사합니다!", ephemeral=True)

        confirmation_message = (
            f"{interaction.user.mention}/{self.name.value}/{self.age.value}/"
            f"{self.gender.value}/{self.join_path.value}"
        )
        await interaction.channel.send(confirmation_message)

        # 제출 후에는 가이드 메시지의 버튼들을 모두 비활성화
        if self.guide_view.message:
            for item in self.guide_view.children:
                item.disabled = True
            try:
                await self.guide_view.message.edit(view=self.guide_view)
            except (discord.NotFound, discord.HTTPException):
                pass
        self.guide_view.stop()

# 스레드 내에서 페이지 넘기기를 담당하는 View 클래스
class InteractiveGuideView(ui.View):
    def __init__(self, cog: 'UserGuide', user: discord.Member, steps_data: List[Dict[str, Any]]):
        super().__init__(timeout=600) # 10분 동안 상호작용 없으면 타임아웃
        self.cog = cog
        self.user = user
        self.steps_data = steps_data
        self.current_step = 0
        self.message: Optional[discord.Message] = None
        self._update_buttons()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # 스레드를 생성한 유저만 버튼을 누를 수 있도록 제한
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ 다른 사람의 안내 가이드 버튼은 누를 수 없습니다.", ephemeral=True)
            return False
        return True

    def _get_current_embed(self) -> discord.Embed:
        embed_data = self.steps_data[self.current_step]
        return format_embed_from_db(embed_data, member_name=self.user.display_name)

    def _update_buttons(self):
        self.clear_items()
        is_first_page = self.current_step == 0
        is_last_page = self.current_step == len(self.steps_data) - 1

        prev_button = ui.Button(label="◀ 이전", style=discord.ButtonStyle.secondary, custom_id="guide_prev", disabled=is_first_page)
        prev_button.callback = self.go_previous
        self.add_item(prev_button)

        if is_last_page:
            intro_button = ui.Button(label="자기소개서 작성하기", style=discord.ButtonStyle.success, emoji="📝", custom_id="guide_intro_form")
            intro_button.callback = self.open_intro_form
            self.add_item(intro_button)
        else:
            next_button = ui.Button(label="다음 ▶", style=discord.ButtonStyle.primary, custom_id="guide_next")
            next_button.callback = self.go_next
            self.add_item(next_button)

    async def go_previous(self, interaction: discord.Interaction):
        if self.current_step > 0:
            self.current_step -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self._get_current_embed(), view=self)

    async def go_next(self, interaction: discord.Interaction):
        if self.current_step < len(self.steps_data) - 1:
            self.current_step += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self._get_current_embed(), view=self)

    async def open_intro_form(self, interaction: discord.Interaction):
        await interaction.response.send_modal(IntroductionFormModal(self))

    async def on_timeout(self):
        if self.message:
            for item in self.children:
                item.disabled = True
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass

# 패널에 표시될 View 클래스 (기존과 동일)
class UserGuidePanelView(ui.View):
    def __init__(self, cog: 'UserGuide'):
        super().__init__(timeout=None)
        self.cog = cog

    async def setup_buttons(self):
        self.clear_items()
        components_data = await get_panel_components_from_db('user_guide')
        comp = components_data[0] if components_data else {}
        button = ui.Button(label=comp.get('label', "안내 시작하기"), style=discord.ButtonStyle.success, emoji=comp.get('emoji', "👋"), custom_id=comp.get('component_key', "start_user_guide"))
        button.callback = self.start_guide_callback
        self.add_item(button)

    async def start_guide_callback(self, interaction: discord.Interaction):
        if self.cog.has_active_thread(interaction.user):
            thread_id = self.cog.active_guide_threads.get(interaction.user.id)
            await interaction.response.send_message(f"❌ 이미 진행 중인 안내 스레드(<#{thread_id}>)가 있습니다.", ephemeral=True)
            return

        staff_role_id = get_id("role_staff_newbie_helper")
        if not staff_role_id or not (staff_role := interaction.guild.get_role(staff_role_id)):
            await interaction.response.send_message("❌ 죄송합니다. 현재 안내를 담당할 스태프 역할이 지정되지 않았습니다.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        try:
            thread_name = f"👋ㅣ{interaction.user.display_name}님의-안내"
            thread = await interaction.channel.create_thread(name=thread_name, type=discord.ChannelType.private_thread, reason=f"{interaction.user.display_name}님의 신규 유저 안내")
            self.cog.active_guide_threads[interaction.user.id] = thread.id

            # DB에서 모든 안내 페이지 데이터를 가져옴
            steps_data = await self.cog.get_guide_steps()
            if not steps_data:
                raise ValueError("안내 가이드 페이지 데이터를 DB에서 불러올 수 없습니다.")

            # InteractiveGuideView 인스턴스 생성
            guide_view = InteractiveGuideView(self.cog, interaction.user, steps_data)
            
            # 스레드에 첫 페이지와 View 전송
            initial_embed = guide_view._get_current_embed()
            content = f"{interaction.user.mention} {staff_role.mention}"
            guide_message = await thread.send(content=content, embed=initial_embed, view=guide_view, allowed_mentions=discord.AllowedMentions(users=True, roles=True))
            
            # View가 자신의 메시지를 참조할 수 있도록 설정
            guide_view.message = guide_message

            msg = await interaction.followup.send(f"✅ 안내를 위한 비공개 스레드를 생성했습니다: {thread.mention}", ephemeral=True, wait=True)
            await asyncio.sleep(10)
            await msg.delete()

        except Exception as e:
            self.cog.active_guide_threads.pop(interaction.user.id, None)
            logger.error(f"유저 안내 스레드 생성 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send("❌ 스레드를 생성하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.", ephemeral=True)

# 메인 Cog 클래스
class UserGuide(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_channel_id: Optional[int] = None
        self.view_instance: Optional[UserGuidePanelView] = None
        self.active_guide_threads: Dict[int, int] = {}
        logger.info("UserGuide Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        await self.load_configs()

    async def register_persistent_views(self):
        self.view_instance = UserGuidePanelView(self)
        await self.view_instance.setup_buttons()
        self.bot.add_view(self.view_instance)
        logger.info("✅ 신규 유저 안내 시스템의 영구 View가 성공적으로 등록되었습니다.")
        
    async def load_configs(self):
        self.panel_channel_id = get_id("user_guide_panel_channel_id")
        logger.info("[UserGuide Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")
        
    async def get_guide_steps(self) -> List[Dict[str, Any]]:
        """DB에서 페이지 순서대로 안내 임베드 데이터를 가져옵니다."""
        keys = ["guide_thread_page_1", "guide_thread_page_2", "guide_thread_page_3"]
        steps = []
        for key in keys:
            embed_data = await get_embed_from_db(key)
            if embed_data:
                steps.append(embed_data)
        return steps

    def has_active_thread(self, user: discord.Member) -> bool:
        thread_id = self.active_guide_threads.get(user.id)
        if not thread_id:
            return False
        if user.guild.get_thread(thread_id):
            return True
        else:
            self.active_guide_threads.pop(user.id, None)
            return False

    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        user_id_to_remove = next((user_id for user_id, t_id in self.active_guide_threads.items() if t_id == thread.id), None)
        if user_id_to_remove:
            self.active_guide_threads.pop(user_id_to_remove, None)
            logger.info(f"안내 스레드(ID: {thread.id})가 삭제되어 추적 목록에서 제거되었습니다.")

    async def regenerate_panel(self, channel: discord.TextChannel, panel_key: str = "panel_user_guide") -> bool:
        base_panel_key = panel_key.replace("panel_", "")
        embed_key = panel_key
        try:
            panel_info = get_panel_id(base_panel_key)
            if panel_info and (old_id := panel_info.get('message_id')):
                try:
                    await (await channel.fetch_message(old_id)).delete()
                except (discord.NotFound, discord.Forbidden):
                    pass
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
