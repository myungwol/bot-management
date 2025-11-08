# cogs/features/ticket_system.py
import discord
from discord import ui
from discord.ext import commands
import logging
from typing import Dict, Any, List, Optional, Set, Union

from utils.database import get_id, add_ticket, remove_ticket, get_all_tickets, remove_multiple_tickets, update_ticket_lock_status, get_embed_from_db, save_panel_id, get_panel_id, get_config
from utils.ui_defaults import TICKET_MASTER_ROLES, TICKET_REPORT_ROLES, TICKET_LEADER_ROLES
from utils.helpers import format_embed_from_db

logger = logging.getLogger(__name__)


class StaffApplicationModal_Part2(ui.Modal, title="관리자 지원서 (2/2)"):
    exp_details = ui.TextInput(label="◟ 경력 (자세히)", placeholder="경력이 없다면 '없음'으로 기재, 있다면 자세히 서술해주세요.", style=discord.TextStyle.paragraph, required=True)
    other_server_staff = ui.TextInput(label="현재 타섭 관리진 유/무", placeholder="예: 유 / 무", max_length=2, required=True)
    activity_time = ui.TextInput(label="주 활동 시간대", placeholder="예: 평일 저녁, 주말 오후 등 자유롭게 기재", required=True)
    resolve = ui.TextInput(label="각오", placeholder="마지막으로 관리자로서의 각오를 들려주세요.", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, cog: 'TicketSystem', part1_data: Dict, department_key: str):
        super().__init__()
        self.cog = cog
        self.part1_data = part1_data
        self.department_key = department_key

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            full_application_data = self.part1_data.copy()
            full_application_data.update({
                "지원 부서 경력 유/무": self.part1_data.pop("has_exp"),
                "◟ 경력 (자세히)": self.exp_details.value,
                "현재 타섭 관리진 유/무": self.other_server_staff.value,
                "주 활동 시간대": self.activity_time.value,
                "각오": self.resolve.value
            })
            
            target_roles = set(self.cog.master_roles)
            await self.cog.create_ticket(
                interaction=interaction,
                ticket_type="application",
                title=f"{interaction.user.display_name}님의 관리자 지원",
                content=full_application_data,
                selected_roles=target_roles,
                embed_key="embed_ticket_staff_application",
                department_key=self.department_key
            )
        except Exception as e:
            logger.error(f"관리자 지원서 2부 제출 중 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 지원서를 제출하는 중 오류가 발생했습니다.", ephemeral=True)


class StaffApplicationModal_Part1(ui.Modal, title="관리자 지원서 (1/2)"):
    name = ui.TextInput(label="이름", placeholder="신청자의 본명을 입력해주세요.", required=True)
    age = ui.TextInput(label="나이", placeholder="만 나이를 숫자로 입력해주세요.", required=True)
    gender = ui.TextInput(label="성별", placeholder="예: 남성, 여성", required=True)
    has_exp = ui.TextInput(label="지원 부서 경력 유/무", placeholder="예: 유 / 무", max_length=2, required=True)

    def __init__(self, cog: 'TicketSystem', department_key: str):
        super().__init__()
        self.cog = cog
        self.department_key = department_key

    async def on_submit(self, interaction: discord.Interaction):
        part1_data = {
            "이름": self.name.value,
            "나이": self.age.value,
            "성별": self.gender.value,
            "has_exp": self.has_exp.value
        }
        await interaction.response.send_modal(StaffApplicationModal_Part2(self.cog, part1_data, self.department_key))


# --- ▼▼▼ [신규] 관리자 신청 부서 선택 View ▼▼▼ ---
class ApplicationDepartmentSelectView(ui.View):
    def __init__(self, cog: 'TicketSystem'):
        super().__init__(timeout=180)
        self.cog = cog
        self.selected_department_key: Optional[str] = None
        
        # ui_defaults.py에 정의된 부서 정보로 드롭다운 옵션 생성
        departments = get_config("TICKET_APPLICATION_DEPARTMENTS", {})
        options = [
            discord.SelectOption(
                label=info['label'],
                value=key,
                description=info['description'],
                emoji=info.get('emoji')
            ) for key, info in departments.items()
        ]

        self.department_select = ui.Select(placeholder="지원할 부서를 선택해주세요...", options=options)
        self.department_select.callback = self.on_department_select
        self.add_item(self.department_select)

        self.proceed_button = ui.Button(label="지원서 작성하기", style=discord.ButtonStyle.success, disabled=True)
        self.proceed_button.callback = self.on_proceed
        self.add_item(self.proceed_button)

    async def on_department_select(self, interaction: discord.Interaction, select: ui.Select):
        self.selected_department_key = select.values[0]
        self.proceed_button.disabled = False
        await interaction.response.edit_message(view=self)

    async def on_proceed(self, interaction: discord.Interaction, button: ui.Button):
        if not self.selected_department_key:
            return
        await interaction.response.send_modal(StaffApplicationModal_Part1(self.cog, self.selected_department_key))
        await interaction.delete_original_response()
# --- ▲▲▲ [신규] 클래스 추가 완료 ---


class InquiryModal(ui.Modal):
    # ... (이 클래스는 변경 없음) ...
    title_input = ui.TextInput(label="제목", placeholder="문의/건의 제목을 입력해주세요.", max_length=100)
    content_input = ui.TextInput(label="내용", placeholder="자세한 내용을 입력해주세요.", style=discord.TextStyle.paragraph, max_length=1000)
    def __init__(self, cog: 'TicketSystem', selected_roles: Set[discord.Role]):
        super().__init__(title="문의/건의 내용 입력")
        self.cog, self.selected_roles = cog, selected_roles
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            await self.cog.create_ticket(interaction, "inquiry", self.title_input.value, self.content_input.value, self.selected_roles)
        except Exception as e:
            logger.error(f"문의/건의 Modal on_submit에서 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 티켓을 만드는 중 오류가 발생했습니다.", ephemeral=True)


class ReportModal(ui.Modal, title="신고 내용 입력"):
    # ... (이 클래스는 변경 없음) ...
    target_user = ui.TextInput(label="신고 대상", placeholder="신고할 상대방의 닉네임#태그를 정확하게 입력해주세요.", max_length=100)
    content_input = ui.TextInput(label="신고 내용", placeholder="자세한 내용을 입력해주세요. (증거 스크린샷은 티켓 생성 후 첨부)", style=discord.TextStyle.paragraph, max_length=1000)
    def __init__(self, cog: 'TicketSystem', include_police: bool):
        super().__init__()
        self.cog, self.include_police = cog, include_police
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        target_roles = set(self.cog.report_roles) if self.include_police else set()
        try:
            await self.cog.create_ticket(
                interaction, 
                "report", 
                f"신고: {self.target_user.value}", 
                self.content_input.value,
                target_roles
            )
        except Exception as e:
            logger.error(f"신고 Modal on_submit에서 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 티켓을 만드는 중 오류가 발생했습니다.", ephemeral=True)


class SpecificLeaderSelect(ui.Select):
    # ... (이 클래스는 변경 없음) ...
    def __init__(self, parent_view: 'InquiryTargetSelectView'):
        self.parent_view = parent_view
        leader_options = [discord.SelectOption(label=role.name, value=str(role.id)) for role in self.parent_view.cog.leader_roles]
        super().__init__(placeholder="담당 팀장을 선택해주세요 (여러 명 선택 가능)...", min_values=1, max_values=len(leader_options) if leader_options else 1, options=leader_options, disabled=not leader_options)
    async def callback(self, interaction: discord.Interaction):
        self.parent_view.selected_roles = {interaction.guild.get_role(int(role_id)) for role_id in self.values}
        await interaction.response.defer()


class InquiryTargetSelectView(ui.View):
    # ... (이 클래스는 변경 없음) ...
    def __init__(self, cog: 'TicketSystem'):
        super().__init__(timeout=180)
        self.cog = cog
        self.selected_roles: Set[discord.Role] = set()
    @ui.select(placeholder="문의할 대상을 선택해주세요...", options=[discord.SelectOption(label="대표/부대표에게", value="master", emoji="🧩"), discord.SelectOption(label="특정 부서 팀장에게", value="specific", emoji="👤"), discord.SelectOption(label="모든 팀장에게", value="all_leaders", emoji="👥")])
    async def select_target_callback(self, interaction: discord.Interaction, select: ui.Select):
        target_type = select.values[0]
        main_select = self.children[0]
        self.clear_items(); self.add_item(main_select)
        if target_type == "master": self.selected_roles = set(self.cog.master_roles)
        elif target_type == "all_leaders": self.selected_roles = set(self.cog.leader_roles)
        elif target_type == "specific": self.selected_roles = set(); self.add_item(SpecificLeaderSelect(self))
        self.add_item(self.proceed_button); await interaction.response.edit_message(view=self)
    @ui.button(label="내용 입력하기", style=discord.ButtonStyle.success, row=4)
    async def proceed_button(self, interaction: discord.Interaction, button: ui.Button):
        if not self.selected_roles: return await interaction.response.send_message("문의 대상을 먼저 선택해주세요.", ephemeral=True)
        await interaction.response.send_modal(InquiryModal(self.cog, self.selected_roles)); await interaction.delete_original_response()


class ReportTargetSelectView(ui.View):
    # ... (이 클래스는 변경 없음) ...
    def __init__(self, cog: 'TicketSystem'): super().__init__(timeout=180); self.cog = cog
    @ui.button(label="✅ 포장 관리팀 포함하기", style=discord.ButtonStyle.success)
    async def include_police(self, interaction: discord.Interaction, button: ui.Button): await interaction.response.send_modal(ReportModal(self, include_police=True)); await interaction.delete_original_response()
    @ui.button(label="❌ 포장 관리팀 제외하기", style=discord.ButtonStyle.danger)
    async def exclude_police(self, interaction: discord.Interaction, button: ui.Button): await interaction.response.send_modal(ReportModal(self, include_police=False)); await interaction.delete_original_response()


class TicketControlView(ui.View):
    # ... (이 클래스는 변경 없음) ...
    def __init__(self, cog: 'TicketSystem', ticket_type: str, is_locked: bool = False):
        super().__init__(timeout=None)
        self.cog = cog; self.ticket_type = ticket_type
        lock_button = ui.Button(label="잠금 해제" if is_locked else "잠그기", style=discord.ButtonStyle.success if is_locked else discord.ButtonStyle.secondary, emoji="🔓" if is_locked else "🔒", custom_id="ticket_toggle_lock")
        delete_button = ui.Button(label="삭제", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="ticket_delete")
        lock_button.callback = self.toggle_lock; delete_button.callback = self.delete
        self.add_item(lock_button); self.add_item(delete_button)
    async def _check_master_permission(self, interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member): return False
        return any(role in interaction.user.roles for role in self.cog.master_roles)
    async def _check_handler_permission(self, interaction: discord.Interaction, ticket_type: str) -> bool:
        if not isinstance(interaction.user, discord.Member): return False
        roles_to_check = self.cog.report_roles if ticket_type == "report" else (self.cog.leader_roles)
        return any(role in interaction.user.roles for role in roles_to_check)
    async def toggle_lock(self, interaction: discord.Interaction):
        can_lock = await self._check_master_permission(interaction) or (self.ticket_type in ["report", "inquiry"] and await self._check_handler_permission(interaction, self.ticket_type))
        if not can_lock: return await interaction.response.send_message("❌ 이 티켓을 조작할 권한이 없습니다.", ephemeral=True)
        thread = interaction.channel
        if not isinstance(thread, discord.Thread) or not (ticket_info := self.cog.tickets.get(thread.id)): return await interaction.response.send_message("❌ 이 티켓의 정보를 찾을 수 없습니다.", ephemeral=True)
        owner = interaction.guild.get_member(ticket_info.get("owner_id")); is_currently_locked = ticket_info.get("is_locked", False); await interaction.response.defer()
        try:
            if is_currently_locked:
                if owner: await thread.add_user(owner)
                await update_ticket_lock_status(thread.id, False); self.cog.tickets[thread.id]['is_locked'] = False
                await interaction.followup.send(f"✅ 티켓의 잠금을 해제했습니다.", ephemeral=True)
                new_view = TicketControlView(self.cog, self.ticket_type, is_locked=False)
            else:
                all_admin_roles = set(self.cog.master_roles + self.cog.leader_roles + self.cog.report_roles)
                members_to_remove = [m for m in await thread.fetch_members() if not m.bot and all_admin_roles.isdisjoint({r.id for r in m.roles})]
                for member in members_to_remove: await thread.remove_user(member)
                await update_ticket_lock_status(thread.id, True); self.cog.tickets[thread.id]['is_locked'] = True
                await interaction.followup.send(f"✅ 관리자 외의 멤버를 제외하고 티켓을 잠갔습니다.", ephemeral=True)
                new_view = TicketControlView(self.cog, self.ticket_type, is_locked=True)
            await (await interaction.original_response()).edit(view=new_view)
        except Exception as e: logger.error(f"티켓 잠금/해제 중 오류 발생: {e}", exc_info=True)
    async def delete(self, interaction: discord.Interaction):
        if not await self._check_master_permission(interaction): return await interaction.response.send_message("❌ `대표`, `부대표`만 이 버튼을 사용할 수 있습니다.", ephemeral=True)
        await interaction.response.send_message(f"✅ 5초 후에 이 티켓을 삭제합니다."); await asyncio.sleep(5)
        try: await interaction.channel.delete(reason=f"{interaction.user.display_name}이(가) 삭제")
        except discord.NotFound: pass


class MainTicketPanelView(ui.View):
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
    
    # --- ▼▼▼ [수정] 관리자 신청 버튼 콜백을 새로운 View를 호출하도록 변경 ▼▼▼ ---
    @ui.button(label="관리자 신청", style=discord.ButtonStyle.success, emoji="✨", custom_id="ticket_create_application")
    async def application(self, interaction: discord.Interaction, button: ui.Button):
        if self.cog.has_open_ticket(interaction.user, "application"): return await interaction.response.send_message("❌ 이미 제출한 지원서가 처리 대기 중입니다.", ephemeral=True)
        await interaction.response.send_message("어떤 부서에 지원하시겠습니까?", view=ApplicationDepartmentSelectView(self.cog), ephemeral=True)
    # --- ▲▲▲ [수정 완료] ---


class TicketSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        # ... (이 클래스의 __init__, cog_load, register_persistent_views, load_configs, has_open_ticket, sync_tickets_from_db 는 변경 없음) ...
        self.bot = bot; self.tickets: Dict[int, Dict] = {}; self.master_roles: List[discord.Role] = []
        self.report_roles: List[discord.Role] = []; self.leader_roles: List[discord.Role] = []
        self.guild: Optional[discord.Guild] = None; self.view_instance: Optional[MainTicketPanelView] = None
        logger.info("TicketSystem Cog가 성공적으로 초기화되었습니다.")
    async def cog_load(self): await self.load_configs(); await self.register_persistent_views(); self.bot.loop.create_task(self.sync_tickets_from_db())
    async def register_persistent_views(self): self.view_instance = MainTicketPanelView(self); self.bot.add_view(self.view_instance); logger.info("✅ 통합 티켓 시스템의 영구 View가 성공적으로 등록되었습니다.")
    async def load_configs(self):
        panel_channel_id = get_id("ticket_main_panel_channel_id")
        if panel_channel_id and (channel := self.bot.get_channel(panel_channel_id)): self.guild = channel.guild
        if self.guild:
            self.master_roles = [role for key in TICKET_MASTER_ROLES if (role_id := get_id(key)) and (role := self.guild.get_role(role_id))]
            self.report_roles = [role for key in TICKET_REPORT_ROLES if (role_id := get_id(key)) and (role := self.guild.get_role(role_id))]
            self.leader_roles = [role for key in TICKET_LEADER_ROLES if (role_id := get_id(key)) and (role := self.guild.get_role(role_id))]
            logger.info(f"[TicketSystem] 역할 로드 완료 (대표: {len(self.master_roles)}, 신고: {len(self.report_roles)}, 팀장: {len(self.leader_roles)})")
        else: logger.warning("[TicketSystem] 티켓 패널 채널이 설정되지 않아 길드 정보를 불러올 수 없습니다.")
    def has_open_ticket(self, user: discord.Member, ticket_type: str):
        for thread_id, ticket_info in self.tickets.items():
            if ticket_info.get("owner_id") == user.id and ticket_info.get("ticket_type") == ticket_type:
                if self.guild and self.guild.get_thread(thread_id): return True
        return False
    async def sync_tickets_from_db(self):
        await self.bot.wait_until_ready(); db_tickets = await get_all_tickets()
        if not db_tickets: return
        zombie_ids = [td['thread_id'] for td in db_tickets if not (self.guild and self.guild.get_thread(td['thread_id']))]
        for td in db_tickets:
            if td['thread_id'] not in zombie_ids:
                self.tickets[td['thread_id']] = td
                self.bot.add_view(TicketControlView(self, td.get("ticket_type"), td.get("is_locked", False)))
        if zombie_ids: await remove_multiple_tickets(zombie_ids)
        logger.info(f"[TicketSystem] 기존 티켓 동기화 완료: {len(self.tickets)}개")

    # --- ▼▼▼ [수정] create_ticket 함수를 새로운 부서 선택 방식에 맞게 최종 수정 ▼▼▼
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
                    
                    # '지원 부서'를 첫 번째 필드로 추가
                    embed_to_send.add_field(name="지원 부서", value=dept_info['label'], inline=False)
                    
                    for name, value in content.items():
                        embed_to_send.add_field(name=name, value=value or "내용 없음", inline=False)
                    
                    # 멘션할 역할에 팀과 팀장 역할 추가
                    if team_role_id := get_id(dept_info['team_role_key']):
                        if team_role := interaction.guild.get_role(team_role_id): selected_roles.add(team_role)
                    if leader_role_id := get_id(dept_info['leader_role_key']):
                        if leader_role := interaction.guild.get_role(leader_role_id): selected_roles.add(leader_role)

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
            if thread: await thread.delete(reason="생성 과정 오류로 인한 자동 삭제")
            if interaction.response.is_done(): await interaction.followup.send("❌ 티켓을 만드는 중 오류가 발생했습니다.", ephemeral=True)
    # --- ▲▲▲ [수정 완료] ---
            
    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        if thread.id in self.tickets: self.tickets.pop(thread.id, None); await remove_ticket(thread.id)
            
    async def regenerate_panel(self, channel: discord.TextChannel, panel_key: str = "panel_ticket_main") -> bool:
        # ... (이 함수는 변경 없음) ...
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
