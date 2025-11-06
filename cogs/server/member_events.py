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
                await channel.send(f"환영합니다, {member.mention}님!", embed=embed, allowed_mentions=discord.AllowedMentions(users=True))

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
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.premium_since == after.premium_since:
            return

        key_role_id = get_id("role_personal_room_key")
        if not key_role_id:
            logger.warning("부스트 감지: '개인 방 열쇠' 역할의 ID가 DB에 설정되지 않았습니다.")
            return

        key_role = after.guild.get_role(key_role_id)
        if not key_role:
            logger.warning(f"부스트 감지: 서버에서 '개인 방 열쇠' 역할(ID: {key_role_id})을 찾을 수 없습니다.")
            return

        if before.premium_since is None and after.premium_since is not None:
            if key_role not in after.roles:
                try:
                    await after.add_roles(key_role, reason="서버 부스트 시작")
                    logger.info(f"{after.display_name}님이 서버 부스트를 시작하여 '개인 방 열쇠' 역할을 지급했습니다.")
                    try:
                        await after.send(
                            f"🎉 **{after.guild.name}** 서버를 부스트해주셔서 감사합니다!\n"
                            "혜택으로 **개인 음성 채널**을 만들 수 있는 `개인 방 열쇠` 역할이 부여되었습니다."
                        )
                    except discord.Forbidden:
                        logger.warning(f"{after.display_name}님에게 DM을 보낼 수 없어 부스트 감사 메시지를 보내지 못했습니다.")
                except discord.Forbidden:
                    logger.error(f"{after.display_name}님에게 '개인 방 열쇠' 역할을 지급하지 못했습니다. (권한 부족)")
                except Exception as e:
                    logger.error(f"{after.display_name}님에게 역할 지급 중 오류 발생: {e}", exc_info=True)

        elif before.premium_since is not None and after.premium_since is None:
            if key_role in after.roles:
                try:
                    await after.remove_roles(key_role, reason="서버 부스트 중지")
                    logger.info(f"{after.display_name}님이 서버 부스트를 중지하여 '개인 방 열쇠' 역할을 회수했습니다.")
                except discord.Forbidden:
                    logger.error(f"{after.display_name}님의 '개인 방 열쇠' 역할을 회수하지 못했습니다. (권한 부족)")
                except Exception as e:
                    logger.error(f"{after.display_name}님의 역할 회수 중 오류 발생: {e}", exc_info=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(MemberEvents(bot))
