# cogs/server/system.py (모든 기능이 포함된 완전한 최종본)

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import logging
import asyncio
from typing import Optional

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 데이터베이스 함수 임포트 ---
from utils.database import (
    get_counter_configs, get_channel_id_from_db, get_role_id,
    save_panel_id, get_panel_id, delete_panel_id,
    add_auto_role_panel, delete_auto_role_panel,
    delete_all_buttons_for_panel, bulk_add_auto_role_buttons,
    save_embed_to_db, get_embed_from_db,
    save_channel_id_to_db
)

# --- 코드 기반 패널 데이터 구조 ---
STATIC_AUTO_ROLE_PANELS = {
    "main_roles": {
        "channel_key": "auto_role_channel_id",
        "embed": {
            "title": "📜 역할 선택",
            "description": "아래 버튼을 눌러 원하는 카테고리의 역할을 선택하세요!",
            "color": 0x5865F2
        },
        "categories": [
            {"id": "notifications", "label": "알림 역할 받기", "emoji": "📢"},
            {"id": "games", "label": "게임 역할 받기", "emoji": "🎮"},
        ],
        "roles": {
            "notifications": [
                {"role_id_key": "mention_role_1", "label": "서버 전체 공지", "description": "서버의 중요 업데이트 알림을 받습니다."},
            ],
            "games": []
        }
    }
}

# --- View / Modal 정의 ---
class EphemeralRoleSelectView(ui.View):
    def __init__(self, member: discord.Member, category_roles: list, all_category_role_ids: set[int]):
        super().__init__(timeout=180)
        self.member = member
        self.all_category_role_ids = all_category_role_ids
        current_user_role_ids = {r.id for r in self.member.roles}
        options = [discord.SelectOption(label=info['label'], value=str(rid), description=info.get('description'), default=(rid in current_user_role_ids)) for info in category_roles if (rid := get_role_id(info['role_id_key']))]
        self.role_select = ui.Select(placeholder="받고 싶은 역할을 모두 선택하세요...", min_values=0, max_values=len(options) or 1, options=options)
        self.role_select.callback = self.select_callback
        self.add_item(self.role_select)

    async def select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        selected_ids = {int(rid) for rid in self.role_select.values}
        current_ids = {r.id for r in interaction.user.roles}
        to_add_ids = selected_ids - current_ids
        to_remove_ids = (self.all_category_role_ids - selected_ids) & current_ids
        try:
            if to_add := [interaction.guild.get_role(rid) for rid in to_add_ids if interaction.guild.get_role(rid)]:
                await interaction.user.add_roles(*to_add)
            if to_remove := [interaction.guild.get_role(rid) for rid in to_remove_ids if interaction.guild.get_role(rid)]:
                await interaction.user.remove_roles(*to_remove)
            self.role_select.disabled = True
            await interaction.edit_original_response(content="✅ 역할이 성공적으로 업데이트되었습니다.", view=self)
            self.stop()
        except Exception as e:
            logger.error(f"드롭다운 역할 처리 오류: {e}")
            await interaction.followup.send("❌ 오류 발생.", ephemeral=True)

class AutoRoleView(ui.View):
    def __init__(self, panel_config: dict):
        super().__init__(timeout=None)
        self.panel_config = panel_config
        for category in self.panel_config.get("categories", []):
            button = ui.Button(label=category['label'], emoji=category.get('emoji'), style=discord.ButtonStyle.secondary, custom_id=f"category_select:{category['id']}")
            button.callback = self.category_button_callback
            self.add_item(button)

    async def category_button_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        category_id = interaction.data['custom_id'].split(':')[1]
        category_roles = self.panel_config.get("roles", {}).get(category_id, [])
        if not category_roles:
            return await interaction.followup.send("선택한 카테고리에 설정된 역할이 없습니다.", ephemeral=True)
        all_ids = {get_role_id(r['role_id_key']) for r in category_roles if get_role_id(r['role_id_key'])}
        embed = discord.Embed(title=f"'{category_id.capitalize()}' 역할 선택", description="아래 드롭다운에서 원하는 역할을 모두 선택하세요.", color=discord.Color.blue())
        await interaction.followup.send(embed=embed, view=EphemeralRoleSelectView(interaction.user, category_roles, all_ids), ephemeral=True)

class EmbedEditModal(ui.Modal, title="임베드 내용 편집"):
    def __init__(self, embed: discord.Embed):
        super().__init__()
        self.embed = embed
        self.embed_title = ui.TextInput(label="제목", default=embed.title, required=False, max_length=256)
        self.embed_description = ui.TextInput(label="설명 (\\n = 줄바꿈)", style=discord.TextStyle.paragraph, default=embed.description, required=False, max_length=4000)
        self.add_item(self.embed_title)
        self.add_item(self.embed_description)

    async def on_submit(self, interaction: discord.Interaction):
        self.embed.title = self.embed_title.value
        self.embed.description = self.embed_description.value.replace('\\n', '\n')
        await interaction.response.edit_message(embed=self.embed)

class EmbedEditorView(ui.View):
    def __init__(self, message: discord.Message, embed_key: str):
        super().__init__(timeout=None)
        self.message = message
        self.embed_key = embed_key

    @ui.button(label="제목/설명 수정", emoji="✍️")
    async def edit_content(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(EmbedEditModal(self.message.embeds[0]))

    @ui.button(label="DB에 저장", style=discord.ButtonStyle.success, emoji="💾")
    async def save_to_db(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        await save_embed_to_db(self.embed_key, self.message.embeds[0].to_dict())
        await interaction.followup.send(f"✅ DB에 '{self.embed_key}'로 저장됨.", ephemeral=True)

    @ui.button(label="편집기 삭제", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_editor(self, interaction: discord.Interaction, button: ui.Button):
        await self.message.delete()
        self.stop()

# --- 메인 Cog 클래스 ---
class ServerSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.welcome_channel_id: Optional[int] = None
        self.farewell_channel_id: Optional[int] = None
        self.temp_user_role_id: Optional[int] = None
        self.counter_configs = []
        self.update_tasks: dict[int, asyncio.Task] = {}
        logger.info("ServerSystem Cog initialized.")

    async def cog_load(self):
        await self.load_all_configs()
        self.update_counters_loop.start()

    def cog_unload(self):
        self.update_counters_loop.cancel()
        for task in self.update_tasks.values(): task.cancel()

    async def load_all_configs(self):
        self.welcome_channel_id = await get_channel_id_from_db("welcome_channel_id")
        self.farewell_channel_id = await get_channel_id_from_db("farewell_channel_id")
        self.temp_user_role_id = get_role_id("temp_user_role")
        self.counter_configs = await get_counter_configs()
        logger.info("[ServerSystem Cog] Loaded all configurations.")

    async def regenerate_panel(self):
        for panel_key, panel_config in STATIC_AUTO_ROLE_PANELS.items():
            try:
                channel_id = self.bot.channel_configs.get(panel_config['channel_key'])
                if not channel_id:
                    logger.info(f"ℹ️ '{panel_key}' 패널 채널이 DB에 설정되지 않아 건너뜁니다.")
                    continue
                channel = self.bot.get_channel(channel_id)
                if not channel:
                    logger.warning(f"❌ '{panel_key}' 패널 채널(ID: {channel_id})을 찾을 수 없습니다.")
                    continue
                embed = discord.Embed.from_dict(panel_config['embed'])
                view = AutoRoleView(panel_config)
                panel_info = await get_panel_id(panel_key)
                if panel_info and (msg_id := panel_info.get('message_id')):
                    try:
                        msg = await channel.fetch_message(msg_id)
                        await msg.edit(embed=embed, view=view)
                        logger.info(f"✅ '{panel_key}' 패널 자동 업데이트 완료.")
                    except discord.NotFound:
                        new_msg = await channel.send(embed=embed, view=view)
                        await save_panel_id(panel_key, new_msg.id, channel.id)
                        logger.info(f"✅ '{panel_key}' 패널 자동 재생성 완료.")
                else:
                    new_msg = await channel.send(embed=embed, view=view)
                    await save_panel_id(panel_key, new_msg.id, channel.id)
                    logger.info(f"✅ '{panel_key}' 패널 자동 생성 완료.")
            except Exception as e:
                logger.error(f"❌ '{panel_key}' 패널 자동 재생성 중 오류: {e}", exc_info=True)

    def _schedule_counter_update(self, guild: discord.Guild):
        guild_id = guild.id
        if guild_id in self.update_tasks and not self.update_tasks[guild_id].done(): self.update_tasks[guild_id].cancel()
        self.update_tasks[guild_id] = asyncio.create_task(self.delayed_update(guild))

    async def delayed_update(self, guild: discord.Guild):
        await asyncio.sleep(5)
        await self.update_all_counters(guild)

    async def update_all_counters(self, guild: discord.Guild):
        if not guild or not (guild_configs := [c for c in self.counter_configs if c['guild_id'] == guild.id]): return
        all_m, human_m, bot_m, boost_c = len(guild.members), len([m for m in guild.members if not m.bot]), len([m for m in guild.members if m.bot]), guild.premium_subscription_count
        for config in guild_configs:
            if not (channel := guild.get_channel(config['channel_id'])): continue
            c_type = config['counter_type']; count = 0
            if c_type == 'total': count = all_m
            elif c_type == 'members': count = human_m
            elif c_type == 'bots': count = bot_m
            elif c_type == 'boosters': count = boost_c
            elif c_type == 'role' and (role := guild.get_role(config['role_id'])): count = len(role.members)
            if channel.name != (new_name := config['format_string'].format(count)):
                try: await channel.edit(name=new_name, reason="카운터 자동 업데이트")
                except Exception as e: logger.error(f"카운터 채널 {channel.id} 수정 실패: {e}"); break

    @tasks.loop(minutes=10)
    async def update_counters_loop(self):
        for guild in self.bot.guilds: await self.update_all_counters(guild)

    @update_counters_loop.before_loop
    async def before_update_counters_loop(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot: return
        if self.temp_user_role_id and (role := member.guild.get_role(self.temp_user_role_id)):
            try: await member.add_roles(role)
            except Exception as e: logger.error(f"임시 역할 부여 오류: {e}")
        if self.welcome_channel_id and (ch := self.bot.get_channel(self.welcome_channel_id)):
            if embed_data := await get_embed_from_db('welcome_embed'):
                desc = embed_data.get('description', '').format(member_mention=member.mention, member_name=member.display_name, guild_name=member.guild.name)
                embed_data['description'] = desc
                embed = discord.Embed.from_dict(embed_data)
                if member.display_avatar: embed.set_thumbnail(url=member.display_avatar.url)
                try: await ch.send(f"@everyone, {member.mention}", embed=embed, allowed_mentions=discord.AllowedMentions(everyone=True, users=True))
                except Exception as e: logger.error(f"환영 메시지 전송 오류: {e}")
        self._schedule_counter_update(member.guild)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if self.farewell_channel_id and (ch := self.bot.get_channel(self.farewell_channel_id)):
            if embed_data := await get_embed_from_db('farewell_embed'):
                embed_data['description'] = embed_data.get('description', '').format(member_name=member.display_name)
                embed = discord.Embed.from_dict(embed_data)
                if member.display_avatar: embed.set_thumbnail(url=member.display_avatar.url)
                try: await ch.send(embed=embed)
                except Exception as e: logger.error(f"작별 메시지 전송 오류: {e}")
        self._schedule_counter_update(member.guild)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles != after.roles or before.premium_since != after.premium_since:
            self._schedule_counter_update(after.guild)

    setup_group = app_commands.Group(name="setup", description="[관리자] 봇의 주요 기능을 설정합니다.")

    @setup_group.command(name="set-channel", description="봇 기능에 필요한 채널을 등록합니다.")
    @app_commands.describe(key="채널 고유 키 (예: auto_role_channel_id)", channel="등록할 채널")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_channel(self, interaction: discord.Interaction, key: str, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        await save_channel_id_to_db(key, channel.id)
        # 봇의 캐시도 즉시 업데이트
        self.bot.channel_configs[key] = channel.id
        await interaction.followup.send(f"✅ 채널 설정 완료: `{key}` 키가 `{channel.mention}` 채널로 등록되었습니다.", ephemeral=True)

    @setup_group.command(name="panels", description="코드에 정의된 역할 패널을 생성/업데이트합니다.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_panels(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild: return
        await self.regenerate_panel()
        await interaction.followup.send("✅ 역할 패널 배포 작업이 완료되었습니다.", ephemeral=True)

    @setup_group.command(name="welcome-message", description="환영 메시지 편집기를 생성합니다.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_welcome_message(self, i: discord.Interaction, c: discord.TextChannel):
        await self.create_message_editor(i, c, 'welcome_embed', "환영 메시지")

    @setup_group.command(name="farewell-message", description="작별 메시지 편집기를 생성합니다.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_farewell_message(self, i: discord.Interaction, c: discord.TextChannel):
        await self.create_message_editor(i, c, 'farewell_embed', "작별 메시지")

    async def create_message_editor(self, i: discord.Interaction, ch: discord.TextChannel, key: str, name: str):
        await i.response.defer(ephemeral=True)
        embed_data = await get_embed_from_db(key) or {"title": f"{name} 제목", "description": f"{name} 설명을 입력하세요."}
        embed = discord.Embed.from_dict(embed_data)
        msg = await ch.send(content=f"**{name} 편집기**", embed=embed)
        await msg.edit(view=EmbedEditorView(msg, key))
        await i.followup.send(f"`{ch.mention}`에 {name} 편집기를 생성했습니다.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))
