# cogs/features/event_system.py

import discord
from discord import ui
from discord.ext import commands
import logging
from utils.database import join_event_participant, get_event_participants, clear_event_participants

logger = logging.getLogger(__name__)

class EventView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="이벤트 참가하기", style=discord.ButtonStyle.success, emoji="✋", custom_id="join_one_time_event")
    async def join_event(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)

        # 1. DB 저장 시도
        success = await join_event_participant(interaction.user.id)

        if not success:
            await interaction.followup.send("❌ 이미 명단에 등록되어 있습니다.", ephemeral=True)
            return

        # 2. 명단 업데이트 (패널 수정)
        await self.update_panel(interaction)
        await interaction.followup.send("✅ 명단에 등록되었습니다!", ephemeral=True)

    async def update_panel(self, interaction: discord.Interaction):
        """DB에서 명단을 다시 불러와 메시지를 수정함"""
        participant_ids = await get_event_participants()
        
        # 멘션 리스트 생성
        if not participant_ids:
            mention_text = "아직 참가자가 없습니다."
        else:
            mentions = [f"<@{uid}>" for uid in participant_ids]
            # 1줄에 1명씩 보기 좋게 출력하거나, 콤마로 연결
            mention_text = "\n".join(mentions)

        # 기존 임베드 가져오기 (없으면 새로 생성)
        try:
            original_msg = interaction.message
            if original_msg.embeds:
                embed = original_msg.embeds[0]
            else:
                embed = discord.Embed(title="🎉 이벤트 참가 신청", color=0x00FF00)
            
            # 설명란 업데이트
            embed.description = f"**[ 참가자 명단 ({len(participant_ids)}명) ]**\n\n{mention_text}"
            
            # 메시지 수정
            await original_msg.edit(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"이벤트 패널 업데이트 실패: {e}")

class EventSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="이벤트시작")
    @commands.has_permissions(administrator=True)
    async def start_event(self, ctx):
        """이벤트 패널을 생성합니다."""
        await ctx.message.delete()
        
        # 혹시 모를 이전 데이터 초기화 (선택사항, 필요하면 주석 해제)
        # await clear_event_participants()

        embed = discord.Embed(title="🎉 1회용 이벤트 참가 신청", description="아래 버튼을 눌러 명단에 이름을 올리세요!", color=0xFEE75C)
        embed.set_footer(text="버튼을 누르면 즉시 명단에 추가됩니다.")
        
        await ctx.send(embed=embed, view=EventView())

    @commands.command(name="이벤트종료")
    @commands.has_permissions(administrator=True)
    async def end_event(self, ctx):
        """(선택) DB 데이터를 초기화합니다."""
        await clear_event_participants()
        await ctx.send("🗑️ 이벤트 참가자 데이터를 DB에서 삭제했습니다.")

async def setup(bot: commands.Bot):
    await bot.add_cog(EventSystem(bot))
