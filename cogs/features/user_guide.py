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


# Modal은 독립적으로 유지
class IntroductionFormModal(ui.Modal, title="자기소개서 작성"):
    name = ui.TextInput(label="이름", placeholder="한글/공백 포함 8자 이하", required=True, max_length=8)
    birth_year_str = ui.TextInput(label="출생년도 (YYYY)", placeholder="예: 1998, 2005", required=True, min_length=4, max_length=4)
    gender = ui.TextInput(label="성별", placeholder="성별을 알려주세요.", required=True, max_length=10)
    join_path = ui.TextInput(label="가입 경로", placeholder="어떻게 우리 서버를 알게 되셨나요?", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, cog: 'UserGuide'):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        name_input = self.name.value
        if len(name_input) > 8 or not re.match(r"^[가-힣 ]+$", name_input):
            return await interaction.followup.send("❌ 이름은 한글과 공백만 사용하여 8자 이하로 입력해주세요.", ephemeral=True)
        try:
            year = int(self.birth_year_str.value)
            if not (1950 <= year <= datetime.now().year - 13):
                return await interaction.followup.send("❌ 유효하지 않은 출생년도입니다. (만 13세 이상)", ephemeral=True)
        except ValueError:
            return await interaction.followup.send("❌ 출생년도는 4자리 숫자로 입력해주세요.", ephemeral=True)

        approval_embed = discord.Embed(title="📝 자기소개서 제출됨", description=f"{interaction.user.mention}님이 자기소개서를 제출했습니다.\n아래 내용을 확인 후 `수락` 버튼을 눌러주세요.", color=discord.Color.yellow())
        approval_embed.add_field(name="신청 이름", value=name_input.strip(), inline=True)
        approval_embed.add_field(name="출생년도", value=self.birth_year_str.value, inline=True)
        approval_embed.add_field(name="성별", value=self.gender.value, inline=True)
        approval_embed.add_field(name="가입 경로", value=self.join_path.value, inline=False)
        approval_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar)
        
        notify_role_id = get_id("role_notify_guide_approval")
        mention_str = f"<@&{notify_role_id}>" if notify_role_id else "스태프 여러분,"
        
        await interaction.channel.send(content=mention_str, embed=approval_embed, view=self.cog.approval_view, allowed_mentions=discord.AllowedMentions(roles=True))
        await interaction.followup.send("✅ 자기소개서를 제출했습니다. 스태프 확인 후 역할이 지급됩니다.", ephemeral=True)


class UserGuide(commands.Cog):
    class GuideApprovalView(ui.View):
        def __init__(self, outer_cog: 'UserGuide'):
            super().__init__(timeout=None)
            self.cog = outer_cog

        @ui.button(label="수락", style=discord.ButtonStyle.success, emoji="✅", custom_id="guide_approve_button")
        async def approve(self, interaction: discord.Interaction, button: ui.Button):
            required_keys = ["role_staff_team_info", "role_staff_team_newbie", "role_staff_leader_info", "role_staff_leader_newbie", "role_staff_deputy_manager", "role_staff_general_manager", "role_staff_deputy_chief", "role_staff_village_chief"]
            if not await has_required_roles(interaction, required_keys, "❌ 안내팀 또는 뉴비 관리팀 스태프만 수락할 수 있습니다."):
                return

            await interaction.response.defer(ephemeral=True)
            embed = interaction.message.embeds[0]
            match = re.search(r"<@!?(\d+)>", embed.description)
            if not match: return
            target_user_id = int(match.group(1))

            submitted_data = {
                "name": next((f.value for f in embed.fields if f.name == "신청 이름"), ""),
                "birth_year": int(next((f.value for f in embed.fields if f.name == "출생년도"), "0")),
                "gender": next((f.value for f in embed.fields if f.name == "성별"), ""),
                "join_path": next((f.value for f in embed.fields if f.name == "가입 경로"), "")
            }

            try: member = await interaction.guild.fetch_member(target_user_id)
            except discord.NotFound: return await interaction.followup.send("❌ 대상 유저를 찾을 수 없습니다.", ephemeral=True)

            try:
                final_roles = {role for role in member.roles if role.id != get_id("role_guest")}
                new_role_ids = [get_id("role_resident_rookie"), get_id("role_resident_regular")]
                gender = submitted_data.get('gender', '').lower()
                if '남' in gender: new_role_ids.append(get_id("role_info_male"))
                elif '여' in gender: new_role_ids.append(get_id("role_info_female"))
                year_map = next((item for item in AGE_ROLE_MAPPING_BY_YEAR if item["year"] == submitted_data['birth_year']), None)
                if year_map: new_role_ids.append(get_id(year_map['key']))
                for role_id in new_role_ids:
                    if role_id and (role := interaction.guild.get_role(role_id)): final_roles.add(role)
                final_nickname = await self.cog.bot.get_cog("PrefixManager").get_final_nickname(member, base_name=submitted_data['name'])
                await member.edit(nick=final_nickname, roles=list(final_roles), reason="안내 가이드 승인")
            except Exception as e:
                logger.error(f"역할/닉네임 업데이트 중 오류: {e}", exc_info=True)
                return await interaction.followup.send("❌ 역할/닉네임 업데이트 중 오류가 발생했습니다.", ephemeral=True)

            await self.cog.send_public_introduction(interaction.user, member, submitted_data)
            await self.cog.send_main_chat_welcome(member)

            button.disabled, button.label = True, "승인 완료"
            embed.color = discord.Color.green()
            embed.set_footer(text=f"✅ {interaction.user.display_name} 님에 의해 승인됨")
            await interaction.message.edit(embed=embed, view=self)
            await interaction.followup.send(f"✅ {member.mention}님의 자기소개를 승인했습니다.", ephemeral=True)
            if interaction.channel.permissions_for(interaction.guild.me).manage_threads:
                await interaction.channel.send(f"🎉 {member.mention}님의 자기소개가 승인되었습니다! 10초 후 안내 스레드가 닫힙니다.")
                await asyncio.sleep(10)
                await interaction.channel.edit(archived=True, reason="안내 완료")

    class GuideThreadView(ui.View):
        def __init__(self, outer_cog: 'UserGuide'):
            super().__init__(timeout=None)
            self.cog = outer_cog
            
        async def _update_view_state(self, new_page: int, total_pages: int):
            prev, next_btn, intro = [discord.utils.get(self.children, custom_id=cid) for cid in ["guide_persistent_prev", "guide_persistent_next", "guide_persistent_intro"]]
            if prev: prev.disabled = (new_page == 0)
            if next_btn: next_btn.disabled = (new_page >= total_pages - 1)
            if intro: intro.disabled = (new_page != total_pages - 1)
            
        @ui.button(label="◀ 이전", style=discord.ButtonStyle.secondary, custom_id="guide_persistent_prev")
        async def go_previous(self, i: discord.Interaction, b: ui.Button):
            steps = await self.cog.get_guide_steps()
            match = re.search(r"(\d+)/(\d+)", i.message.embeds[0].footer.text)
            page = int(match.group(1)) - 1 if match else 0
            if not steps or page <= 0: return await i.response.defer()
            new_page = page - 1
            await self._update_view_state(new_page, len(steps))
            await i.response.edit_message(embed=format_embed_from_db(steps[new_page], user_mention=i.user.mention), view=self)
            
        @ui.button(label="다음 ▶", style=discord.ButtonStyle.primary, custom_id="guide_persistent_next")
        async def go_next(self, i: discord.Interaction, b: ui.Button):
            steps = await self.cog.get_guide_steps()
            match = re.search(r"(\d+)/(\d+)", i.message.embeds[0].footer.text)
            page = int(match.group(1)) - 1 if match else 0
            if not steps or page >= len(steps) - 1: return await i.response.defer()
            new_page = page + 1
            await self._update_view_state(new_page, len(steps))
            await i.response.edit_message(embed=format_embed_from_db(steps[new_page], user_mention=i.user.mention), view=self)
            
        @ui.button(label="자기소개서 작성하기", style=discord.ButtonStyle.success, emoji="📝", custom_id="guide_persistent_intro", disabled=True)
        async def open_intro_form(self, i: discord.Interaction, b: ui.Button):
            await i.response.send_modal(IntroductionFormModal(self.cog))

    class UserGuidePanelView(ui.View):
        def __init__(self, outer_cog: 'UserGuide'):
            super().__init__(timeout=None)
            self.cog = outer_cog
            
        async def setup_buttons(self):
            self.clear_items()
            comps = await get_panel_components_from_db('user_guide')
            comp = comps[0] if comps else {}
            btn = ui.Button(label=comp.get('label', "안내 시작하기"), style=discord.ButtonStyle.success, emoji=comp.get('emoji', "👋"), custom_id=comp.get('component_key', "start_user_guide"))
            btn.callback = self.start_guide_callback
            self.add_item(btn)
        
        async def start_guide_callback(self, i: discord.Interaction):
            await i.response.defer(ephemeral=True)
            if self.cog.has_active_thread(i.user):
                return await i.followup.send(f"❌ 이미 진행 중인 안내 스레드(<#{self.cog.active_guide_threads.get(i.user.id)}>)가 있습니다.", ephemeral=True)
            try:
                if (guest_rid := get_id("role_guest")) and (guest_role := i.guild.get_role(guest_rid)) and guest_role not in i.user.roles:
                    await i.user.add_roles(guest_role, reason="안내 가이드 시작")
                thread = await i.channel.create_thread(name=f"👋ㅣ{i.user.display_name}님의-안내", type=discord.ChannelType.private_thread)
                self.cog.active_guide_threads[i.user.id] = thread.id
                steps = await self.cog.get_guide_steps()
                if not steps: raise ValueError("DB에서 안내 가이드 페이지를 불러올 수 없습니다.")
                
                guide_view = self.cog.guide_thread_view
                await guide_view._update_view_state(0, len(steps))
                await thread.send(content=f"{i.user.mention}", embed=format_embed_from_db(steps[0], user_mention=i.user.mention), view=guide_view, allowed_mentions=discord.AllowedMentions(users=True, roles=False))
                fu_msg = await i.followup.send(f"✅ 안내 스레드를 생성했습니다: {thread.mention}", ephemeral=True, wait=True)
                await asyncio.sleep(10)
                await fu_msg.delete()
            except Exception as e:
                self.cog.active_guide_threads.pop(i.user.id, None)
                logger.error(f"유저 안내 스레드 생성 중 오류: {e}", exc_info=True)
                await i.followup.send("❌ 스레드 생성 중 오류가 발생했습니다.", ephemeral=True)

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_channel_id: Optional[int] = None
        self.public_intro_channel_id: Optional[int] = None
        self.main_chat_channel_id: Optional[int] = None
        self.active_guide_threads: Dict[int, int] = {}
        self.panel_view = self.UserGuidePanelView(self)
        self.guide_thread_view = self.GuideThreadView(self)
        self.approval_view = self.GuideApprovalView(self)
        logger.info("UserGuide Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self): 
        await self.load_configs()
        
    async def register_persistent_views(self):
        await self.panel_view.setup_buttons()
        self.bot.add_view(self.panel_view)
        self.bot.add_view(self.guide_thread_view)
        self.bot.add_view(self.approval_view)
        logger.info("✅ 신규 유저 안내 시스템의 영구 View 3개가 성공적으로 등록되었습니다.")
        
    async def load_configs(self): 
        self.panel_channel_id = get_id("user_guide_panel_channel_id")
        self.public_intro_channel_id = get_id("introduction_public_channel_id")
        self.main_chat_channel_id = get_id("main_chat_channel_id")
        logger.info("[UserGuide Cog] DB로부터 설정을 로드했습니다.")
        
    async def get_guide_steps(self) -> List[Dict[str, Any]]:
        keys = ["guide_thread_page_1", "guide_thread_page_2", "guide_thread_page_verification", "guide_thread_page_4", "guide_thread_page_5"]
        return [data for key in keys if (data := await get_embed_from_db(key))]
        
    def has_active_thread(self, user: discord.Member) -> bool:
        tid = self.active_guide_threads.get(user.id)
        if not tid: return False
        if user.guild.get_thread(tid): return True
        else: self.active_guide_threads.pop(user.id, None); return False

    async def send_public_introduction(self, approver: discord.Member, member: discord.Member, data: dict):
        if not self.public_intro_channel_id: return
        channel = self.bot.get_channel(self.public_intro_channel_id)
        if not isinstance(channel, discord.TextChannel): return

        embed_data = await get_embed_from_db("guide_public_introduction")
        if not embed_data: return
        
        embed = format_embed_from_db(
            embed_data, 
            member_mention=member.mention, 
            submitted_name=data['name'],
            submitted_birth_year=data['birth_year'],
            submitted_gender=data['gender'],
            submitted_join_path=data['join_path'],
            approver_mention=approver.mention
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(embed=embed)

    # ▼▼▼ [수정] 임베드 대신 일반 메시지로 포맷팅하여 전송하도록 변경 ▼▼▼
    async def send_main_chat_welcome(self, member: discord.Member):
        try:
            if not self.main_chat_channel_id:
                return
            
            channel = self.bot.get_channel(self.main_chat_channel_id)
            if not isinstance(channel, discord.TextChannel):
                return

            # DB에서 ID를 가져오되, 없으면 요청하신 기본값을 사용
            # 1. 역할 채널 ID (notification_role_panel_channel_id 또는 기본값)
            role_channel_id = get_id('notification_role_panel_channel_id') or 1421544728494604369
            
            # 2. 문의 채널 ID (ticket_main_panel_channel_id 또는 기본값)
            inquiry_channel_id = get_id('ticket_main_panel_channel_id') or 1414675593533984860
            
            # 3. 도우미 역할 ID (role_staff_newbie_helper 또는 기본값)
            helper_role_id = get_id('role_staff_newbie_helper') or 1414627893727858770
            
            # 4. 규칙 채널 ID (DB 키가 명확치 않으면 기본값 사용)
            rule_channel_id = 1414675515759005727

            message_content = (
                f"{member.mention}님, 해몽 : 海夢에 오신 걸 환영합니다!\n\n"
                f" <a:1124928221243244644:1416125149782212831> <#{rule_channel_id}> 서버 규칙사항 먼저 숙지해주세요 ! \n\n"
                f" <a:1124928273755938907:1416125162671046736> <#1421544728494604369> 역할은 여기에서 받아주세요 ! \n\n"
                f" <:1367097758577852427:1421788139940479036> 문의 & 건의사항이 있으시다면 <#1414675593533984860> 채널을 사용해주세요 ! \n\n"
                f" <a:1125436475631218769:1416108859956793344> 마지막으로 적응이 힘드시다면 <@&1414627893727858770> 을 멘션 해주세요 ! \n\n"
                f" 해몽에서 즐거운 시간 되시길 바랍니다 ! <:1339999746298740788:1419558757716725760>"
            )

            await channel.send(content=message_content, allowed_mentions=discord.AllowedMentions(users=True, roles=True))
            
        except Exception as e:
            logger.error(f"메인 채팅 환영 메시지 전송 중 오류 발생: {e}", exc_info=True)
    # ▲▲▲ [수정 완료] ▲▲▲

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
            await self.panel_view.setup_buttons()
            new_msg = await channel.send(embed=discord.Embed.from_dict(embed_data), view=self.panel_view)
            await save_panel_id(base_key, new_msg.id, channel.id)
            logger.info(f"✅ {panel_key} 패널을 #{channel.name}에 새로 생성했습니다.")
            return True
        except Exception as e: 
            logger.error(f"❌ {panel_key} 패널 재설치 중 오류: {e}", exc_info=True)
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(UserGuide(bot))
