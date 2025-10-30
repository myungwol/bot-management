# cogs/server/introduction.py

import discord
from discord.ext import commands
from discord import ui
import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
import copy

from utils.database import (
    get_id, save_panel_id, get_panel_id,
    get_embed_from_db, get_panel_components_from_db, get_config
)
from utils.helpers import format_embed_from_db, has_required_roles

logger = logging.getLogger(__name__)

# --- 기존 Onboarding Cog에서 복사된 자기소개 관련 클래스들 ---

class RejectionReasonModal(ui.Modal, title="拒否事由入力"):
    reason = ui.TextInput(label="拒否事由", placeholder="拒否する理由を具体的に入力してください。", style=discord.TextStyle.paragraph, required=True, max_length=200)
    async def on_submit(self, interaction: discord.Interaction): await interaction.response.defer()

class IntroductionModal(ui.Modal, title="住民登録証"):
    name = ui.TextInput(label="名前", placeholder="村で使用する名前を記入してください", required=True, max_length=12)
    hobby = ui.TextInput(label="趣味/好きなこと", placeholder="趣味や好きなことを自由にお書きください", style=discord.TextStyle.paragraph, required=True, max_length=500)
    path = ui.TextInput(label="参加経緯", placeholder="例: Disboard, ○○からの招待など", style=discord.TextStyle.paragraph, required=True, max_length=200)
    
    def __init__(self, cog_instance: 'Introduction', gender: str, birth_year: str):
        super().__init__()
        self.introduction_cog = cog_instance
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
            name_to_check = self.name.value
            pattern_str = r"^[a-zA-Z0-9\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]+$"
            
            nicknames_cog = self.introduction_cog.bot.get_cog("Nicknames")
            if not nicknames_cog:
                 logger.error("Nicknames Cogを読み込めず、名前の長さ検証をスキップします。")
            else:
                max_length = int(get_config("NICKNAME_MAX_WEIGHTED_LENGTH", 8))
                if not re.match(pattern_str, name_to_check):
                    await interaction.followup.send("❌ エラー: 名前に絵文字、特殊文字、空白は使用できません。", ephemeral=True)
                    return
                
                if (length := nicknames_cog.calculate_weighted_length(name_to_check)) > max_length:
                    await interaction.followup.send(f"❌ エラー: 名前の長さがルールを超過しました。(現在: **{length}/{max_length}**)", ephemeral=True)
                    return

            actual_birth_year_for_validation = self.public_birth_year_display
            birth_year_for_approval_channel = self.public_birth_year_display

            if self.private_birth_year_input:
                private_year_str = self.private_birth_year_input.value
                try:
                    year = int(private_year_str)
                    current_year = datetime.now(timezone.utc).year
                    # [수정] 나이 제한을 18세로 변경하고, 관련 에러 메시지를 수정합니다.
                    if not (1940 <= year <= current_year - 18):
                        await interaction.followup.send("❌ 無効な出生年です。満18歳以上の方のみ参加できます。", ephemeral=True)
                        return
                    actual_birth_year_for_validation = str(year)
                except ValueError:
                    await interaction.followup.send("❌ 出生年は数字で入力してください（例: 2001）。", ephemeral=True)
                    return
                
                private_log_channel = self.introduction_cog.private_age_log_channel
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

            approval_channel = self.introduction_cog.approval_channel
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
                cog_instance=self.introduction_cog,
                actual_birth_year=actual_birth_year_for_validation
            )
            approval_role_id = self.introduction_cog.approval_role_id
            content = f"<@&{approval_role_id}> 新しい住民登録申請書が提出されました。" if approval_role_id else "新しい住民登録申請書が提出されました。"
            await approval_channel.send(content=content, embed=embed, view=view, allowed_mentions=discord.AllowedMentions(roles=True))
            await interaction.followup.send("✅ 住民登録証を担当者に提出しました。", ephemeral=True)
        except Exception as e: 
            logger.error(f"自己紹介提出中にエラー発生: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 予期せぬエラーが発生しました。", ephemeral=True)

class GenderAgeSelectView(ui.View):
    def __init__(self, cog: 'Introduction'):
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
            custom_id="introduction_gender_select"
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
        self.decade_select = ui.Select(placeholder="生まれた年代を選択してください...", options=decade_options, custom_id="introduction_decade_select")
        self.decade_select.callback = self.on_decade_select
        self.add_item(self.decade_select)

        self.year_select = ui.Select(
            placeholder="まず年代を選択してください...", 
            disabled=True, 
            custom_id="introduction_year_select",
            options=[discord.SelectOption(label="placeholder", value="placeholder")]
        )
        self.year_select.callback = self.on_year_select
        self.add_item(self.year_select)

        self.proceed_button = ui.Button(label="次へ", style=discord.ButtonStyle.success, disabled=True, custom_id="introduction_proceed")
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
    def __init__(self, author: discord.Member, original_embed: discord.Embed, cog_instance: 'Introduction', actual_birth_year: str):
        super().__init__(timeout=None)
        self.author_id = author.id
        self.original_embed = copy.deepcopy(original_embed)
        self.introduction_cog = cog_instance
        self.actual_birth_year = actual_birth_year
    
    @ui.button(label="承認", style=discord.ButtonStyle.success, custom_id="introduction_approve")
    async def approve(self, i: discord.Interaction, b: ui.Button): await self._handle_approval_flow(i, is_approved=True)
    
    @ui.button(label="拒否", style=discord.ButtonStyle.danger, custom_id="introduction_reject")
    async def reject(self, i: discord.Interaction, b: ui.Button): await self._handle_approval_flow(i, is_approved=False)
    
    async def _check_permission(self, interaction: discord.Interaction) -> bool:
        required_keys = ["role_approval", "role_staff_village_chief", "role_staff_deputy_chief"]
        return await has_required_roles(interaction, required_keys)
    
    def _get_field_value(self, embed: discord.Embed, field_name: str) -> Optional[str]:
        return next((f.value for f in embed.fields if f.name == field_name), None)
        
    async def _handle_approval_flow(self, interaction: discord.Interaction, is_approved: bool):
        if not await self._check_permission(interaction): return

        lock = self.introduction_cog.get_user_lock(self.author_id)
        if lock.locked():
            await interaction.response.send_message("⏳ 他の管理者がこの申請を処理中です。しばらくしてからもう一度お試しください。", ephemeral=True)
            return
        
        rejection_reason = None
        if not is_approved:
            rejection_modal = RejectionReasonModal()
            await interaction.response.send_modal(rejection_modal)
            timed_out = await rejection_modal.wait()
            if timed_out or not rejection_modal.reason.value: return 
            rejection_reason = rejection_modal.reason.value
        else:
            await interaction.response.defer(ephemeral=True)

        await lock.acquire()
        try:
            for item in self.children: item.disabled = True
            await interaction.edit_original_response(content=f"⏳ {interaction.user.mention}さんが処理中...", view=self)
            
            member = interaction.guild.get_member(self.author_id)
            if not member:
                await interaction.followup.send("❌ 対象メンバーが見つかりません。サーバーから退出したようです。", ephemeral=True)
                try: await interaction.message.delete()
                except (discord.NotFound, discord.HTTPException): pass
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
            logger.error(f"自己紹介承認失敗 (1/4): 役職付与中にエラー - {role_grant_error}")
            errors.append(role_grant_error); return False, errors

        nickname_update_error = await self._update_nickname(member)
        if nickname_update_error:
            logger.warning(f"自己紹介承認中の警告 (2/4): ニックネーム更新失敗 - {nickname_update_error}")
            errors.append(nickname_update_error)

        public_welcome_error = await self._send_public_welcome(moderator, member)
        if public_welcome_error:
            logger.warning(f"自己紹介承認中の警告 (3/4): 公開歓迎メッセージ失敗 - {public_welcome_error}")
            errors.append(public_welcome_error)
            
        main_chat_error = await self._send_main_chat_welcome(member)
        if main_chat_error:
            logger.warning(f"自己紹介承認中の警告 (4/4): メインチャット歓迎失敗 - {main_chat_error}")
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
            guild = member.guild
            roles_to_add: List[discord.Role] = []
            failed_to_find_roles: List[str] = []
            
            # [수정] 기본 역할만 부여하도록 목록을 단순화합니다.
            role_keys_to_grant = [
                "role_resident", 
                "role_resident_rookie", 
                "role_warning_separator",
                "role_shop_separator"
            ]
            for key in role_keys_to_grant:
                if (rid := get_id(key)) and (r := guild.get_role(rid)):
                    roles_to_add.append(r)
                else:
                    failed_to_find_roles.append(key)

            # [수정] 나이 제한 검사를 18세로 상향 조정합니다.
            age_limit = 18
            if self.actual_birth_year.isdigit():
                birth_year = int(self.actual_birth_year)
                current_year = datetime.now(timezone.utc).year
                if (current_year - birth_year) < age_limit:
                    return f"年齢制限: ユーザーが満{age_limit}歳未満です。(出生年: {birth_year})"
            
            # [삭제] 성별 역할 부여 로직을 제거합니다.
            # [삭제] 나이대 역할 부여 로직을 제거합니다.
            
            if roles_to_add:
                await member.add_roles(*list(set(roles_to_add)), reason="自己紹介承認")
            
            if (rid := get_id("role_guest")) and (r := guild.get_role(rid)) and r in member.roles:
                await member.remove_roles(r, reason="自己紹介承認完了")
            
            if failed_to_find_roles: 
                return f"役職が見つかりません: `{', '.join(failed_to_find_roles)}`。`/admin setup`コマンドで役職を同期してください。"
        except discord.Forbidden: 
            return "ボットの権限不足: 役職を付与/削除する権限がありません。"
        except Exception as e:
            logger.error(f"役職付与中にエラー: {e}", exc_info=True)
            return "役職付与中に不明なエラーが発生しました。"
        return None
        
    async def _update_nickname(self, member: discord.Member) -> Optional[str]:
        try:
            if (nick_cog := self.introduction_cog.bot.get_cog("Nicknames")) and (name_field := self._get_field_value(self.original_embed, "名前")):
                await nick_cog.update_nickname(member, base_name_override=name_field)
        except discord.Forbidden: return "ボットの権限不足: ボットの役職がメンバーの役職より低いため、ニックネームを変更できません。"
        except Exception as e:
            logger.error(f"ニックネーム更新中にエラー: {e}", exc_info=True); return f"ニックネーム更新中に不明なエラーが発生しました。"
        return None
    
    async def _send_public_welcome(self, moderator: discord.Member, member: discord.Member) -> Optional[str]:
        try:
            ch_id = self.introduction_cog.introduction_log_channel_id
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
            logger.error(f"公開歓迎メッセージ送信失敗: {e}", exc_info=True); return "自己紹介チャンネルへのメッセージ送信に失敗しました。"
        return None
    
    async def _send_main_chat_welcome(self, member: discord.Member) -> Optional[str]:
        try:
            ch_id = self.introduction_cog.main_chat_channel_id
            if ch_id and (ch := member.guild.get_channel(ch_id)):
                embed_data = await get_embed_from_db("embed_main_chat_welcome")
                if not embed_data: return "メインチャット歓迎の埋め込みが見つかりません。"
                
                staff_role_id = get_id('role_staff_newbie_helper') or 1424609915921502209
                nickname_channel_id = get_id('nickname_panel_channel_id') or 1423523844374925432
                role_channel_id = get_id('auto_role_channel_id') or 1423523908992368710
                inquiry_channel_id = get_id('inquiry_panel_channel_id') or 1423523001499914240
                bot_guide_channel_id = get_id('bot_guide_channel_id') or 1423527917362876457 
                festival_channel_id = get_id('festival_channel_id') or 1423523493231984763

                format_args = {
                    "member_mention": member.mention, "staff_role_mention": f"<@&{staff_role_id}>",
                    "nickname_channel_mention": f"<#{nickname_channel_id}>", "role_channel_mention": f"<#{role_channel_id}>",
                    "inquiry_channel_mention": f"<#{inquiry_channel_id}>", "bot_guide_channel_mention": f"<#{bot_guide_channel_id}>",
                    "festival_channel_mention": f"<#{festival_channel_id}>"
                }
                embed = format_embed_from_db(embed_data, **format_args)
                await ch.send(content=member.mention, embed=embed, allowed_mentions=discord.AllowedMentions(users=True, roles=True))
        except Exception as e:
            logger.error(f"メインチャット歓迎メッセージ送信失敗: {e}", exc_info=True); return "メインチャットチャンネルへのメッセージ送信に失敗しました。"
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
                panel_channel_id = self.introduction_cog.panel_channel_id
                if panel_channel_id:
                    embed.add_field(name="再申請", value=f"<#{panel_channel_id}> で再度お試しください。", inline=False)
            await member.send(embed=embed)
        except discord.Forbidden: logger.warning(f"{member.display_name}さんへDMを送信できませんでした（DMがブロックされています）。")
        except Exception as e: logger.error(f"DM通知送信失敗: {e}", exc_info=True)
        return None
        
    async def _send_rejection_log(self, moderator: discord.Member, member: discord.Member, reason: str) -> Optional[str]:
        try:
            ch_id = self.introduction_cog.rejection_log_channel_id
            if ch_id and (ch := member.guild.get_channel(ch_id)):
                embed = discord.Embed(title="❌ 住民登録が拒否されました", color=discord.Color.red())
                embed.add_field(name="旅行者", value=member.mention, inline=False)
                for field in self.original_embed.fields: embed.add_field(name=field.name, value=field.value, inline=False)
                embed.add_field(name="拒否事由", value=reason, inline=False); embed.add_field(name="担当者", value=moderator.mention, inline=False)
                if member.display_avatar: embed.set_thumbnail(url=member.display_avatar.url)
                
                await ch.send(content=f"||{member.mention}||", embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
        except Exception as e:
            logger.error(f"拒否ログ送信失敗: {e}", exc_info=True); return "拒否ログチャンネルへのメッセージ送信に失敗しました。"
        return None

class IntroductionPanelView(ui.View):
    def __init__(self, cog_instance: 'Introduction'):
        super().__init__(timeout=None)
        self.introduction_cog = cog_instance
    
    async def setup_buttons(self):
        self.clear_items()
        components = await get_panel_components_from_db('introduction')
        if not components:
            logger.warning("住民登録パネルのコンポーネントが見つかりませんでした。")
            return

        button_info = components[0]
        button = ui.Button(
            label=button_info.get('label'),
            style=discord.ButtonStyle.success,
            emoji=button_info.get('emoji'),
            custom_id=button_info.get('component_key')
        )
        button.callback = self.start_introduction_callback
        self.add_item(button)

    async def start_introduction_callback(self, interaction: discord.Interaction):
        view = GenderAgeSelectView(self.introduction_cog)
        await interaction.response.send_message("まず、あなたの性別と生まれた年を選択してください。", view=view, ephemeral=True)

class Introduction(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_channel_id: Optional[int] = None
        self.approval_channel_id: Optional[int] = None
        self.introduction_log_channel_id: Optional[int] = None
        self.rejection_log_channel_id: Optional[int] = None
        self.approval_role_id: Optional[int] = None
        self.main_chat_channel_id: Optional[int] = None
        self.private_age_log_channel_id: Optional[int] = None
        self.view_instance = None
        self._user_locks: Dict[int, asyncio.Lock] = {}
        logger.info("Introduction (住民登録) Cogが正常に初期化されました。")
        
    def get_user_lock(self, user_id: int) -> asyncio.Lock:
        if user_id not in self._user_locks: self._user_locks[user_id] = asyncio.Lock()
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
        self.view_instance = IntroductionPanelView(self)
        await self.view_instance.setup_buttons()
        self.bot.add_view(self.view_instance)

    async def cog_load(self): 
        await self.load_configs()

    async def load_configs(self):
        self.panel_channel_id = get_id("introduction_panel_channel_id")
        self.approval_channel_id = get_id("onboarding_approval_channel_id")
        self.introduction_log_channel_id = get_id("introduction_channel_id")
        self.rejection_log_channel_id = get_id("introduction_rejection_log_channel_id")
        self.approval_role_id = get_id("role_approval")
        self.main_chat_channel_id = get_id("main_chat_channel_id")
        self.private_age_log_channel_id = get_id("onboarding_private_age_log_channel_id")
        logger.info("[Introduction Cog] データベースから設定を正常にロードしました。")
    
    async def regenerate_panel(self, channel: discord.TextChannel, panel_key: str = "panel_introduction") -> bool:
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
                logger.warning(f"DBで '{embed_key}' の埋め込みデータが見つからず、パネル作成をスキップします。")
                return False
                
            embed = discord.Embed.from_dict(embed_data)
            if self.view_instance is None:
                await self.register_persistent_views()
            
            await self.view_instance.setup_buttons()
            new_message = await channel.send(embed=embed, view=self.view_instance)
            await save_panel_id(base_panel_key, new_message.id, channel.id)
            logger.info(f"✅ {panel_key} パネルを正常に再作成しました。(チャンネル: #{channel.name})")
            return True
        except Exception as e:
            logger.error(f"❌ {panel_key} パネルの再インストール中にエラー発生: {e}", exc_info=True)
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(Introduction(bot))
