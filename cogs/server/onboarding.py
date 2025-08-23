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
from utils.helpers import format_embed_from_db

logger = logging.getLogger(__name__)

# --- UI 클래스 (RejectionReasonModal, IntroductionModal) ---
class RejectionReasonModal(ui.Modal, title="拒否理由入力"):
    reason = ui.TextInput(label="拒否理由", placeholder="拒否する理由を具体的に入力してください。", style=discord.TextStyle.paragraph, required=True, max_length=200)
    async def on_submit(self, interaction: discord.Interaction): await interaction.response.defer()

class IntroductionModal(ui.Modal, title="住人登録票"):
    name = ui.TextInput(label="名前", placeholder="里で使用する名前を記入してください", required=True, max_length=12)
    # [✅ 수정] '나이' 필드를 '출생 연도'로 변경하고 더 명확한 placeholder 제공
    birth_year = ui.TextInput(label="生まれた年 (西暦)", placeholder="例: 1995 (4桁の数字で入力してください)", required=True, min_length=4, max_length=4)
    gender = ui.TextInput(label="性別", placeholder="例：男、女性", required=True, max_length=10)
    hobby = ui.TextInput(label="趣味・好きなこと", placeholder="趣味や好きなことを自由に記入してください", style=discord.TextStyle.paragraph, required=True, max_length=500)
    path = ui.TextInput(label="参加経路", placeholder="例：Disboard、〇〇からの招待など", style=discord.TextStyle.paragraph, required=True, max_length=200)
    
    def __init__(self, cog_instance: 'Onboarding'): super().__init__(); self.onboarding_cog = cog_instance
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            # [✅ 추가] 출생 연도 유효성 검사
            try:
                year = int(self.birth_year.value)
                # 서버 정책에 맞는 연도 범위 설정 (예: 1940년 ~ 2010년)
                # 이 값은 필요에 따라 조정할 수 있습니다.
                if not (1940 <= year <= 2010):
                    await interaction.followup.send("❌ 生まれた年は1940年から2010年の間で入力してください。", ephemeral=True)
                    return
            except ValueError:
                await interaction.followup.send("❌ 生まれた年は4桁の数字で入力してください。", ephemeral=True)
                return

            approval_channel = self.onboarding_cog.approval_channel
            if not approval_channel: await interaction.followup.send("❌ エラー: 承認チャンネルが見つかりません。", ephemeral=True); return
            embed_data = await get_embed_from_db("embed_onboarding_approval")
            if not embed_data: await interaction.followup.send("❌ エラー: 承認用メッセージのテンプレートが見つかりません。", ephemeral=True); return
            
            embed = format_embed_from_db(embed_data, member_mention=interaction.user.mention, member_name=interaction.user.display_name)
            if interaction.user.display_avatar: embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            embed.add_field(name="名前", value=self.name.value, inline=False)
            # [✅ 수정] '나이' 대신 '출생 연도'를 임베드에 추가
            embed.add_field(name="生まれた年", value=self.birth_year.value, inline=False)
            embed.add_field(name="性別", value=self.gender.value, inline=False)
            embed.add_field(name="趣味・好きなこと", value=self.hobby.value, inline=False)
            embed.add_field(name="参加経路", value=self.path.value, inline=False)
            
            view = ApprovalView(author=interaction.user, original_embed=embed, cog_instance=self.onboarding_cog)
            approval_role_id = self.onboarding_cog.approval_role_id
            content = f"<@&{approval_role_id}> 新しい住人登録票が提出されました。" if approval_role_id else "新しい住人登録票が提出されました。"
            await approval_channel.send(content=content, embed=embed, view=view, allowed_mentions=discord.AllowedMentions(roles=True))
            await interaction.followup.send("✅ 住人登録票を公務員に提出しました。", ephemeral=True)
        except Exception as e: 
            logger.error(f"자기소개서 제출 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 予期せぬエラーが発生しました。", ephemeral=True)

class ApprovalView(ui.View):
    def __init__(self, author: discord.Member, original_embed: discord.Embed, cog_instance: 'Onboarding'):
        super().__init__(timeout=None)
        self.author_id = author.id
        self.original_embed = copy.deepcopy(original_embed)
        self.onboarding_cog = cog_instance
        self.user_process_lock = self.onboarding_cog.get_user_lock(self.author_id)
    
    async def _check_permission(self, interaction: discord.Interaction) -> bool:
        approval_role_id = self.onboarding_cog.approval_role_id
        if not approval_role_id or not isinstance(interaction.user, discord.Member) or not any(role.id == approval_role_id for role in interaction.user.roles):
            await interaction.response.send_message("❌ このボタンを押す権限がありません。", ephemeral=True)
            return False
        return True
    
    def _get_field_value(self, embed: discord.Embed, field_name: str) -> Optional[str]:
        return next((f.value for f in embed.fields if f.name == field_name), None)
    
    # [✅ 삭제] 더 이상 복잡한 파싱 함수가 필요 없으므로 _parse_birth_year 함수를 제거합니다.
        
    async def _handle_approval_flow(self, interaction: discord.Interaction, is_approved: bool):
        if not await self._check_permission(interaction): return
        if self.user_process_lock.locked():
            await interaction.response.send_message("⏳ 他の管理者がこの申請を処理中です。少し待ってからお試しください。", ephemeral=True)
            return
        
        async with self.user_process_lock:
            member = interaction.guild.get_member(self.author_id)
            if not member:
                try:
                    await interaction.message.delete()
                    await interaction.response.send_message("❌ 対象メンバーが見つかりません。サーバーから退出したようです。", ephemeral=True)
                except (discord.NotFound, discord.HTTPException): pass
                return
            
            rejection_reason = None
            if not is_approved:
                rejection_modal = RejectionReasonModal()
                await interaction.response.send_modal(rejection_modal)
                if await rejection_modal.wait() or not rejection_modal.reason.value: return
                rejection_reason = rejection_modal.reason.value
            else:
                await interaction.response.defer()

            for item in self.children: item.disabled = True
            try: await interaction.message.edit(content=f"⏳ {interaction.user.mention}さんが処理中...", view=self)
            except (discord.NotFound, discord.HTTPException): pass

            if is_approved:
                success, results = await self._process_approval(member)
            else:
                success, results = await self._process_rejection(interaction.user, member, rejection_reason)

            status_text = "承認" if is_approved else "拒否"
            if success:
                if interaction.response.is_done():
                    await interaction.followup.send(f"✅ **{status_text}**処理が完了しました。", ephemeral=True)
                else:
                    await interaction.edit_original_response(content=f"✅ **{status_text}**処理が完了しました。", view=None)
            else:
                error_report = f"❌ **{status_text}**処理中にエラーが発生しました:\n" + "\n".join(f"- {res}" for res in results)
                if interaction.response.is_done():
                    await interaction.followup.send(error_report, ephemeral=True)
                else:
                    await interaction.edit_original_response(content=error_report, view=None)

            try: await interaction.message.delete()
            except (discord.NotFound, discord.HTTPException): pass
        
        if self.author_id in self.onboarding_cog._user_locks:
            del self.onboarding_cog._user_locks[self.author_id]

    async def _process_approval(self, member: discord.Member) -> (bool, List[str]):
        role_grant_error = await self._grant_roles(member)
        
        if role_grant_error:
            logger.error(f"자기소개 승인 실패: 역할 부여 중 오류 발생 - {role_grant_error}")
            return False, [role_grant_error]
        
        remaining_tasks = [
            self._update_nickname(member),
            self._send_public_welcome(member),
            self._send_main_chat_welcome(member),
            self._send_dm_notification(member, is_approved=True)
        ]
        results = await asyncio.gather(*remaining_tasks, return_exceptions=True)
        
        failed_tasks_messages = [res for res in results if isinstance(res, str)]
        
        if failed_tasks_messages:
            logger.warning(f"자기소개 승인 후 부가 작업 실패: {failed_tasks_messages}")

        return True, failed_tasks_messages

    async def _process_rejection(self, moderator: discord.Member, member: discord.Member, reason: str) -> (bool, List[str]):
        tasks = [ self._send_rejection_log(moderator, member, reason), self._send_dm_notification(member, is_approved=False, reason=reason) ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        failed_tasks_messages = [res for res in results if isinstance(res, str)]
        return not failed_tasks_messages, failed_tasks_messages

    async def _grant_roles(self, member: discord.Member) -> Optional[str]:
        try:
            guild = member.guild; roles_to_add: List[discord.Role] = []; failed_to_find_roles: List[str] = []
            
            role_keys_to_grant = ["role_resident", "role_resident_rookie", "role_warning_separator"]
            for key in role_keys_to_grant:
                if (rid := get_id(key)) and (r := guild.get_role(rid)):
                    roles_to_add.append(r)
                else: failed_to_find_roles.append(key)

            # [✅ 수정] 성별 역할 부여 로직 (기존과 동일하지만 명시)
            gender_role_mapping = get_config("GENDER_ROLE_MAPPING", [])
            if gender_field := self._get_field_value(self.original_embed, "性別"):
                for rule in gender_role_mapping:
                    if any(k.lower() in gender_field.lower() for k in rule.get("keywords", [])):
                        if (rid := get_id(rule["role_id_key"])) and (r := guild.get_role(rid)): roles_to_add.append(r)
                        else: failed_to_find_roles.append(rule["role_id_key"])
                        break
            
            # [✅✅✅ 핵심 수정: 나이 역할 부여 로직]
            age_role_mapping = get_config("AGE_ROLE_MAPPING", [])
            birth_year_str = self._get_field_value(self.original_embed, "生まれた年")

            if birth_year_str and birth_year_str.isdigit():
                birth_year = int(birth_year_str)
                
                # 서버의 나이 제한 정책 확인 (예: 20세 이상)
                # 이 부분은 서버 정책에 맞게 조정이 필요합니다.
                age_limit = 20
                current_year = datetime.now(timezone.utc).year
                if (current_year - birth_year) < age_limit:
                    # [중요] 나이 제한에 걸리는 경우, 승인 프로세스를 중단하고 에러 메시지 반환
                    return f"年齢制限: ユーザーは{age_limit}歳未満です。 (生まれた年: {birth_year})"

                for mapping in age_role_mapping:
                    if mapping["range"][0] <= birth_year < mapping["range"][1]:
                        if (rid := get_id(mapping["key"])) and (r := guild.get_role(rid)):
                            roles_to_add.append(r)
                        else:
                            failed_to_find_roles.append(mapping["key"])
                        break
            
            if roles_to_add: await member.add_roles(*list(set(roles_to_add)), reason="自己紹介の承認")
            if (rid := get_id("role_guest")) and (r := guild.get_role(rid)) and r in member.roles: await member.remove_roles(r, reason="自己紹介の承認完了")
            
            if failed_to_find_roles: 
                return f"役割が見つかりません: `{', '.join(failed_to_find_roles)}`. `/setup`コマンドで役割を同期してください。"
        except discord.Forbidden: 
            return "ボットの権限不足: 役割を付与/削除する権限がありません。"
        except Exception as e:
            logger.error(f"역할 부여 중 오류: {e}", exc_info=True)
            return "役割の付与中に不明なエラーが発生しました。"
        return None
        
    async def _update_nickname(self, member: discord.Member) -> Optional[str]:
        try:
            if (nick_cog := self.onboarding_cog.bot.get_cog("Nicknames")) and (name_field := self._get_field_value(self.original_embed, "名前")):
                await nick_cog.update_nickname(member, base_name_override=name_field)
        except discord.Forbidden: return "봇 권한 부족: 봇이 닉네임을 변경할 권한보다 낮은 위치에 있습니다。"
        except Exception as e:
            logger.error(f"닉네임 업데이트 중 오류: {e}", exc_info=True); return f"닉네임 업데이트 중 알 수 없는 오류 발생。"
        return None
    
    async def _send_public_welcome(self, member: discord.Member) -> Optional[str]:
        try:
            ch_id = self.onboarding_cog.introduction_channel_id
            if ch_id and (ch := member.guild.get_channel(ch_id)):
                embed = discord.Embed(title="📝 自己紹介", color=discord.Color.green())
                embed.add_field(name="住民", value=member.mention, inline=False)
                for field in self.original_embed.fields: embed.add_field(name=field.name, value=field.value, inline=False)
                if member.display_avatar: embed.set_thumbnail(url=member.display_avatar.url)
                await ch.send(content=f"||{member.mention}||", embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
        except Exception as e:
            logger.error(f"공개 환영 메시지 전송 실패: {e}", exc_info=True); return "자기소개 채널에 메시지 전송 실패。"
        return None
    
    async def _send_main_chat_welcome(self, member: discord.Member) -> Optional[str]:
        try:
            ch_id = self.onboarding_cog.main_chat_channel_id
            if ch_id and (ch := member.guild.get_channel(ch_id)):
                embed_data = await get_embed_from_db("embed_main_chat_welcome")
                if not embed_data: return "메인 채팅 환영 임베드를 찾을 수 없음。"
                embed = format_embed_from_db(embed_data, member_mention=member.mention)
                await ch.send(content=member.mention, embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
        except Exception as e:
            logger.error(f"메인 채팅 환영 메시지 전송 실패: {e}", exc_info=True); return "메인 채팅 채널에 메시지 전송 실패。"
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
                embed.add_field(name="理由 (理由)", value=reason, inline=False)
                panel_channel_id = self.onboarding_cog.panel_channel_id
                if panel_channel_id:
                    embed.add_field(name="再申請 (再申請)", value=f"<#{panel_channel_id}> からやり直してください。", inline=False)
            await member.send(embed=embed)
        except discord.Forbidden: logger.warning(f"{member.display_name}님에게 DM을 보낼 수 없습니다 (DM 차단됨)。")
        except Exception as e: logger.error(f"DM 알림 전송 실패: {e}", exc_info=True)
        return None
        
    async def _send_rejection_log(self, moderator: discord.Member, member: discord.Member, reason: str) -> Optional[str]:
        try:
            ch_id = self.onboarding_cog.rejection_log_channel_id
            if ch_id and (ch := member.guild.get_channel(ch_id)):
                embed = discord.Embed(title="❌ 住人登録が拒否されました", color=discord.Color.red())
                embed.add_field(name="旅の人", value=member.mention, inline=False)
                for field in self.original_embed.fields: embed.add_field(name=field.name, value=field.value, inline=False)
                embed.add_field(name="拒否理由", value=reason, inline=False); embed.add_field(name="担当者", value=moderator.mention, inline=False)
                if member.display_avatar: embed.set_thumbnail(url=member.display_avatar.url)
                await ch.send(content=f"||{member.mention}||", embed=embed, allowed_mentions=discord.AllowedMentions.none())
        except Exception as e:
            logger.error(f"거부 로그 전송 실패: {e}", exc_info=True); return "거부 로그 채널에 메시지 전송 실패。"
        return None
        
    @ui.button(label="承認", style=discord.ButtonStyle.success, custom_id="onboarding_approve")
    async def approve(self, i: discord.Interaction, b: ui.Button): await self._handle_approval_flow(i, is_approved=True)
    @ui.button(label="拒否", style=discord.ButtonStyle.danger, custom_id="onboarding_reject")
    async def reject(self, i: discord.Interaction, b: ui.Button): await self._handle_approval_flow(i, is_approved=False)

# ... 이하 OnboardingGuideView, OnboardingPanelView, Onboarding Cog 클래스는 기존과 동일하게 유지됩니다. ...
# (생략 없이 전체 코드를 요청하셨으므로, 아래에 동일한 코드를 그대로 붙여넣습니다.)

class OnboardingGuideView(ui.View):
    def __init__(self, cog_instance: 'Onboarding', steps_data: List[Dict[str, Any]], user: discord.User):
        super().__init__(timeout=300); self.onboarding_cog = cog_instance; self.steps_data = steps_data
        self.user = user; self.current_step = 0; self.message: Optional[discord.WebhookMessage] = None
    async def on_timeout(self) -> None:
        if self.message:
            for item in self.children: item.disabled = True
            try: await self.message.edit(content="案内の時間が経過しました。最初からやり直してください。", view=self)
            except (discord.NotFound, discord.HTTPException): pass
    def stop(self):
        super().stop()
    def _update_components(self):
        self.clear_items(); step_info = self.steps_data[self.current_step]
        is_first = self.current_step == 0; is_last = self.current_step == len(self.steps_data) - 1
        prev_button = ui.Button(label="◀ 戻る", style=discord.ButtonStyle.secondary, custom_id="onboarding_prev", row=1, disabled=is_first)
        prev_button.callback = self.go_previous; self.add_item(prev_button)
        step_type = step_info.get("step_type")
        if step_type == "intro":
             intro_button = ui.Button(label=step_info.get("button_label", "住民登録票を作成する"), style=discord.ButtonStyle.success, custom_id="onboarding_intro")
             intro_button.callback = self.create_introduction; self.add_item(intro_button)
        else:
            next_button = ui.Button(label="次へ ▶", style=discord.ButtonStyle.primary, custom_id="onboarding_next", disabled=is_last)
            next_button.callback = self.go_next; self.add_item(next_button)
    async def _grant_step_role(self, interaction: discord.Interaction, role_key_to_add: str):
        role_id = get_id(role_key_to_add)
        if role_id and isinstance(interaction.user, discord.Member):
            if role := interaction.guild.get_role(role_id):
                try:
                    if role not in interaction.user.roles: await interaction.user.add_roles(role, reason="オンボーディング進行")
                except Exception as e: logger.error(f"온보딩 가이드 중 역할 부여 실패: {e}")
            else: logger.warning(f"온보딩: DB에 설정된 역할 ID({role_id})를 서버에서 찾을 수 없습니다。 ({role_key_to_add})")
    def _prepare_next_step_message_content(self) -> dict:
        step_info = self.steps_data[self.current_step]
        embed_data = step_info.get("embed_data", {}).get("embed_data")
        if not embed_data: embed = discord.Embed(title="エラー", description="このステップの表示データが見つかりません。", color=discord.Color.red())
        else: embed = format_embed_from_db(embed_data, member_mention=self.user.mention)
        self._update_components()
        return {"embed": embed, "view": self}
    async def go_next(self, interaction: discord.Interaction):
        await interaction.response.defer()
        tasks = []
        step_info = self.steps_data[self.current_step]
        role_key_to_add = step_info.get("role_key_to_add")
        if role_key_to_add: tasks.append(self._grant_step_role(interaction, role_key_to_add))
        if self.current_step < len(self.steps_data) - 1: self.current_step += 1
        content = self._prepare_next_step_message_content()
        tasks.append(self.message.edit(**content))
        await asyncio.gather(*tasks)
    async def go_previous(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.current_step > 0: self.current_step -= 1
        content = self._prepare_next_step_message_content()
        if self.message: await self.message.edit(**content)
    async def create_introduction(self, interaction: discord.Interaction):
        await interaction.response.send_modal(IntroductionModal(self.onboarding_cog))
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
            default_button = ui.Button(label="案内を読む", style=discord.ButtonStyle.success, custom_id="start_onboarding_guide")
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
            logger.warning("ONBOARDING_COOLDOWN_SECONDS 설정값이 숫자가 아니므로 기본값(300)을 사용합니다。")
        utc_now = datetime.now(timezone.utc).timestamp()
        last_time = await get_cooldown(user_id_str, cooldown_key)
        if last_time > 0 and (utc_now - last_time) < cooldown_seconds:
            remaining_time = cooldown_seconds - (utc_now - last_time)
            minutes = int(remaining_time // 60)
            seconds = int(remaining_time % 60)
            await interaction.response.send_message(f"次の案内まであと{minutes}分{seconds}秒です。少々お待ちください。", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        await set_cooldown(user_id_str, cooldown_key)
        try:
            steps = await get_onboarding_steps()
            if not steps: 
                await interaction.followup.send("現在、案内を準備中です。しばらくお待ちください。", ephemeral=True)
                return
            guide_view = OnboardingGuideView(self.onboarding_cog, steps, interaction.user)
            content = guide_view._prepare_next_step_message_content()
            message = await interaction.followup.send(**content, ephemeral=True, wait=True)
            guide_view.message = message
            await guide_view.wait()
        except Exception as e:
            logger.error(f"안내 가이드 시작 중 오류: {e}", exc_info=True)
            if not interaction.is_done():
                try: await interaction.followup.send("エラーが発生しました。もう一度お試しください。", ephemeral=True)
                except discord.NotFound: logger.warning("안내 가이드 시작 오류 메시지 전송 실패: Interaction not found。")

class Onboarding(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_channel_id: Optional[int] = None
        self.approval_channel_id: Optional[int] = None
        self.introduction_channel_id: Optional[int] = None
        self.rejection_log_channel_id: Optional[int] = None
        self.approval_role_id: Optional[int] = None
        self.main_chat_channel_id: Optional[int] = None
        self.view_instance = None
        logger.info("Onboarding Cog가 성공적으로 초기화되었습니다。")
        self._user_locks: Dict[int, asyncio.Lock] = {}
        
    def get_user_lock(self, user_id: int) -> asyncio.Lock:
        if user_id not in self._user_locks:
            self._user_locks[user_id] = asyncio.Lock()
        return self._user_locks[user_id]

    @property
    def approval_channel(self) -> Optional[discord.TextChannel]:
        if self.approval_channel_id: return self.bot.get_channel(self.approval_channel_id)
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
    
    async def regenerate_panel(self, channel: discord.TextChannel) -> bool:
        panel_key = "onboarding"
        embed_key = "panel_onboarding"

        try:
            panel_info = get_panel_id(panel_key)
            if panel_info and (old_id := panel_info.get('message_id')):
                try: 
                    old_message = await channel.fetch_message(old_id)
                    await old_message.delete()
                except (discord.NotFound, discord.HTTPException): pass

            embed_data = await get_embed_from_db(embed_key)
            if not embed_data:
                logger.warning(f"DB에서 '{embed_key}' 임베드 데이터를 찾을 수 없어, 패널 생성을 건너뜁니다。")
                return False
                
            embed = discord.Embed.from_dict(embed_data)
            if self.view_instance is None:
                await self.register_persistent_views()
            
            await self.view_instance.setup_buttons()
            new_message = await channel.send(embed=embed, view=self.view_instance)
            await save_panel_id(panel_key, new_message.id, channel.id)
            logger.info(f"✅ {panel_key} 패널을 성공적으로 새로 생성했습니다。 (채널: #{channel.name})")
            return True
        except Exception as e:
            logger.error(f"❌ {panel_key} 패널 재설치 중 오류 발생: {e}", exc_info=True)
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(Onboarding(bot))
