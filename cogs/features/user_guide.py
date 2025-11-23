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
from utils.helpers import format_embed_from_db, has_required_roles
from utils.ui_defaults import AGE_ROLE_MAPPING_BY_YEAR

logger = logging.getLogger(__name__)

# --- Forward declaration ---
class GuideThreadView:
    pass

class GuideApprovalView(ui.View):
    def __init__(self, cog: 'UserGuide', target_user_id: int, submitted_data: dict):
        super().__init__(timeout=None)
        self.cog = cog
        self.target_user_id = target_user_id
        self.submitted_data = submitted_data

    # ▼▼▼ [디버깅 추가 1/2] 권한 확인 함수에 로그 추가 ▼▼▼
    async def _check_permission(self, interaction: discord.Interaction) -> bool:
        print("\n" + "="*50)
        print(f"--- [디버깅] 권한 확인 시작: {interaction.user.display_name} ---")
        
        required_keys = [
            "role_staff_team_info", "role_staff_team_newbie",
            "role_staff_leader_info", "role_staff_leader_newbie",
            "role_staff_deputy_manager", "role_staff_general_manager",
            "role_staff_deputy_chief", "role_staff_village_chief"
        ]
        print(f"[디버깅] 필요한 역할 키 목록: {required_keys}")

        # 필요한 역할들의 ID를 DB에서 가져옵니다.
        allowed_role_ids = {get_id(key) for key in required_keys if get_id(key)}
        print(f"[디버깅] DB에서 찾은 필요 역할 ID 목록: {allowed_role_ids}")

        if not allowed_role_ids:
            print("[디버깅] 오류: DB에 필요한 역할이 하나도 설정되지 않았습니다.")
            await interaction.response.send_message("❌ 권한 확인에 필요한 역할이 서버에 설정되지 않았습니다. 관리자에게 문의하세요.", ephemeral=True)
            print("="*50 + "\n")
            return False

        # 버튼을 누른 유저의 역할 ID 목록을 가져옵니다.
        user_role_ids = {role.id for role in interaction.user.roles}
        user_role_names = {role.name for role in interaction.user.roles}
        print(f"[디버깅] 유저가 가진 역할 ID 목록: {user_role_ids}")
        print(f"[디버깅] 유저가 가진 역할 이름 목록: {user_role_names}")

        # 두 목록의 교집합(공통된 역할)을 확인합니다.
        has_permission = not user_role_ids.isdisjoint(allowed_role_ids)
        print(f"[디버깅] 권한 확인 결과: {has_permission}")

        if not has_permission:
            error_message = "❌ 안내팀 또는 뉴비 관리팀 스태프만 수락할 수 있습니다."
            await interaction.response.send_message(error_message, ephemeral=True)
        
        print("="*50 + "\n")
        return has_permission
    # ▲▲▲ [디버깅 추가 완료] ▲▲▲


    async def _send_public_introduction(self, approver: discord.Member, member: discord.Member):
        # (이 함수는 변경 없음)
        # ...
        try:
            channel_id = self.cog.public_intro_channel_id
            if not channel_id:
                logger.warning("공개 자기소개 채널이 설정되지 않아 메시지를 보낼 수 없습니다.")
                return

            channel = self.cog.bot.get_channel(channel_id)
            if not channel:
                logger.warning(f"공개 자기소개 채널(ID: {channel_id})을 찾을 수 없습니다.")
                return
            
            embed_data = await get_embed_from_db("guide_public_introduction")
            if not embed_data:
                logger.warning("DB에서 'guide_public_introduction' 임베드 템플릿을 찾을 수 없습니다.")
                return

            embed = format_embed_from_db(
                embed_data,
                member_mention=member.mention,
                submitted_name=self.submitted_data['name'],
                submitted_birth_year=str(self.submitted_data['birth_year']),
                submitted_gender=self.submitted_data['gender'],
                submitted_join_path=self.submitted_data['join_path'],
                approver_mention=approver.mention
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            
            await channel.send(content=member.mention, embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
        except Exception as e:
            logger.error(f"공개 자기소개 메시지 전송 중 오류 발생: {e}", exc_info=True)


    # ▼▼▼ [디버깅 추가 2/2] approve 함수에 진입 로그 추가 ▼▼▼
    @ui.button(label="수락", style=discord.ButtonStyle.success, emoji="✅", custom_id="guide_approve_button")
    async def approve(self, interaction: discord.Interaction, button: ui.Button):
        # 함수 진입 직후 로그를 남겨, 함수가 호출되었는지 확인
        print("\n>>> 'approve' 함수가 호출되었습니다! 권한 확인을 시작합니다...")
        if not await self._check_permission(interaction):
            print(">>> 권한이 없어 'approve' 함수를 종료합니다.\n")
            return
        print(">>> 권한 확인 통과! 'approve' 로직을 계속 진행합니다.")

        await interaction.response.defer(ephemeral=True)
        
        try:
            member = await interaction.guild.fetch_member(self.target_user_id)
        except discord.NotFound:
            await interaction.followup.send("❌ 대상 유저를 찾을 수 없습니다. 서버를 나간 것 같습니다.", ephemeral=True)
            return

        try:
            print("\n" + "="*50)
            print(f"--- [디버깅 시작] {member.display_name} 역할 업데이트 ---")

            guest_rid = get_id("role_guest")
            print(f"[디버깅 1] 제거할 '해변' 역할 ID: {guest_rid}")

            current_role_names = [r.name for r in member.roles]
            print(f"[디버깅 2] 수정 전 역할 목록 ({len(current_role_names)}개): {current_role_names}")

            roles_to_keep = [role for role in member.roles if role.id != guest_rid]
            print(f"[디버깅 3] '해변' 제외 후 유지할 역할 목록 ({len(roles_to_keep)}개): {[r.name for r in roles_to_keep]}")
            
            new_role_ids_to_add = [
                get_id("role_resident_rookie"),
                get_id("role_resident_regular")
            ]
            gender_text = self.submitted_data['gender'].strip().lower()
            if any(k in gender_text for k in ['남자', '남성', '남']):
                new_role_ids_to_add.append(get_id("role_info_male"))
            elif any(k in gender_text for k in ['여자', '여성', '여']):
                new_role_ids_to_add.append(get_id("role_info_female"))

            birth_year = self.submitted_data['birth_year']
            year_mapping = next((item for item in AGE_ROLE_MAPPING_BY_YEAR if item["year"] == birth_year), None)
            if year_mapping:
                new_role_ids_to_add.append(get_id(year_mapping['key']))
            
            print(f"[디버깅 4] 새로 추가할 역할 ID 목록: {new_role_ids_to_add}")

            final_roles = roles_to_keep
            for role_id in new_role_ids_to_add:
                if role_id and (role := interaction.guild.get_role(role_id)):
                    final_roles.append(role)
            final_roles = list(dict.fromkeys(final_roles))
            
            final_role_names = [r.name for r in final_roles]
            print(f"[디버깅 5] 최종 적용될 역할 목록 ({len(final_role_names)}개): {final_role_names}")

            final_nickname = await self.cog.bot.get_cog("PrefixManager").get_final_nickname(
                member, base_name=self.submitted_data['name']
            )
            print(f"[디버깅 6] 최종 적용될 닉네임: {final_nickname}")

            print("[디버깅 7] member.edit() 실행 직전...")
            await member.edit(
                nick=final_nickname,
                roles=final_roles,
                reason="안내 가이드 승인"
            )
            print("[디버깅 8] member.edit() 실행 완료!")
            print("="*50 + "\n")
            # ▲▲▲ [디버깅 로그 완료] ▲▲▲
        except discord.Forbidden:
            logger.error(f"역할/닉네임 업데이트 실패(Forbidden): {member.display_name}")
            await interaction.followup.send("❌ 역할/닉네임 업데이트에 실패했습니다. 봇의 역할이 대상 역할들보다 높은지 확인해주세요.", ephemeral=True)
            return
        except Exception as e:
            logger.error(f"역할/닉네임 업데이트 중 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 역할/닉네임 업데이트 중 알 수 없는 오류가 발생했습니다.", ephemeral=True)
            return

        await self._send_public_introduction(interaction.user, member)

        button.disabled = True
        button.label = "승인 완료"
        
        original_embed = interaction.message.embeds[0]
        original_embed.color = discord.Color.green()
        original_embed.set_footer(text=f"✅ {interaction.user.display_name} 님에 의해 승인됨")
        
        await interaction.message.edit(embed=original_embed, view=self)
        await interaction.followup.send(f"✅ {member.mention}님의 자기소개를 승인했습니다.", ephemeral=True)
        await interaction.channel.send(f"🎉 {member.mention}님의 자기소개가 승인되었습니다! 이제 서버의 모든 채널을 이용할 수 있습니다.")
        
class IntroductionFormModal(ui.Modal, title="자기소개서 작성"):
    # ▼▼▼ [핵심 수정 1/2] 이름 입력 필드의 최대 길이를 8로 변경 ▼▼▼
    name = ui.TextInput(label="이름", placeholder="한글/공백 포함 8자 이하", required=True, max_length=8)
    # ▲▲▲ [수정 완료] ▲▲▲
    
    birth_year_str = ui.TextInput(label="출생년도 (YYYY)", placeholder="예: 1998, 2005 (4자리로 입력)", required=True, min_length=4, max_length=4)
    gender = ui.TextInput(label="성별", placeholder="성별을 알려주세요.", required=True, max_length=10)
    join_path = ui.TextInput(label="가입 경로", placeholder="어떻게 우리 서버를 알게 되셨나요?", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, cog: 'UserGuide'):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # ▼▼▼ [핵심 수정 2/2] 이름 유효성 검사 로직 추가 ▼▼▼
        name_input = self.name.value
        if len(name_input) > 8:
            await interaction.followup.send("❌ 이름은 공백을 포함하여 8자 이하로 입력해주세요.", ephemeral=True)
            return
        
        if not re.match(r"^[가-힣 ]+$", name_input):
            await interaction.followup.send("❌ 이름은 한글과 공백만 사용하여 입력해주세요. (특수문자, 영문, 숫자 불가)", ephemeral=True)
            return
        # ▲▲▲ [수정 완료] ▲▲▲

        try:
            year = int(self.birth_year_str.value)
            current_year = datetime.now().year
            if not (1950 <= year <= current_year - 13):
                await interaction.followup.send("❌ 유효하지 않은 출생년도입니다. (만 13세 이상)", ephemeral=True)
                return
        except ValueError:
            await interaction.followup.send("❌ 출생년도는 4자리 숫자로 입력해주세요.", ephemeral=True)
            return

        submitted_data = {
            "name": name_input.strip(), # .strip()으로 앞뒤 공백 제거
            "birth_year": int(self.birth_year_str.value),
            "gender": self.gender.value,
            "join_path": self.join_path.value
        }
        
        approval_embed = discord.Embed(
            title="📝 자기소개서 제출됨",
            description=f"{interaction.user.mention}님이 자기소개서를 제출했습니다.\n아래 내용을 확인 후 `수락` 버튼을 눌러주세요.",
            color=discord.Color.yellow()
        )
        approval_embed.add_field(name="신청 이름", value=submitted_data['name'], inline=True)
        approval_embed.add_field(name="출생년도", value=self.birth_year_str.value, inline=True)
        approval_embed.add_field(name="성별", value=self.gender.value, inline=True)
        approval_embed.add_field(name="가입 경로", value=self.join_path.value, inline=False)
        approval_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar)
        
        approval_view = GuideApprovalView(self.cog, interaction.user.id, submitted_data)
        
        notify_role_id = get_id("role_notify_guide_approval")
        mention_str = f"<@&{notify_role_id}>" if notify_role_id else "스태프 여러분,"
        
        await interaction.channel.send(
            content=mention_str,
            embed=approval_embed,
            view=approval_view,
            allowed_mentions=discord.AllowedMentions(roles=True)
        )
        await interaction.followup.send("✅ 자기소개서를 제출했습니다. 스태프 확인 후 역할이 지급됩니다.", ephemeral=True)

class GuideThreadView(ui.View):
    def __init__(self, cog: 'UserGuide'):
        super().__init__(timeout=None)
        self.cog = cog

    async def _get_steps_and_page(self, interaction: discord.Interaction):
        steps = await self.cog.get_guide_steps()
        if not interaction.message.embeds: return None, 0
        footer_text = interaction.message.embeds[0].footer.text
        match = re.search(r"(\d+)/(\d+)", footer_text)
        current_page = int(match.group(1)) - 1 if match else 0
        return steps, current_page

    # ▼▼▼ [핵심 수정] 버튼 비활성화 로직 변경 ▼▼▼
    async def _update_view_state(self, new_page: int, total_pages: int):
        prev_button = discord.utils.get(self.children, custom_id="guide_persistent_prev")
        next_button = discord.utils.get(self.children, custom_id="guide_persistent_next")
        intro_button = discord.utils.get(self.children, custom_id="guide_persistent_intro")
        
        if isinstance(prev_button, ui.Button):
            prev_button.disabled = (new_page == 0)
        
        if isinstance(next_button, ui.Button):
            # 경로 인증 페이지(인덱스 2)에서도 비활성화하지 않음
            next_button.disabled = (new_page == total_pages - 1)
            
        if isinstance(intro_button, ui.Button):
            intro_button.disabled = (new_page != total_pages - 1)
    # ▲▲▲ [수정 완료] ▲▲▲

    @ui.button(label="◀ 이전", style=discord.ButtonStyle.secondary, custom_id="guide_persistent_prev")
    async def go_previous(self, interaction: discord.Interaction, button: ui.Button):
        steps, current_page = await self._get_steps_and_page(interaction)
        if not steps or current_page <= 0: return await interaction.response.defer()
        new_page = current_page - 1
        new_embed = format_embed_from_db(steps[new_page], user_mention=interaction.user.mention)
        await self._update_view_state(new_page, len(steps))
        await interaction.response.edit_message(embed=new_embed, view=self)

    @ui.button(label="다음 ▶", style=discord.ButtonStyle.primary, custom_id="guide_persistent_next")
    async def go_next(self, interaction: discord.Interaction, button: ui.Button):
        steps, current_page = await self._get_steps_and_page(interaction)
        if not steps or current_page >= len(steps) - 1: return await interaction.response.defer()
        new_page = current_page + 1
        new_embed = format_embed_from_db(steps[new_page], user_mention=interaction.user.mention)
        await self._update_view_state(new_page, len(steps))
        await interaction.response.edit_message(embed=new_embed, view=self)

    @ui.button(label="자기소개서 작성하기", style=discord.ButtonStyle.success, emoji="📝", custom_id="guide_persistent_intro", disabled=True)
    async def open_intro_form(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(IntroductionFormModal(self.cog))


class UserGuidePanelView(ui.View):
    def __init__(self, cog: 'UserGuide'):
        super().__init__(timeout=None); self.cog = cog
    async def setup_buttons(self):
        self.clear_items(); comps = await get_panel_components_from_db('user_guide')
        comp = comps[0] if comps else {}; btn = ui.Button(label=comp.get('label', "안내 시작하기"), style=discord.ButtonStyle.success, emoji=comp.get('emoji', "👋"), custom_id=comp.get('component_key', "start_user_guide"))
        btn.callback = self.start_guide_callback; self.add_item(btn)
        
    async def start_guide_callback(self, i: discord.Interaction):
        if self.cog.has_active_thread(i.user): 
            await i.response.send_message(f"❌ 이미 진행 중인 안내 스레드(<#{self.cog.active_guide_threads.get(i.user.id)}>)가 있습니다.", ephemeral=True)
            return
        
        await i.response.defer(ephemeral=True)
        try:
            # ▼▼▼ [핵심 수정] '해변' 역할 부여 로직 추가 ▼▼▼
            if (guest_rid := get_id("role_guest")) and (guest_role := i.guild.get_role(guest_rid)):
                if guest_role not in i.user.roles:
                    await i.user.add_roles(guest_role, reason="안내 가이드 시작")
            # ▲▲▲ [수정 완료] ▲▲▲

            thread_name = f"👋ㅣ{i.user.display_name}님의-안내"
            thread = await i.channel.create_thread(name=thread_name, type=discord.ChannelType.private_thread)
            
            self.cog.active_guide_threads[i.user.id] = thread.id
            steps = await self.cog.get_guide_steps()
            if not steps: raise ValueError("DB에서 안내 가이드 페이지를 불러올 수 없습니다.")
            
            guide_view = self.cog.guide_thread_view_instance
            await guide_view._update_view_state(0, len(steps))
            
            initial_embed = format_embed_from_db(steps[0], user_mention=i.user.mention)
            
            await thread.send(
                content=f"{i.user.mention}", 
                embed=initial_embed, 
                view=guide_view, 
                allowed_mentions=discord.AllowedMentions(users=True, roles=False)
            )
            
            fu_msg = await i.followup.send(f"✅ 안내 스레드를 생성했습니다: {thread.mention}", ephemeral=True, wait=True)
            await asyncio.sleep(10)
            await fu_msg.delete()
        except Exception as e:
            self.cog.active_guide_threads.pop(i.user.id, None)
            logger.error(f"유저 안내 스레드 생성 중 오류: {e}", exc_info=True)
            await i.followup.send("❌ 스레드 생성 중 오류가 발생했습니다.", ephemeral=True)


class UserGuide(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_channel_id: Optional[int] = None
        self.public_intro_channel_id: Optional[int] = None
        self.view_instance: Optional[UserGuidePanelView] = None
        self.guide_thread_view_instance: Optional[GuideThreadView] = None
        self.active_guide_threads: Dict[int, int] = {}
        logger.info("UserGuide Cog가 성공적으로 초기화되었습니다.")
        
    async def cog_load(self): 
        await self.load_configs()
        
    async def register_persistent_views(self):
        self.view_instance = UserGuidePanelView(self)
        await self.view_instance.setup_buttons()
        self.bot.add_view(self.view_instance)
        
        self.guide_thread_view_instance = GuideThreadView(self)
        self.bot.add_view(self.guide_thread_view_instance)
        
        self.bot.add_view(GuideApprovalView(self, 0, {}))
        
        logger.info("✅ 신규 유저 안내 시스템의 영구 View 3개가 성공적으로 등록되었습니다.")
        
    async def load_configs(self): 
        self.panel_channel_id = get_id("user_guide_panel_channel_id")
        self.public_intro_channel_id = get_id("introduction_public_channel_id")
        logger.info("[UserGuide Cog] DB로부터 설정을 로드했습니다.")
        
    async def get_guide_steps(self) -> List[Dict[str, Any]]:
        # ▼▼▼ [핵심 수정] 5단계에 맞는 임베드 키 목록으로 변경 ▼▼▼
        keys = ["guide_thread_page_1", "guide_thread_page_2", "guide_thread_page_verification", "guide_thread_page_4", "guide_thread_page_5"]
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
            logger.info(f"안내 스레드(ID: {thread.id})가 삭제되어 목록에서 제거되었습니다.")
            
    async def regenerate_panel(self, channel: discord.TextChannel, panel_key: str = "panel_user_guide") -> bool:
        base_key, embed_key = panel_key.replace("panel_", ""), panel_key
        try:
            if (info := get_panel_id(base_key)) and (old_id := info.get('message_id')):
                try: await (await channel.fetch_message(old_id)).delete()
                except (discord.NotFound, discord.Forbidden): pass
            embed_data = await get_embed_from_db(embed_key)
            if not embed_data: 
                logger.warning(f"DB에서 '{embed_key}'를 찾을 수 없어 패널 생성을 건너뜁니다.")
                return False
            if self.view_instance is None: 
                await self.register_persistent_views()
            await self.view_instance.setup_buttons()
            new_msg = await channel.send(embed=discord.Embed.from_dict(embed_data), view=self.view_instance)
            await save_panel_id(base_key, new_msg.id, channel.id)
            logger.info(f"✅ {panel_key} 패널을 #{channel.name}에 새로 생성했습니다.")
            return True
        except Exception as e: 
            logger.error(f"❌ {panel_key} 패널 재설치 중 오류: {e}", exc_info=True)
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(UserGuide(bot))
