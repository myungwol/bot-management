# cogs/server/system.py (단일 /setup 명령어 시스템 최종본)

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
    save_embed_to_db, get_embed_from_db,
    save_panel_id, get_panel_id,
    add_auto_role_panel, delete_auto_role_panel, # delete_auto_role_panel은 패널 삭제 시 필요
    add_auto_role_button, get_auto_role_buttons, remove_auto_role_button # remove는 현재 미사용
)

# ----------------------------------------------------------------------------
# [복구] 코드에서 역할 패널을 직접 정의하는 부분
# ----------------------------------------------------------------------------
STATIC_AUTO_ROLE_PANELS = {
    "main_roles": {
        "channel_key": "auto_role_channel_id",
        "embed": {
            "title": "📜 역할 선택 패널",
            "description": "아래 버튼을 눌러 원하시는 역할을 받거나 해제하세요!",
            "color": 0x5865F2
        },
        "buttons": [
            {"role_id_key": "mention_role_1", "label": "공지 알림", "emoji": "📢"},
        ]
    },
}

# ----------------------------------------------------------------------------
# View / Modal 정의
# ----------------------------------------------------------------------------

# 2단계 역할 부여를 위한 본인만 보이는 View
class EphemeralRoleGrantView(ui.View):
    def __init__(self, role: discord.Role, member: discord.Member):
        super().__init__(timeout=120)
        self.role = role
        self.member = member
        has_role = self.role in self.member.roles
        self.children[0].disabled = has_role
        self.children[1].disabled = not has_role
    async def handle_role(self, i: discord.Interaction, action: str):
        await i.response.defer()
        has_role = self.role in self.member.roles
        try:
            if action == 'add' and not has_role: await self.member.add_roles(self.role); await i.followup.send(f"✅ '{self.role.name}' 역할을 받았습니다.", ephemeral=True)
            elif action == 'remove' and has_role: await self.member.remove_roles(self.role); await i.followup.send(f"✅ '{self.role.name}' 역할을 해제했습니다.", ephemeral=True)
            else: await i.followup.send("ℹ️ 역할 상태에 변경사항이 없습니다.", ephemeral=True)
            for item in self.children: item.disabled = True
            await i.edit_original_response(view=self)
            self.stop()
        except Exception as e: logger.error(f"역할 처리 오류: {e}"); await i.followup.send("❌ 오류 발생.", ephemeral=True)
    @ui.button(label="역할 받기", style=discord.ButtonStyle.success, emoji="✅")
    async def grant_role(self, i: discord.Interaction, b: ui.Button): await self.handle_role(i, 'add')
    @ui.button(label="역할 해제", style=discord.ButtonStyle.danger, emoji="❌")
    async def remove_role(self, i: discord.Interaction, b: ui.Button): await self.handle_role(i, 'remove')
    @ui.button(label="닫기", style=discord.ButtonStyle.secondary, emoji="✖️")
    async def close_view(self, i: discord.Interaction, b: ui.Button): await i.message.delete(); self.stop()

# 공개 패널의 버튼을 담당하는 핵심 View
class AutoRoleView(ui.View):
    def __init__(self, buttons_config: list | None = None):
        super().__init__(timeout=None)
        if buttons_config:
            for config in buttons_config:
                button = ui.Button(label=config['button_label'], emoji=config.get('button_emoji'), style=discord.ButtonStyle.secondary, custom_id=f"auto_role:{config['role_id']}")
                button.callback = self.button_callback
                self.add_item(button)
    async def button_callback(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        role_id = int(i.data['custom_id'].split(':')[1])
        if not isinstance(i.user, discord.Member) or not i.guild or not (role := i.guild.get_role(role_id)): return
        embed = discord.Embed(title=f"'{role.name}' 역할 관리", description="아래 버튼으로 역할을 받거나 해제하세요.", color=role.color if role.color.value != 0 else discord.Color.blurple())
        embed.set_footer(text="이 창은 2분 뒤 사라집니다.")
        await i.followup.send(embed=embed, view=EphemeralRoleGrantView(role=role, member=i.user), ephemeral=True)

# 환영/작별 메시지 임베드 수정을 위한 Modal 및 View
class EmbedEditModal(ui.Modal, title="임베드 내용 편집"):
    def __init__(self, current_embed: discord.Embed):
        super().__init__()
        self.embed = current_embed
        self.embed_title = ui.TextInput(label="제목", default=current_embed.title, required=False, max_length=256)
        self.embed_description = ui.TextInput(label="설명 (\\n = 줄바꿈)", style=discord.TextStyle.paragraph, default=current_embed.description, required=False, max_length=4000)
        self.add_item(self.embed_title); self.add_item(self.embed_description)
    async def on_submit(self, i: discord.Interaction):
        self.embed.title = self.embed_title.value
        self.embed.description = self.embed_description.value.replace('\\n', '\n')
        await i.response.edit_message(embed=self.embed)

class EmbedEditorView(ui.View):
    def __init__(self, message: discord.Message, embed_key: str):
        super().__init__(timeout=None)
        self.message = message; self.embed_key = embed_key
    @ui.button(label="제목/설명 수정", style=discord.ButtonStyle.primary, emoji="✍️")
    async def edit_content(self, i: discord.Interaction, b: ui.Button): await i.response.send_modal(EmbedEditModal(self.message.embeds[0]))
    @ui.button(label="DB에 저장", style=discord.ButtonStyle.success, emoji="💾")
    async def save_to_db(self, i: discord.Interaction, b: ui.Button):
        await i.response.defer(ephemeral=True); await save_embed_to_db(self.embed_key, self.message.embeds[0].to_dict())
        await i.followup.send(f"✅ 임베드가 DB에 '{self.embed_key}' 키로 저장되었습니다.", ephemeral=True)
    @ui.button(label="편집기 삭제", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_editor(self, i: discord.Interaction, b: ui.Button): await self.message.delete(); self.stop()

# ----------------------------------------------------------------------------
# 메인 Cog 클래스
# ----------------------------------------------------------------------------
class ServerSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # ... (이하 모든 변수 선언은 이전과 동일)

    # --- [유지] Cog 생명주기, 카운터, 이벤트 리스너 ---
    # 이 부분의 코드는 변경이 없으므로, 이전 코드의 내용을 그대로 사용하시면 됩니다.
    # cog_load, cog_unload, load_all_configs, 카운터 함수들, on_member_join 등...

    # --- [통합] /setup 명령어 그룹 ---
    setup_group = app_commands.Group(name="setup", description="[관리자] 봇의 주요 기능을 설정합니다.")

    @setup_group.command(name="panels", description="코드에 정의된 모든 역할 패널을 생성/업데이트합니다.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_panels(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not guild: return

        successful_panels = []
        # DB에서 이전에 배포된 모든 패널의 메시지 ID를 가져옵니다.
        all_db_panels = {(await get_panel_id(key) or {}).get('message_id') for key in STATIC_AUTO_ROLE_PANELS.keys()}

        for panel_key, panel_config in STATIC_AUTO_ROLE_PANELS.items():
            channel_id = await get_channel_id_from_db(panel_config['channel_key'])
            if not channel_id or not (channel := guild.get_channel(channel_id)):
                logger.warning(f"패널 '{panel_key}' 배포 실패: 채널 키 '{panel_config['channel_key']}'를 찾을 수 없습니다.")
                continue

            embed = discord.Embed.from_dict(panel_config['embed'])
            buttons_for_view = [{'role_id': get_role_id(key), 'button_label': btn['label'], 'button_emoji': btn.get('emoji')} for key in (btn['role_id_key'] for btn in panel_config['buttons']) if get_role_id(key)]
            view = AutoRoleView(buttons_for_view)
            
            panel_message_id = (await get_panel_id(panel_key) or {}).get('message_id')
            live_message = None
            if panel_message_id:
                try: live_message = await channel.fetch_message(panel_message_id)
                except discord.NotFound: panel_message_id = None
            
            if live_message:
                await live_message.edit(embed=embed, view=view)
            else:
                live_message = await channel.send(embed=embed, view=view)
                await save_panel_id(panel_key, live_message.id, channel.id)
                await add_auto_role_panel(live_message.id, guild.id, channel.id, embed.title, embed.description)
                for btn in buttons_for_view:
                    await add_auto_role_button(live_message.id, btn['role_id'], btn['button_label'], btn['button_emoji'], 'secondary')
            
            successful_panels.append(f"'{panel_key}'")
            if live_message.id in all_db_panels:
                all_db_panels.remove(live_message.id)

        # 이제 코드에는 없지만 DB에는 남아있는 오래된 패널들을 삭제
        for old_msg_id in all_db_panels:
            await delete_auto_role_panel(old_msg_id) # 연관된 데이터 모두 삭제
        
        await interaction.followup.send(f"✅ 패널 배포 완료: {', '.join(successful_panels) if successful_panels else '없음'}", ephemeral=True)

    @setup_group.command(name="welcome-message", description="환영 메시지 편집기를 생성합니다.")
    @app_commands.describe(channel="편집기를 생성할 채널")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_welcome_message(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.create_message_editor(interaction, channel, 'welcome_embed', "환영 메시지")

    @setup_group.command(name="farewell-message", description="작별 메시지 편집기를 생성합니다.")
    @app_commands.describe(channel="편집기를 생성할 채널")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_farewell_message(self, interaction: discord.Interaction, channel: discord.TextChannel):
        await self.create_message_editor(interaction, channel, 'farewell_embed', "작별 메시지")

    async def create_message_editor(self, interaction: discord.Interaction, channel: discord.TextChannel, key: str, name: str):
        await interaction.response.defer(ephemeral=True)
        embed_data = await get_embed_from_db(key)
        if embed_data:
            embed = discord.Embed.from_dict(embed_data)
        else:
            embed = discord.Embed(title=f"{name} 제목", description=f"{name} 설명을 입력하세요.", color=0x7289da)
        
        editor_message = await channel.send(content=f"**{name} 편집기**", embed=embed)
        view = EmbedEditorView(editor_message, key)
        await editor_message.edit(view=view)
        await interaction.followup.send(f"`{channel.mention}` 채널에 {name} 편집기를 생성했습니다.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))
