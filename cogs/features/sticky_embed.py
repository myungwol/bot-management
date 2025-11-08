# cogs/features/sticky_embed.py
import discord
from discord import app_commands
from discord.ext import commands
import logging
import asyncio
from typing import Dict, Optional, Set

from utils.database import set_sticky_message, remove_sticky_message, _sticky_messages_cache, get_id
from utils.ui_defaults import CUSTOM_EMBED_SENDER_ROLES

logger = logging.getLogger(__name__)

class StickyEmbed(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # { channel_id: { "message_id": int, "embed_data": dict } }
        self.sticky_channels: Dict[int, Dict] = {}
        # 채널별 동시 처리를 방지하기 위한 Lock
        self.channel_locks: Dict[int, asyncio.Lock] = {}
        
        # 관리자 역할 ID를 저장할 Set
        self.admin_role_ids: Set[int] = set()

        # Context Menu 등록
        self.set_sticky_menu = app_commands.ContextMenu(
            name="고정 임베드로 설정",
            callback=self.set_as_sticky,
        )
        self.unset_sticky_menu = app_commands.ContextMenu(
            name="고정 임베드 해제",
            callback=self.unset_sticky,
        )
        self.bot.tree.add_command(self.set_sticky_menu)
        self.bot.tree.add_command(self.unset_sticky_menu)
        
        logger.info("StickyEmbed Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        # Cog가 로드될 때 캐시를 동기화하고 관리자 역할을 불러옵니다.
        self.sticky_channels = _sticky_messages_cache.copy()
        self.admin_role_ids = {
            role_id for key in CUSTOM_EMBED_SENDER_ROLES 
            if (role_id := get_id(key)) is not None
        }

    async def cog_unload(self):
        # Cog가 언로드될 때 Context Menu를 제거합니다.
        self.bot.tree.remove_command(self.set_sticky_menu.name, type=self.set_sticky_menu.type)
        self.bot.tree.remove_command(self.unset_sticky_menu.name, type=self.unset_sticky_menu.type)

    async def _check_permission(self, interaction: discord.Interaction) -> bool:
        """명령어 사용 권한을 확인하는 내부 함수"""
        if not isinstance(interaction.user, discord.Member):
            return False
        if interaction.user.guild_permissions.manage_guild:
            return True
        return any(role.id in self.admin_role_ids for role in interaction.user.roles)

    async def set_as_sticky(self, interaction: discord.Interaction, message: discord.Message):
        """[Context Menu] 메시지를 고정 임베드로 설정합니다."""
        if not await self._check_permission(interaction):
            return await interaction.response.send_message("❌ 이 기능을 사용할 권한이 없습니다.", ephemeral=True)

        if message.author.id != self.bot.user.id or not message.embeds:
            return await interaction.response.send_message("❌ 봇이 보낸 임베드 메시지만 고정할 수 있습니다.", ephemeral=True)

        channel_id = message.channel.id
        embed_data = message.embeds[0].to_dict()

        await set_sticky_message(channel_id, message.id, message.guild.id, embed_data)
        self.sticky_channels[channel_id] = {
            "message_id": message.id,
            "embed_data": embed_data
        }
        
        await interaction.response.send_message(f"✅ 이 메시지를 <#{channel_id}> 채널의 고정 임베드로 설정했습니다.", ephemeral=True)

    async def unset_sticky(self, interaction: discord.Interaction, message: discord.Message):
        """[Context Menu] 채널의 고정 임베드를 해제합니다."""
        if not await self._check_permission(interaction):
            return await interaction.response.send_message("❌ 이 기능을 사용할 권한이 없습니다.", ephemeral=True)

        channel_id = interaction.channel_id
        if channel_id not in self.sticky_channels:
            return await interaction.response.send_message("ℹ️ 이 채널에는 설정된 고정 임베드가 없습니다.", ephemeral=True)

        await remove_sticky_message(channel_id)
        self.sticky_channels.pop(channel_id, None)

        await interaction.response.send_message(f"✅ <#{channel_id}> 채널의 고정 임베드 설정을 해제했습니다.", ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """새 메시지가 올라오면 고정 임베드를 다시 보냅니다."""
        # 봇 메시지, DM, 또는 고정 임베드가 없는 채널은 무시
        if message.author.bot or not message.guild or message.channel.id not in self.sticky_channels:
            return

        channel = message.channel
        
        # 특정 채널에 대한 동시 실행 방지
        lock = self.channel_locks.setdefault(channel.id, asyncio.Lock())
        
        async with lock:
            # Lock을 획득한 후에도 여전히 고정 채널인지 다시 확인
            sticky_data = self.sticky_channels.get(channel.id)
            if not sticky_data:
                return

            # 이전 고정 메시지 삭제
            try:
                old_message = await channel.fetch_message(sticky_data['message_id'])
                await old_message.delete()
            except discord.NotFound:
                # 이미 수동으로 삭제된 경우, 그냥 넘어감
                pass
            except discord.Forbidden:
                logger.warning(f"고정 임베드: 채널 '{channel.name}'에서 메시지를 삭제할 권한이 없습니다.")
                return # 권한이 없으면 더 이상 진행할 수 없음
            except Exception as e:
                logger.error(f"이전 고정 메시지 삭제 중 오류: {e}", exc_info=True)

            # 새 고정 메시지 전송
            try:
                new_embed = discord.Embed.from_dict(sticky_data['embed_data'])
                new_message = await channel.send(embed=new_embed)

                # DB와 캐시에 새 메시지 ID 업데이트
                await set_sticky_message(channel.id, new_message.id, message.guild.id, sticky_data['embed_data'])
                self.sticky_channels[channel.id]['message_id'] = new_message.id

            except discord.Forbidden:
                logger.warning(f"고정 임베드: 채널 '{channel.name}'에 임베드를 보낼 권한이 없습니다.")
            except Exception as e:
                logger.error(f"새 고정 메시지 전송 중 오류: {e}", exc_info=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(StickyEmbed(bot))
