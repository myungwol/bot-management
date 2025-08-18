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
    
    def __init__(self, cog: 'TicketSystem', interaction: discord.Interaction):
        super().__init__(timeout=None)
        self.cog = cog
        self.original_interaction = interaction # 나중에 응답을 보내기 위해 저장
        if self.cog.guild:
            inquiry_roles = [role for role_id in self.cog.inquiry_role_ids if (role := self.cog.guild.get_role(role_id))]
            if inquiry_roles:
                self.exclude_select = ui.Select(placeholder="この管理者を相談から除外します...", min_values=0, max_values=len(inquiry_roles),
                                                options=[discord.SelectOption(label=r.name, value=str(r.id)) for r in inquiry_roles])
                self.add_item(self.exclude_select)
                
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True) # defer는 모달의 상호작용에 대한 것
        try:
            excluded_role_ids = []
            if hasattr(self, 'exclude_select'):
                excluded_role_ids = [int(role_id_str) for role_id_str in self.exclude_select.values]
            # [수정] 원본 상호작용(버튼클릭)을 전달
            await self.cog.create_ticket(self.original_interaction, "inquiry", self.title_input.value, self.content_input.value, excluded_role_ids=excluded_role_ids)
        except Exception as e:
            logger.error(f"InquiryModal on_submit에서 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ チケットの作成中にエラーが発生しました。", ephemeral=True)

class ReportModal(ui.Modal, title="通報"):
    target_user = ui.TextInput(label="対象者", placeholder="通報する相手の名前を正確に入力してください。")
    content_input = ui.TextInput(label="内容", placeholder="通報内容を詳しく入力してください。(証拠SSなど)", style=discord.TextStyle.paragraph, max_length=1000)
    
    def __init__(self, cog: 'TicketSystem', interaction: discord.Interaction):
        super().__init__(timeout=None)
        self.cog = cog
        self.original_interaction = interaction
        
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            title = f"通報: {self.target_user.value}"
            content = f"**通報対象者:** {self.target_user.value}\n\n**内容:**\n{self.content_input.value}"
            await self.cog.create_ticket(self.original_interaction, "report", title, content)
        except Exception as e:
            logger.error(f"ReportModal on_submit에서 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ チケットの作成中にエラーが発生しました。", ephemeral=True)

# --- 제어판/패널 View ---
class TicketControlView(ui.View):
    def __init__(self, cog: 'TicketSystem', ticket_type: str):
        super().__init__(timeout=None)
        self.cog = cog; self.ticket_type = ticket_type
        
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # [수정] View 자체에서는 상호작용 유저가 누구인지 체크하지 않고, 각 버튼 콜백에서 처리
        return True

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

class TicketPanelView(ui.View):
    def __init__(self, cog: 'TicketSystem'):
        super().__init__(timeout=None)
        self.cog = cog
    @ui.button(label="お問い合わせ・ご提案", style=discord.ButtonStyle.primary, emoji="📨", custom_id="ticket_inquiry_panel")
    async def inquiry(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(InquiryModal(self.cog, interaction))
    @ui.button(label="通報", style=discord.ButtonStyle.danger, emoji="🚨", custom_id="ticket_report_panel")
    async def report(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ReportModal(self.cog, interaction))

# --- 메인 Cog ---
class TicketSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tickets: Dict[int, Dict] = {}
        self.master_role_ids: List[int] = []
        self.inquiry_role_ids: List[int] = []
        self.report_role_ids: List[int] = []
        self.guild: Optional[discord.Guild] = None
        logger.info("TicketSystem Cog가 성공적으로 초기화되었습니다.")

    @commands.Cog.listener()
    async def on_ready(self):
        await self.load_configs()
        await self.sync_tickets_from_db()

    async def load_configs(self):
        # [수정] 봇이 재시작해도 View가 계속 작동하도록 영구 View를 등록
        self.bot.add_view(TicketPanelView(self))
        self.bot.add_view(TicketControlView(self, "inquiry"))
        self.bot.add_view(TicketControlView(self, "report"))

        panel_channel_id = get_id("ticket_panel_channel_id")
        if panel_channel_id and (channel := self.bot.get_channel(panel_channel_id)):
            self.guild = channel.guild
        if self.guild:
            self.master_role_ids = [r_id for key in ["role_staff_village_chief", "role_staff_deputy_chief"] if (r_id := get_id(key))]
            self.inquiry_role_ids = [r_id for key in TICKET_INQUIRY_ROLES if (r_id := get_id(key))]
            self.report_role_ids = [r_id for key in TICKET_REPORT_ROLES if (r_id := get_id(key))]
            logger.info(f"[TicketSystem] 역할 로드 완료.")
        else:
            logger.warning("[TicketSystem] 티켓 패널 채널이 설정되지 않아 길드 정보를 불러올 수 없습니다.")
    
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

    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str, title: str, content: str, excluded_role_ids: List[int] = []):
        try:
            panel_channel = interaction.channel
            if not isinstance(panel_channel, discord.TextChannel):
                return await interaction.followup.send("❌ このチャンネルではチケットを作成できません。", ephemeral=True)
            
            role_ids_to_add = self.inquiry_role_ids if ticket_type == "inquiry" else self.report_role_ids
            final_role_ids = [r_id for r_id in role_ids_to_add if r_id not in excluded_role_ids]
            
            thread_name = f"[{'お問い合わせ' if ticket_type == 'inquiry' else '通報'}] {title}"
            thread = await panel_channel.create_thread(name=thread_name, type=discord.ChannelType.private_thread)
            
            await add_ticket(thread.id, interaction.user.id, interaction.guild.id, ticket_type)
            self.tickets[thread.id] = {"thread_id": thread.id, "owner_id": interaction.user.id, "ticket_type": ticket_type}
            
            # 스레드에 첫 메시지 전송
            embed = discord.Embed(title=title, description=content, color=discord.Color.blue() if ticket_type == "inquiry" else discord.Color.red())
            embed.set_author(name=f"{interaction.user.display_name} さんの{ticket_type}", icon_url=interaction.user.display_avatar.url)
            await thread.send(embed=embed)
            
            # [수정] 관리자와 작성자를 스레드에 멘션하여 초대
            roles_to_add = [interaction.guild.get_role(r_id) for r_id in final_role_ids if interaction.guild.get_role(r_id)]
            mention_string = ' '.join(role.mention for role in roles_to_add)
            
            # 제어판과 함께 멘션을 보내 참여를 유도
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
        
        view = None; embed = None
        # [수정] 통합 패널을 생성하도록 변경
        if panel_type == "ticket":
            embed = discord.Embed(title="お問い合わせ・通報", description="下のボタンを押して、必要な手続きを進めてください。")
            view = TicketPanelView(self)

        if view and embed:
            try:
                # 기존 패널 메시지 삭제
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
