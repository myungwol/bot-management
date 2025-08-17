# cogs/server/system.py

import discord
from discord.ext import commands
from discord import app_commands
import logging
from typing import Optional, List

from utils.database import get_id, save_id_to_db, load_channel_ids_from_db, get_config

logger = logging.getLogger(__name__)

# --- ServerSystem Cog ---
class ServerSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("System (통합 관리 명령어) Cog가 성공적으로 초기화되었습니다.")

    # ==============================================================================
    # 통합 /setup 명령어 그룹 생성
    # ==============================================================================
    setup = app_commands.Group(name="setup", description="[관리자] 서버의 패널, 채널, 역할 등 봇의 모든 설정을 관리합니다.")

    # ==============================================================================
    # 1. /setup set (채널/패널 설정)
    # ==============================================================================
    
    # 자동완성 목록 생성 (채널/패널 설정용)
    def get_channel_setup_choices(self) -> List[app_commands.Choice[str]]:
        setup_map = get_config("SETUP_COMMAND_MAP", {})
        choices = []
        for key, info in setup_map.items():
            type_prefix = "[패널]" if info.get('type') == 'panel' else "[채널]"
            choices.append(app_commands.Choice(name=f"{type_prefix} {info.get('friendly_name', key)}", value=key))
        return choices

    @setup.command(name="set", description="[관리자] 각종 채널을 설정하거나 패널을 설치합니다.")
    @app_commands.describe(setting_type="설정할 항목을 선택하세요.", channel="설정할 텍스트 채널을 지정하세요.")
    @app_commands.autocomplete('setting_type')
    async def setup_set_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        choices = self.get_channel_setup_choices()
        # 사용자가 입력한 내용을 기반으로 자동완성 목록 필터링
        return [choice for choice in choices if current.lower() in choice.name.lower()][:25]

    @setup_set.error
    async def on_setup_set_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ 이 명령어를 사용하려면 서버 관리 권한이 필요합니다.", ephemeral=True)
        else:
            logger.error(f"/setup set 명령어 오류 발생: {error}", exc_info=True)
            await interaction.response.send_message("❌ 명령어 처리 중 오류가 발생했습니다.", ephemeral=True)

    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_set_command(self, interaction: discord.Interaction, setting_type: str, channel: discord.TextChannel):
        # 자동완성 목록을 다시 가져와 유효한 값인지 확인
        valid_keys = [choice.value for choice in self.get_channel_setup_choices()]
        if setting_type not in valid_keys:
            await interaction.response.send_message("❌ 잘못된 설정 항목입니다. 목록에서 선택해주세요.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        setup_map = get_config("SETUP_COMMAND_MAP", {})
        config = setup_map.get(setting_type)
        
        try:
            db_key, friendly_name = config['key'], config['friendly_name']
            await save_id_to_db(db_key, channel.id)
            
            # Cog 설정 리로드
            cog_to_reload = self.bot.get_cog(config["cog_name"])
            if cog_to_reload and hasattr(cog_to_reload, 'load_configs'):
                await cog_to_reload.load_configs()
                logger.info(f"'{config['cog_name']}' Cog의 설정을 새로고침했습니다.")

            # 패널 재생성
            if config["type"] == "panel":
                if hasattr(cog_to_reload, 'regenerate_panel'):
                    await cog_to_reload.regenerate_panel(channel)
                    await interaction.followup.send(f"✅ `{channel.mention}` 채널에 **{friendly_name}** 패널을 성공적으로 설치했습니다.", ephemeral=True)
                else:
                    await interaction.followup.send(f"⚠️ **{friendly_name}** 설정은 완료되었지만, 패널 자동 생성 기능(`regenerate_panel`)이 없습니다.", ephemeral=True)
            else: # 채널 설정
                await interaction.followup.send(f"✅ **{friendly_name}**을(를) `{channel.mention}` 채널로 설정했습니다.", ephemeral=True)

        except Exception as e:
            logger.error(f"채널/패널 설정({setting_type}) 처리 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 설정 중 오류가 발생했습니다. 봇 로그를 확인해주세요.", ephemeral=True)

    # 실제 명령어 콜백을 등록
    setup.command(name="set", description="[관리자] 각종 채널을 설정하거나 패널을 설치합니다.")(setup_set_command)


    # ==============================================================================
    # 2. /setup roles (역할 관련 명령어 그룹)
    # ==============================================================================
    roles = app_commands.Group(name="roles", parent=setup, description="[관리자] 서버 역할을 DB와 동기화하거나 개별 설정합니다.")

    @roles.command(name="sync", description="[관리자] 서버의 모든 역할을 이름 기준으로 DB와 한번에 동기화합니다.")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def roles_sync(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild
        role_key_map_config = get_config("ROLE_KEY_MAP", {})
        if not role_key_map_config:
            await interaction.followup.send("❌ `ROLE_KEY_MAP` 설정이 DB에 없습니다. 관리자에게 문의하세요.", ephemeral=True)
            return

        synced_roles, missing_roles, error_roles = [], [], []
        server_roles_by_name = {role.name: role.id for role in guild.roles}
        
        for db_key, role_name in role_key_map_config.items():
            role_id = server_roles_by_name.get(role_name)
            if role_id:
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
            embed.color = 0xFEE75C # Warning Yellow
            embed.add_field(name=f"⚠️ 서버에 역할 없음 ({len(missing_roles)}개)", value="\n".join(missing_roles)[:1024], inline=False)
        if error_roles:
            embed.color = 0xED4245 # Error Red
            embed.add_field(name=f"❌ DB 저장 오류 ({len(error_roles)}개)", value="\n".join(error_roles)[:1024], inline=False)
        
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def role_type_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        role_key_map = get_config("ROLE_KEY_MAP", {})
        return [app_commands.Choice(name=f"{key} ({name_info.get('name', '')})", value=key) for key, name_info in role_key_map.items() if current.lower() in key.lower() or current.lower() in name_info.get('name', '').lower()][:25]

    @roles.command(name="set", description="[관리자] 특정 역할을 DB에 개별적으로 설정합니다.")
    @app_commands.describe(role_type="DB에 저장할 역할의 종류 (예: role_resident)", role="서버에 실제로 존재하는 역할을 선택하세요.")
    @app_commands.autocomplete(role_type=role_type_autocomplete)
    @app_commands.checks.has_permissions(manage_roles=True)
    async def roles_set(self, interaction: discord.Interaction, role_type: str, role: discord.Role):
        role_key_map = get_config("ROLE_KEY_MAP", {})
        if role_type not in role_key_map:
            await interaction.response.send_message(f"❌ '{role_type}'은(는) 유효하지 않은 역할 종류입니다. 목록에서 선택해주세요.", ephemeral=True)
            return
        
        await interaction.response.defer(ephemeral=True)
        try:
            await save_id_to_db(role_type, role.id)
            await load_channel_ids_from_db() # 캐시 새로고침
            embed = discord.Embed(title="✅ 역할 설정 완료", description=f"DB의 `{role_type}` 키에 {role.mention} 역할이 성공적으로 연결되었습니다.", color=discord.Color.blue())
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"개별 역할 설정 중 오류: {e}", exc_info=True)
            embed = discord.Embed(title="❌ 오류 발생", description=f"`{role_type}` 역할 설정 중 오류가 발생했습니다.", color=discord.Color.red())
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))
