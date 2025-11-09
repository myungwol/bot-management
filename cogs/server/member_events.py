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
        self.welcome_channel_id: Optional[int] = None
        self.farewell_channel_id: Optional[int] = None
        logger.info("MemberEvents (입장/퇴장) Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        await self.load_configs()

    async def load_configs(self):
        self.welcome_channel_id = get_id("new_welcome_channel_id")
        self.farewell_channel_id = get_id("farewell_channel_id")
        logger.info("[MemberEvents Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot:
            return

        backup = await get_member_backup(member.id, member.guild.id)
        if backup:
            logger.info(f"재참여 유저 '{member.display_name}'님의 데이터를 발견하여 복구를 시도합니다.")
            try:
                role_ids_to_restore = backup.get('roles', [])
                roles_to_restore = [
                    role for role_id in role_ids_to_restore
                    if (role := member.guild.get_role(role_id)) is not None
                ]
                restored_nick = backup.get('nickname')

                if roles_to_restore or restored_nick:
                    await member.edit(roles=roles_to_restore, nick=restored_nick, reason="서버 재참여로 인한 데이터 복구")

                await delete_member_backup(member.id, member.guild.id)
                logger.info(f"'{member.display_name}'님의 역할과 닉네임을 성공적으로 복구하고 백업 데이터를 삭제했습니다.")
            except discord.Forbidden:
                logger.error(f"'{member.display_name}'님의 데이터 복구에 실패했습니다. (권한 부족) 백업 데이터는 유지됩니다.")
            except Exception as e:
                logger.error(f"'{member.display_name}'님 데이터 복구 중 예기치 않은 오류 발생: {e}", exc_info=True)
            return

        try:
            await supabase.table('user_levels').upsert({
                'user_id': member.id,
                'level': 1,
                'xp': 0
            }, on_conflict='user_id').execute()
            logger.info(f"신규 유저 '{member.display_name}'님의 초기 레벨 데이터를 DB에 생성했습니다.")
        except Exception as e:
            logger.error(f"'{member.display_name}'님의 초기 레벨 데이터 생성 중 오류 발생: {e}", exc_info=True)

        # [수정] 초기 역할 목록에 role_notify_welcome, role_notify_dding 추가
        initial_role_keys = ["role_notify_welcome", "role_notify_dding", "role_guest"]

        roles_to_add: List[discord.Role] = []
        missing_role_names: List[str] = []
        role_key_map = get_config("ROLE_KEY_MAP", {})

        for key in initial_role_keys:
            role_id = get_id(key)
            if role_id and (role := member.guild.get_role(role_id)):
                roles_to_add.append(role)
            else:
                missing_role_names.append(role_key_map.get(key, key))

        if roles_to_add:
            try:
                await member.add_roles(*roles_to_add, reason="서버 참여 시 초기 역할 부여")
            except discord.Forbidden:
                logger.error(f"'{member.display_name}'님에게 초기 역할을 부여하지 못했습니다. (권한 부족)")

        if missing_role_names:
            logger.warning(f"초기 역할 중 일부를 찾을 수 없습니다: {', '.join(missing_role_names)}")

        if self.welcome_channel_id and (channel := self.bot.get_channel(self.welcome_channel_id)):
            embed_data = await get_embed_from_db('welcome_embed')
            if embed_data:
                embed = format_embed_from_db(embed_data, member_mention=member.mention, guild_name=member.guild.name)
                if member.display_avatar:
                    embed.set_thumbnail(url=member.display_avatar.url)
                await channel.send(f"{member.mention}님, 과자 공장에 오신 것을 환영합니다 <a:newheart_01:1427212124588998706> ", embed=embed, allowed_mentions=discord.AllowedMentions(users=True))

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if member.bot:
            return

        try:
            role_ids_to_backup = [role.id for role in member.roles if not role.is_default()]
            await backup_member_data(member.id, member.guild.id, role_ids_to_backup, member.nick)
            logger.info(f"'{member.display_name}'님이 서버를 떠나 역할과 닉네임을 DB에 백업했습니다.")
        except Exception as e:
            logger.error(f"'{member.display_name}'님 데이터 백업 중 오류 발생: {e}", exc_info=True)

        if self.farewell_channel_id and (channel := self.bot.get_channel(self.farewell_channel_id)):
            embed_data = await get_embed_from_db('farewell_embed')
            if embed_data:
                embed = format_embed_from_db(embed_data, member_name=member.name)
                if member.display_avatar:
                    embed.set_thumbnail(url=member.display_avatar.url)
                await channel.send(embed=embed)

    @commands.Cog.listener()
    # ▼▼▼ [수정] 이 함수 전체를 아래 내용으로 교체해주세요. ▼▼▼
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        # 부스트 상태가 변경되지 않았으면 아무것도 하지 않음
        if before.premium_since == after.premium_since:
            return

        # 부스트 보상 역할 키 목록 ('마이룸 열쇠' 제외)
        boost_ticket_role_keys = [f"role_boost_ticket_{i}" for i in range(1, 11)]
        
        all_reward_role_ids = {get_id(key) for key in boost_ticket_role_keys if get_id(key)}
        if not all_reward_role_ids:
            logger.warning("부스트 감지: 보상 역할을 DB에서 찾을 수 없습니다. '/admin setup'으로 역할 동기화가 필요합니다.")
            return

        # --- 시나리오 1: 사용자가 새로 부스트를 시작했을 때 ---
        if before.premium_since is None and after.premium_since is not None:
            logger.info(f"{after.display_name}님이 서버 부스트를 시작했습니다. 보상 지급을 시작합니다.")
            
            # 1. 현재 사용자가 가진 '역할선택권' 역할의 수를 계산합니다.
            existing_reward_roles = [role for role in after.roles if role.id in all_reward_role_ids]
            num_existing_tickets = len(existing_reward_roles)

            # 2. 새로 지급할 역할 2개를 결정합니다. (최대 10개까지)
            roles_to_add_keys = []
            if num_existing_tickets < 10:
                roles_to_add_keys.append(f"role_boost_ticket_{num_existing_tickets + 1}")
            if num_existing_tickets + 1 < 10:
                roles_to_add_keys.append(f"role_boost_ticket_{num_existing_tickets + 2}")

            # 3. discord.Role 객체로 변환
            final_roles_to_add = []
            for key in roles_to_add_keys:
                role_id = get_id(key)
                if role_id and (role := after.guild.get_role(role_id)):
                    if role not in after.roles:
                        final_roles_to_add.append(role)
            
            # 4. 역할 지급 및 DM 발송
            try:
                if final_roles_to_add:
                    await after.add_roles(*final_roles_to_add, reason="서버 부스트 보상 지급")
                    logger.info(f"{after.display_name}님에게 다음 역할을 지급했습니다: {[r.name for r in final_roles_to_add]}")
                
                # DM 발송
                embed_data = await get_embed_from_db("dm_boost_reward")
                if embed_data:
                    # 지급된 모든 보상 역할 목록 생성 (원래 있던 것 + 새로 받은 것)
                    current_reward_roles = sorted(existing_reward_roles + final_roles_to_add, key=lambda r: r.name)
                    roles_list_str = "\n".join([f"- {role.mention}" for role in current_reward_roles]) if current_reward_roles else "지급된 역할 없음"
                    
                    embed = format_embed_from_db(embed_data, member_name=after.display_name, guild_name=after.guild.name, roles_list=roles_list_str)
                    await after.send(embed=embed)

            except discord.Forbidden:
                logger.error(f"{after.display_name}님에게 부스트 보상 역할을 지급하거나 DM을 보내지 못했습니다. (권한 부족)")
            except Exception as e:
                logger.error(f"{after.display_name}님에게 부스트 보상 지급 중 오류 발생: {e}", exc_info=True)

        # --- 시나리오 2: 사용자가 부스트를 중지했을 때 ---
        elif before.premium_since is not None and after.premium_since is None:
            logger.info(f"{after.display_name}님이 서버 부스트를 중지하여 보상 역할을 회수합니다.")
            
            roles_to_remove = [role for role in after.roles if role.id in all_reward_role_ids]
            
            if roles_to_remove:
                try:
                    await after.remove_roles(*roles_to_remove, reason="서버 부스트 중지")
                    logger.info(f"{after.display_name}님에게서 다음 역할을 회수했습니다: {[r.name for r in roles_to_remove]}")
                except discord.Forbidden:
                    logger.error(f"{after.display_name}님의 부스트 보상 역할을 회수하지 못했습니다. (권한 부족)")
                except Exception as e:
                    logger.error(f"{after.display_name}님의 역할 회수 중 오류 발생: {e}", exc_info=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(MemberEvents(bot))
