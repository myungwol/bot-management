# cogs/features/user_guide.py

import discord
from discord import ui
from discord.ext import commands
import logging
from typing import Optional, Dict, Any
import asyncio
from datetime import datetime
import re

from utils.database import get_id, save_panel_id, get_panel_id, get_embed_from_db, get_panel_components_from_db
from utils.helpers import format_embed_from_db, has_required_roles
from utils.ui_defaults import AGE_ROLE_MAPPING_BY_YEAR

logger = logging.getLogger(__name__)

# --- [View] 3단계: 자기소개 작성 버튼 ---
class IntroductionButtonView(ui.View):
    def __init__(self, cog: 'UserGuide'):
        super().__init__(timeout=None)
        self.cog = cog

    @ui.button(label="자기소개서 작성", style=discord.ButtonStyle.success, emoji="📝", custom_id="guide_submit_intro_btn")
    async def open_modal(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(IntroductionFormModal(self.cog))

# --- [Modal] 자기소개서 입력 양식 ---
class IntroductionFormModal(ui.Modal, title="자기소개서 작성"):
    name = ui.TextInput(label="이름", placeholder="한글/공백 포함 8자 이하", required=True, max_length=8)
    birth_year_str = ui.TextInput(label="출생년도 (YYYY)", placeholder="예: 1998, 2005", required=True, min_length=4, max_length=4)
    gender = ui.TextInput(label="성별", placeholder="성별을 알려주세요.", required=True, max_length=10)
    join_path = ui.TextInput(label="가입 경로", placeholder="텍스트로 간단히 적어주세요.", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, cog: 'UserGuide'):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        # 유효성 검사
        name_input = self.name.value
        if len(name_input) > 8 or not re.match(r"^[가-힣\s]+$", name_input):
            return await interaction.followup.send("❌ 이름은 한글과 공백만 사용하여 8자 이하로 입력해주세요.", ephemeral=True)
        try:
            year = int(self.birth_year_str.value)
            if not (1950 <= year <= datetime.now().year - 13):
                return await interaction.followup.send("❌ 유효하지 않은 출생년도입니다.", ephemeral=True)
        except ValueError:
            return await interaction.followup.send("❌ 출생년도는 숫자로 입력해주세요.", ephemeral=True)

        # 승인 대기 메시지 생성
        approval_embed = discord.Embed(
            title="📝 자기소개서 제출 완료", 
            description=f"{interaction.user.mention}님이 모든 과정을 마쳤습니다.\n위의 인증샷들을 확인하고 승인해주세요.", 
            color=discord.Color.orange()
        )
        approval_embed.add_field(name="이름", value=name_input.strip(), inline=True)
        approval_embed.add_field(name="출생년도", value=self.birth_year_str.value, inline=True)
        approval_embed.add_field(name="성별", value=self.gender.value, inline=True)
        approval_embed.add_field(name="가입 경로", value=self.join_path.value, inline=False)
        approval_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None)
        
        # 알림 역할 멘션
        notify_role_id = get_id("role_notify_guide_approval")
        mention_str = f"<@&{notify_role_id}>" if notify_role_id else "@here"
        
        # 승인 버튼 View 생성
        approval_view = self.cog.GuideApprovalView(self.cog)
        
        await interaction.channel.send(content=mention_str, embed=approval_embed, view=approval_view, allowed_mentions=discord.AllowedMentions(roles=True))
        await interaction.followup.send("✅ 제출되었습니다! 잠시만 기다려주세요.", ephemeral=True)
        
        # 상태 제거 (더 이상 이미지 감지 안 함)
        if interaction.channel.id in self.cog.guide_states:
            del self.cog.guide_states[interaction.channel.id]

# --- [Cog] UserGuide 메인 ---
class UserGuide(commands.Cog):
    # 승인 버튼 View (내부 클래스)
    class GuideApprovalView(ui.View):
        def __init__(self, outer_cog: 'UserGuide'):
            super().__init__(timeout=None)
            self.cog = outer_cog

        @ui.button(label="수락", style=discord.ButtonStyle.success, emoji="✅", custom_id="guide_approve_btn")
        async def approve(self, interaction: discord.Interaction, button: ui.Button):
            required_keys = [
                "role_staff_team_info", "role_staff_team_newbie", 
                "role_staff_leader_info", "role_staff_leader_newbie", 
                "role_staff_deputy_manager", "role_staff_general_manager", 
                "role_staff_deputy_chief", "role_staff_village_chief"
            ]
            if not await has_required_roles(interaction, required_keys, "❌ 권한이 없습니다."):
                return

            await interaction.response.defer(ephemeral=True)
            embed = interaction.message.embeds[0]
            
            # 임베드에서 정보 추출
            try:
                submitted_data = {
                    "name": next(f.value for f in embed.fields if f.name == "이름"),
                    "birth_year": int(next(f.value for f in embed.fields if f.name == "출생년도")),
                    "gender": next(f.value for f in embed.fields if f.name == "성별"),
                    "join_path": next(f.value for f in embed.fields if f.name == "가입 경로")
                }
                # description에서 유저 ID 추출
                match = re.search(r"<@!?(\d+)>", embed.description)
                if not match: raise ValueError("유저 ID를 찾을 수 없음")
                target_user_id = int(match.group(1))
                
                member = await interaction.guild.fetch_member(target_user_id)
            except Exception as e:
                logger.error(f"승인 처리 중 데이터 추출 오류: {e}")
                return await interaction.followup.send("❌ 유저 정보를 찾을 수 없습니다.", ephemeral=True)

            # 역할 및 닉네임 부여 로직
            try:
                final_roles = {role for role in member.roles if role.id != get_id("role_guest")}
                new_role_ids = [get_id("role_resident_rookie"), get_id("role_resident_regular")]
                
                if '남' in submitted_data['gender']: new_role_ids.append(get_id("role_info_male"))
                elif '여' in submitted_data['gender']: new_role_ids.append(get_id("role_info_female"))
                
                year_map = next((item for item in AGE_ROLE_MAPPING_BY_YEAR if item["year"] == submitted_data['birth_year']), None)
                if year_map: new_role_ids.append(get_id(year_map['key']))
                
                for rid in new_role_ids:
                    if rid and (role := interaction.guild.get_role(rid)): final_roles.add(role)
                
                final_nickname = await self.cog.bot.get_cog("PrefixManager").get_final_nickname(member, base_name=submitted_data['name'])
                await member.edit(nick=final_nickname, roles=list(final_roles), reason="안내 승인 완료")
            except Exception as e:
                logger.error(f"정보 업데이트 오류: {e}")
                return await interaction.followup.send("❌ 역할/닉네임 변경 실패. 권한을 확인해주세요.", ephemeral=True)

            # 완료 메시지 전송
            await self.cog.send_public_introduction(interaction.user, member, submitted_data)
            await self.cog.send_main_chat_welcome(member)

            # 버튼 비활성화 및 스레드 정리 예약
            button.disabled = True
            button.label = "승인 완료"
            embed.color = discord.Color.green()
            embed.set_footer(text=f"처리자: {interaction.user.display_name}")
            await interaction.message.edit(embed=embed, view=self)
            
            await interaction.followup.send(f"✅ {member.mention}님의 안내를 완료했습니다!", ephemeral=True)
            if interaction.channel.type == discord.ChannelType.private_thread:
                await interaction.channel.send("🎉 안내가 완료되었습니다! 10초 후 스레드가 닫힙니다.")
                await asyncio.sleep(10)
                await interaction.channel.edit(archived=True, locked=True)

    # 시작 버튼 View (내부 클래스)
    class UserGuidePanelView(ui.View):
        def __init__(self, outer_cog: 'UserGuide'):
            super().__init__(timeout=None)
            self.cog = outer_cog
            
        async def setup_buttons(self):
            self.clear_items()
            comps = await get_panel_components_from_db('user_guide')
            comp = comps[0] if comps else {}
            btn = ui.Button(label=comp.get('label', "안내 시작하기"), style=discord.ButtonStyle.success, emoji=comp.get('emoji', "👋"), custom_id=comp.get('component_key', "start_user_guide"))
            btn.callback = self.start_guide_callback
            self.add_item(btn)
        
        async def start_guide_callback(self, i: discord.Interaction):
            await i.response.defer(ephemeral=True)
            
            # 이미 진행 중인지 확인 (스레드 ID로 체크)
            existing_thread_id = self.cog.user_threads.get(i.user.id)
            if existing_thread_id:
                thread = i.guild.get_thread(existing_thread_id)
                if thread and not thread.archived:
                    return await i.followup.send(f"❌ 이미 진행 중인 안내 스레드가 있습니다: {thread.mention}", ephemeral=True)
            
            try:
                # 스레드 생성
                if (guest_rid := get_id("role_guest")) and (guest_role := i.guild.get_role(guest_rid)) and guest_role not in i.user.roles:
                    await i.user.add_roles(guest_role, reason="안내 시작")
                
                thread = await i.channel.create_thread(name=f"👋ㅣ{i.user.display_name}님의-안내", type=discord.ChannelType.private_thread)
                await thread.add_user(i.user)
                
                # 상태 저장: {채널ID: {"user": 유저ID, "step": 단계}}
                self.cog.guide_states[thread.id] = {"user_id": i.user.id, "step": 1}
                self.cog.user_threads[i.user.id] = thread.id
                
                # 1단계 메시지 전송
                embed_data = await get_embed_from_db("guide_step_1_join_path")
                if embed_data:
                    embed = format_embed_from_db(embed_data)
                    await thread.send(content=i.user.mention, embed=embed)
                
                await i.followup.send(f"✅ 안내 스레드가 생성되었습니다: {thread.mention}", ephemeral=True)
                
            except Exception as e:
                logger.error(f"스레드 생성 오류: {e}", exc_info=True)
                await i.followup.send("❌ 스레드 생성 중 오류가 발생했습니다.", ephemeral=True)

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.public_intro_channel_id: Optional[int] = None
        self.main_chat_channel_id: Optional[int] = None
        
        # 상태 관리
        # guide_states: {thread_id: {"user_id": int, "step": int}}
        self.guide_states: Dict[int, Dict[str, Any]] = {}
        # user_threads: {user_id: thread_id} (중복 생성 방지용)
        self.user_threads: Dict[int, int] = {}
        
        self.panel_view = self.UserGuidePanelView(self)
        logger.info("UserGuide (Interactive) Cog initialized.")

    async def cog_load(self):
        await self.load_configs()
        await self.register_persistent_views()

    async def register_persistent_views(self):
        await self.panel_view.setup_buttons()
        self.bot.add_view(self.panel_view)
        self.bot.add_view(IntroductionButtonView(self))
        self.bot.add_view(self.GuideApprovalView(self))

    async def load_configs(self):
        self.public_intro_channel_id = get_id("introduction_public_channel_id")
        self.main_chat_channel_id = get_id("main_chat_channel_id")

    # --- [이벤트 리스너] 이미지 업로드 감지 및 단계 진행 ---
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not isinstance(message.channel, discord.Thread):
            return
        
        # 현재 채널이 가이드 진행 중인 스레드인지 확인
        state = self.guide_states.get(message.channel.id)
        if not state:
            return
        
        # 해당 스레드의 주인(신규 유저)이 보낸 메시지인지 확인
        if message.author.id != state["user_id"]:
            return
        
        # 이미지가 첨부되었는지 확인
        if not message.attachments:
            return

        current_step = state["step"]
        
        try:
            # 1단계 -> 2단계 (가입 경로 인증 -> 디코올 인증)
            if current_step == 1:
                embed_data = await get_embed_from_db("guide_step_2_dicoall")
                if embed_data:
                    embed = format_embed_from_db(embed_data)
                    await message.channel.send(embed=embed)
                    self.guide_states[message.channel.id]["step"] = 2
                    await message.add_reaction("✅")

            # 2단계 -> 3단계 (디코올 인증 -> 자기소개 버튼)
            elif current_step == 2:
                embed_data = await get_embed_from_db("guide_step_3_intro")
                if embed_data:
                    embed = format_embed_from_db(embed_data)
                    view = IntroductionButtonView(self)
                    await message.channel.send(embed=embed, view=view)
                    self.guide_states[message.channel.id]["step"] = 3 # 버튼 대기 상태
                    await message.add_reaction("✅")
                    
        except Exception as e:
            logger.error(f"가이드 진행 중 오류: {e}", exc_info=True)

    async def send_public_introduction(self, approver: discord.Member, member: discord.Member, data: dict):
        if not self.public_intro_channel_id: return
        channel = self.bot.get_channel(self.public_intro_channel_id)
        if not channel: return

        embed_data = await get_embed_from_db("guide_public_introduction")
        if not embed_data: return
        
        embed = format_embed_from_db(
            embed_data, 
            member_mention=member.mention, 
            submitted_name=data['name'],
            submitted_birth_year=str(data['birth_year']),
            submitted_gender=data['gender'],
            submitted_join_path=data['join_path'],
            approver_mention=approver.mention
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        await channel.send(embed=embed)

    async def send_main_chat_welcome(self, member: discord.Member):
        if not self.main_chat_channel_id: return
        channel = self.bot.get_channel(self.main_chat_channel_id)
        if not channel: return

        message_content = (
            f"{member.mention}님, 해몽 : 海夢에 오신 걸 환영합니다!\n\n"
            f" <a:1124928221243244644:1416125149782212831> <#1414675515759005727> 서버 규칙사항 먼저 숙지해주세요 ! \n\n"
            f" <a:1124928273755938907:1416125162671046736> <#1421544728494604369> 역할은 여기에서 받아주세요 ! \n\n"
            f" <:1367097758577852427:1421788139940479036> 문의 & 건의사항이 있으시다면 <#1414675593533984860> 채널을 사용해주세요 ! \n\n"
            f" <a:1125436475631218769:1416108859956793344> 마지막으로 적응이 힘드시다면 <@&1414627893727858770> 을 멘션 해주세요 ! \n\n"
            f" 해몽에서 즐거운 시간 되시길 바랍니다 ! <:1339999746298740788:1419558757716725760>"
        )
        await channel.send(content=message_content, allowed_mentions=discord.AllowedMentions(users=True, roles=True))

    async def regenerate_panel(self, channel: discord.TextChannel, panel_key: str = "panel_user_guide") -> bool:
        try:
            if (info := get_panel_id("user_guide")) and (old_id := info.get('message_id')):
                try: await (await channel.fetch_message(old_id)).delete()
                except: pass
            
            embed_data = await get_embed_from_db("panel_user_guide")
            if not embed_data: return False
            
            await self.panel_view.setup_buttons()
            new_msg = await channel.send(embed=discord.Embed.from_dict(embed_data), view=self.panel_view)
            await save_panel_id("user_guide", new_msg.id, channel.id)
            return True
        except Exception as e:
            logger.error(f"패널 재설치 오류: {e}")
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(UserGuide(bot))
