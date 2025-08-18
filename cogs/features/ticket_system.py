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
class TicketModal(ui.Modal):
    title_input = ui.TextInput(label="件名", placeholder="チケットの件名を入力してください。", max_length=100)
    content_input = ui.TextInput(label="内容", placeholder="詳細な内容を入力してください。", style=discord.TextStyle.paragraph, max_length=1000)
    
    def __init__(self, cog: 'TicketSystem', ticket_type: str, selected_roles: List[discord.Role]):
        super().__init__(title=f"{'お問い合わせ' if ticket_type == 'inquiry' else '通報'} 内容入力", timeout=None)
        self.cog = cog
        self.ticket_type = ticket_type
        self.selected_roles = selected_roles # 사용자가 선택한 역할들을 저장

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            await self.cog.create_ticket(interaction, self.ticket_type, self.title_input.value, self.content_input.value, self.selected_roles)
        except Exception as e:
            logger.error(f"TicketModal on_submit에서 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ チケットの作成中にエラーが発生しました。", ephemeral=True)

# --- 역할 선택 View ---
class RoleSelectView(ui.View):
    def __init__(self, cog: 'TicketSystem', ticket_type: str):
        super().__init__(timeout=180)
        self.cog = cog
        self.ticket_type = ticket_type
        self.selected_roles: List[discord.Role] = []
        
        role_ids = self.cog.inquiry_role_ids if ticket_type == "inquiry" else self.cog.report_role_ids
        
        if self.cog.guild:
            allowed_roles = [role for role_id in role_ids if (role := self.cog.guild.get_role(role_id))]
            if allowed_roles:
                self.add_item(self.RoleSelectDropdown(allowed_roles))
        
        self.add_item(self.ProceedButton())
        
    class RoleSelectDropdown(ui.Select):
        def __init__(self, allowed_roles: List[discord.Role]):
            options = [discord.SelectOption(label=role.name, value=str(role.id)) for role in allowed_roles]
            super().__init__(placeholder="担当の管理者を選択してください...", min_values=1, max_values=len(options), options=options)
        
        async def callback(self, interaction: discord.Interaction):
            self.view.selected_roles = [interaction.guild.get_role(int(role_id)) for role_id in self.values]
            await interaction.response.defer()

    class ProceedButton(ui.Button):
        def __init__(self):
            super().__init__(label="内容入力へ進む", style=discord.ButtonStyle.success)
        
        async def callback(self, interaction: discord.Interaction):
            if not self.view.selected_roles:
                return await interaction.response.send_message("担当の管理者を選択してください。", ephemeral=True)
            await interaction.response.send_modal(TicketModal(self.view.cog, self.view.ticket_type, self.view.selected_roles))
            await interaction.delete_original_response()

# --- 제어판 View (이전과 동일) ---
class TicketControlView(ui.View):
    def __init__(self, cog: 'TicketSystem', ticket_type: str):
        super().__init__(timeout=None)
        self.cog = cog; self.ticket_type = ticket_type
    async def _check_master_permission(self, interaction: discord.Interaction) -> bool:
        if not isinstance(interaction.user, discord.Member): return False
        return any(role.id in self.cog.master_role_ids for role in interaction.user.roles)
    async def _check_handler_permission(self, interaction: discord.Interaction, ticket_type: str) -> bool:
        if not isinstance(interaction.user, discord.Member): return False
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
        self.inquiry_panel_channel: Optional[discord.TextChannel] = None
        self.report_panel_channel: Optional[discord.TextChannel] = None
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
        
        inquiry_channel_id = get_id("inquiry_panel_channel_id")
        if inquiry_channel_id: self.inquiry_panel_channel = self.bot.get_channel(inquiry_channel_id)
        if self.inquiry_panel_channel: self.guild = self.inquiry_panel_channel.guild
        
        report_channel_id = get_id("report_panel_channel_id")
        if report_channel_id: self.report_panel_channel = self.bot.get_channel(report_channel_id)
        if self.report_panel_channel and not self.guild: self.guild = self.report_panel_channel.guild

        if self.guild:
            self.master_role_ids = [r_id for key in ["role_staff_village_chief", "role_staff_deputy_chief"] if (r_id := get_id(key))]
            self.inquiry_role_ids = [r_id for key in TICKET_INQUIRY_ROLES if (r_id := get_id(key))]
            self.report_role_ids = [r_id for key in TICKET_REPORT_ROLES if (r_id := get_id(key))]
            logger.info(f"[TicketSystem] 역할 로드 완료.")
        else:
            logger.warning("[TicketSystem] 티켓 패널 채널이 설정되지 않아 길드 정보를 불러올 수 없습니다.")
    
    def create_panel_view(self, panel_type: str):
        view = ui.View(timeout=None)
        if panel_type == "inquiry":
            button = ui.Button(label="お問い合わせ・ご提案", style=discord.ButtonStyle.primary, emoji="📨", custom_id="ticket_inquiry_panel")
            async def callback(interaction: discord.Interaction):
                await interaction.response.send_message("担当の管理者を選択してください。", view=RoleSelectView(self, "inquiry"), ephemeral=True)
            button.callback = callback
            view.add_item(button)
        elif panel_type == "report":
            button = ui.Button(label="通報", style=discord.ButtonStyle.danger, emoji="🚨", custom_id="ticket_report_panel")
            async def callback(interaction: discord.Interaction):
                await interaction.response.send_message("担当の管理者を選択してください。", view=RoleSelectView(self, "report"), ephemeral=True)
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

    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str, title: str, content: str, selected_roles: List[discord.Role]):
        try:
            panel_channel = interaction.channel
            thread_name = f"[{'お問い合わせ' if ticket_type == 'inquiry' else '通報'}] {title}"
            thread = await panel_channel.create_thread(name=thread_name, type=discord.ChannelType.private_thread, auto_archive_duration=10080)
            
            await add_ticket(thread.id, interaction.user.id, interaction.guild.id, ticket_type)
            self.tickets[thread.id] = {"thread_id": thread.id, "owner_id": interaction.user.id, "ticket_type": ticket_type}
            
            embed = discord.Embed(title=title, description=content, color=discord.Color.blue() if ticket_type == "inquiry" else discord.Color.red())
            embed.set_author(name=f"{interaction.user.display_name} さんの{ticket_type}", icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None)
            await thread.send(embed=embed)
            
            mention_string = ' '.join(role.mention for role in selected_roles)
            control_view = TicketControlView(self, ticket_type)
            await thread.send(f"{interaction.user.mention} {mention_string}\n**[チケット管理パネル]**", view=control_view, allowed_mentions=discord.AllowedMentions(users=True, roles=True))
            
            await interaction.followup.send(f"✅ 非公開のチケットを作成しました: {thread.mention}", ephemeral=True)
            
        except discord.Forbidden:
            logger.error(f"티켓 생성 실패 (권한 부족): #{interaction.channel.name}")
            await interaction.followup.send(f"❌ チケットの作成に失敗しました。ボットに`#{interaction.channel.name}`チャンネルでスレッドを作成する権限があるか確認してください。", ephemeral=True)
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
