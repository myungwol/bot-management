# cogs/server/onboarding.py

import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import copy

from utils.database import (
    get_id, save_panel_id, get_panel_id, get_cooldown, set_cooldown, 
    get_embed_from_db, get_onboarding_steps, get_panel_components_from_db, get_config
)
from utils.helpers import format_embed_from_db, format_seconds_to_hms, has_required_roles

logger = logging.getLogger(__name__)

class RejectionReasonModal(ui.Modal, title="거절 사유 입력"):
    reason = ui.TextInput(label="거절 사유", placeholder="거절하는 이유를 구체적으로 입력해주세요.", style=discord.TextStyle.paragraph, required=True, max_length=200)
    async def on_submit(self, interaction: discord.Interaction): await interaction.response.defer()

class IntroductionModal(ui.Modal, title="주민 등록증"):
    name = ui.TextInput(label="이름", placeholder="마을에서 사용할 이름을 적어주세요", required=True, max_length=12)
    hobby = ui.TextInput(label="취미/좋아하는 것", placeholder="취미나 좋아하는 것을 자유롭게 적어주세요", style=discord.TextStyle.paragraph, required=True, max_length=500)
    path = ui.TextInput(label="가입 경로", placeholder="예: Disboard, ○○의 초대 등", style=discord.TextStyle.paragraph, required=True, max_length=200)
    
    def __init__(self, cog_instance: 'Onboarding', gender: str, birth_year: str):
        super().__init__()
        self.onboarding_cog = cog_instance
        self.gender = gender
        self.public_birth_year_display = birth_year
        
        self.private_birth_year_input: Optional[ui.TextInput] = None
        if self.public_birth_year_display == "비공개":
            self.private_birth_year_input = ui.TextInput(
                label="출생 연도 (촌장/부촌장 확인용)",
                placeholder="YYYY 형식으로 입력해주세요. 비공개 처리됩니다.",
                required=True, min_length=4, max_length=4
            )
            self.add_item(self.private_birth_year_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            actual_birth_year_for_validation = self.public_birth_year_display
            birth_year_for_approval_channel = self.public_birth_year_display

            if self.private_birth_year_input:
                private_year_str = self.private_birth_year_input.value
                try:
                    year = int(private_year_str)
                    current_year = datetime.now(timezone.utc).year
                    if not (1940 <= year <= current_year - 16):
                        await interaction.followup.send("❌ 유효하지 않은 출생 연도입니다. 만 16세 이상만 가입할 수 있습니다.", ephemeral=True)
                        return
                    actual_birth_year_for_validation = str(year)
                except ValueError:
                    await interaction.followup.send("❌ 출생 연도는 숫자로 입력해주세요 (예: 2001).", ephemeral=True)
                    return
                
                private_log_channel = self.onboarding_cog.private_age_log_channel
                if private_log_channel:
                    log_embed = discord.Embed(
                        title="📝 비공개 나이 제출 기록",
                        description=f"{interaction.user.mention} 님이 비공개 옵션을 선택하고 실제 출생 연도를 제출했습니다.",
                        color=discord.Color.blurple()
                    )
                    log_embed.add_field(name="제출자", value=f"{interaction.user.mention} (`{interaction.user.id}`)")
                    log_embed.add_field(name="제출된 연도", value=f"`{actual_birth_year_for_validation}`년")
                    log_embed.set_footer(text="이 정보는 나이 제한 확인 목적으로만 사용됩니다.")
                    await private_log_channel.send(embed=log_embed)
                
                birth_year_for_approval_channel = "비공개"

            approval_channel = self.onboarding_cog.approval_channel
            if not approval_channel: await interaction.followup.send("❌ 오류: 승인 채널을 찾을 수 없습니다.", ephemeral=True); return
            embed_data = await get_embed_from_db("embed_onboarding_approval")
            if not embed_data: await interaction.followup.send("❌ 오류: 승인용 메시지 템플릿을 찾을 수 없습니다.", ephemeral=True); return
            
            embed = format_embed_from_db(embed_data, member_mention=interaction.user.mention, member_name=interaction.user.display_name)
            if interaction.user.display_avatar: embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            embed.add_field(name="이름", value=self.name.value, inline=False)
            embed.add_field(name="출생 연도", value=birth_year_for_approval_channel, inline=False)
            embed.add_field(name="성별", value=self.gender, inline=False)
            embed.add_field(name="취미/좋아하는 것", value=self.hobby.value, inline=False)
            embed.add_field(name="가입 경로", value=self.path.value, inline=False)
            
            view = ApprovalView(
                author=interaction.user, 
                original_embed=embed, 
                cog_instance=self.onboarding_cog,
                actual_birth_year=actual_birth_year_for_validation
            )
            approval_role_id = self.onboarding_cog.approval_role_id
            content = f"<@&{approval_role_id}> 새로운 주민 등록 신청서가 제출되었습니다." if approval_role_id else "새로운 주민 등록 신청서가 제출되었습니다."
            await approval_channel.send(content=content, embed=embed, view=view, allowed_mentions=discord.AllowedMentions(roles=True))
            await interaction.followup.send("✅ 주민 등록증을 담당자에게 제출했습니다.", ephemeral=True)
        except Exception as e: 
            logger.error(f"자기소개서 제출 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 예기치 않은 오류가 발생했습니다.", ephemeral=True)

class GenderAgeSelectView(ui.View):
    def __init__(self, cog: 'Onboarding'):
        super().__init__(timeout=300)
        self.cog = cog
        self.selected_gender: Optional[str] = None
        self.selected_birth_year: Optional[str] = None
        
        self.choices_config = get_config("ONBOARDING_CHOICES", {})
        
        gender_options = [discord.SelectOption(**opt) for opt in self.choices_config.get("gender", [])]
        self.gender_select = ui.Select(
            placeholder="성별을 선택해주세요...",
            options=gender_options or [discord.SelectOption(label="오류", value="error")],
            disabled=not gender_options,
            custom_id="onboarding_gender_select"
        )
        self.gender_select.callback = self.on_gender_select
        self.add_item(self.gender_select)
        
        decade_options = [
            discord.SelectOption(label="2000년대", value="2000s"),
            discord.SelectOption(label="1990년대", value="1990s"),
            discord.SelectOption(label="1980년대", value="1980s"),
            discord.SelectOption(label="1970년대", value="1970s"),
            discord.SelectOption(label="비공개", value="private")
        ]
        self.decade_select = ui.Select(placeholder="태어난 연대를 선택해주세요...", options=decade_options, custom_id="onboarding_decade_select")
        self.decade_select.callback = self.on_decade_select
        self.add_item(self.decade_select)

        self.year_select = ui.Select(
            placeholder="먼저 연대를 선택해주세요...", 
            disabled=True, 
            custom_id="onboarding_year_select",
            options=[discord.SelectOption(label="placeholder", value="placeholder")]
        )
        self.year_select.callback = self.on_year_select
        self.add_item(self.year_select)

        self.proceed_button = ui.Button(label="다음으로", style=discord.ButtonStyle.success, disabled=True, custom_id="onboarding_proceed")
        self.proceed_button.callback = self.on_proceed
        self.add_item(self.proceed_button)

    async def _update_view_state(self, interaction: discord.Interaction):
        if self.selected_gender and self.selected_birth_year:
            self.proceed_button.disabled = False
        await interaction.response.edit_message(view=self)

    async def on_gender_select(self, interaction: discord.Interaction):
        self.selected_gender = interaction.data["values"][0]
        await self._update_view_state(interaction)

    async def on_decade_select(self, interaction: discord.Interaction):
        selected_decade = interaction.data["values"][0]
        
        if selected_decade == "private":
            self.selected_birth_year = "비공개"
            self.year_select.placeholder = "비공개가 선택되었습니다"
            self.year_select.disabled = True
            self.year_select.options = [discord.SelectOption(label="placeholder", value="placeholder")]
            await self._update_view_state(interaction)
            return

        year_options_data = self.choices_config.get("birth_year_groups", {}).get(selected_decade, [])
        year_options = [discord.SelectOption(**opt) for opt in year_options_data]
        
        self.year_select.options = year_options or [discord.SelectOption(label="오류", value="error")]
        self.year_select.placeholder = f"{selected_decade}년대에서 선택..."
        self.year_select.disabled = not year_options
        
        self.selected_birth_year = None
        self.proceed_button.disabled = True
        
        await interaction.response.edit_message(view=self)

    async def on_year_select(self, interaction: discord.Interaction):
        self.selected_birth_year = interaction.data["values"][0]
        await self._update_view_state(interaction)

    async def on_proceed(self, interaction: discord.Interaction):
        modal = IntroductionModal(self.cog, self.selected_gender, self.selected_birth_year)
        await interaction.response.send_modal(modal)
        await interaction.delete_original_response()

class ApprovalView(ui.View):
    def __init__(self, author: discord.Member, original_embed: discord.Embed, cog_instance: 'Onboarding', actual_birth_year: str):
        super().__init__(timeout=None)
        self.author_id = author.id
        self.original_embed = copy.deepcopy(original_embed)
        self.onboarding_cog = cog_instance
        self.actual_birth_year = actual_birth_year
    
    @ui.button(label="승인", style=discord.ButtonStyle.success, custom_id="onboarding_approve")
    async def approve(self, i: discord.Interaction, b: ui.Button): await self._handle_approval_flow(i, is_approved=True)
    
    @ui.button(label="거절", style=discord.ButtonStyle.danger, custom_id="onboarding_reject")
    async def reject(self, i: discord.Interaction, b: ui.Button): await self._handle_approval_flow(i, is_approved=False)
    
    async def _check_permission(self, interaction: discord.Interaction) -> bool:
        required_keys = ["role_approval", "role_staff_village_chief", "role_staff_deputy_chief"]
        return await has_required_roles(interaction, required_keys)
    
    def _get_field_value(self, embed: discord.Embed, field_name: str) -> Optional[str]:
        return next((f.value for f in embed.fields if f.name == field_name), None)
        
    async def _handle_approval_flow(self, interaction: discord.Interaction, is_approved: bool):
        if not await self._check_permission(interaction):
            return

        lock = self.onboarding_cog.get_user_lock(self.author_id)
        if lock.locked():
            await interaction.response.send_message("⏳ 다른 관리자가 이 신청을 처리 중입니다. 잠시 후 다시 시도해주세요.", ephemeral=True)
            return
        
        rejection_reason = None
        if not is_approved:
            rejection_modal = RejectionReasonModal()
            await interaction.response.send_modal(rejection_modal)
            timed_out = await rejection_modal.wait()
            
            if timed_out or not rejection_modal.reason.value:
                return 
            
            rejection_reason = rejection_modal.reason.value
        else:
            await interaction.response.defer(ephemeral=True)

        await lock.acquire()
        try:
            for item in self.children:
                item.disabled = True
            await interaction.edit_original_response(content=f"⏳ {interaction.user.mention}님이 처리 중...", view=self)
            
            member = interaction.guild.get_member(self.author_id)
            if not member:
                await interaction.followup.send("❌ 대상 멤버를 찾을 수 없습니다. 서버에서 나간 것 같습니다.", ephemeral=True)
                try:
                    await interaction.message.delete()
                except (discord.NotFound, discord.HTTPException):
                    pass
                return

            moderator = interaction.user
            if is_approved:
                success, results = await self._process_approval(moderator, member)
            else:
                # ▼▼▼ [핵심 수정] 변수명을 'reason'에서 'rejection_reason'으로 변경합니다. ▼▼▼
                success, results = await self._process_rejection(moderator, member, rejection_reason)

            status_text = "승인" if is_approved else "거절"
            if success:
                message = await interaction.followup.send(f"✅ **{status_text}** 처리가 완료되었습니다.", ephemeral=True, wait=True)
                await asyncio.sleep(3)
                await message.delete()
            else:
                error_report = f"❌ **{status_text}** 처리 중 오류가 발생했습니다:\n" + "\n".join(f"- {res}" for res in results)
                await interaction.followup.send(error_report, ephemeral=True)

            await interaction.delete_original_response()
        
        finally:
            lock.release()

    async def _process_approval(self, moderator: discord.Member, member: discord.Member) -> (bool, List[str]):
        errors: List[str] = []

        role_grant_error = await self._grant_roles(member)
        if role_grant_error:
            logger.error(f"자기소개 승인 실패 (1/4): 역할 부여 중 오류 - {role_grant_error}")
            errors.append(role_grant_error)
            return False, errors

        nickname_update_error = await self._update_nickname(member)
        if nickname_update_error:
            logger.warning(f"자기소개 승인 중 경고 (2/4): 닉네임 업데이트 실패 - {nickname_update_error}")
            errors.append(nickname_update_error)

        public_welcome_error = await self._send_public_welcome(moderator, member)
        if public_welcome_error:
            logger.warning(f"자기소개 승인 중 경고 (3/4): 공개 환영 메시지 실패 - {public_welcome_error}")
            errors.append(public_welcome_error)
            
        main_chat_error = await self._send_main_chat_welcome(member)
        if main_chat_error:
            logger.warning(f"자기소개 승인 중 경고 (4/4): 메인 채팅 환영 실패 - {main_chat_error}")
            errors.append(main_chat_error)

        await self._send_dm_notification(member, is_approved=True)

        return True, errors

    async def _process_rejection(self, moderator: discord.Member, member: discord.Member, reason: str) -> (bool, List[str]):
        tasks = [ self._send_rejection_log(moderator, member, reason), self._send_dm_notification(member, is_approved=False, reason=reason) ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        failed_tasks_messages = [res for res in results if isinstance(res, str)]
        return not failed_tasks_messages, failed_tasks_messages

    async def _grant_roles(self, member: discord.Member) -> Optional[str]:
        try:
            guild = member.guild; roles_to_add: List[discord.Role] = []; failed_to_find_roles: List[str] = []
            
            role_keys_to_grant = [
                "role_resident", 
                "role_resident_rookie", 
                "role_warning_separator",
                "role_shop_separator"
            ]
            for key in role_keys_to_grant:
                if (rid := get_id(key)) and (r := guild.get_role(rid)):
                    roles_to_add.append(r)
                else: failed_to_find_roles.append(key)
            
            gender_field = self._get_field_value(self.original_embed, "성별")
            if gender_field == "남성":
                if (rid := get_id("role_info_male")) and (r := guild.get_role(rid)): roles_to_add.append(r)
            elif gender_field == "여성":
                if (rid := get_id("role_info_female")) and (r := guild.get_role(rid)): roles_to_add.append(r)

            age_role_mapping = get_config("AGE_ROLE_MAPPING", [])
            
            # ▼▼▼▼▼ 핵심 수정 시작 ▼▼▼▼▼
            public_birth_year_display = self._get_field_value(self.original_embed, "출생 연도")
            
            # 1. 공개적으로 '비공개'를 선택했는지 먼저 확인합니다.
            if public_birth_year_display == "비공개":
                if (rid := get_id("role_info_age_private")) and (r := guild.get_role(rid)):
                    roles_to_add.append(r)
                else:
                    failed_to_find_roles.append("role_info_age_private")
            
            # 2. '비공개'가 아닐 경우에만 실제 나이 기반 역할을 부여합니다.
            elif self.actual_birth_year.isdigit():
                birth_year = int(self.actual_birth_year)
                age_limit = 16
                current_year = datetime.now(timezone.utc).year
                if (current_year - birth_year) < age_limit:
                    return f"연령 제한: 사용자가 만 {age_limit}세 미만입니다. (출생 연도: {birth_year})"

                for mapping in age_role_mapping:
                    if mapping["range"][0] <= birth_year < mapping["range"][1]:
                        if (rid := get_id(mapping["key"])) and (r := guild.get_role(rid)):
                            roles_to_add.append(r)
                        else:
                            failed_to_find_roles.append(mapping["key"])
                        break
            # ▲▲▲▲▲ 핵심 수정 종료 ▲▲▲▲▲
            
            if roles_to_add: await member.add_roles(*list(set(roles_to_add)), reason="자기소개 승인")
            if (rid := get_id("role_guest")) and (r := guild.get_role(rid)) and r in member.roles: await member.remove_roles(r, reason="자기소개 승인 완료")
            
            if failed_to_find_roles: 
                return f"역할을 찾을 수 없음: `{', '.join(failed_to_find_roles)}`. `/setup` 명령어로 역할을 동기화해주세요."
        except discord.Forbidden: 
            return "봇 권한 부족: 역할을 부여/제거할 권한이 없습니다."
        except Exception as e:
            logger.error(f"역할 부여 중 오류: {e}", exc_info=True)
            return "역할 부여 중 알 수 없는 오류가 발생했습니다."
        return None
        
    async def _update_nickname(self, member: discord.Member) -> Optional[str]:
        try:
            if (nick_cog := self.onboarding_cog.bot.get_cog("Nicknames")) and (name_field := self._get_field_value(self.original_embed, "이름")):
                await nick_cog.update_nickname(member, base_name_override=name_field)
        except discord.Forbidden: return "봇 권한 부족: 봇의 역할이 멤버의 역할보다 낮아 닉네임을 변경할 수 없습니다."
        except Exception as e:
            logger.error(f"닉네임 업데이트 중 오류: {e}", exc_info=True); return f"닉네임 업데이트 중 알 수 없는 오류 발생."
        return None
    
    async def _send_public_welcome(self, moderator: discord.Member, member: discord.Member) -> Optional[str]:
        try:
            ch_id = self.onboarding_cog.introduction_channel_id
            if ch_id and (ch := member.guild.get_channel(ch_id)):
                embed = discord.Embed(title="📝 자기소개", color=discord.Color.green())
                embed.add_field(name="주민", value=member.mention, inline=False)
                
                for field in self.original_embed.fields: 
                    embed.add_field(name=field.name, value=field.value, inline=False)
                
                embed.add_field(name="담당자", value=moderator.mention, inline=False)
                
                if member.display_avatar: 
                    embed.set_thumbnail(url=member.display_avatar.url)
                await ch.send(content=f"||{member.mention}||", embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
        except Exception as e:
            logger.error(f"공개 환영 메시지 전송 실패: {e}", exc_info=True); return "자기소개 채널에 메시지 전송 실패."
        return None
    
    async def _send_main_chat_welcome(self, member: discord.Member) -> Optional[str]:
        try:
            ch_id = self.onboarding_cog.main_chat_channel_id
            if ch_id and (ch := member.guild.get_channel(ch_id)):
                embed_data = await get_embed_from_db("embed_main_chat_welcome")
                if not embed_data: return "메인 채팅 환영 임베드를 찾을 수 없음."
                
                staff_role_id = get_id('role_staff_newbie_helper') or 1412052122949779517
                nickname_channel_id = get_id('nickname_panel_channel_id') or 1412052293096050729
                role_channel_id = get_id('auto_role_channel_id') or 1412052301115424799
                inquiry_channel_id = get_id('inquiry_panel_channel_id') or 1412052236736925737
                bot_guide_channel_id = get_id('bot_guide_channel_id') or 1412052405477970040 
                festival_channel_id = get_id('festival_channel_id') or 1412052244349845627

                format_args = {
                    "member_mention": member.mention,
                    "staff_role_mention": f"<@&{staff_role_id}>",
                    "nickname_channel_mention": f"<#{nickname_channel_id}>",
                    "role_channel_mention": f"<#{role_channel_id}>",
                    "inquiry_channel_mention": f"<#{inquiry_channel_id}>",
                    "bot_guide_channel_mention": f"<#{bot_guide_channel_id}>",
                    "festival_channel_mention": f"<#{festival_channel_id}>"
                }

                embed = format_embed_from_db(embed_data, **format_args)
                await ch.send(content=member.mention, embed=embed, allowed_mentions=discord.AllowedMentions(users=True, roles=True))
        except Exception as e:
            logger.error(f"메인 채팅 환영 메시지 전송 실패: {e}", exc_info=True); return "메인 채팅 채널에 메시지 전송 실패."
        return None
    
    async def _send_dm_notification(self, member: discord.Member, is_approved: bool, reason: str = "") -> None:
        try:
            guild_name = member.guild.name
            if is_approved:
                embed_data = await get_embed_from_db("dm_onboarding_approved")
                if not embed_data: return
                embed = format_embed_from_db(embed_data, guild_name=guild_name)
            else:
                embed_data = await get_embed_from_db("dm_onboarding_rejected")
                if not embed_data: return
                embed = format_embed_from_db(embed_data, guild_name=guild_name)
                embed.add_field(name="사유", value=reason, inline=False)
                panel_channel_id = self.onboarding_cog.panel_channel_id
                if panel_channel_id:
                    embed.add_field(name="재신청", value=f"<#{panel_channel_id}> 에서 다시 진행해주세요.", inline=False)
            await member.send(embed=embed)
        except discord.Forbidden: logger.warning(f"{member.display_name}님에게 DM을 보낼 수 없습니다 (DM 차단됨).")
        except Exception as e: logger.error(f"DM 알림 전송 실패: {e}", exc_info=True)
        return None
        
    async def _send_rejection_log(self, moderator: discord.Member, member: discord.Member, reason: str) -> Optional[str]:
        try:
            ch_id = self.onboarding_cog.rejection_log_channel_id
            if ch_id and (ch := member.guild.get_channel(ch_id)):
                embed = discord.Embed(title="❌ 주민 등록이 거절되었습니다", color=discord.Color.red())
                embed.add_field(name="여행객", value=member.mention, inline=False)
                for field in self.original_embed.fields: embed.add_field(name=field.name, value=field.value, inline=False)
                embed.add_field(name="거절 사유", value=reason, inline=False); embed.add_field(name="담당자", value=moderator.mention, inline=False)
                if member.display_avatar: embed.set_thumbnail(url=member.display_avatar.url)
                
                await ch.send(content=f"||{member.mention}||", embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
        except Exception as e:
            logger.error(f"거절 로그 전송 실패: {e}", exc_info=True); return "거절 로그 채널에 메시지 전송 실패."
        return None

class OnboardingGuideView(ui.View):
    def __init__(self, cog_instance: 'Onboarding', steps_data: List[Dict[str, Any]], user: discord.User):
        super().__init__(timeout=300); self.onboarding_cog = cog_instance; self.steps_data = steps_data
        self.user = user; self.current_step = 0; self.message: Optional[discord.WebhookMessage] = None
    async def on_timeout(self) -> None:
        if self.message:
            for item in self.children: item.disabled = True
            try: await self.message.edit(content="안내 시간이 만료되었습니다. 처음부터 다시 시작해주세요.", view=self)
            except (discord.NotFound, discord.HTTPException): pass
    def stop(self):
        super().stop()
    def _update_components(self):
        self.clear_items(); step_info = self.steps_data[self.current_step]
        is_first = self.current_step == 0; is_last = self.current_step == len(self.steps_data) - 1
        prev_button = ui.Button(label="◀ 이전", style=discord.ButtonStyle.secondary, custom_id="onboarding_prev", row=1, disabled=is_first)
        prev_button.callback = self.go_previous; self.add_item(prev_button)
        step_type = step_info.get("step_type")
        if step_type == "intro":
             intro_button = ui.Button(label=step_info.get("button_label", "주민 등록증 작성하기"), style=discord.ButtonStyle.success, custom_id="onboarding_intro")
             intro_button.callback = self.create_introduction; self.add_item(intro_button)
        else:
            next_button = ui.Button(label="다음 ▶", style=discord.ButtonStyle.primary, custom_id="onboarding_next", disabled=is_last)
            next_button.callback = self.go_next; self.add_item(next_button)

    async def _grant_step_role(self, interaction: discord.Interaction, role_key_to_add: str):
        role_id = get_id(role_key_to_add)
        if role_id and isinstance(interaction.user, discord.Member):
            if role := interaction.guild.get_role(role_id):
                try:
                    if role not in interaction.user.roles: await interaction.user.add_roles(role, reason="온보딩 진행")
                except Exception as e: logger.error(f"온보딩 가이드 중 역할 부여 실패: {e}")
            else: logger.warning(f"온보딩: DB에 설정된 역할 ID({role_id})를 서버에서 찾을 수 없습니다. ({role_key_to_add})")
    
    def _prepare_next_step_message_content(self) -> dict:
        step_info = self.steps_data[self.current_step]
        embed_data = step_info.get("embed_data", {}).get("embed_data")
        if not embed_data: embed = discord.Embed(title="오류", description="이 단계의 표시 데이터를 찾을 수 없습니다.", color=discord.Color.red())
        else: embed = format_embed_from_db(embed_data, member_mention=self.user.mention)
        self._update_components()
        return {"embed": embed, "view": self}

    # ▼▼▼ [핵심 수정] 작업 순서를 보장하도록 로직 변경 ▼▼▼
    async def go_next(self, interaction: discord.Interaction):
        await interaction.response.defer()

        # 1. 현재 단계에 부여할 역할이 있다면, 먼저 부여하고 기다립니다.
        step_info = self.steps_data[self.current_step]
        role_key_to_add = step_info.get("role_key_to_add")
        if role_key_to_add:
            await self._grant_step_role(interaction, role_key_to_add)

        # 2. 다음 단계로 인덱스를 이동합니다.
        if self.current_step < len(self.steps_data) - 1:
            self.current_step += 1
        
        # 3. 새로운 단계의 콘텐츠를 준비합니다.
        content = self._prepare_next_step_message_content()
        
        # 4. 모든 작업이 끝난 후, 메시지를 수정합니다.
        if self.message:
            await self.message.edit(**content)
    # ▲▲▲ [핵심 수정] ▲▲▲

    async def go_previous(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.current_step > 0: self.current_step -= 1
        content = self._prepare_next_step_message_content()
        if self.message: await self.message.edit(**content)

    async def create_introduction(self, interaction: discord.Interaction):
        view = GenderAgeSelectView(self.onboarding_cog)
        await interaction.response.send_message(
            "먼저, 당신의 성별과 태어난 연도를 선택해주세요.",
            view=view,
            ephemeral=True
        )
        if self.message:
            try: await self.message.delete()
            except (discord.NotFound, discord.HTTPException): pass
        self.stop()

class OnboardingPanelView(ui.View):
    def __init__(self, cog_instance: 'Onboarding'):
        super().__init__(timeout=None)
        self.onboarding_cog = cog_instance
    async def setup_buttons(self):
        self.clear_items()
        button_styles = get_config("DISCORD_BUTTON_STYLES_MAP", {})
        components_data = await get_panel_components_from_db('onboarding')
        if not components_data:
            default_button = ui.Button(label="안내 읽기", style=discord.ButtonStyle.success, custom_id="start_onboarding_guide")
            default_button.callback = self.start_guide_callback
            self.add_item(default_button)
            return
        for comp in components_data:
            if comp.get('component_type') == 'button' and comp.get('component_key'):
                style = button_styles.get(comp.get('style','secondary'), discord.ButtonStyle.secondary)
                button = ui.Button(label=comp.get('label'),style=style,emoji=comp.get('emoji'),row=comp.get('row'),custom_id=comp.get('component_key'))
                if comp.get('component_key') == 'start_onboarding_guide':
                    button.callback = self.start_guide_callback
                self.add_item(button)
    async def start_guide_callback(self, interaction: discord.Interaction):
        user_id_str = str(interaction.user.id)
        cooldown_key = "onboarding_start"
        try:
            cooldown_seconds = int(get_config("ONBOARDING_COOLDOWN_SECONDS", 300))
        except (ValueError, TypeError):
            cooldown_seconds = 300
            logger.warning("ONBOARDING_COOLDOWN_SECONDS 설정값이 숫자가 아니므로 기본값(300)을 사용합니다.")
        
        utc_now = datetime.now(timezone.utc).timestamp()
        last_time = await get_cooldown(user_id_str, cooldown_key)
        
        if last_time > 0 and (utc_now - last_time) < cooldown_seconds:
            time_remaining = cooldown_seconds - (utc_now - last_time)
            formatted_time = format_seconds_to_hms(time_remaining)
            message = f"❌ 다음 안내는 **{formatted_time}** 후에 볼 수 있습니다. 잠시만 기다려주세요."
            await interaction.response.send_message(message, ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True, thinking=True)
        await set_cooldown(user_id_str, cooldown_key)
        try:
            steps = await get_onboarding_steps()
            if not steps: 
                await interaction.followup.send("현재 안내를 준비 중입니다. 잠시만 기다려주세요.", ephemeral=True)
                return
            guide_view = OnboardingGuideView(self.onboarding_cog, steps, interaction.user)
            content = guide_view._prepare_next_step_message_content()
            message = await interaction.followup.send(**content, ephemeral=True, wait=True)
            guide_view.message = message
            await guide_view.wait()
        except Exception as e:
            logger.error(f"안내 가이드 시작 중 오류: {e}", exc_info=True)
            if not interaction.is_done():
                try: await interaction.followup.send("오류가 발생했습니다. 다시 시도해주세요.", ephemeral=True)
                except discord.NotFound: logger.warning("안내 가이드 시작 오류 메시지 전송 실패: Interaction not found.")

class Onboarding(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_channel_id: Optional[int] = None
        self.approval_channel_id: Optional[int] = None
        self.introduction_channel_id: Optional[int] = None
        self.rejection_log_channel_id: Optional[int] = None
        self.approval_role_id: Optional[int] = None
        self.main_chat_channel_id: Optional[int] = None
        self.private_age_log_channel_id: Optional[int] = None
        self.master_role_id: Optional[int] = None
        self.vice_master_role_id: Optional[int] = None
        self.view_instance = None
        logger.info("Onboarding Cog가 성공적으로 초기화되었습니다.")
        self._user_locks: Dict[int, asyncio.Lock] = {}
        
    def get_user_lock(self, user_id: int) -> asyncio.Lock:
        if user_id not in self._user_locks:
            self._user_locks[user_id] = asyncio.Lock()
        return self._user_locks[user_id]

    @property
    def approval_channel(self) -> Optional[discord.TextChannel]:
        if self.approval_channel_id: return self.bot.get_channel(self.approval_channel_id)
        return None

    @property
    def private_age_log_channel(self) -> Optional[discord.TextChannel]:
        if self.private_age_log_channel_id: return self.bot.get_channel(self.private_age_log_channel_id)
        return None

    async def register_persistent_views(self):
        self.view_instance = OnboardingPanelView(self)
        await self.view_instance.setup_buttons()
        self.bot.add_view(self.view_instance)

    async def cog_load(self): 
        await self.load_configs()

    async def load_configs(self):
        self.panel_channel_id = get_id("onboarding_panel_channel_id")
        self.approval_channel_id = get_id("onboarding_approval_channel_id")
        self.introduction_channel_id = get_id("introduction_channel_id")
        self.rejection_log_channel_id = get_id("introduction_rejection_log_channel_id")
        self.approval_role_id = get_id("role_approval")
        self.main_chat_channel_id = get_id("main_chat_channel_id")
        self.private_age_log_channel_id = get_id("onboarding_private_age_log_channel_id")
        self.master_role_id = get_id("role_staff_village_chief")
        self.vice_master_role_id = get_id("role_staff_deputy_chief")
        logger.info("[Onboarding Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")
    
    async def regenerate_panel(self, channel: discord.TextChannel, panel_key: str = "panel_onboarding") -> bool:
        base_panel_key = panel_key.replace("panel_", "")
        embed_key = panel_key

        try:
            panel_info = get_panel_id(base_panel_key)
            if panel_info and (old_id := panel_info.get('message_id')):
                try: 
                    old_message = await channel.fetch_message(old_id)
                    await old_message.delete()
                except (discord.NotFound, discord.HTTPException): pass

            embed_data = await get_embed_from_db(embed_key)
            if not embed_data:
                logger.warning(f"DB에서 '{embed_key}' 임베드 데이터를 찾을 수 없어, 패널 생성을 건너뜁니다.")
                return False
                
            embed = discord.Embed.from_dict(embed_data)
            if self.view_instance is None:
                await self.register_persistent_views()
            
            await self.view_instance.setup_buttons()
            new_message = await channel.send(embed=embed, view=self.view_instance)
            await save_panel_id(base_panel_key, new_message.id, channel.id)
            logger.info(f"✅ {panel_key} 패널을 성공적으로 새로 생성했습니다. (채널: #{channel.name})")
            return True
        except Exception as e:
            logger.error(f"❌ {panel_key} 패널 재설치 중 오류 발생: {e}", exc_info=True)
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(Onboarding(bot))

async def setup(bot: commands.Bot):
    await bot.add_cog(Onboarding(bot))
