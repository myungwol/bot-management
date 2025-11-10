# cogs/features/user_guide.py

import discord
from discord import ui
from discord.ext import commands
import logging
from typing import Optional, Dict, List, Any
import asyncio
from datetime import datetime
import re

from utils.database import get_id, save_panel_id, get_panel_id, get_embed_from_db, get_panel_components_from_db, get_config
from utils.helpers import format_embed_from_db

logger = logging.getLogger(__name__)

# --- Forward declaration ---
class GuideThreadView:
    pass

class IntroductionFormModal(ui.Modal, title="자기소개서 작성"):
    name = ui.TextInput(label="이름", placeholder="마을에서 사용할 이름을 알려주세요.", required=True)
    birth_year = ui.TextInput(label="출생년도 (YY)", placeholder="예: 98, 05 (2자리로 입력)", required=True, min_length=2, max_length=2)
    gender = ui.TextInput(label="성별", placeholder="성별을 알려주세요.", required=True, max_length=10)
    join_path = ui.TextInput(label="가입 경로", placeholder="어떻게 우리 마을을 알게 되셨나요?", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, guide_view: 'GuideThreadView'):
        super().__init__()
        self.guide_view = guide_view

    # ▼▼▼▼▼ [핵심 수정] on_submit 메소드 전체를 아래 내용으로 교체합니다. ▼▼▼▼▼
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        member = interaction.user

        # 1. 기존에 봇이 보냈던 확인 메시지들 삭제
        if self.guide_view.last_confirmation_message_id:
            try:
                old_msg = await interaction.channel.fetch_message(self.guide_view.last_confirmation_message_id)
                await old_msg.delete()
            except (discord.NotFound, discord.HTTPException): pass
        if self.guide_view.last_role_message_id:
            try:
                old_role_msg = await interaction.channel.fetch_message(self.guide_view.last_role_message_id)
                await old_role_msg.delete()
            except (discord.NotFound, discord.HTTPException): pass

        # 2. 역할 부여 로직 (기존과 동일)
        roles_to_add = []; assigned_role_names = []; failed_role_details = []
        current_year = datetime.now().year
        year_of_birth = 0
        
        gender_text = self.gender.value.strip().lower()
        if any(k in gender_text for k in ['남자', '남성', '남']):
            if (rid := get_id("role_info_male")) and (r := member.guild.get_role(rid)): roles_to_add.append(r); assigned_role_names.append(r.name)
            else: failed_role_details.append("성별(남)")
        elif any(k in gender_text for k in ['여자', '여성', '여']):
            if (rid := get_id("role_info_female")) and (r := member.guild.get_role(rid)): roles_to_add.append(r); assigned_role_names.append(r.name)
            else: failed_role_details.append("성별(여)")
        
        try:
            yy = int(self.birth_year.value)
            year_of_birth = (1900 + yy) if yy > (current_year % 100) else (2000 + yy)
            age = current_year - year_of_birth + 1
            age_brackets = get_config("AGE_BRACKET_ROLES", [])
            if not age_brackets: failed_role_details.append("나이대 역할 설정 없음")
            else:
                target_bracket = next((b for b in age_brackets if b['min_age'] <= age <= b['max_age']), None)
                if target_bracket:
                    if (rid := get_id(target_bracket['key'])) and (r := member.guild.get_role(rid)): roles_to_add.append(r); assigned_role_names.append(r.name)
                    else: failed_role_details.append(f"{age//10 * 10}대")
        except ValueError: await interaction.followup.send("❌ 출생년도는 2자리 숫자로 입력해주세요.", ephemeral=True); return
        
        if roles_to_add: await member.add_roles(*roles_to_add, reason="유저 안내 자기소개서 작성")

        # 3. 새로운 확인 메시지 전송 및 ID 저장
        role_message_content = []
        if assigned_role_names: role_message_content.append(f"✅ 역할이 부여되었습니다: `{'`, `'.join(assigned_role_names)}`")
        if failed_role_details: role_message_content.append(f"⚠️ 일부 역할 부여에 실패했습니다: `{'`, `'.join(failed_role_details)}`")
        
        sent_role_msg = None
        if role_message_content:
            sent_role_msg = await interaction.channel.send("\n".join(role_message_content))
        
        confirmation_message = f"{interaction.user.mention}/{self.name.value}/{self.birth_year.value}/{self.gender.value}/{self.join_path.value}"
        sent_conf_msg = await interaction.channel.send(confirmation_message)

        # View에 새로 생성된 메시지들의 ID를 저장
        self.guide_view.last_role_message_id = sent_role_msg.id if sent_role_msg else None
        self.guide_view.last_confirmation_message_id = sent_conf_msg.id

        # 4. 버튼 제거 로직 삭제됨
    # ▲▲▲▲▲ [수정 완료] ▲▲▲▲▲

class GuideThreadView(ui.View):
    def __init__(self, cog: 'UserGuide'):
        super().__init__(timeout=None)
        self.cog = cog
        # 재제출 시 삭제할 메시지 ID를 저장하기 위한 변수 추가
        self.last_confirmation_message_id: Optional[int] = None
        self.last_role_message_id: Optional[int] = None

    async def _get_steps_and_page(self, interaction: discord.Interaction):
        # ... (이전과 동일)
        steps = await self.cog.get_guide_steps()
        if not interaction.message.embeds: return None, 0, 0
        footer_text = interaction.message.embeds[0].footer.text
        match = re.search(r"(\d+)/(\d+)", footer_text)
        current_page = int(match.group(1)) - 1 if match else 0
        total_pages = len(steps)
        return steps, current_page, total_pages

    @ui.button(label="◀ 이전", style=discord.ButtonStyle.secondary, custom_id="guide_persistent_prev")
    async def go_previous(self, interaction: discord.Interaction, button: ui.Button):
        steps, current_page, total_pages = await self._get_steps_and_page(interaction)
        if not steps or current_page <= 0: return await interaction.response.defer()
        new_page = current_page - 1
        new_embed = format_embed_from_db(steps[new_page], member_name=interaction.user.display_name)
        
        # 버튼 상태 업데이트
        for item in self.children:
            if isinstance(item, ui.Button):
                if item.custom_id == "guide_persistent_prev": item.disabled = (new_page == 0)
                elif item.custom_id == "guide_persistent_next": item.disabled = (new_page == total_pages - 1)
                elif item.custom_id == "guide_persistent_intro": item.disabled = (new_page != total_pages - 1)
        
        await interaction.response.edit_message(embed=new_embed, view=self)

    @ui.button(label="다음 ▶", style=discord.ButtonStyle.primary, custom_id="guide_persistent_next")
    async def go_next(self, interaction: discord.Interaction, button: ui.Button):
        steps, current_page, total_pages = await self._get_steps_and_page(interaction)
        if not steps or current_page >= total_pages - 1: return await interaction.response.defer()
        new_page = current_page + 1
        new_embed = format_embed_from_db(steps[new_page], member_name=interaction.user.display_name)
        
        # 버튼 상태 업데이트
        for item in self.children:
            if isinstance(item, ui.Button):
                if item.custom_id == "guide_persistent_prev": item.disabled = (new_page == 0)
                elif item.custom_id == "guide_persistent_next": item.disabled = (new_page == total_pages - 1)
                elif item.custom_id == "guide_persistent_intro": item.disabled = (new_page != total_pages - 1)

        await interaction.response.edit_message(embed=new_embed, view=self)

    @ui.button(label="자기소개서 작성하기", style=discord.ButtonStyle.success, emoji="📝", custom_id="guide_persistent_intro", disabled=True)
    async def open_intro_form(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(IntroductionFormModal(self))
        
class UserGuidePanelView(ui.View):
    def __init__(self, cog: 'UserGuide'):
        super().__init__(timeout=None); self.cog = cog
    async def setup_buttons(self):
        self.clear_items(); comps = await get_panel_components_from_db('user_guide')
        comp = comps[0] if comps else {}; btn = ui.Button(label=comp.get('label', "안내 시작하기"), style=discord.ButtonStyle.success, emoji=comp.get('emoji', "👋"), custom_id=comp.get('component_key', "start_user_guide"))
        btn.callback = self.start_guide_callback; self.add_item(btn)
    async def start_guide_callback(self, i: discord.Interaction):
        if self.cog.has_active_thread(i.user): await i.response.send_message(f"❌ 이미 진행 중인 안내 스레드(<#{self.cog.active_guide_threads.get(i.user.id)}>)가 있습니다.", ephemeral=True); return
        role_id = get_id("role_staff_newbie_helper");
        if not role_id or not (role := i.guild.get_role(role_id)): await i.response.send_message("❌ 안내 담당 스태프 역할이 지정되지 않았습니다.", ephemeral=True); return
        await i.response.defer(ephemeral=True)
        try:
            thread = await i.channel.create_thread(name=f"👋ㅣ{i.user.display_name}님의-안내", type=discord.ChannelType.private_thread)
            self.cog.active_guide_threads[i.user.id] = thread.id
            steps = await self.cog.get_guide_steps()
            if not steps: raise ValueError("DB에서 안내 가이드 페이지를 불러올 수 없습니다.")
            
            # Cog에 저장된 영구 View 인스턴스를 사용
            guide_view = self.cog.guide_thread_view_instance
            guide_view.children[0].disabled = True # 처음엔 '이전' 비활성화
            guide_view.children[1].disabled = False # '다음' 활성화
            guide_view.children[2].disabled = True # '작성' 비활성화

            initial_embed = format_embed_from_db(steps[0], member_name=i.user.display_name)
            await thread.send(content=f"{i.user.mention} {role.mention}", embed=initial_embed, view=guide_view, allowed_mentions=discord.AllowedMentions(users=True, roles=True))
            
            fu_msg = await i.followup.send(f"✅ 안내 스레드를 생성했습니다: {thread.mention}", ephemeral=True, wait=True)
            await asyncio.sleep(10); await fu_msg.delete()
        except Exception as e:
            self.cog.active_guide_threads.pop(i.user.id, None); logger.error(f"유저 안내 스레드 생성 중 오류: {e}", exc_info=True)
            await i.followup.send("❌ 스레드 생성 중 오류가 발생했습니다.", ephemeral=True)

class UserGuide(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot; self.panel_channel_id: Optional[int] = None
        self.view_instance: Optional[UserGuidePanelView] = None
        self.guide_thread_view_instance: Optional[GuideThreadView] = None # 영구 View 인스턴스 저장
        self.active_guide_threads: Dict[int, int] = {}
        logger.info("UserGuide Cog가 성공적으로 초기화되었습니다.")
    async def cog_load(self): await self.load_configs()
    async def register_persistent_views(self):
        self.view_instance = UserGuidePanelView(self); await self.view_instance.setup_buttons(); self.bot.add_view(self.view_instance)
        # 스레드 내부용 View도 영구적으로 등록
        self.guide_thread_view_instance = GuideThreadView(self); self.bot.add_view(self.guide_thread_view_instance)
        logger.info("✅ 신규 유저 안내 시스템의 영구 View 2개가 성공적으로 등록되었습니다.")
    async def load_configs(self): self.panel_channel_id = get_id("user_guide_panel_channel_id"); logger.info("[UserGuide Cog] DB로부터 설정을 로드했습니다.")
    async def get_guide_steps(self) -> List[Dict[str, Any]]:
        keys = ["guide_thread_page_1", "guide_thread_page_2", "guide_thread_page_3"]; return [data for key in keys if (data := await get_embed_from_db(key))]
    def has_active_thread(self, user: discord.Member) -> bool:
        tid = self.active_guide_threads.get(user.id);
        if not tid: return False
        if user.guild.get_thread(tid): return True
        else: self.active_guide_threads.pop(user.id, None); return False
    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        uid = next((uid for uid, tid in self.active_guide_threads.items() if tid == thread.id), None)
        if uid: self.active_guide_threads.pop(uid, None); logger.info(f"안내 스레드(ID: {thread.id})가 삭제되어 목록에서 제거되었습니다.")
    async def regenerate_panel(self, channel: discord.TextChannel, panel_key: str = "panel_user_guide") -> bool:
        base_key, embed_key = panel_key.replace("panel_", ""), panel_key
        try:
            if (info := get_panel_id(base_key)) and (old_id := info.get('message_id')):
                try: await (await channel.fetch_message(old_id)).delete()
                except (discord.NotFound, discord.Forbidden): pass
            embed_data = await get_embed_from_db(embed_key)
            if not embed_data: logger.warning(f"DB에서 '{embed_key}'를 찾을 수 없어 패널 생성을 건너뜁니다."); return False
            if self.view_instance is None: await self.register_persistent_views()
            await self.view_instance.setup_buttons()
            new_msg = await channel.send(embed=discord.Embed.from_dict(embed_data), view=self.view_instance)
            await save_panel_id(base_key, new_msg.id, channel.id); logger.info(f"✅ {panel_key} 패널을 #{channel.name}에 새로 생성했습니다."); return True
        except Exception as e: logger.error(f"❌ {panel_key} 패널 재설치 중 오류: {e}", exc_info=True); return False

async def setup(bot: commands.Bot):
    await bot.add_cog(UserGuide(bot))
