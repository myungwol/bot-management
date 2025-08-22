# bot-management/cogs/server/LevelSystem.py

import discord
from discord.ext import commands
from discord import ui
import logging
from typing import Optional

from utils.database import supabase, get_panel_id, save_panel_id

logger = logging.getLogger(__name__)

def create_xp_bar(current_xp: int, required_xp: int, length: int = 10) -> str:
    """경험치 바 문자열을 생성합니다."""
    if required_xp <= 0:
        # 0으로 나누는 것을 방지하고, 최대 레벨 등의 상황을 표시
        return "▓" * length
    
    progress = min(current_xp / required_xp, 1.0)
    
    filled_length = int(length * progress)
    bar = '▓' * filled_length + '░' * (length - filled_length)
    return f"[{bar}]"

class LevelCheckView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @ui.button(label="自分のレベルを確認", style=discord.ButtonStyle.primary, emoji="📊", custom_id="level_check_button")
    async def check_level_button(self, interaction: discord.Interaction, button: ui.Button):
        # [✅ 레벨 시스템] 버튼 클릭 시 모두에게 보이도록 ephemeral=False 설정
        await interaction.response.defer(ephemeral=False)
        
        user = interaction.user
        
        try:
            # 1. 유저 레벨 정보 가져오기
            level_res = await supabase.table('user_levels').select('*').eq('user_id', user.id).maybe_single().execute()
            user_level_data = level_res.data if level_res.data else {'level': 1, 'xp': 0}
            current_level = user_level_data['level']
            total_xp = user_level_data['xp']

            # 2. 현재 레벨과 다음 레벨에 필요한 *총* 경험치 가져오기
            xp_res_next = await supabase.rpc('get_xp_for_level', {'target_level': current_level}).execute()
            xp_for_next_level = xp_res_next.data

            # 3. 현재 레벨이 시작되는 시점의 *총* 경험치 가져오기
            # 레벨 1인 경우 시작 경험치는 0입니다.
            xp_at_level_start = 0
            if current_level > 1:
                xp_res_prev = await supabase.rpc('get_xp_for_level', {'target_level': current_level - 1}).execute()
                xp_at_level_start = xp_res_prev.data
            
            # 4. 현재 레벨 구간에서의 경험치 계산
            xp_in_current_level = total_xp - xp_at_level_start
            required_xp_for_this_level = xp_for_next_level - xp_at_level_start

            # 5. 유저 직업 정보 가져오기
            job_res = await supabase.table('user_jobs').select('jobs(job_name)').eq('user_id', user.id).maybe_single().execute()
            job_name = job_res.data['jobs']['job_name'] if job_res.data and job_res.data.get('jobs') else "一般住民"

            # 6. 임베드 생성
            embed = discord.Embed(
                title=f"{user.display_name}のステータス",
                color=user.color or discord.Color.blue()
            )
            if user.display_avatar:
                embed.set_thumbnail(url=user.display_avatar.url)
                
            embed.add_field(name="レベル", value=f"**Lv. {current_level}**", inline=True)
            embed.add_field(name="職業", value=f"**{job_name}**", inline=True)
            
            xp_bar = create_xp_bar(xp_in_current_level, required_xp_for_this_level)
            embed.add_field(
                name="経験値",
                value=f"`{xp_in_current_level:,} / {required_xp_for_this_level:,}`\n{xp_bar}",
                inline=False
            )
            embed.set_footer(text=f"次のレベルまでの総経験値: {xp_for_next_level:,}")
            
            await interaction.followup.send(embed=embed)
        
        except Exception as e:
            logger.error(f"레벨 확인 중 오류 발생 (유저: {user.id}): {e}", exc_info=True)
            await interaction.followup.send("❌ ステータス情報の読み込み中にエラーが発生しました。", ephemeral=True)


class LevelSystem(commands.Cog):
    PANEL_KEY = "panel_level_check"

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # 봇 재시작 시 View가 계속 동작하도록 등록
        self.bot.add_view(LevelCheckView())
        logger.info("LevelSystem Cog가 성공적으로 초기화되었습니다.")
        
    async def regenerate_panel(self, channel: discord.TextChannel, **kwargs):
        # 기존 패널 삭제 로직
        if panel_info := get_panel_id(self.PANEL_KEY):
            try:
                msg = await self.bot.get_channel(panel_info['channel_id']).fetch_message(panel_info['message_id'])
                await msg.delete()
            except (discord.NotFound, AttributeError, discord.Forbidden):
                pass
        
        embed = discord.Embed(
            title="📊 レベル確認",
            description="下のボタンを押して、ご自身の現在のレベルと経験値を確認できます。",
            color=0x5865F2
        )
        view = LevelCheckView()
        
        message = await channel.send(embed=embed, view=view)
        await save_panel_id(self.PANEL_KEY, message.id, channel.id)
        logger.info(f"✅ レベル確認パネルを #{channel.name} に設置しました。")
    
    # (향후 여기에 전직 관련 명령어나 리스너 추가)

async def setup(bot: commands.Bot):
    await bot.add_cog(LevelSystem(bot))
