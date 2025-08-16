# cogs/server/onboarding.py (임베드 DB 연동, 2차 수정)

import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
import logging
import re
from datetime import datetime
import time
from typing import List, Dict, Any, Optional

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] %(message)s')
logger = logging.getLogger(__name__)

from utils.database import (
    get_id, save_panel_id, get_panel_id, get_auto_role_mappings, 
    get_cooldown, set_cooldown, get_embed_from_db, get_onboarding_steps,
    get_panel_components_from_db
)
from cogs.admin.panel_manager import BUTTON_STYLES_MAP

INTRODUCTION_COOLDOWN_SECONDS = 10 * 60
AGE_ROLE_MAPPING = [{"key": "role_info_age_70s", "range": range(1970, 1980)}, {"key": "role_info_age_80s", "range": range(1980, 1990)}, {"key": "role_info_age_90s", "range": range(1990, 2000)}, {"key": "role_info_age_00s", "range": range(2000, 2010)}]

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
            if not self.onboarding_cog or not self.onboarding_cog.approval_channel_id:
                await interaction.followup.send("❌ エラー: Onboarding機能が設定されていません。", ephemeral=True); return
            approval_channel = interaction.guild.get_channel(self.onboarding_cog.approval_channel_id)
            if not approval_channel:
                await interaction.followup.send("❌ エラー: 承認チャンネルが見つかりません。", ephemeral=True); return
            await set_cooldown(str(interaction.user.id), "introduction", time.time())
            embed = discord.Embed(title="📝 新しい住人登録票が提出されました", description=f"**作成者:** {interaction.user.mention}", color=discord.Color.blue())
            if interaction.user.display_avatar: embed.set_thumbnail(url=interaction.user.display_avatar.url)
            embed.add_field(name="名前", value=self.name.value, inline=False); embed.add_field(name="年齢", value=self.age.value, inline=False)
            embed.add_field(name="性別", value=self.gender.value, inline=False); embed.add_field(name="趣味・好きなこと", value=self.hobby.value, inline=False)
            embed.add_field(name="参加経路", value=self.path.value, inline=False)
            view = ApprovalView(author=interaction.user, original_embed=embed, cog_instance=self.onboarding_cog)
            await approval_channel.send(content=f"<@&{self.onboarding_cog.approval_role_id}> 新しい住人登録票が提出されました。", embed=embed, view=view)
            await interaction.followup.send("✅ 住人登録票を公務員に提出しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"자기소개서 제출 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 予期せぬエラーが発生しました。", ephemeral=True)

class ApprovalView(ui.View):
    def __init__(self, author: discord.Member, original_embed: discord.Embed, cog_instance: 'Onboarding'):
        super().__init__(timeout=None); self.author_id = author.id; self.original_embed = original_embed
        self.onboarding_cog = cog_instance; self.rejection_reason: Optional[str] = None
    async def _check_permission(self, interaction: discord.Interaction) -> bool:
        approval_role_id = self.onboarding_cog.approval_role_id
        if not approval_role_id or not isinstance(interaction.user, discord.Member) or not any(role.id == approval_role_id for role in interaction.user.roles):
            await interaction.response.send_message("❌ このボタンを押す権限がありません。", ephemeral=True); return False
        return True
    def _parse_birth_year(self, text: str) -> Optional[int]:
        text = text.strip().lower()
        if "非公開" in text or "ひこうかい" in text: return 0
        era_patterns = {'heisei': r'(?:h|平成)\s*(\d{1,2})', 'showa': r'(?:s|昭和)\s*(\d{1,2})', 'reiwa': r'(?:r|令和)\s*(\d{1,2})'}
        era_start_years = {"heisei": 1989, "showa": 1926, "reiwa": 2019}
        for era, pattern in era_patterns.items():
            if match := re.search(pattern, text): return era_start_years[era] + int(match.group(1)) - 1
        if dai_match := re.search(r'(\d{1,2})\s*代', text): return datetime.now().year - (int(dai_match.group(1)) + 5)
        if year_match := re.search(r'(\d{2,4})', text):
            if "年" in text or "生まれ" in text:
                year = int(year_match.group(1))
                return year + (1900 if year > datetime.now().year % 100 else 2000) if year < 100 else year
        if age_match := re.search(r'(\d+)', text):
            if "歳" in text or "才" in text: return datetime.now().year - int(age_match.group(1))
        return None
    async def _handle_approval_flow(self, interaction: discord.Interaction, is_approved: bool):
        if not await self._check_permission(interaction): return
        member = interaction.guild.get_member(self.author_id)
        if not member:
            await interaction.response.send_message("❌ エラー: 対象のメンバーがサーバーに見つかりませんでした。", ephemeral=True); return
        status_text = "承認" if is_approved else "拒否"
        if not is_approved:
            rejection_modal = RejectionReasonModal(); await interaction.response.send_modal(rejection_modal)
            if await rejection_modal.wait(): return
            self.rejection_reason = rejection_modal.reason.value
        else: await interaction.response.defer()
        for item in self.children: item.disabled = True
        try: await interaction.message.edit(content=f"⏳ {interaction.user.mention}さんが処理中...", view=self)
        except (discord.NotFound, discord.HTTPException): pass
        tasks = [self._send_notifications(interaction.user, member, is_approved)]
        if is_approved:
            tasks.extend([self._grant_roles(member), self._update_nickname(member), self._send_public_welcome(interaction.user, member)])
        results = await asyncio.gather(*tasks, return_exceptions=True)
        failed_tasks = [res for res in results if isinstance(res, Exception)]
        if failed_tasks:
            error_report = f"❌ **{status_text} 처리 중 일부 작업에 실패했습니다:**\n" + "".join(f"- `{type(e).__name__}: {e}`\n" for e in failed_tasks)
            await interaction.followup.send(error_report, ephemeral=True)
        else: await interaction.followup.send(f"✅ {status_text}処理が正常に完了しました。", ephemeral=True)
        try: await interaction.message.delete()
        except (discord.NotFound, discord.HTTPException): pass
    async def _grant_roles(self, member: discord.Member) -> None:
        roles_to_add, guild = [], member.guild
        if (rid := get_id("role_resident")) and (r := guild.get_role(rid)): roles_to_add.append(r)
        gender_field = next((f.value for f in self.original_embed.fields if f.name == "性別"), "")
        for rule in get_auto_role_mappings():
            if any(k.lower() in gender_field.lower() for k in rule["keywords"]):
                if (rid := get_id(rule["role_id_key"])) and (r := guild.get_role(rid)): roles_to_add.append(r); break
        age_field = next((f.value for f in self.original_embed.fields if f.name == "年齢"), "")
        birth_year = self._parse_birth_year(age_field)
        if birth_year == 0:
            if (rid := get_id("role_info_age_private")) and (r := guild.get_role(rid)): roles_to_add.append(r)
        elif birth_year:
            for mapping in AGE_ROLE_MAPPING:
                if birth_year in mapping["range"]:
                    if (rid := get_id(mapping["key"])) and (r := guild.get_role(rid)): roles_to_add.append(r); break
        if roles_to_add: await member.add_roles(*list(set(roles_to_add)), reason="자기소개서 승인")
        if (rid := get_id("role_guest")) and (r := guild.get_role(rid)) and r in member.roles:
            await member.remove_roles(r, reason="자기소개서 승인 완료")
    async def _update_nickname(self, member: discord.Member) -> None:
        if (nick_cog := self.onboarding_cog.bot.get_cog("Nicknames")) and (name_field := next((f.value for f in self.original_embed.fields if f.name == "名前"), None)):
            await nick_cog.update_nickname(member, base_name_override=name_field)
    async def _send_public_welcome(self, moderator: discord.Member, member: discord.Member) -> None:
        guild = member.guild
        if (ch_id := self.onboarding_cog.introduction_channel_id) and (ch := guild.get_channel(ch_id)):
            embed = self.original_embed.copy()
            embed.title = "ようこそ！新しい仲間です！"
            embed.color = discord.Color.green()
            embed.add_field(name="処理者", value=moderator.mention, inline=False)
            await ch.send(embed=embed)
        if (ch_id := self.onboarding_cog.new_welcome_channel_id) and (ch := guild.get_channel(ch_id)):
            await self._send_new_welcome_message(ch, member, self.onboarding_cog.mention_role_id_1)
    async def _send_notifications(self, moderator: discord.Member, member: discord.Member, is_approved: bool) -> None:
        guild = member.guild
        if is_approved:
            try: await member.send(f"✅ お知らせ：「{guild.name}」での住人登録が承認されました。")
            except discord.Forbidden: logger.warning(f"{member.display_name}님에게 DM을 보낼 수 없습니다.")
        else:
            try: await member.send(f"❌ お知らせ：「{guild.name}」での住人登録が拒否されました。\n理由: 「{self.rejection_reason}」\n<#{self.onboarding_cog.panel_channel_id}> からやり直してください。")
            except discord.Forbidden: logger.warning(f"{member.display_name}님에게 DM을 보낼 수 없습니다.")
            if (ch_id := self.onboarding_cog.rejection_log_channel_id) and (ch := guild.get_channel(ch_id)):
                embed = self.original_embed.copy(); embed.title = "❌ 住人登録が拒否されました"; embed.color = discord.Color.red(); embed.description = f"**対象者:** {member.mention}"
                embed.add_field(name="拒否理由", value=self.rejection_reason or "理由未入力", inline=False); embed.add_field(name="処理者", value=moderator.mention, inline=False)
                await ch.send(content=member.mention, embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
    async def _send_new_welcome_message(self, channel: discord.TextChannel, member: discord.Member, mention_role_id: Optional[int]):
        mention = f"<@&{mention_role_id}>" if mention_role_id else ""
        content = f"# {member.mention} さんがDico森へ里入りしました！\n## 皆さんで歓迎しましょう！ {mention}"
        desc = ("Dico森は、皆さんの「森での暮らし」をより豊かにするための場所です。\n"
                "**<#1404410186562666546>**で依頼を確認し、里の活動に参加してみましょう。\n"
                "困ったことがあれば、**<#1404410207148445818>**にいる世話役さんに質問してくださいね。")
        embed = discord.Embed(description=desc, color=0xFFFFE0)
        try: await channel.send(content=content, embed=embed, allowed_mentions=discord.AllowedMentions(users=True, roles=True))
        except Exception as e: logger.error(f"Error sending new welcome message: {e}", exc_info=True)

class OnboardingView(ui.View):
    def __init__(self, cog_instance: 'Onboarding', steps_data: List[Dict[str, Any]]):
        super().__init__(timeout=300)
        self.onboarding_cog = cog_instance
        self.steps_data = steps_data
        self.update_view()

    def update_view(self):
        self.clear_items()
        page = self.steps_data[self.current_step]
        
        if self.current_step > 0:
            prev_button = ui.Button(label="◀ 前へ", style=discord.ButtonStyle.secondary, custom_id="onboarding_prev", row=1)
            prev_button.callback = self.go_previous
            self.add_item(prev_button)

        page_type = page.get("step_type")
        if page_type == "info":
            next_button = ui.Button(label="次へ ▶", style=discord.ButtonStyle.primary, custom_id="onboarding_next")
            next_button.callback = self.go_next
            self.add_item(next_button)
        elif page_type == "action":
            action_button = ui.Button(label=page.get("button_label", "確認"), style=discord.ButtonStyle.success, custom_id="onboarding_action")
            action_button.callback = self.do_action
            self.add_item(action_button)
        elif page_type == "intro":
            intro_button = ui.Button(label="住人登録票を作成する", style=discord.ButtonStyle.success, custom_id="onboarding_intro")
            intro_button.callback = self.create_introduction
            self.add_item(
