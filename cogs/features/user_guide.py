# cogs/features/user_guide.py

import discord
from discord import app_commands
from discord.ext import commands
import logging
import re
from typing import Optional

from utils.database import get_id, get_embed_from_db
from utils.helpers import format_embed_from_db, has_required_roles
from utils.ui_defaults import AGE_ROLE_MAPPING_BY_YEAR

logger = logging.getLogger(__name__)

class UserGuide(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.public_intro_channel_id: Optional[int] = None
        self.main_chat_channel_id: Optional[int] = None
        logger.info("UserGuide (명령어 방식) Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        await self.load_configs()

    async def load_configs(self):
        self.public_intro_channel_id = get_id("introduction_public_channel_id")
        self.main_chat_channel_id = get_id("main_chat_channel_id")
        logger.info("[UserGuide] 채널 설정 로드 완료")

    @app_commands.command(name="안내완료", description="신규 유저의 안내를 완료하고 정식 주민으로 등록합니다.")
    @app_commands.describe(
        member="대상 유저",
        name="이름 (한글/공백 8자 이내)",
        birth_year="출생년도 4자리 (예: 2000)",
        gender="성별",
        join_path="가입 경로"
    )
    @app_commands.choices(gender=[
        app_commands.Choice(name="남성", value="남성"),
        app_commands.Choice(name="여성", value="여성")
    ])
    async def complete_guide(self, interaction: discord.Interaction, member: discord.Member, name: str, birth_year: int, gender: str, join_path: str):
        # 1. 권한 확인
        required_keys = [
            "role_staff_team_info", "role_staff_team_newbie", 
            "role_staff_leader_info", "role_staff_leader_newbie", 
            "role_staff_deputy_manager", "role_staff_general_manager", 
            "role_staff_deputy_chief", "role_staff_village_chief"
        ]
        if not await has_required_roles(interaction, required_keys, "❌ 안내팀 또는 뉴비 관리팀 스태프만 사용할 수 있습니다."):
            return

        # 2. 입력값 검증
        if len(name) > 8 or not re.match(r"^[가-힣\s]+$", name):
            return await interaction.response.send_message("❌ 이름은 한글과 공백만 사용하여 8자 이하로 입력해주세요.", ephemeral=True)
        
        current_year = datetime.now().year
        if not (1950 <= birth_year <= current_year - 13):
            return await interaction.response.send_message(f"❌ 유효하지 않은 출생년도입니다. (1950 ~ {current_year - 13})", ephemeral=True)

        await interaction.response.defer()

        # 3. 역할 및 닉네임 업데이트
        try:
            update_success = await self.update_member_info(interaction.guild, member, name, birth_year, gender)
            if not update_success:
                return await interaction.followup.send("❌ 역할 또는 닉네임 변경 중 오류가 발생했습니다. (봇 권한을 확인해주세요)", ephemeral=True)
        except Exception as e:
            logger.error(f"유저 정보 업데이트 실패: {e}", exc_info=True)
            return await interaction.followup.send("❌ 처리 중 치명적인 오류가 발생했습니다.", ephemeral=True)

        # 4. 메시지 전송 (자기소개 채널 & 메인 챗)
        await self.send_public_introduction(interaction.user, member, name, birth_year, gender, join_path)
        await self.send_main_chat_welcome(member)

        await interaction.followup.send(f"✅ **{member.display_name}**님의 안내를 완료했습니다!", ephemeral=True)

    async def update_member_info(self, guild: discord.Guild, member: discord.Member, name: str, birth_year: int, gender: str) -> bool:
        """유저의 닉네임 변경 및 역할 부여/제거"""
        try:
            # 부여할 역할 찾기
            roles_to_add = []
            
            # 기본 주민 역할
            if r := guild.get_role(get_id("role_resident_rookie")): roles_to_add.append(r)
            if r := guild.get_role(get_id("role_resident_regular")): roles_to_add.append(r)
            
            # 성별 역할
            if gender == "남성":
                if r := guild.get_role(get_id("role_info_male")): roles_to_add.append(r)
            else:
                if r := guild.get_role(get_id("role_info_female")): roles_to_add.append(r)
            
            # 나이 역할
            year_map = next((item for item in AGE_ROLE_MAPPING_BY_YEAR if item["year"] == birth_year), None)
            if year_map:
                if r := guild.get_role(get_id(year_map['key'])): roles_to_add.append(r)

            # 닉네임 계산 (접두사 적용)
            prefix_cog = self.bot.get_cog("PrefixManager")
            final_nickname = name
            # 임시로 역할 리스트를 구성해 접두사 미리 계산 (실제 적용 전)
            if prefix_cog:
                # 현재 역할 + 추가될 역할 - 제거될 역할(Guest) 로 시뮬레이션은 복잡하므로
                # 일단 닉네임을 변경하고, 추후 PrefixManager Listener가 동작하거나, 
                # 여기서 강제로 base_name을 name으로 하여 계산.
                # 여기서는 간단히 name을 적용하고, 역할 부여 후 PrefixManager가 자동 감지하게 하거나 직접 호출.
                pass 

            # 실제 적용
            await member.add_roles(*roles_to_add, reason="안내 완료 명령어 실행")
            
            # 손님 역할 제거
            if guest_role := guild.get_role(get_id("role_guest")):
                if guest_role in member.roles:
                    await member.remove_roles(guest_role, reason="정식 주민 등록")

            # 닉네임 변경 (역할이 부여된 상태여야 접두사가 정확함)
            if prefix_cog:
                final_nickname = await prefix_cog.apply_prefix(member, base_name=name)
            else:
                await member.edit(nick=name, reason="안내 완료 명령어 실행")

            return True
        except discord.Forbidden:
            logger.error(f"{member.display_name}에 대한 권한 오류")
            return False
        except Exception as e:
            logger.error(f"유저 업데이트 중 예외: {e}", exc_info=True)
            return False

    async def send_public_introduction(self, approver: discord.Member, member: discord.Member, name: str, birth_year: int, gender: str, join_path: str):
        """자기소개 채널에 임베드 전송"""
        if not self.public_intro_channel_id: return
        channel = self.bot.get_channel(self.public_intro_channel_id)
        if not isinstance(channel, discord.TextChannel): return

        embed_data = await get_embed_from_db("guide_public_introduction")
        if not embed_data: return
        
        embed = format_embed_from_db(
            embed_data, 
            member_mention=member.mention, 
            submitted_name=name,
            submitted_birth_year=str(birth_year),
            submitted_gender=gender,
            submitted_join_path=join_path,
            approver_mention=approver.mention
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(embed=embed)

    async def send_main_chat_welcome(self, member: discord.Member):
        """메인 채팅방에 환영 메시지 전송"""
        if not self.main_chat_channel_id: return
        channel = self.bot.get_channel(self.main_chat_channel_id)
        if not isinstance(channel, discord.TextChannel): return

        # 설정값 로드 (DB 없으면 기본값)
        role_channel_id = get_id('notification_role_panel_channel_id') or 1421544728494604369
        inquiry_channel_id = get_id('ticket_main_panel_channel_id') or 1414675593533984860
        helper_role_id = get_id('role_staff_newbie_helper') or 1414627893727858770
        rule_channel_id = 1414675515759005727

        message_content = (
            f"{member.mention}님, 해몽 : 海夢에 오신 걸 환영합니다!\n\n"
            f" <a:1124928221243244644:1416125149782212831> <#{rule_channel_id}> 서버 규칙사항 먼저 숙지해주세요 ! \n\n"
            f" <a:1124928273755938907:1416125162671046736> <#{role_channel_id}> 역할은 여기에서 받아주세요 ! \n\n"
            f" <:1367097758577852427:1421788139940479036> 문의 & 건의사항이 있으시다면 <#{inquiry_channel_id}> 채널을 사용해주세요 ! \n\n"
            f" <a:1125436475631218769:1416108859956793344> 마지막으로 적응이 힘드시다면 <@&{helper_role_id}> 을 멘션 해주세요 ! \n\n"
            f" 해몽에서 즐거운 시간 되시길 바랍니다 ! <:1339999746298740788:1419558757716725760>"
        )
        await channel.send(content=message_content, allowed_mentions=discord.AllowedMentions(users=True, roles=True))

    # 패널 관련 메서드는 더 이상 사용하지 않으므로 제거하거나 비워둡니다.
    # 하지만 system.py 등에서 호출할 가능성을 대비해 최소한의 호환성만 남깁니다.
    async def regenerate_panel(self, channel, panel_key=None):
        return False

async def setup(bot: commands.Bot):
    await bot.add_cog(UserGuide(bot))
from datetime import datetime
