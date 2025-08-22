# bot-management/cogs/server/LevelSystem.py

import discord
from discord.ext import commands, tasks
from discord import ui
import logging
import asyncio
import time
import math
from typing import Optional, Dict, List, Any

from utils.database import supabase, get_panel_id, save_panel_id, get_id, get_config, get_cooldown, set_cooldown

logger = logging.getLogger(__name__)

# --- Helper Functions ---
def create_xp_bar(current_xp: int, required_xp: int, length: int = 10) -> str:
    if required_xp <= 0: return "▓" * length
    progress = min(current_xp / required_xp, 1.0)
    filled_length = int(length * progress)
    bar = '▓' * filled_length + '░' * (length - filled_length)
    return f"[{bar}]"

# --- UI Views ---

class RankingView(ui.View):
    def __init__(self, user: discord.Member, total_users: int):
        super().__init__(timeout=180)
        self.user = user
        self.current_page = 0
        self.users_per_page = 10
        self.total_pages = math.ceil(total_users / self.users_per_page)

    async def update_view(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = await self.build_embed()
        self.update_buttons()
        await interaction.edit_original_response(embed=embed, view=self)
        
    def update_buttons(self):
        prev_button = next((child for child in self.children if isinstance(child, ui.Button) and child.custom_id == "prev_page"), None)
        next_button = next((child for child in self.children if isinstance(child, ui.Button) and child.custom_id == "next_page"), None)
        
        if prev_button: prev_button.disabled = self.current_page == 0
        if next_button: next_button.disabled = self.current_page >= self.total_pages - 1

    async def build_embed(self) -> discord.Embed:
        offset = self.current_page * self.users_per_page
        res = await supabase.table('user_levels').select('user_id, level, xp', count='exact').order('xp', desc=True).range(offset, offset + self.users_per_page - 1).execute()

        embed = discord.Embed(title="👑 サーバーランキング", color=0xFFD700)
        
        rank_list = []
        if res and res.data:
            for i, user_data in enumerate(res.data):
                rank = offset + i + 1
                # user_id가 문자열일 경우를 대비해 int로 변환
                member = self.user.guild.get_member(int(user_data['user_id']))
                name = member.display_name if member else f"ID: {user_data['user_id']}"
                rank_list.append(f"`{rank}.` {name} - **Lv.{user_data['level']}** (`{user_data['xp']:,} XP`)")
        
        embed.description = "\n".join(rank_list) if rank_list else "まだランキング情報がありません。"
        embed.set_footer(text=f"ページ {self.current_page + 1} / {self.total_pages}")
        return embed

    @ui.button(label="◀", style=discord.ButtonStyle.secondary, custom_id="prev_page", disabled=True)
    async def prev_page(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
        await self.update_view(interaction)

    @ui.button(label="▶", style=discord.ButtonStyle.secondary, custom_id="next_page")
    async def next_page(self, interaction: discord.Interaction, button: ui.Button):
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
        await self.update_view(interaction)

    @ui.button(label="自分の順位へ", style=discord.ButtonStyle.primary, emoji="👤", custom_id="my_rank")
    async def go_to_my_rank(self, interaction: discord.Interaction, button: ui.Button):
        my_rank_res = await supabase.rpc('get_user_rank', {'p_user_id': self.user.id}).execute()
        if my_rank_res and my_rank_res.data:
            my_rank = my_rank_res.data
            self.current_page = (my_rank - 1) // self.users_per_page
            await self.update_view(interaction)
        else:
            await interaction.response.send_message("❌ 自分の順位情報を取得できませんでした。", ephemeral=True)


class LevelPanelView(ui.View):
    def __init__(self, cog_instance: 'LevelSystem'):
        super().__init__(timeout=None)
        self.cog = cog_instance

    @ui.button(label="ステータス確認", style=discord.ButtonStyle.primary, emoji="📊", custom_id="level_check_button")
    async def check_level_button(self, interaction: discord.Interaction, button: ui.Button):
        user = interaction.user
        user_id_str = str(user.id)
        cooldown_key = "level_check_cooldown"
        cooldown_seconds = 60

        last_used = await get_cooldown(user_id_str, cooldown_key)
        if time.time() - last_used < cooldown_seconds:
            remaining = int(cooldown_seconds - (time.time() - last_used))
            await interaction.response.send_message(f"⏳ このボタンはクールダウン中です。あと`{remaining}`秒お待ちください。", ephemeral=True)
            return
            
        await interaction.response.defer()
        
        try:
            await set_cooldown(user_id_str, cooldown_key)
            
            # [UI 복원] xp_logs를 함께 조회하여 경험치 획득 내역을 가져옵니다.
            level_res, job_res, xp_logs_res = await asyncio.gather(
                supabase.table('user_levels').select('*').eq('user_id', user.id).maybe_single().execute(),
                supabase.table('user_jobs').select('jobs(*)').eq('user_id', user.id).maybe_single().execute(),
                supabase.table('xp_logs').select('source, xp_amount').eq('user_id', user.id).execute()
            )

            user_level_data = level_res.data if level_res and level_res.data else {'level': 1, 'xp': 0}
            current_level, total_xp = user_level_data['level'], user_level_data['xp']

            xp_for_next_level_res = await supabase.rpc('get_xp_for_level', {'target_level': current_level + 1}).execute()
            xp_for_next_level = xp_for_next_level_res.data if xp_for_next_level_res.data is not None else total_xp + 1

            xp_at_level_start_res = await supabase.rpc('get_xp_for_level', {'target_level': current_level}).execute()
            xp_at_level_start = xp_at_level_start_res.data if xp_at_level_start_res.data is not None else 0
            
            xp_in_current_level = total_xp - xp_at_level_start
            required_xp_for_this_level = xp_for_next_level - xp_at_level_start

            job_system_config = get_config("JOB_SYSTEM_CONFIG", {})
            
            job_name = "なし"
            job_role_mention = ""
            job_role_map = job_system_config.get("JOB_ROLE_MAP", {})
            if job_res and job_res.data and job_res.data.get('jobs'):
                job_data = job_res.data['jobs']
                job_name = job_data['job_name']
                if role_key := job_role_map.get(job_data['job_key']):
                    if role_id := get_id(role_key):
                        job_role_mention = f"<@&{role_id}>"

            level_tier_roles = job_system_config.get("LEVEL_TIER_ROLES", [])
            tier_role_mention = ""
            for tier in sorted(level_tier_roles, key=lambda x: x['level'], reverse=True):
                if current_level >= tier['level']:
                    if role_id := get_id(tier['role_key']):
                        tier_role_mention = f"<@&{role_id}>"
                        break
            
            # [UI 복원] 경험치 획득 내역을 집계하는 로직
            source_map = {'chat': '💬 チャット', 'voice': '🎙️ VC参加', 'fishing': '🎣 釣り', 'farming': '🌾 農業'}
            aggregated_xp = {v: 0 for v in source_map.values()}
            if xp_logs_res and xp_logs_res.data:
                for log in xp_logs_res.data:
                    source_name = source_map.get(log['source'], log['source'])
                    if source_name in aggregated_xp:
                        aggregated_xp[source_name] += log['xp_amount']
            
            details = [f"> {source}: `{amount:,} XP`" for source, amount in aggregated_xp.items()]
            xp_details_text = "\n".join(details) if details else "まだ経験値を獲得していません。"

            # [UI 복원] 상세한 정보가 포함된 Embed 메시지 구성
            embed = discord.Embed(title=f"{user.mention}のステータス", color=user.color or discord.Color.blue())
            if user.display_avatar:
                embed.set_thumbnail(url=user.display_avatar.url)
            
            embed.add_field(name="レベル", value=f"**Lv. {current_level}**", inline=False)
            embed.add_field(name="等級", value=tier_role_mention or "`かけだし住民`", inline=True)
            embed.add_field(name="職業", value=job_role_mention or "`なし`", inline=True)
            
            xp_bar = create_xp_bar(xp_in_current_level, required_xp_for_this_level)
            embed.add_field(name="経験値", value=f"`{xp_in_current_level:,} / {required_xp_for_this_level:,}`\n{xp_bar}", inline=False)
            
            embed.add_field(name="🏆 総獲得経験値", value=f"`{total_xp:,} XP`", inline=False)
            embed.add_field(name="📊 経験値獲得の内訳", value=xp_details_text, inline=False)
            
            await interaction.followup.send(embed=embed)
            
            if isinstance(interaction.channel, discord.TextChannel):
                await asyncio.sleep(1) 
                # [호환성 수정] 작동하는 파일의 함수 시그니처에 맞게 panel_key 인자를 추가합니다.
                await self.cog.regenerate_panel(interaction.channel, panel_key="panel_level_check")

        except Exception as e:
            logger.error(f"레벨 확인 중 오류 발생 (유저: {user.id}): {e}", exc_info=True)
            await interaction.followup.send("❌ ステータス情報の読み込み中にエラーが発生しました。", ephemeral=True)

    @ui.button(label="ランキング確認", style=discord.ButtonStyle.secondary, emoji="👑", custom_id="show_ranking_button")
    async def show_ranking_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            count_res = await supabase.table('user_levels').select('user_id', count='exact').execute()
            total_users = count_res.count if count_res and count_res.count is not None else 0

            if total_users == 0:
                await interaction.followup.send("まだランキング情報がありません。", ephemeral=True)
                return

            view = RankingView(interaction.user, total_users)
            embed = await view.build_embed()
            view.update_buttons()
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"랭킹 표시 중 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ ランキング情報の読み込み中にエラーが発生しました。", ephemeral=True)

class LevelSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(LevelPanelView(self))
        self.check_advancement_requests.start()
        self.check_level_tier_updates.start()
        logger.info("LevelSystem Cog가 성공적으로 초기화되었습니다.")

    def cog_unload(self):
        self.check_advancement_requests.cancel()
        self.check_level_tier_updates.cancel()
        
    async def load_configs(self):
        pass

    @tasks.loop(seconds=15.0)
    async def check_advancement_requests(self):
        try:
            res = await supabase.table('bot_configs').select('config_key, config_value').like('config_key', 'job_advancement_request_%').execute()
            if not res or not res.data: return

            keys_to_delete = [req['config_key'] for req in res.data]
            
            if keys_to_delete:
                await supabase.table('bot_configs').delete().in_('config_key', keys_to_delete).execute()
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

            keys_to_delete = [req['config_key'] for req in res.data]
            
            for req in res.data:
                user_id = int(req['config_key'].split('_')[-1])
                new_level = req['config_value'].get('level', 0)
                
                user_member = None
                for guild in self.bot.guilds:
                    if member := guild.get_member(user_id):
                        user_member = member; break
                
                if user_member:
                    await self.update_level_tier_role(user_member, new_level)
            
            if keys_to_delete:
                await supabase.table('bot_configs').delete().in_('config_key', keys_to_delete).execute()
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

    async def regenerate_panel(self, channel: discord.TextChannel, panel_key: str = "panel_level_check") -> bool:
        try:
            panel_info = get_panel_id(panel_key)
            if panel_info and panel_info.get('message_id'):
                try:
                    original_channel = self.bot.get_channel(panel_info.get('channel_id')) or channel
                    msg = await original_channel.fetch_message(panel_info['message_id'])
                    await msg.delete()
                except (discord.NotFound, discord.Forbidden):
                    pass
            
            embed = discord.Embed(title="📊 レベル＆ランキング", description="下のボタンでご自身のレベルを確認したり、サーバーのランキングを見ることができます。", color=0x5865F2)
            view = LevelPanelView(self)
            
            message = await channel.send(embed=embed, view=view)
            await save_panel_id(panel_key, message.id, channel.id)
            logger.info(f"✅ 「{panel_key}」パネルを #{channel.name} に再設置しました。")
            return True
        except Exception as e:
            logger.error(f"「{panel_key}」パネルの再設置中にエラー: {e}", exc_info=True)
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(LevelSystem(bot))
