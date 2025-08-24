# cogs/server/role_panel.py

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
                    label=role_info.get('label', '名前のない役割'),
                    value=str(role_id),
                    description=role_info.get('description'),
                    default=(role_id in current_user_role_ids)
                ))
                self.managed_role_ids.add(role_id)
            else:
                logger.warning(f"役割パネル: DBで '{role_id_key}' に該当する役割IDが見つからなかったため、ドロップダウンに追加できませんでした。")

        super().__init__(
            placeholder=f"{category_name}の役割を選択してください (複数選択可能)",
            min_values=0,
            max_values=len(options) if options else 1,
            options=options,
            disabled=not options
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        if not isinstance(interaction.user, discord.Member):
             await interaction.followup.send("❌ エラーが発生しました: メンバー情報が見つかりません。", ephemeral=True)
             return

        try:
            selected_ids = {int(value) for value in self.values}
            current_roles_set = set(interaction.user.roles)
            unmanaged_roles = [role for role in current_roles_set if role.id not in self.managed_role_ids]
            roles_to_set = unmanaged_roles
            for role_id in selected_ids:
                if role := interaction.guild.get_role(role_id):
                    roles_to_set.append(role)
            
            await interaction.user.edit(roles=roles_to_set, reason="役割パネルによる役割変更")
            
            message = await interaction.followup.send("✅ 役割が正常に更新されました。", ephemeral=True, wait=True)
            await asyncio.sleep(5)
            await message.delete()
            
        except discord.Forbidden:
            logger.error("役割パネル: 役割の更新に失敗。ボットの役割が対象の役割より低いか、権限が不足しています。")
            await interaction.followup.send("❌ 役割の更新に失敗しました。ボットの権限を確認してください。", ephemeral=True)
        except Exception as e:
            logger.error(f"役割パネルの更新中に予期せぬエラーが発生しました: {e}", exc_info=True)
            await interaction.followup.send("❌ 処理中にエラーが発生しました。しばらくしてからもう一度お試しください。", ephemeral=True)

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# 역할 카테고리 선택 View (채널에 항상 떠 있는 영구 View)
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
class PersistentCategorySelectView(ui.View):
    def __init__(self, panel_config: Dict[str, Any]):
        super().__init__(timeout=None)
        self.panel_config = panel_config
        
        options = [
            discord.SelectOption(
                label=category.get('label', '名前のないカテゴリー'),
                value=category.get('id'),
                emoji=category.get('emoji'),
                description=category.get('description')
            )
            for category in self.panel_config.get("categories", []) if category.get('id') and category.get('label')
        ]
        
        category_select = ui.Select(
            placeholder="役割を付与されるカテゴリーを選択してください...",
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
            await interaction.followup.send("❌ 役職パネルの設定が正しくありません。管理者に問い合わせてください。", ephemeral=True)
            return

        # [수정] 여러 패널이 있을 수 있으므로, 현재 View의 설정과 일치하는 설정을 찾습니다.
        panel_key = self.panel_config.get("panel_key")
        panel_config = panel_configs.get(panel_key)

        if not panel_config:
             await interaction.followup.send("❌ 役職パネルの設定が見つかりませんでした。", ephemeral=True)
             return

        selected_category_id = interaction.data["values"][0]
        category_info = next((c for c in panel_config.get("categories", []) if c.get('id') == selected_category_id), None)
        if not category_info:
            await interaction.followup.send("❌ 選択したカテゴリーの情報が見つかりませんでした。", ephemeral=True)
            return
            
        category_name = category_info.get('label', '不明なカテゴリー')
        category_roles = panel_config.get("roles", {}).get(selected_category_id, [])
        
        temp_view = ui.View(timeout=300)
        temp_view.add_item(RoleSelectDropdown(interaction.user, category_roles, category_name))
        await interaction.followup.send("下のメニューから希望の役割をすべて選択した後、メニューの外側をクリックして閉じてください。", view=temp_view, ephemeral=True)

# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# RolePanel Cog
# =-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
class RolePanel(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_configs: Optional[Dict[str, Any]] = None
        logger.info("RolePanel Cog가 성공적으로 초기화되었습니다。")

    async def cog_load(self):
        await self.load_configs()

    async def load_configs(self):
        self.panel_configs = get_config("STATIC_AUTO_ROLE_PANELS", {})
        if self.panel_configs:
            logger.info("✅ 역할 패널 설정을 성공적으로 로드했습니다。")
        else:
            logger.warning("⚠️ DB에서 유효한 'STATIC_AUTO_ROLE_PANELS' 설정을 찾을 수 없습니다。")

    async def register_persistent_views(self):
        if self.panel_configs and isinstance(self.panel_configs, dict):
            for config in self.panel_configs.values():
                self.bot.add_view(PersistentCategorySelectView(config))
            logger.info(f"✅ {len(self.panel_configs)}개의 역할 패널 영구 View가 성공적으로 등록되었습니다。")
        else:
            logger.warning("⚠️ 역할 패널 설정이 없어 영구 View를 등록할 수 없습니다。")

    # [✅✅✅ 핵심 수정 ✅✅✅]
    # 함수가 panel_key를 인자로 받도록 변경하고, 내부 로직을 수정합니다.
    async def regenerate_panel(self, channel: discord.TextChannel, panel_key: str = "panel_roles") -> bool:
        if not self.panel_configs:
            logger.error("❌ 역할 패널을 생성할 수 없습니다: DB에 설정 정보가 없습니다。")
            return False
        
        # 전달받은 panel_key를 사용하여 정확한 설정을 찾습니다.
        panel_config = self.panel_configs.get(panel_key)
        if not panel_config:
            logger.error(f"❌ 역할 패널 설정에서 '{panel_key}'에 대한 구성을 찾을 수 없습니다.")
            return False

        # DB에서 패널 ID를 찾을 때도 base key를 사용합니다 (예: "panel_roles" -> "roles")
        base_panel_key = panel_key.replace("panel_", "")
        
        try:
            panel_info = get_panel_id(base_panel_key)
            if panel_info and (old_message_id := panel_info.get('message_id')):
                try:
                    old_message = await channel.fetch_message(old_message_id)
                    await old_message.delete()
                except (discord.NotFound, discord.Forbidden): pass
            
            embed_key = panel_config.get('embed_key')
            if not embed_key:
                logger.error(f"❌ '{panel_key}' 설정에 'embed_key'가 지정되지 않았습니다.")
                return False

            embed_data = await get_embed_from_db(embed_key)
            if not embed_data:
                logger.error(f"❌ '{embed_key}' 임베드 데이터를 찾을 수 없어 패널 생성을 중단합니다。")
                return False
            
            embed = discord.Embed.from_dict(embed_data)
            view = PersistentCategorySelectView(panel_config)
            new_message = await channel.send(embed=embed, view=view)
            
            await save_panel_id(base_panel_key, new_message.id, channel.id)
            logger.info(f"✅ '{panel_key}' 패널을 #{channel.name} 채널에 성공적으로 새로 생성했습니다。")
            return True
        except Exception as e:
            logger.error(f"❌ '{panel_key}' 패널 처리 중 예기치 않은 오류 발생: {e}", exc_info=True)
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(RolePanel(bot))
