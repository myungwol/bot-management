# cogs/server/system.py (IndentationError 수정 및 자동 재생성 최종본)

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
    save_panel_id, get_panel_id, delete_auto_role_panel,
    add_auto_role_panel,
    delete_all_buttons_for_panel, bulk_add_auto_role_buttons,
    save_embed_to_db, get_embed_from_db,
    save_channel_id_to_db # 채널 설정 명령어를 위해 추가
)

# --- 코드 기반 패널 데이터 구조 ---
STATIC_AUTO_ROLE_PANELS = {
    "main_roles": {
        "channel_key": "auto_role_channel_id", "embed": {"title": "📜 역할 선택", "description": "아래 버튼으로 원하는 카테고리의 역할을 선택하세요!", "color": 0x5865F2},
        "categories": [{"id": "notifications", "label": "알림 역할 받기", "emoji": "📢"}, {"id": "games", "label": "게임 역할 받기", "emoji": "🎮"}],
        "roles": {
            "notifications": [{"role_id_key": "mention_role_1", "label": "서버 전체 공지", "description": "서버의 중요 업데이트 알림을 받습니다."}],
            "games": []
        }
    }
}

# --- View / Modal 정의 ---
class EphemeralRoleSelectView(ui.View):
    def __init__(self, member: discord.Member, category_roles: list, all_category_role_ids: set[int]):
        super().__init__(timeout=180)
        self.member = member; self.all_category_role_ids = all_category_role_ids
        current_user_role_ids = {r.id for r in self.member.roles}
        options = [discord.SelectOption(label=info['label'], value=str(rid), description=info.get('description'), default=(rid in current_user_role_ids)) for info in category_roles if (rid := get_role_id(info['role_id_key']))]
        self.role_select = ui.Select(placeholder="받고 싶은 역할을 모두 선택하세요...", min_values=0, max_values=len(options) or 1, options=options)
        self.role_select.callback = self.select_callback; self.add_item(self.role_select)
    async def select_callback(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        selected_ids = {int(rid) for rid in self.role_select.values}
        current_ids = {r.id for r in i.user.roles}
        to_add_ids = selected_ids - current_ids
        to_remove_ids = (self.all_category_role_ids - selected_ids) & current_ids
        try:
            if to_add := [i.guild.get_role(rid) for rid in to_add_ids if i.guild.get_role(rid)]: await i.user.add_roles(*to_add)
            if to_remove := [i.guild.get_role(rid) for rid in to_remove_ids if i.guild.get_role(rid)]: await i.user.remove_roles(*to_remove)
            self.role_select.disabled = True
            await i.edit_original_response(content="✅ 역할이 성공적으로 업데이트되었습니다.", view=self); self.stop()
        except Exception as e: logger.error(f"드롭다운 역할 처리 오류: {e}"); await i.followup.send("❌ 오류 발생.", ephemeral=True)

class AutoRoleView(ui.View):
    def __init__(self, panel_config: dict):
        super().__init__(timeout=None); self.panel_config = panel_config
        for category in self.panel_config.get("categories", []):
            button = ui.Button(label=category['label'], emoji=category.get('emoji'), style=discord.ButtonStyle.secondary, custom_id=f"category_select:{category['id']}")
            button.callback = self.category_button_callback; self.add_item(button)
    async def category_button_callback(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True); category_id = i.data['custom_id'].split(':')[1]
        category_roles = self.panel_config.get("roles", {}).get(category_id, [])
        if not category_roles: return await i.followup.send("선택한 카테고리에 설정된 역할이 없습니다.", ephemeral=True)
        all_ids = {get_role_id(r['role_id_key']) for r in category_roles if get_role_id(r['role_id_key'])}
        embed = discord.Embed(title=f"'{category_id.capitalize()}' 역할 선택", description="아래 드롭다운에서 원하는 역할을 모두 선택하세요.", color=discord.Color.blue())
        await i.followup.send(embed=embed, view=EphemeralRoleSelectView(i.user, category_roles, all_ids), ephemeral=True)

class EmbedEditModal(ui.Modal, title="임베드 내용 편집"):
    def __init__(self, embed: discord.Embed):
        super().__init__()
        self.embed = embed
        self.embed_title = ui.TextInput(label="제목", default=embed.title, required=False, max_length=256)
        self.embed_description = ui.TextInput(label="설명 (\\n = 줄바꿈)", style=discord.TextStyle.paragraph, default=embed.description, required=False, max_length=4000)
        self.add_item(self.embed_title); self.add_item(self.embed_description)
    async def on_submit(self, i: discord.Interaction):
        self.embed.title = self.embed_title.value; self.embed.description = self.embed_description.value.replace('\\n', '\n')
        await i.response.edit_message(embed=self.embed)

class EmbedEditorView(ui.View):
    def __init__(self, msg: discord.Message, key: str):
        super().__init__(timeout=None)
        self.message = msg; self.embed_key = key
    @ui.button(label="제목/설명 수정", emoji="✍️")
    async def edit_content(self, i: discord.Interaction, b: ui.Button): await i.response.send_modal(EmbedEditModal(self.message.embeds[0]))
    @ui.button(label="DB에 저장", style=discord.ButtonStyle.success, emoji="💾")
    async def save_to_db(self, i: discord.Interaction, b: ui.Button):
        await i.response.defer(ephemeral=True); await save_embed_to_db(self.embed_key, self.message.embeds[0].to_dict())
        await i.followup.send(f"✅ DB에 '{self.embed_key}'로 저장됨.", ephemeral=True)
    @ui.button(label="편집기 삭제", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_editor(self, i: discord.Interaction, b: ui.Button): await self.message.delete(); self.stop()

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

    # [수정] main.py가 호출할 자동 패널 재생성 함수 (올바른 들여쓰기 적용)
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

    # ... (카운터, 이벤트 리스너 함수들은 이전과 동일) ...
    
    setup_group = app_commands.Group(name="setup", description="[관리자] 봇의 주요 기능을 설정합니다.")

    @setup_group.command(name="set-channel", description="봇 기능에 필요한 채널을 등록합니다.")
    @app_commands.describe(key="채널 고유 키 (예: auto_role_channel_id)", channel="등록할 채널")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_channel(self, interaction: discord.Interaction, key: str, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True)
        await save_channel_id_to_db(key, channel.id)
        await interaction.followup.send(f"✅ 채널 설정 완료: `{key}` 키가 `{channel.mention}` 채널로 등록되었습니다.", ephemeral=True)
        
    @setup_group.command(name="panels", description="코드에 정의된 역할 패널을 생성/업데이트합니다.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_panels(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if not interaction.guild: return
        await self.regenerate_panel() # 자동 재생성 함수를 그대로 호출
        await interaction.followup.send("✅ 역할 패널 배포 작업이 완료되었습니다.", ephemeral=True)

    # ... (welcome-message, farewell-message 명령어는 이전과 동일) ...

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))
