# cogs/features/ticket_system.py
import discord
from discord import app_commands, ui
from discord.ext import commands
import logging
from typing import Dict, Any, List, Optional
import asyncio

from utils.database import get_id, add_ticket, remove_ticket, get_all_tickets, remove_multiple_tickets
from utils.ui_defaults import TICKET_INQUIRY_ROLES, TICKET_REPORT_ROLES

logger = logging.getLogger(__name__)

# ... (InquiryModal, ReportModal, ExcludeAdminSelect 등 UI 클래스는 이전과 동일) ...
class ExcludeAdminSelect(ui.RoleSelect):
    def __init__(self, allowed_roles: List[discord.Role]):
        super().__init__(placeholder="この管理者を相談から除外します...", min_values=0, max_values=len(allowed_roles))
        # 옵션을 직접 설정하지 않고 RoleSelect의 기본 기능을 사용
class InquiryModal(ui.Modal, title="お問い合わせ・ご提案"):
    title_input = ui.TextInput(label="件名", placeholder="お問い合わせの件名を入力してください。", max_length=100)
    content_input = ui.TextInput(label="内容", placeholder="お問い合わせ内容を詳しく入力してください。", style=discord.TextStyle.paragraph, max_length=1000)
    def __init__(self, cog: 'TicketSystem'):
        super().__init__(timeout=None)
        self.cog = cog
        inquiry_roles = [role for role_id in self.cog.inquiry_role_ids if (role := self.cog.bot.get_guild(self.cog.guild_id).get_role(role_id))]
        if inquiry_roles:
            self.exclude_select = ExcludeAdminSelect(inquiry_roles)
            self.add_item(self.exclude_select)
    async def on_submit(self, interaction: discord.Interaction): await interaction.response.defer()
class ReportModal(ui.Modal, title="通報"):
    target_user = ui.TextInput(label="対象者", placeholder="通報する相手の名前を正確に入力してください。")
    content_input = ui.TextInput(label="内容", placeholder="通報内容を詳しく入力してください。(証拠SSなど)", style=discord.TextStyle.paragraph, max_length=1000)
    async def on_submit(self, interaction: discord.Interaction): await interaction.response.defer()

class TicketControlView(ui.View):
    def __init__(self, cog: 'TicketSystem', ticket_type: str):
        super().__init__(timeout=None)
        self.cog = cog; self.ticket_type = ticket_type
    async def _check_master_permission(self, interaction: discord.Interaction) -> bool:
        return any(role.id in self.cog.master_role_ids for role in interaction.user.roles)
    async def _check_handler_permission(self, interaction: discord.Interaction, ticket_type: str) -> bool:
        role_ids_to_check = self.cog.report_role_ids if ticket_type == "report" else self.cog.inquiry_role_ids
        return any(role.id in role_ids_to_check for role in interaction.user.roles)
    @ui.button(label="ロック", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="ticket_lock")
    async def lock(self, interaction: discord.Interaction, button: ui.Button):
        is_master = await self._check_master_permission(interaction)
        is_handler = await self._check_handler_permission(interaction, self.ticket_type)
        can_lock = is_master or (self.ticket_type == "report" and is_handler)
        if not can_lock: return await interaction.response.send_message("❌ このチケットをロックする権限がありません。", ephemeral=True)
        thread = interaction.channel
        await interaction.response.send_message(f"✅ {interaction.user.mention}さんがこのチケットをロックしました。")
        await thread.edit(locked=True, archived=True, reason=f"{interaction.user.display_name}によるロック")
    @ui.button(label="削除", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="ticket_delete")
    async def delete(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check_master_permission(interaction):
            return await interaction.response.send_message("❌ `村長`、`副村長`のみがこのボタンを使用できます。", ephemeral=True)
        thread_id = interaction.channel.id
        await interaction.response.send_message(f"✅ 5秒後にこのチケットを削除します。")
        await asyncio.sleep(5)
        try: await interaction.channel.delete(reason=f"{interaction.user.display_name}による削除")
        except discord.NotFound: pass

# --- [수정] 패널 View를 2개로 분리 ---
class InquiryPanelView(ui.View):
    def __init__(self, cog: 'TicketSystem'):
        super().__init__(timeout=None)
        self.cog = cog
    @ui.button(label="お問い合わせ・ご提案", style=discord.ButtonStyle.primary, emoji="📨", custom_id="ticket_inquiry")
    async def inquiry(self, interaction: discord.Interaction, button: ui.Button):
        modal = InquiryModal(self.cog)
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.is_submitted():
            excluded_role_ids = [int(role.id) for role in modal.exclude_select.values]
            await self.cog.create_ticket(interaction, "inquiry", modal.title_input.value, modal.content_input.value, excluded_role_ids=excluded_role_ids)

class ReportPanelView(ui.View):
    def __init__(self, cog: 'TicketSystem'):
        super().__init__(timeout=None)
        self.cog = cog
    @ui.button(label="通報", style=discord.ButtonStyle.danger, emoji="🚨", custom_id="ticket_report")
    async def report(self, interaction: discord.Interaction, button: ui.Button):
        modal = ReportModal()
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.is_submitted():
            title = f"通報: {modal.target_user.value}"
            content = f"**通報対象者:** {modal.target_user.value}\n\n**内容:**\n{modal.content_input.value}"
            await self.cog.create_ticket(interaction, "report", title, content)

# --- 메인 Cog ---
class TicketSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tickets: Dict[int, Dict] = {}
        self.master_role_ids: List[int] = []
        self.inquiry_role_ids: List[int] = []
        self.report_role_ids: List[int] = []
        self.guild_id: Optional[int] = None
        logger.info("TicketSystem Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        # [수정] 2개의 패널 View를 등록
        self.bot.add_view(InquiryPanelView(self))
        self.bot.add_view(ReportPanelView(self))
        await self.load_configs()
        self.bot.loop.create_task(self.sync_tickets_from_db())

    async def load_configs(self):
        # [수정] 두 패널 중 하나라도 설정되어 있으면 Guild ID를 가져옴
        inquiry_channel_id = get_id("inquiry_panel_channel_id")
        report_channel_id = get_id("report_panel_channel_id")
        panel_channel_id = inquiry_channel_id or report_channel_id
        if panel_channel_id and (channel := self.bot.get_channel(panel_channel_id)):
            self.guild_id = channel.guild.id
        
        self.master_role_ids = [r_id for key in ["role_staff_village_chief", "role_staff_deputy_chief"] if (r_id := get_id(key))]
        self.inquiry_role_ids = [r_id for key in TICKET_INQUIRY_ROLES if (r_id := get_id(key))]
        self.report_role_ids = [r_id for key in TICKET_REPORT_ROLES if (r_id := get_id(key))]
        logger.info(f"[TicketSystem] {len(self.master_role_ids)}개의 마스터 역할을, {len(self.inquiry_role_ids)}개의 문의 역할을, {len(self.report_role_ids)}개의 신고 역할을 로드했습니다.")
    
    async def sync_tickets_from_db(self):
        await self.bot.wait_until_ready()
        db_tickets = await get_all_tickets()
        if not db_tickets: return
        zombie_ids = []
        for ticket_data in db_tickets:
            thread_id, guild_id = ticket_data.get("thread_id"), ticket_data.get("guild_id")
            guild = self.bot.get_guild(guild_id)
            if guild and self.bot.get_channel(thread_id):
                self.tickets[thread_id] = ticket_data
                self.bot.add_view(TicketControlView(self, ticket_data.get("ticket_type")))
            else: zombie_ids.append(thread_id)
        if zombie_ids: await remove_multiple_tickets(zombie_ids)

    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str, title: str, content: str, excluded_role_ids: List[int] = []):
        try:
            category = interaction.channel.category
            if not category: return await interaction.followup.send("❌ チケットを作成するカテゴリーが見つかりません。", ephemeral=True)
            
            forum_name = f"문의-{interaction.user.name}" if ticket_type == "inquiry" else f"신고-{interaction.user.name}"
            role_ids_to_add = self.inquiry_role_ids if ticket_type == "inquiry" else self.report_role_ids
            final_role_ids = [r_id for r_id in role_ids_to_add if r_id not in excluded_role_ids]
            
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(view_channel=True),
            }
            roles_to_add = [interaction.guild.get_role(r_id) for r_id in final_role_ids]
            for role in roles_to_add:
                if role: overwrites[role] = discord.PermissionOverwrite(view_channel=True)

            forum = await category.create_forum(name=forum_name, overwrites=overwrites, reason=f"{ticket_type} 티켓 생성")
            
            thread = await forum.create_thread(name=title, content=f"**作成者:** {interaction.user.mention}\n\n**内容:**\n{content}")
            
            await add_ticket(thread.id, interaction.user.id, interaction.guild.id, ticket_type)
            self.tickets[thread.id] = {"thread_id": thread.id, "owner_id": interaction.user.id, "ticket_type": ticket_type}
            
            control_view = TicketControlView(self, ticket_type)
            mention_string = ' '.join(role.mention for role in roles_to_add if role)
            await thread.send(f"**[チケット管理パネル]**\n{mention_string}", view=control_view, allowed_mentions=discord.AllowedMentions(roles=True))
            
            await interaction.followup.send(f"✅ 非公開のチケットを作成しました: {forum.mention}", ephemeral=True)
            
        except Exception as e:
            logger.error(f"티켓 생성 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send("❌ チケットの作成中にエラーが発生しました。", ephemeral=True)

    async def _cleanup_ticket_data(self, thread_id: int):
        self.tickets.pop(thread_id, None); await remove_ticket(thread_id)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        if thread.id in self.tickets:
            await self._cleanup_ticket_data(thread.id)
            if isinstance(thread.parent, discord.ForumChannel):
                try: await thread.parent.delete(reason="チケットのスレッドが削除されたため")
                except discord.NotFound: pass

    # [수정] regenerate_panel 함수를 패널 타입에 따라 분리
    async def regenerate_panel(self, channel: discord.TextChannel | discord.ForumChannel):
        panel_key = None
        if channel.id == get_id("inquiry_panel_channel_id"):
            panel_key = "inquiry"
        elif channel.id == get_id("report_panel_channel_id"):
            panel_key = "report"
            
        if panel_key == "inquiry":
            embed = discord.Embed(title="サーバーへのお問い合わせ・ご提案", description="下のボタンを押して、サーバー運営へのご意見をお聞かせください。")
            view = InquiryPanelView(self)
            await channel.send(embed=embed, view=view)
            logger.info(f"✅ 문의/건의 패널을 #{channel.name} 채널에 생성했습니다.")
        elif panel_key == "report":
            embed = discord.Embed(title="ユーザーへの通報", description="サーバー内での迷惑行為や問題を発見した場合、下のボタンで通報してください。")
            view = ReportPanelView(self)
            await channel.send(embed=embed, view=view)
            logger.info(f"✅ 유저 신고 패널을 #{channel.name} 채널에 생성했습니다.")

async def setup(bot):
    await bot.add_cog(TicketSystem(bot))
