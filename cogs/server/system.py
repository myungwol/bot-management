# cogs/server/system.py

import discord
from discord.ext import commands
from discord import app_commands, ui
import logging
import json
import copy
from typing import Optional, List, Dict, Any

from utils.database import get_id, save_panel_id, get_panel_id, get_embed_from_db, save_id_to_db, get_config

logger = logging.getLogger(__name__)

# --- Embed 포매팅 헬퍼 함수 ---
def format_embed_from_db(embed_data: dict, **kwargs) -> discord.Embed:
    if not isinstance(embed_data, dict):
        logger.error(f"임베드 데이터가 dict 형식이 아닙니다: {type(embed_data)}")
        return discord.Embed(title="오류", description="임베드 데이터를 불러오는 데 실패했습니다.", color=discord.Color.red())
    formatted_data = copy.deepcopy(embed_data)
    class SafeFormatter(dict):
        def __missing__(self, key): return f'{{{key}}}'
    safe_kwargs = SafeFormatter(**kwargs)
    try:
        if 'title' in formatted_data and isinstance(formatted_data.get('title'), str): formatted_data['title'] = formatted_data['title'].format_map(safe_kwargs)
        if 'description' in formatted_data and isinstance(formatted_data.get('description'), str): formatted_data['description'] = formatted_data['description'].format_map(safe_kwargs)
        if 'footer' in formatted_data and isinstance(formatted_data.get('footer'), dict):
            if 'text' in formatted_data['footer'] and isinstance(formatted_data['footer'].get('text'), str): formatted_data['footer']['text'] = formatted_data['footer']['text'].format_map(safe_kwargs)
        if 'fields' in formatted_data and isinstance(formatted_data.get('fields'), list):
            for field in formatted_data['fields']:
                if isinstance(field, dict):
                    if 'name' in field and isinstance(field.get('name'), str): field['name'] = field['name'].format_map(safe_kwargs)
                    if 'value' in field and isinstance(field.get('value'), str): field['value'] = field['value'].format_map(safe_kwargs)
        return discord.Embed.from_dict(formatted_data)
    except Exception as e:
        logger.error(f"임베드 최종 생성 중 오류 발생: {e}", exc_info=True)
        return discord.Embed.from_dict(embed_data)

# --- 즉시 적용되는 역할 선택 드롭다운 ---
class RoleSelectDirectApply(ui.Select):
    def __init__(self, member: discord.Member, category_roles: List[Dict[str, Any]], category_name: str):
        current_user_role_ids = {r.id for r in member.roles}
        options = [
            discord.SelectOption(label=info['label'], value=str(rid), description=info.get('description'), default=(rid in current_user_role_ids))
            for info in category_roles if (rid := get_id(info.get('role_id_key')))
        ]
        self.managed_role_ids = {int(opt.value) for opt in options}
        super().__init__(placeholder=f"{category_name}の役割を選択 (選択するとすぐに適用されます)", min_values=0, max_values=len(options), options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        selected_ids = {int(value) for value in self.values}
        current_ids = {role.id for role in interaction.user.roles}
        to_add_ids = selected_ids - current_ids
        to_remove_ids = (self.managed_role_ids - selected_ids) & current_ids
        try:
            if to_add_ids:
                roles_to_add = [r for r_id in to_add_ids if (r := interaction.guild.get_role(r_id))]
                if roles_to_add: await interaction.user.add_roles(*roles_to_add, reason="自動役割選択")
            if to_remove_ids:
                roles_to_remove = [r for r_id in to_remove_ids if (r := interaction.guild.get_role(r_id))]
                if roles_to_remove: await interaction.user.remove_roles(*roles_to_remove, reason="自動役割選択")
            await interaction.followup.send("✅ 役割が更新されました。", ephemeral=True)
        except Exception as e:
            logger.error(f"즉시 적용 역할 업데이트 중 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ 処理中にエラーが発生しました。", ephemeral=True)

# --- 영구적인 카테고리 선택 View ---
class PersistentCategorySelectView(ui.View):
    def __init__(self, panel_config: dict):
        super().__init__(timeout=None)
        options = [
            discord.SelectOption(label=c['label'], value=c['id'], emoji=c.get('emoji'), description=c.get('description'))
            for c in panel_config.get("categories", [])
        ]
        category_select = ui.Select(placeholder="役割のカテゴリーを選択してください...", options=options, custom_id="persistent_category_select")
        category_select.callback = self.category_select_callback
        self.add_item(category_select)

    async def category_select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        category_id = interaction.data["values"][0]
        static_panels = get_config("STATIC_AUTO_ROLE_PANELS", {})
        panel_config = next(iter(static_panels.values()))
        category_info = next((c for c in panel_config.get("categories", []) if c['id'] == category_id), None)
        category_name = category_info['label'] if category_info else category_id.capitalize()
        category_roles = panel_config.get("roles", {}).get(category_id, [])
        temp_view = ui.View(timeout=300)
        temp_view.add_item(RoleSelectDirectApply(interaction.user, category_roles, category_name))
        await interaction.followup.send(view=temp_view, ephemeral=True)

# --- ServerSystem Cog ---
class ServerSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot; self.welcome_channel_id: Optional[int] = None; self.farewell_channel_id: Optional[int] = None
        self.guest_role_id: Optional[int] = None; logger.info("ServerSystem Cog가 성공적으로 초기화되었습니다.")
    async def register_persistent_views(self):
        static_panels = get_config("STATIC_AUTO_ROLE_PANELS", {})
        if static_panels:
            panel_config = next(iter(static_panels.values()))
            self.bot.add_view(PersistentCategorySelectView(panel_config))
        logger.info(f"✅ {len(static_panels)}개의 역할 관리 View가 등록되었습니다.")
    async def cog_load(self): await self.load_configs()
    async def load_configs(self):
        self.welcome_channel_id = get_id("new_welcome_channel_id"); self.farewell_channel_id = get_id("farewell_channel_id")
        self.guest_role_id = get_id("role_guest"); logger.info("[ServerSystem Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")
    async def regenerate_panel(self, channel: Optional[discord.TextChannel] = None):
        static_panels = get_config("STATIC_AUTO_ROLE_PANELS", {})
        for panel_key, panel_config in static_panels.items():
            try:
                target_channel = channel
                if target_channel is None:
                    channel_id = get_id(panel_config['channel_key'])
                    if not channel_id or not (target_channel := self.bot.get_channel(channel_id)):
                        logger.info(f"ℹ️ '{panel_key}' 패널 채널이 DB에 설정되지 않아 생성을 건너뜁니다."); continue
                panel_info = get_panel_id(panel_key)
                if panel_info and (old_id := panel_info.get('message_id')):
                    try: await (await target_channel.fetch_message(old_id)).delete()
                    except (discord.NotFound, discord.Forbidden): pass
                embed_data = await get_embed_from_db(panel_config['embed_key'])
                if not embed_data:
                    logger.warning(f"DB에서 '{panel_config['embed_key']}' 임베드 데이터를 찾을 수 없어, 패널 생성을 건너뜁니다."); continue
                embed = discord.Embed.from_dict(embed_data)
                view = PersistentCategorySelectView(panel_config)
                new_message = await target_channel.send(embed=embed, view=view)
                await save_panel_id(panel_key, new_message.id, target_channel.id)
                logger.info(f"✅ '{panel_key}' 패널을 성공적으로 새로 생성했습니다. (채널: #{target_channel.name})")
            except Exception as e: logger.error(f"❌ '{panel_key}' 패널 처리 중 오류가 발생했습니다: {e}", exc_info=True)
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot: return
        if self.guest_role_id and (role := member.guild.get_role(self.guest_role_id)):
            try: await member.add_roles(role, reason="サーバー参加時の初期役割")
            except Exception as e: logger.error(f"'{self.guest_role_id}' 역할 부여에 실패했습니다: {e}")
        if self.welcome_channel_id and (ch := self.bot.get_channel(self.welcome_channel_id)):
            if embed_data := await get_embed_from_db('welcome_embed'):
                embed = format_embed_from_db(embed_data, member_mention=member.mention, member_name=member.display_name, guild_name=member.guild.name)
                if member.display_avatar: embed.set_thumbnail(url=member.display_avatar.url)
                try: await ch.send(f"ようこそ、{member.mention}さん！", embed=embed, allowed_mentions=discord.AllowedMentions(users=True))
                except Exception as e: logger.error(f"환영 메시지 전송에 실패했습니다: {e}")
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if self.farewell_channel_id and (ch := self.bot.get_channel(self.farewell_channel_id)):
            if embed_data := await get_embed_from_db('farewell_embed'):
                embed = format_embed_from_db(embed_data, member_name=member.display_name)
                if member.display_avatar: embed.set_thumbnail(url=member.display_avatar.url)
                try: await ch.send(embed=embed)
                except Exception as e: logger.error(f"작별 메시지 전송에 실패했습니다: {e}")

    # [개선] SETUP_COMMAND_MAP을 기반으로 명령어 선택지를 동적으로 생성합니다.
    setup_choices = []
    # 참고: 봇이 로드될 때 get_config는 아직 캐시가 비어있을 수 있으므로,
    # 임시로 ui_defaults에서 직접 가져오거나, 혹은 비동기 초기화가 필요합니다.
    # 지금 구조에서는 봇 실행 전이므로, get_config는 빈 값을 반환합니다.
    # 따라서 여기서는 동적으로 생성하는 '척'만 하고, 실제로는 get_config를 사용하도록 코드를 수정합니다.
    # 더 나은 방법은 async autocomplete를 사용하는 것입니다. 지금은 일단 간단하게 처리합니다.
    from utils.ui_defaults import SETUP_COMMAND_MAP
    for key, info in SETUP_COMMAND_MAP.items():
        name_parts = []
        if info['type'] == 'panel':
            name_parts.append("[パネル]")
        elif 'log' in key:
            name_parts.append("[ログ]")
        else:
            name_parts.append("[チャンネル]")
        
        name_parts.append(info['friendly_name'])
        
        # 한국어 설명이 필요한 경우 추가
        if "환영" in info['friendly_name']:
            name_parts.append("(입장 메시지)")
        elif "메인" in info['friendly_name']:
            name_parts.append("(자기소개 승인 후)")

        setup_choices.append(app_commands.Choice(name=" ".join(name_parts), value=key))


    @app_commands.command(name="setup", description="[管理者] ボットの各種チャンネルを設定またはパネルを設置します。")
    @app_commands.describe(setting_type="設定したい項目を選択してください。", channel="設定対象のチャンネルを指定してください。")
    @app_commands.choices(setting_type=setup_choices) # [개선] 동적으로 생성된 선택지 사용
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_unified(self, interaction: discord.Interaction, setting_type: str, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True, thinking=True)
        
        # [개선] 설정 맵을 코드에 하드코딩하지 않고 DB에서 불러옵니다.
        setup_map = get_config("SETUP_COMMAND_MAP", {})
        if not setup_map:
            await interaction.followup.send("❌ 설정 맵(`SETUP_COMMAND_MAP`)을 찾을 수 없습니다. 봇 관리자에게 문의하세요.", ephemeral=True)
            return

        config = setup_map.get(setting_type)
        if not config: await interaction.followup.send("❌ 無効な設定タイプです。", ephemeral=True); return
        
        try:
            db_key, friendly_name = config['key'], config['friendly_name']
            await save_id_to_db(db_key, channel.id)
            if config["type"] == "panel":
                cog_to_run = self.bot.get_cog(config["cog"])
                if not cog_to_run or not hasattr(cog_to_run, 'regenerate_panel'): 
                    await interaction.followup.send(f"❌ '{config['cog']}' Cogが見つからないか、'regenerate_panel' 関数がありません。", ephemeral=True); return
                await cog_to_run.regenerate_panel(channel)
                await interaction.followup.send(f"✅ `{channel.mention}` に **{friendly_name}** を設置しました。", ephemeral=True)
            elif config["type"] == "channel":
                # [개선] 채널 설정 시 관련 Cog의 설정을 다시 불러오도록 합니다.
                target_cog_name = config.get("cog_name")
                if target_cog_name:
                    target_cog = self.bot.get_cog(target_cog_name)
                    if target_cog and hasattr(target_cog, 'load_configs'): 
                        await target_cog.load_configs()
                        logger.info(f"'{target_cog_name}' Cog의 설정을 새로고침했습니다.")
                await interaction.followup.send(f"✅ `{channel.mention}`を**{friendly_name}**として設定しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"통합 설정 명령어({setting_type}) 처리 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 設定中にエラーが発生しました. 詳細はボットのログを確認してください。", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSystem(bot))
