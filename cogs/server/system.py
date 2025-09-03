# cogs/server/system.py
import discord
from discord.ext import commands
from discord import app_commands, ui
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
import asyncio
import time

# [✅✅✅ 핵심 수정 ✅✅✅]
# 게임 봇 전용 함수(update_wallet)를 import 목록에서 제거합니다.
from utils.database import (
    get_config, save_id_to_db, save_config_to_db, get_id,
    get_all_stats_channels, add_stats_channel, remove_stats_channel,
    _channel_id_cache,
    supabase,
    get_all_embeds, get_embed_from_db, save_embed_to_db
)
from utils.helpers import calculate_xp_for_level
from utils.ui_defaults import (
    UI_ROLE_KEY_MAP, SETUP_COMMAND_MAP, ADMIN_ROLE_KEYS, 
    ADMIN_ACTION_MAP, UI_STRINGS, JOB_ADVANCEMENT_DATA, PROFILE_RANK_ROLES,
    USABLE_ITEMS, WARNING_THRESHOLDS
)

logger = logging.getLogger(__name__)

async def is_admin(interaction: discord.Interaction) -> bool:
    if not isinstance(interaction.user, discord.Member): return False
    admin_role_ids = {get_id(key) for key in ADMIN_ROLE_KEYS if get_id(key)}
    user_role_ids = {role.id for role in interaction.user.roles}
    if not user_role_ids.intersection(admin_role_ids):
        if interaction.user.id == interaction.guild.owner_id: return True
        raise app_commands.CheckFailure("이 명령어를 실행할 관리자 권한이 없습니다.")
    return True

class TemplateEditModal(ui.Modal, title="임베드 템플릿 편집"):
    title_input = ui.TextInput(label="제목", placeholder="임베드 제목을 입력하세요.", required=False, max_length=256)
    description_input = ui.TextInput(label="설명", placeholder="임베드 설명을 입력하세요.", style=discord.TextStyle.paragraph, required=False, max_length=4000)
    color_input = ui.TextInput(label="색상 (16진수 코드)", placeholder="예: #5865F2 (비워두면 기본 색상)", required=False, max_length=7)
    image_url_input = ui.TextInput(label="이미지 URL", placeholder="임베드에 표시할 이미지 URL을 입력하세요.", required=False)
    thumbnail_url_input = ui.TextInput(label="썸네일 URL", placeholder="오른쪽 상단에 표시할 썸네일 이미지 URL을 입력하세요.", required=False)

    def __init__(self, existing_embed: discord.Embed):
        super().__init__()
        self.embed: Optional[discord.Embed] = None
        self.title_input.default = existing_embed.title
        self.description_input.default = existing_embed.description
        if existing_embed.color: self.color_input.default = str(existing_embed.color)
        if existing_embed.image and existing_embed.image.url: self.image_url_input.default = existing_embed.image.url
        if existing_embed.thumbnail and existing_embed.thumbnail.url: self.thumbnail_url_input.default = existing_embed.thumbnail.url

    async def on_submit(self, interaction: discord.Interaction):
        if not self.title_input.value and not self.description_input.value and not self.image_url_input.value:
            return await interaction.response.send_message("❌ 제목, 설명, 이미지 URL 중 하나는 반드시 입력해야 합니다.", ephemeral=True)
        try:
            color = discord.Color.default()
            if self.color_input.value: color = discord.Color(int(self.color_input.value.replace("#", ""), 16))
            embed = discord.Embed(title=self.title_input.value or None, description=self.description_input.value or None, color=color)
            if self.image_url_input.value: embed.set_image(url=self.image_url_input.value)
            if self.thumbnail_url_input.value: embed.set_thumbnail(url=self.thumbnail_url_input.value)
            self.embed = embed
            await interaction.response.defer(ephemeral=True)
        except Exception:
            await interaction.response.send_message("❌ 임베드를 만드는 중 오류가 발생했습니다.", ephemeral=True)

class EmbedTemplateSelectView(ui.View):
    def __init__(self, all_embeds: List[Dict[str, Any]]):
        super().__init__(timeout=300)
        self.all_embeds = {e['embed_key']: e['embed_data'] for e in all_embeds}
        options = [discord.SelectOption(label=key, description=data.get('title', '제목 없음')[:100]) for key, data in self.all_embeds.items()]
        for i in range(0, len(options), 25):
            select = ui.Select(placeholder=f"편집할 임베드 템플릿을 선택하세요... ({i//25 + 1})", options=options[i:i+25])
            select.callback = self.select_callback
            self.add_item(select)

    async def select_callback(self, interaction: discord.Interaction):
        embed_key = interaction.data['values'][0]
        embed_data = self.all_embeds.get(embed_key)
        if not embed_data: return await interaction.response.send_message("❌ 템플릿을 찾을 수 없습니다.", ephemeral=True)
        modal = TemplateEditModal(discord.Embed.from_dict(embed_data))
        await interaction.response.send_modal(modal)
        await modal.wait()
        if modal.embed:
            await save_embed_to_db(embed_key, modal.embed.to_dict())
            for item in self.children: item.disabled = True
            await interaction.edit_original_response(view=self)
            await interaction.followup.send(f"✅ 임베드 템플릿 `{embed_key}`가 성공적으로 업데이트되었습니다.\n`/admin setup`으로 관련 패널을 재설치하면 변경사항이 적용됩니다.", embed=modal.embed, ephemeral=True)

class ServerSystem(commands.Cog):
    admin_group = app_commands.Group(name="admin", description="서버 관리용 명령어입니다.", default_permissions=discord.Permissions(manage_guild=True))

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("System (통합 관리 명령어) Cog가 성공적으로 초기화되었습니다.")

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure): await interaction.response.send_message(f"❌ {error}", ephemeral=True)
        elif isinstance(error, app_commands.MissingPermissions): await interaction.response.send_message(f"❌ 이 명령어를 사용하려면 다음 권한이 필요합니다: `{', '.join(error.missing_permissions)}`", ephemeral=True)
        else:
            logger.error(f"'{interaction.command.qualified_name}' 명령어 처리 중 오류 발생: {error}", exc_info=True)
            if not interaction.response.is_done(): await interaction.response.send_message("❌ 명령어를 처리하는 중 예기치 않은 오류가 발생했습니다.", ephemeral=True)
            else: await interaction.followup.send("❌ 명령어를 처리하는 중 예기치 않은 오류가 발생했습니다.", ephemeral=True)

    @admin_group.command(name="purge", description="채널의 메시지를 삭제합니다. (별칭: clean)")
    @app_commands.rename(amount='개수', user='유저')
    @app_commands.describe(
        amount="삭제할 메시지의 개수를 입력하세요. (최대 100개)",
        user="특정 유저의 메시지만 삭제하려면 선택하세요."
    )
    @app_commands.check(is_admin)
    async def purge(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100], user: Optional[discord.Member] = None):
        await interaction.response.defer(ephemeral=True)
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.followup.send("❌ 이 명령어는 일반 텍스트 채널에서만 사용할 수 있습니다.", ephemeral=True)
            return

        try:
            check_func = lambda m: m.author == user if user else lambda m: True
            deleted_messages = await channel.purge(limit=amount, check=check_func)

            if user:
                response_message = f"✅ {user.mention}님의 메시지 {len(deleted_messages)}개를 삭제했습니다."
            else:
                response_message = f"✅ 메시지 {len(deleted_messages)}개를 삭제했습니다."
            
            if len(deleted_messages) < amount:
                response_message += "\nℹ️ 14일이 지난 메시지는 삭제할 수 없습니다."

            await interaction.followup.send(response_message, ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send("❌ 봇에게 '메시지 관리' 권한이 없습니다. 서버 설정에서 권한을 확인해주세요.", ephemeral=True)
        except Exception as e:
            logger.error(f"메시지 삭제 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send("❌ 메시지를 삭제하는 중 오류가 발생했습니다.", ephemeral=True)

    async def setup_action_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        choices = []
        for key, name in ADMIN_ACTION_MAP.items():
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=key))
        
        for key, info in SETUP_COMMAND_MAP.items():
            prefix = "[패널]" if info.get("type") == "panel" else "[채널]"
            choice_name = f"{prefix} {info.get('friendly_name', key)} 설정"
            if current.lower() in choice_name.lower():
                choices.append(app_commands.Choice(name=choice_name, value=f"channel_setup:{key}"))
        
        role_setup_actions = {"role_setup:bump_reminder_role_id": "[알림] Disboard BUMP 알림 역할 설정", "role_setup:dissoku_reminder_role_id": "[알림] Dissoku UP 알림 역할 설정"}
        for key, name in role_setup_actions.items():
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=key))
        
        return sorted(choices, key=lambda c: c.name)[:25]

    @admin_group.command(name="setup", description="봇의 모든 설정을 관리합니다.")
    @app_commands.describe(action="실행할 작업을 선택하세요.", channel="[채널/통계] 작업에 필요한 채널을 선택하세요.", role="[역할/통계] 작업에 필요한 역할을 선택하세요.", user="[코인/XP/레벨] 대상을 지정하세요.", amount="[코인/XP] 지급 또는 차감할 수량을 입력하세요.", level="[레벨] 설정할 레벨을 입력하세요.", stat_type="[통계] 표시할 통계 유형을 선택하세요.", template="[통계] 채널 이름 형식을 지정하세요. (예: 👤 유저: {count}명)")
    @app_commands.autocomplete(action=setup_action_autocomplete)
    @app_commands.choices(stat_type=[app_commands.Choice(name="[설정] 전체 멤버 수 (봇 포함)", value="total"), app_commands.Choice(name="[설정] 유저 수 (봇 제외)", value="humans"), app_commands.Choice(name="[설정] 봇 수", value="bots"), app_commands.Choice(name="[설정] 서버 부스트 수", value="boosters"), app_commands.Choice(name="[설정] 특정 역할 멤버 수", value="role"), app_commands.Choice(name="[삭제] 이 채널의 통계 설정 삭제", value="remove")])
    @app_commands.check(is_admin)
    async def setup(self, interaction: discord.Interaction, action: str, channel: Optional[discord.TextChannel | discord.VoiceChannel | discord.ForumChannel] = None, role: Optional[discord.Role] = None, user: Optional[discord.Member] = None, amount: Optional[app_commands.Range[int, 1, None]] = None, level: Optional[app_commands.Range[int, 1, None]] = None, stat_type: Optional[str] = None, template: Optional[str] = None):
        await interaction.response.defer(ephemeral=True)

        if action == "strings_sync":
            try:
                await save_config_to_db("strings", UI_STRINGS)
                await save_config_to_db("JOB_ADVANCEMENT_DATA", JOB_ADVANCEMENT_DATA)
                await save_config_to_db("PROFILE_RANK_ROLES", PROFILE_RANK_ROLES)
                await save_config_to_db("USABLE_ITEMS", USABLE_ITEMS)
                await save_config_to_db("WARNING_THRESHOLDS", WARNING_THRESHOLDS)
                await save_config_to_db("config_reload_request", time.time())
                logger.info("UI 텍스트 및 게임 관련 주요 설정이 데이터베이스에 성공적으로 동기화되었습니다.")
                await interaction.followup.send("✅ UI 텍스트와 게임 데이터를 데이터베이스에 성공적으로 동기화했습니다.\n"
                                                "**게임 봇을 재시작**하면 모든 설정이 정상적으로 적용됩니다.")
            except Exception as e:
                logger.error(f"UI 동기화 중 오류: {e}", exc_info=True)
                await interaction.followup.send("❌ UI 동기화 중 오류가 발생했습니다.")
            return

        elif action == 'eventpass_enable':
            await save_config_to_db('event_priority_pass_active', True)
            await save_config_to_db('event_priority_pass_users', [])
            await save_config_to_db("config_reload_request", time.time())
            await interaction.followup.send("✅ **이벤트 우선 참여권** 사용을 **활성화**했습니다.\n이제 유저들이 아이템을 사용할 수 있습니다.")
            return
        
        elif action == 'eventpass_disable':
            await save_config_to_db('event_priority_pass_active', False)
            await save_config_to_db("config_reload_request", time.time())
            await interaction.followup.send("✅ **이벤트 우선 참여권** 사용을 **비활성화**했습니다.")
            return

        if action.startswith("channel_setup:"):
            setting_key = action.split(":", 1)[1]
            config = SETUP_COMMAND_MAP.get(setting_key)
            if not config:
                return await interaction.followup.send(f"❌ 유효하지 않은 설정 키입니다: {setting_key}", ephemeral=True)
            
            required_channel_type = config.get("channel_type", "text")
            error_msg = None
            if not channel:
                error_msg = f"❌ 이 작업을 실행하려면 `channel` 옵션에 **{required_channel_type} 채널**을 지정해야 합니다."
            elif (required_channel_type == "text" and not isinstance(channel, discord.TextChannel)) or \
                 (required_channel_type == "voice" and not isinstance(channel, discord.VoiceChannel)) or \
                 (required_channel_type == "forum" and not isinstance(channel, discord.ForumChannel)):
                error_msg = f"❌ 이 작업에는 **{required_channel_type} 채널**이 필요합니다. 올바른 타입의 채널을 선택해주세요."
            
            if error_msg:
                return await interaction.followup.send(error_msg, ephemeral=True)

            db_key, friendly_name = config['key'], config['friendly_name']
            
            save_success = await save_id_to_db(db_key, channel.id)
            if not save_success:
                return await interaction.followup.send(f"❌ **{friendly_name}** 설정 중 DB 저장에 실패했습니다.", ephemeral=True)

            if (cog_to_reload := self.bot.get_cog(config["cog_name"])) and hasattr(cog_to_reload, 'load_configs'):
                await cog_to_reload.load_configs()
            
            await interaction.followup.send(f"✅ **{friendly_name}**을(를) `{channel.mention}` 채널로 설정했습니다.", ephemeral=True)
            return
        
        if action == "game_data_reload":
            try:
                await save_config_to_db("game_data_reload_request", time.time())
                logger.info("게임 데이터 새로고침 요청을 DB에 저장했습니다.")
                await interaction.followup.send("✅ 게임 봇에게 게임 데이터(아이템, 낚시 확률 등)를 새로고침하도록 요청했습니다.\n"
                                                "약 10초 내에 변경사항이 적용됩니다.")
            except Exception as e:
                logger.error(f"게임 데이터 새로고침 요청 중 오류: {e}", exc_info=True)
                await interaction.followup.send("❌ 게임 데이터 새로고침 요청 중 오류가 발생했습니다.")
            return

        if action == "status_show":
            embed = discord.Embed(title="⚙️ 서버 설정 현황 대시보드", color=0x3498DB)
            embed.set_footer(text=f"최종 확인: {discord.utils.format_dt(discord.utils.utcnow(), style='F')}")
            channel_lines = []
            for key, info in sorted(SETUP_COMMAND_MAP.items(), key=lambda item: item[1]['friendly_name']):
                channel_id = _channel_id_cache.get(info['key'])
                status_emoji = "✅" if channel_id else "❌"
                channel_mention = f"<#{channel_id}>" if channel_id else "미설정"
                channel_lines.append(f"{status_emoji} **{info['friendly_name']}**: {channel_mention}")
            full_channel_text = "\n".join(channel_lines)
            for i in range(0, len(full_channel_text), 1024):
                chunk = full_channel_text[i:i+1024]
                field_name = "채널 설정" if i == 0 else "채널 설정 (계속)"
                embed.add_field(name=f"**{field_name}**", value=chunk, inline=False)
            role_lines = []
            for key, info in sorted(UI_ROLE_KEY_MAP.items(), key=lambda item: item[1]['priority'], reverse=True):
                if info.get('priority', 0) > 0:
                    role_id = _channel_id_cache.get(key)
                    status_emoji = "✅" if role_id else "❌"
                    role_mention = f"<@&{role_id}>" if role_id else f"`{info['name']}` (미설정)"
                    role_lines.append(f"{status_emoji} **{info['name']}**: {role_mention if role_id else '미설정'}")
            if role_lines: embed.add_field(name="**주요 역할 설정**", value="\n".join(role_lines)[:1024], inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
        elif action == "server_id_set":
            server_id = interaction.guild.id
            try:
                await save_config_to_db("SERVER_ID", str(server_id))
                logger.info(f"서버 ID가 {server_id}(으)로 성공적으로 설정되었습니다. (요청자: {interaction.user.name})")
                await interaction.followup.send(f"✅ 이 서버의 ID (`{server_id}`)를 봇의 핵심 설정으로 저장했습니다.\n이제 게임 봇이 관리자 명령어를 올바르게 처리할 수 있습니다.")
            except Exception as e:
                logger.error(f"서버 ID 저장 중 오류 발생: {e}", exc_info=True)
                await interaction.followup.send("❌ 서버 ID를 데이터베이스에 저장하는 중 오류가 발생했습니다.")
        
        # [✅✅✅ 핵심 수정 ✅✅✅]
        # 코인/XP/레벨 관련 명령어는 직접 DB를 수정하는 대신, 게임 봇에게 요청을 보냅니다.
        elif action in ["coin_give", "coin_take", "xp_give", "level_set"]:
            if not user: return await interaction.followup.send("❌ 이 작업을 수행하려면 `user` 옵션이 필요합니다.", ephemeral=True)
            if action == "coin_give":
                if not amount: return await interaction.followup.send("❌ `amount` 옵션이 필요합니다.", ephemeral=True)
                await save_config_to_db(f"coin_admin_update_request_{user.id}", {"amount": amount, "timestamp": time.time()})
                await interaction.followup.send(f"✅ {user.mention}님에게 코인 `{amount}`를 지급하도록 게임 봇에게 요청했습니다.")
            elif action == "coin_take":
                if not amount: return await interaction.followup.send("❌ `amount` 옵션이 필요합니다.", ephemeral=True)
                await save_config_to_db(f"coin_admin_update_request_{user.id}", {"amount": -amount, "timestamp": time.time()})
                await interaction.followup.send(f"✅ {user.mention}님의 코인 `{amount}`를 차감하도록 게임 봇에게 요청했습니다.")
            elif action == "xp_give":
                if not amount: return await interaction.followup.send("❌ `amount` 옵션이 필요합니다.", ephemeral=True)
                await save_config_to_db(f"xp_admin_update_request_{user.id}", {"xp_to_add": amount, "timestamp": time.time()})
                await interaction.followup.send(f"✅ {user.mention}님에게 XP `{amount}`를 부여하도록 게임 봇에게 요청했습니다.")
            elif action == "level_set":
                if not level: return await interaction.followup.send("❌ `level` 옵션이 필요합니다.", ephemeral=True)
                await save_config_to_db(f"xp_admin_update_request_{user.id}", {"exact_level": level, "timestamp": time.time()})
                await interaction.followup.send(f"✅ {user.mention}님의 레벨을 **{level}**로 설정하도록 게임 봇에게 요청했습니다.")

        elif action == "template_edit":
            all_embeds = await get_all_embeds()
            if not all_embeds: return await interaction.followup.send("❌ DB에 편집 가능한 임베드 템플릿이 없습니다.", ephemeral=True)
            view = EmbedTemplateSelectView(all_embeds)
            await interaction.followup.send("편집하고 싶은 임베드 템플릿을 아래 메뉴에서 선택해주세요.", view=view, ephemeral=True)

        elif action == "request_regenerate_all_game_panels":
            game_panel_keys = [key for key, info in SETUP_COMMAND_MAP.items() if "[게임]" in info.get("friendly_name", "")]
            if not game_panel_keys:
                return await interaction.followup.send("❌ 설정 파일에서 게임 패널을 찾을 수 없습니다.", ephemeral=True)
            
            timestamp = datetime.now(timezone.utc).timestamp()
            tasks = []
            for panel_key in game_panel_keys:
                db_key = f"panel_regenerate_request_{panel_key}"
                tasks.append(save_config_to_db(db_key, timestamp))
            
            await asyncio.gather(*tasks)
            
            return await interaction.followup.send(
                f"✅ {len(game_panel_keys)}개의 게임 패널에 대해 일괄 재설치를 요청했습니다.\n"
                "게임 봇이 온라인 상태라면 약 10초 내에 패널이 업데이트됩니다.",
                ephemeral=True
            )

        elif action.startswith("role_setup:"):
            db_key = action.split(":", 1)[1]
            if not role:
                return await interaction.followup.send("❌ 이 작업을 실행하려면 `role` 옵션에 역할을 지정해야 합니다.", ephemeral=True)
            
            friendly_name = "알림 역할"
            for choice in await self.setup_action_autocomplete(interaction, ""):
                if choice.value == action:
                    friendly_name = choice.name.replace(" 설정", "")
            
            save_success = await save_id_to_db(db_key, role.id)
            if not save_success:
                 return await interaction.followup.send(f"❌ **{friendly_name}** 설정 중 DB 저장에 실패했습니다. Supabase RLS 정책을 확인해주세요.", ephemeral=True)

            cog_to_reload = self.bot.get_cog("Reminder")
            if cog_to_reload and hasattr(cog_to_reload, 'load_configs'):
                await cog_to_reload.load_configs()
            
            await interaction.followup.send(f"✅ **{friendly_name}**을(를) `{role.mention}` 역할로 설정했습니다.", ephemeral=True)

        elif action == "panels_regenerate_all":
            setup_map = get_config("SETUP_COMMAND_MAP", {})
            success_list, failure_list = [], []

            await interaction.followup.send("⏳ 모든 패널의 재설치를 시작합니다...", ephemeral=True)

            for key, info in setup_map.items():
                if info.get("type") == "panel":
                    friendly_name = info.get("friendly_name", key)
                    try:
                        cog_name, channel_db_key = info.get("cog_name"), info.get("key")
                        if not all([cog_name, channel_db_key]):
                            failure_list.append(f"・`{friendly_name}`: 설정 정보가 불완전합니다.")
                            continue

                        is_game_panel = "[게임]" in friendly_name
                        if is_game_panel:
                            timestamp = datetime.now(timezone.utc).timestamp()
                            await save_config_to_db(f"panel_regenerate_request_{key}", timestamp)
                            success_list.append(f"・`{friendly_name}`: 게임 봇에게 재설치를 요청했습니다.")
                            continue

                        cog = self.bot.get_cog(cog_name)
                        if not cog or not hasattr(cog, 'regenerate_panel'):
                            failure_list.append(f"・`{friendly_name}`: Cog를 찾을 수 없거나 재설치 기능이 없습니다.")
                            continue
                        channel_id = get_id(channel_db_key)
                        if not channel_id or not (target_channel := self.bot.get_channel(channel_id)):
                            failure_list.append(f"・`{friendly_name}`: 채널이 설정되지 않았거나 찾을 수 없습니다.")
                            continue
                        
                        success = False
                        if cog_name == "TicketSystem":
                            panel_type = key.replace("panel_", "")
                            success = await cog.regenerate_panel(target_channel, panel_type=panel_type)
                        else:
                            success = await cog.regenerate_panel(target_channel, panel_key=key)
                        
                        if success: success_list.append(f"・`{friendly_name}` → <#{target_channel.id}>")
                        else: failure_list.append(f"・`{friendly_name}`: 재설치 중 알 수 없는 오류가 발생했습니다.")

                    except Exception as e:
                        logger.error(f"'{friendly_name}' 패널 일괄 재설치 중 오류: {e}", exc_info=True)
                        failure_list.append(f"・`{friendly_name}`: 스크립트 오류 발생.")

            embed = discord.Embed(title="⚙️ 모든 패널 재설치 결과", color=0x3498DB, timestamp=discord.utils.utcnow())
            if success_list: embed.add_field(name="✅ 성공/요청", value="\n".join(success_list), inline=False)
            if failure_list:
                embed.color = 0xED4245
                embed.add_field(name="❌ 실패", value="\n".join(failure_list), inline=False)
            
            await interaction.edit_original_response(content="모든 패널 재설치가 완료되었습니다.", embed=embed)

        elif action == "roles_sync":
            role_name_map = {key: info["name"] for key, info in UI_ROLE_KEY_MAP.items()}
            await save_config_to_db("ROLE_KEY_MAP", role_name_map)
            
            synced_roles, missing_roles, error_roles = [], [], []
            server_roles_by_name = {r.name: r.id for r in interaction.guild.roles}
            
            for db_key, role_info in UI_ROLE_KEY_MAP.items():
                if not (role_name := role_info.get('name')): continue
                if role_id := server_roles_by_name.get(role_name):
                    if await save_id_to_db(db_key, role_id): synced_roles.append(f"・`{role_name}`")
                    else: error_roles.append(f"・`{role_name}`: DB 저장 실패")
                else: missing_roles.append(f"・`{role_name}`")
            
            embed = discord.Embed(title="⚙️ 역할 데이터베이스 전체 동기화 결과", color=0x2ECC71)
            embed.set_footer(text=f"총 {len(UI_ROLE_KEY_MAP)}개 중 | 성공: {len(synced_roles)} / 실패: {len(missing_roles) + len(error_roles)}")

            if synced_roles: embed.add_field(name=f"✅ 동기화 성공 ({len(synced_roles)}개)", value="\n".join(synced_roles)[:1024], inline=False)
            if missing_roles:
                embed.color = 0xFEE75C
                embed.add_field(name=f"⚠️ 서버에 해당 역할 없음 ({len(missing_roles)}개)", value="\n".join(missing_roles)[:1024], inline=False)
            if error_roles:
                embed.color = 0xED4245
                embed.add_field(name=f"❌ DB 저장 오류 ({len(error_roles)}개)", value="\n".join(error_roles)[:1024], inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)

        elif action == "stats_set":
            if not channel or not isinstance(channel, discord.VoiceChannel):
                return await interaction.followup.send("❌ 이 작업을 실행하려면 `channel` 옵션에 음성 채널을 지정해야 합니다.", ephemeral=True)
            if not stat_type:
                return await interaction.followup.send("❌ 이 작업을 실행하려면 `stat_type` 옵션을 선택해야 합니다.", ephemeral=True)
            
            if stat_type == "remove":
                await remove_stats_channel(channel.id)
                await interaction.followup.send(f"✅ `{channel.name}` 채널의 통계 설정을 삭제했습니다.", ephemeral=True)
            else:
                current_template = template or f"정보: {{count}}"
                if "{count}" not in current_template:
                    return await interaction.followup.send("❌ 이름 형식(`template`)에는 반드시 `{count}`를 포함해야 합니다.", ephemeral=True)
                if stat_type == "role" and not role:
                    return await interaction.followup.send("❌ '특정 역할 멤버 수'를 선택한 경우, `role` 옵션을 지정해야 합니다.", ephemeral=True)
                
                await add_stats_channel(channel.id, interaction.guild_id, stat_type, current_template, role.id if role else None)
                
                if (stats_cog := self.bot.get_cog("StatsUpdater")) and hasattr(stats_cog, 'update_stats_loop') and stats_cog.update_stats_loop.is_running():
                    stats_cog.update_stats_loop.restart()
                
                await interaction.followup.send(f"✅ `{channel.name}` 채널에 통계 설정을 추가/수정했습니다. 곧 업데이트됩니다.", ephemeral=True)

        elif action == "stats_refresh":
            if (stats_cog := self.bot.get_cog("StatsUpdater")) and hasattr(stats_cog, 'update_stats_loop') and stats_cog.update_stats_loop.is_running():
                stats_cog.update_stats_loop.restart()
                await interaction.followup.send("✅ 모든 통계 채널의 업데이트를 요청했습니다.", ephemeral=True)
            else:
                await interaction.followup.send("❌ 통계 업데이트 기능을 찾을 수 없거나, 실행 중이 아닙니다.", ephemeral=True)

        elif action == "stats_list":
            configs = await get_all_stats_channels()
            guild_configs = [c for c in configs if c.get('guild_id') == interaction.guild_id]
            if not guild_configs:
                return await interaction.followup.send("ℹ️ 설정된 통계 채널이 없습니다.", ephemeral=True)
            
            embed = discord.Embed(title="📊 설정된 통계 채널 목록", color=0x3498DB)
            description = []
            for config in guild_configs:
                ch_mention = f"<#{config['channel_id']}>" if self.bot.get_channel(config['channel_id']) else f"삭제된 채널({config['channel_id']})"
                role_info = ""
                if config['stat_type'] == 'role' and config.get('role_id'):
                    role_obj = interaction.guild.get_role(config['role_id'])
                    role_info = f"\n**대상 역할:** {role_obj.mention if role_obj else '알 수 없는 역할'}"
                description.append(f"**채널:** {ch_mention}\n**종류:** `{config['stat_type']}`{role_info}\n**이름 형식:** `{config['channel_name_template']}`")
            
            embed.description = "\n\n".join(description)
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        else:
            await interaction.followup.send("❌ 알 수 없는 작업입니다. 목록에서 올바른 작업을 선택해주세요.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))
