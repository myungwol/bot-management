# cogs/economy/core.py (성능, 안정성, UX 대폭 개선 최종본)

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import random
import asyncio
from collections import defaultdict
import logging
from typing import Optional, Dict

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] %(message)s')
logger = logging.getLogger(__name__)

# 유틸리티 함수 임포트
from utils.database import (
    get_wallet, update_wallet, update_activity_data,
    CURRENCY_ICON, get_id, supabase # [신규] supabase 클라이언트 직접 사용
)

# --- 상수 정의 ---
CHAT_MESSAGE_REQUIREMENT = 10
CHAT_REWARD_RANGE = (5, 10)
VOICE_TIME_REQUIREMENT_MINUTES = 10
VOICE_REWARD_RANGE = (10, 15)

class TransferConfirmView(ui.View):
    def __init__(self, sender: discord.Member, recipient: discord.Member, amount: int, cog_instance: 'EconomyCore'):
        super().__init__(timeout=60)
        self.sender = sender
        self.recipient = recipient
        self.amount = amount
        self.economy_cog = cog_instance
        self.result_message: Optional[str] = None
        self.error: Optional[Exception] = None

    @ui.button(label="はい", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.sender.id:
            await interaction.response.send_message("本人確認が必要です。", ephemeral=True)
            return

        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            # [핵심] 원자적 트랜잭션을 위한 RPC 함수 호출
            params = {'sender_id_param': str(self.sender.id), 'recipient_id_param': str(self.recipient.id), 'amount_param': self.amount}
            await supabase.rpc('transfer_coins', params).execute()
            
            # 성공 로그 기록
            await self.economy_cog.log_coin_transfer(self.sender, self.recipient, self.amount)
            self.result_message = f"✅ {self.recipient.mention}さんへ `{self.amount:,}`{CURRENCY_ICON}を正常に送金しました。"
            
        except Exception as e:
            self.error = e
            logger.error(f"송금 RPC 실행 중 오류: {e}", exc_info=True)
            self.result_message = f"❌ 送金に失敗しました。残高が不足しているか、予期せぬエラーが発生しました。"

        self.stop()
    
    @ui.button(label="いいえ", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.sender.id:
            await interaction.response.send_message("本人確認が必要です。", ephemeral=True)
            return
        self.result_message = "❌ 送金がキャンセルされました。"
        self.stop()
        await interaction.response.edit_message(content=self.result_message, view=None)

class EconomyCore(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.coin_log_channel_id: Optional[int] = None
        self.admin_role_id: Optional[int] = None
        
        # [핵심] 인메모리 카운터를 사용하여 DB 부하 감소
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
            self.user_chat_progress[user.id] = 0 # 즉시 초기화하여 중복 지급 방지
            reward = random.randint(*CHAT_REWARD_RANGE)
            await update_wallet(user, reward)
            await self.log_coin_activity(user, reward, "チャット活動報酬", 0x3498DB)

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
                                await self.log_coin_activity(member, reward, "ボイスチャット活動報酬", 0x2ECC71)
        except Exception as e: logger.error(f"음성 보상 루프 중 오류: {e}", exc_info=True)

    @voice_reward_loop.before_loop
    async def before_voice_reward_loop(self): await self.bot.wait_until_ready()

    async def log_coin_activity(self, user: discord.Member, amount: int, reason: str, color: int):
        if not self.coin_log_channel_id or not (log_channel := self.bot.get_channel(self.coin_log_channel_id)): return
        embed = discord.Embed(title=f"💰 コイン獲得: {reason}", color=color)
        embed.add_field(name="獲得者", value=user.mention, inline=True)
        embed.add_field(name="獲得コイン", value=f"`+{amount}` {CURRENCY_ICON}", inline=True)
        try: await log_channel.send(embed=embed)
        except Exception as e: logger.error(f"코인 활동 로그 전송 실패: {e}", exc_info=True)

    async def log_coin_transfer(self, sender: discord.Member, recipient: discord.Member, amount: int):
        if not self.coin_log_channel_id or not (log_channel := self.bot.get_channel(self.coin_log_channel_id)): return
        embed = discord.Embed(title="💸 コイン送金ログ", color=0x9B59B6)
        embed.add_field(name="送金者", value=sender.mention, inline=True)
        embed.add_field(name="受取人", value=recipient.mention, inline=True)
        embed.add_field(name="金額", value=f"`{amount:,}` {CURRENCY_ICON}", inline=False)
        try: await log_channel.send(embed=embed)
        except Exception as e: logger.error(f"코인 송금 로그 전송 실패: {e}", exc_info=True)
        
    async def log_admin_action(self, admin: discord.Member, target: discord.Member, amount: int, action: str, color: int):
        if not self.coin_log_channel_id or not (log_channel := self.bot.get_channel(self.coin_log_channel_id)): return
        title = "🔧 コイン管理ログ"
        embed = discord.Embed(title=title, description=f"管理者によるコイン操作: **{action}**", color=color)
        embed.add_field(name="対象者", value=target.mention, inline=False)
        embed.add_field(name="金額", value=f"`{amount:,}` {CURRENCY_ICON}", inline=True)
        embed.add_field(name="処理者", value=admin.mention, inline=True)
        try: await log_channel.send(embed=embed)
        except Exception as e: logger.error(f"관리자 코인 조작 로그 전송 실패: {e}", exc_info=True)

    @app_commands.command(name="送金", description="他のユーザーにコインを送ります。")
    @app_commands.describe(recipient="コインを受け取るユーザー", amount="送る金額")
    async def transfer_command(self, interaction: discord.Interaction, recipient: discord.Member, amount: app_commands.Range[int, 1, None]):
        sender = interaction.user
        if recipient.bot or recipient.id == sender.id:
            return await interaction.response.send_message("自分自身やボットには送金できません。", ephemeral=True)
        
        sender_wallet = await get_wallet(sender.id)
        if sender_wallet.get('balance', 0) < amount:
            return await interaction.response.send_message(f"残高が不足しています。 현재 잔액: `{sender_wallet.get('balance', 0):,}`{CURRENCY_ICON}", ephemeral=True)

        view = TransferConfirmView(sender, recipient, amount, self)
        embed = discord.Embed(title="💸 送金確認", description=f"本当に {recipient.mention}さんへ `{amount:,}`{CURRENCY_ICON} を送金しますか？", color=0xE67E22)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
        await view.wait()
        await interaction.edit_original_response(content=view.result_message, view=None)

    @app_commands.command(name="コイン付与", description="[管理者専用] 特定のユーザーにコインを付与します。")
    @app_commands.checks.has_permissions(administrator=True)
    async def give_coin_command(self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 1, None]):
        await interaction.response.defer(ephemeral=True)
        result = await update_wallet(user, amount)
        if result:
            await self.log_admin_action(interaction.user, user, amount, "付与", 0x3498DB)
            await interaction.followup.send(f"✅ {user.mention}さんへ `{amount:,}`{CURRENCY_ICON}を付与しました。", ephemeral=True)
        else: await interaction.followup.send("❌ コイン付与中にエラーが発生しました。", ephemeral=True)

    @app_commands.command(name="コイン削減", description="[管理者専用] 特定のユーザーのコインを削減します。")
    @app_commands.checks.has_permissions(administrator=True)
    async def take_coin_command(self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 1, None]):
        await interaction.response.defer(ephemeral=True)
        result = await update_wallet(user, -amount)
        if result:
            await self.log_admin_action(interaction.user, user, -amount, "削減", 0xE74C3C)
            await interaction.followup.send(f"✅ {user.mention}さんの残高から `{amount:,}`{CURRENCY_ICON}を削減しました。", ephemeral=True)
        else: await interaction.followup.send("❌ コイン削減中にエラーが発生しました。", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCore(bot))
