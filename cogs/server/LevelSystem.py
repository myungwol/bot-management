# bot-management/cogs/server/LevelSystem.py

import discord
from discord.ext import commands, tasks
from discord import ui
import logging
import asyncio
import time
from typing import Optional, Dict, List, Any

from utils.database import supabase, get_panel_id, save_panel_id, get_id, get_config, save_config_to_db, get_cooldown, set_cooldown

logger = logging.getLogger(__name__)

# --- Helper Functions ---
def create_xp_bar(current_xp: int, required_xp: int, length: int = 10) -> str:
    if required_xp <= 0: return "▓" * length
    progress = min(current_xp / required_xp, 1.0)
    filled_length = int(length * progress)
    bar = '▓' * filled_length + '░' * (length - filled_length)
    return f"[{bar}]"

# --- 전직 프로세스 관리 클래스 ---
class JobAdvancement:
    def __init__(self, bot: commands.Bot, user: discord.Member, guild: discord.Guild, required_level: int, cog_instance: 'LevelSystem'):
        self.bot = bot
        self.user = user
        self.guild = guild
        self.required_level = required_level
        self.cog = cog_instance
        self.thread: Optional[discord.Thread] = None
        self.current_message: Optional[discord.Message] = None
        self.current_job_key: Optional[str] = None
        self.next_tier = 1 if required_level == 50 else 2

    async def start_process(self):
        try:
            panel_info = get_panel_id("panel_level_check")
            channel: Optional[discord.TextChannel] = self.guild.get_channel(panel_info['channel_id']) if panel_info and panel_info.get('channel_id') else self.guild.system_channel
            if not channel or not isinstance(channel, discord.TextChannel):
                logger.error(f"전직 스레드를 생성할 적절한 채널을 찾지 못했습니다. (서버: {self.guild.name})")
                return

            self.thread = await channel.create_thread(
                name=f"📜｜{self.user.display_name}さんの転職手続き",
                type=discord.ChannelType.private_thread, invitable=False
            )
            await self.thread.add_user(self.user)
            await self.thread.send(f"🎉 {self.user.mention}さん、レベル{self.required_level}達成おめでとうございます！\nこのスレッドで転職手続きを進めてください。")
            
            job_res = await supabase.table('user_jobs').select('jobs(job_key)').eq('user_id', self.user.id).maybe_single().execute()
            if job_res and job_res.data:
                self.current_job_key = job_res.data['jobs']['job_key']

            await self.show_job_selection()
        except Exception as e:
            logger.error(f"자동 전직 프로세스 시작 중 오류: {e}", exc_info=True)

    async def show_job_selection(self):
        try:
            query = supabase.table('jobs').select('*').eq('tier', self.next_tier)
            if self.next_tier == 2:
                query = query.eq('required_previous_job_key', self.current_job_key)
            
            jobs_res = await query.execute()
            if not jobs_res or not jobs_res.data:
                await self.thread.send("❌ 現在選択できる職業がありません。管理者に問い合わせてください。")
                return

            available_jobs = jobs_res.data
            embed = discord.Embed(title=f"📜 {self.next_tier}次転職：職業選択", description="転職したい職業を選択してください。", color=0x3498DB)
            view = JobSelectView(self, available_jobs)
            self.current_message = await self.thread.send(embed=embed, view=view)
        except Exception as e:
            logger.error(f"직업 선택 UI 표시 중 오류: {e}", exc_info=True)
            await self.thread.send("❌ 職業情報の読み込み中にエラーが発生しました。")

    async def show_ability_selection(self, selected_job: Dict[str, Any]):
        try:
            abilities_res = await supabase.table('job_abilities').select('*').eq('job_key', selected_job['job_key']).eq('tier', self.next_tier).execute()
            if not abilities_res or not abilities_res.data:
                await self.current_message.edit(content="❌ この職業で選択できる能力がありません。管理者に問い合わせてください。", embed=None, view=None)
                return

            available_abilities = abilities_res.data
            embed = discord.Embed(title=f"✨ {selected_job['job_name']}：能力選択", description=f"{self.next_tier}次転職の能力を1つ選択してください。", color=0x2ECC71)
            view = AbilitySelectView(self, selected_job, available_abilities)
            await self.current_message.edit(embed=embed, view=view)
        except Exception as e:
            logger.error(f"능력 선택 UI 표시 중 오류: {e}", exc_info=True)
            await self.current_message.edit(content="❌ 能力情報の読み込み中にエラーが発生しました。", embed=None, view=None)

    async def finalize_advancement(self, selected_job: Dict[str, Any], selected_ability: Dict[str, Any]):
        try:
            await supabase.table('user_jobs').upsert({'user_id': self.user.id, 'job_key': selected_job['job_key']}).execute()
            await supabase.table('user_abilities').insert({'user_id': self.user.id, 'ability_key': selected_ability['ability_key']}).execute()
            
            job_system_config = get_config("JOB_SYSTEM_CONFIG", {})
            job_role_map = job_system_config.get("JOB_ROLE_MAP", {})
            
            roles_to_remove = [self.guild.get_role(get_id(rk)) for rk in job_role_map.values() if get_id(rk)]
            await self.user.remove_roles(*[r for r in roles_to_remove if r], reason="転職による役割変更")

            new_role_key = job_role_map.get(selected_job['job_key'])
            if new_role_key and (new_role_id := get_id(new_role_key)):
                if new_role := self.guild.get_role(new_role_id):
                    await self.user.add_roles(new_role, reason="転職による役割付与")
            
            res = await supabase.table('user_levels').select('level').eq('user_id', self.user.id).maybe_single().execute()
            user_level = res.data['level'] if res and res.data else 1
            await self.cog.update_level_tier_role(self.user, user_level)

            embed = discord.Embed(title="🎉 転職完了！ 🎉", description=f"**{self.user.mention}**さんが **{selected_job['job_name']}** に転職しました！\n新しい能力 **[{selected_ability['ability_name']}]** を獲得しました。", color=0xFFD700)
            if self.user.display_avatar:
                embed.set_thumbnail(url=self.user.display_avatar.url)
            await self.current_message.edit(embed=embed, view=None)
            
            log_channel_id = get_id("job_log_channel_id")
            if log_channel_id and (log_channel := self.bot.get_channel(log_channel_id)):
                log_embed = embed.copy()
                log_embed.description += f"\n\n> {selected_ability['description']}"
                await log_channel.send(embed=log_embed)

            await self.thread.send("5秒後にこのスレッドは自動的に削除されます。")
            await asyncio.sleep(5)
            await self.thread.delete()
        except Exception as e:
            logger.error(f"전직 최종 처리 중 오류: {e}", exc_info=True)
            if self.current_message and not self.current_message.is_deleted():
                await self.current_message.edit(content="❌ 転職処理の最終段階でエラーが発生しました。管理者に報告してください。", embed=None, view=None)

# --- UI Views ---
class JobSelectView(ui.View):
    def __init__(self, process: JobAdvancement, jobs: List[Dict[str, Any]]):
        super().__init__(timeout=300)
        self.process = process
        self.selected_job_data = {job['job_key']: job for job in jobs}
        for job in jobs:
            button = ui.Button(label=job['job_name'], style=discord.ButtonStyle.primary, custom_id=f"job_{job['job_key']}")
            button.callback = self.on_select
            self.add_item(button)

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
        options = [discord.SelectOption(label=a['ability_name'], value=a['ability_key'], description=a['description']) for a in abilities]
        select = ui.Select(placeholder="獲得する能力を選択...", options=options, custom_id="ability_select")
        select.callback = self.on_select
        self.add_item(select)

    async def on_select(self, interaction: discord.Interaction):
        await interaction.response.defer()
        ability_key = interaction.data['values'][0]
        selected_ability = self.ability_data[ability_key]
        await self.process.finalize_advancement(self.job, selected_ability)

# --- Main Cog View & Class ---
class LevelPanelView(ui.View):
    def __init__(self, cog_instance: 'LevelSystem'):
        super().__init__(timeout=None)
        self.cog = cog_instance

    @ui.button(label="ステータス確認", style=discord.ButtonStyle.primary, emoji="📊", custom_id="level_check_button")
    async def check_level_button(self, interaction: discord.Interaction, button: ui.Button):
        user_id_str = str(interaction.user.id)
        cooldown_key = "level_check_cooldown"
        cooldown_seconds = 600

        last_used = await get_cooldown(user_id_str, cooldown_key)
        if time.time() - last_used < cooldown_seconds:
            remaining = int(cooldown_seconds - (time.time() - last_used))
            await interaction.response.send_message(f"⏳ このボタンはクールダウン中です。あと`{remaining}`秒お待ちください。", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=False)
        user = interaction.user
        
        try:
            await set_cooldown(user_id_str, cooldown_key)
            level_res, job_res, xp_logs_res = await asyncio.gather(
                supabase.table('user_levels').select('*').eq('user_id', user.id).maybe_single().execute(),
                supabase.table('user_jobs').select('jobs(*)').eq('user_id', user.id).maybe_single().execute(),
                supabase.table('xp_logs').select('source, xp_amount').eq('user_id', user.id).execute()
            )

            user_level_data = level_res.data if level_res and level_res.data else {'level': 1, 'xp': 0}
            current_level, total_xp = user_level_data['level'], user_level_data['xp']

            xp_for_next_level_res = await supabase.rpc('get_xp_for_level', {'target_level': current_level + 1}).execute()
            xp_for_next_level = xp_for_next_level_res.data if xp_for_next_level_res and xp_for_next_level_res.data is not None else total_xp + 1

            xp_at_level_start_res = await supabase.rpc('get_xp_for_level', {'target_level': current_level}).execute()
            xp_at_level_start = xp_at_level_start_res.data if xp_at_level_start_res and xp_at_level_start_res.data is not None else 0
            
            xp_in_current_level = total_xp - xp_at_level_start
            required_xp_for_this_level = xp_for_next_level - xp_at_level_start

            job_name = "一般住民"
            job_role_mention = ""
            if job_res and job_res.data and job_res.data.get('jobs'):
                job_data = job_res.data['jobs']
                job_name = job_data['job_name']
                job_system_config = get_config("JOB_SYSTEM_CONFIG", {})
                job_role_map = job_system_config.get("JOB_ROLE_MAP", {})
                if role_key := job_role_map.get(job_data['job_key']):
                    if role_id := get_id(role_key):
                        job_role_mention = f"<@&{role_id}>"

            source_map = {'chat': '💬 チャット', 'voice': '🎙️ VC参加', 'fishing': '🎣 釣り', 'farming': '🌾 農業'}
            aggregated_xp = {v: 0 for v in source_map.values()}
            if xp_logs_res and xp_logs_res.data:
                for log in xp_logs_res.data:
                    source_name = source_map.get(log['source'], log['source'])
                    if source_name in aggregated_xp:
                        aggregated_xp[source_name] += log['xp_amount']
            
            details = [f"> {source}: `{amount:,} XP`" for source, amount in aggregated_xp.items()]
            xp_details_text = "\n".join(details)

            embed = discord.Embed(title=f"{user.mention}のステータス", color=user.color or discord.Color.blue())
            if user.display_avatar:
                embed.set_thumbnail(url=user.display_avatar.url)
            
            embed.add_field(name="レベル", value=f"**Lv. {current_level}**", inline=True)
            embed.add_field(name="職業", value=f"**{job_name}** {job_role_mention}", inline=True)
            xp_bar = create_xp_bar(xp_in_current_level, required_xp_for_this_level)
            embed.add_field(name="経験値", value=f"`{xp_in_current_level:,} / {required_xp_for_this_level:,}`\n{xp_bar}", inline=False)
            embed.add_field(name="📊 経験値獲得の内訳", value=xp_details_text, inline=False)
            embed.add_field(name="🏆 総獲得経験値", value=f"`{total_xp:,} XP`", inline=False)
            
            view = ui.View()
            rank_button = ui.Button(label="ランキング確認", style=discord.ButtonStyle.secondary, emoji="👑")
            rank_button.callback = self.show_ranking
            view.add_item(rank_button)
            await interaction.followup.send(embed=embed, view=view)
        
        except Exception as e:
            logger.error(f"레벨 확인 중 오류 발생 (유저: {user.id}): {e}", exc_info=True)
            await interaction.followup.send("❌ ステータス情報の読み込み中にエラーが発生しました。", ephemeral=True)

    async def show_ranking(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            user_id = interaction.user.id
            my_rank_res = await supabase.rpc('get_user_rank', {'p_user_id': user_id}).execute()
            my_rank = my_rank_res.data if my_rank_res and my_rank_res.data is not None else "N/A"

            top_10_res = await supabase.table('user_levels').select('user_id, level, xp').order('xp', desc=True).limit(10).execute()
            
            embed = discord.Embed(title="👑 サーバーランキング TOP 10", color=0xFFD700)
            
            rank_list = []
            if top_10_res and top_10_res.data:
                for i, user_data in enumerate(top_10_res.data):
                    member = interaction.guild.get_member(user_data['user_id'])
                    name = member.display_name if member else f"ID: {user_data['user_id']}"
                    rank_list.append(f"`{i+1}.` {name} - **Lv.{user_data['level']}** (`{user_data['xp']:,} XP`)")

            embed.description = "\n".join(rank_list) if rank_list else "まだランキング情報がありません。"
            embed.set_footer(text=f"{interaction.user.display_name}さんの順位: {my_rank}位")
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"랭킹 확인 중 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ ランキング情報の読み込み中にエラーが発生しました。", ephemeral=True)

class LevelSystem(commands.Cog):
    PANEL_KEY = "panel_level_check"

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_channel_id: Optional[int] = None
        self.bot.add_view(LevelPanelView(self))
        self.check_advancement_requests.start()
        self.check_level_tier_updates.start()
        logger.info("LevelSystem Cog가 성공적으로 초기화되었습니다.")

    def cog_unload(self):
        self.check_advancement_requests.cancel()
        self.check_level_tier_updates.cancel()
        
    # [✅ 오류 수정] cog_load를 삭제하고, on_ready 이후에 호출될 load_configs를 만듭니다.
    async def load_configs(self):
        panel_info = get_panel_id(self.PANEL_KEY)
        if panel_info:
            self.panel_channel_id = panel_info.get('channel_id')
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not self.panel_channel_id or message.channel.id != self.panel_channel_id:
            return
        
        await asyncio.sleep(1)
        if isinstance(message.channel, discord.TextChannel):
            await self.regenerate_panel(message.channel)

    @tasks.loop(seconds=15.0)
    async def check_advancement_requests(self):
        try:
            res = await supabase.table('bot_configs').select('config_key, config_value').like('config_key', 'job_advancement_request_%').execute()
            if not res or not res.data:
                return

            for req in res.data:
                user_id = int(req['config_key'].split('_')[-1])
                req_level = req['config_value'].get('level', 0)
                
                guild_found, user_member = None, None
                for guild in self.bot.guilds:
                    if member := guild.get_member(user_id):
                        guild_found, user_member = guild, member
                        break
                
                if user_member:
                    logger.info(f"유저 {user_member.display_name}의 전직 요청(Lv.{req_level})을 감지하여 프로세스를 시작합니다.")
                    process = JobAdvancement(self.bot, user_member, guild_found, req_level, self)
                    await process.start_process()
                else:
                    logger.warning(f"전직 요청 유저(ID: {user_id})를 어느 서버에서도 찾을 수 없습니다.")
                
                await supabase.table('bot_configs').delete().eq('config_key', req['config_key']).execute()
        except Exception as e:
            logger.error(f"전직 요청 확인 중 오류: {e}", exc_info=True)

    @check_advancement_requests.before_loop
    async def before_check_advancement_requests(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=20.0)
    async def check_level_tier_updates(self):
        try:
            res = await supabase.table('bot_configs').select('config_key, config_value').like('config_key', 'level_tier_update_request_%').execute()
            if not res or not res.data: return

            for req in res.data:
                user_id = int(req['config_key'].split('_')[-1])
                new_level = req['config_value'].get('level', 0)
                
                user_member = None
                for guild in self.bot.guilds:
                    if member := guild.get_member(user_id):
                        user_member = member; break
                
                if user_member:
                    await self.update_level_tier_role(user_member, new_level)
                
                await supabase.table('bot_configs').delete().eq('config_key', req['config_key']).execute()
        except Exception as e:
            logger.error(f"레벨 등급 업데이트 확인 중 오류: {e}", exc_info=True)
            
    @check_level_tier_updates.before_loop
    async def before_check_level_tier_updates(self):
        await self.bot.wait_until_ready()
        
    async def update_level_tier_role(self, user: discord.Member, current_level: int):
        job_system_config = get_config("JOB_SYSTEM_CONFIG", {})
        level_tier_roles = job_system_config.get("LEVEL_TIER_ROLES", [])
        if not level_tier_roles: return
        
        role_key_to_add = None
        for tier in sorted(level_tier_roles, key=lambda x: x['level'], reverse=True):
            if current_level >= tier['level']:
                role_key_to_add = tier['role_key']
                break
        
        if not role_key_to_add: return
        
        all_tier_role_ids = {get_id(tier['role_key']) for tier in level_tier_roles if get_id(tier['role_key'])}
        roles_to_remove = [role for role in user.roles if role.id in all_tier_role_ids]
        
        if roles_to_remove:
            await user.remove_roles(*roles_to_remove, reason="レベル等級の変更")
        
        new_role_id = get_id(role_key_to_add)
        if new_role_id and (new_role := user.guild.get_role(new_role_id)):
            if new_role not in user.roles:
                await user.add_roles(new_role, reason="レベル等級の変更")
                logger.info(f"{user.display_name}さんの等級役割を「{new_role.name}」に更新しました。")

    async def regenerate_panel(self, channel: discord.TextChannel, **kwargs):
        self.panel_channel_id = channel.id
        if panel_info := get_panel_id(self.PANEL_KEY):
            if msg_id := panel_info.get('message_id'):
                try:
                    msg = await channel.fetch_message(msg_id)
                    await msg.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass
        
        embed = discord.Embed(title="📊 レベル＆転職", description="下のボタンでご自身のレベルを確認したり、ランキングを見ることができます。", color=0x5865F2)
        view = LevelPanelView(self)
        
        message = await channel.send(embed=embed, view=view)
        await save_panel_id(self.PANEL_KEY, message.id, channel.id)
        logger.info(f"✅ レベル確認パネルを #{channel.name} に再設置しました。")

async def setup(bot: commands.Bot):
    await bot.add_cog(LevelSystem(bot))
