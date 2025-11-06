# cogs/features/ticket_system.py
import discord
from discord import ui
from discord.ext import commands
import logging
from typing import Dict, Any, List, Optional, Set
import asyncio

from utils.database import get_id, add_ticket, remove_ticket, get_all_tickets, remove_multiple_tickets, update_ticket_lock_status
from utils.ui_defaults import TICKET_MASTER_ROLES, TICKET_STAFF_GENERAL_ROLES, TICKET_STAFF_SPECIFIC_ROLES, TICKET_REPORT_ROLES

logger = logging.getLogger(__name__)

class TicketModal(ui.Modal):
    title_input = ui.TextInput(label="제목", placeholder="티켓 제목을 입력해주세요.", max_length=100)
    content_input = ui.TextInput(label="내용", placeholder="자세한 내용을 입력해주세요.", style=discord.TextStyle.paragraph, max_length=1000)
    def __init__(self, cog: 'TicketSystem', ticket_type: str, selected_roles: Set[discord.Role]):
        super().__init__(title=f"{'문의' if ticket_type == 'inquiry' else '신고'} 내용 입력", timeout=None)
        self.cog, self.ticket_type, self.selected_roles = cog, ticket_type, selected_roles
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            final_title = self.title_input.value
            if self.ticket_type == 'report': final_title = f"신고: {self.title_input.value}"
            await self.cog.create_ticket(interaction, self.ticket_type, final_title, self.content_input.value, self.selected_roles)
        except Exception as e:
            logger.error(f"TicketModal on_submit에서 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 티켓을 만드는 중 오류가 발생했습니다.", ephemeral=True)

class ReportModal(TicketModal):
    def __init__(self, cog: 'TicketSystem', selected_roles: Set[discord.Role]):
        super().__init__(cog, "report", selected_roles)
        self.title = "신고 내용 입력"; self.children[0].label = "대상자"; self.children[0].placeholder = "신고할 상대방의 이름을 정확하게 입력해주세요."

class InquiryTargetSelectView(ui.View):
    def __init__(self, cog: 'TicketSystem'):
        super().__init__(timeout=180)
        self.cog, self.target_type, self.specific_roles = cog, None, set()
        self.target_select = ui.Select(placeholder="문의할 대상을 선택해주세요...", options=[discord.SelectOption(label="대표/부대표에게", value="master"), discord.SelectOption(label="관라자 전체에게", value="general"), discord.SelectOption(label="특정 담당 관리자에게", value="specific")])
        self.target_select.callback = self.select_target_callback; self.add_item(self.target_select)
        self.proceed_button = ui.Button(label="내용 입력하기", style=discord.ButtonStyle.success, row=2)
        self.proceed_button.callback = self.proceed_callback; self.add_item(self.proceed_button)
    async def select_target_callback(self, interaction: discord.Interaction):
        self.target_type = interaction.data['values'][0]; self.target_select.disabled = True
        if self.target_type == "specific":
            specific_roles = [role for key in TICKET_STAFF_SPECIFIC_ROLES if (role_id := get_id(key)) and (role := self.cog.guild.get_role(role_id))]
            if specific_roles:
                self.specific_role_select = ui.Select(placeholder="담당자를 선택해주세요 (여러 명 선택 가능)...", min_values=1, max_values=len(specific_roles), options=[discord.SelectOption(label=role.name, value=str(role.id)) for role in specific_roles])
                self.specific_role_select.callback = self.specific_role_callback; self.add_item(self.specific_role_select)
        await interaction.response.edit_message(view=self)
    async def specific_role_callback(self, interaction: discord.Interaction):
        self.specific_roles = {interaction.guild.get_role(int(role_id)) for role_id in interaction.data['values']}; await interaction.response.defer()
    async def proceed_callback(self, interaction: discord.Interaction):
        if not self.target_type: return await interaction.response.send_message("문의 대상을 선택해주세요.", ephemeral=True)
        if self.target_type == "specific" and not self.specific_roles: return await interaction.response.send_message("담당자를 선택해주세요.", ephemeral=True)
        selected_roles: Set[discord.Role] = set()
        if self.target_type == "master": selected_roles.update(self.cog.master_roles)
        elif self.target_type == "general": selected_roles.update(self.cog.staff_general_roles)
        elif self.target_type == "specific": selected_roles.update(self.specific_roles)
        await interaction.response.send_modal(TicketModal(self.cog, "inquiry", selected_roles)); await interaction.delete_original_response()

class ReportTargetSelectView(ui.View):
    def __init__(self, cog: 'TicketSystem'):
        super().__init__(timeout=180); self.cog = cog
    @ui.button(label="✅ 포장 관리팀 포함하기", style=discord.ButtonStyle.success)
    async def include_police(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ReportModal(self.cog, set(self.cog.report_roles))); await interaction.delete_original_response()
    @ui.button(label="❌ 포장 관리팀 제외하기", style=discord.ButtonStyle.danger)
    async def exclude_police(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ReportModal(self.cog, set())); await interaction.delete_original_response()

class TicketControlView(ui.View):
    def __init__(self, cog: 'TicketSystem', ticket_type: str, is_locked: bool = False):
        super().__init__(timeout=None)
        self.cog = cog
        self.ticket_type = ticket_type
        
        if is_locked:
            lock_button = ui.Button(label="잠금 해제", style=discord.ButtonStyle.success, emoji="🔓", custom_id="ticket_toggle_lock")
        else:
            lock_button = ui.Button(label="잠그기", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="ticket_toggle_lock")
        
        delete_button = ui.Button(label="삭제", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="ticket_delete")

        lock_button.callback = self.toggle_lock
        delete_button.callback = self.delete
        
        self.add_item(lock_button)
        self.add_item(delete_button)

    async def _check_master_permission(self, interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member): return False
        return any(role in interaction.user.roles for role in self.cog.master_roles)
    async def _check_handler_permission(self, interaction: discord.Interaction, ticket_type: str) -> bool:
        if not isinstance(interaction.user, discord.Member): return False
        roles_to_check = self.cog.report_roles if ticket_type == "report" else (self.cog.staff_general_roles + self.cog.staff_specific_roles)
        return any(role in interaction.user.roles for role in roles_to_check)

    async def toggle_lock(self, interaction: discord.Interaction):
        is_master = await self._check_master_permission(interaction)
        is_handler = await self._check_handler_permission(interaction, self.ticket_type)
        can_lock = is_master or (self.ticket_type == "report" and is_handler)
        if not can_lock: return await interaction.response.send_message("❌ 이 티켓을 조작할 권한이 없습니다.", ephemeral=True)

        thread = interaction.channel
        if not isinstance(thread, discord.Thread): return

        ticket_info = self.cog.tickets.get(thread.id)
        if not ticket_info: return await interaction.response.send_message("❌ 이 티켓의 정보를 찾을 수 없습니다.", ephemeral=True)
        
        owner = interaction.guild.get_member(ticket_info.get("owner_id"))
        is_currently_locked = ticket_info.get("is_locked", False)
        
        await interaction.response.defer()
        
        try:
            if is_currently_locked:
                if owner: await thread.add_user(owner)
                await update_ticket_lock_status(thread.id, False)
                self.cog.tickets[thread.id]['is_locked'] = False
                await interaction.followup.send(f"✅ 티켓의 잠금을 해제했습니다. {owner.mention if owner else ''}님을 다시 초대했습니다.", ephemeral=True)
                new_view = TicketControlView(self.cog, self.ticket_type, is_locked=False)
            else:
                all_admin_roles = self.cog.master_roles + self.cog.staff_general_roles + self.cog.staff_specific_roles + self.cog.report_roles
                all_admin_role_ids = {role.id for role in all_admin_roles}
                
                members_to_remove = []
                thread_members = await thread.fetch_members()
                for m in thread_members:
                    member = interaction.guild.get_member(m.id)
                    if not member: continue
                    
                    if not member.bot and not any(r.id in all_admin_role_ids for r in member.roles):
                        members_to_remove.append(member)
                
                for member in members_to_remove: await thread.remove_user(member)
                
                await update_ticket_lock_status(thread.id, True)
                self.cog.tickets[thread.id]['is_locked'] = True
                removed_names = ", ".join([m.display_name for m in members_to_remove])
                await interaction.followup.send(f"✅ 관리자 외의 멤버({removed_names})를 제외하고 티켓을 잠갔습니다.", ephemeral=True)
                new_view = TicketControlView(self.cog, self.ticket_type, is_locked=True)

            message_to_edit = await interaction.original_response()
            await message_to_edit.edit(view=new_view)
            
        except Exception as e:
            logger.error(f"티켓 잠금/해제 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send("❌ 티켓을 처리하는 중 오류가 발생했습니다.", ephemeral=True)

    async def delete(self, interaction: discord.Interaction):
        if not await self._check_master_permission(interaction):
            return await interaction.response.send_message("❌ `대표`, `부대표`만 이 버튼을 사용할 수 있습니다.", ephemeral=True)
        await interaction.response.send_message(f"✅ 5초 후에 이 티켓을 삭제합니다.")
        await asyncio.sleep(5)
        try: await interaction.channel.delete(reason=f"{interaction.user.display_name}이(가) 삭제")
        except discord.NotFound: pass

class TicketSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot; self.tickets: Dict[int, Dict] = {}; self.master_roles: List[discord.Role] = []
        self.staff_general_roles: List[discord.Role] = []; self.staff_specific_roles: List[discord.Role] = []
        self.report_roles: List[discord.Role] = []; self.guild: Optional[discord.Guild] = None
        logger.info("TicketSystem Cog가 성공적으로 초기화되었습니다.")

    @commands.Cog.listener()
    async def on_ready(self):
        await self.load_configs(); await self.sync_tickets_from_db()

    async def load_configs(self):
        self.bot.add_view(self.create_panel_view("inquiry")); self.bot.add_view(self.create_panel_view("report"))
        panel_channel_id = get_id("inquiry_panel_channel_id") or get_id("report_panel_channel_id")
        if panel_channel_id and (channel := self.bot.get_channel(panel_channel_id)): self.guild = channel.guild
        if self.guild:
            self.master_roles = [role for key in TICKET_MASTER_ROLES if (role_id := get_id(key)) and (role := self.guild.get_role(role_id))]
            self.staff_general_roles = [role for key in TICKET_STAFF_GENERAL_ROLES if (role_id := get_id(key)) and (role := self.guild.get_role(role_id))]
            self.staff_specific_roles = [role for key in TICKET_STAFF_SPECIFIC_ROLES if (role_id := get_id(key)) and (role := self.guild.get_role(role_id))]
            self.report_roles = [role for key in TICKET_REPORT_ROLES if (role_id := get_id(key)) and (role := self.guild.get_role(role_id))]
            logger.info(f"[TicketSystem] 역할 로드 완료.")
        else: logger.warning("[TicketSystem] 티켓 패널 채널이 설정되지 않아 길드 정보를 불러올 수 없습니다.")
    
    def create_panel_view(self, panel_type: str):
        view = ui.View(timeout=None)
        if panel_type == "inquiry":
            button = ui.Button(label="문의/건의", style=discord.ButtonStyle.primary, emoji="📨", custom_id="ticket_inquiry_panel")
            async def callback(interaction: discord.Interaction):
                if self.has_open_ticket(interaction.user, "inquiry"): return await interaction.response.send_message("❌ 이미 참여 중인 문의 티켓이 있습니다.", ephemeral=True)
                await interaction.response.send_message("문의할 대상을 선택해주세요.", view=InquiryTargetSelectView(self), ephemeral=True)
            button.callback = callback; view.add_item(button)
        elif panel_type == "report":
            button = ui.Button(label="신고", style=discord.ButtonStyle.danger, emoji="🚨", custom_id="ticket_report_panel")
            async def callback(interaction: discord.Interaction):
                if self.has_open_ticket(interaction.user, "report"): return await interaction.response.send_message("❌ 이미 참여 중인 신고 티켓이 있습니다.", ephemeral=True)
                await interaction.response.send_message("이 신고에 `경찰관`을 포함하시겠습니까?", view=ReportTargetSelectView(self), ephemeral=True)
            button.callback = callback; view.add_item(button)
        return view

    def has_open_ticket(self, user: discord.Member, ticket_type: str):
        for thread_id, ticket_info in self.tickets.items():
            if ticket_info.get("owner_id") == user.id and ticket_info.get("ticket_type") == ticket_type:
                if self.guild and self.guild.get_thread(thread_id): return True
        return False

    async def sync_tickets_from_db(self):
        db_tickets = await get_all_tickets()
        if not db_tickets: return
        zombie_ids = []
        for ticket_data in db_tickets:
            thread_id = ticket_data.get("thread_id")
            if self.guild and self.guild.get_thread(thread_id):
                self.tickets[thread_id] = ticket_data
                self.bot.add_view(TicketControlView(self, ticket_data.get("ticket_type"), ticket_data.get("is_locked", False)))
            else:
                zombie_ids.append(thread_id)
        if zombie_ids: await remove_multiple_tickets(zombie_ids)

    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str, title: str, content: str, selected_roles: Set[discord.Role]):
        thread: Optional[discord.Thread] = None
        try:
            panel_channel = interaction.channel
            thread_name = f"[{'문의' if ticket_type == 'inquiry' else '신고'}] {title}"
            thread = await panel_channel.create_thread(name=thread_name, type=discord.ChannelType.private_thread)
            
            await add_ticket(thread.id, interaction.user.id, interaction.guild.id, ticket_type)
            
            self.tickets[thread.id] = {"thread_id": thread.id, "owner_id": interaction.user.id, "ticket_type": ticket_type, "is_locked": False}
            
            embed = discord.Embed(title=title, description=content, color=discord.Color.blue() if ticket_type == "inquiry" else discord.Color.red())
            embed.set_author(name=f"{interaction.user.display_name} 님의 {ticket_type}", icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None)
            await thread.send(embed=embed)
            
            final_roles_to_mention = set(self.master_roles) | selected_roles
            mention_string = ' '.join(role.mention for role in final_roles_to_mention)
            control_view = TicketControlView(self, ticket_type, is_locked=False)
            await thread.send(f"{interaction.user.mention} {mention_string}\n**[티켓 관리 패널]**", view=control_view, allowed_mentions=discord.AllowedMentions(users=True, roles=True))
            
            message = await interaction.followup.send(f"✅ 비공개 티켓을 만들었습니다: {thread.mention}", ephemeral=True, wait=True)
            await asyncio.sleep(5)
            await message.delete()
        except Exception as e:
            logger.error(f"티켓 생성 중 오류 발생: {e}", exc_info=True)
            if thread:
                logger.warning(f"오류로 인해 방금 생성된 티켓 스레드 '{thread.name}'(ID: {thread.id})을(를) 삭제합니다.")
                try:
                    await thread.delete(reason="생성 과정 오류로 인한 자동 삭제")
                except (discord.NotFound, discord.Forbidden):
                    pass
            
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("❌ 티켓을 만드는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.", ephemeral=True)
                else:
                    await interaction.response.send_message("❌ 티켓을 만드는 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.", ephemeral=True)
            except discord.NotFound:
                pass

    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        if thread.id in self.tickets:
            await self._cleanup_ticket_data(thread.id)
    async def _cleanup_ticket_data(self, thread_id: int):
        self.tickets.pop(thread_id, None); await remove_ticket(thread_id)
    async def regenerate_panel(self, channel: discord.TextChannel, panel_type: str) -> bool:
        if not isinstance(channel, discord.TextChannel): return False
        view = self.create_panel_view(panel_type)
        embed = None
        if panel_type == "inquiry":
            embed = discord.Embed(title="서버 문의/건의", description="아래 버튼을 눌러 서버 운영에 대한 의견을 보내주세요.")
        elif panel_type == "report":
            embed = discord.Embed(title="유저 신고", description="서버 내에서 불편을 겪거나 문제를 발견했다면 아래 버튼으로 신고해주세요.")
        if view and embed:
            try:
                async for message in channel.history(limit=100):
                    if message.author == self.bot.user and message.embeds and message.embeds[0].title == embed.title:
                        await message.delete()
                await channel.send(embed=embed, view=view)
                logger.info(f"✅ {panel_type} 패널을 텍스트 채널 #{channel.name}에 생성했습니다.")
                return True
            except Exception as e:
                logger.error(f"❌ #{channel.name} 채널에 패널 생성 중 오류 발생: {e}", exc_info=True)
                return False
        return False

async def setup(bot):
    await bot.add_cog(TicketSystem(bot))
