# cogs/economy/core.py (임베드 DB 연동 최종)

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import random
import asyncio
from collections import defaultdict
import logging
from typing import Optional, Dict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] %(message)s')
logger = logging.getLogger(__name__)

from utils.database import (
    get_wallet, update_wallet,
    CURRENCY_ICON, get_id, supabase, get_embed_from_db
)

CHAT_MESSAGE_REQUIREMENT = 10
CHAT_REWARD_RANGE = (5, 10)
VOICE_TIME_REQUIREMENT_MINUTES = 10
VOICE_REWARD_RANGE = (10, 15)

class TransferConfirmView(ui.View):
    # ... (이 클래스는 수정할 필요 없음, 그대로 유지) ...

# [신규] DB에서 불러온 임베드 데이터의 변수를 실제 값으로 채워주는 헬퍼 함수
def format_embed_data(data: dict, **kwargs) -> dict:
    # json.dumps와 .format을 사용하여 중첩된 딕셔너리/리스트 안의 모든 문자열 변수를 치환합니다.
    # .format(**kwargs)는 키워드 인자를 사용하여 문자열의 {key} 부분을 값으로 바꿉니다.
    json_str = json.dumps(data)
    formatted_str = json_str.format(**kwargs)
    return json.loads(formatted_str)

class EconomyCore(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.coin_log_channel_id: Optional[int] = None
        self.admin_role_id: Optional[int] = None
        self.user_chat_progress: Dict[int, int] = defaultdict(int)
        self.user_voice_progress: Dict[int, int] = defaultdict(int)
        self.voice_reward_loop.start()
        logger.info("EconomyCore Cog가 성공적으로 초기화되었습니다.")
        
    async def cog_load(self): await self.load_all_configs()
    async def load_all_configs(self):
        self.coin_log_channel_id = get_id("coin_log_channel_id")
        self.admin_role_id = get_id("role_admin_total")
        logger.info("[EconomyCore Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")
        
    def cog_unload(self): self.voice_reward_loop.cancel()
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None or message.content.startswith('/'): return
        user = message.author
        self.user_chat_progress[user.id] += 1
        if self.user_chat_progress[user.id] >= CHAT_MESSAGE_REQUIREMENT:
            self.user_chat_progress[user.id] = 0
            reward = random.randint(*CHAT_REWARD_RANGE)
            await update_wallet(user, reward)
            await self.log_coin_activity(user, reward, "チャット活動報酬")
            
    @tasks.loop(minutes=1)
    async def voice_reward_loop(self):
        try:
            for guild in self.bot.guilds:
                afk_ch_id = guild.afk_channel.id if guild.afk_channel else None
                for vc in guild.voice_channels:
                    if vc.id == afk_ch_id: continue
                    for member in vc.members:
                        if not member.bot and member.voice and not member.voice.self_deaf and not member.voice.self_mute:
                            self.user_voice_progress[member.id] += 1
                            if self.user_voice_progress[member.id] >= VOICE_TIME_REQUIREMENT_MINUTES:
                                self.user_voice_progress[member.id] = 0
                                reward = random.randint(*VOICE_REWARD_RANGE)
                                await update_wallet(member, reward)
                                await self.log_coin_activity(member, reward, "ボイスチャット活動報酬")
        except Exception as e: logger.error(f"음성 보상 루프 중 오류: {e}", exc_info=True)
        
    @voice_reward_loop.before_loop
    async def before_voice_reward_loop(self): await self.bot.wait_until_ready()
    
    # [수정] DB에서 임베드를 불러와 로그를 전송하도록 변경
    async def log_coin_activity(self, user: discord.Member, amount: int, reason: str):
        if not self.coin_log_channel_id or not (log_channel := self.bot.get_channel(self.coin_log_channel_id)): return
        
        embed_data = await get_embed_from_db("log_coin_gain")
        if not embed_data: return
        
        formatted_data = format_embed_data(
            embed_data,
            reason=reason,
            user_mention=user.mention,
            amount=f"{amount:,}",
            currency_icon=CURRENCY_ICON
        )
        embed = discord.Embed.from_dict(formatted_data)

        try: await log_channel.send(embed=embed)
        except Exception as e: logger.error(f"코인 활동 로그 전송 실패: {e}", exc_info=True)
        
    # [수정] DB에서 임베드를 불러와 로그를 전송하도록 변경
    async def log_coin_transfer(self, sender: discord.Member, recipient: discord.Member, amount: int):
        if not self.coin_log_channel_id or not (log_channel := self.bot.get_channel(self.coin_log_channel_id)): return

        embed_data = await get_embed_from_db("log_coin_transfer")
        if not embed_data: return

        formatted_data = format_embed_data(
            embed_data,
            sender_mention=sender.mention,
            recipient_mention=recipient.mention,
            amount=f"{amount:,}",
            currency_icon=CURRENCY_ICON
        )
        embed = discord.Embed.from_dict(formatted_data)
        
        try: await log_channel.send(embed=embed)
        except Exception as e: logger.error(f"코인 송금 로그 전송 실패: {e}", exc_info=True)
        
    # [수정] DB에서 임베드를 불러와 로그를 전송하도록 변경
    async def log_admin_action(self, admin: discord.Member, target: discord.Member, amount: int, action: str):
        if not self.coin_log_channel_id or not (log_channel := self.bot.get_channel(self.coin_log_channel_id)): return

        embed_data = await get_embed_from_db("log_coin_admin")
        if not embed_data: return
        
        # 금액에 따라 색상과 텍스트를 다르게 설정
        color = 0x3498DB if amount > 0 else 0xE74C3C
        amount_str = f"+{amount:,}" if amount > 0 else f"{amount:,}"

        formatted_data = format_embed_data(
            embed_data,
            action=action,
            target_mention=target.mention,
            amount=amount_str,
            currency_icon=CURRENCY_ICON,
            admin_mention=admin.mention
        )
        # DB에 저장된 색상 대신, 상황에 맞는 색상으로 덮어쓰기
        formatted_data['color'] = color
        
        embed = discord.Embed.from_dict(formatted_data)
        
        try: await log_channel.send(embed=embed)
        except Exception as e: logger.error(f"관리자 코인 조작 로그 전송 실패: {e}", exc_info=True)
        
    @app_commands.command(name="コイン付与", description="[管理者専用] 特定のユーザーにコインを付与します。")
    @app_commands.checks.has_permissions(administrator=True)
    async def give_coin_command(self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 1, None]):
        await interaction.response.defer(ephemeral=True)
        result = await update_wallet(user, amount)
        if result:
            await self.log_admin_action(interaction.user, user, amount, "付与")
            await interaction.followup.send(f"✅ {user.mention}さんへ `{amount:,}`{CURRENCY_ICON}を付与しました。", ephemeral=True)
        else: await interaction.followup.send("❌ コイン付与中にエラーが発生しました。", ephemeral=True)
        
    @app_commands.command(name="コイン削減", description="[管理者専用] 特定のユーザーのコインを削減します。")
    @app_commands.checks.has_permissions(administrator=True)
    async def take_coin_command(self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 1, None]):
        await interaction.response.defer(ephemeral=True)
        result = await update_wallet(user, -amount)
        if result:
            await self.log_admin_action(interaction.user, user, -amount, "削減")
            await interaction.followup.send(f"✅ {user.mention}さんの残高から `{amount:,}`{CURRENCY_ICON}を削減しました。", ephemeral=True)
        else: await interaction.followup.send("❌ コイン削減中にエラーが発生しました。", ephemeral=True)

    # ... 나머지 명령어(송금 등)는 수정할 필요 없음 ...
    
async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCore(bot))
