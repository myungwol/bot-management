# cogs/server/system.py (카운터 기능 포함 최종본)

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import logging
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

# --- 데이터베이스 함수 임포트 ---
from utils.database import (
    get_counter_configs, get_channel_id_from_db, get_role_id,
    save_embed_to_db, get_embed_from_db, delete_embed_from_db,
    save_panel_id, get_panel_id, delete_panel_id,
    add_auto_role_panel, get_all_auto_role_panels, delete_auto_role_panel,
    add_auto_role_button, get_auto_role_buttons, remove_auto_role_button
)

# ----------------------------------------------------------------------------
# View / Modal 정의
# ----------------------------------------------------------------------------

class EphemeralRoleGrantView(ui.View):
    def __init__(self, role: discord.Role, member: discord.Member):
        super().__init__(timeout=120)
        self.role = role
        self.member = member
        if self.role in self.member.roles: self.children[0].disabled = True
        else: self.children[1].disabled = True
    @ui.button(label="역할 받기", style=discord.ButtonStyle.success, emoji="✅")
    async def grant_role(self, i: discord.Interaction, b: ui.Button): await self.handle_role(i, 'add')
    @ui.button(label="역할 해제", style=discord.ButtonStyle.danger, emoji="❌")
    async def remove_role(self, i: discord.Interaction, b: ui.Button): await self.handle_role(i, 'remove')
    async def handle_role(self, interaction: discord.Interaction, action: str):
        await interaction.response.defer()
        try:
            has_role = self.role in self.member.roles
            if action == 'add' and not has_role:
                await self.member.add_roles(self.role)
                await interaction.followup.send(f"✅ 역할 '{self.role.name}'을(를) 성공적으로 받았습니다.", ephemeral=True)
            elif action == 'remove' and has_role:
                await self.member.remove_roles(self.role)
                await interaction.followup.send(f"✅ 역할 '{self.role.name}'을(를) 성공적으로 해제했습니다.", ephemeral=True)
            else:
                await interaction.followup.send(f"ℹ️ 역할 상태에 변경사항이 없습니다.", ephemeral=True)
            for item in self.children: item.disabled = True
            await interaction.edit_original_response(view=self)
            self.stop()
        except Exception as e:
            logger.error(f"임시 창 역할 처리 오류: {e}"); await interaction.followup.send("❌ 오류가 발생했습니다.", ephemeral=True)
    @ui.button(label="닫기", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def close_view(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.message.delete(); self.stop()

class AutoRoleView(ui.View):
    def __init__(self, buttons_config: list | None = None):
        super().__init__(timeout=None)
        if buttons_config:
            for config in buttons_config:
                style_map = {'primary': discord.ButtonStyle.primary, 'secondary': discord.ButtonStyle.secondary, 'success': discord.ButtonStyle.success, 'danger': discord.ButtonStyle.danger}
                button = ui.Button(label=config['button_label'], emoji=config.get('button_emoji'), style=style_map.get(config.get('button_style', 'secondary'), discord.ButtonStyle.secondary), custom_id=f"auto_role:{config['role_id']}")
                button.callback = self.button_callback
                self.add_item(button)
    async def button_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        role_id = int(interaction.data['custom_id'].split(':')[1])
        if not isinstance(interaction.user, discord.Member) or not interaction.guild: return
        role = interaction.guild.get_role(role_id)
        if not role: return await interaction.followup.send("❌ 오류: 이 역할은 더 이상 존재하지 않습니다.", ephemeral=True)
        embed = discord.Embed(title=f"'{role.name}' 역할 관리", description="아래 버튼을 눌러 역할을 받거나 해제하세요.", color=role.color if role.color.value != 0 else discord.Color.blurple())
        embed.set_footer(text="이 메시지는 2분 후에 비활성화됩니다.")
        await interaction.followup.send(embed=embed, view=EphemeralRoleGrantView(role=role, member=interaction.user), ephemeral=True)

class RoleButtonModal(ui.Modal, title="역할 버튼 편집"):
    def __init__(self, current_label: str = "", current_emoji: str = ""):
        super().__init__()
        self.label = ui.TextInput(label="버튼 텍스트", default=current_label, max_length=80)
        self.emoji = ui.TextInput(label="버튼 이모지 (선택)", default=current_emoji, required=False, max_length=10)
        self.add_item(self.label); self.add_item(self.emoji)
    async def on_submit(self, i: discord.Interaction): await i.response.defer(); self.stop()

class EmbedEditModal(ui.Modal, title="임베드 편집"):
    def __init__(self, panel_key: str, current_embed: Optional[discord.Embed]):
        super().__init__()
        self.panel_key = panel_key
        self.current_embed_data = current_embed.to_dict() if current_embed else {}
        self.embed_title = ui.TextInput(label="제목", default=current_embed.title if current_embed else "", required=False, max_length=256)
        self.embed_description = ui.TextInput(label="설명 (\\n = 줄바꿈)", style=discord.TextStyle.paragraph, default=current_embed.description if current_embed else "", required=False, max_length=4000)
        self.add_item(self.embed_title); self.add_item(self.embed_description)
    async def on_submit(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True, thinking=True)
        self.current_embed_data.update({'title': self.embed_title.value, 'description': self.embed_description.value.replace('\\n', '\n')})
        await save_embed_to_db(self.panel_key, self.current_embed_data)
        await self.refresh_live_panel(i)
        await i.followup.send("✅ 임베드가 수정되었습니다.", ephemeral=True)
    async def refresh_live_panel(self, i: discord.Interaction):
        p_info = await get_panel_id(self.panel_key)
        if not p_info or not i.guild or not (ch := i.guild.get_channel(p_info['channel_id'])): return
        embed = discord.Embed.from_dict(await get_embed_from_db(self.panel_key) or {})
        view = AutoRoleView(await get_auto_role_buttons(p_info['message_id']))
        try: await (await ch.fetch_message(p_info['message_id'])).edit(embed=embed, view=view)
        except discord.NotFound: await delete_panel_id(self.panel_key); await delete_auto_role_panel(p_info['message_id'])

class PanelEditorView(ui.View):
    def __init__(self, bot: commands.Bot, panel_key: str):
        super().__init__(timeout=None)
        self.bot = bot; self.panel_key = panel_key
    async def _refresh_live_panel(self, i: discord.Interaction):
        await EmbedEditModal(self.panel_key, None).refresh_live_panel(i)
    @ui.button(label="임베드 수정", style=discord.ButtonStyle.primary, emoji="✍️", row=0)
    async def edit_embed(self, i: discord.Interaction, b: ui.Button):
        await i.response.send_modal(EmbedEditModal(self.panel_key, discord.Embed.from_dict(await get_embed_from_db(self.panel_key) or {})))
    @ui.button(label="버튼 추가", style=discord.ButtonStyle.success, emoji="➕", row=1)
    async def add_button(self, i: discord.Interaction, b: ui.Button):
        p_info = await get_panel_id(self.panel_key)
        if not p_info: return await i.response.send_message("❌ 패널 생성 후 사용 가능합니다.", ephemeral=True)
        await i.response.send_message("추가할 역할을 멘션하거나 역할 ID를 입력하세요. (60초)", ephemeral=True)
        try:
            msg = await self.bot.wait_for('message', timeout=60.0, check=lambda m: m.author == i.user and m.channel == i.channel)
            role = msg.role_mentions[0] if msg.role_mentions else i.guild.get_role(int(msg.content)) if msg.content.isdigit() else None
            await msg.delete()
            if not role: return await i.followup.send("❌ 역할을 찾지 못했습니다.", ephemeral=True)
            modal = RoleButtonModal()
            await i.followup.send_modal(modal); await modal.wait()
            if not modal.is_finished(): return
            await add_auto_role_button(p_info['message_id'], role.id, modal.label.value, modal.emoji.value or None, 'secondary')
            await self._refresh_live_panel(i)
            await i.followup.send(f"✅ 역할 '{role.name}' 버튼이 추가되었습니다.", ephemeral=True)
        except asyncio.TimeoutError: await i.followup.send("⏰ 시간이 초과되었습니다.", ephemeral=True)
    @ui.button(label="버튼 제거", style=discord.ButtonStyle.danger, emoji="➖", row=1)
    async def remove_button(self, i: discord.Interaction, b: ui.Button):
        p_info = await get_panel_id(self.panel_key)
        if not p_info or not (btns := await get_auto_role_buttons(p_info['message_id'])): return await i.response.send_message("ℹ️ 제거할 버튼이 없습니다.", ephemeral=True)
        opts = [discord.SelectOption(label=f"{btn['button_label']}", value=str(btn['role_id']), emoji=btn.get('button_emoji')) for btn in btns]
        select = ui.Select(placeholder="제거할 버튼을 선택하세요...", options=opts)
        async def cb(inner_i: discord.Interaction):
            await remove_auto_role_button(p_info['message_id'], int(select.values[0]))
            await self._refresh_live_panel(inner_i)
            await inner_i.response.edit_message(content="✅ 버튼이 제거되었습니다.", view=None)
        select.callback = cb
        view = ui.View(timeout=60); view.add_item(select)
        await i.response.send_message("아래 메뉴에서 제거할 버튼을 선택하세요.", view=view, ephemeral=True)
    @ui.button(label="편집기 닫기", style=discord.ButtonStyle.secondary, emoji="✖️", row=2)
    async def close_editor(self, i: discord.Interaction, b: ui.Button): await i.message.delete()

# ----------------------------------------------------------------------------
# 메인 Cog 클래스
# ----------------------------------------------------------------------------
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
        self.update_counters_loop.start() # <--- 이 함수가 이제 존재합니다.

    def cog_unload(self):
        self.update_counters_loop.cancel()
        for task in self.update_tasks.values(): task.cancel()

    async def load_all_configs(self):
        self.welcome_channel_id = await get_channel_id_from_db("welcome_channel_id")
        self.farewell_channel_id = await get_channel_id_from_db("farewell_channel_id")
        self.temp_user_role_id = get_role_id("temp_user_role")
        self.counter_configs = await get_counter_configs()
        logger.info("[ServerSystem Cog] Loaded all configurations.")

    # --- [복구] 유저 카운터 관련 로직 ---
    def _schedule_counter_update(self, guild: discord.Guild):
        guild_id = guild.id
        if guild_id in self.update_tasks and not self.update_tasks[guild_id].done(): self.update_tasks[guild_id].cancel()
        self.update_tasks[guild_id] = asyncio.create_task(self.delayed_update(guild))

    async def delayed_update(self, guild: discord.Guild):
        await asyncio.sleep(5)
        await self.update_all_counters(guild)

    async def update_all_counters(self, guild: discord.Guild):
        if not guild: return
        guild_configs = [config for config in self.counter_configs if config['guild_id'] == guild.id]
        if not guild_configs: return
        all_members, human_members, bot_members = len(guild.members), len([m for m in guild.members if not m.bot]), len([m for m in guild.members if m.bot])
        booster_count = guild.premium_subscription_count
        for config in guild_configs:
            channel = guild.get_channel(config['channel_id'])
            if not channel: continue
            count = 0; c_type = config['counter_type']
            if c_type == 'total': count = all_members
            elif c_type == 'members': count = human_members
            elif c_type == 'bots': count = bot_members
            elif c_type == 'boosters': count = booster_count
            elif c_type == 'role' and (role := guild.get_role(config['role_id'])): count = len(role.members)
            new_name = config['format_string'].format(count)
            if channel.name != new_name:
                try: await channel.edit(name=new_name, reason="카운터 자동 업데이트")
                except Exception as e: logger.error(f"카운터 채널 {channel.id} 수정 실패: {e}"); break

    @tasks.loop(minutes=10)
    async def update_counters_loop(self):
        logger.info("주기적 카운터 업데이트 실행...")
        for guild in self.bot.guilds: await self.update_all_counters(guild)

    @update_counters_loop.before_loop
    async def before_update_counters_loop(self):
        await self.bot.wait_until_ready()
        logger.info("카운터 업데이트 루프 준비 완료.")

    # --- 이벤트 리스너 ---
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

    # --- 패널 관리 명령어 그룹 ---
    panel_group = app_commands.Group(name="panel", description="자동 역할 패널을 동적으로 관리합니다.")

    @panel_group.command(name="create", description="[관리자] 역할 패널과 편집기를 생성합니다.")
    @app_commands.describe(panel_key="패널 고유 키 (영문, 숫자, _ 사용)", channel="역할 패널이 생성될 채널")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def panel_create(self, i: discord.Interaction, panel_key: str, channel: discord.TextChannel):
        await i.response.defer(ephemeral=True)
        if await get_panel_id(panel_key): return await i.followup.send(f"❌ `{panel_key}` 키는 이미 존재합니다.", ephemeral=True)
        embed = discord.Embed(title=f"📜 {panel_key} 역할 패널", description="관리자가 패널을 설정하고 있습니다...", color=0x7289da)
        await save_embed_to_db(panel_key, embed.to_dict())
        msg = await channel.send(embed=embed, view=AutoRoleView([]))
        await save_panel_id(panel_key, msg.id, channel.id)
        await add_auto_role_panel(msg.id, i.guild.id, channel.id, embed.title, embed.description)
        await i.followup.send(f"✅ `{channel.mention}`에 패널 생성 완료.", view=PanelEditorView(self.bot, panel_key), ephemeral=True)

    @panel_group.command(name="edit", description="[관리자] 기존 역할 패널의 편집기를 불러옵니다.")
    @app_commands.describe(panel_key="편집할 패널의 고유 키")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def panel_edit(self, i: discord.Interaction, panel_key: str):
        if not await get_panel_id(panel_key): return await i.response.send_message(f"❌ `{panel_key}` 키를 찾을 수 없습니다.", ephemeral=True)
        await i.response.send_message(f"⚙️ `{panel_key}` 패널 편집기", view=PanelEditorView(self.bot, panel_key), ephemeral=True)

    @panel_group.command(name="delete", description="[관리자] 역할 패널과 모든 데이터를 삭제합니다.")
    @app_commands.describe(panel_key="삭제할 패널의 고유 키")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def panel_delete(self, i: discord.Interaction, panel_key: str):
        await i.response.defer(ephemeral=True)
        p_info = await get_panel_id(panel_key)
        if not p_info: return await i.followup.send(f"❌ `{panel_key}` 키를 찾을 수 없습니다.", ephemeral=True)
        try:
            if ch := self.bot.get_channel(p_info['channel_id']): await (await ch.fetch_message(p_info['message_id'])).delete()
        except (discord.NotFound, discord.Forbidden): pass
        await delete_panel_id(panel_key); await delete_auto_role_panel(p_info['message_id']); await delete_embed_from_db(panel_key)
        await i.followup.send(f"✅ `{panel_key}` 패널이 삭제되었습니다.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))
