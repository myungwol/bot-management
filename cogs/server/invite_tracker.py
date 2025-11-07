# cogs/server/invite_tracker.py
import discord
from discord.ext import commands
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class InviteTracker(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # { guild_id: { code: invite } }
        self.invite_cache: Dict[int, Dict[str, discord.Invite]] = {}
        logger.info("InviteTracker Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        self.bot.loop.create_task(self.build_cache())

    async def build_cache(self):
        await self.bot.wait_until_ready()
        logger.info("[InviteTracker] 서버 초대 정보 캐싱을 시작합니다...")
        for guild in self.bot.guilds:
            try:
                self.invite_cache[guild.id] = {invite.code: invite for invite in await guild.invites()}
            except discord.Forbidden:
                logger.warning(f"[{guild.name}] 서버의 초대 링크를 볼 권한이 없어 캐시할 수 없습니다.")
        logger.info("[InviteTracker] 초대 정보 캐싱이 완료되었습니다.")

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        if invite.guild.id in self.invite_cache:
            self.invite_cache[invite.guild.id][invite.code] = invite

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        if invite.guild.id in self.invite_cache and invite.code in self.invite_cache[invite.guild.id]:
            del self.invite_cache[invite.guild.id][invite.code]
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        try:
            self.invite_cache[guild.id] = {invite.code: invite for invite in await guild.invites()}
        except discord.Forbidden:
            pass

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        if guild.id in self.invite_cache:
            del self.invite_cache[guild.id]

    async def get_invite_for_member(self, member: discord.Member) -> Optional[discord.Invite]:
        """새로 참여한 멤버가 어떤 초대를 통해 들어왔는지 찾아냅니다."""
        guild = member.guild
        if guild.id not in self.invite_cache:
            return None
            
        try:
            current_invites = await guild.invites()
        except discord.Forbidden:
            return None

        found_invite = None
        for new_invite in current_invites:
            cached_invite = self.invite_cache[guild.id].get(new_invite.code)
            # 캐시된 사용 횟수보다 현재 사용 횟수가 1 많으면, 이 초대를 통해 들어온 것
            if cached_invite and new_invite.uses > cached_invite.uses:
                found_invite = new_invite
                break
        
        # 최신 정보로 캐시 업데이트
        self.invite_cache[guild.id] = {invite.code: invite for invite in current_invites}
        return found_invite

async def setup(bot: commands.Bot):
    await bot.add_cog(InviteTracker(bot))
