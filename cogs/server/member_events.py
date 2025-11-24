# cogs/server/member_events.py
import discord
from discord.ext import commands
import logging
from typing import Optional, List
import re

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
        if member.bot: return
        
        # 재참여 유저 데이터 복구 로직 (유지)
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
            
        # 신규 유저 초기 데이터 생성 (유지)
        try:
            await supabase.table('user_levels').upsert({'user_id': member.id, 'level': 1, 'xp': 0}, on_conflict='user_id').execute()
        except Exception as e: logger.error(f"'{member.display_name}'님의 초기 레벨 데이터 생성 중 오류: {e}", exc_info=True)
        
        # 초기 알림 역할만 부여
        initial_role_keys = ["role_notify_welcome", "role_notify_dding"]
        
        roles_to_add = [role for key in initial_role_keys if (role_id := get_id(key)) and (role := member.guild.get_role(role_id))]
        if roles_to_add:
            try: await member.add_roles(*roles_to_add, reason="서버 참여 시 초기 역할 부여")
            except discord.Forbidden: logger.error(f"'{member.display_name}'님에게 초기 역할을 부여하지 못했습니다. (권한 부족)")
            
        # 환영 메시지 전송 (유지)
        if self.welcome_channel_id and (channel := self.bot.get_channel(self.welcome_channel_id)):
            embed_data = await get_embed_from_db('welcome_embed')
            if embed_data:
                embed = format_embed_from_db(embed_data, member_mention=member.mention, guild_name=member.guild.name)
                if member.display_avatar: embed.set_thumbnail(url=member.display_avatar.url)
                await channel.send(f"{member.mention}님, 서버에 오신 것을 환영합니다.", embed=embed, allowed_mentions=discord.AllowedMentions(users=True))

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
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
        
        role_to_add = None
        roles_to_remove_set = set(existing_reward_roles)
        final_roles_for_embed = []

        if highest_level < 10:
            new_level = highest_level + 2
            if new_level > 10: new_level = 10
            role_to_add = boost_ticket_roles_by_level.get(new_level)
            
            final_roles = list(current_member_roles - roles_to_remove_set)
            if role_to_add: final_roles.append(role_to_add)
            await member.edit(roles=final_roles, reason="서버 부스트 보상 업데이트")
            final_roles_for_embed = [role_to_add] if role_to_add else []
        else:
            logger.info("이미 최고 레벨(10)에 도달하여 역할 변경은 없습니다.")
            final_roles_for_embed = existing_reward_roles

        try:
            boost_channel_id = get_id("boost_log_channel_id")
            if boost_channel := self.bot.get_channel(boost_channel_id):
                embed_data = await get_embed_from_db("log_boost_start")
                if embed_data:
                    roles_list_str = "\n".join([f"- {role.mention}" for role in final_roles_for_embed]) if final_roles_for_embed else "최고 레벨 달성!"
                    embed = format_embed_from_db(
                        embed_data, 
                        member_mention=member.mention, 
                        member_name=member.display_name,
                        roles_list=roles_list_str
                    )
                    await boost_channel.send(content=member.mention, embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
        except Exception as e:
            logger.error(f"{member.display_name}님에게 부스트 보상 지급 중 오류 발생: {e}", exc_info=True)
        
        logger.info(f"--- 부스트 보상 지급 프로세스 종료: {member.display_name} ---")
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if after.bot: return

        # ▼▼▼ [추가] 해몽 역할(role_resident_regular) 수호자 로직 ▼▼▼
        # 손님(role_guest)이 아닌데, 해몽 역할이 없다면 강제로 다시 부여합니다.
        try:
            haemong_role_id = get_id("role_resident_regular")
            guest_role_id = get_id("role_guest")

            if haemong_role_id and guest_role_id:
                has_guest_role = any(r.id == guest_role_id for r in after.roles)
                has_haemong_role = any(r.id == haemong_role_id for r in after.roles)

                # 손님이 아니고 && 해몽 역할이 없으면 -> 해몽 역할 복구
                if not has_guest_role and not has_haemong_role:
                    haemong_role = after.guild.get_role(haemong_role_id)
                    if haemong_role:
                        await after.add_roles(haemong_role, reason="[자동 복구] 해몽 역할은 필수 기본 역할입니다.")
                        logger.info(f"🛡️ {after.display_name} 님에게서 누락된 '해몽' 역할을 자동으로 복구했습니다.")
        except Exception as e:
            logger.error(f"해몽 역할 자동 복구 로직 수행 중 오류: {e}")
        # ▲▲▲ [추가 완료] ▲▲▲

        # 부스트 상태 변경 확인 및 처리
        if before.premium_since == after.premium_since:
            return

        if before.premium_since is None and after.premium_since is not None:
            await self._handle_boost_start(after)

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
