# cogs/server/system.py (대규모 수정 제안본)

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import logging
import asyncio
from typing import Optional

# --- 로깅 설정 (기존과 동일) ---
logger = logging.getLogger(__name__)

# --- 데이터베이스 및 설정 임포트 (수정) ---
from utils.database import (
    get_channel_id_from_db, get_role_id, save_panel_id, get_panel_id,
    get_counter_configs, add_counter_config, remove_counter_config, # 카운터 기능은 유지
    # 자동 역할 관련 DB 함수는 AutoRoleView에서만 사용되므로 그대로 둠
    add_auto_role_button, remove_auto_role_button, get_auto_role_buttons, add_auto_role_panel,
    # [추가] 임베드 저장을 위한 DB 함수
    save_embed_to_db, get_embed_from_db, delete_embed_from_db
)

# --------------------------------------------------------------------------------
# [추가] 정적으로 자동 역할 패널을 정의하는 부분
# 이곳에 필요한 패널과 버튼 정보를 미리 작성합니다.
# --------------------------------------------------------------------------------
STATIC_AUTO_ROLE_PANELS = {
    "main_roles": {  # 이 패널의 고유 키 (DB 저장에 사용)
        "channel_key": "auto_role_channel_id", # 이 패널이 생성될 채널 ID를 가져올 키
        "embed": {
            "title": "📜 역할 선택 패널",
            "description": "아래 버튼을 눌러 원하시는 역할을 받거나 해제하세요!",
            "color": 0x5865F2 # Discord Blurple
        },
        "buttons": [
            # { "role_id_key": DB의 ROLE_ID_CONFIG 키, "label": 버튼 이름, "emoji": 이모지, "style": 버튼 색상 }
            {"role_id_key": "mention_role_1", "label": "공지 알림", "emoji": "📢", "style": "secondary"},
            # 여기에 필요한 만큼 버튼을 추가합니다.
        ]
    },
    # 다른 패널이 필요하면 여기에 추가
    # "age_roles": { ... }
}

# --------------------------------------------------------------------------------
# 자동 역할 View (기존과 거의 동일, 봇 재시작 시 버튼 복구에 필수)
# --------------------------------------------------------------------------------
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
        # (기존 콜백 로직과 동일)
        await interaction.response.defer(ephemeral=True)
        custom_id = interaction.data['custom_id']
        role_id = int(custom_id.split(':')[1])
        if not isinstance(interaction.user, discord.Member): return
        role = interaction.guild.get_role(role_id)
        if not role:
            return await interaction.followup.send("오류: 이 역할은 더 이상 존재하지 않습니다.", ephemeral=True)
        try:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                await interaction.followup.send(f"✅ 역할 '{role.name}'을(를) 해제했습니다.", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.followup.send(f"✅ 역할 '{role.name}'을(를) 부여했습니다.", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("오류: 봇이 역할을 부여/해제할 권한이 없습니다.", ephemeral=True)
        except Exception as e:
            logger.error(f"자동 역할 변경 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send("오류가 발생했습니다.", ephemeral=True)


# --------------------------------------------------------------------------------
# [추가] Mimu 스타일 임베드 편집을 위한 Modal
# --------------------------------------------------------------------------------
class EmbedEditModal(ui.Modal, title="임베드 편집"):
    def __init__(self, current_embed: discord.Embed):
        super().__init__()
        self.new_embed = current_embed

        self.embed_title = ui.TextInput(label="제목", style=discord.TextStyle.short, default=current_embed.title, required=False, max_length=256)
        self.embed_description = ui.TextInput(label="설명", style=discord.TextStyle.paragraph, default=current_embed.description, required=False, max_length=4000)
        self.add_item(self.embed_title)
        self.add_item(self.embed_description)

    async def on_submit(self, interaction: discord.Interaction):
        self.new_embed.title = self.embed_title.value
        self.new_embed.description = self.embed_description.value
        await interaction.response.edit_message(embed=self.new_embed)
        # on_submit에서는 followup을 보낼 수 없으므로, edit_message로 즉시 반영

# --------------------------------------------------------------------------------
# [추가] 임베드 편집기 View
# --------------------------------------------------------------------------------
class EmbedEditorView(ui.View):
    def __init__(self, message: discord.Message, embed_key: str):
        super().__init__(timeout=None)
        self.message = message
        self.embed_key = embed_key # DB에 저장할 때 사용할 키 (예: 'welcome_embed')

    @ui.button(label="제목/설명 수정", style=discord.ButtonStyle.primary, emoji="✍️")
    async def edit_content(self, interaction: discord.Interaction, button: ui.Button):
        modal = EmbedEditModal(self.message.embeds[0])
        await interaction.response.send_modal(modal)

    @ui.button(label="색상 변경", style=discord.ButtonStyle.secondary, emoji="🎨")
    async def edit_color(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_message("16진수 색상 코드를 입력해주세요 (예: #FF0000).", ephemeral=True)
        try:
            msg = await interaction.client.wait_for('message', timeout=60.0, check=lambda m: m.author == interaction.user and m.channel == interaction.channel)
            color_str = msg.content.replace("#", "")
            color_int = int(color_str, 16)
            new_embed = self.message.embeds[0]
            new_embed.color = discord.Color(color_int)
            await self.message.edit(embed=new_embed)
            await interaction.followup.send("✅ 색상이 변경되었습니다.", ephemeral=True)
            await msg.delete() # 사용자가 입력한 메시지 삭제
        except asyncio.TimeoutError:
            await interaction.followup.send("시간이 초과되었습니다.", ephemeral=True)
        except (ValueError, TypeError):
            await interaction.followup.send("올바르지 않은 색상 코드입니다.", ephemeral=True)

    @ui.button(label="DB에 저장", style=discord.ButtonStyle.success, emoji="💾")
    async def save_to_db(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True)
        current_embed = self.message.embeds[0]
        # discord.Embed 객체를 DB에 저장하기 쉬운 dict 형태로 변환
        embed_data = current_embed.to_dict()
        await save_embed_to_db(self.embed_key, embed_data)
        await interaction.followup.send(f"✅ 임베드가 데이터베이스에 키 '{self.embed_key}'(으)로 저장되었습니다.", ephemeral=True)

    @ui.button(label="편집기 삭제", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_editor(self, interaction: discord.Interaction, button: ui.Button):
        await self.message.delete()
        await interaction.response.send_message("편집기를 삭제했습니다.", ephemeral=True)
        self.stop()

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

    # ----------------------------------------------------------------------------
    # 명령어 그룹
    # ----------------------------------------------------------------------------
    
    # [삭제] counter_group: 명령어 목록에서 숨기기 위해 주석 처리 또는 삭제
    # counter_group = app_commands.Group(name="counter", ...)
    # @counter_group.command(...)

    # [삭제] autorole_group: 정적 방식으로 변경되었으므로 명령어 삭제
    # autorole_group = app_commands.Group(name="autorole", ...)
    # @autorole_group.command(...)

    # [변경] 새로운 'system' 명령어 그룹
    system_group = app_commands.Group(name="system", description="봇의 시스템 기능을 설정합니다.")

    @system_group.command(name="setup-panels", description="[관리자] 코드에 정의된 자동 역할 패널을 생성/업데이트합니다.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_static_panels(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not guild: return

        for panel_key, panel_config in STATIC_AUTO_ROLE_PANELS.items():
            channel_key = panel_config['channel_key']
            channel_id = await get_channel_id_from_db(channel_key)
            if not channel_id or not (channel := guild.get_channel(channel_id)):
                await interaction.followup.send(f"⚠️ `{panel_key}` 패널을 위한 채널(`{channel_key}`)을 찾을 수 없습니다. 건너뜁니다.", ephemeral=True)
                continue

            # 버튼 설정 생성
            buttons_config_for_view = []
            for btn in panel_config['buttons']:
                role_id = get_role_id(btn['role_id_key'])
                if not role_id:
                    logger.warning(f"역할 키 '{btn['role_id_key']}'에 해당하는 ID를 찾을 수 없습니다.")
                    continue
                buttons_config_for_view.append({
                    'role_id': role_id,
                    'button_label': btn['label'],
                    'button_emoji': btn.get('emoji'),
                    'button_style': btn.get('style', 'secondary')
                })
            
            view = AutoRoleView(buttons_config_for_view)
            embed_info = panel_config['embed']
            embed = discord.Embed(
                title=embed_info['title'],
                description=embed_info['description'],
                color=embed_info.get('color', 0x5865F2)
            )

            # 기존 메시지가 있는지 확인하고 업데이트, 없으면 새로 생성
            panel_message_id = await get_panel_id(panel_key)
            if panel_message_id:
                try:
                    message = await channel.fetch_message(panel_message_id)
                    await message.edit(embed=embed, view=view)
                    await interaction.followup.send(f"✅ `{panel_key}` 패널을 업데이트했습니다.", ephemeral=True)
                except discord.NotFound:
                    panel_message_id = None # 메시지를 찾을 수 없으면 새로 생성하도록 유도

            if not panel_message_id:
                message = await channel.send(embed=embed, view=view)
                await save_panel_id(panel_key, message.id) # DB에 패널 이름과 메시지 ID 저장
                # DB에 패널과 버튼 정보를 저장 (봇 재시작 시 View 복구를 위함)
                await add_auto_role_panel(message.id, guild.id, channel.id, embed.title, embed.description)
                for btn_conf in buttons_config_for_view:
                    await add_auto_role_button(message.id, btn_conf['role_id'], btn_conf['button_label'], btn_conf['button_emoji'], btn_conf['button_style'])
                
                await interaction.followup.send(f"✅ `{panel_key}` 패널을 생성했습니다.", ephemeral=True)

    # [추가] embed 명령어 그룹
    embed_group = app_commands.Group(name="embed", description="DB에 저장될 임베드를 관리합니다.")

    @embed_group.command(name="create", description="[관리자] 임베드 편집기를 생성합니다.")
    @app_commands.describe(channel="편집기를 생성할 채널", embed_key="DB에 저장될 임베드의 고유 키 (예: welcome_embed)")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def create_embed_editor(self, interaction: discord.Interaction, channel: discord.TextChannel, embed_key: str):
        await interaction.response.defer(ephemeral=True)
        
        # DB에서 기존 임베드를 불러오거나, 없으면 기본 임베드 생성
        embed_data = await get_embed_from_db(embed_key)
        if embed_data:
            embed = discord.Embed.from_dict(embed_data)
        else:
            embed = discord.Embed(
                title="임베드 제목",
                description="이곳에 설명을 입력하세요.\n\n"
                            "환영/작별 메시지에서는 다음 변수를 사용할 수 있습니다:\n"
                            "`{member_mention}`: 유저 멘션\n"
                            "`{member_name}`: 유저 이름\n"
                            "`{guild_name}`: 서버 이름",
                color=0x7289da
            )
        
        editor_message = await channel.send(content=f"**임베드 편집기: `{embed_key}`**", embed=embed)
        view = EmbedEditorView(editor_message, embed_key)
        await editor_message.edit(view=view)
        await interaction.followup.send(f"`{channel.mention}` 채널에 임베드 편집기를 생성했습니다.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))
