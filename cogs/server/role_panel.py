# cogs/server/role_panel.py
import discord
from discord.ext import commands
from discord import ui
import logging
from typing import Optional, List, Dict, Any, Set
import asyncio

from utils.database import get_id, save_panel_id, get_panel_id, get_embed_from_db, get_config

logger = logging.getLogger(__name__)

class RoleSelectDropdown(ui.Select):
    def __init__(self, member: discord.Member, category_roles: List[Dict[str, Any]], category_name: str):
        current_user_role_ids: Set[int] = {r.id for r in member.roles}
        options: List[discord.SelectOption] = []
        self.managed_role_ids: Set[int] = set()
        for role_info in category_roles:
            role_id_key = role_info.get('role_id_key')
            if not role_id_key: continue
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
            min_values=0, max_values=len(options) if options else 1,
            options=options, disabled=not options
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

class PersistentCategorySelectView(ui.View):
    def __init__(self, panel_config: Dict[str, Any]):
        super().__init__(timeout=None)
        self.panel_config = panel_config
        options = [
            discord.SelectOption(
                label=category.get('label', '이름 없는 카테고리'),
                value=category.get('id'),
                emoji=category.get('emoji'),
                description=category.get('description')
            )
            for category in self.panel_config.get("categories", []) if category.get('id') and category.get('label')
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
        selected_category_id = interaction.data["values"][0]
        category_info = next((c for c in self.panel_config.get("categories", []) if c.get('id') == selected_category_id), None)
        if not category_info:
            await interaction.followup.send("❌ 선택한 카테고리 정보를 찾을 수 없습니다.", ephemeral=True)
            return
        category_name = category_info.get('label', '알 수 없는 카테고리')
        category_roles = self.panel_config.get("roles", {}).get(selected_category_id, [])
        temp_view = ui.View(timeout=300)
        temp_view.add_item(RoleSelectDropdown(interaction.user, category_roles, category_name))
        await interaction.followup.send("아래 메뉴에서 원하는 역할을 모두 선택한 후, 메뉴 바깥쪽을 클릭하여 닫아주세요.", view=temp_view, ephemeral=True)

class RolePanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_configs: Optional[Dict[str, Any]] = None
        logger.info("RolePanel Cog가 성공적으로 초기화되었습니다.")
    async def cog_load(self):
        await self.load_configs()
    async def load_configs(self):
        self.panel_configs = get_config("STATIC_AUTO_ROLE_PANELS", {})
        if self.panel_configs:
            logger.info("✅ 역할 패널 설정을 성공적으로 로드했습니다.")
        else:
            logger.warning("⚠️ DB에서 유효한 'STATIC_AUTO_ROLE_PANELS' 설정을 찾을 수 없습니다.")
    async def register_persistent_views(self):
        if self.panel_configs and isinstance(self.panel_configs, dict):
            for config in self.panel_configs.values():
                self.bot.add_view(PersistentCategorySelectView(config))
            logger.info(f"✅ {len(self.panel_configs)}개의 역할 패널 영구 View가 성공적으로 등록되었습니다.")
        else:
            logger.warning("⚠️ 역할 패널 설정이 없어 영구 View를 등록할 수 없습니다.")

    async def regenerate_panel(self, channel: discord.TextChannel) -> bool:
        if not self.panel_configs:
            logger.error("❌ 역할 패널을 생성할 수 없습니다: DB에 설정 정보가 없습니다.")
            return False
        
        # [수정] 이 Cog는 하나의 설정만 사용한다고 가정
        panel_config = next(iter(self.panel_configs.values()), None)
        if not panel_config: return False

        panel_key = panel_config.get("panel_key", "default_role_panel")
        
        try:
            panel_info = get_panel_id(panel_key)
            if panel_info and (old_message_id := panel_info.get('message_id')):
                try:
                    old_message = await channel.fetch_message(old_message_id)
                    await old_message.delete()
                except (discord.NotFound, discord.Forbidden): pass
            
            embed_data = await get_embed_from_db(panel_config.get('embed_key'))
            if not embed_data:
                logger.error(f"❌ '{panel_config.get('embed_key')}' 임베드 데이터를 찾을 수 없어 패널 생성을 중단합니다.")
                return False
            
            embed = discord.Embed.from_dict(embed_data)
            view = PersistentCategorySelectView(panel_config)
            new_message = await channel.send(embed=embed, view=view)
            await save_panel_id(panel_key, new_message.id, channel.id)
            logger.info(f"✅ '{panel_key}' 패널을 #{channel.name} 채널에 성공적으로 새로 생성했습니다.")
            return True
        except Exception as e:
            logger.error(f"❌ '{panel_key}' 패널 처리 중 예기치 않은 오류 발생: {e}", exc_info=True)
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(RolePanel(bot))
