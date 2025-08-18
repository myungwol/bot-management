# cogs/features/ticket_system.py
import discord
from discord import ui
from discord.ext import commands
import logging
from typing import Dict, Any, List, Optional, Set
import asyncio

from utils.database import get_id, add_ticket, remove_ticket, get_all_tickets, remove_multiple_tickets
from utils.ui_defaults import TICKET_MASTER_ROLES, TICKET_STAFF_GENERAL_ROLES, TICKET_STAFF_SPECIFIC_ROLES, TICKET_REPORT_ROLES

logger = logging.getLogger(__name__)

# --- UI 클래스 ---
class TicketModal(ui.Modal):
    title_input = ui.TextInput(label="件名", placeholder="チケットの件名を入力してください。", max_length=100)
    content_input = ui.TextInput(label="内容", placeholder="詳細な内容を入力してください。", style=discord.TextStyle.paragraph, max_length=1000)
    def __init__(self, cog: 'TicketSystem', ticket_type: str, selected_roles: Set[discord.Role]):
        super().__init__(title=f"{'お問い合わせ' if ticket_type == 'inquiry' else '通報'} 内容入力", timeout=None)
        self.cog, self.ticket_type, self.selected_roles = cog, ticket_type, selected_roles
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            # 신고의 경우, 제목을 여기서 만듬
            final_title = self.title_input.value
            if self.ticket_type == 'report':
                final_title = f"通報: {self.title_input.value}" # 신고 모달에서는 '件名'이 '対象者'가 됨
            
            await self.cog.create_ticket(interaction, self.ticket_type, final_title, self.content_input.value, self.selected_roles)
        except Exception as e:
            logger.error(f"TicketModal on_submit에서 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ チケットの作成中にエラーが発生しました。", ephemeral=True)

# [수정] 신고 모달을 TicketModal을 상속받도록 변경하여 재사용
class ReportModal(TicketModal):
    def __init__(self, cog: 'TicketSystem', selected_roles: Set[discord.Role]):
        super().__init__(cog, "report", selected_roles)
        self.title = "通報 内容入力"
        self.children[0].label = "対象者"
        self.children[0].placeholder = "通報する相手の名前を正確に入力してください。"

class InquiryTargetSelectView(ui.View):
    def __init__(self, cog: 'TicketSystem'):
        super().__init__(timeout=180)
        self.cog, self.target_type, self.specific_roles = cog, None, set()
    @ui.select(placeholder="お問い合わせ先を選択してください...", options=[
        discord.SelectOption(label="村長・副村長へ", value="master"),
        discord.SelectOption(label="役場の職員全体へ", value="general"),
        discord.SelectOption(label="特定の担当者へ", value="specific")
    ])
    async def select_target(self, interaction: discord.Interaction, select: ui.Select):
        self.target_type = select.values[0]
        self.children[0].disabled = True
        if self.target_type == "specific":
            specific_roles = [role for key in TICKET_STAFF_SPECIFIC_ROLES if (role_id := get_id(key)) and (role := self.cog.guild.get_role(role_id))]
            if specific_roles: self.add_item(self.SpecificRoleSelect(specific_roles))
        await interaction.response.edit_message(view=self)
    class SpecificRoleSelect(ui.Select):
        def __init__(self, roles: List[discord.Role]):
            options = [discord.SelectOption(label=role.name, value=str(role.id)) for role in roles]
            super().__init__(placeholder="担当者を選択してください (複数選択可)...", min_values=1, max_values=len(options), options=options)
        async def callback(self, interaction: discord.Interaction):
            self.view.specific_roles = {interaction.guild.get_role(int(role_id)) for role_id in self.values}
            await interaction.response.defer()
    @ui.button(label="内容入力へ進む", style=discord.ButtonStyle.success, row=2)
    async def proceed(self, interaction: discord.Interaction, button: ui.Button):
        if not self.target_type: return await interaction.response.send_message("お問い合わせ先を選択してください。", ephemeral=True)
        if self.target_type == "specific" and not self.specific_roles: return await interaction.response.send_message("担当者を選択してください。", ephemeral=True)
        selected_roles: Set[discord.Role] = set()
        if self.target_type == "master": selected_roles.update(self.cog.master_roles)
        elif self.target_type == "general": selected_roles.update(self.cog.staff_general_roles)
        elif self.target_type == "specific": selected_roles.update(self.specific_roles)
        await interaction.response.send_modal(TicketModal(self.view.cog, "inquiry", selected_roles))
        await interaction.delete_original_response()

# [신규] 신고 시 경찰 포함 여부를 선택하는 View
class ReportTargetSelectView(ui.View):
    def __init__(self, cog: 'TicketSystem'):
        super().__init__(timeout=180)
        self.cog = cog
    
    @ui.button(label="✅ 交番さんを含める", style=discord.ButtonStyle.success)
    async def include_police(self, interaction: discord.Interaction, button: ui.Button):
        selected_roles = set(self.cog.report_roles)
        await interaction.response.send_modal(ReportModal(self.cog, selected_roles))
        await interaction.delete_original_response()
        
    @ui.button(label="❌ 交番さんを除外する", style=discord.ButtonStyle.danger)
    async def exclude_police(self, interaction: discord.Interaction, button: ui.Button):
        selected_roles = set() # 빈 집합 전달
        await interaction.response.send_modal(ReportModal(self.cog, selected_roles))
        await interaction.delete_original_response()

class TicketControlView(ui.View):
    def __init__(self, cog: 'TicketSystem', ticket_type: str):
        super().__init__(timeout=None)
        self.cog = cog
        self.ticket_type = ticket_type

    async def _check_master_permission(self, interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member): return False
        # [수정] Cog에 캐시된 Role 객체와 직접 비교하여 더 효율적으로 변경
        return any(role in interaction.user.roles for role in self.cog.master_roles)
        
    @ui.button(label="ロック", style=discord.ButtonStyle.secondary, emoji="🔒", custom_id="ticket_lock")
    async def lock(self, interaction: discord.Interaction, button: ui.Button):
        # [수정] 권한 확인을 _check_master_permission으로 통일
        if not await self._check_master_permission(interaction):
            return await interaction.response.send_message("❌ `村長`、`副村長`のみがこのボタンを使用できます。", ephemeral=True)
        
        thread = interaction.channel
        await interaction.response.send_message(f"✅ {interaction.user.mention}さんがこのチケットをロックしました。")
        await thread.edit(locked=True, archived=True, reason=f"{interaction.user.display_name}によるロック")
        
    @ui.button(label="削除", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="ticket_delete")
    async def delete(self, interaction: discord.Interaction, button: ui.Button):
        # [수정] 권한 확인을 _check_master_permission으로 통일
        if not await self._check_master_permission(interaction):
            return await interaction.response.send_message("❌ `村長`、`副村長`のみがこのボタンを使用できます。", ephemeral=True)
        
        await interaction.response.send_message(f"✅ 5秒後にこのチケットを削除します。")
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"{interaction.user.display_name}による削除")
        except discord.NotFound:
            pass
class TicketSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tickets: Dict[int, Dict] = {}
        self.master_roles: List[discord.Role] = []
        self.staff_general_roles: List[discord.Role] = []
        self.staff_specific_roles: List[discord.Role] = []
        self.report_roles: List[discord.Role] = []
        self.guild: Optional[discord.Guild] = None
        logger.info("TicketSystem Cog가 성공적으로 초기화되었습니다.")

    @commands.Cog.listener()
    async def on_ready(self):
        await self.load_configs()
        await self.sync_tickets_from_db()

    async def load_configs(self):
        self.bot.add_view(self.create_panel_view("inquiry"))
        self.bot.add_view(self.create_panel_view("report"))
        self.bot.add_view(TicketControlView(self, "inquiry"))
        self.bot.add_view(TicketControlView(self, "report"))
        panel_channel_id = get_id("inquiry_panel_channel_id") or get_id("report_panel_channel_id")
        if panel_channel_id and (channel := self.bot.get_channel(panel_channel_id)):
            self.guild = channel.guild
        if self.guild:
            self.master_roles = [role for key in TICKET_MASTER_ROLES if (role_id := get_id(key)) and (role := self.guild.get_role(role_id))]
            self.staff_general_roles = [role for key in TICKET_STAFF_GENERAL_ROLES if (role_id := get_id(key)) and (role := self.guild.get_role(role_id))]
            self.staff_specific_roles = [role for key in TICKET_STAFF_SPECIFIC_ROLES if (role_id := get_id(key)) and (role := self.guild.get_role(role_id))]
            self.report_roles = [role for key in TICKET_REPORT_ROLES if (role_id := get_id(key)) and (role := self.guild.get_role(role_id))]
            logger.info(f"[TicketSystem] 역할 로드 완료.")
        else:
            logger.warning("[TicketSystem] 티켓 패널 채널이 설정되지 않아 길드 정보를 불러올 수 없습니다.")
    
    def create_panel_view(self, panel_type: str):
        view = ui.View(timeout=None)
        if panel_type == "inquiry":
            button = ui.Button(label="お問い合わせ・ご提案", style=discord.ButtonStyle.primary, emoji="📨", custom_id="ticket_inquiry_panel")
            async def callback(interaction: discord.Interaction):
                await interaction.response.send_message("お問い合わせ先を選択してください。", view=InquiryTargetSelectView(self), ephemeral=True)
            button.callback = callback
            view.add_item(button)
        elif panel_type == "report":
            button = ui.Button(label="通報", style=discord.ButtonStyle.danger, emoji="🚨", custom_id="ticket_report_panel")
            async def callback(interaction: discord.Interaction):
                # [수정] 신고 버튼 클릭 시 ReportTargetSelectView를 보냄
                await interaction.response.send_message("この通報に`交番さん`を含めますか？", view=ReportTargetSelectView(self), ephemeral=True)
            button.callback = callback
            view.add_item(button)
        return view

    async def sync_tickets_from_db(self):
        db_tickets = await get_all_tickets()
        if not db_tickets: return
        zombie_ids = []
        for ticket_data in db_tickets:
            thread_id = ticket_data.get("thread_id")
            if self.guild and self.guild.get_thread(thread_id):
                self.tickets[thread_id] = ticket_data
            else:
                zombie_ids.append(thread_id)
        if zombie_ids: await remove_multiple_tickets(zombie_ids)

    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str, title: str, content: str, selected_roles: Set[discord.Role]):
        try:
            panel_channel = interaction.channel
            thread_name = f"[{'お問い合わせ' if ticket_type == 'inquiry' else '通報'}] {title}"
            thread = await panel_channel.create_thread(name=thread_name, type=discord.ChannelType.private_thread)
            await add_ticket(thread.id, interaction.user.id, interaction.guild.id, ticket_type)
            self.tickets[thread.id] = {"thread_id": thread.id, "owner_id": interaction.user.id, "ticket_type": ticket_type}
            embed = discord.Embed(title=title, description=content, color=discord.Color.blue() if ticket_type == "inquiry" else discord.Color.red())
            embed.set_author(name=f"{interaction.user.display_name} さんの{ticket_type}", icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None)
            await thread.send(embed=embed)
            
            final_roles_to_mention = set(self.master_roles) | selected_roles
            mention_string = ' '.join(role.mention for role in final_roles_to_mention)
            control_view = TicketControlView(self, ticket_type)
            await thread.send(f"{interaction.user.mention} {mention_string}\n**[チケット管理パネル]**", view=control_view, allowed_mentions=discord.AllowedMentions(users=True, roles=True))
            
            await interaction.followup.send(f"✅ 非公開のチケットを作成しました: {thread.mention}", ephemeral=True)
            
        except Exception as e:
            logger.error(f"티켓 생성 중 오류 발생: {e}", exc_info=True)
            try: await interaction.followup.send("❌ チケットの作成中にエラーが発生しました。", ephemeral=True)
            except discord.NotFound: pass

    async def _cleanup_ticket_data(self, thread_id: int):
        self.tickets.pop(thread_id, None); await remove_ticket(thread_id)

    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        if thread.id in self.tickets:
            await self._cleanup_ticket_data(thread.id)

    async def regenerate_panel(self, channel: discord.TextChannel, panel_type: str) -> bool:
        if not isinstance(channel, discord.TextChannel): return False
        view = self.create_panel_view(panel_type)
        embed = None
        if panel_type == "inquiry":
            embed = discord.Embed(title="サーバーへのお問い合わせ・ご提案", description="下のボタンを押して、サーバー運営へのご意見をお聞かせください。")
        elif panel_type == "report":
            embed = discord.Embed(title="ユーザーへの通報", description="サーバー内での迷惑行為や問題を発見した場合、下のボタンで通報してください。")
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
