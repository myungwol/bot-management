# cogs/server/member_events.py
import discord
from discord.ext import commands
import logging
from typing import Optional, List
import re # <-- 정규표현식을 위해 re 모듈을 import 합니다.

from utils.helpers import format_embed_from_db
from utils.database import get_id, get_embed_from_db, supabase, get_config, backup_member_data, get_member_backup, delete_member_backup

logger = logging.getLogger(__name__)

class MemberEvents(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.welcome_channel_id: Optional[int] = None
        self.farewell_channel_id: Optional[int] = None
        logger.info("MemberEvents (입장/퇴장) Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        pass

    async def load_configs(self):
        self.welcome_channel_id = get_id("new_welcome_channel_id")
        self.farewell_channel_id = get_id("farewell_channel_id")
        logger.info("[MemberEvents Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        # ... (이 함수는 변경 없음) ...
        if member.bot: return
        backup = await get_member_backup(member.id, member.guild.id)
        if backup:
            logger.info(f"재참여 유저 '{member.display_name}'님의 데이터를 발견하여 복구를 시도합니다.")
            try:
                role_ids_to_restore = backup.get('roles', [])
                roles_to_restore = [role for role_id in role_ids_to_restore if (role := member.guild.get_role(role_id)) is not None]
                restored_nick = backup.get('nickname')
                if roles_to_restore or restored_nick: await member.edit(roles=roles_to_restore, nick=restored_nick, reason="서버 재참여로 인한 데이터 복구")
                await delete_member_backup(member.id, member.guild.id)
            except Exception as e: logger.error(f"'{member.display_name}'님 데이터 복구 중 오류: {e}", exc_info=True)
            return
        try:
            await supabase.table('user_levels').upsert({'user_id': member.id, 'level': 1, 'xp': 0}, on_conflict='user_id').execute()
        except Exception as e: logger.error(f"'{member.display_name}'님의 초기 레벨 데이터 생성 중 오류: {e}", exc_info=True)
        initial_role_keys = ["role_notify_welcome", "role_notify_dding", "role_guest"]
        roles_to_add = [role for key in initial_role_keys if (role_id := get_id(key)) and (role := member.guild.get_role(role_id))]
        if roles_to_add:
            try: await member.add_roles(*roles_to_add, reason="서버 참여 시 초기 역할 부여")
            except discord.Forbidden: logger.error(f"'{member.display_name}'님에게 초기 역할을 부여하지 못했습니다. (권한 부족)")
        if self.welcome_channel_id and (channel := self.bot.get_channel(self.welcome_channel_id)):
            embed_data = await get_embed_from_db('welcome_embed')
            if embed_data:
                embed = format_embed_from_db(embed_data, member_mention=member.mention, guild_name=member.guild.name)
                if member.display_avatar: embed.set_thumbnail(url=member.display_avatar.url)
                await channel.send(f"{member.mention}님, 과자 공장에 오신 것을 환영합니다 <a:newheart_01:1427212124588998706> ", embed=embed, allowed_mentions=discord.AllowedMentions(users=True))

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        # ... (이 함수는 변경 없음) ...
        if member.bot: return
        try:
            role_ids_to_backup = [role.id for role in member.roles if not role.is_default()]
            await backup_member_data(member.id, member.guild.id, role_ids_to_backup, member.nick)
        except Exception as e: logger.error(f"'{member.display_name}'님 데이터 백업 중 오류: {e}", exc_info=True)
        if self.farewell_channel_id and (channel := self.bot.get_channel(self.farewell_channel_id)):
            embed_data = await get_embed_from_db('farewell_embed')
            if embed_data:
                embed = format_embed_from_db(embed_data, member_name=member.name)
                if member.display_avatar: embed.set_thumbnail(url=member.display_avatar.url)
                await channel.send(embed=embed)

    async def _handle_boost_start(self, member: discord.Member):
        logger.info(f"--- 부스트 보상 지급 프로세스 시작: {member.display_name} ---")
        
        try:
            guild = self.bot.get_guild(member.guild.id)
            if not guild: return
            member = await guild.fetch_member(member.id)
        except Exception as e:
            logger.error(f"부스트 핸들러: 최신 멤버 정보를 가져오는 중 오류: {e}")
            return

        boost_ticket_roles_by_level = { i: guild.get_role(get_id(f"role_boost_ticket_{i}")) for i in range(1, 11) }
        valid_boost_roles_by_id = {role.id for role in boost_ticket_roles_by_level.values() if role}
        if not valid_boost_roles_by_id:
            logger.warning("부스트 감지: DB에 설정된 보상 역할을 서버에서 찾을 수 없습니다.")
            return

        current_member_roles = set(member.roles)
        existing_reward_roles = [role for role in current_member_roles if role.id in valid_boost_roles_by_id]
        
        highest_level = 0
        for role in existing_reward_roles:
            match = re.search(r'역할선택권\s*(\d+)', role.name)
            if match:
                level = int(match.group(1))
                if level > highest_level:
                    highest_level = level
        
        # --- ▼▼▼ [핵심 수정] 최고 레벨 도달 시의 로직 변경 ---
        if highest_level >= 10:
            logger.info("이미 최고 레벨(10)에 도달하여 역할을 변경하지 않습니다.")
            boost_channel_id = get_id("boost_log_channel_id")
            if boost_channel := self.bot.get_channel(boost_channel_id):
                try:
                    await boost_channel.send(f"🎉 {member.mention}님은 이미 최고 부스트 레벨 보상을 모두 받으셨습니다! 서버를 계속 후원해주셔서 감사합니다! 💖")
                except discord.Forbidden:
                    pass
            return

        new_level = highest_level + 2
        
        # 만약 계산된 레벨이 10을 초과하면, 10으로 고정합니다.
        if new_level > 10:
            new_level = 10
        # --- ▲▲▲ [수정 완료] ---
            
        logger.info(f"계산된 현재 최고 레벨: {highest_level}")
        logger.info(f"새로 지급할 목표 레벨: {new_level}")
        
        role_to_add = boost_ticket_roles_by_level.get(new_level)
        logger.info(f"새로 지급할 역할 객체: {role_to_add.name if role_to_add else '없음'}")

        roles_to_remove_set = set(existing_reward_roles)
        final_roles = list(current_member_roles - roles_to_remove_set)
        if role_to_add:
            final_roles.append(role_to_add)

        try:
            await member.edit(roles=final_roles, reason="서버 부스트 보상 업데이트")
            
            boost_channel_id = get_id("boost_log_channel_id")
            if boost_channel := self.bot.get_channel(boost_channel_id):
                embed_data = await get_embed_from_db("log_boost_start")
                if embed_data:
                    final_reward_roles = [role_to_add] if role_to_add else []
                    roles_list_str = "\n".join([f"- {role.mention}" for role in final_reward_roles])
                    embed = format_embed_from_db(embed_data, member_mention=member.mention, member_name=member.display_name, roles_list=roles_list_str)
                    await boost_channel.send(content=member.mention, embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
        except Exception as e:
            logger.error(f"{member.display_name}님에게 부스트 보상 지급 중 오류 발생: {e}", exc_info=True)
        
        logger.info(f"--- 부스트 보상 지급 프로세스 종료: {member.display_name} ---")
    # ▲▲▲ [수정 완료] ▲▲▲
    
    # --- ▼▼▼ [핵심 추가] 테스트 전용 함수 ---
    async def run_boost_test(self, member: discord.Member):
        # 단순히 부스트 시작 로직을 호출합니다.
        await self._handle_boost_start(member)
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.premium_since == after.premium_since:
            return

        # --- 시나리오 1: 사용자가 새로 부스트를 시작했을 때 ---
        if before.premium_since is None and after.premium_since is not None:
            await self._handle_boost_start(after)

        # --- 시나리오 2: 사용자가 부스트를 중지했을 때 ---
        elif before.premium_since is not None and after.premium_since is None:
            logger.info(f"{after.display_name}님이 서버 부스트를 중지하여 보상 역할을 회수합니다.")
            
            boost_ticket_role_keys = [f"role_boost_ticket_{i}" for i in range(1, 11)]
            all_reward_role_ids = {get_id(key) for key in boost_ticket_role_keys if get_id(key)}
            roles_to_remove = [role for role in after.roles if role.id in all_reward_role_ids]
            
            try:
                if roles_to_remove:
                    await after.remove_roles(*roles_to_remove, reason="서버 부스트 중지")
                
                boost_channel_id = get_id("boost_log_channel_id")
                if boost_channel := self.bot.get_channel(boost_channel_id):
                    embed_data = await get_embed_from_db("log_boost_stop")
                    if embed_data:
                        embed = format_embed_from_db(embed_data, member_mention=after.mention)
                        if after.display_avatar:
                            embed.set_author(name=after.display_name, icon_url=after.display_avatar.url)
                        await boost_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"{after.display_name}님의 역할 회수 중 오류 발생: {e}", exc_info=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(MemberEvents(bot))
