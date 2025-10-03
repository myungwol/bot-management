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

class RejectionReasonModal(ui.Modal, title="拒否事由入力"):
    reason = ui.TextInput(label="拒否事由", placeholder="拒否する理由を具体的に入力してください。", style=discord.TextStyle.paragraph, required=True, max_length=200)
    async def on_submit(self, interaction: discord.Interaction): await interaction.response.defer()

class IntroductionModal(ui.Modal, title="住民登録証"):
    name = ui.TextInput(label="名前", placeholder="村で使用する名前を記入してください", required=True, max_length=12)
    hobby = ui.TextInput(label="趣味/好きなこと", placeholder="趣味や好きなことを自由にお書きください", style=discord.TextStyle.paragraph, required=True, max_length=500)
    path = ui.TextInput(label="参加経緯", placeholder="例: Disboard, ○○からの招待など", style=discord.TextStyle.paragraph, required=True, max_length=200)
    
    def __init__(self, cog_instance: 'Onboarding', gender: str, birth_year: str):
        super().__init__()
        self.onboarding_cog = cog_instance
        self.gender = gender
        self.public_birth_year_display = birth_year
        
        self.private_birth_year_input: Optional[ui.TextInput] = None
        if self.public_birth_year_display == "非公開":
            self.private_birth_year_input = ui.TextInput(
                label="出生年（村長/副村長確認用）",
                placeholder="YYYY形式で入力してください。非公開として扱われます。",
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
                        await interaction.followup.send("❌ 無効な出生年です。満16歳以上の方のみ参加できます。", ephemeral=True)
                        return
                    actual_birth_year_for_validation = str(year)
                except ValueError:
                    await interaction.followup.send("❌ 出生年は数字で入力してください（例: 2001）。", ephemeral=True)
                    return
                
                private_log_channel = self.onboarding_cog.private_age_log_channel
                if private_log_channel:
                    log_embed = discord.Embed(
                        title="📝 非公開年齢提出記録",
                        description=f"{interaction.user.mention}さんが非公開オプションを選択し、実際の出生年を提出しました。",
                        color=discord.Color.blurple()
                    )
                    log_embed.add_field(name="提出者", value=f"{interaction.user.mention} (`{interaction.user.id}`)")
                    log_embed.add_field(name="提出された年", value=f"`{actual_birth_year_for_validation}`年")
                    log_embed.set_footer(text="この情報は年齢制限の確認目的でのみ使用されます。")
                    await private_log_channel.send(embed=log_embed)
                
                birth_year_for_approval_channel = "非公開"

            approval_channel = self.onboarding_cog.approval_channel
            if not approval_channel: await interaction.followup.send("❌ エラー: 承認チャンネルが見つかりません。", ephemeral=True); return
            embed_data = await get_embed_from_db("embed_onboarding_approval")
            if not embed_data: await interaction.followup.send("❌ エラー: 承認用メッセージテンプレートが見つかりません。", ephemeral=True); return
            
            embed = format_embed_from_db(embed_data, member_mention=interaction.user.mention, member_name=interaction.user.display_name)
            if interaction.user.display_avatar: embed.set_thumbnail(url=interaction.user.display_avatar.url)
            
            embed.add_field(name="名前", value=self.name.value, inline=False)
            embed.add_field(name="出生年", value=birth_year_for_approval_channel, inline=False)
            embed.add_field(name="性別", value=self.gender, inline=False)
            embed.add_field(name="趣味/好きなこと", value=self.hobby.value, inline=False)
            embed.add_field(name="参加経緯", value=self.path.value, inline=False)
            
            view = ApprovalView(
                author=interaction.user, 
                original_embed=embed, 
                cog_instance=self.onboarding_cog,
                actual_birth_year=actual_birth_year_for_validation
            )
            approval_role_id = self.onboarding_cog.approval_role_id
            content = f"<@&{approval_role_id}> 新しい住民登録申請書が提出されました。" if approval_role_id else "新しい住民登録申請書が提出されました。"
            await approval_channel.send(content=content, embed=embed, view=view, allowed_mentions=discord.AllowedMentions(roles=True))
            await interaction.followup.send("✅ 住民登録証を担当者に提出しました。", ephemeral=True)
        except Exception as e: 
            logger.error(f"자기소개서 제출 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 予期せぬエラーが発生しました。", ephemeral=True)

class GenderAgeSelectView(ui.View):
    def __init__(self, cog: 'Onboarding'):
        super().__init__(timeout=300)
        self.cog = cog
        self.selected_gender: Optional[str] = None
        self.selected_birth_year: Optional[str] = None
        
        self.choices_config = get_config("ONBOARDING_CHOICES", {})
        
        gender_options = [discord.SelectOption(**opt) for opt in self.choices_config.get("gender", [])]
        self.gender_select = ui.Select(
            placeholder="性別を選択してください...",
            options=gender_options or [discord.SelectOption(label="エラー", value="error")],
            disabled=not gender_options,
            custom_id="onboarding_gender_select"
        )
        self.gender_select.callback = self.on_gender_select
        self.add_item(self.gender_select)
        
        decade_options = [
            discord.SelectOption(label="非公開", value="private"),
            discord.SelectOption(label="2000年代", value="2000s"),
            discord.SelectOption(label="1990年代", value="1990s"),
            discord.SelectOption(label="1980年代", value="1980s"),
            discord.SelectOption(label="1970年代", value="1970s")
        ]
        self.decade_select = ui.Select(placeholder="生まれた年代を選択してください...", options=decade_options, custom_id="onboarding_decade_select")
        self.decade_select.callback = self.on_decade_select
        self.add_item(self.decade_select)

        self.year_select = ui.Select(
            placeholder="まず年代を選択してください...", 
            disabled=True, 
            custom_id="onboarding_year_select",
            options=[discord.SelectOption(label="placeholder", value="placeholder")]
        )
        self.year_select.callback = self.on_year_select
        self.add_item(self.year_select)

        self.proceed_button = ui.Button(label="次へ", style=discord.ButtonStyle.success, disabled=True, custom_id="onboarding_proceed")
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
            self.selected_birth_year = "非公開"
            self.year_select.placeholder = "非公開が選択されました"
            self.year_select.disabled = True
            self.year_select.options = [discord.SelectOption(label="placeholder", value="placeholder")]
            await self._update_view_state(interaction)
            return

        year_options_data = self.choices_config.get("birth_year_groups", {}).get(selected_decade, [])
        year_options = [discord.SelectOption(**opt) for opt in year_options_data]
        
        self.year_select.options = year_options or [discord.SelectOption(label="エラー", value="error")]
        self.year_select.placeholder = f"{selected_decade}代から選択..."
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
    
    @ui.button(label="承認", style=discord.ButtonStyle.success, custom_id="onboarding_approve")
    async def approve(self, i: discord.Interaction, b: ui.Button): await self._handle_approval_flow(i, is_approved=True)
    
    @ui.button(label="拒否", style=discord.ButtonStyle.danger, custom_id="onboarding_reject")
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
            await interaction.response.send_message("⏳ 他の管理者がこの申請を処理中です。しばらくしてからもう一度お試しください。", ephemeral=True)
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
            await interaction.edit_original_response(content=f"⏳ {interaction.user.mention}さんが処理中...", view=self)
            
            member = interaction.guild.get_member(self.author_id)
            if not member:
                await interaction.followup.send("❌ 対象メンバーが見つかりません。サーバーから退出したようです。", ephemeral=True)
                try:
                    await interaction.message.delete()
                except (discord.NotFound, discord.HTTPException):
                    pass
                return

            moderator = interaction.user
            if is_approved:
                success, results = await self._process_approval(moderator, member)
            else:
                success, results = await self._process_rejection(moderator, member, rejection_reason)

            status_text = "承認" if is_approved else "拒否"
            if success:
                message = await interaction.followup.send(f"✅ **{status_text}** 処理が完了しました。", ephemeral=True, wait=True)
                await asyncio.sleep(3)
                await message.delete()
            else:
                error_report = f"❌ **{status_text}** 処理中にエラーが発生しました:\n" + "\n".join(f"- {res}" for res in results)
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
            
            gender_field = self._get_field_value(self.original_embed, "性別")
            if gender_field == "男性":
                if (rid := get_id("role_info_male")) and (r := guild.get_role(rid)): roles_to_add.append(r)
            elif gender_field == "女性":
                if (rid := get_id("role_info_female")) and (r := guild.get_role(rid)): roles_to_add.append(r)

            age_role_mapping = get_config("AGE_ROLE_MAPPING", [])
            
            public_birth_year_display = self._get_field_value(self.original_embed, "出生年")
            
            if public_birth_year_display == "非公開":
                if (rid := get_id("role_info_age_private")) and (r := guild.get_role(rid)):
                    roles_to_add.append(r)
                else:
                    failed_to_find_roles.append("role_info_age_private")
            
            elif self.actual_birth_year.isdigit():
                birth_year = int(self.actual_birth_year)
                age_limit = 16
                current_year = datetime.now(timezone.utc).year
                if (current_year - birth_year) < age_limit:
                    return f"年齢制限: ユーザーが満{age_limit}歳未満です。(出生年: {birth_year})"

                for mapping in age_role_mapping:
                    if mapping["range"][0] <= birth_year < mapping["range"][1]:
                        if (rid := get_id(mapping["key"])) and (r := guild.get_role(rid)):
                            roles_to_add.append(r)
                        else:
                            failed_to_find_roles.append(mapping["key"])
                        break
            
            if roles_to_add: await member.add_roles(*list(set(roles_to_add)), reason="自己紹介承認")
            if (rid := get_id("role_guest")) and (r := guild.get_role(rid)) and r in member.roles: await member.remove_roles(r, reason="自己紹介承認完了")
            
            if failed_to_find_roles: 
                return f"役職が見つかりません: `{', '.join(failed_to_find_roles)}`。`/setup`コマンドで役職を同期してください。"
        except discord.Forbidden: 
            return "ボットの権限不足: 役職を付与/削除する権限がありません。"
        except Exception as e:
            logger.error(f"역할 부여 중 오류: {e}", exc_info=True)
            return "役職付与中に不明なエラーが発生しました。"
        return None
        
    async def _update_nickname(self, member: discord.Member) -> Optional[str]:
        try:
            if (nick_cog := self.onboarding_cog.bot.get_cog("Nicknames")) and (name_field := self._get_field_value(self.original_embed, "名前")):
                await nick_cog.update_nickname(member, base_name_override=name_field)
        except discord.Forbidden: return "ボットの権限不足: ボットの役職がメンバーの役職より低いため、ニックネームを変更できません。"
        except Exception as e:
            logger.error(f"닉네임 업데이트 중 오류: {e}", exc_info=True); return f"ニックネーム更新中に不明なエラーが発生しました。"
        return None
    
    async def _send_public_welcome(self, moderator: discord.Member, member: discord.Member) -> Optional[str]:
        try:
            ch_id = self.onboarding_cog.introduction_channel_id
            if ch_id and (ch := member.guild.get_channel(ch_id)):
                embed = discord.Embed(title="📝 自己紹介", color=discord.Color.green())
                embed.add_field(name="住民", value=member.mention, inline=False)
                
                for field in self.original_embed.fields: 
                    embed.add_field(name=field.name, value=field.value, inline=False)
                
                embed.add_field(name="担当者", value=moderator.mention, inline=False)
                
                if member.display_avatar: 
                    embed.set_thumbnail(url=member.display_avatar.url)
                await ch.send(content=f"||{member.mention}||", embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
        except Exception as e:
            logger.error(f"공개 환영 메시지 전송 실패: {e}", exc_info=True); return "自己紹介チャンネルへのメッセージ送信に失敗しました。"
        return None
    
    async def _send_main_chat_welcome(self, member: discord.Member) -> Optional[str]:
        try:
            ch_id = self.onboarding_cog.main_chat_channel_id
            if ch_id and (ch := member.guild.get_channel(ch_id)):
                embed_data = await get_embed_from_db("embed_main_chat_welcome")
                if not embed_data: return "メインチャット歓迎の埋め込みが見つかりません。"
                
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
            logger.error(f"메인 채팅 환영 메시지 전송 실패: {e}", exc_info=True); return "メインチャットチャンネルへのメッセージ送信に失敗しました。"
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
                embed.add_field(name="事由", value=reason, inline=False)
                panel_channel_id = self.onboarding_cog.panel_channel_id
                if panel_channel_id:
                    embed.add_field(name="再申請", value=f"<#{panel_channel_id}> で再度お試しください。", inline=False)
            await member.send(embed=embed)
        except discord.Forbidden: logger.warning(f"{member.display_name}さんへDMを送信できませんでした（DMがブロックされています）。")
        except Exception as e: logger.error(f"DM 알림 전송 실패: {e}", exc_info=True)
        return None
        
    async def _send_rejection_log(self, moderator: discord.Member, member: discord.Member, reason: str) -> Optional[str]:
        try:
            ch_id = self.onboarding_cog.rejection_log_channel_id
            if ch_id and (ch := member.guild.get_channel(ch_id)):
                embed = discord.Embed(title="❌ 住民登録が拒否されました", color=discord.Color.red())
                embed.add_field(name="旅行者", value=member.mention, inline=False)
                for field in self.original_embed.fields: embed.add_field(name=field.name, value=field.value, inline=False)
                embed.add_field(name="拒否事由", value=reason, inline=False); embed.add_field(name="担当者", value=moderator.mention, inline=False)
                if member.display_avatar: embed.set_thumbnail(url=member.display_avatar.url)
                
                await ch.send(content=f"||{member.mention}||", embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
        except Exception as e:
            logger.error(f"거절 로그 전송 실패: {e}", exc_info=True); return "拒否ログチャンネルへのメッセージ送信に失敗しました。"
        return None

class OnboardingGuideView(ui.View):
    def __init__(self, cog_instance: 'Onboarding', steps_data: List[Dict[str, Any]], user: discord.User):
        super().__init__(timeout=300); self.onboarding_cog = cog_instance; self.steps_data = steps_data
        self.user = user; self.current_step = 0; self.message: Optional[discord.WebhookMessage] = None
    async def on_timeout(self) -> None:
        if self.message:
            for item in self.children: item.disabled = True
            try: await self.message.edit(content="案内の有効期限が切れました。最初からやり直してください。", view=self)
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
             intro_button = ui.Button(label=step_info.get("button_label", "住民登録証を作成する"), style=discord.ButtonStyle.success, custom_id="onboarding_intro")
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
            else: logger.warning(f"온보딩: DB에 설정된 역할 ID({role_id})를 서버에서 찾을 수 없습니다. ({role_key_to_add})")
    
    def _prepare_next_step_message_content(self) -> dict:
        step_info = self.steps_data[self.current_step]
        embed_data = step_info.get("embed_data", {}).get("embed_data")
        if not embed_data: embed = discord.Embed(title="エラー", description="このステップの表示データが見つかりません。", color=discord.Color.red())
        else: embed = format_embed_from_db(embed_data, member_mention=self.user.mention)
        self._update_components()
        return {"embed": embed, "view": self}

    async def go_next(self, interaction: discord.Interaction):
        await interaction.response.defer()
        step_info = self.steps_data[self.current_step]
        role_key_to_add = step_info.get("role_key_to_add")
        if role_key_to_add:
            await self._grant_step_role(interaction, role_key_to_add)
        if self.current_step < len(self.steps_data) - 1:
            self.current_step += 1
        content = self._prepare_next_step_message_content()
        if self.message:
            await self.message.edit(**content)

    async def go_previous(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.current_step > 0: self.current_step -= 1
        content = self._prepare_next_step_message_content()
        if self.message: await self.message.edit(**content)

    async def create_introduction(self, interaction: discord.Interaction):
        view = GenderAgeSelectView(self.onboarding_cog)
        await interaction.response.send_message(
            "まず、あなたの性別と生まれた年を選択してください。",
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
            logger.warning("ONBOARDING_COOLDOWN_SECONDS 설정값이 숫자가 아니므로 기본값(300)을 사용합니다.")
        
        utc_now = datetime.now(timezone.utc).timestamp()
        last_time = await get_cooldown(user_id_str, cooldown_key)
        
        if last_time > 0 and (utc_now - last_time) < cooldown_seconds:
            time_remaining = cooldown_seconds - (utc_now - last_time)
            formatted_time = format_seconds_to_hms(time_remaining)
            message = f"❌ 次の案内は **{formatted_time}** 後に見ることができます。しばらくお待ちください。"
            await interaction.response.send_message(message, ephemeral=True)
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
