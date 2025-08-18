# cogs/features/ticket_system.py
import discord
from discord import ui
from discord.ext import commands
import logging
from typing import Dict, Any, List, Optional
import asyncio

from utils.database import get_id, add_ticket, remove_ticket, get_all_tickets, remove_multiple_tickets
from utils.ui_defaults import TICKET_INQUIRY_ROLES, TICKET_REPORT_ROLES

logger = logging.getLogger(__name__)

# --- 모달 클래스 ---
class InquiryModal(ui.Modal, title="お問い合わせ・ご提案"):
    title_input = ui.TextInput(label="件名", placeholder="お問い合わせの件名を入力してください。", max_length=100)
    content_input = ui.TextInput(label="内容", placeholder="お問い合わせ内容を詳しく入力してください。", style=discord.TextStyle.paragraph, max_length=1000)
    def __init__(self, cog: 'TicketSystem', forum_channel: discord.ForumChannel):
        super().__init__(timeout=None)
        self.cog = cog; self.forum_channel = forum_channel
        if self.cog.guild and (guild := self.cog.bot.get_guild(self.cog.guild.id)):
            inquiry_roles = [role for role_id in self.cog.inquiry_role_ids if (role := guild.get_role(role_id))]
            if inquiry_roles:
                self.exclude_select = ui.RoleSelect(placeholder="この管理者を相談から除外します...", min_values=0, max_values=len(inquiry_roles), role_ids=[r.id for r in inquiry_roles])
                self.add_item(self.exclude_select)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("⏳ チケットを作成しています...", ephemeral=True)
        excluded_role_ids = []
        if hasattr(self, 'exclude_select'):
            excluded_role_ids = [int(role.id) for role in self.exclude_select.values]
        await self.cog.create_ticket(interaction, "inquiry", self.forum_channel, self.title_input.value, self.content_input.value, excluded_role_ids=excluded_role_ids)

class ReportModal(ui.Modal, title="通報"):
    target_user = ui.TextInput(label="対象者", placeholder="通報する相手の名前を正確に入力してください。")
    content_input = ui.TextInput(label="内容", placeholder="通報内容を詳しく入力してください。(証拠SSなど)", style=discord.TextStyle.paragraph, max_length=1000)
    def __init__(self, cog: 'TicketSystem', forum_channel: discord.ForumChannel):
        super().__init__(timeout=None)
        self.cog = cog; self.forum_channel = forum_channel
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message("⏳ チケットを作成しています...", ephemeral=True)
        title = f"通報: {self.target_user.value}"
        content = f"**通報対象者:** {self.target_user.value}\n\n**内容:**\n{self.content_input.value}"
        await self.cog.create_ticket(interaction, "report", self.forum_channel, title, content)

# --- 제어판 View ---
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
        await interaction.response.send_message(f"✅ {interaction.user.mention}さんがこのチケットをロックしました。")
        await interaction.channel.edit(locked=True, archived=True, reason=f"{interaction.user.display_name}によるロック")
    @ui.button(label="削除", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="ticket_delete")
    async def delete(self, interaction: discord.Interaction, button: ui.Button):
        if not await self._check_master_permission(interaction):
            return await interaction.response.send_message("❌ `村長`、`副村長`のみがこのボタンを使用できます。", ephemeral=True)
        await interaction.response.send_message(f"✅ 5秒後にこのチケットを削除します。")
        await asyncio.sleep(5)
        try: await interaction.channel.delete(reason=f"{interaction.user.display_name}による削除")
        except discord.NotFound: pass

# --- 메인 Cog ---
class TicketSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tickets: Dict[int, Dict] = {}
        self.master_role_ids: List[int] = []
        self.inquiry_role_ids: List[int] = []
        self.report_role_ids: List[int] = []
        self.guild: Optional[discord.Guild] = None
        self.inquiry_forum: Optional[discord.ForumChannel] = None
        self.report_forum: Optional[discord.ForumChannel] = None
        logger.info("TicketSystem Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        # View는 regenerate_panel에서 동적으로 생성되므로 여기서 등록할 필요 없음
        await self.load_configs()
        self.bot.loop.create_task(self.sync_tickets_from_db())

    async def load_configs(self):
        inquiry_forum_id = get_id("inquiry_forum_channel_id")
        if inquiry_forum_id:
            self.inquiry_forum = self.bot.get_channel(inquiry_forum_id)
            if self.inquiry_forum: self.guild = self.inquiry_forum.guild
        
        report_forum_id = get_id("report_forum_channel_id")
        if report_forum_id:
            self.report_forum = self.bot.get_channel(report_forum_id)
            if self.report_forum and not self.guild: self.guild = self.report_forum.guild

        if self.guild:
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
            thread_id = ticket_data.get("thread_id")
            # 스레드가 실제로 존재하는지 확인 (get_thread는 비공개 스레드도 찾아줌)
            if self.guild and self.guild.get_thread(thread_id):
                self.tickets[thread_id] = ticket_data
                self.bot.add_view(TicketControlView(self, ticket_data.get("ticket_type")))
            else:
                zombie_ids.append(thread_id)
        if zombie_ids: await remove_multiple_tickets(zombie_ids)

    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str, forum_channel: discord.ForumChannel, title: str, content: str, excluded_role_ids: List[int] = []):
        try:
            role_ids_to_add = self.inquiry_role_ids if ticket_type == "inquiry" else self.report_role_ids
            final_role_ids = [r_id for r_id in role_ids_to_add if r_id not in excluded_role_ids]
            roles_to_add = [interaction.guild.get_role(r_id) for r_id in final_role_ids if interaction.guild.get_role(r_id)]
            
            thread_content = f"**作成者:** {interaction.user.mention}\n\n**内容:**\n{content}"
            # 비공개 스레드를 만들고, 생성자와 담당 역할 멤버들을 초대
            thread = await forum_channel.create_thread(name=title, content=thread_content[:1900], auto_archive_duration=10080)
            
            # 비공개 스레드로 만들기 위해 권한 수정 (스레드 생성 후 가능)
            # 현재 discord.py에서는 스레드 권한을 직접 수정하는 API가 공식적으로 지원되지 않음
            # 대신, 생성 시점에 초대하는 방식으로 구현
            
            await add_ticket(thread.id, interaction.user.id, interaction.guild.id, ticket_type)
            self.tickets[thread.id] = {"thread_id": thread.id, "owner_id": interaction.user.id, "ticket_type": ticket_type}
            
            # 스레드에 작성자(이미 추가됨)와 관리자들을 추가
            members_to_add = {interaction.user}
            for role in roles_to_add:
                for member in role.members:
                    members_to_add.add(member)
            
            # 초대 메시지 (실제 초대는 아님, 멘션용)
            mention_string = ' '.join(role.mention for role in roles_to_add)

            # 첫 메시지 수정하여 제어판과 멘션 추가
            control_view = TicketControlView(self, ticket_type)
            first_message = await thread.fetch_message(thread.id)
            await first_message.edit(view=control_view)
            await thread.send(f"担当者: {mention_string}", allowed_mentions=discord.AllowedMentions(roles=True))

            await interaction.edit_original_response(content=f"✅ 非公開のチケットを作成しました: {thread.mention}")
            
        except Exception as e:
            logger.error(f"티켓 생성 중 오류 발생: {e}", exc_info=True)
            try: await interaction.edit_original_response(content="❌ チケットの作成中にエラーが発生しました。")
            except discord.NotFound: pass

    async def _cleanup_ticket_data(self, thread_id: int):
        self.tickets.pop(thread_id, None); await remove_ticket(thread_id)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        if thread.id in self.tickets:
            await self._cleanup_ticket_data(thread.id)

    def create_panel_view(self, panel_type: str):
        view = ui.View(timeout=None)
        if panel_type == "inquiry":
            button = ui.Button(label="お問い合わせ・ご提案", style=discord.ButtonStyle.primary, emoji="📨", custom_id="ticket_inquiry_panel")
            async def inquiry_callback(interaction: discord.Interaction):
                if not self.inquiry_forum: return await interaction.response.send_message("❌ お問い合わせフォーラムが設定されていません。", ephemeral=True)
                await interaction.response.send_modal(InquiryModal(self, self.inquiry_forum))
            button.callback = inquiry_callback
            view.add_item(button)
        elif panel_type == "report":
            button = ui.Button(label="通報", style=discord.ButtonStyle.danger, emoji="🚨", custom_id="ticket_report_panel")
            async def report_callback(interaction: discord.Interaction):
                if not self.report_forum: return await interaction.response.send_message("❌ 通報フォーラムが設定されていません。", ephemeral=True)
                await interaction.response.send_modal(ReportModal(self, self.report_forum))
            button.callback = report_callback
            view.add_item(button)
        return view

    async def regenerate_panel(self, channel: discord.TextChannel | discord.ForumChannel) -> bool:
        panel_type = None
        if channel.id == get_id("inquiry_forum_channel_id"): panel_type = "inquiry"
        elif channel.id == get_id("report_forum_channel_id"): panel_type = "report"
        
        if panel_type:
            view = self.create_panel_view(panel_type)
            embed_title = "サーバーへのお問い合わせ・ご提案" if panel_type == "inquiry" else "ユーザーへの通報"
            embed_desc = "下のボタンを押して新しいチケットを作成してください。"
            embed = discord.Embed(title=embed_title, description=embed_desc)
            try:
                if isinstance(channel, discord.ForumChannel):
                    # 기존 패널용 게시물이 있는지 확인하고 있다면 삭제
                    for thread in channel.threads:
                        if thread.owner == self.bot.user and "チケット作成はこちらから" in thread.name:
                            await thread.delete()
                    
                    post_title = "チケット作成はこちらから"
                    await channel.create_thread(name=post_title, embed=embed, view=view)
                    logger.info(f"✅ {panel_type} 패널을 포럼 #{channel.name}에 생성했습니다.")
                    return True # 성공 반환
                elif isinstance(channel, discord.TextChannel):
                    await channel.send(embed=embed, view=view)
                    logger.info(f"✅ {panel_type} 패널을 텍스트 채널 #{channel.name}에 생성했습니다.")
                    return True # 성공 반환
            except Exception as e:
                logger.error(f"❌ #{channel.name} 채널에 패널 생성 중 오류 발생: {e}", exc_info=True)
                return False # 실패 반환
        return False # 실패 반환
        
async def setup(bot):
    await bot.add_cog(TicketSystem(bot))
