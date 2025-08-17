# cogs/server/role_panel.py

import discord
from discord.ext import commands
from discord import ui
import logging
from typing import Optional, List, Dict, Any

from utils.database import get_id, save_panel_id, get_panel_id, get_embed_from_db, get_config

logger = logging.getLogger(__name__)

# --- 즉시 적용되는 역할 선택 드롭다운 ---
class RoleSelectDirectApply(ui.Select):
    def __init__(self, member: discord.Member, category_roles: List[Dict[str, Any]], category_name: str):
        current_user_role_ids = {r.id for r in member.roles}
        options = []
        for info in category_roles:
            role_id_key = info.get('role_id_key')
            if role_id_key and (rid := get_id(role_id_key)):
                 options.append(discord.SelectOption(label=info['label'], value=str(rid), description=info.get('description'), default=(rid in current_user_role_ids)))

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
        # 참고: 현재 설정에서는 패널이 하나뿐이라고 가정합니다.
        if not static_panels:
            await interaction.followup.send("❌ 역할 패널 설정 정보를 찾을 수 없습니다.", ephemeral=True)
            return
            
        panel_config = next(iter(static_panels.values()))
        category_info = next((c for c in panel_config.get("categories", []) if c['id'] == category_id), None)
        
        category_name = category_info['label'] if category_info else category_id.capitalize()
        category_roles = panel_config.get("roles", {}).get(category_id, [])
        
        temp_view = ui.View(timeout=300)
        temp_view.add_item(RoleSelectDirectApply(interaction.user, category_roles, category_name))
        await interaction.followup.send(view=temp_view, ephemeral=True)


class RolePanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("RolePanel Cog가 성공적으로 초기화되었습니다.")

    # 봇이 켜질 때 영구 View를 등록합니다.
    async def register_persistent_views(self):
        static_panels = get_config("STATIC_AUTO_ROLE_PANELS", {})
        if static_panels:
            # 여러 개의 자동 역할 패널이 있을 수 있지만, 현재 로직은 첫 번째 패널 설정만 사용합니다.
            panel_config = next(iter(static_panels.values()))
            self.bot.add_view(PersistentCategorySelectView(panel_config))
        logger.info(f"✅ {len(static_panels)}개의 역할 관리 View가 등록되었습니다.")

    # /setup 명령어로 패널을 (재)생성할 때 호출됩니다.
    async def regenerate_panel(self, channel: Optional[discord.TextChannel] = None):
        static_panels = get_config("STATIC_AUTO_ROLE_PANELS", {})
        for panel_key, panel_config in static_panels.items():
            try:
                target_channel = channel
                if target_channel is None:
                    channel_id = get_id(panel_config.get('channel_key'))
                    if not channel_id or not (target_channel := self.bot.get_channel(channel_id)):
                        logger.info(f"ℹ️ '{panel_key}' 패널 채널이 DB에 설정되지 않아 생성을 건너뜁니다."); continue
                
                panel_info = get_panel_id(panel_key)
                if panel_info and (old_id := panel_info.get('message_id')):
                    try:
                        old_message = await target_channel.fetch_message(old_id)
                        await old_message.delete()
                    except (discord.NotFound, discord.Forbidden):
                        pass

                embed_data = await get_embed_from_db(panel_config.get('embed_key'))
                if not embed_data:
                    logger.warning(f"DB에서 '{panel_config.get('embed_key')}' 임베드 데이터를 찾을 수 없어, 패널 생성을 건너뜁니다."); continue
                
                embed = discord.Embed.from_dict(embed_data)
                view = PersistentCategorySelectView(panel_config)
                new_message = await target_channel.send(embed=embed, view=view)
                await save_panel_id(panel_key, new_message.id, target_channel.id)
                logger.info(f"✅ '{panel_key}' 패널을 성공적으로 새로 생성했습니다. (채널: #{target_channel.name})")
            except Exception as e:
                logger.error(f"❌ '{panel_key}' 패널 처리 중 오류가 발생했습니다: {e}", exc_info=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(RolePanel(bot))
