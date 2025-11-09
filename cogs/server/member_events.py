# cogs/server/member_events.py
"""
서버 멤버의 입장 및 퇴장 이벤트를 처리하는 Cog입니다.
- 새로운 멤버가 서버에 참여하면 환영 메시지를 보내고 초기 역할을 부여합니다.
- 멤버가 서버에서 나가면 작별 메시지를 보냅니다.
"""
import discord
from discord.ext import commands
import logging
from typing import Optional, List

from utils.helpers import format_embed_from_db
from utils.database import get_id, get_embed_from_db, supabase, get_config, backup_member_data, get_member_backup, delete_member_backup

logger = logging.getLogger(__name__)

class MemberEvents(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # __init__에서는 변수만 선언하고 값을 할당하지 않습니다.
        self.welcome_channel_id: Optional[int] = None
        self.farewell_channel_id: Optional[int] = None
        logger.info("MemberEvents (입장/퇴장) Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        # on_ready에서 load_configs를 호출하므로 여기서 호출할 필요가 없습니다.
        pass

    async def load_configs(self):
        # 이 함수는 이제 on_ready에서만 호출됩니다.
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
                logger.info(f"'{member.display_name}'님의 역할과 닉네임을 성공적으로 복구하고 백업 데이터를 삭제했습니다.")
            except discord.Forbidden: logger.error(f"'{member.display_name}'님의 데이터 복구에 실패했습니다. (권한 부족) 백업 데이터는 유지됩니다.")
            except Exception as e: logger.error(f"'{member.display_name}'님 데이터 복구 중 예기치 않은 오류 발생: {e}", exc_info=True)
            return
        try:
            await supabase.table('user_levels').upsert({'user_id': member.id, 'level': 1, 'xp': 0}, on_conflict='user_id').execute()
        except Exception as e: logger.error(f"'{member.display_name}'님의 초기 레벨 데이터 생성 중 오류 발생: {e}", exc_info=True)
        initial_role_keys = ["role_notify_welcome", "role_notify_dding", "role_guest"]
        roles_to_add: List[discord.Role] = []
        role_key_map = get_config("UI_ROLE_KEY_MAP", {})
        for key in initial_role_keys:
            if (role_id := get_id(key)) and (role := member.guild.get_role(role_id)): roles_to_add.append(role)
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
        except Exception as e: logger.error(f"'{member.display_name}'님 데이터 백업 중 오류 발생: {e}", exc_info=True)
        if self.farewell_channel_id and (channel := self.bot.get_channel(self.farewell_channel_id)):
            embed_data = await get_embed_from_db('farewell_embed')
            if embed_data:
                embed = format_embed_from_db(embed_data, member_name=member.name)
                if member.display_avatar: embed.set_thumbnail(url=member.display_avatar.url)
                await channel.send(embed=embed)

    # ▼▼▼ [수정] 이 함수 전체를 아래 내용으로 교체해주세요. ▼▼▼
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.premium_since == after.premium_since:
            return

        boost_ticket_role_keys = [f"role_boost_ticket_{i}" for i in range(1, 11)]
        all_reward_role_ids = {get_id(key) for key in boost_ticket_role_keys if get_id(key)}
        if not all_reward_role_ids:
            logger.warning("부스트 감지: 보상 역할을 DB에서 찾을 수 없습니다.")
            return

        # [핵심 수정 1] 이벤트 발생 시점에 DB 캐시에서 최신 채널 ID를 다시 가져옵니다.
        boost_channel_id = get_id("boost_log_channel_id")
        boost_channel = self.bot.get_channel(boost_channel_id) if boost_channel_id else None

        # --- 시나리오 1: 사용자가 새로 부스트를 시작했을 때 ---
        if before.premium_since is None and after.premium_since is not None:
            logger.info(f"{after.display_name}님이 서버 부스트를 시작했습니다. 보상 지급을 시작합니다.")
            
            existing_reward_roles = [role for role in after.roles if role.id in all_reward_role_ids]
            num_existing_tickets = len(existing_reward_roles)

            # [핵심 수정 2] 역할 지급 로직을 단순하고 명확하게 변경
            roles_to_add_keys = []
            # 지급할 첫 번째 역할 번호
            first_role_num = num_existing_tickets + 1
            if first_role_num <= 10:
                roles_to_add_keys.append(f"role_boost_ticket_{first_role_num}")
            
            # 지급할 두 번째 역할 번호
            second_role_num = num_existing_tickets + 2
            if second_role_num <= 10:
                roles_to_add_keys.append(f"role_boost_ticket_{second_role_num}")

            final_roles_to_add = [role for key in roles_to_add_keys if (role_id := get_id(key)) and (role := after.guild.get_role(role_id)) and role not in after.roles]
            
            try:
                if final_roles_to_add:
                    await after.add_roles(*final_roles_to_add, reason="서버 부스트 보상 지급")
                
                if boost_channel:
                    embed_data = await get_embed_from_db("log_boost_start")
                    if embed_data:
                        current_reward_roles = sorted(existing_reward_roles + final_roles_to_add, key=lambda r: r.name)
                        roles_list_str = "\n".join([f"- {role.mention}" for role in current_reward_roles]) if current_reward_roles else "지급된 역할 없음"
                        embed = format_embed_from_db(embed_data, member_mention=after.mention, roles_list=roles_list_str)
                        if after.display_avatar:
                            embed.set_author(name=after.display_name, icon_url=after.display_avatar.url)
                        await boost_channel.send(content=after.mention, embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
                else:
                    logger.warning("부스트 로그 채널이 설정되지 않아 부스트 시작 알림을 보낼 수 없습니다.")

            except discord.Forbidden:
                logger.error(f"{after.display_name}님의 부스트 보상 처리 중 권한 오류 발생")
            except Exception as e:
                logger.error(f"{after.display_name}님에게 부스트 보상 지급 중 오류 발생: {e}", exc_info=True)

        # --- 시나리오 2: 사용자가 부스트를 중지했을 때 ---
        elif before.premium_since is not None and after.premium_since is None:
            logger.info(f"{after.display_name}님이 서버 부스트를 중지하여 보상 역할을 회수합니다.")
            
            roles_to_remove = [role for role in after.roles if role.id in all_reward_role_ids]
            
            try:
                if roles_to_remove:
                    await after.remove_roles(*roles_to_remove, reason="서버 부스트 중지")
                
                if boost_channel:
                    embed_data = await get_embed_from_db("log_boost_stop")
                    if embed_data:
                        embed = format_embed_from_db(embed_data, member_mention=after.mention)
                        if after.display_avatar:
                            embed.set_author(name=after.display_name, icon_url=after.display_avatar.url)
                        await boost_channel.send(embed=embed)
                else:
                    logger.warning("부스트 로그 채널이 설정되지 않아 부스트 중지 알림을 보낼 수 없습니다.")
                    
            except discord.Forbidden:
                logger.error(f"{after.display_name}님의 부스트 보상 역할을 회수하지 못했습니다. (권한 부족)")
            except Exception as e:
                logger.error(f"{after.display_name}님의 역할 회수 중 오류 발생: {e}", exc_info=True)
    # ▲▲▲ [수정 완료] ▲▲▲

async def setup(bot: commands.Bot):
    await bot.add_cog(MemberEvents(bot))
