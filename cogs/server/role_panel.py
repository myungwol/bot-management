# cogs/server/role_panel.py
"""
역할 자동 부여 패널과 관련된 모든 기능을 담당하는 Cog입니다.
- 사용자는 드롭다운 메뉴를 통해 스스로에게 역할을 부여하거나 제거할 수 있습니다.
- 모든 패널과 역할 정보는 데이터베이스 설정을 기반으로 동적으로 생성됩니다.
"""
import discord
from discord.ext import commands
from discord import ui
import logging
from typing import Optional, List, Dict, Any, Set
import asyncio

from utils.database import get_id, save_panel_id, get_panel_id, get_embed_from_db, get_config

logger = logging.getLogger(__name__)

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 역할 선택 드롭다운 UI (사용자에게 임시로 보여짐)
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
class RoleSelectDropdown(ui.Select):
    """
    특정 카테고리에 속한 역할들을 보여주는 드롭다운 메뉴.
    사용자가 역할을 선택하면 즉시 적용/해제됩니다.
    """
    def __init__(self, member: discord.Member, category_roles: List[Dict[str, Any]], category_name: str):
        current_user_role_ids: Set[int] = {r.id for r in member.roles}
        options: List[discord.SelectOption] = []
        
        self.managed_role_ids: Set[int] = set()

        for role_info in category_roles:
            role_id_key = role_info.get('role_id_key')
            if not role_id_key:
                continue

            role_id = get_id(role_id_key)
            if role_id:
                options.append(discord.SelectOption(
                    label=role_info.get('label', '이름 없는 역할'),
                    value=str(role_id),
                    description=role_info.get('description'),
                    default=(role_id in current_user_role_ids)
                ))
                self.managed_role_ids.add(role_id)
            else:
                logger.warning(f"역할 패널: DB에서 '{role_id_key}'에 해당하는 역할 ID를 찾을 수 없어 드롭다운에 추가하지 못했습니다.")

        super().__init__(
            placeholder=f"{category_name}의 역할을 선택하세요 (다중 선택 가능)",
            min_values=0,
            max_values=len(options) if options else 1,
            options=options,
            disabled=not options
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        if not isinstance(interaction.user, discord.Member):
             await interaction.followup.send("❌ 오류가 발생했습니다: 멤버 정보를 찾을 수 없습니다.", ephemeral=True)
             return

        try:
            selected_ids = {int(value) for value in self.values}
            current_roles_set = set(interaction.user.roles)
            unmanaged_roles = [role for role in current_roles_set if role.id not in self.managed_role_ids]
            roles_to_set = unmanaged_roles
            for role_id in selected_ids:
                if role := interaction.guild.get_role(role_id):
                    roles_to_set.append(role)
            
            await interaction.user.edit(roles=roles_to_set, reason="역할 패널을 통한 역할 변경")
            
            message = await interaction.followup.send("✅ 역할이 성공적으로 업데이트되었습니다.", ephemeral=True, wait=True)
            await asyncio.sleep(5)
            await message.delete()
            
        except discord.Forbidden:
            logger.error("역할 패널: 역할 업데이트 실패. 봇의 역할이 대상 역할보다 낮거나 권한이 부족합니다.")
            await interaction.followup.send("❌ 역할 업데이트에 실패했습니다. 봇의 권한을 확인해주세요.", ephemeral=True)
        except Exception as e:
            logger.error(f"역할 패널 업데이트 중 예기치 않은 오류 발생: {e}", exc_info=True)
            await interaction.followup.send("❌ 처리 중에 오류가 발생했습니다. 잠시 후 다시 시도해주세요.", ephemeral=True)


# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 역할 카테고리 선택 View (채널에 항상 떠 있는 영구 View)
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
class PersistentCategorySelectView(ui.View):
    def __init__(self, panel_config: Dict[str, Any]):
        super().__init__(timeout=None)
        
        options = [
            discord.SelectOption(
                label=category.get('label', '이름 없는 카테고리'),
                value=category.get('id'),
                emoji=category.get('emoji'),
                description=category.get('description')
            )
            for category in panel_config.get("categories", []) if category.get('id') and category.get('label')
        ]
        
        category_select = ui.Select(
            placeholder="역할을 부여받을 카테고리를 선택하세요...",
            options=options,
            custom_id="persistent_role_category_select",
            disabled=not options
        )
        category_select.callback = self.on_category_select
        self.add_item(category_select)

    async def on_category_select(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        panel_configs = get_config("STATIC_AUTO_ROLE_PANELS", {})
        if not panel_configs or not isinstance(panel_configs, dict):
            await interaction.followup.send("❌ 역할 패널 설정이 올바르지 않습니다. 관리자에게 문의하세요.", ephemeral=True)
            return

        panel_config = next(iter(panel_configs.values()))
        selected_category_id = interaction.data["values"][0]
        category_info = next((c for c in panel_config.get("categories", []) if c.get('id') == selected_category_id), None)
        if not category_info:
            await interaction.followup.send("❌ 선택한 카테고리 정보를 찾을 수 없습니다.", ephemeral=True)
            return
            
        category_name = category_info.get('label', '알 수 없는 카테고리')
        category_roles = panel_config.get("roles", {}).get(selected_category_id, [])
        
        temp_view = ui.View(timeout=300)
        temp_view.add_item(RoleSelectDropdown(interaction.user, category_roles, category_name))
        await interaction.followup.send("아래 메뉴에서 원하는 역할을 모두 선택한 후, 메뉴 바깥쪽을 클릭하여 닫아주세요.", view=temp_view, ephemeral=True)


# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# RolePanel Cog
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
class RolePanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_config: Optional[Dict[str, Any]] = None
        logger.info("RolePanel Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        await self.load_configs()

    async def load_configs(self):
        panel_configs = get_config("STATIC_AUTO_ROLE_PANELS", {})
        if panel_configs and isinstance(panel_configs, dict):
            self.panel_config = next(iter(panel_configs.values()))
            logger.info("✅ 역할 패널 설정을 성공적으로 로드했습니다.")
        else:
            self.panel_config = None
            logger.warning("⚠️ DB에서 유효한 'STATIC_AUTO_ROLE_PANELS' 설정을 찾을 수 없습니다.")

    async def register_persistent_views(self):
        if self.panel_config:
            self.bot.add_view(PersistentCategorySelectView(self.panel_config))
            logger.info("✅ 역할 패널의 영구 View가 성공적으로 등록되었습니다.")
        else:
            logger.warning("⚠️ 역할 패널 설정이 없어 영구 View를 등록할 수 없습니다.")

    async def regenerate_panel(self, channel: Optional[discord.TextChannel] = None):
        if not self.panel_config:
            logger.error("❌ 역할 패널을 생성할 수 없습니다: DB에 설정 정보가 없습니다.")
            return

        panel_key = self.panel_config.get("panel_key", "default_role_panel")
        
        target_channel = channel
        if not target_channel:
            channel_id = get_id(self.panel_config.get('channel_key'))
            if not channel_id or not (target_channel := self.bot.get_channel(channel_id)):
                logger.warning(f"ℹ️ '{panel_key}' 패널 채널이 DB에 설정되지 않아 생성을 건너뜁니다.")
                return

        try:
            panel_info = get_panel_id(panel_key)
            if panel_info and (old_message_id := panel_info.get('message_id')):
                try:
                    old_message = await target_channel.fetch_message(old_message_id)
                    await old_message.delete()
                    logger.info(f"이전 역할 패널 메시지(ID: {old_message_id})를 삭제했습니다.")
                except (discord.NotFound, discord.Forbidden):
                    pass

            embed_data = await get_embed_from_db(self.panel_config.get('embed_key'))
            if not embed_data:
                logger.error(f"❌ '{self.panel_config.get('embed_key')}' 임베드 데이터를 찾을 수 없어 패널 생성을 중단합니다.")
                return
            
            embed = discord.Embed.from_dict(embed_data)
            view = PersistentCategorySelectView(self.panel_config)
            new_message = await target_channel.send(embed=embed, view=view)
            
            await save_panel_id(panel_key, new_message.id, target_channel.id)
            logger.info(f"✅ '{panel_key}' 패널을 #{target_channel.name} 채널에 성공적으로 새로 생성했습니다.")
            
        except discord.Forbidden:
             logger.error(f"❌ 역할 패널 생성 실패: #{target_channel.name} 채널에 메시지를 보내거나 삭제할 권한이 없습니다.")
        except Exception as e:
            logger.error(f"❌ '{panel_key}' 패널 처리 중 예기치 않은 오류 발생: {e}", exc_info=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(RolePanel(bot))
