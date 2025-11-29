# cogs/features/event_system.py

import discord
from discord import ui, app_commands
from discord.ext import commands
import logging
import random
import asyncio
from utils.database import join_event_participant, get_event_participants, clear_event_participants

logger = logging.getLogger(__name__)

class EventView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="이벤트 참가하기", style=discord.ButtonStyle.success, emoji="✋", custom_id="join_one_time_event")
    async def join_event(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)

        success = await join_event_participant(interaction.user.id)

        if not success:
            await interaction.followup.send("❌ 이미 명단에 등록되어 있습니다.", ephemeral=True)
            return

        await self.update_panel(interaction)
        await interaction.followup.send("✅ 명단에 등록되었습니다!", ephemeral=True)

    async def update_panel(self, interaction: discord.Interaction):
        participant_ids = await get_event_participants()
        total_count = len(participant_ids)
        
        if not participant_ids:
            mention_text = "아직 참가자가 없습니다."
        else:
            mentions = [f"<@{uid}>" for uid in participant_ids]
            
            rows = []
            chunk_size = 4
            for i in range(0, len(mentions), chunk_size):
                rows.append(" ".join(mentions[i:i + chunk_size]))
            
            full_text = "\n".join(rows)

            if len(full_text) > 3500:
                mention_text = full_text[:3500] + f"\n\n...외 **{total_count}**명 (명단이 너무 길어 생략됨)"
            else:
                mention_text = full_text

        try:
            original_msg = interaction.message
            if original_msg.embeds:
                embed = original_msg.embeds[0]
            else:
                embed = discord.Embed(title="🎉 이벤트 참가 신청", color=0x00FF00)
            
            embed.description = f"**[ 참가자 명단 ({total_count}명) ]**\n\n{mention_text}"
            
            await original_msg.edit(embed=embed, view=self)
            
        except Exception as e:
            logger.error(f"이벤트 패널 업데이트 실패: {e}")

class EventSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="이벤트시작", description="[관리자] 이벤트 패널을 생성합니다.")
    @app_commands.default_permissions(administrator=True)
    async def start_event(self, interaction: discord.Interaction):
        """이벤트 패널을 생성합니다."""
        embed = discord.Embed(title="🎉 1회용 이벤트 참가 신청", description="아래 버튼을 눌러 명단에 이름을 올리세요!", color=0xFEE75C)
        embed.set_footer(text="버튼을 누르면 즉시 명단에 추가됩니다.")
        await interaction.response.send_message(embed=embed, view=EventView())

    @app_commands.command(name="이벤트종료", description="[관리자] 이벤트 DB 데이터를 초기화합니다.")
    @app_commands.default_permissions(administrator=True)
    async def end_event(self, interaction: discord.Interaction):
        """DB 데이터를 초기화합니다."""
        await interaction.response.defer(ephemeral=True)
        await clear_event_participants()
        await interaction.followup.send("🗑️ 이벤트 참가자 데이터를 DB에서 삭제했습니다.", ephemeral=True)

    # ▼▼▼ [추가된 기능] 스테이지 랜덤 추첨 ▼▼▼
    @app_commands.command(name="추첨", description="[관리자] 현재 접속한 스테이지 채널에서 1명을 랜덤으로 추첨합니다.")
    @app_commands.default_permissions(administrator=True)
    async def draw_winner(self, interaction: discord.Interaction):
        """현재 접속 중인 음성/스테이지 채널에서 당첨자를 뽑습니다."""
        
        # 1. 관리자가 채널에 들어가 있는지 확인
        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.response.send_message("❌ 먼저 추첨을 진행할 **스테이지 채널**에 입장해주세요.", ephemeral=True)

        channel = interaction.user.voice.channel

        # 2. 후보자 추리기 (봇 제외, 자기 자신 제외)
        candidates = [
            member for member in channel.members 
            if not member.bot and member.id != interaction.user.id
        ]

        if not candidates:
            return await interaction.response.send_message(f"❌ **{channel.name}** 채널에 추첨할 유저가 없습니다.", ephemeral=True)

        # 3. 추첨 연출 및 결과 발표
        await interaction.response.send_message(f"🎤 **{channel.name}** 채널에서 추첨을 진행합니다...\n🥁 **두구두구두구...**")
        
        # 3초 딜레이 (긴장감 조성)
        await asyncio.sleep(3)

        winner = random.choice(candidates)
        
        embed = discord.Embed(title="🎉 축하합니다! 🎉", description=f"행운의 주인공은 바로... **{winner.mention}** 님입니다!", color=0xFFD700)
        embed.set_thumbnail(url=winner.display_avatar.url)
        embed.set_footer(text=f"총 {len(candidates)}명의 참가자 중 당첨")

        await interaction.edit_original_response(content=None, embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(EventSystem(bot))
