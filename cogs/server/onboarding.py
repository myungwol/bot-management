# cogs/server/onboarding.py (명령어 통합 최종본)

import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
import logging
import re
from datetime import datetime
import time

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 데이터베이스 함수 임포트
from utils.database import (
    get_panel_id, save_panel_id, get_channel_id_from_db, 
    get_role_id, get_auto_role_mappings, get_cooldown, set_cooldown
)

# 설정값
INTRODUCTION_COOLDOWN_SECONDS = 10 * 60
GUIDE_GIF_URL = "https://media.discordapp.net/attachments/1402228452106436689/1404406045635252266/welcome.gif?ex=689b128d&is=6899c10d&hm=e0226740554e16e44a6d8034c99c247ac174c38f53ea998aa0de600153e1c495&="
GUIDE_PAGES = [
    {"type": "info", "title": "🏡 Dico森へようこそ！ ✨", "description": "➡️ 次に進むには、下の「次へ」ボタンを押してください 📩"},
    {"type": "action", "title": "ボット紹介", "description": "**下のボタンを押すと、次の段階である「里の掟」チャンネルを閲覧する権限が付与されます。**", "button_label": "ボットの紹介を確認しました", "role_key": "role_onboarding_step_1"},
    {"type": "action", "title": "里の掟", "description": "「里の掟」チャンネルが閲覧可能になりました。\n\n## <#1404410157504397322>\n\n上記のチャンネルに移動し、すべての掟をよく確認してください。", "button_label": "掟を確認しました", "role_key": "role_onboarding_step_2"},
    {"type": "action", "title": "里の地図", "description": "次は、里のチャンネルについての案内です。\n\n## <#1404410171689664552>\n\nですべてのチャンネルの役割を確認してください。", "button_label": "地図を確認しました", "role_key": "role_onboarding_step_3"},
    {"type": "action", "title": "依頼掲示板", "description": "次は依頼掲示板の確認です。\n\n## <#1404410186562666546>", "button_label": "依頼掲示板を確認しました", "role_key": "role_onboarding_step_4"},
    {"type": "intro", "title": "住人登録票 (最終段階)", "description": "すべての案内を確認しました！いよいよ最終段階です。\n\n**下のボタンを押して、住人登録票を作成してください。**\n登録票が公務員によって承認されると、正式にすべての場所が利用可能になります。", "rules": "・性別の記載は必須です\n・年齢を非公開にしたい場合は、公務員に個別にご連絡ください\n・名前に特殊文字は使用できません\n・漢字は4文字まで、ひらがな・カタカナ・英数字は合わせて8文字まで可能です\n・不適切な名前は拒否される場合があります\n・未記入の項目がある場合、拒否されることがあります\n・参加経路も必ずご記入ください。（例：Disboard、〇〇からの招待など）"}
]

# --- View / Modal 클래스들 ---
class RejectionReasonModal(ui.Modal, title="拒否理由入力"):
    reason = ui.TextInput(label="拒否理由", placeholder="拒否する理由を具体的に入力してください。", style=discord.TextStyle.paragraph, required=True, max_length=200)
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

class IntroductionModal(ui.Modal, title="住人登録票"):
    name = ui.TextInput(label="名前", placeholder="里で使用する名前を記入してください", required=True, max_length=12)
    age = ui.TextInput(label="年齢", placeholder="例：20代、90年生まれ、30歳、非公開", required=True, max_length=20)
    gender = ui.TextInput(label="性別", placeholder="例：男、女性", required=True, max_length=10)
    hobby = ui.TextInput(label="趣味・好きなこと", placeholder="趣味や好きなことを自由に記入してください", style=discord.TextStyle.paragraph, required=True, max_length=500)
    path = ui.TextInput(label="参加経路", placeholder="例：Disboard、〇〇からの招待など", style=discord.TextStyle.paragraph, required=True, max_length=200)

    def __init__(self, approval_role_id: int):
        super().__init__()
        self.approval_role_id = approval_role_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            onboarding_cog = interaction.client.get_cog("Onboarding")
            if not onboarding_cog or not onboarding_cog.approval_channel_id:
                return await interaction.followup.send("❌ エラー: Onboarding機能が設定されていません。", ephemeral=True)
            approval_channel = interaction.guild.get_channel(onboarding_cog.approval_channel_id)
            if not approval_channel: return await interaction.followup.send("❌ エラー: 承認チャンネルが見つかりません。", ephemeral=True)
            await set_cooldown(f"intro_{interaction.user.id}", time.time())
            
            embed = discord.Embed(title="📝 新しい住人登録票が提出されました", description=f"**作成者:** {interaction.user.mention}", color=discord.Color.blue())
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            embed.add_field(name="名前", value=self.name.value, inline=False)
            embed.add_field(name="年齢", value=self.age.value, inline=False)
            embed.add_field(name="性別", value=self.gender.value, inline=False)
            embed.add_field(name="趣味・好きなこと", value=self.hobby.value, inline=False)
            embed.add_field(name="参加経路", value=self.path.value, inline=False)
            
            await approval_channel.send(
                content=f"<@&{self.approval_role_id}> 新しい住人登録票が提出されました。",
                embed=embed,
                view=ApprovalView(author=interaction.user, original_embed=embed, bot=interaction.client, approval_role_id=self.approval_role_id, auto_role_mappings=onboarding_cog.auto_role_mappings)
            )
            await interaction.followup.send("✅ 住人登録票を公務員に提出しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"Error submitting self-introduction: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 予期せぬエラーが発生しました。", ephemeral=True)

class ApprovalView(ui.View):
    def __init__(self, author: discord.Member, original_embed: discord.Embed, bot: commands.Bot, approval_role_id: int, auto_role_mappings: list):
        super().__init__(timeout=None)
        self.author = author
        self.original_embed = original_embed
        self.bot = bot
        self.approval_role_id = approval_role_id
        self.auto_role_mappings = auto_role_mappings
        self.rejection_reason: str | None = None

    def _parse_birth_year(self, text: str) -> int | None:
        text = text.strip().lower()
        if "非公開" in text or "ひこうかい" in text: return 0
        era_patterns = {'heisei': r'(?:h|平成)\s*(\d{1,2})', 'showa': r'(?:s|昭和)\s*(\d{1,2})', 'reiwa': r'(?:r|令和)\s*(\d{1,2})'}
        era_start_years = {"heisei": 1989, "showa": 1926, "reiwa": 2019}
        for era, pattern in era_patterns.items():
            match = re.search(pattern, text)
            if match: return era_start_years[era] + int(match.group(1)) - 1
        dai_match = re.search(r'(\d{1,2})\s*代', text)
        if dai_match: return datetime.now().year - (int(dai_match.group(1)) + 5)
        year_match = re.search(r'(\d{2,4})', text)
        if year_match and ("年" in text or "生まれ" in text):
            year = int(year_match.group(1))
            if year < 100: year += 1900 if year > datetime.now().year % 100 else 2000
            return year
        age_match = re.search(r'(\d+)', text)
        if age_match and ("歳" in text or "才" in text): return datetime.now().year - int(age_match.group(1))
        return None

    async def _check_permission(self, interaction: discord.Interaction) -> bool:
        if not self.approval_role_id:
            await interaction.response.send_message("エラー: 承認役割IDが設定されていません。", ephemeral=True)
            return False
        if not isinstance(interaction.user, discord.Member) or not any(role.id == self.approval_role_id for role in interaction.user.roles):
            await interaction.response.send_message("このボタンを押す権限がありません。", ephemeral=True)
            return False
        return True

    async def _handle_approval(self, interaction: discord.Interaction, approved: bool):
        if not await self._check_permission(interaction): return
        status_text = "承認" if approved else "拒否"
        original_message = interaction.message
        if not approved:
            rejection_modal = RejectionReasonModal()
            await interaction.response.send_modal(rejection_modal)
            if await rejection_modal.wait(): return
            self.rejection_reason = rejection_modal.reason.value
        else:
            await interaction.response.defer()
        for item in self.children: item.disabled = True
        processing_embed = discord.Embed(title=f"⏳ {status_text}処理中...", description=f"{self.author.mention}さんの住人登録票を処理しています。", color=discord.Color.orange())
        try: await original_message.edit(embed=processing_embed, view=self)
        except (discord.NotFound, discord.HTTPException): pass
        
        member = interaction.guild.get_member(self.author.id)
        if not member: return await interaction.followup.send("エラー: 対象のメンバーが見つかりませんでした。", ephemeral=True)
        try:
            if approved: await self._perform_approval_tasks(interaction, member)
            else: await self._perform_rejection_tasks(interaction)
            await interaction.followup.send(f"✅ {status_text}処理が正常に完了しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"Error during approval/rejection tasks: {e}", exc_info=True)
            await interaction.followup.send(f"❌ {status_text}処理中にエラーが発生しました。\n`{e}`", ephemeral=True)
        finally:
            try: await original_message.delete()
            except discord.NotFound: pass

    async def _perform_approval_tasks(self, i: discord.Interaction, member: discord.Member):
        tasks = []; cog = self.bot.get_cog("Onboarding")
        if cog.introduction_channel_id and (ch := i.guild.get_channel(cog.introduction_channel_id)):
            embed = self.original_embed.copy(); embed.title = "ようこそ！新しい仲間です！"; embed.color = discord.Color.green()
            embed.add_field(name="承認した公務員", value=i.user.mention, inline=False)
            tasks.append(ch.send(content=member.mention, embed=embed, allowed_mentions=discord.AllowedMentions(users=True)))
        if cog.new_welcome_channel_id and (ch := i.guild.get_channel(cog.new_welcome_channel_id)):
            tasks.append(self._send_new_welcome_message(member, ch, cog.mention_role_id_1))
        async def send_dm():
            try: await member.send(f"お知らせ：「{i.guild.name}」での住人登録が承認されました。")
            except discord.Forbidden: pass
        tasks.append(send_dm())
        async def update_roles_nick():
            try:
                roles_to_add = []
                if cog.guest_role_id and (role := i.guild.get_role(cog.guest_role_id)): roles_to_add.append(role)
                gender_field = next((f for f in self.original_embed.fields if f.name == "性別"), None)
                if gender_field:
                    for rule in self.auto_role_mappings:
                        if any(k.lower() in gender_field.value.lower() for k in rule["keywords"]):
                            if (role := i.guild.get_role(rule["role_id"])): roles_to_add.append(role); break
                age_field = next((f for f in self.original_embed.fields if f.name == "年齢"), None)
                if age_field:
                    year = self._parse_birth_year(age_field.value); key = None
                    if year == 0: key = "age_private_role"
                    elif year:
                        if 1970 <= year <= 1979: key = "age_70s_role"
                        elif 1980 <= year <= 1989: key = "age_80s_role"
                        elif 1990 <= year <= 1999: key = "age_90s_role"
                        elif 2000 <= year <= 2009: key = "age_00s_role"
                    if key and (rid := get_role_id(key)) and (role := i.guild.get_role(rid)): roles_to_add.append(role)
                if roles_to_add: await member.add_roles(*list(set(roles_to_add)))
                if cog.temp_user_role_id and (role := i.guild.get_role(cog.temp_user_role_id)) and role in member.roles: await member.remove_roles(role)
                if (nick_cog := self.bot.get_cog("Nicknames")) and (name_field := next((f for f in self.original_embed.fields if f.name == "名前"), None)):
                    await nick_cog.update_nickname(member, base_name_override=name_field.value)
            except Exception as e: logger.error(f"Error updating roles/nick for {member.display_name}: {e}", exc_info=True)
        tasks.append(update_roles_nick())
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _perform_rejection_tasks(self, i: discord.Interaction):
        tasks = []; cog = self.bot.get_cog("Onboarding")
        if cog.rejection_log_channel_id and (ch := i.guild.get_channel(cog.rejection_log_channel_id)):
            embed = discord.Embed(title="❌ 住人登録が拒否されました", description=f"**対象者:** {self.author.mention}", color=discord.Color.red())
            embed.set_thumbnail(url=self.author.display_avatar.url)
            for f in self.original_embed.fields: embed.add_field(name=f"申請内容「{f.name}」", value=f.value, inline=False)
            embed.add_field(name="拒否理由", value=self.rejection_reason or "理由未入力", inline=False)
            embed.add_field(name="処理者", value=i.user.mention, inline=False)
            tasks.append(ch.send(content=self.author.mention, embed=embed, allowed_mentions=discord.AllowedMentions(users=True)))
        async def send_dm():
            try: await self.author.send(f"「{i.guild.name}」での住人登録が拒否されました。\n理由: 「{self.rejection_reason}」\n<#{cog.panel_channel_id}> からやり直してください。")
            except discord.Forbidden: pass
        tasks.append(send_dm())
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_new_welcome_message(self, member: discord.Member, channel: discord.TextChannel, mention_role_id: int):
        mention = f"<@&{mention_role_id}>" if mention_role_id else ""
        content = f"# {member.mention} さんがDico森へ里入りしました！\n## 皆さんで歓迎しましょう！ {mention}"
        desc = ("Dico森は、皆さんの「森での暮らし」をより豊かにするための場所です。\n"
                "**<#1404410186562666546>**で依頼を確認し、里の活動に参加してみましょう。\n"
                "困ったことがあれば、**<#1404410207148445818>**にいる世話役さんに質問してくださいね。")
        embed = discord.Embed(description=desc, color=0xFFFFE0)
        try: await channel.send(content=content, embed=embed, allowed_mentions=discord.AllowedMentions(users=True, roles=True))
        except Exception as e: logger.error(f"Error sending new welcome message: {e}", exc_info=True)

    @ui.button(label='承認', style=discord.ButtonStyle.success, custom_id='approve_button_final')
    async def approve(self, i: discord.Interaction, b: ui.Button): await self._handle_approval(i, approved=True)
    @ui.button(label='拒否', style=discord.ButtonStyle.danger, custom_id='reject_button_final')
    async def reject(self, i: discord.Interaction, b: ui.Button): await self._handle_approval(i, approved=False)

class OnboardingView(ui.View):
    def __init__(self, current_step: int = 0, approval_role_id: int = 0):
        super().__init__(timeout=300); self.current_step = current_step; self.approval_role_id = approval_role_id; self.update_view()
    def update_view(self):
        self.clear_items(); page_data = GUIDE_PAGES[self.current_step]
        if self.current_step > 0:
            prev_button = ui.Button(label="◀ 前へ", style=discord.ButtonStyle.secondary, custom_id="onboarding_prev"); prev_button.callback = self.go_previous; self.add_item(prev_button)
        if page_data["type"] == "info":
            button = ui.Button(label="次へ ▶", style=discord.ButtonStyle.primary, custom_id="onboarding_next"); button.callback = self.go_next; self.add_item(button)
        elif page_data["type"] == "action":
            button = ui.Button(label=page_data.get("button_label", "確認"), style=discord.ButtonStyle.success, custom_id="onboarding_action"); button.callback = self.do_action; self.add_item(button)
        elif page_data["type"] == "intro":
            button = ui.Button(label="住人登録票を作成する", style=discord.ButtonStyle.success, custom_id="onboarding_intro"); button.callback = self.create_introduction; self.add_item(button)
    async def _update_message(self, interaction: discord.Interaction):
        page = GUIDE_PAGES[self.current_step]
        embed = discord.Embed(title=page["title"], description=page["description"], color=discord.Color.purple())
        if GUIDE_GIF_URL: embed.set_image(url=GUIDE_GIF_URL)
        if page.get("rules"): embed.add_field(name="⚠️ ルール", value=page["rules"], inline=False)
        self.update_view(); await interaction.edit_original_response(embed=embed, view=self)
    async def go_previous(self, i: discord.Interaction): await i.response.defer(); self.current_step -= 1; await self._update_message(i)
    async def go_next(self, i: discord.Interaction): await i.response.defer(); self.current_step += 1; await self._update_message(i)
    async def do_action(self, i: discord.Interaction):
        page_data = GUIDE_PAGES[self.current_step]; role_id = get_role_id(page_data.get("role_key"));
        if not role_id or not (role := i.guild.get_role(role_id)): return await i.response.send_message("エラー: 役職が見つかりません。", ephemeral=True)
        try:
            await i.response.defer()
            if role not in i.user.roles: await i.user.add_roles(role)
            self.current_step += 1; await self._update_message(i)
        except discord.Forbidden: await i.followup.send("エラー: 役職を付与する権限がありません。", ephemeral=True)
        except Exception as e: await i.followup.send(f"❌ 予期せぬエラー: {e}", ephemeral=True)
    async def create_introduction(self, interaction: discord.Interaction):
        key = f"intro_{interaction.user.id}"; last_time = await get_cooldown(key)
        if last_time and time.time() - last_time < INTRODUCTION_COOLDOWN_SECONDS:
            remaining = INTRODUCTION_COOLDOWN_SECONDS - (time.time() - last_time)
            return await interaction.response.send_message(f"次の申請まであと {int(remaining/60)}分 お待ちください。", ephemeral=True)
        cog = interaction.client.get_cog("Onboarding")
        await interaction.response.send_modal(IntroductionModal(approval_role_id=cog.approval_role_id if cog else 0))

class OnboardingPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @ui.button(label="里の案内・住人登録を始める", style=discord.ButtonStyle.success, custom_id="start_onboarding_button_final")
    async def start_onboarding(self, interaction: discord.Interaction, button: ui.Button):
        cog = interaction.client.get_cog("Onboarding")
        if not cog: return await interaction.response.send_message("エラー: Onboarding機能が利用できません。", ephemeral=True)
        page = GUIDE_PAGES[0]
        embed = discord.Embed(title=page["title"], description=page["description"], color=discord.Color.purple())
        if GUIDE_GIF_URL: embed.set_image(url=GUIDE_GIF_URL)
        await interaction.response.send_message(embed=embed, view=OnboardingView(approval_role_id=cog.approval_role_id if cog else 0), ephemeral=True)

# --- 메인 Cog 클래스 ---
class Onboarding(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(OnboardingPanelView())
        self.auto_role_mappings: list = []
        self.panel_channel_id: int | None = None; self.approval_channel_id: int | None = None
        self.introduction_channel_id: int | None = None; self.rejection_log_channel_id: int | None = None
        self.new_welcome_channel_id: int | None = None; self.approval_role_id: int | None = None
        self.guest_role_id: int | None = None; self.temp_user_role_id: int | None = None; self.mention_role_id_1: int | None = None
        logger.info("Onboarding Cog initialized.")

    async def cog_load(self):
        await self.load_onboarding_configs()

    async def load_onboarding_configs(self):
        self.auto_role_mappings = get_auto_role_mappings()
        self.panel_channel_id = await get_channel_id_from_db("onboarding_panel_channel_id")
        self.approval_channel_id = await get_channel_id_from_db("onboarding_approval_channel_id")
        self.introduction_channel_id = await get_channel_id_from_db("introduction_channel_id")
        self.rejection_log_channel_id = await get_channel_id_from_db("introduction_rejection_log_channel_id")
        self.new_welcome_channel_id = await get_channel_id_from_db("new_welcome_channel_id")
        self.approval_role_id = get_role_id("approval_role")
        self.guest_role_id = get_role_id("guest_role")
        self.temp_user_role_id = get_role_id("temp_user_role")
        self.mention_role_id_1 = get_role_id("mention_role_1")
        logger.info("[Onboarding Cog] Loaded configurations.")

    async def regenerate_panel(self, channel: discord.TextChannel | None = None):
        if channel is None:
            if self.panel_channel_id: channel = self.bot.get_channel(self.panel_channel_id)
            else: logger.info("ℹ️ Onboarding panel channel not set, skipping auto-regeneration."); return
        if not channel: logger.warning("❌ Onboarding panel channel could not be found."); return
        
        old_id = await get_panel_id("onboarding")
        if old_id:
            try: (await channel.fetch_message(old_id)).delete()
            except (discord.NotFound, discord.Forbidden): pass
        
        embed = discord.Embed(title="🏡 新米住人の方へ", description="この里へようこそ！\n下のボタンを押して、里での暮らし方を確認し、住人登録を始めましょう。", color=discord.Color.gold())
        msg = await channel.send(embed=embed, view=OnboardingPanelView())
        await save_panel_id("onboarding", msg.id, channel.id)
        logger.info(f"✅ Onboarding panel successfully regenerated in channel {channel.name}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Onboarding(bot))
