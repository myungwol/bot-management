# cogs/economy/core.py (최종 수정본 - 버그 수정 및 안정성 강화)

import discord
from discord.ext import commands, tasks
from discord import app_commands
import random
from datetime import datetime
import logging
import asyncio
from collections import defaultdict

# 로깅 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

from utils.database import (get_wallet, update_wallet, get_activity_data,
                            update_activity_data, CURRENCY_ICON,
                            get_channel_id_from_db, get_role_id) # get_cooldown, set_cooldown은 채팅 보상 로직에서 제거됨

# 설정값
EXCLUDED_VOICE_CHANNEL_IDS = []
CHAT_MESSAGE_REQUIREMENT = 10
CHAT_REWARD_MIN = 5
CHAT_REWARD_MAX = 10
VOICE_TIME_REQUIREMENT_MINUTES = 10
VOICE_REWARD_MIN = 10
VOICE_REWARD_MAX = 15

class EconomyCore(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.coin_log_channel_id: int | None = None
        self.admin_role_id: int | None = None
        # [핵심 1] 채팅 보상 버그 수정을 위한 유저별 Lock
        self.user_chat_locks = defaultdict(asyncio.Lock)
        self.voice_reward_loop.start()
        logger.info("EconomyCore Cog initialized.")

    async def cog_load(self):
        await self.load_config_from_db()

    async def load_config_from_db(self):
        self.coin_log_channel_id = await get_channel_id_from_db("coin_log_channel_id")
        # [수정] 올바른 함수로 관리자 역할 ID 로드
        self.admin_role_id = get_role_id("admin_total")
        logger.info(f"[EconomyCore Cog] Loaded COIN_LOG_CHANNEL_ID: {self.coin_log_channel_id}")
        logger.info(f"[EconomyCore Cog] Loaded ADMIN_ROLE_ID: {self.admin_role_id}")

    def cog_unload(self):
        self.voice_reward_loop.cancel()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or message.guild is None or message.content.startswith('/'):
            return

        user = message.author
        user_id_str = str(user.id)

        # [핵심 2] 유저별 Lock을 사용하여 동시성 문제 해결
        async with self.user_chat_locks[user.id]:
            activity_data = await get_activity_data(user_id_str)
            current_chats = activity_data.get('chat_counts', 0)

            new_chat_count = current_chats + 1

            if new_chat_count >= CHAT_MESSAGE_REQUIREMENT:
                reward = random.randint(CHAT_REWARD_MIN, CHAT_REWARD_MAX)
                await update_wallet(user, reward)
                # 채팅 카운트를 0으로 리셋
                await update_activity_data(user_id_str, reset_chat=True)

                # 로그 채널에 메시지 전송
                if self.coin_log_channel_id and (log_channel := self.bot.get_channel(self.coin_log_channel_id)):
                    embed = discord.Embed(title="💬 チャット活動報酬", description=f"{user.mention}さんがチャット活動でコインを獲得しました。", color=discord.Color.blue())
                    embed.add_field(name="獲得者", value=user.mention, inline=True)
                    embed.add_field(name="獲得コイン", value=f"+{reward} {CURRENCY_ICON}", inline=True)
                    embed.set_footer(text="おめでとうございます！")
                    try:
                        await log_channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
                    except Exception as e:
                        logger.error(f"Failed to send chat reward log: {e}", exc_info=True)
            else:
                # 채팅 카운트만 1 증가
                await update_activity_data(user_id_str, chat_increment=1)

    @tasks.loop(minutes=1)
    async def voice_reward_loop(self):
        try:
            for guild in self.bot.guilds:
                afk_channel_id = guild.afk_channel.id if guild.afk_channel else None
                for vc in guild.voice_channels:
                    if vc.id == afk_channel_id or vc.id in EXCLUDED_VOICE_CHANNEL_IDS:
                        continue

                    for member in vc.members:
                        if not member.bot and member.voice and not member.voice.self_deaf and not member.voice.self_mute:
                            user_id_str = str(member.id)
                            await update_activity_data(user_id_str, voice_increment=1)

                            activity_data = await get_activity_data(user_id_str)
                            current_minutes = activity_data.get('voice_minutes', 0)

                            if current_minutes >= VOICE_TIME_REQUIREMENT_MINUTES:
                                reward = random.randint(VOICE_REWARD_MIN, VOICE_REWARD_MAX)
                                await update_wallet(member, reward)
                                # [핵심 3] 음성 활동 시간을 안전하게 0으로 리셋
                                await update_activity_data(user_id_str, reset_voice=True)

                                if self.coin_log_channel_id and (log_channel := self.bot.get_channel(self.coin_log_channel_id)):
                                    embed = discord.Embed(title="🎙️ ボイスチャット活動報酬", description=f"{member.mention}さんがVC活動でコインを獲得しました。", color=discord.Color.green())
                                    embed.add_field(name="獲得者", value=member.mention, inline=True)
                                    embed.add_field(name="獲得コイン", value=f"+{reward} {CURRENCY_ICON}", inline=True)
                                    embed.set_footer(text="おめでとうございます！")
                                    try:
                                        await log_channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
                                    except Exception as e:
                                        logger.error(f"Failed to send voice reward log: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Voice reward loop encountered an error: {e}", exc_info=True)

    @voice_reward_loop.before_loop
    async def before_voice_reward_loop(self):
        await self.bot.wait_until_ready()

    @app_commands.command(name="送金", description="他のユーザーにコインを送ります。")
    @app_commands.describe(recipient="コインを受け取るユーザー", amount="送る金額")
    async def transfer_command(self, interaction: discord.Interaction, recipient: discord.Member, amount: app_commands.Range[int, 1, None]):
        sender = interaction.user
        if recipient.bot or recipient.id == sender.id:
            await interaction.response.send_message("自分自身やボットには送金できません。", ephemeral=True)
            return
        sender_wallet = await get_wallet(sender.id)
        if sender_wallet.get('balance', 0) < amount:
            await interaction.response.send_message(f"残高が不足しています。", ephemeral=True)
            return

        await update_wallet(sender, -amount)
        await update_wallet(recipient, amount)

        updated_sender_wallet = await get_wallet(sender.id)
        embed = discord.Embed(title="💸 送金完了", description=f"{recipient.mention}さんへ `{amount:,}` {CURRENCY_ICON}を送金しました。", color=discord.Color.green())
        embed.add_field(name="送金者", value=sender.mention, inline=True)
        embed.add_field(name="受取人", value=recipient.mention, inline=True)
        embed.set_footer(text=f"送金後の残高: {updated_sender_wallet.get('balance', 0):,} {CURRENCY_ICON}")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="コイン付与", description="[管理者専用] 特定のユーザーにコインを付与します。")
    @app_commands.describe(user="コインを付与するユーザー", amount="付与する金額")
    async def give_coin_command(self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 1, None]):
        if not self.admin_role_id or not discord.utils.get(interaction.user.roles, id=self.admin_role_id):
            return await interaction.response.send_message("このコマンドを使用する権限がありません。", ephemeral=True)

        result = await update_wallet(user, amount)
        if result:
            embed = discord.Embed(title="コイン付与完了", description=f"{user.mention}さんへ `{amount:,}` {CURRENCY_ICON}を付与しました。", color=discord.Color.blue())
            embed.set_footer(text=f"付与後の残高: {result['balance']:,} {CURRENCY_ICON} | 処理者: {interaction.user.display_name} (公務員)")
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("コイン付与中にエラーが発生しました。", ephemeral=True)

    @app_commands.command(name="コイン削減", description="[管理者専用] 特定のユーザーのコインを削減します。")
    @app_commands.describe(user="コインを削減するユーザー", amount="削減する金額")
    async def take_coin_command(self, interaction: discord.Interaction, user: discord.Member, amount: app_commands.Range[int, 1, None]):
        if not self.admin_role_id or not discord.utils.get(interaction.user.roles, id=self.admin_role_id):
            return await interaction.response.send_message("このコマンドを使用する権限がありません。", ephemeral=True)

        result = await update_wallet(user, -amount)
        if result:
            embed = discord.Embed(title="コイン削減完了", description=f"{user.mention}さんの残高から `{amount:,}` {CURRENCY_ICON}を削減しました。", color=discord.Color.red())
            embed.set_footer(text=f"削減後の残高: {result['balance']:,} {CURRENCY_ICON} | 処理者: {interaction.user.display_name} (公務員)")
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("コイン削減中にエラーが発生しました。", ephemeral=True)

async def setup(bot: commands.Bot):
    cog = EconomyCore(bot)
    await bot.add_cog(cog)