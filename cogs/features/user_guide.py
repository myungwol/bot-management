# cogs/features/user_guide.py

import discord
from discord import ui
from discord.ext import commands
import logging
from typing import Optional, Dict, List, Any
import asyncio
from datetime import datetime

from utils.database import get_id, save_panel_id, get_panel_id, get_embed_from_db, get_panel_components_from_db, get_config
from utils.helpers import format_embed_from_db

logger = logging.getLogger(__name__)

# --- Forward declaration for type hinting ---
class InteractiveGuideView:
    pass

class IntroductionFormModal(ui.Modal, title="자기소개서 작성"):
    name = ui.TextInput(label="이름", placeholder="마을에서 사용할 이름을 알려주세요.", required=True)
    birth_year = ui.TextInput(label="출생년도 (YY)", placeholder="예: 98, 05 (2자리로 입력)", required=True, min_length=2, max_length=2)
    gender = ui.TextInput(label="성별", placeholder="성별을 알려주세요.", required=True, max_length=10)
    join_path = ui.TextInput(label="가입 경로", placeholder="어떻게 우리 마을을 알게 되셨나요?", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, guide_view: InteractiveGuideView):
        super().__init__()
        self.guide_view = guide_view

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        member = interaction.user

        if self.guide_view.last_confirmation_message_id:
            try: await (await interaction.channel.fetch_message(self.guide_view.last_confirmation_message_id)).delete()
            except discord.NotFound: pass
        if self.guide_view.last_role_message_id:
            try: await (await interaction.channel.fetch_message(self.guide_view.last_role_message_id)).delete()
            except discord.NotFound: pass

        roles_to_add = []
        assigned_role_names = []
        failed_role_names = [] # 역할 부여 실패 시 이름을 저장할 리스트
        current_year = datetime.now().year
        year_of_birth = 0

        # 성별 역할 처리
        gender_text = self.gender.value.strip().lower()
        if any(k in gender_text for k in ['남자', '남성', '남']):
            role_id = get_id("role_info_male")
            if role_id and (role := member.guild.get_role(role_id)): roles_to_add.append(role); assigned_role_names.append(role.name)
            else: failed_role_names.append("남자")
        elif any(k in gender_text for k in ['여자', '여성', '여']):
            role_id = get_id("role_info_female")
            if role_id and (role := member.guild.get_role(role_id)): roles_to_add.append(role); assigned_role_names.append(role.name)
            else: failed_role_names.append("여자")

        # 나이 역할 처리
        try:
            yy = int(self.birth_year.value)
            year_of_birth = (1900 + yy) if yy > (current_year % 100) else (2000 + yy)
            age = current_year - year_of_birth + 1
            age_brackets = get_config("AGE_BRACKET_ROLES", [])
            
            # ▼▼▼▼▼ [핵심 수정 1/3] 역할 부여 실패 시 원인을 기록하는 로직 추가 ▼▼▼▼▼
            target_bracket = None
            for bracket in age_brackets:
                if bracket['min_age'] <= age <= bracket['max_age']:
                    target_bracket = bracket
                    break
            
            if target_bracket:
                role_id = get_id(target_bracket['key'])
                if role_id and (role := member.guild.get_role(role_id)):
                    roles_to_add.append(role)
                    assigned_role_names.append(role.name)
                else:
                    # 역할을 찾지 못했을 때 실패 목록에 추가
                    age_role_map = {"role_age_10s": "10대", "role_age_20s": "20대", "role_age_30s": "30대", "role_age_40s": "40대 이상"}
                    failed_role_names.append(age_role_map.get(target_bracket['key'], "알 수 없는 나이"))
            # ▲▲▲▲▲ [수정 완료] ▲▲▲▲▲
                    
        except ValueError:
            await interaction.followup.send("❌ 출생년도는 2자리 숫자로만 입력해주세요 (예: 99, 01).", ephemeral=True); return
        except Exception as e:
            logger.error(f"나이 역할 처리 중 오류: {e}")

        if roles_to_add:
            try: await member.add_roles(*roles_to_add, reason="유저 안내 자기소개서 작성")
            except discord.Forbidden: await interaction.followup.send("❌ 역할 부여에 실패했습니다. 봇의 권한을 확인해주세요.", ephemeral=True)

        # ▼▼▼▼▼ [핵심 수정 2/3] 확인 메시지에 계산된 나이 대신 원본 입력값을 사용 ▼▼▼▼▼
        confirmation_message = (
            f"{interaction.user.mention}/{self.name.value}/{self.birth_year.value}/"
            f"{self.gender.value}/{self.join_path.value}"
        )
        # ▲▲▲▲▲ [수정 완료] ▲▲▲▲▲
        
        sent_conf_msg = await interaction.channel.send(confirmation_message)
        self.guide_view.last_confirmation_message_id = sent_conf_msg.id

        role_message_content = []
        if assigned_role_names:
            role_message_content.append(f"✅ 자기소개서를 바탕으로 역할이 부여되었습니다: `{'`, `'.join(assigned_role_names)}`")
        if failed_role_names:
            role_message_content.append(f"⚠️ 역할을 찾지 못해 부여에 실패했습니다: `{'`, `'.join(failed_role_names)}`\n(역할 이름이 정확한지 또는 역할 동기화가 되었는지 확인해주세요.)")
        
        if role_message_content:
            sent_role_msg = await interaction.channel.send("\n".join(role_message_content))
            self.guide_view.last_role_message_id = sent_role_msg.id
        else:
            self.guide_view.last_role_message_id = None

        # ▼▼▼▼▼ [핵심 수정 3/3] 마지막 ephemeral 메시지 전송 로직 제거 ▼▼▼▼▼
        # await interaction.followup.send("✅ 자기소개서가 제출/수정 되었습니다!", ephemeral=True)
        # ▲▲▲▲▲ [수정 완료] ▲▲▲▲▲

class InteractiveGuideView(ui.View):
    def __init__(self, cog: 'UserGuide', user: discord.Member, steps_data: List[Dict[str, Any]]):
        super().__init__(timeout=600)
        self.cog = cog; self.user = user; self.steps_data = steps_data
        self.current_step = 0; self.message: Optional[discord.Message] = None
        self.last_confirmation_message_id: Optional[int] = None
        self.last_role_message_id: Optional[int] = None
        self._update_buttons()
    async def interaction_check(self, i: discord.Interaction) -> bool:
        if i.user.id != self.user.id:
            await i.response.send_message("❌ 다른 사람의 안내 가이드 버튼은 누를 수 없습니다.", ephemeral=True); return False
        return True
    def _get_current_embed(self) -> discord.Embed:
        return format_embed_from_db(self.steps_data[self.current_step], member_name=self.user.display_name)
    def _update_buttons(self):
        self.clear_items()
        is_first, is_last = self.current_step == 0, self.current_step == len(self.steps_data) - 1
        prev = ui.Button(label="◀ 이전", style=discord.ButtonStyle.secondary, custom_id="guide_prev", disabled=is_first)
        prev.callback = self.go_previous; self.add_item(prev)
        if is_last:
            intro = ui.Button(label="자기소개서 작성하기", style=discord.ButtonStyle.success, emoji="📝", custom_id="guide_intro_form")
            intro.callback = self.open_intro_form; self.add_item(intro)
        else:
            next_b = ui.Button(label="다음 ▶", style=discord.ButtonStyle.primary, custom_id="guide_next")
            next_b.callback = self.go_next; self.add_item(next_b)
    async def go_previous(self, i: discord.Interaction):
        if self.current_step > 0: self.current_step -= 1
        self._update_buttons(); await i.response.edit_message(embed=self._get_current_embed(), view=self)
    async def go_next(self, i: discord.Interaction):
        if self.current_step < len(self.steps_data) - 1: self.current_step += 1
        self._update_buttons(); await i.response.edit_message(embed=self._get_current_embed(), view=self)
    async def open_intro_form(self, i: discord.Interaction): await i.response.send_modal(IntroductionFormModal(self))
    async def on_timeout(self):
        if self.message:
            for item in self.children: item.disabled = True
            try: await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException): pass
# (이 아래의 UserGuidePanelView, UserGuide Cog 클래스는 이전 답변과 동일하게 유지됩니다)
class UserGuidePanelView(ui.View):
    def __init__(self, cog: 'UserGuide'):
        super().__init__(timeout=None); self.cog = cog
    async def setup_buttons(self):
        self.clear_items()
        comps = await get_panel_components_from_db('user_guide')
        comp = comps[0] if comps else {}
        btn = ui.Button(label=comp.get('label', "안내 시작하기"), style=discord.ButtonStyle.success, emoji=comp.get('emoji', "👋"), custom_id=comp.get('component_key', "start_user_guide"))
        btn.callback = self.start_guide_callback; self.add_item(btn)
    async def start_guide_callback(self, i: discord.Interaction):
        if self.cog.has_active_thread(i.user):
            await i.response.send_message(f"❌ 이미 진행 중인 안내 스레드(<#{self.cog.active_guide_threads.get(i.user.id)}>)가 있습니다.", ephemeral=True)
            return
        role_id = get_id("role_staff_newbie_helper")
        if not role_id or not (role := i.guild.get_role(role_id)):
            await i.response.send_message("❌ 죄송합니다. 현재 안내를 담당할 스태프 역할이 지정되지 않았습니다.", ephemeral=True)
            return
        await i.response.defer(ephemeral=True)
        try:
            thread = await i.channel.create_thread(name=f"👋ㅣ{i.user.display_name}님의-안내", type=discord.ChannelType.private_thread, reason=f"{i.user.display_name}님의 신규 유저 안내")
            self.cog.active_guide_threads[i.user.id] = thread.id
            steps = await self.cog.get_guide_steps()
            if not steps: raise ValueError("DB에서 안내 가이드 페이지를 불러올 수 없습니다.")
            view = InteractiveGuideView(self.cog, i.user, steps)
            msg = await thread.send(content=f"{i.user.mention} {role.mention}", embed=view._get_current_embed(), view=view, allowed_mentions=discord.AllowedMentions(users=True, roles=True))
            view.message = msg
            fu_msg = await i.followup.send(f"✅ 안내를 위한 비공개 스레드를 생성했습니다: {thread.mention}", ephemeral=True, wait=True)
            await asyncio.sleep(10); await fu_msg.delete()
        except Exception as e:
            self.cog.active_guide_threads.pop(i.user.id, None)
            logger.error(f"유저 안내 스레드 생성 중 오류 발생: {e}", exc_info=True)
            await i.followup.send("❌ 스레드를 생성하는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.", ephemeral=True)
class UserGuide(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot; self.panel_channel_id: Optional[int] = None
        self.view_instance: Optional[UserGuidePanelView] = None
        self.active_guide_threads: Dict[int, int] = {}
        logger.info("UserGuide Cog가 성공적으로 초기화되었습니다.")
    async def cog_load(self): await self.load_configs()
    async def register_persistent_views(self):
        self.view_instance = UserGuidePanelView(self)
        await self.view_instance.setup_buttons()
        self.bot.add_view(self.view_instance)
        logger.info("✅ 신규 유저 안내 시스템의 영구 View가 성공적으로 등록되었습니다.")
    async def load_configs(self):
        self.panel_channel_id = get_id("user_guide_panel_channel_id")
        logger.info("[UserGuide Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")
    async def get_guide_steps(self) -> List[Dict[str, Any]]:
        keys = ["guide_thread_page_1", "guide_thread_page_2", "guide_thread_page_3"]
        return [data for key in keys if (data := await get_embed_from_db(key))]
    def has_active_thread(self, user: discord.Member) -> bool:
        tid = self.active_guide_threads.get(user.id)
        if not tid: return False
        if user.guild.get_thread(tid): return True
        else: self.active_guide_threads.pop(user.id, None); return False
    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        uid = next((uid for uid, tid in self.active_guide_threads.items() if tid == thread.id), None)
        if uid:
            self.active_guide_threads.pop(uid, None)
            logger.info(f"안내 스레드(ID: {thread.id})가 삭제되어 추적 목록에서 제거되었습니다.")
    async def regenerate_panel(self, channel: discord.TextChannel, panel_key: str = "panel_user_guide") -> bool:
        base_key, embed_key = panel_key.replace("panel_", ""), panel_key
        try:
            info = get_panel_id(base_key)
            if info and (old_id := info.get('message_id')):
                try: await (await channel.fetch_message(old_id)).delete()
                except (discord.NotFound, discord.Forbidden): pass
            embed_data = await get_embed_from_db(embed_key)
            if not embed_data:
                logger.warning(f"DB에서 '{embed_key}'를 찾을 수 없어 패널 생성을 건너뜁니다."); return False
            if self.view_instance is None: await self.register_persistent_views()
            await self.view_instance.setup_buttons()
            new_msg = await channel.send(embed=discord.Embed.from_dict(embed_data), view=self.view_instance)
            await save_panel_id(base_key, new_msg.id, channel.id)
            logger.info(f"✅ {panel_key} 패널을 #{channel.name}에 새로 생성했습니다."); return True
        except Exception as e:
            logger.error(f"❌ {panel_key} 패널 재설치 중 오류: {e}", exc_info=True); return False
async def setup(bot: commands.Bot):
    await bot.add_cog(UserGuide(bot))
