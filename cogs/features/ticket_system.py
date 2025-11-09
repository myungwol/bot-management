# cogs/features/ticket_system.py
import discord
from discord import ui
from discord.ext import commands
import logging
from typing import Dict, Any, List, Optional, Set, Union
import asyncio

from utils.database import get_id, add_ticket, remove_ticket, get_all_tickets, remove_multiple_tickets, update_ticket_lock_status, get_embed_from_db, save_panel_id, get_panel_id, get_config
from utils.ui_defaults import TICKET_MASTER_ROLES, TICKET_REPORT_ROLES, TICKET_LEADER_ROLES, TICKET_DEPARTMENT_MANAGERS
from utils.helpers import format_embed_from_db

logger = logging.getLogger(__name__)


# --- ▼▼▼ [수정] 관리자 신청 모달을 하나의 클래스로 통합 ▼▼▼ ---
class StaffApplicationModal(ui.Modal, title="관리자 지원서"):
    name = ui.TextInput(label="이름 / 나이 / 성별", placeholder="예: 김마을 / 25 / 남성", required=True)
    experience = ui.TextInput(label="지원 부서 경력 유/무", placeholder="예: 유 (자세히 서술) / 무", style=discord.TextStyle.paragraph, required=True)
    other_server_staff = ui.TextInput(label="현재 타섭 관리진 유/무", placeholder="예: 유 / 무", max_length=2, required=True)
    activity_time = ui.TextInput(label="주 활동 시간대", placeholder="예: 평일 저녁, 주말 오후 등 자유롭게 기재", required=True)
    resolve = ui.TextInput(label="각오", placeholder="마지막으로 관리자로서의 각오를 들려주세요.", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, cog: 'TicketSystem', department_key: str, department_label: str):
        super().__init__()
        self.cog = cog
        self.department_key = department_key
        self.department_label = department_label

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            application_data = {
                "지원 부서": self.department_label,
                "이름 / 나이 / 성별": self.name.value,
                "지원 부서 경력": self.experience.value,
                "현재 타섭 관리진 유/무": self.other_server_staff.value,
                "주 활동 시간대": self.activity_time.value,
                "각오": self.resolve.value,
            }
            
            target_roles = set(self.cog.master_roles)
            await self.cog.create_ticket(
                interaction=interaction,
                ticket_type="application",
                title=f"{interaction.user.display_name}님의 관리자 지원",
                content=application_data,
                selected_roles=target_roles,
                embed_key="embed_ticket_staff_application",
                department_key=self.department_key
            )
        except Exception as e:
            logger.error(f"관리자 지원서 제출 중 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 지원서를 제출하는 중 오류가 발생했습니다.", ephemeral=True)
# --- ▲▲▲ [수정 완료] ---


class ApplicationDepartmentSelectView(ui.View):
    def __init__(self, cog: 'TicketSystem', departments: dict):
        super().__init__(timeout=180)
        self.cog = cog
        self.departments = departments
        self.selected_department_key: Optional[str] = None

        options = [
            discord.SelectOption(
                label=info['label'], value=key,
                description=info['description'], emoji=info.get('emoji')
            ) for key, info in departments.items()
        ]

        class DepartmentSelect(ui.Select):
            async def callback(inner_self, interaction: discord.Interaction):
                outer_self = inner_self.view
                outer_self.selected_department_key = inner_self.values[0]
                outer_self.proceed_button.disabled = False
                await interaction.response.edit_message(view=outer_self)
        
        self.department_select = DepartmentSelect(placeholder="지원할 부서를 선택해주세요...", options=options)
        self.add_item(self.department_select)

        self.proceed_button = ui.Button(label="지원서 작성하기", style=discord.ButtonStyle.success, disabled=True)
        self.proceed_button.callback = self.on_proceed
        self.add_item(self.proceed_button)

    async def on_proceed(self, interaction: discord.Interaction):
        if not self.selected_department_key:
            return
        department_label = self.departments[self.selected_department_key]['label']
        await interaction.response.send_modal(StaffApplicationModal(self.cog, self.selected_department_key, department_label))
        await interaction.delete_original_response()


class InquiryModal(ui.Modal):
    title_input = ui.TextInput(label="제목", placeholder="문의/건의 제목을 입력해주세요.", max_length=100)
    content_input = ui.TextInput(label="내용", placeholder="자세한 내용을 입력해주세요.", style=discord.TextStyle.paragraph, max_length=1000)
    
    def __init__(self, cog: 'TicketSystem', selected_roles: Set[discord.Role]):
        super().__init__(title="문의/건의 내용 입력")
        self.cog, self.selected_roles = cog, selected_roles

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try: await self.cog.create_ticket(interaction, "inquiry", self.title_input.value, self.content_input.value, self.selected_roles)
        except Exception as e: logger.error(f"문의/건의 Modal on_submit에서 오류: {e}", exc_info=True); await interaction.followup.send("❌ 티켓을 만드는 중 오류가 발생했습니다.", ephemeral=True)


class ReportModal(ui.Modal, title="신고 내용 입력"):
    target_user = ui.TextInput(label="신고 대상", placeholder="신고할 상대방의 닉네임#태그를 정확하게 입력해주세요.", max_length=100)
    content_input = ui.TextInput(label="신고 내용", placeholder="자세한 내용을 입력해주세요. (증거 스크린샷은 티켓 생성 후 첨부)", style=discord.TextStyle.paragraph, max_length=1000)
    
    def __init__(self, cog: 'TicketSystem', include_police: bool):
        super().__init__(); self.cog, self.include_police = cog, include_police

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True); target_roles = set(self.cog.report_roles) if self.include_police else set()
        try: await self.cog.create_ticket(interaction, "report", f"신고: {self.target_user.value}", self.content_input.value, target_roles)
        except Exception as e: logger.error(f"신고 Modal on_submit에서 오류: {e}", exc_info=True); await interaction.followup.send("❌ 티켓을 만드는 중 오류가 발생했습니다.", ephemeral=True)


class SpecificLeaderSelect(ui.Select):
    def __init__(self, parent_view: 'InquiryTargetSelectView'):
        self.parent_view = parent_view
        leader_options = [discord.SelectOption(label=role.name, value=str(role.id)) for role in self.parent_view.cog.leader_roles]
        super().__init__(placeholder="담당 팀장을 선택해주세요 (여러 명 선택 가능)...", min_values=1, max_values=len(leader_options) if leader_options else 1, options=leader_options, disabled=not leader_options)
    async def callback(self, interaction: discord.Interaction): self.parent_view.selected_roles = {interaction.guild.get_role(int(role_id)) for role_id in self.values}; await interaction.response.defer()


class InquiryTargetSelectView(ui.View):
    # ▼▼▼ [수정 1/2] __init__ 함수를 교체 ▼▼▼
    def __init__(self, cog: 'TicketSystem'):
        super().__init__(timeout=180)
        self.cog = cog
        self.selected_roles: Set[discord.Role] = set()

        # 새로운 옵션을 포함하여 Select 메뉴를 생성합니다.
        self.target_select = ui.Select(
            placeholder="문의할 대상을 선택해주세요...",
            options=[
                discord.SelectOption(label="대표/부대표에게", value="master", emoji="🧩"),
                discord.SelectOption(label="특정 부서 팀장에게", value="specific", emoji="👤"),
                discord.SelectOption(label="모든 팀장에게", value="all_leaders", emoji="👥"),
                # 새로운 옵션 추가
                discord.SelectOption(label="모든 부서 관리자에게", value="all_managers", emoji="🏢")
            ]
        )
        self.target_select.callback = self.select_target_callback
        self.add_item(self.target_select)

        self.proceed_button = ui.Button(label="내용 입력하기", style=discord.ButtonStyle.success, row=4)
        self.proceed_button.callback = self.proceed_callback
        self.add_item(self.proceed_button)

    # ▼▼▼ [수정 2/2] select_target_callback 함수를 교체 ▼▼▼
    async def select_target_callback(self, interaction: discord.Interaction, select: ui.Select):
        target_type = select.values[0]
        
        # View를 재구성하기 위해 아이템들을 정리합니다.
        self.clear_items()
        self.add_item(self.target_select) # 메인 선택 메뉴는 유지

        if target_type == "master":
            self.selected_roles = set(self.cog.master_roles)
        elif target_type == "all_leaders":
            self.selected_roles = set(self.cog.leader_roles)
        elif target_type == "all_managers": # 새로운 옵션에 대한 처리 추가
            self.selected_roles = set(self.cog.department_manager_roles)
        elif target_type == "specific":
            self.selected_roles = set()
            # '특정 부서 팀장' 선택 시, 팀장 선택 메뉴 추가
            leader_select = SpecificLeaderSelect(self)
            if not leader_select.options:
                await interaction.response.send_message("❌ 현재 문의 가능한 팀장 역할이 설정되지 않았습니다.", ephemeral=True)
                return
            self.add_item(leader_select)

        self.add_item(self.proceed_button) # 내용 입력 버튼 다시 추가
        await interaction.response.edit_message(view=self)


class ReportTargetSelectView(ui.View):
    def __init__(self, cog: 'TicketSystem'):
        super().__init__(timeout=180)
        self.cog = cog

    # ▼▼▼ [수정 후] 아래 두 함수로 교체하세요 ▼▼▼
    @ui.button(label="✅ 포장 관리팀 포함하기", style=discord.ButtonStyle.success)
    async def include_police(self, interaction: discord.Interaction, button: ui.Button):
        # self 대신 self.cog를 전달하도록 수정
        await interaction.response.send_modal(ReportModal(self.cog, include_police=True))
        await interaction.delete_original_response()

    @ui.button(label="❌ 포장 관리팀 제외하기", style=discord.ButtonStyle.danger)
    async def exclude_police(self, interaction: discord.Interaction, button: ui.Button):
        # self 대신 self.cog를 전달하도록 수정
        await interaction.response.send_modal(ReportModal(self.cog, include_police=False))
        await interaction.delete_original_response()
    # ▲▲▲ [수정 후] 완료 ▲▲▲


class TicketControlView(ui.View):
    # ... (이하 모든 다른 클래스들은 기존과 동일하게 유지) ...
    def __init__(self, cog: 'TicketSystem', ticket_type: str, is_locked: bool = False):
        super().__init__(timeout=None); self.cog = cog; self.ticket_type = ticket_type
        lock_button = ui.Button(label="잠금 해제" if is_locked else "잠그기", style=discord.ButtonStyle.success if is_locked else discord.ButtonStyle.secondary, emoji="🔓" if is_locked else "🔒", custom_id="ticket_toggle_lock")
        delete_button = ui.Button(label="삭제", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="ticket_delete")
        lock_button.callback = self.toggle_lock; delete_button.callback = self.delete; self.add_item(lock_button); self.add_item(delete_button)
    async def _check_master_permission(self, interaction: discord.Interaction) -> bool: return isinstance(interaction.user, discord.Member) and any(role in interaction.user.roles for role in self.cog.master_roles)
    async def _check_handler_permission(self, interaction: discord.Interaction, ticket_type: str) -> bool: return isinstance(interaction.user, discord.Member) and any(role in interaction.user.roles for role in (self.cog.report_roles if ticket_type == "report" else self.cog.leader_roles))
    async def toggle_lock(self, interaction: discord.Interaction):
        can_lock = await self._check_master_permission(interaction) or (self.ticket_type in ["report", "inquiry"] and await self._check_handler_permission(interaction, self.ticket_type))
        if not can_lock: return await interaction.response.send_message("❌ 이 티켓을 조작할 권한이 없습니다.", ephemeral=True)
        thread = interaction.channel
        if not isinstance(thread, discord.Thread) or not (ticket_info := self.cog.tickets.get(thread.id)): return await interaction.response.send_message("❌ 이 티켓의 정보를 찾을 수 없습니다.", ephemeral=True)
        owner = interaction.guild.get_member(ticket_info.get("owner_id")); is_currently_locked = ticket_info.get("is_locked", False); await interaction.response.defer()
        try:
            if is_currently_locked:
                if owner: await thread.add_user(owner); await update_ticket_lock_status(thread.id, False); self.cog.tickets[thread.id]['is_locked'] = False
                await interaction.followup.send(f"✅ 티켓의 잠금을 해제했습니다.", ephemeral=True); new_view = TicketControlView(self.cog, self.ticket_type, is_locked=False)
            else:
                all_admin_roles = set(self.cog.master_roles + self.cog.leader_roles + self.cog.report_roles); members_to_remove = [m for m in await thread.fetch_members() if not m.bot and all_admin_roles.isdisjoint({r.id for r in m.roles})]
                for member in members_to_remove: await thread.remove_user(member)
                await update_ticket_lock_status(thread.id, True); self.cog.tickets[thread.id]['is_locked'] = True
                await interaction.followup.send(f"✅ 관리자 외의 멤버를 제외하고 티켓을 잠갔습니다.", ephemeral=True); new_view = TicketControlView(self.cog, self.ticket_type, is_locked=True)
            await (await interaction.original_response()).edit(view=new_view)
        except Exception as e: logger.error(f"티켓 잠금/해제 중 오류 발생: {e}", exc_info=True)
    async def delete(self, interaction: discord.Interaction):
        if not await self._check_master_permission(interaction): return await interaction.response.send_message("❌ `대표`, `부대표`만 이 버튼을 사용할 수 있습니다.", ephemeral=True)
        await interaction.response.send_message(f"✅ 5초 후에 이 티켓을 삭제합니다."); await asyncio.sleep(5);
        try: await interaction.channel.delete(reason=f"{interaction.user.display_name}이(가) 삭제")
        except discord.NotFound: pass


class MainTicketPanelView(ui.View):
    # ... (기존과 동일) ...
    def __init__(self, cog: 'TicketSystem'):
        super().__init__(timeout=None)
        self.cog = cog
    @ui.button(label="문의/건의", style=discord.ButtonStyle.primary, emoji="📨", custom_id="ticket_create_inquiry")
    async def inquiry(self, interaction: discord.Interaction, button: ui.Button):
        if self.cog.has_open_ticket(interaction.user, "inquiry"): return await interaction.response.send_message("❌ 이미 참여 중인 문의/건의 티켓이 있습니다.", ephemeral=True)
        await interaction.response.send_message("문의할 대상을 선택해주세요.", view=InquiryTargetSelectView(self.cog), ephemeral=True)
    @ui.button(label="신고", style=discord.ButtonStyle.danger, emoji="🚨", custom_id="ticket_create_report")
    async def report(self, interaction: discord.Interaction, button: ui.Button):
        if self.cog.has_open_ticket(interaction.user, "report"): return await interaction.response.send_message("❌ 이미 참여 중인 신고 티켓이 있습니다.", ephemeral=True)
        await interaction.response.send_message("이 신고에 `포장 관리팀`을 포함하시겠습니까?", view=ReportTargetSelectView(self.cog), ephemeral=True)
    @ui.button(label="관리자 신청", style=discord.ButtonStyle.success, emoji="✨", custom_id="ticket_create_application")
    async def application(self, interaction: discord.Interaction, button: ui.Button):
        if self.cog.has_open_ticket(interaction.user, "application"): return await interaction.response.send_message("❌ 이미 제출한 지원서가 처리 대기 중입니다.", ephemeral=True)
        departments = get_config("TICKET_APPLICATION_DEPARTMENTS", {})
        if not departments: return await interaction.response.send_message("❌ 현재 관리자 신청이 불가능합니다. 부서 정보를 불러올 수 없습니다.", ephemeral=True)
        view = ApplicationDepartmentSelectView(self.cog, departments)
        await interaction.response.send_message("어떤 부서에 지원하시겠습니까?", view=view, ephemeral=True)


class TicketSystem(commands.Cog):
    # ▼▼▼ [수정] __init__ 과 load_configs 함수를 교체 ▼▼▼
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tickets: Dict[int, Dict] = {}
        self.master_roles: List[discord.Role] = []
        self.report_roles: List[discord.Role] = []
        self.leader_roles: List[discord.Role] = []
        # '모든 부서 관리자' 역할을 저장할 리스트 추가
        self.department_manager_roles: List[discord.Role] = []
        self.guild: Optional[discord.Guild] = None
        self.view_instance: Optional[MainTicketPanelView] = None
        self.departments: Dict[str, Any] = {}
        logger.info("TicketSystem Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        # 순서 변경: Cog 로드 시 바로 설정 로드
        await self.load_configs()
        await self.register_persistent_views()
        self.bot.loop.create_task(self.sync_tickets_from_db())
    async def register_persistent_views(self): self.view_instance = MainTicketPanelView(self); self.bot.add_view(self.view_instance); logger.info("✅ 통합 티켓 시스템의 영구 View가 성공적으로 등록되었습니다.")
    async def load_configs(self):
        self.departments = get_config("TICKET_APPLICATION_DEPARTMENTS", {})
        panel_channel_id = get_id("ticket_main_panel_channel_id")
        if panel_channel_id and (channel := self.bot.get_channel(panel_channel_id)):
            self.guild = channel.guild
        
        if self.guild:
            self.master_roles = [role for key in TICKET_MASTER_ROLES if (role_id := get_id(key)) and (role := self.guild.get_role(role_id))]
            self.report_roles = [role for key in TICKET_REPORT_ROLES if (role_id := get_id(key)) and (role := self.guild.get_role(role_id))]
            self.leader_roles = [role for key in TICKET_LEADER_ROLES if (role_id := get_id(key)) and (role := self.guild.get_role(role_id))]
            # 새로 추가한 역할 그룹 로드
            self.department_manager_roles = [role for key in TICKET_DEPARTMENT_MANAGERS if (role_id := get_id(key)) and (role := self.guild.get_role(role_id))]
            
            logger.info(f"[TicketSystem] 역할 및 부서 정보 로드 완료 (부서 관리자: {len(self.department_manager_roles)}개)")
        else:
            logger.warning("[TicketSystem] 티켓 패널 채널이 설정되지 않아 길드 정보를 불러올 수 없습니다.")
    # ▲▲▲ [수정 완료] ▲▲▲
    def has_open_ticket(self, user: discord.Member, ticket_type: str):
        for thread_id, ticket_info in self.tickets.items():
            if ticket_info.get("owner_id") == user.id and ticket_info.get("ticket_type") == ticket_type and self.guild and self.guild.get_thread(thread_id): return True
        return False
    async def sync_tickets_from_db(self):
        await self.bot.wait_until_ready(); db_tickets = await get_all_tickets()
        if not db_tickets: return
        zombie_ids = [td['thread_id'] for td in db_tickets if not (self.guild and self.guild.get_thread(td['thread_id']))]
        for td in db_tickets:
            if td['thread_id'] not in zombie_ids:
                self.tickets[td['thread_id']] = td; self.bot.add_view(TicketControlView(self, td.get("ticket_type"), td.get("is_locked", False)))
        if zombie_ids: await remove_multiple_tickets(zombie_ids)
        logger.info(f"[TicketSystem] 기존 티켓 동기화 완료: {len(self.tickets)}개")
    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str, title: str, content: Union[str, Dict], selected_roles: Set[discord.Role], embed_key: Optional[str] = None, department_key: Optional[str] = None):
        thread: Optional[discord.Thread] = None
        try:
            panel_channel = interaction.channel
            type_map = {"inquiry": "문의", "report": "신고", "application": "지원"}
            thread_name = f"[{type_map.get(ticket_type, '티켓')}] {title}"
            thread = await panel_channel.create_thread(name=thread_name, type=discord.ChannelType.private_thread)
            
            await add_ticket(thread.id, interaction.user.id, interaction.guild.id, ticket_type)
            self.tickets[thread.id] = {"thread_id": thread.id, "owner_id": interaction.user.id, "ticket_type": ticket_type, "is_locked": False}
            
            embed_to_send = None
            final_roles_to_mention = set(self.master_roles)

            if ticket_type == "application" and isinstance(content, dict) and department_key:
                departments = get_config("TICKET_APPLICATION_DEPARTMENTS", {})
                dept_info = departments.get(department_key)
                embed_data = await get_embed_from_db(embed_key)
                if embed_data and dept_info:
                    embed_to_send = format_embed_from_db(embed_data, member_mention=interaction.user.mention)
                    embed_to_send.set_author(name=f"{interaction.user.display_name} ({interaction.user.id})", icon_url=interaction.user.display_avatar.url)
                    embed_to_send.timestamp = discord.utils.utcnow()
                    for name, value in content.items():
                        embed_to_send.add_field(name=name, value=value or "내용 없음", inline=False)
                    
                    # --- ▼▼▼ [핵심 수정] 팀원 역할 멘션 부분을 주석 처리합니다. ▼▼▼ ---
                    # if team_role_id := get_id(dept_info['team_role_key']):
                    #     if team_role := interaction.guild.get_role(team_role_id): 
                    #         selected_roles.add(team_role)
                    # --- ▲▲▲ [수정 완료] ▲▲▲ ---
                        
                    # 팀장 역할은 계속 멘션하도록 유지합니다.
                    if leader_role_id := get_id(dept_info['leader_role_key']):
                        if leader_role := interaction.guild.get_role(leader_role_id): 
                            selected_roles.add(leader_role)

            elif ticket_type in ["inquiry", "report"]:
                color = {"inquiry": 0x3498DB, "report": 0xE74C3C}
                embed_to_send = discord.Embed(title=title, description=str(content), color=color.get(ticket_type, 0x99AAB5))
                embed_to_send.set_author(name=f"{interaction.user.display_name} 님의 {type_map.get(ticket_type)}", icon_url=interaction.user.display_avatar.url)
                embed_to_send.timestamp = discord.utils.utcnow()

            await thread.send(embed=embed_to_send)
            
            final_roles_to_mention.update(selected_roles)
            mention_string = ' '.join(role.mention for role in final_roles_to_mention if role)
            control_view = TicketControlView(self, ticket_type, is_locked=False)
            await thread.send(f"{interaction.user.mention} {mention_string}\n**[티켓 관리 패널]**", view=control_view, allowed_mentions=discord.AllowedMentions(users=True, roles=True))
            
            message = await interaction.followup.send(f"✅ 비공개 티켓을 만들었습니다: {thread.mention}", ephemeral=True, wait=True)
            await asyncio.sleep(5)
            await message.delete()

        except Exception as e:
            logger.error(f"티켓 생성 중 오류 발생: {e}", exc_info=True)
            if thread: 
                await thread.delete(reason="생성 과정 오류로 인한 자동 삭제")
            if interaction.response.is_done(): 
                await interaction.followup.send("❌ 티켓을 만드는 중 오류가 발생했습니다.", ephemeral=True)
    # ▲▲▲ [수정 완료] ▲▲▲
    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        if thread.id in self.tickets: self.tickets.pop(thread.id, None); await remove_ticket(thread.id)
    async def regenerate_panel(self, channel: discord.TextChannel, panel_key: str = "panel_ticket_main") -> bool:
        if not isinstance(channel, discord.TextChannel): return False
        base_panel_key = panel_key.replace("panel_", ""); embed_key = panel_key
        try:
            panel_info = get_panel_id(base_panel_key)
            if panel_info and (old_id := panel_info.get('message_id')):
                try: await (await channel.fetch_message(old_id)).delete()
                except (discord.NotFound, discord.Forbidden): pass
            embed_data = await get_embed_from_db(embed_key)
            if not embed_data: logger.error(f"DB에서 '{embed_key}' 임베드를 찾을 수 없어 패널 생성을 중단합니다."); return False
            new_message = await channel.send(embed=discord.Embed.from_dict(embed_data), view=self.view_instance)
            await save_panel_id(base_panel_key, new_message.id, channel.id)
            logger.info(f"✅ '{panel_key}' 패널을 #{channel.name} 채널에 성공적으로 새로 생성했습니다."); return True
        except Exception as e: logger.error(f"❌ '{panel_key}' 패널 처리 중 예기치 않은 오류 발생: {e}", exc_info=True); return False

async def setup(bot: commands.Bot):
    await bot.add_cog(TicketSystem(bot))
