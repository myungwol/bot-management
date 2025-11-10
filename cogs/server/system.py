# cogs/server/system.py

import discord
from discord.ext import commands
from discord import app_commands, ui
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta, date
import asyncio
import time
import json

from utils.database import (
    get_config, save_id_to_db, save_config_to_db, get_id,
    get_all_stats_channels, add_stats_channel, remove_stats_channel,
    _channel_id_cache,
    supabase,
    get_all_embeds, get_embed_from_db, save_embed_to_db,
    delete_config_from_db
)
from utils.helpers import calculate_xp_for_level
from utils.ui_defaults import (
    UI_ROLE_KEY_MAP, SETUP_COMMAND_MAP, ADMIN_ROLE_KEYS, 
    ADMIN_ACTION_MAP, UI_STRINGS, JOB_ADVANCEMENT_DATA, PROFILE_RANK_ROLES,
    USABLE_ITEMS, WARNING_THRESHOLDS, JOB_SYSTEM_CONFIG
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
        if isinstance(error, app_commands.CheckFailure): 
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ {error}", ephemeral=True)
        elif isinstance(error, app_commands.MissingPermissions): 
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ 이 명령어를 사용하려면 다음 권한이 필요합니다: `{', '.join(error.missing_permissions)}`", ephemeral=True)
        else:
            logger.error(f"'{interaction.command.qualified_name}' 명령어 처리 중 오류 발생: {error}", exc_info=True)
            if not interaction.response.is_done(): 
                await interaction.response.send_message("❌ 명령어를 처리하는 중 예기치 않은 오류가 발생했습니다.", ephemeral=True)
            else: 
                await interaction.followup.send("❌ 명령어를 처리하는 중 예기치 않은 오류가 발생했습니다.", ephemeral=True)

    @admin_group.command(name="check_roles", description="[진단용] 주요 역할의 코드-서버-DB 동기화 상태를 확인합니다.")
    @app_commands.check(is_admin)
    async def check_roles(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        role_keys_to_check = { "성별(남)": "role_info_male", "성별(여)": "role_info_female", "나이(10대)": "role_age_10s", "나이(20대)": "role_age_20s", "나이(30대)": "role_age_30s", }
        ui_role_map = get_config("UI_ROLE_KEY_MAP", {})
        results = []
        for name, key in role_keys_to_check.items():
            code_name = ui_role_map.get(key, {}).get("name", "정의되지 않음")
            server_role = discord.utils.get(interaction.guild.roles, name=code_name)
            server_status = f"✅ 발견 (ID: {server_role.id})" if server_role else "❌ 없음"
            db_id = get_id(key)
            db_status = f"✅ 저장됨 (ID: {db_id})" if db_id else "❌ 없음"
            status = "🔴 불일치"
            if server_role and db_id and server_role.id == db_id: status = "🟢 일치"
            elif not server_role and not db_id: status = "🟡 둘 다 없음"
            results.append(f"| {name.ljust(8)} | `{code_name}` | {server_status.ljust(15)} | {db_status.ljust(15)} | {status} |")
        
        header = "| 구분         | 코드에 정의된 이름              | 서버에서 발견        | DB에 저장됨          | 상태     |\n" + \
                 "|--------------|---------------------------------|----------------------|----------------------|----------|"
        
        description = "\n".join(results)
        embed = discord.Embed(
            title="[진단] 주요 역할 동기화 상태",
            description=f"```markdown\n{header}\n{description}\n```",
            color=discord.Color.gold(),
            timestamp=datetime.now(timezone.utc)
        )
        embed.set_footer(text="'상태'가 '🔴 불일치'인 경우, 역할 이름이 정확한지 확인 후 /admin setup의 roles_sync를 다시 실행하세요.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @admin_group.command(name="purge", description="채널의 메시지를 삭제합니다. (별칭: clean)")
    @app_commands.rename(amount='개수', user='유저')
    @app_commands.describe(amount="삭제할 메시지의 개수를 입력하세요. (최대 100개)", user="특정 유저의 메시지만 삭제하려면 선택하세요.")
    @app_commands.check(is_admin)
    async def purge(self, interaction: discord.Interaction, amount: app_commands.Range[int, 1, 100], user: Optional[discord.Member] = None):
        await interaction.response.defer(ephemeral=True)
        if not isinstance(interaction.channel, discord.TextChannel):
            await interaction.followup.send("❌ 이 명령어는 일반 텍스트 채널에서만 사용할 수 있습니다.", ephemeral=True)
            return
        try:
            check_func = (lambda m: m.author == user) if user else (lambda m: True)
            deleted = await interaction.channel.purge(limit=amount, check=check_func)
            msg = f"✅ 메시지 {len(deleted)}개를 삭제했습니다."
            if user: msg = f"✅ {user.mention}님의 메시지 {len(deleted)}개를 삭제했습니다."
            if len(deleted) < amount: msg += "\nℹ️ 14일이 지난 메시지는 삭제할 수 없습니다."
            await interaction.followup.send(msg, ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ 봇에게 '메시지 관리' 권한이 없습니다.", ephemeral=True)
        except Exception as e:
            logger.error(f"메시지 삭제 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send("❌ 메시지를 삭제하는 중 오류가 발생했습니다.", ephemeral=True)
    
    async def setup_action_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        choices = []
        extended_admin_map = {**ADMIN_ACTION_MAP, "boss_reset_check_test": "[보스] 리셋 루프 즉시 실행 (테스트용)"}
        for key, name in extended_admin_map.items():
            if current.lower() in name.lower(): choices.append(app_commands.Choice(name=name, value=key))
        for key, info in SETUP_COMMAND_MAP.items():
            prefix = "[패널]" if info.get("type") == "panel" else "[채널]"
            choice_name = f"{prefix} {info.get('friendly_name', key)} 설정"
            if current.lower() in choice_name.lower(): choices.append(app_commands.Choice(name=choice_name, value=f"channel_setup:{key}"))
        role_setup_actions = {"role_setup:bump_reminder_role_id": "[알림] Disboard BUMP 알림 역할 설정", "role_setup:dicoall_reminder_role_id": "[알림] Dicoall UP 알림 역할 설정"}
        for key, name in role_setup_actions.items():
            if current.lower() in name.lower(): choices.append(app_commands.Choice(name=name, value=key))
        return sorted(choices, key=lambda c: c.name)[:25]

    @admin_group.command(name="setup", description="봇의 모든 설정을 관리합니다.")
    @app_commands.describe(
        action="실행할 작업을 선택하세요.",
        boss_type="[보스] 대상으로 할 보스의 종류를 선택하세요.",
        channel="[채널/통계] 작업에 필요한 채널을 선택하세요.",
        role="[역할/통계] 작업에 필요한 역할을 선택하세요.",
        user="[코인/XP/레벨/펫] 대상을 지정하세요.",
        amount="[코인/XP] 지급 또는 차감할 수량을 입력하세요.",
        level="[레벨/펫] 설정할 레벨을 입력하세요.",
        stat_type="[통계] 표시할 통계 유형을 선택하세요.",
        template="[통계] 채널 이름 형식을 지정하세요. (예: 👤 유저: {count}명)"
    )
    @app_commands.autocomplete(action=setup_action_autocomplete)
    @app_commands.choices(
        stat_type=[
            app_commands.Choice(name="[설정] 전체 멤버 수 (봇 포함)", value="total"),
            app_commands.Choice(name="[설정] 유저 수 (봇 제외)", value="humans"),
            app_commands.Choice(name="[설정] 봇 수", value="bots"),
            app_commands.Choice(name="[설정] 서버 부스트 수", value="boosters"),
            app_commands.Choice(name="[설정] 특정 역할 멤버 수", value="role"),
            app_commands.Choice(name="[삭제] 이 채널의 통계 설정 삭제", value="remove")
        ],
        boss_type=[
            app_commands.Choice(name="주간 보스", value="weekly"),
            app_commands.Choice(name="월간 보스", value="monthly"),
        ]
    )
    @app_commands.check(is_admin)
    async def setup(self, interaction: discord.Interaction, action: str,
                    boss_type: Optional[str] = None,
                    channel: Optional[discord.abc.GuildChannel] = None,
                    role: Optional[discord.Role] = None, user: Optional[discord.Member] = None,
                    amount: Optional[app_commands.Range[int, 1, None]] = None,
                    level: Optional[app_commands.Range[int, 1, None]] = None,
                    stat_type: Optional[str] = None, template: Optional[str] = None):
        await interaction.response.defer(ephemeral=True)
        
        logger.info(f"[Admin Command] '{interaction.user}' (ID: {interaction.user.id})님이 'setup' 명령어를 실행했습니다. (action: {action})")
        
        if action == "fix_boss_reward_tiers":
            try:
                reward_tiers_config = get_config("BOSS_REWARD_TIERS")
                if not reward_tiers_config: return await interaction.followup.send("❌ DB에서 BOSS_REWARD_TIERS 설정을 찾을 수 없습니다.", ephemeral=True)
                for boss_type_key in ['weekly', 'monthly']:
                    if boss_type_key in reward_tiers_config and reward_tiers_config[boss_type_key]:
                        last_tier = max(reward_tiers_config[boss_type_key], key=lambda x: x['percentile'])
                        last_tier['percentile'] = 1.01
                await save_config_to_db("BOSS_REWARD_TIERS", reward_tiers_config)
                await save_config_to_db("config_reload_request", time.time())
                await interaction.followup.send("✅ 보스 보상 티어의 랭킹 조건을 수정했습니다.", ephemeral=True)
            except Exception as e:
                logger.error(f"보스 보상 티어 수정 중 오류: {e}", exc_info=True)
                await interaction.followup.send("❌ 보스 보상 티어를 수정하는 중 오류가 발생했습니다.", ephemeral=True)
            return
                        
        if action == "strings_sync":
            try:
                await save_config_to_db("strings", UI_STRINGS)
                await save_config_to_db("JOB_ADVANCEMENT_DATA", JOB_ADVANCEMENT_DATA)
                await save_config_to_db("JOB_SYSTEM_CONFIG", JOB_SYSTEM_CONFIG)
                await save_config_to_db("PROFILE_RANK_ROLES", PROFILE_RANK_ROLES)
                await save_config_to_db("USABLE_ITEMS", USABLE_ITEMS)
                await save_config_to_db("WARNING_THRESHOLDS", WARNING_THRESHOLDS)
                await save_config_to_db("config_reload_request", time.time())
                await interaction.followup.send("✅ UI 텍스트와 게임 데이터를 DB에 동기화했습니다.\n**게임 봇을 재시작**하면 적용됩니다.")
            except Exception as e:
                logger.error(f"UI 동기화 중 오류: {e}", exc_info=True)
                await interaction.followup.send("❌ UI 동기화 중 오류가 발생했습니다.")
            return

        elif action == 'eventpass_enable':
            await save_config_to_db('event_priority_pass_active', True); await save_config_to_db('event_priority_pass_users', [])
            await save_config_to_db("config_reload_request", time.time()); await interaction.followup.send("✅ **이벤트 우선 참여권** 사용을 **활성화**했습니다.")
            return
        
        elif action == 'eventpass_disable':
            await save_config_to_db('event_priority_pass_active', False); await save_config_to_db("config_reload_request", time.time())
            await interaction.followup.send("✅ **이벤트 우선 참여권** 사용을 **비활성화**했습니다.")
            return

        if action.startswith("channel_setup:"):
            setting_key = action.split(":", 1)[1]
            config = SETUP_COMMAND_MAP.get(setting_key)
            if not config: return await interaction.followup.send(f"❌ 유효하지 않은 설정 키입니다: {setting_key}", ephemeral=True)
            required_type = config.get("channel_type", "text")
            error_msg = None
            if not channel: error_msg = f"❌ `channel` 옵션에 **{required_type} 채널**을 지정해야 합니다."
            elif (required_type == "text" and not isinstance(channel, discord.TextChannel)) or \
                 (required_type == "voice" and not isinstance(channel, discord.VoiceChannel)) or \
                 (required_type == "forum" and not isinstance(channel, discord.ForumChannel)):
                error_msg = f"❌ **{required_type} 채널**이 필요합니다. 올바른 타입의 채널을 선택해주세요."
            if error_msg: return await interaction.followup.send(error_msg, ephemeral=True)
            db_key, friendly_name = config['key'], config['friendly_name']
            if not await save_id_to_db(db_key, channel.id): return await interaction.followup.send(f"❌ **{friendly_name}** 설정 중 DB 저장에 실패했습니다.", ephemeral=True)
            if (cog := self.bot.get_cog(config["cog_name"])) and hasattr(cog, 'load_configs'): await cog.load_configs()
            await interaction.followup.send(f"✅ **{friendly_name}**을(를) `{channel.mention}` 채널로 설정했습니다.", ephemeral=True)
            return

        if action == "game_data_reload":
            try:
                await save_config_to_db("game_data_reload_request", time.time())
                await interaction.followup.send("✅ 게임 봇에게 게임 데이터를 새로고침하도록 요청했습니다.")
            except Exception as e:
                logger.error(f"게임 데이터 새로고침 요청 중 오류: {e}", exc_info=True)
                await interaction.followup.send("❌ 게임 데이터 새로고침 요청 중 오류가 발생했습니다.")
            return
        
        if action == "boss_reset_check_test":
            try:
                await save_config_to_db("boss_reset_manual_request", {"timestamp": time.time()})
                await interaction.followup.send(f"✅ 게임 봇에게 보스 리셋 루프를 즉시 실행하도록 요청했습니다.", ephemeral=True)
            except Exception as e:
                logger.error(f"보스 리셋 루프 수동 실행 요청 중 오류: {e}", exc_info=True)
                await interaction.followup.send("❌ 보스 리셋 루프를 요청하는 중 오류가 발생했습니다.", ephemeral=True)
            return

        if action == "status_show":
            embed = discord.Embed(title="⚙️ 서버 설정 현황 대시보드", color=0x3498DB, timestamp=discord.utils.utcnow())
            channel_lines = [f"{'✅' if _channel_id_cache.get(info['key']) else '❌'} **{info['friendly_name']}**: {f'<#{_channel_id_cache.get(info["key"])}>' if _channel_id_cache.get(info["key"]) else '미설정'}" for _, info in sorted(SETUP_COMMAND_MAP.items(), key=lambda i: i[1]['friendly_name'])]
            for i in range(0, len(channel_lines), 20):
                embed.add_field(name="채널 설정" if i == 0 else " ", value="\n".join(channel_lines[i:i+20]), inline=False)
            role_lines = [f"{'✅' if _channel_id_cache.get(key) else '❌'} **{info['name']}**: {f'<@&{_channel_id_cache.get(key)}>' if _channel_id_cache.get(key) else '미설정'}" for key, info in sorted(UI_ROLE_KEY_MAP.items(), key=lambda i: i[1]['priority'], reverse=True) if info.get('priority', 0) > 0]
            if role_lines: embed.add_field(name="**주요 역할 설정**", value="\n".join(role_lines)[:1024], inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)
        
        elif action == "server_id_set":
            try:
                await save_config_to_db("SERVER_ID", str(interaction.guild.id))
                await interaction.followup.send(f"✅ 이 서버의 ID (`{interaction.guild.id}`)를 봇의 핵심 설정으로 저장했습니다.")
            except Exception as e:
                logger.error(f"서버 ID 저장 중 오류: {e}", exc_info=True); await interaction.followup.send("❌ 서버 ID 저장 중 오류 발생.")

        elif action in ["coin_give", "coin_take", "xp_give", "level_set"]:
            if not user: return await interaction.followup.send("❌ `user` 옵션이 필요합니다.", ephemeral=True)
            payload = {}; response_msg = ""
            if action == "coin_give":
                if not amount: return await interaction.followup.send("❌ `amount`가 필요합니다.", ephemeral=True)
                payload, response_msg = {"amount": amount, "timestamp": time.time()}, f"✅ {user.mention}님에게 코인 `{amount}`를 지급하도록 요청했습니다."
            elif action == "coin_take":
                if not amount: return await interaction.followup.send("❌ `amount`가 필요합니다.", ephemeral=True)
                payload, response_msg = {"amount": -amount, "timestamp": time.time()}, f"✅ {user.mention}님의 코인 `{amount}`를 차감하도록 요청했습니다."
            elif action == "xp_give":
                if not amount: return await interaction.followup.send("❌ `amount`가 필요합니다.", ephemeral=True)
                payload, response_msg = {"xp_to_add": amount, "timestamp": time.time()}, f"✅ {user.mention}님에게 XP `{amount}`를 부여하도록 요청했습니다."
            elif action == "level_set":
                if not level: return await interaction.followup.send("❌ `level`이 필요합니다.", ephemeral=True)
                payload, response_msg = {"exact_level": level, "timestamp": time.time()}, f"✅ {user.mention}님의 레벨을 **{level}**로 설정하도록 요청했습니다."
            db_key = f"{action.split('_')[0]}_admin_update_request_{user.id}"
            try: await save_config_to_db(db_key, payload); await interaction.followup.send(response_msg)
            except Exception as e: logger.error(f"게임 봇 요청({action}) 저장 중 DB 오류: {e}", exc_info=True); await interaction.followup.send("❌ 요청 실패.")
            return

        elif action == "pet_hatch_now":
            if not user: return await interaction.followup.send("❌ `user` 옵션이 필요합니다.", ephemeral=True)
            try:
                res = await supabase.table('pets').select('id, current_stage').eq('user_id', user.id).maybe_single().execute()
                if not (res and res.data): return await interaction.followup.send(f"❌ {user.mention}님은 펫이 없습니다.", ephemeral=True)
                if res.data['current_stage'] != 1: return await interaction.followup.send(f"❌ 이미 부화한 펫입니다.", ephemeral=True)
                await supabase.table('pets').update({'hatches_at': (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()}).eq('id', res.data['id']).execute()
                await interaction.followup.send(f"✅ {user.mention}님의 알을 즉시 부화시키도록 요청했습니다.", ephemeral=True)
            except Exception as e: logger.error(f"펫 즉시 부화 처리 중 오류: {e}", exc_info=True); await interaction.followup.send("❌ 처리 실패.")
            return

        elif action in ["pet_admin_levelup", "pet_level_set", "exploration_complete_now"]:
            if not user: return await interaction.followup.send("❌ `user` 옵션이 필요합니다.", ephemeral=True)
            db_key, payload, response_msg = "", {}, ""
            if action == "pet_admin_levelup": db_key, payload, response_msg = f"pet_admin_levelup_request_{user.id}", time.time(), f"✅ {user.mention}님의 펫을 1레벨 성장시키도록 요청했습니다."
            elif action == "pet_level_set":
                if not level: return await interaction.followup.send("❌ `level` 옵션이 필요합니다.", ephemeral=True)
                db_key, payload, response_msg = f"pet_level_set_request_{user.id}", {"exact_level": level, "timestamp": time.time()}, f"✅ {user.mention}님의 펫 레벨을 **{level}**로 설정하도록 요청했습니다."
            elif action == "exploration_complete_now": db_key, payload, response_msg = f"exploration_complete_request_{user.id}", time.time(), f"✅ {user.mention}님의 펫 탐사를 즉시 완료하도록 요청했습니다."
            try: await save_config_to_db(db_key, payload); await interaction.followup.send(response_msg, ephemeral=True)
            except Exception as e: logger.error(f"펫 관련 요청 중 오류: {e}", exc_info=True); await interaction.followup.send("❌ 요청 실패.")
            return
            
        elif action == "template_edit":
            embeds = await get_all_embeds();
            if not embeds: return await interaction.followup.send("❌ 편집 가능한 임베드 템플릿이 없습니다.", ephemeral=True)
            await interaction.followup.send("편집할 템플릿을 선택하세요.", view=EmbedTemplateSelectView(embeds), ephemeral=True)

        elif action == "request_regenerate_all_game_panels":
            keys = [k for k, i in SETUP_COMMAND_MAP.items() if "[게임]" in i.get("friendly_name", "")]
            if not keys: return await interaction.followup.send("❌ 게임 패널을 찾을 수 없습니다.", ephemeral=True)
            ts = time.time(); tasks = [save_config_to_db(f"panel_regenerate_request_{key}", ts) for key in keys]
            try: await asyncio.gather(*tasks); await interaction.followup.send(f"✅ {len(keys)}개의 게임 패널 재설치를 요청했습니다.", ephemeral=True)
            except Exception as e: logger.error(f"게임 패널 일괄 재설치 요청 중 오류: {e}", exc_info=True); await interaction.followup.send("❌ 요청 실패.")
        
        elif action.startswith("role_setup:"):
            db_key = action.split(":", 1)[1]
            if not role: return await interaction.followup.send("❌ `role` 옵션을 지정해야 합니다.", ephemeral=True)
            friendly_name = next((c.name.replace(" 설정", "") for c in await self.setup_action_autocomplete(interaction, "") if c.value == action), "알림 역할")
            if not await save_id_to_db(db_key, role.id): return await interaction.followup.send(f"❌ **{friendly_name}** 설정 중 DB 저장 실패.", ephemeral=True)
            if (cog := self.bot.get_cog("Reminder")) and hasattr(cog, 'load_configs'): await cog.load_configs()
            await interaction.followup.send(f"✅ **{friendly_name}**을(를) `{role.mention}` 역할로 설정했습니다.", ephemeral=True)

        elif action == "panels_regenerate_all":
            await interaction.followup.send("⏳ 모든 패널의 재설치를 시작합니다...", ephemeral=True)
            success, failure = [], []
            for key, info in get_config("SETUP_COMMAND_MAP", {}).items():
                if info.get("type") == "panel":
                    name = info.get("friendly_name", key)
                    try:
                        cog_name, channel_key = info.get("cog_name"), info.get("key")
                        if not all([cog_name, channel_key]): failure.append(f"・`{name}`: 설정 불완전"); continue
                        if any(s in name for s in ["[게임]", "[보스]"]):
                            await save_config_to_db(f"panel_regenerate_request_{key}", time.time()); success.append(f"・`{name}`: 게임 봇에게 요청")
                            continue
                        cog = self.bot.get_cog(cog_name)
                        if not cog or not hasattr(cog, 'regenerate_panel'): failure.append(f"・`{name}`: Cog 없음/기능 없음"); continue
                        channel_id = get_id(channel_key)
                        if not channel_id or not (target_ch := self.bot.get_channel(channel_id)): failure.append(f"・`{name}`: 채널 미설정"); continue
                        if await cog.regenerate_panel(target_ch, panel_key=key): success.append(f"・`{name}` → <#{target_ch.id}>")
                        else: failure.append(f"・`{name}`: 재설치 실패")
                        await asyncio.sleep(1)
                    except Exception as e: logger.error(f"'{name}' 패널 재설치 중 오류: {e}", exc_info=True); failure.append(f"・`{name}`: 스크립트 오류")
            embed = discord.Embed(title="⚙️ 모든 패널 재설치 결과", color=0x3498DB, timestamp=discord.utils.utcnow())
            if success: embed.add_field(name="✅ 성공/요청", value="\n".join(success), inline=False)
            if failure: embed.color = 0xED4245; embed.add_field(name="❌ 실패", value="\n".join(failure), inline=False)
            await interaction.edit_original_response(content="모든 패널 재설치가 완료되었습니다.", embed=embed)

        elif action == "roles_sync":
            await save_config_to_db("ROLE_KEY_MAP", {k: i["name"] for k, i in UI_ROLE_KEY_MAP.items()})
            synced, missing, errors = [], [], []
            roles_by_name = {r.name: r.id for r in interaction.guild.roles}
            for key, info in UI_ROLE_KEY_MAP.items():
                if not (name := info.get('name')): continue
                if rid := roles_by_name.get(name):
                    if await save_id_to_db(key, rid): synced.append(f"・`{name}`")
                    else: errors.append(f"・`{name}`: DB 저장 실패")
                else: missing.append(f"・`{name}`")
                await asyncio.sleep(0.1)
            embed = discord.Embed(title="⚙️ 역할 DB 동기화 결과", color=0x2ECC71, timestamp=discord.utils.utcnow())
            embed.set_footer(text=f"총 {len(UI_ROLE_KEY_MAP)}개 | 성공: {len(synced)} / 실패: {len(missing) + len(errors)}")
            if synced: embed.add_field(name=f"✅ 동기화 성공 ({len(synced)}개)", value="\n".join(synced)[:1024], inline=False)
            if missing: embed.color = 0xFEE75C; embed.add_field(name=f"⚠️ 서버에 역할 없음 ({len(missing)}개)", value="\n".join(missing)[:1024], inline=False)
            if errors: embed.color = 0xED4245; embed.add_field(name=f"❌ DB 저장 오류 ({len(errors)}개)", value="\n".join(errors)[:1024], inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)

        elif action == "stats_set":
            if not channel or not isinstance(channel, discord.VoiceChannel): return await interaction.followup.send("❌ `channel` 옵션에 음성 채널을 지정해야 합니다.", ephemeral=True)
            if not stat_type: return await interaction.followup.send("❌ `stat_type` 옵션을 선택해야 합니다.", ephemeral=True)
            if stat_type == "remove":
                await remove_stats_channel(channel.id); await interaction.followup.send(f"✅ `{channel.name}` 채널의 통계 설정을 삭제했습니다.", ephemeral=True)
            else:
                current_template = template or "정보: {count}"
                if "{count}" not in current_template: return await interaction.followup.send("❌ 이름 형식(`template`)에 `{count}`를 포함해야 합니다.", ephemeral=True)
                if stat_type == "role" and not role: return await interaction.followup.send("❌ '특정 역할 멤버 수'는 `role` 옵션이 필요합니다.", ephemeral=True)
                await add_stats_channel(channel.id, interaction.guild_id, stat_type, current_template, role.id if role else None)
                if (cog := self.bot.get_cog("StatsUpdater")) and hasattr(cog, 'update_stats_loop') and cog.update_stats_loop.is_running(): cog.update_stats_loop.restart()
                await interaction.followup.send(f"✅ `{channel.name}` 채널에 통계 설정을 추가/수정했습니다.", ephemeral=True)

        elif action == "stats_refresh":
            if (cog := self.bot.get_cog("StatsUpdater")) and hasattr(cog, 'update_stats_loop') and cog.update_stats_loop.is_running():
                cog.update_stats_loop.restart(); await interaction.followup.send("✅ 모든 통계 채널 업데이트를 요청했습니다.", ephemeral=True)
            else: await interaction.followup.send("❌ 통계 업데이트 기능이 실행 중이 아닙니다.", ephemeral=True)

        elif action == "stats_list":
            configs = [c for c in await get_all_stats_channels() if c.get('guild_id') == interaction.guild_id]
            if not configs: return await interaction.followup.send("ℹ️ 설정된 통계 채널이 없습니다.", ephemeral=True)
            embed = discord.Embed(title="📊 설정된 통계 채널 목록", color=0x3498DB)
            desc = []
            for c in configs:
                ch = f"<#{c['channel_id']}>" if self.bot.get_channel(c['channel_id']) else f"삭제된 채널({c['channel_id']})"
                role_info = ""
                if c['stat_type'] == 'role' and c.get('role_id'): role_info = f"\n**대상 역할:** {interaction.guild.get_role(c['role_id']).mention if interaction.guild.get_role(c['role_id']) else '알 수 없음'}"
                desc.append(f"**채널:** {ch}\n**종류:** `{c['stat_type']}`{role_info}\n**이름 형식:** `{c['channel_name_template']}`")
            embed.description = "\n\n".join(desc); await interaction.followup.send(embed=embed, ephemeral=True)
            
        elif action in ["trigger_daily_updates", "farm_next_day", "farm_reset_date"]:
            try:
                if action == "farm_next_day":
                    current_date = date.fromisoformat(get_config("farm_current_date")) if get_config("farm_current_date") else datetime.now(timezone(timedelta(hours=9))).date()
                    next_day = current_date + timedelta(days=1)
                    await save_config_to_db("farm_current_date", next_day.isoformat())
                    await save_config_to_db("config_reload_request", time.time())
                    await save_config_to_db("manual_update_request", time.time())
                    await interaction.followup.send(f"✅ 농장 시간을 다음 날로 변경했습니다: **{next_day.strftime('%Y-%m-%d')}**")
                elif action == "farm_reset_date":
                    await delete_config_from_db("farm_current_date")
                    await save_config_to_db("manual_update_request", time.time())
                    await interaction.followup.send("✅ 농장 시간을 현재 실제 시간으로 초기화했습니다.")
                else:
                    await save_config_to_db("manual_update_request", time.time())
                    await interaction.followup.send("✅ 시세 변동 및 작물 상태 업데이트를 요청했습니다.")
            except Exception as e:
                logger.error(f"수동 업데이트 요청 중 오류: {e}", exc_info=True)
                await interaction.followup.send("❌ 수동 업데이트 요청 중 오류가 발생했습니다.")
        
        elif action in ["boss_spawn_test", "boss_defeat_test"]:
            if not boss_type: return await interaction.followup.send("❌ `boss_type` 옵션(주간/월간)을 선택해야 합니다.", ephemeral=True)
            try:
                db_key = f"{action}_request"
                payload = {"boss_type": boss_type, "timestamp": time.time()}
                await save_config_to_db(db_key, payload)
                response_msg = f"✅ 게임 봇에게 **{boss_type} 보스**를 강제로 소환하도록 요청했습니다." if action == "boss_spawn_test" else f"✅ 게임 봇에게 현재 진행 중인 **{boss_type} 보스**를 강제로 처치하도록 요청했습니다."
                await interaction.followup.send(response_msg, ephemeral=True)
            except Exception as e:
                logger.error(f"보스 테스트 명령어 처리 중 오류: {e}", exc_info=True)
                await interaction.followup.send("❌ 보스 테스트 명령 요청 중 오류가 발생했습니다.", ephemeral=True)
            return

        else:
            await interaction.followup.send("❌ 알 수 없는 작업입니다.", ephemeral=True)
            
async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))
