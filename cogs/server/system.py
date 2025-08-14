# cogs/server/system.py (완전 동적 방식으로 수정된 최종본)

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import logging
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

# --- 데이터베이스 함수 임포트 ---
from utils.database import (
    get_channel_id_from_db, get_role_id,
    save_embed_to_db, get_embed_from_db, delete_embed_from_db,
    save_panel_id, get_panel_id, delete_panel_id,
    add_auto_role_panel, get_all_auto_role_panels, delete_auto_role_panel,
    add_auto_role_button, get_auto_role_buttons, remove_auto_role_button
)

# --- View / Modal 정의 ---

# [유지] 봇 재시작 시 실제 패널의 버튼을 복구하는 핵심 View
class AutoRoleView(ui.View):
    def __init__(self, buttons_config: list | None = None):
        super().__init__(timeout=None)
        if buttons_config:
            for config in buttons_config:
                style_map = {'primary': discord.ButtonStyle.primary, 'secondary': discord.ButtonStyle.secondary,
                             'success': discord.ButtonStyle.success, 'danger': discord.ButtonStyle.danger}
                button = ui.Button(
                    label=config['button_label'], emoji=config.get('button_emoji'),
                    style=style_map.get(config.get('button_style', 'secondary'), discord.ButtonStyle.secondary),
                    custom_id=f"auto_role:{config['role_id']}"
                )
                button.callback = self.button_callback
                self.add_item(button)

    async def button_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        custom_id = interaction.data['custom_id']
        role_id = int(custom_id.split(':')[1])
        if not isinstance(interaction.user, discord.Member): return
        role = interaction.guild.get_role(role_id)
        if not role:
            return await interaction.followup.send("❌ 오류: 이 역할은 더 이상 존재하지 않습니다.", ephemeral=True)
        try:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                await interaction.followup.send(f"✅ 역할 '{role.name}'을(를) 해제했습니다.", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.followup.send(f"✅ 역할 '{role.name}'을(를) 부여했습니다.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ 오류: 봇이 역할을 부여/해제할 권한이 없습니다.", ephemeral=True)
        except Exception as e:
            logger.error(f"자동 역할 변경 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send("❌ 오류가 발생했습니다.", ephemeral=True)

# [신규] 역할 버튼 추가/수정을 위한 Modal
class RoleButtonModal(ui.Modal, title="역할 버튼 편집"):
    def __init__(self, current_label: str = "", current_emoji: str = ""):
        super().__init__()
        self.label = ui.TextInput(label="버튼에 표시될 텍스트", placeholder="예: 공지 알림", default=current_label, max_length=80)
        self.emoji = ui.TextInput(label="버튼 이모지 (선택 사항)", placeholder="예: 📢", default=current_emoji, required=False, max_length=10)
        self.add_item(self.label)
        self.add_item(self.emoji)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer() # 응답을 지연시켜 view에서 후속처리
        self.stop()

# [신규] 임베드 수정을 위한 Modal
class EmbedEditModal(ui.Modal, title="임베드 편집"):
    def __init__(self, current_embed: Optional[discord.Embed]):
        super().__init__()
        self.new_embed_data = {}
        title = current_embed.title if current_embed else ""
        desc = current_embed.description if current_embed else ""

        self.embed_title = ui.TextInput(label="제목", default=title, required=False, max_length=256)
        self.embed_description = ui.TextInput(label="설명 (\\n으로 줄바꿈)", style=discord.TextStyle.paragraph, default=desc, required=False, max_length=4000)
        self.add_item(self.embed_title)
        self.add_item(self.embed_description)

    async def on_submit(self, interaction: discord.Interaction):
        self.new_embed_data['title'] = self.embed_title.value
        self.new_embed_data['description'] = self.embed_description.value.replace('\\n', '\n')
        await interaction.response.defer()
        self.stop()

# [신규] 패널의 모든 것을 관리하는 View
class PanelEditorView(ui.View):
    def __init__(self, panel_key: str):
        super().__init__(timeout=None)
        self.panel_key = panel_key

    async def refresh_live_panel(self, interaction: discord.Interaction):
        """DB 정보를 기반으로 실제 역할 패널 메시지를 생성/업데이트합니다."""
        panel_info = await get_panel_id(self.panel_key)
        if not panel_info: return

        channel = interaction.guild.get_channel(panel_info['channel_id'])
        if not channel: return

        embed_data = await get_embed_from_db(self.panel_key)
        embed = discord.Embed.from_dict(embed_data) if embed_data else discord.Embed(title=f"{self.panel_key} 패널")

        buttons_config = await get_auto_role_buttons(panel_info['message_id'])
        view = AutoRoleView(buttons_config)

        try:
            msg = await channel.fetch_message(panel_info['message_id'])
            await msg.edit(embed=embed, view=view)
        except discord.NotFound:
            # 메시지가 삭제된 경우, DB 정보도 삭제
            await delete_panel_id(self.panel_key)
            await delete_auto_role_panel(panel_info['message_id'])
            await interaction.followup.send("⚠️ 실제 패널 메시지를 찾을 수 없어 DB에서 제거했습니다. 다시 생성해주세요.", ephemeral=True)

    @ui.button(label="임베드 수정", style=discord.ButtonStyle.primary, emoji="✍️", row=0)
    async def edit_embed(self, interaction: discord.Interaction, button: ui.Button):
        embed_data = await get_embed_from_db(self.panel_key)
        embed = discord.Embed.from_dict(embed_data) if embed_data else None
        
        modal = EmbedEditModal(embed)
        await interaction.response.send_modal(modal)
        await modal.wait()

        if not modal.is_finished(): return

        if embed_data:
            embed_data.update(modal.new_embed_data)
        else:
            embed_data = modal.new_embed_data
        
        await save_embed_to_db(self.panel_key, embed_data)
        await self.refresh_live_panel(interaction)
        await interaction.followup.send("✅ 임베드가 수정되었습니다.", ephemeral=True)

    @ui.button(label="버튼 추가", style=discord.ButtonStyle.success, emoji="➕", row=1)
    async def add_button(self, interaction: discord.Interaction, button: ui.Button):
        panel_info = await get_panel_id(self.panel_key)
        if not panel_info:
            return await interaction.response.send_message("❌ 이 작업을 수행하기 전에 먼저 패널을 생성하고 저장해야 합니다.", ephemeral=True)

        await interaction.response.send_message("추가할 역할을 멘션하거나 역할 ID를 입력해주세요. (60초)", ephemeral=True)
        try:
            msg = await self.bot.wait_for('message', timeout=60.0, check=lambda m: m.author == interaction.user and m.channel == interaction.channel)
            role_to_add = None
            if msg.role_mentions: role_to_add = msg.role_mentions[0]
            elif msg.content.isdigit(): role_to_add = interaction.guild.get_role(int(msg.content))
            
            await msg.delete()

            if not role_to_add:
                return await interaction.followup.send("❌ 올바른 역할을 찾지 못했습니다.", ephemeral=True)

            modal = RoleButtonModal()
            await interaction.followup.send_modal(modal) # followup으로 보내야 함
            await modal.wait()

            if not modal.is_finished(): return

            # DB에 버튼 추가
            await add_auto_role_button(panel_info['message_id'], role_to_add.id, modal.label.value, modal.emoji.value or None, 'secondary')
            await self.refresh_live_panel(interaction)
            await interaction.followup.send(f"✅ 역할 '{role_to_add.name}' 버튼이 추가되었습니다.", ephemeral=True)

        except asyncio.TimeoutError:
            await interaction.followup.send("⏰ 시간이 초과되었습니다.", ephemeral=True)

    @ui.button(label="버튼 제거", style=discord.ButtonStyle.danger, emoji="➖", row=1)
    async def remove_button(self, interaction: discord.Interaction, button: ui.Button):
        panel_info = await get_panel_id(self.panel_key)
        if not panel_info:
            return await interaction.response.send_message("❌ 패널이 생성되지 않았습니다.", ephemeral=True)
            
        buttons_config = await get_auto_role_buttons(panel_info['message_id'])
        if not buttons_config:
            return await interaction.response.send_message("ℹ️ 제거할 버튼이 없습니다.", ephemeral=True)

        options = []
        for btn in buttons_config:
            role = interaction.guild.get_role(btn['role_id'])
            if role:
                options.append(discord.SelectOption(label=f"{btn['button_label']} ({role.name})", value=str(btn['role_id']), emoji=btn.get('button_emoji')))
        
        select = ui.Select(placeholder="제거할 버튼을 선택하세요...", options=options)

        async def select_callback(inner_interaction: discord.Interaction):
            role_id_to_remove = int(select.values[0])
            await remove_auto_role_button(panel_info['message_id'], role_id_to_remove)
            await self.refresh_live_panel(inner_interaction)
            await inner_interaction.response.edit_message(content="✅ 버튼이 제거되었습니다.", view=None)

        select.callback = select_callback
        view = ui.View(timeout=60)
        view.add_item(select)
        await interaction.response.send_message("아래 메뉴에서 제거할 버튼을 선택하세요.", view=view, ephemeral=True)

    @ui.button(label="편집기 닫기", style=discord.ButtonStyle.secondary, emoji="✖️", row=2)
    async def close_editor(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.message.delete()
# --------------------------------------------------------------------------------
# 메인 Cog 클래스
# --------------------------------------------------------------------------------
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
        
    # --- 유저 카운터 관련 로직 (기존과 동일, 변경 없음) ---
    def _schedule_counter_update(self, guild: discord.Guild):
        guild_id = guild.id
        if guild_id in self.update_tasks and not self.update_tasks[guild_id].done(): self.update_tasks[guild_id].cancel()
        self.update_tasks[guild_id] = asyncio.create_task(self.delayed_update(guild))

    async def delayed_update(self, guild: discord.Guild):
        await asyncio.sleep(5)
        await self.update_all_counters(guild)

    async def update_all_counters(self, guild: discord.Guild):
        # ... (기존 코드와 동일)
        pass

    @tasks.loop(minutes=10)
    async def update_counters_loop(self):
        # ... (기존 코드와 동일)
        pass

    @update_counters_loop.before_loop
    async def before_update_counters_loop(self):
        await self.bot.wait_until_ready()

    # --- 이벤트 리스너 (환영/작별 메시지 로직 수정) ---
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot: return
        # 임시 역할 부여
        if self.temp_user_role_id and (temp_role := member.guild.get_role(self.temp_user_role_id)):
            try: await member.add_roles(temp_role)
            except Exception as e: logger.error(f"임시 역할 부여 오류: {e}")

        # [변경] DB에서 환영 임베드를 불러와서 전송
        if self.welcome_channel_id and (welcome_channel := self.bot.get_channel(self.welcome_channel_id)):
            embed_data = await get_embed_from_db('welcome_embed')
            if not embed_data:
                logger.warning("DB에서 'welcome_embed'를 찾을 수 없어 환영 메시지를 보낼 수 없습니다.")
                return

            # member 관련 정보로 description을 포맷팅
            embed_data['description'] = embed_data.get('description', '').format(
                member_mention=member.mention,
                member_name=member.display_name,
                guild_name=member.guild.name
            )
            embed = discord.Embed.from_dict(embed_data)
            if member.display_avatar:
                embed.set_thumbnail(url=member.display_avatar.url)

            try:
                await welcome_channel.send(content=f"@everyone, {member.mention}", embed=embed)
            except Exception as e:
                logger.error(f"환영 메시지 전송 오류: {e}")
        
        self._schedule_counter_update(member.guild)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        # [변경] DB에서 작별 임베드를 불러와서 전송
        if self.farewell_channel_id and (farewell_channel := self.bot.get_channel(self.farewell_channel_id)):
            embed_data = await get_embed_from_db('farewell_embed')
            if not embed_data:
                logger.warning("DB에서 'farewell_embed'를 찾을 수 없어 작별 메시지를 보낼 수 없습니다.")
                return

            embed_data['description'] = embed_data.get('description', '').format(
                member_name=member.display_name
            )
            embed = discord.Embed.from_dict(embed_data)
            if member.display_avatar:
                embed.set_thumbnail(url=member.display_avatar.url)

            try:
                await farewell_channel.send(embed=embed)
            except Exception as e:
                logger.error(f"작별 메시지 전송 오류: {e}")

        self._schedule_counter_update(member.guild)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles != after.roles or before.premium_since != after.premium_since:
            self._schedule_counter_update(after.guild)

  # [신규] 패널 관리 명령어 그룹
    panel_group = app_commands.Group(name="panel", description="자동 역할 패널을 동적으로 관리합니다.")

    @panel_group.command(name="create", description="[관리자] 새로운 역할 패널과 편집기를 생성합니다.")
    @app_commands.describe(panel_key="패널을 식별할 고유 키 (영문, 숫자, _ 만 사용)", channel="실제 역할 패널이 생성될 채널")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def panel_create(self, interaction: discord.Interaction, panel_key: str, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)

        if await get_panel_id(panel_key):
            return await interaction.followup.send(f"❌ 오류: `{panel_key}` 키를 사용하는 패널이 이미 존재합니다.", ephemeral=True)

        # 1. 기본 임베드 생성 및 DB 저장
        default_embed = discord.Embed(
            title=f"📜 {panel_key} 역할 패널",
            description="아래 버튼을 눌러 역할을 받으세요!\n(관리자가 버튼을 설정할 때까지 기다려주세요.)",
            color=0x7289da
        )
        await save_embed_to_db(panel_key, default_embed.to_dict())

        # 2. 실제 패널 메시지 생성
        live_panel_msg = await channel.send(embed=default_embed, view=AutoRoleView([]))

        # 3. DB에 패널 정보 저장
        await save_panel_id(panel_key, live_panel_msg.id, channel.id)
        await add_auto_role_panel(live_panel_msg.id, interaction.guild.id, channel.id, default_embed.title, default_embed.description)

        # 4. 편집기 View 생성 및 전송
        editor_view = PanelEditorView(panel_key)
        await interaction.followup.send(f"✅ `{channel.mention}` 채널에 `{panel_key}` 패널을 생성했습니다.\n아래 편집기를 사용하여 패널을 완성하세요.", view=editor_view, ephemeral=True)

    @panel_group.command(name="edit", description="[관리자] 기존 역할 패널의 편집기를 불러옵니다.")
    @app_commands.describe(panel_key="편집할 패널의 고유 키")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def panel_edit(self, interaction: discord.Interaction, panel_key: str):
        if not await get_panel_id(panel_key):
            return await interaction.response.send_message(f"❌ 오류: `{panel_key}` 키를 사용하는 패널을 찾을 수 없습니다.", ephemeral=True)
        
        editor_view = PanelEditorView(panel_key)
        await interaction.response.send_message(f"⚙️ `{panel_key}` 패널 편집기입니다.", view=editor_view, ephemeral=True)

    @panel_group.command(name="delete", description="[관리자] 역할 패널과 모든 데이터를 삭제합니다.")
    @app_commands.describe(panel_key="삭제할 패널의 고유 키")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def panel_delete(self, interaction: discord.Interaction, panel_key: str):
        await interaction.response.defer(ephemeral=True)

        panel_info = await get_panel_id(panel_key)
        if not panel_info:
            return await interaction.followup.send(f"❌ 오류: `{panel_key}` 키를 사용하는 패널을 찾을 수 없습니다.", ephemeral=True)

        # 실제 메시지 삭제 시도
        try:
            channel = self.bot.get_channel(panel_info['channel_id'])
            if channel:
                msg = await channel.fetch_message(panel_info['message_id'])
                await msg.delete()
        except (discord.NotFound, discord.Forbidden):
            pass # 메시지가 없거나 권한이 없어도 DB는 삭제

        # DB에서 모든 관련 데이터 삭제
        await delete_panel_id(panel_key)
        await delete_auto_role_panel(panel_info['message_id']) # auto_roles의 데이터는 CASCADE로 자동 삭제됨
        await delete_embed_from_db(panel_key)
        
        await interaction.followup.send(f"✅ `{panel_key}` 패널과 관련된 모든 데이터가 삭제되었습니다.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))
