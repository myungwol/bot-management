# bot-management/cogs/server/LevelSystem.py

import discord
from discord.ext import commands
from discord import ui
import logging
from typing import Optional, Dict, List, Any

from utils.database import supabase, get_panel_id, save_panel_id, get_id
from utils.helpers import format_embed_from_db

logger = logging.getLogger(__name__)

# --- Helper Functions ---
def create_xp_bar(current_xp: int, required_xp: int, length: int = 10) -> str:
    if required_xp <= 0:
        return "▓" * length
    progress = min(current_xp / required_xp, 1.0)
    filled_length = int(length * progress)
    bar = '▓' * filled_length + '░' * (length - filled_length)
    return f"[{bar}]"

# --- 전직 프로세스 관리 클래스 ---
class JobAdvancement:
    def __init__(self, bot: commands.Bot, user: discord.Member, interaction: discord.Interaction):
        self.bot = bot
        self.user = user
        self.original_interaction = interaction
        self.thread: Optional[discord.Thread] = None
        self.current_message: Optional[discord.Message] = None
        self.user_level = 0
        self.current_job_key: Optional[str] = None
        self.next_tier = 1

    async def start_process(self):
        # 1. 전직 가능 여부 확인
        can_advance, reason = await self.check_advancement_eligibility()
        if not can_advance:
            await self.original_interaction.followup.send(f"❌ {reason}", ephemeral=True)
            return

        # 2. 전용 스레드 생성
        self.thread = await self.original_interaction.channel.create_thread(
            name=f"📜｜{self.user.display_name}さんの転職手続き",
            type=discord.ChannelType.private_thread,
            invitable=False
        )
        await self.thread.add_user(self.user)
        await self.original_interaction.followup.send(f"✅ 転職手続きを開始します。{self.thread.mention} を確認してください。", ephemeral=True)

        # 3. 1차 직업 선택 시작
        await self.show_job_selection()

    async def check_advancement_eligibility(self) -> (bool, str):
        level_res = await supabase.table('user_levels').select('level').eq('user_id', self.user.id).maybe_single().execute()
        self.user_level = level_res.data['level'] if level_res.data else 1

        job_res = await supabase.table('user_jobs').select('jobs(job_key, tier)').eq('user_id', self.user.id).maybe_single().execute()
        
        if job_res.data:
            self.current_job_key = job_res.data['jobs']['job_key']
            current_tier = job_res.data['jobs']['tier']
            self.next_tier = current_tier + 1
            if self.next_tier > 2:
                return False, "すでに最終転職を完了しています。"
            
            # 2차 전직 레벨 확인
            if self.user_level < 100:
                return False, f"2次転職にはレベル100が必要です。(現在 Lv.{self.user_level})"
        else:
            # 1차 전직 레벨 확인
            if self.user_level < 50:
                return False, f"1次転職にはレベル50が必要です。(現在 Lv.{self.user_level})"
        
        return True, ""

    async def show_job_selection(self):
        # DB에서 현재 티어에 맞는 직업 목록 조회
        query = supabase.table('jobs').select('*').eq('tier', self.next_tier)
        if self.next_tier == 2:
            # 2차 전직 시, 현재 직업의 상위 직업만 보여줌
            query = query.eq('required_previous_job_key', self.current_job_key)
        
        jobs_res = await query.execute()
        available_jobs = jobs_res.data

        embed = discord.Embed(
            title=f"📜 {self.next_tier}次転職：職業選択",
            description="転職したい職業を選択してください。選択すると、その職業の詳細な能力を選択する段階に進みます。",
            color=0x3498DB
        )
        view = JobSelectView(self, available_jobs)
        
        self.current_message = await self.thread.send(embed=embed, view=view)

    async def show_ability_selection(self, selected_job: Dict[str, Any]):
        # 선택된 직업의 능력 목록 조회
        abilities_res = await supabase.table('job_abilities').select('*').eq('job_key', selected_job['job_key']).eq('tier', self.next_tier).execute()
        available_abilities = abilities_res.data

        embed = discord.Embed(
            title=f"✨ {selected_job['job_name']}：能力選択",
            description=f"{self.next_tier}次転職の能力を1つ選択してください。この選択は変更できません。",
            color=0x2ECC71
        )
        view = AbilitySelectView(self, selected_job, available_abilities)
        
        await self.current_message.edit(embed=embed, view=view)

    async def finalize_advancement(self, selected_job: Dict[str, Any], selected_ability: Dict[str, Any]):
        # DB에 직업과 능력 정보 저장
        await supabase.table('user_jobs').upsert({'user_id': self.user.id, 'job_key': selected_job['job_key']}).execute()
        await supabase.table('user_abilities').insert({'user_id': self.user.id, 'ability_key': selected_ability['ability_key']}).execute()
        
        # 스레드에 최종 안내
        embed = discord.Embed(
            title="🎉 転職完了！ 🎉",
            description=f"**{self.user.display_name}**さんが **{selected_job['job_name']}** に転職しました！\n"
                        f"새로운 능력 **[{selected_ability['ability_name']}]** を獲得しました。",
            color=0xFFD700
        )
        if self.user.display_avatar:
            embed.set_thumbnail(url=self.user.display_avatar.url)
        await self.current_message.edit(embed=embed, view=None)
        
        # 전직 로그 채널에 공지
        log_channel_id = get_id("job_log_channel_id")
        if log_channel_id and (log_channel := self.bot.get_channel(log_channel_id)):
            log_embed = embed.copy()
            log_embed.description += f"\n\n> {selected_ability['description']}"
            await log_channel.send(embed=log_embed)

        # 5초 후 스레드 삭제
        await self.thread.send("5秒後にこのスレッドは自動的に削除されます。")
        await asyncio.sleep(5)
        await self.thread.delete()

# --- UI Views ---
class JobSelectView(ui.View):
    def __init__(self, process: JobAdvancement, jobs: List[Dict[str, Any]]):
        super().__init__(timeout=300)
        self.process = process
        
        for job in jobs:
            button = ui.Button(label=job['job_name'], style=discord.ButtonStyle.primary, custom_id=f"job_{job['job_key']}")
            button.callback = self.on_select
            self.add_item(button)
            self.selected_job_data = {job['job_key']: job for job in jobs}

    async def on_select(self, interaction: discord.Interaction):
        await interaction.response.defer()
        job_key = interaction.data['custom_id'].split('_')[1]
        selected_job = self.selected_job_data[job_key]
        
        await self.process.show_ability_selection(selected_job)

class AbilitySelectView(ui.View):
    def __init__(self, process: JobAdvancement, job: Dict[str, Any], abilities: List[Dict[str, Any]]):
        super().__init__(timeout=300)
        self.process = process
        self.job = job
        self.ability_data = {ability['ability_key']: ability for ability in abilities}
        
        options = []
        for ability in abilities:
            options.append(discord.SelectOption(
                label=ability['ability_name'],
                value=ability['ability_key'],
                description=ability['description']
            ))
        
        select = ui.Select(placeholder="獲得する能力を選択...", options=options, custom_id="ability_select")
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        await interaction.response.defer()
        ability_key = interaction.data['values'][0]
        selected_ability = self.ability_data[ability_key]
        
        await self.process.finalize_advancement(self.job, selected_ability)

# --- Main Cog View & Class ---
class LevelCheckView(ui.View):
    def __init__(self, cog_instance: 'LevelSystem'):
        super().__init__(timeout=None)
        self.cog = cog_instance
    
    @ui.button(label="自分のレベルを確認", style=discord.ButtonStyle.primary, emoji="📊", custom_id="level_check_button")
    async def check_level_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=False)
        user = interaction.user
        try:
            level_res = await supabase.table('user_levels').select('*').eq('user_id', user.id).maybe_single().execute()
            user_level_data = level_res.data if level_res.data else {'level': 1, 'xp': 0}
            current_level, total_xp = user_level_data['level'], user_level_data['xp']

            xp_res_next = await supabase.rpc('get_xp_for_level', {'target_level': current_level}).execute()
            xp_for_next_level = xp_res_next.data

            xp_at_level_start = 0
            if current_level > 1:
                xp_res_prev = await supabase.rpc('get_xp_for_level', {'target_level': current_level - 1}).execute()
                xp_at_level_start = xp_res_prev.data
            
            xp_in_current_level = total_xp - xp_at_level_start
            required_xp_for_this_level = xp_for_next_level - xp_at_level_start

            job_res = await supabase.table('user_jobs').select('jobs(job_name)').eq('user_id', user.id).maybe_single().execute()
            job_name = job_res.data['jobs']['job_name'] if job_res.data and job_res.data.get('jobs') else "一般住民"

            embed = discord.Embed(title=f"{user.display_name}のステータス", color=user.color or discord.Color.blue())
            if user.display_avatar:
                embed.set_thumbnail(url=user.display_avatar.url)
            embed.add_field(name="レベル", value=f"**Lv. {current_level}**", inline=True)
            embed.add_field(name="職業", value=f"**{job_name}**", inline=True)
            xp_bar = create_xp_bar(xp_in_current_level, required_xp_for_this_level)
            embed.add_field(name="経験値", value=f"`{xp_in_current_level:,} / {required_xp_for_this_level:,}`\n{xp_bar}", inline=False)
            embed.set_footer(text=f"次のレベルまでの総経験値: {xp_for_next_level:,}")
            await interaction.followup.send(embed=embed)
        except Exception as e:
            logger.error(f"레벨 확인 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send("❌ ステータス情報の読み込み中にエラーが発生しました。", ephemeral=True)

    @ui.button(label="転職する", style=discord.ButtonStyle.success, emoji="📜", custom_id="job_advancement_button")
    async def advance_job_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True) # 시작 메시지는 본인에게만
        process = JobAdvancement(self.cog.bot, interaction.user, interaction)
        await process.start_process()


class LevelSystem(commands.Cog):
    PANEL_KEY = "panel_level_check"

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(LevelCheckView(self))
        logger.info("LevelSystem Cog가 성공적으로 초기화되었습니다.")
        
    async def regenerate_panel(self, channel: discord.TextChannel, **kwargs):
        if panel_info := get_panel_id(self.PANEL_KEY):
            try:
                msg = await self.bot.get_channel(panel_info['channel_id']).fetch_message(panel_info['message_id'])
                await msg.delete()
            except (discord.NotFound, AttributeError, discord.Forbidden):
                pass
        
        embed = discord.Embed(
            title="📊 レベル＆転職",
            description="下のボタンでご自身のレベルを確認したり、転職手続きを開始できます。",
            color=0x5865F2
        )
        view = LevelCheckView(self)
        message = await channel.send(embed=embed, view=view)
        await save_panel_id(self.PANEL_KEY, message.id, channel.id)
        logger.info(f"✅ レベル確認パネルを #{channel.name} に設置しました。")

async def setup(bot: commands.Bot):
    await bot.add_cog(LevelSystem(bot))
