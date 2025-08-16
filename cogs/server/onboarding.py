# cogs/server/onboarding.py (임베드 DB 연동)

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
    get_id, save_panel_id, get_panel_id, get_auto_role_mappings, get_cooldown, set_cooldown, get_embed_from_db
)

GUIDE_GIF_URL = None
INTRODUCTION_COOLDOWN_SECONDS = 10 * 60
AGE_ROLE_MAPPING = [{"key": "role_info_age_70s", "range": range(1970, 1980)}, {"key": "role_info_age_80s", "range": range(1980, 1990)}, {"key": "role_info_age_90s", "range": range(1990, 2000)}, {"key": "role_info_age_00s", "range": range(2000, 2010)}]
GUIDE_PAGES = [
    {"type": "info", "title": "🏡 Dico森へようこそ！ ✨", "description": "➡️ 次に進むには、下の「次へ」ボタンを押してください 📩"},
    {"type": "action", "title": "ボット紹介", "description": "**下のボタンを押すと、次の段階である「里の掟」チャンネルを閲覧する権限が付与されます。**", "button_label": "ボットの紹介を確認しました", "role_key": "role_onboarding_step_1"},
    {"type": "action", "title": "里の掟", "description": "「里の掟」チャンネルが閲覧可能になりました。\n\n## <#1404410157504397322>\n\n上記のチャンネルに移動し、すべての掟をよく確認してください。", "button_label": "掟を確認しました", "role_key": "role_onboarding_step_2"},
    {"type": "action", "title": "里の地図", "description": "次は、里のチャンネルについての案内です。\n\n## <#1404410171689664552>\n\nですべてのチャンネルの役割を確認してください。", "button_label": "地図を確認しました", "role_key": "role_onboarding_step_3"},
    {"type": "action", "title": "依頼掲示板", "description": "次は依頼掲示板の確認です。\n\n## <#1404410186562666546>", "button_label": "依頼掲示板を確認しました", "role_key": "role_onboarding_step_4"},
    {"type": "intro", "title": "住人登録票 (最終段階)", "description": "すべての案内を確認しました！いよいよ最終段階です。\n\n**下のボタンを押して、住人登録票を作成してください。**\n登録票が公務員によって承認されると、正式にすべての場所が利用可能になります。", "rules": "・性別の記載は必須です\n・年齢を非公開にしたい場合は、公務員に個別にご連絡ください\n・名前に特殊文字は使用できません\n・漢字は4文字まで、ひらがな・カタカナ・英数字は合わせて8文字まで可能です\n・不適切な名前は拒否される場合があります\n・未記入の項目がある場合、拒否されることがあります\n・参加経路も必ずご記入ください。（例：Disboard、〇〇からの招待など）"}
]

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
        if not approval_role_id:
            await interaction.response.send_message("❌ エラー: 承認役割IDが設定されていません。", ephemeral=True); return False
        if not isinstance(interaction.user, discord.Member) or not any(role.id == approval_role_id for role in interaction.user.roles):
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
    @ui.button(label='承認', style=discord.ButtonStyle.success, custom_id='approve_button_final')
    async def approve(self, i: discord.Interaction, b: ui.Button): await self._handle_approval_flow(i, is_approved=True)
    @ui.button(label='拒否', style=discord.ButtonStyle.danger, custom_id='reject_button_final')
    async def reject(self, i: discord.Interaction, b: ui.Button): await self._handle_approval_flow(i, is_approved=False)

class OnboardingView(ui.View):
    def __init__(self, cog_instance: 'Onboarding', current_step: int = 0):
        super().__init__(timeout=300); self.onboarding_cog = cog_instance; self.current_step = current_step; self.update_view()
    def update_view(self):
        self.clear_items(); page = GUIDE_PAGES[self.current_step]
        if self.current_step > 0:
            prev_button = ui.Button(label="◀ 前へ", style=discord.ButtonStyle.secondary, custom_id="onboarding_prev", row=1)
            prev_button.callback = self.go_previous; self.add_item(prev_button)
        if page["type"] == "info":
            next_button = ui.Button(label="次へ ▶", style=discord.ButtonStyle.primary, custom_id="onboarding_next")
            next_button.callback = self.go_next; self.add_item(next_button)
        elif page["type"] == "action":
            action_button = ui.Button(label=page.get("button_label", "確認"), style=discord.ButtonStyle.success, custom_id="onboarding_action")
            action_button.callback = self.do_action; self.add_item(action_button)
        elif page["type"] == "intro":
            intro_button = ui.Button(label="住人登録票を作成する", style=discord.ButtonStyle.success, custom_id="onboarding_intro")
            intro_button.callback = self.create_introduction; self.add_item(intro_button)
    async def _update_message(self, interaction: discord.Interaction):
        page = GUIDE_PAGES[self.current_step]
        embed = discord.Embed(title=page["title"], description=page["description"], color=discord.Color.purple())
        if GUIDE_GIF_URL: embed.set_image(url=GUIDE_GIF_URL)
        if page.get("rules"): embed.add_field(name="⚠️ ルール", value=page["rules"], inline=False)
        self.update_view()
        if interaction.response.is_done():
            await interaction.edit_original_response(embed=embed, view=self)
    async def go_previous(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.current_step > 0: self.current_step -= 1
        await self._update_message(interaction)
    async def go_next(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.current_step < len(GUIDE_PAGES) - 1: self.current_step += 1
        await self._update_message(interaction)
    async def do_action(self, interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            page_data = GUIDE_PAGES[self.current_step]
            role_id = get_id(page_data.get("role_key"))
            if not role_id or not (role := interaction.guild.get_role(role_id)):
                await interaction.followup.send("エラー: 役職が見つかりません。", ephemeral=True); return
            if role not in interaction.user.roles: await interaction.user.add_roles(role)
            if self.current_step < len(GUIDE_PAGES) - 1: self.current_step += 1
            await self._update_message(interaction)
        except Exception as e: await interaction.followup.send(f"❌ エラー: {e}", ephemeral=True)
    async def create_introduction(self, interaction: discord.Interaction):
        key = str(interaction.user.id)
        last_time = await get_cooldown(key, "introduction")
        if last_time and time.time() - last_time < INTRODUCTION_COOLDOWN_SECONDS:
            rem = INTRODUCTION_COOLDOWN_SECONDS - (time.time() - last_time)
            await interaction.response.send_message(f"次の申請まであと {int(rem/60)}分 お待ちください。", ephemeral=True); return
        await interaction.response.send_modal(IntroductionModal(self.onboarding_cog))

class OnboardingPanelView(ui.View):
    def __init__(self, cog_instance: 'Onboarding'):
        super().__init__(timeout=None); self.onboarding_cog = cog_instance
    @ui.button(label="里の案内・住人登録を始める", style=discord.ButtonStyle.success, custom_id="start_onboarding_button_final")
    async def start_onboarding(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            page = GUIDE_PAGES[0]
            embed = discord.Embed(title=page["title"], description=page["description"], color=discord.Color.purple())
            if GUIDE_GIF_URL: embed.set_image(url=GUIDE_GIF_URL)
            await interaction.followup.send(embed=embed, view=OnboardingView(self.onboarding_cog), ephemeral=True)
        except Exception as e:
            logger.error(f"온보딩 시작 중 오류: {e}", exc_info=True)
            if not interaction.response.is_done(): await interaction.response.send_message("오류가 발생했습니다.", ephemeral=True)

class Onboarding(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_channel_id: Optional[int] = None; self.approval_channel_id: Optional[int] = None
        self.introduction_channel_id: Optional[int] = None; self.rejection_log_channel_id: Optional[int] = None
        self.new_welcome_channel_id: Optional[int] = None; self.approval_role_id: Optional[int] = None
        self.guest_role_id: Optional[int] = None; self.mention_role_id_1: Optional[int] = None
        logger.info("Onboarding Cog가 성공적으로 초기화되었습니다.")
    
    def register_persistent_views(self):
        self.bot.add_view(OnboardingPanelView(self))
    
    async def cog_load(self): await self.load_all_configs()
    async def load_all_configs(self):
        self.panel_channel_id = get_id("onboarding_panel_channel_id"); self.approval_channel_id = get_id("onboarding_approval_channel_id")
        self.introduction_channel_id = get_id("introduction_channel_id"); self.rejection_log_channel_id = get_id("introduction_rejection_log_channel_id")
        self.new_welcome_channel_id = get_id("new_welcome_channel_id"); self.approval_role_id = get_id("role_approval")
        self.guest_role_id = get_id("role_guest"); self.mention_role_id_1 = get_id("role_mention_role_1")
        logger.info("[Onboarding Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")
        
    async def regenerate_panel(self, channel: Optional[discord.TextChannel] = None):
        target_channel = channel
        if target_channel is None:
            channel_id = get_id("onboarding_panel_channel_id")
            if channel_id: target_channel = self.bot.get_channel(channel_id)
            else: logger.info("ℹ️ 온보딩 패널 채널이 설정되지 않아, 자동 생성을 건너뜁니다."); return
        if not target_channel: logger.warning("❌ Onboarding panel channel could not be found."); return
        panel_info = get_panel_id("onboarding")
        if panel_info and (old_id := panel_info.get('message_id')):
            try:
                old_message = await target_channel.fetch_message(old_id)
                await old_message.delete()
            except (discord.NotFound, discord.Forbidden): pass
            
        embed_data = await get_embed_from_db("panel_onboarding")
        if not embed_data:
            logger.warning("DB에서 'panel_onboarding' 임베드 데이터를 찾을 수 없어, 패널 생성을 건너뜁니다.")
            return
        embed = discord.Embed.from_dict(embed_data)
        
        view = OnboardingPanelView(self)
        new_message = await target_channel.send(embed=embed, view=view)
        await save_panel_id("onboarding", new_message.id, target_channel.id)
        logger.info(f"✅ 온보딩 패널을 성공적으로 새로 생성했습니다. (채널: #{target_channel.name})")

async def setup(bot: commands.Bot):
    await bot.add_cog(Onboarding(bot))
