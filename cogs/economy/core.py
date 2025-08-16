# cogs/economy/core.py (UI 중앙 관리 시스템 연동)

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import random
import asyncio
from collections import defaultdict
import logging
import json
from typing import Optional, Dict

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] %(message)s')
logger = logging.getLogger(__name__)

from utils.database import (
    get_wallet, update_wallet,
    CURRENCY_ICON, get_id, supabase, get_embed_from_db
)
# [수정] system.py에서 만든 헬퍼 함수를 가져옵니다.
from cogs.server.system import format_embed_from_db

CHAT_MESSAGE_REQUIREMENT = 10
CHAT_REWARD_RANGE = (5, 10)
VOICE_TIME_REQUIREMENT_MINUTES = 10
VOICE_REWARD_RANGE = (10, 15)

class TransferConfirmView(ui.View):
    def __init__(self, sender: discord.Member, recipient: discord.Member, amount: int, cog_instance: 'EconomyCore'):
        super().__init__(timeout=60)
        self.sender = sender; self.recipient = recipient; self.amount = amount
        self.economy_cog = cog_instance; self.result_message: Optional[str] = None
    @ui.button(label="はい", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.sender.id:
            await interaction.response.send_message("本人確認が必要です。", ephemeral=True); return
        await interaction.response.defer(thinking=True, ephemeral=True)
        try:
            params = {'sender_id_param': str(self.sender.id), 'recipient_id_param': str(self.recipient.id), 'amount_param': self.amount}
            response = await supabase.rpc('transfer_coins', params).execute()
            # [수정] Supabase RPC 응답에 대한 더 안정적인 오류 확인
            if response.data is None or (isinstance(response.data, list) and not response.data):
                 raise Exception(f"송금 실패: 잔액 부족 또는 DB 오류. {response.error}")
            await self.economy_cog.log_coin_transfer(self.sender, self.recipient, self.amount)
            self.result_message = f"✅ {self.recipient.mention}さんへ `{self.amount:,}`{CURRENCY_ICON}を正常に送金しました。"
        except Exception as e:
            logger.error(f"송금 RPC 실행 중 오류: {e}", exc_info=True)
            self.result_message = f"❌ 送金に失敗しました。残高が不足しているか、予期せぬエラーが発生しました。"
        self.stop()
    @ui.button(label="いいえ", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.id != self.sender.id:
            await interaction.response.send_message("本人確認が必要です。", ephemeral=True); return
        self.result_message = "❌ 送金がキャンセルされました。"; self.stop()
        await interaction.response.edit_message(content=self.result_message, view=None)

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
        user = message.author; self.user_chat_progress[user.id] += 1
        if self.user_chat_progress[user.id] >= CHAT_MESSAGE_REQUIREMENT:
            self.user_chat_progress[user.id] = 0; reward = random.randint(*CHAT_REWARD_RANGE)
            await update_wallet(user, reward); await self.log_coin_activity(user, reward, "チャット活動報酬")
            
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
                                self.user_voice_progress[member.id] = 0; reward = random.randint(*VOICE_REWARD_RANGE)
                                await update_wallet(member, reward); await self.log_coin_activity(member, reward, "ボイスチャット活動報酬")
        except Exception as e: logger.error(f"음성 보상 루프 중 오류: {e}", exc_info=True)
        
    @voice_reward_loop.before_loop
    async def before_voice_reward_loop(self): await self.bot.wait_until_ready()
    
    async def log_coin_activity(self, user: discord.Member, amount: int, reason: str):
        if not self.coin_log_channel_id or not (log_channel := self.bot.get_channel(self.coin_log_channel_id)): return
        if embed_data := await get_embed_from_db("log_coin_gain"):
            embed = format_embed_from_db(embed_data, reason=reason, user_mention=user.mention, amount=f"{amount:,}", currency_icon=CURRENCY_ICON)
            try: await log_channel.send(embed=embed)
            except Exception as e: logger.error(f"코인 활동 로그 전송 실패: {e}", exc_info=True)
        
    async def log_coin_transfer(self, sender: discord.Member, recipient: discord.Member, amount: int):
        if not self.coin_log_channel_id or not (log_channel := self.bot.get_channel(self.coin_log_channel_id)): return
        if embed_data := await get_embed_from_db("log_coin_transfer"):
            embed = format_embed_from_db(embed_data, sender_mention=sender.mention, recipient_mention=recipient.mention, amount=f"{amount:,}", currency_icon=CURRENCY_ICON)
            try: await log_channel.send(embed=embed)
            except Exception as e: logger.error(f"코인 송금 로그 전송 실패: {e}", exc_info=True)
        
    async def log_admin_action(self, admin: discord.Member, target: discord.Member, amount: int, action: str):
        if not self.coin_log_channel_id or not (log_channel := self.bot.get_channel(self.coin_log_channel_id)): return
        if embed_data := await get_embed_from_db("log_coin_admin"):
            action_color = 0x3498DB if amount > 0 else 0xE74C3C
            amount_str = f"+{amount:,}" if amount > 0 else f"{amount:,}"
            embed = format_embed_from_db(embed_data, action=action, target_mention=target.mention, amount=amount_str, currency_icon=CURRENCY_ICON, admin_mention=admin.mention)
            embed.color = discord.Color(action_color) # 색상은 동적으로 변경
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
            return await interaction.response.send_message(f"残高が不足しています。 現在の残高: `{sender_wallet.get('balance', 0):,}`{CURRENCY_ICON}", ephemeral=True)
        
        # [수정] 송금 확인 임베드를 DB에서 불러옵니다.
        embed_data = await get_embed_from_db("embed_transfer_confirmation")
        if not embed_data: # DB에 데이터가 없을 경우를 대비한 기본값
            embed = discord.Embed(title="💸 送金確認", description=f"本当に {recipient.mention}さんへ `{amount:,}`{CURRENCY_ICON} を送金しますか？", color=0xE67E22)
        else:
            embed = format_embed_from_db(embed_data, recipient_mention=recipient.mention, amount=f"{amount:,}", currency_icon=CURRENCY_ICON)

        view = TransferConfirmView(sender, recipient, amount, self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        await view.wait()
        await interaction.edit_original_response(content=view.result_message, view=None)
        
    @app_commands.command(name="コイン付与", description="[管理者専用] 特定のユーザーにコインを付与します。")
    @app_commands.checks.has_permissions(administrator=True)
    async def give_coin_command(self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 1, None]):
        await interaction.response.defer(ephemeral=True)
        result = await update_wallet(user, amount)
        if result:
            await self.log_admin_action(interaction.user, user, amount, "付与"); await interaction.followup.send(f"✅ {user.mention}さんへ `{amount:,}`{CURRENCY_ICON}を付与しました。")
        else: await interaction.followup.send("❌ コイン付与中にエラーが発生しました。")
        
    @app_commands.command(name="コイン削減", description="[管理者専用] 特定のユーザーのコインを削減します。")
    @app_commands.checks.has_permissions(administrator=True)
    async def take_coin_command(self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 1, None]):
        await interaction.response.defer(ephemeral=True)
        result = await update_wallet(user, -amount)
        if result:
            await self.log_admin_action(interaction.user, user, -amount, "削減"); await interaction.followup.send(f"✅ {user.mention}さんの残高から `{amount:,}`{CURRENCY_ICON}を削減しました。")
        else: await interaction.followup.send("❌ コイン削減中にエラーが発生しました。")

async def setup(bot: commands.Bot):
    await bot.add_cog(EconomyCore(bot))
