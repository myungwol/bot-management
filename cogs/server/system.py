# cogs/server/system.py
"""
서버 관리와 관련된 모든 통합 명령어를 단일 /setup 명령어로 담당하는 Cog입니다.
"""
import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional, List

from utils.database import (
    get_config, save_id_to_db, load_channel_ids_from_db,
    get_all_stats_channels, add_stats_channel, remove_stats_channel
)

logger = logging.getLogger(__name__)

class ServerSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("System (통합 관리 명령어) Cog가 성공적으로 초기화되었습니다.")

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message(f"❌ 이 명령어를 사용하려면 다음 권한이 필요합니다: `{', '.join(error.missing_permissions)}`", ephemeral=True)
        else:
            logger.error(f"'{interaction.command.qualified_name}' 명령어 처리 중 오류 발생: {error}", exc_info=True)
            if interaction.response.is_done():
                await interaction.followup.send("❌ 명령어를 처리하는 중에 예기치 않은 오류가 발생했습니다.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ 명령어를 처리하는 중에 예기치 않은 오류가 발생했습니다.", ephemeral=True)

    async def setup_action_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        setup_map = get_config("SETUP_COMMAND_MAP", {})
        choices = []
        for key, info in setup_map.items():
            type_prefix = "[채널/패널]"
            choice_name = f"{type_prefix} {info.get('friendly_name', key)} 설정"
            if current.lower() in choice_name.lower():
                choices.append(app_commands.Choice(name=choice_name, value=f"channel_setup:{key}"))

        role_actions = { "roles_sync": "[역할] 모든 역할 DB와 동기화" }
        for key, name in role_actions.items():
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=key))
        
        stats_actions = {
            "stats_set": "[통계] 통계 채널 설정/제거",
            "stats_refresh": "[통계] 모든 통계 채널 새로고침",
            "stats_list": "[통계] 설정된 통계 채널 목록 보기",
        }
        for key, name in stats_actions.items():
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=key))

        return sorted(choices, key=lambda c: c.name)[:25]

    @app_commands.command(name="setup", description="[관리자] 봇의 채널, 역할, 통계 등 모든 설정을 관리합니다.")
    @app_commands.describe(
        action="수행할 작업을 선택하세요.",
        channel="[채널/통계] 작업에 필요한 채널을 선택하세요.",
        role="[통계] '특정 역할 인원' 선택 시 필요한 역할입니다.",
        stat_type="[통계] 표시할 통계 종류를 선택하세요.",
        template="[통계] 채널 이름 형식을 지정하세요 (예: 👤 유저: {count}명)"
    )
    @app_commands.autocomplete(action=setup_action_autocomplete)
    @app_commands.choices(stat_type=[
        app_commands.Choice(name="[설정] 전체 인원 (봇 포함)", value="total"),
        app_commands.Choice(name="[설정] 유저 인원 (봇 제외)", value="humans"),
        app_commands.Choice(name="[설정] 봇 개수", value="bots"),
        app_commands.Choice(name="[설정] 서버 부스터 수", value="boosters"),
        app_commands.Choice(name="[설정] 특정 역할 인원", value="role"),
        app_commands.Choice(name="[제거] 이 채널의 통계 설정 제거", value="remove"),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup(self, interaction: discord.Interaction,
                    action: str,
                    channel: Optional[discord.TextChannel | discord.VoiceChannel] = None,
                    role: Optional[discord.Role] = None,
                    stat_type: Optional[str] = None,
                    template: Optional[str] = None):
        
        await interaction.response.defer(ephemeral=True)

        # --- 1. 채널/패널 설정 로직 ---
        if action.startswith("channel_setup:"):
            setting_type = action.split(":", 1)[1]
            setup_map = get_config("SETUP_COMMAND_MAP", {})
            config = setup_map[setting_type]
            
            required_channel_type = config.get("channel_type", "text")
            
            error_msg = None
            if not channel:
                error_msg = f"❌ 이 작업을 수행하려면 'channel' 옵션에 **{required_channel_type} 채널**을 지정해야 합니다."
            elif (required_channel_type == "text" and not isinstance(channel, discord.TextChannel)) or \
                 (required_channel_type == "voice" and not isinstance(channel, discord.VoiceChannel)):
                error_msg = f"❌ 이 작업에는 **{required_channel_type} 채널**이 필요합니다. 올바른 타입의 채널을 선택해주세요."
            
            if error_msg:
                await interaction.followup.send(error_msg, ephemeral=True)
                return

            db_key, friendly_name = config['key'], config['friendly_name']
            await save_id_to_db(db_key, channel.id)
            
            cog_to_reload = self.bot.get_cog(config["cog_name"])
            if cog_to_reload and hasattr(cog_to_reload, 'load_configs'):
                await cog_to_reload.load_configs()

            if config["type"] == "panel" and hasattr(cog_to_reload, 'regenerate_panel'):
                await cog_to_reload.regenerate_panel(channel)
                await interaction.followup.send(f"✅ `{channel.mention}` 채널에 **{friendly_name}** 패널을 성공적으로 설치했습니다.", ephemeral=True)
            else:
                await interaction.followup.send(f"✅ **{friendly_name}**을(를) `{channel.mention}` 채널로 설정했습니다.", ephemeral=True)

        # --- 2. 역할 관련 로직 ---
        elif action == "roles_sync":
            role_key_map_config = get_config("ROLE_KEY_MAP", {})
            synced_roles, missing_roles, error_roles = [], [], []
            server_roles_by_name = {r.name: r.id for r in interaction.guild.roles}
            
            for db_key, role_info in role_key_map_config.items():
                role_name = role_info.get('name')
                if not role_name: continue
                if role_id := server_roles_by_name.get(role_name):
                    try:
                        await save_id_to_db(db_key, role_id)
                        synced_roles.append(f"・**{role_name}** (`{db_key}`)")
                    except Exception as e: error_roles.append(f"・**{role_name}**: `{e}`")
                else: missing_roles.append(f"・**{role_name}** (`{db_key}`)")
            
            embed = discord.Embed(title="⚙️ 역할 데이터베이스 전체 동기화 결과", color=0x2ECC71)
            embed.set_footer(text=f"총 {len(role_key_map_config)}개 중 성공: {len(synced_roles)} / 실패: {len(missing_roles) + len(error_roles)}")
            if synced_roles: embed.add_field(name=f"✅ 동기화 성공 ({len(synced_roles)}개)", value="\n".join(synced_roles)[:1024], inline=False)
            if missing_roles:
                embed.color = 0xFEE75C
                embed.add_field(name=f"⚠️ 서버에 해당 역할 없음 ({len(missing_roles)}개)", value="\n".join(missing_roles)[:1024], inline=False)
            if error_roles:
                embed.color = 0xED4245
                embed.add_field(name=f"❌ DB 저장 오류 ({len(error_roles)}개)", value="\n".join(error_roles)[:1024], inline=False)
            await interaction.followup.send(embed=embed, ephemeral=True)

        # --- 3. 통계 관련 로직 ---
        elif action == "stats_set":
            if not channel or not isinstance(channel, discord.VoiceChannel):
                await interaction.followup.send("❌ 이 작업을 수행하려면 'channel' 옵션에 음성 채널을 지정해야 합니다.", ephemeral=True)
                return
            if not stat_type:
                await interaction.followup.send("❌ 이 작업을 수행하려면 'stat_type' 옵션을 선택해야 합니다.", ephemeral=True)
                return

            if stat_type == "remove":
                await remove_stats_channel(channel.id)
                await interaction.followup.send(f"✅ `{channel.name}` 채널의 통계 설정을 제거했습니다.", ephemeral=True)
            else:
                current_template = template or f"이름: {{count}}"
                if "{count}" not in current_template:
                    await interaction.followup.send("❌ 이름 형식(`template`)에는 반드시 `{count}`가 포함되어야 합니다.", ephemeral=True)
                    return
                if stat_type == "role" and not role:
                    await interaction.followup.send("❌ '특정 역할 인원'을 선택했다면, 'role' 옵션을 지정해야 합니다.", ephemeral=True)
                    return
                
                role_id = role.id if role else None
                await add_stats_channel(channel.id, interaction.guild_id, stat_type, current_template, role_id)
                stats_cog = self.bot.get_cog("VoiceMaster") # Cog 이름 수정 필요
                if stats_cog: stats_cog.update_stats_loop.restart()
                await interaction.followup.send(f"✅ `{channel.name}` 채널에 통계 설정을 추가/수정했습니다.", ephemeral=True)

        elif action == "stats_refresh":
            stats_cog = self.bot.get_cog("VoiceMaster") # Cog 이름 수정 필요
            if stats_cog:
                stats_cog.update_stats_loop.restart()
                await interaction.followup.send("✅ 모든 통계 채널에 대한 새로고침을 요청했습니다.", ephemeral=True)
            else:
                await interaction.followup.send("❌ 통계 업데이트 기능을 찾을 수 없습니다.", ephemeral=True)

        elif action == "stats_list":
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
        
        else:
             await interaction.followup.send("❌ 알 수 없는 작업입니다. 목록에서 올바른 작업을 선택해주세요.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))
