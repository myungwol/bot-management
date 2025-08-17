# 기존 setup 함수 전체를 아래 코드로 교체하세요.

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
            
            # [수정] channel_type에 따라 올바른 채널 타입 검사
            required_channel_type = config.get("channel_type", "text") # 기본값은 text
            
            if not channel:
                await interaction.followup.send(f"❌ 이 작업을 수행하려면 'channel' 옵션에 **{required_channel_type} 채널**을 지정해야 합니다.", ephemeral=True)
                return
            if (required_channel_type == "text" and not isinstance(channel, discord.TextChannel)) or \
               (required_channel_type == "voice" and not isinstance(channel, discord.VoiceChannel)):
                await interaction.followup.send(f"❌ 이 작업에는 **{required_channel_type} 채널**이 필요합니다. 올바른 타입의 채널을 선택해주세요.", ephemeral=True)
                return

            db_key, friendly_name = config['key'], config['friendly_name']
            await save_id_to_db(db_key, channel.id)
            
            cog_to_reload = self.bot.get_cog(config["cog_name"])
            if cog_to_reload and hasattr(cog_to_reload, 'load_configs'):
                await cog_to_reload.load_configs()

            if config["type"] == "panel" and hasattr(cog_to_reload, 'regenerate_panel'):
                # regenerate_panel은 TextChannel만 받을 수 있다고 가정
                await cog_to_reload.regenerate_panel(channel if isinstance(channel, discord.TextChannel) else None)
                await interaction.followup.send(f"✅ `{channel.mention}` 채널에 **{friendly_name}** 패널을 성공적으로 설치했습니다.", ephemeral=True)
            else:
                await interaction.followup.send(f"✅ **{friendly_name}**을(를) `{channel.mention}` 채널로 설정했습니다.", ephemeral=True)

        # --- 2. 역할 관련 로직 ---
        elif action == "roles_sync":
            # (이하 생략 - 이 부분은 변경 없음)
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
            # (이하 생략 - 이 부분은 변경 없음)
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
                stats_cog = self.bot.get_cog("StatsUpdater")
                if stats_cog: stats_cog.update_stats_loop.restart()
                await interaction.followup.send(f"✅ `{channel.name}` 채널에 통계 설정을 추가/수정했습니다.", ephemeral=True)

        elif action == "stats_refresh":
            stats_cog = self.bot.get_cog("StatsUpdater")
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
