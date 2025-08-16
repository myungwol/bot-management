# cogs/server/onboarding.py

import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
import logging
import re
from datetime import datetime
import time
from typing import List, Dict, Any, Optional

from utils.database import (
    get_id, save_panel_id, get_panel_id, get_cooldown, set_cooldown, 
    get_embed_from_db, get_onboarding_steps, get_panel_components_from_db, get_config
)
from cogs.server.system import format_embed_from_db

logger = logging.getLogger(__name__)

# --- UI 클래스 ---
class RejectionReasonModal(ui.Modal, title="拒否理由入力"):
    reason = ui.TextInput(label="拒否理由", placeholder="拒否する理由を具体的に入力してください。", style=discord.TextStyle.paragraph, required=True, max_length=200)
    async def on_submit(self, interaction: discord.Interaction): await interaction.response.defer()

class IntroductionModal(ui.Modal, title="住人登録票"):
    name = ui.TextInput(label="名前", placeholder="里で使用する名前を記入してください", required=True, max_length=12)
    age = ui.TextInput(label="年齢", placeholder="例：20代、90年生まれ、30歳、非公開", required=True, max_length=20)
    gender = ui.TextInput(label="性別", placeholder="例：男、女性", required=True, max_length=10)
    hobby = ui.TextInput(label="趣味・好きなこと", placeholder="趣味や好きなことを自由に記入してください", style=discord.TextStyle.paragraph, required=True, max_length=500)
    path = ui.TextInput(label="参加経路", placeholder="例：Disboard、〇〇からの招待など", style=discord.TextStyle.paragraph, required=True, max_length=200)
    def __init__(self, cog_instance: 'Onboarding'): super().__init__(); self.onboarding_cog = cog_instance
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            approval_channel = self.onboarding_cog.approval_channel
            if not approval_channel: await interaction.followup.send("❌ エラー: 承認チャンネルが見つかりません。", ephemeral=True); return
            await set_cooldown(str(interaction.user.id), "introduction", time.time())
            embed_data = await get_embed_from_db("embed_onboarding_approval")
            if not embed_data: await interaction.followup.send("❌ エラー: 承認用メッセージのテンプレートが見つかりません。", ephemeral=True); return
            embed = format_embed_from_db(embed_data, member_mention=interaction.user.mention, member_name=interaction.user.display_name)
            if interaction.user.display_avatar: embed.set_thumbnail(url=interaction.user.display_avatar.url)
            embed.add_field(name="名前", value=self.name.value, inline=False); embed.add_field(name="年齢", value=self.age.value, inline=False)
            embed.add_field(name="性別", value=self.gender.value, inline=False); embed.add_field(name="趣味・好きなこと", value=self.hobby.value, inline=False)
            embed.add_field(name="参加経路", value=self.path.value, inline=False)
            view = ApprovalView(author=interaction.user, original_embed=embed, cog_instance=self.onboarding_cog)
            await approval_channel.send(content=f"<@&{self.onboarding_cog.approval_role_id}> 新しい住人登録票が提出されました。", embed=embed, view=view)
            await interaction.followup.send("✅ 住人登録票を公務員に提出しました。", ephemeral=True)
        except Exception as e: logger.error(f"자기소개서 제출 중 오류 발생: {e}", exc_info=True); await interaction.followup.send(f"❌ 予期せぬエラーが発生しました。", ephemeral=True)

class ApprovalView(ui.View):
    def __init__(self, author: discord.Member, original_embed: discord.Embed, cog_instance: 'Onboarding'):
        super().__init__(timeout=None); self.author_id = author.id; self.original_embed = original_embed
        self.onboarding_cog = cog_instance; self.rejection_reason: Optional[str] = None
    async def _check_permission(self, interaction: discord.Interaction) -> bool:
        approval_role_id = self.onboarding_cog.approval_role_id
        if not approval_role_id or not isinstance(interaction.user, discord.Member) or not any(role.id == approval_role_id for role in interaction.user.roles):
            await interaction.response.send_message("❌ このボタンを押す権限がありません。", ephemeral=True); return False
        return True
    def _get_field_value(self, embed: discord.Embed, field_name: str) -> Optional[str]:
        return next((f.value for f in embed.fields if f.name == field_name), None)
    def _parse_birth_year(self, text: str) -> Optional[int]:
        if not text: return None; text = text.strip().lower()
        if "非公開" in text or "ひこうかい" in text: return 0
        era_patterns = {'heisei': r'(?:h|平成)\s*(\d{1,2})', 'showa': r'(?:s|昭和)\s*(\d{1,2})', 'reiwa': r'(?:r|令和)\s*(\d{1,2})'}
        era_start_years = {"heisei": 1989, "showa": 1926, "reiwa": 2019}
        for era, pattern in era_patterns.items():
            if match := re.search(pattern, text): return era_start_years[era] + int(match.group(1)) - 1
        if dai_match := re.search(r'(\d{1,2})\s*代', text): return datetime.now().year - (int(dai_match.group(1)) + 5)
        if year_match := re.search(r'(\d{2,4})', text):
            if "年" in text or "生まれ" in text:
                year = int(year_match.group(1)); return year + (1900 if year > datetime.now().year % 100 else 2000) if year < 100 else year
        if age_match := re.search(r'(\d+)', text):
            if "歳" in text or "才" in text: return datetime.now().year - int(age_match.group(1))
        return None
    async def _handle_approval_flow(self, interaction: discord.Interaction, is_approved: bool):
        if not await self._check_permission(interaction): return
        member = interaction.guild.get_member(self.author_id)
        if not member:
            try: await interaction.message.delete(); await interaction.response.send_message("❌ 対象メンバーが見つかりません。", ephemeral=True)
            except (discord.NotFound, discord.HTTPException): pass; return
        if not is_approved:
            rejection_modal = RejectionReasonModal(); await interaction.response.send_modal(rejection_modal)
            if await rejection_modal.wait() or rejection_modal.reason is None: return
            self.rejection_reason = rejection_modal.reason.value
        else: await interaction.response.defer()
        for item in self.children: item.disabled = True
        try: await interaction.message.edit(content=f"⏳ {interaction.user.mention}さんが処理中...", view=self)
        except (discord.NotFound, discord.HTTPException): pass
        tasks = [self._send_notifications(interaction.user, member, is_approved)]
        if is_approved: tasks.extend([self._grant_roles(member), self._update_nickname(member), self._send_public_welcome(interaction.user, member)])
        results = await asyncio.gather(*tasks, return_exceptions=True)
        failed_tasks = [res for res in results if isinstance(res, Exception)]
        status_text = "承認" if is_approved else "拒否"
        if failed_tasks:
            error_report = f"❌ **{status_text}**処理中にエラー:\n" + "".join(f"- `{type(e).__name__}: {e}`\n" for e in failed_tasks)
            await interaction.followup.send(error_report, ephemeral=True)
        else: await interaction.followup.send(f"✅ **{status_text}**処理が完了しました。", ephemeral=True)
        try: await interaction.message.delete()
        except (discord.NotFound, discord.HTTPException): pass
    async def _grant_roles(self, member: discord.Member) -> None:
        roles_to_add, guild = [], member.guild
        if (rid := get_id("role_resident")) and (r := guild.get_role(rid)): roles_to_add.append(r)
        gender_role_mapping = get_config("GENDER_ROLE_MAPPING", [])
        if gender_field := self._get_field_value(self.original_embed, "性別"):
            for rule in gender_role_mapping:
                if any(k.lower() in gender_field.lower() for k in rule.get("keywords", [])):
                    if (rid := get_id(rule["role_id_key"])) and (r := guild.get_role(rid)): roles_to_add.append(r); break
        age_role_mapping = get_config("AGE_ROLE_MAPPING", [])
        if age_field := self._get_field_value(self.original_embed, "年齢"):
            birth_year = self._parse_birth_year(age_field)
            if birth_year == 0:
                if (rid := get_id("role_info_age_private")) and (r := guild.get_role(rid)): roles_to_add.append(r)
            elif birth_year:
                for mapping in age_role_mapping:
                    year_range = range(mapping["range"][0], mapping["range"][1])
                    if birth_year in year_range:
                        if (rid := get_id(mapping["key"])) and (r := guild.get_role(rid)): roles_to_add.append(r); break
        if roles_to_add: await member.add_roles(*list(set(roles_to_add)), reason="자기소개서 승인")
        if (rid := get_id("role_guest")) and (r := guild.get_role(rid)) and r in member.roles: await member.remove_roles(r, reason="자기소개서 승인 완료")
    async def _update_nickname(self, member: discord.Member) -> None:
        if (nick_cog := self.onboarding_cog.bot.get_cog("Nicknames")) and (name_field := self._get_field_value(self.original_embed, "名前")):
            await nick_cog.update_nickname(member, base_name_override=name_field)
    async def _send_public_welcome(self, moderator: discord.Member, member: discord.Member) -> None:
        if (ch_id := self.onboarding_cog.introduction_channel_id) and (ch := member.guild.get_channel(ch_id)):
            embed = discord.Embed(title="📝 自己紹介", color=discord.Color.green())
            embed.add_field(name="住民", value=member.mention, inline=False)
            for field in self.original_embed.fields: embed.add_field(name=field.name, value=field.value, inline=False)
            embed.add_field(name="担当者", value=moderator.mention, inline=False)
            if member.display_avatar: embed.set_thumbnail(url=member.display_avatar.url)
            content = f"||{member.mention}||"; await ch.send(content=content, embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
    async def _send_notifications(self, moderator: discord.Member, member: discord.Member, is_approved: bool) -> None:
        guild = member.guild
        if is_approved:
            try: await member.send(f"✅ お知らせ：「{guild.name}」での住人登録が承認されました。")
            except discord.Forbidden: logger.warning(f"{member.display_name}님에게 DM을 보낼 수 없습니다.")
        else:
            try: await member.send(f"❌ お知らせ：「{guild.name}」での住人登録が拒否されました。\n理由: 「{self.rejection_reason}」\n<#{self.onboarding_cog.panel_channel_id}> からやり直してください。")
            except discord.Forbidden: logger.warning(f"{member.display_name}님에게 DM을 보낼 수 없습니다.")
            if (ch_id := self.onboarding_cog.rejection_log_channel_id) and (ch := guild.get_channel(ch_id)):
                embed = discord.Embed(title="❌ 住人登録が拒否されました", color=discord.Color.red())
                embed.add_field(name="旅の人", value=member.mention, inline=False)
                for field in self.original_embed.fields: embed.add_field(name=field.name, value=field.value, inline=False)
                embed.add_field(name="拒否理由", value=self.rejection_reason or "理由未入力", inline=False); embed.add_field(name="担当者", value=moderator.mention, inline=False)
                if member.display_avatar: embed.set_thumbnail(url=member.display_avatar.url)
                content = f"||{member.mention}||"; await ch.send(content=content, embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
    @ui.button(label="承認", style=discord.ButtonStyle.success, custom_id="onboarding_approve")
    async def approve(self, i: discord.Interaction, b: ui.Button): await self._handle_approval_flow(i, is_approved=True)
    @ui.button(label="拒否", style=discord.ButtonStyle.danger, custom_id="onboarding_reject")
    async def reject(self, i: discord.Interaction, b: ui.Button): await self._handle_approval_flow(i, is_approved=False)

class OnboardingGuideView(ui.View):
    def __init__(self, cog_instance: 'Onboarding', steps_data: List[Dict[str, Any]], user: discord.User):
        super().__init__(timeout=300); self.onboarding_cog = cog_instance; self.steps_data = steps_data
        self.user = user; self.current_step = 0; self.message: Optional[discord.WebhookMessage] = None
        self.user_lock = asyncio.Lock()
    def _update_components(self):
        self.clear_items(); step_info = self.steps_data[self.current_step]
        is_first = self.current_step == 0; is_last = self.current_step == len(self.steps_data) - 1
        prev_button = ui.Button(label="◀ 戻る", style=discord.ButtonStyle.secondary, custom_id="onboarding_prev", row=1, disabled=is_first)
        prev_button.callback = self.go_previous; self.add_item(prev_button)
        step_type = step_info.get("step_type")
        if step_type == "intro":
             intro_button = ui.Button(label=step_info.get("button_label", "住民登録票を作成する"), style=discord.ButtonStyle.success, custom_id="onboarding_intro")
             intro_button.callback = self.create_introduction; self.add_item(intro_button)
        elif step_type == "action":
            action_button = ui.Button(label=step_info.get("button_label", "同意する"), style=discord.ButtonStyle.primary, custom_id="onboarding_action", disabled=is_last)
            action_button.callback = self.do_action; self.add_item(action_button)
        else:
            next_button = ui.Button(label="次へ ▶", style=discord.ButtonStyle.primary, custom_id="onboarding_next", disabled=is_last)
            next_button.callback = self.go_next; self.add_item(next_button)
    async def _update_message(self):
        step_info = self.steps_data[self.current_step]; embed_data = step_info.get("embed_data", {}).get("embed_data")
        if not embed_data: embed = discord.Embed(title="エラー", description="このステップの表示データが見つかりません。", color=discord.Color.red())
        else: embed = format_embed_from_db(embed_data, member_mention=self.user.mention)
        self._update_components()
        if self.message: await self.message.edit(embed=embed, view=self)
    
    async def go_next(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.current_step < len(self.steps_data) - 1: self.current_step += 1
        await self._update_message()
    async def go_previous(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.current_step > 0: self.current_step -= 1
        await self._update_message()

    # --- [수정] 역할 부여 순서 변경 ---
    async def do_action(self, interaction: discord.Interaction):
        await interaction.response.defer()
        step_info = self.steps_data[self.current_step]
        role_key_to_add = step_info.get("role_key_to_add")
        
        # 1. 역할 부여를 먼저 실행하고 기다립니다.
        if role_key_to_add:
            role_id = get_id(role_key_to_add)
            if role_id and isinstance(interaction.user, discord.Member) and (role := interaction.guild.get_role(role_id)):
                try:
                    await interaction.user.add_roles(role, reason="オンボーディング進行")
                except Exception as e:
                    # 역할 부여 실패 시 followup으로 알리고 함수를 종료합니다.
                    await interaction.followup.send(f"❌ 役割の付与中にエラー: {e}", ephemeral=True)
                    return
        
        # 2. 역할 부여가 성공적으로 끝나면, 다음 단계로 넘어갑니다.
        if self.current_step < len(self.steps_data) - 1:
            self.current_step += 1
        
        # 3. 마지막으로 화면을 업데이트합니다.
        await self._update_message()

    # --- [수정] 쿨타임 로직 복구 ---
    async def create_introduction(self, interaction: discord.Interaction):
        async with self.user_lock:
            cooldown_seconds = get_config("ONBOARDING_COOLDOWN_SECONDS", 300) # 기본값 5분
            last_time = await get_cooldown(str(interaction.user.id), "introduction")
            
            if last_time and (time.time() - last_time) < cooldown_seconds:
                rem = cooldown_seconds - (time.time() - last_time)
                m, s = divmod(int(rem), 60)
                await interaction.response.send_message(f"次の申請まであと {m}分{s}秒 お待ちください。", ephemeral=True)
                return
            
            # 쿨타임이 아니면 모달을 보냅니다. (이후 로직은 on_submit에서 처리)
            await interaction.response.send_modal(IntroductionModal(self.onboarding_cog))
        
        # 모달이 닫힌 후 View를 정지하고 메시지를 삭제합니다.
        if self.message:
            await self.message.delete()
        self.stop()

class OnboardingPanelView(ui.View):
    def __init__(self, cog_instance: 'Onboarding'):
        super().__init__(timeout=None); self.onboarding_cog = cog_instance
        self.user_locks: Dict[int, asyncio.Lock] = {}
    async def setup_buttons(self):
        button_styles = get_config("DISCORD_BUTTON_STYLES_MAP", {})
        components_data = await get_panel_components_from_db('onboarding')
        if not components_data:
            default_button = ui.Button(label="案内を読む", style=discord.ButtonStyle.success, custom_id="start_onboarding_guide");
            default_button.callback = self.start_guide_callback; self.add_item(default_button); return
        for comp in components_data:
            if comp.get('component_type') == 'button' and comp.get('component_key'):
                style = button_styles.get(comp.get('style','secondary'), discord.ButtonStyle.secondary)
                button = ui.Button(label=comp.get('label'),style=style,emoji=comp.get('emoji'),row=comp.get('row'),custom_id=comp.get('component_key'))
                if comp.get('component_key') == 'start_onboarding_guide': button.callback = self.start_guide_callback
                self.add_item(button)
    async def start_guide_callback(self, interaction: discord.Interaction):
        lock = self.user_locks.setdefault(interaction.user.id, asyncio.Lock())
        if lock.locked(): return await interaction.response.send_message("以前のリクエストを処理中です。", ephemeral=True)
        async with lock:
            await interaction.response.defer(ephemeral=True, thinking=True)
            steps = await get_onboarding_steps()
            if not steps: await interaction.followup.send("現在、案内を準備中です。しばらくお待ちください。", ephemeral=True); return
            guide_view = OnboardingGuideView(self.onboarding_cog, steps, interaction.user); first_step_info = steps[0]
            embed_data = first_step_info.get("embed_data", {}).get("embed_data")
            if not embed_data: embed = discord.Embed(title="エラー", description="表示データが見つかりません。", color=discord.Color.red())
            else: embed = format_embed_from_db(embed_data, member_mention=interaction.user.mention)
            guide_view._update_components()
            message = await interaction.followup.send(embed=embed, view=guide_view, ephemeral=True)
            guide_view.message = message

class Onboarding(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot; self.panel_channel_id: Optional[int] = None; self.approval_channel_id: Optional[int] = None
        self.introduction_channel_id: Optional[int] = None; self.rejection_log_channel_id: Optional[int] = None
        self.approval_role_id: Optional[int] = None; self.view_instance = None; logger.info("Onboarding Cog가 성공적으로 초기화되었습니다.")
    @property
    def approval_channel(self) -> Optional[discord.TextChannel]:
        if self.approval_channel_id: return self.bot.get_channel(self.approval_channel_id)
        return None
    async def register_persistent_views(self):
        self.view_instance = OnboardingPanelView(self); await self.view_instance.setup_buttons(); self.bot.add_view(self.view_instance)
    async def cog_load(self): await self.load_configs()
    async def load_configs(self):
        self.panel_channel_id = get_id("onboarding_panel_channel_id"); self.approval_channel_id = get_id("onboarding_approval_channel_id")
        self.introduction_channel_id = get_id("introduction_channel_id"); self.rejection_log_channel_id = get_id("introduction_rejection_log_channel_id")
        self.approval_role_id = get_id("role_approval")
    async def regenerate_panel(self, channel: Optional[discord.TextChannel] = None):
        target_channel = channel
        if target_channel is None:
            channel_id = get_id("onboarding_panel_channel_id")
            if channel_id: target_channel = self.bot.get_channel(channel_id)
            else: logger.info("ℹ️ 온보딩 패널 채널이 설정되지 않아, 자동 생성을 건너뜁니다."); return
        if not target_channel: logger.warning("❌ Onboarding panel channel could not be found."); return
        panel_info = get_panel_id("onboarding");
        if panel_info and (old_id := panel_info.get('message_id')):
            try: await (await target_channel.fetch_message(old_id)).delete()
            except (discord.NotFound, discord.Forbidden): pass
        embed_data = await get_embed_from_db("panel_onboarding")
        if not embed_data: logger.warning("DB에서 'panel_onboarding' 임베드 데이터를 찾을 수 없어, 패널 생성을 건너뜁니다."); return
        embed = discord.Embed.from_dict(embed_data)
        self.view_instance = OnboardingPanelView(self); await self.view_instance.setup_buttons()
        new_message = await target_channel.send(embed=embed, view=self.view_instance)
        await save_panel_id("onboarding", new_message.id, target_channel.id)
        logger.info(f"✅ 온보딩 패널을 성공적으로 새로 생성했습니다. (채널: #{target_channel.name})")

async def setup(bot: commands.Bot):
    await bot.add_cog(Onboarding(bot))
