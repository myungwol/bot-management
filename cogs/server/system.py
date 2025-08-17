# cogs/server/system.py
"""
서버 관리와 관련된 모든 통합 명령어를 담당하는 Cog입니다.
- /setup 그룹 명령어를 통해 봇의 모든 설정을 관리합니다.
- 채널/패널 설정, 역할 동기화, 통계 채널 관리 등의 기능을 포함합니다.
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional, List

# [수정] database.py에서 필요한 모든 함수를 가져옵니다.
from utils.database import (
    get_config, save_id_to_db, load_channel_ids_from_db,
    get_all_stats_channels, add_stats_channel, remove_stats_channel
)

logger = logging.getLogger(__name__)

class ServerSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("System (통합 관리 명령어) Cog가 성공적으로 초기화되었습니다.")

    # Cog 전역 오류 처리기
    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(
                f"❌ 이 명령어를 사용하려면 다음 권한이 필요합니다: `{', '.join(error.missing_permissions)}`",
                ephemeral=True
            )
        else:
            logger.error(f"'{interaction.command.qualified_name}' 명령어 처리 중 오류 발생: {error}", exc_info=True)
            if interaction.response.is_done():
                await interaction.followup.send("❌ 명령어를 처리하는 중에 예기치 않은 오류가 발생했습니다. 봇 로그를 확인해주세요.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ 명령어를 처리하는 중에 예기치 않은 오류가 발생했습니다. 봇 로그를 확인해주세요.", ephemeral=True)

    # =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # /setup 명령어 그룹
    # =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    setup = app_commands.Group(
        name="setup",
        description="[관리자] 서버의 패널, 채널, 역할 등 봇의 모든 설정을 관리합니다.",
        default_permissions=discord.Permissions(manage_guild=True),
        guild_only=True
    )

    # ------------------------------------------------------------------------------
    # 1. /setup set (채널/패널 설정)
    # ------------------------------------------------------------------------------
    async def setup_set_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        setup_map = get_config("SETUP_COMMAND_MAP", {})
        choices = []
        for key, info in setup_map.items():
            type_prefix = "[패널]" if info.get('type') == 'panel' else "[채널]"
            choice_name = f"{type_prefix} {info.get('friendly_name', key)}"
            if current.lower() in choice_name.lower():
                choices.append(app_commands.Choice(name=choice_name, value=key))
        return choices[:25]

    # [수정] 데코레이터 순서를 올바르게 변경하고 명령어 정의를 통합
    @setup.command(name="set", description="각종 채널을 설정하거나 패널을 설치합니다.")
    @app_commands.describe(setting_type="설정할 항목을 선택하세요.", channel="설정할 텍스트 채널을 지정하세요.")
    @app_commands.autocomplete(setting_type=setup_set_autocomplete)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_set(self, interaction: discord.Interaction, setting_type: str, channel: discord.TextChannel):
        setup_map = get_config("SETUP_COMMAND_MAP", {})
        if setting_type not in setup_map:
            await interaction.response.send_message("❌ 잘못된 설정 항목입니다. 목록에서 선택해주세요.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        
        config = setup_map[setting_type]
        db_key, friendly_name = config['key'], config['friendly_name']
        
        await save_id_to_db(db_key, channel.id)
        
        cog_to_reload = self.bot.get_cog(config["cog_name"])
        if cog_to_reload and hasattr(cog_to_reload, 'load_configs'):
            await cog_to_reload.load_configs()

        if config["type"] == "panel":
            if hasattr(cog_to_reload, 'regenerate_panel'):
                await cog_to_reload.regenerate_panel(channel)
                await interaction.followup.send(f"✅ `{channel.mention}` 채널에 **{friendly_name}** 패널을 성공적으로 설치했습니다.", ephemeral=True)
            else:
                await interaction.followup.send(f"⚠️ **{friendly_name}** 설정은 완료되었지만, 이 Cog에는 패널 자동 생성 기능이 없습니다.", ephemeral=True)
        else:
            await interaction.followup.send(f"✅ **{friendly_name}**을(를) `{channel.mention}` 채널로 설정했습니다.", ephemeral=True)

    # ------------------------------------------------------------------------------
    # 2. /setup roles (역할 관련 하위 명령어 그룹)
    # ------------------------------------------------------------------------------
    roles = app_commands.Group(name="roles", parent=setup, description="서버 역할을 DB와 동기화하거나 개별 설정합니다.")

    @roles.command(name="sync", description="서버의 모든 역할을 이름 기준으로 DB와 한번에 동기화합니다.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def roles_sync(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        role_key_map_config = get_config("ROLE_KEY_MAP", {})
        if not role_key_map_config:
            await interaction.followup.send("❌ `ROLE_KEY_MAP` 설정이 DB에 없습니다. 봇 관리자에게 문의하세요.", ephemeral=True)
            return

        synced_roles, missing_roles, error_roles = [], [], []
        server_roles_by_name = {role.name: role.id for role in interaction.guild.roles}
        
        for db_key, role_name in role_key_map_config.items():
            if role_id := server_roles_by_name.get(role_name):
                try:
                    await save_id_to_db(db_key, role_id)
                    synced_roles.append(f"・**{role_name}** (`{db_key}`)")
                except Exception as e:
                    error_roles.append(f"・**{role_name}**: `{e}`")
            else:
                missing_roles.append(f"・**{role_name}** (`{db_key}`)")
        
        embed = discord.Embed(title="⚙️ 역할 데이터베이스 전체 동기화 결과", color=0x2ECC71)
        embed.set_footer(text=f"총 {len(role_key_map_config)}개 중 성공: {len(synced_roles)} / 실패: {len(missing_roles) + len(error_roles)}")
        if synced_roles:
            embed.add_field(name=f"✅ 동기화 성공 ({len(synced_roles)}개)", value="\n".join(synced_roles)[:1024], inline=False)
        if missing_roles:
            embed.color = 0xFEE75C
            embed.add_field(name=f"⚠️ 서버에 해당 역할 없음 ({len(missing_roles)}개)", value="\n".join(missing_roles)[:1024], inline=False)
        if error_roles:
            embed.color = 0xED4245
            embed.add_field(name=f"❌ DB 저장 오류 ({len(error_roles)}개)", value="\n".join(error_roles)[:1024], inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def role_set_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        role_key_map = get_config("ROLE_KEY_MAP", {})
        choices = []
        for key, info in role_key_map.items():
            role_name = info.get('name', '')
            choice_name = f"{key} ({role_name})"
            if current.lower() in key.lower() or current.lower() in role_name.lower():
                choices.append(app_commands.Choice(name=choice_name, value=key))
        return choices[:25]

    @roles.command(name="set", description="특정 역할을 DB에 개별적으로 설정합니다.")
    @app_commands.describe(role_type="DB에 저장할 역할의 종류 (예: role_resident)", role="서버에 실제로 존재하는 역할을 선택하세요.")
    @app_commands.autocomplete(role_type=role_set_autocomplete)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def roles_set(self, interaction: discord.Interaction, role_type: str, role: discord.Role):
        if role_type not in get_config("ROLE_KEY_MAP", {}):
            await interaction.response.send_message(f"❌ '{role_type}'은(는) 유효하지 않은 역할 종류입니다. 목록에서 선택해주세요.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        await save_id_to_db(role_type, role.id)
        await load_channel_ids_from_db()
        
        embed = discord.Embed(title="✅ 역할 설정 완료", description=f"DB의 `{role_type}` 키에 {role.mention} 역할이 성공적으로 연결되었습니다.", color=0x3498DB)
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ------------------------------------------------------------------------------
    # 3. /setup stats (서버 통계 채널 관리 그룹)
    # ------------------------------------------------------------------------------
    stats = app_commands.Group(name="stats", parent=setup, description="서버 통계 채널을 관리합니다.")

    @stats.command(name="add", description="통계 정보를 표시할 채널을 추가하거나 수정합니다.")
    @app_commands.describe(
        stat_type="표시할 통계의 종류를 선택하세요.",
        channel="통계를 표시할 음성 채널 또는 카테고리를 선택하세요.",
        template="채널 이름 형식을 지정하세요. 반드시 '{count}'를 포함해야 합니다.",
        role="통계 종류가 '특정 역할'인 경우에만 역할을 선택하세요."
    )
    @app_commands.choices(stat_type=[
        app_commands.Choice(name="전체 인원 (봇 포함)", value="total"),
        app_commands.Choice(name="유저 인원 (봇 제외)", value="humans"),
        app_commands.Choice(name="봇 개수", value="bots"),
        app_commands.Choice(name="서버 부스터 수", value="boosters"),
        app_commands.Choice(name="특정 역할 인원", value="role"),
    ])
    async def stats_add(self, interaction: discord.Interaction,
                        stat_type: str,
                        channel: discord.VoiceChannel,
                        template: str,
                        role: Optional[discord.Role] = None):
        
        if "{count}" not in template:
            await interaction.response.send_message("❌ 이름 형식(`template`)에는 반드시 `{count}`가 포함되어야 합니다.", ephemeral=True)
            return
        if stat_type == "role" and not role:
            await interaction.response.send_message("❌ '특정 역할 인원'을 선택했다면, 반드시 역할을 지정해야 합니다.", ephemeral=True)
            return
        if stat_type != "role" and role:
            await interaction.response.send_message("⚠️ 역할은 '특정 역할 인원' 통계에서만 의미가 있습니다.", ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        
        role_id = role.id if role else None
        await add_stats_channel(channel.id, interaction.guild_id, stat_type, template, role_id)

        stats_cog = self.bot.get_cog("StatsUpdater")
        if stats_cog and hasattr(stats_cog, 'update_stats_loop'):
            stats_cog.update_stats_loop.restart()

        await interaction.followup.send(f"✅ `{channel.name}` 채널에 통계 설정을 추가했습니다. 잠시 후 채널 이름이 변경됩니다.", ephemeral=True)

    @stats.command(name="remove", description="통계 채널 설정을 제거합니다.")
    @app_commands.describe(channel="설정을 제거할 채널을 선택하세요.")
    async def stats_remove(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        await interaction.response.defer(ephemeral=True)
        await remove_stats_channel(channel.id)
        await interaction.followup.send(f"✅ `{channel.name}` 채널의 통계 설정을 제거했습니다.", ephemeral=True)

    @stats.command(name="list", description="현재 설정된 모든 통계 채널 목록을 봅니다.")
    async def stats_list(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        configs = await get_all_stats_channels()
        if not configs:
            await interaction.followup.send("ℹ️ 설정된 통계 채널이 없습니다.", ephemeral=True)
            return
        
        embed = discord.Embed(title="📊 설정된 통계 채널 목록", color=0x3498DB)
        description = []
        for config in configs:
            ch = self.bot.get_channel(config['channel_id'])
            ch_mention = f"<#{ch.id}>" if ch else f"삭제된 채널({config['channel_id']})"
            description.append(f"**채널:** {ch_mention}\n"
                               f"**종류:** `{config['stat_type']}`\n"
                               f"**이름 형식:** `{config['channel_name_template']}`")
        embed.description = "\n\n".join(description)
        await interaction.followup.send(embed=embed, ephemeral=True)

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    # 4. /setup check_counts (멤버 수 진단용 임시 명령어)
    # =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
    @setup.command(name="check_counts", description="[관리자] 현재 봇이 인식하는 각종 멤버 수를 직접 확인합니다.")
    async def check_counts(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild

        # 1. API가 제공하는 공식 총 인원
        total_from_api = guild.member_count
        
        # 2. 봇의 내부 캐시(목록)에 있는 총 인원
        total_from_cache = len(guild.members)
        
        # 3. 캐시 기반 유저 수
        humans_from_cache = len([m for m in guild.members if not m.bot])
        
        # 4. 캐시 기반 봇 수
        bots_from_cache = len([m for m in guild.members if m.bot])
        
        # 5. 부스터 수
        boosters = guild.premium_subscription_count

        embed = discord.Embed(title="📊 멤버 수 진단 결과", color=0xFFD700)
        embed.description = "봇이 현재 인식하고 있는 각 항목별 인원수입니다."
        
        embed.add_field(name="1️⃣ Discord API 공식 총 인원 (`guild.member_count`)", value=f"**{total_from_api}** 명", inline=False)
        embed.add_field(name="2️⃣ 봇의 내부 목록상 총 인원 (`len(guild.members)`)", value=f"**{total_from_cache}** 명", inline=False)
        embed.add_field(name="3️⃣ 내부 목록상 유저 수 (봇 제외)", value=f"**{humans_from_cache}** 명", inline=False)
        embed.add_field(name="4️⃣ 내부 목록상 봇 수", value=f"**{bots_from_cache}** 명", inline=False)
        embed.add_field(name="5️⃣ 서버 부스터 수", value=f"**{boosters}** 개", inline=False)
        
        if total_from_api != total_from_cache:
            embed.add_field(
                name="🔍 분석",
                value=f"**1번**과 **2번**의 차이가 **{total_from_api - total_from_cache}명** 만큼 발생했습니다.\n이는 봇의 내부 멤버 목록이 불완전하다는 명확한 증거입니다. 다음 단계에서 이 문제를 해결하겠습니다.",
                inline=False
            )
            embed.color = 0xED4245 # Error Red
        else:
            embed.add_field(name="🔍 분석", value="API와 내부 목록의 인원수가 일치합니다. 문제가 다른 곳에 있을 수 있습니다.", inline=False)

        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))
