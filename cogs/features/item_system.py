# cogs/features/item_system.py
import discord
from discord import ui
from discord.ext import commands
import logging
from typing import Optional, List, Tuple
from datetime import datetime, timezone
import asyncio

from utils.database import get_id, add_warning, get_total_warning_count, get_embed_from_db, get_panel_id, save_panel_id, get_panel_components_from_db
from utils.ui_defaults import USABLE_ITEMS
from utils.helpers import format_embed_from_db

logger = logging.getLogger(__name__)

class ItemSelectDropdown(ui.Select):
    def __init__(self, cog: 'ItemSystem', member: discord.Member):
        self.cog = cog
        options: List[discord.SelectOption] = []
        member_role_ids = {role.id for role in member.roles}
        
        for role_key, item_info in USABLE_ITEMS.items():
            role_id = get_id(role_key)
            if role_id in member_role_ids:
                options.append(discord.SelectOption(
                    label=item_info['name'],
                    value=role_key,
                    description=item_info.get('description')
                ))

        super().__init__(
            placeholder="使用するアイテムを選択してください...",
            options=options,
            disabled=not options
        )

    # [✅✅✅ 핵심 수정 ✅✅✅]
    # 아이템 사용 흐름 전체를 재구성하여 요청사항을 반영합니다.
    async def callback(self, interaction: discord.Interaction):
        # 1. 드롭다운 메시지를 즉시 삭제합니다.
        await interaction.response.defer(ephemeral=True)
        try:
            await interaction.delete_original_response()
        except discord.HTTPException:
            pass

        member = interaction.user
        item_key = self.values[0]
        item_info = USABLE_ITEMS.get(item_key)
        item_role = interaction.guild.get_role(get_id(item_key))

        if not all([isinstance(member, discord.Member), item_info, item_role]):
            message = await interaction.followup.send("❌ アイテムの使用中にエラーが発生しました。", ephemeral=True, wait=True)
            self.cog.bot.loop.create_task(self.cog.delete_message_after_delay(message, 3))
            return

        # 2. 아이템 사용 로직을 실행하고, 결과(성공 여부, 메시지 내용)를 받습니다.
        if item_info['type'] == 'warning_deduction':
            success, message_content = await self.cog.use_warning_deduction_ticket(interaction, member, item_role, item_info)
            
            # 3. 아이템 사용에 성공했다면, 패널을 즉시 재생성합니다.
            if success:
                await self.cog.regenerate_panel(interaction.channel, panel_key="panel_item_usage")

            # 4. 결과 메시지를 3초간 보여주고 삭제하는 작업을 예약합니다.
            message = await interaction.followup.send(message_content, ephemeral=True, wait=True)
            self.cog.bot.loop.create_task(self.cog.delete_message_after_delay(message, 3))

        else:
            message = await interaction.followup.send("❌ このアイテムは現在使用できません。", ephemeral=True, wait=True)
            self.cog.bot.loop.create_task(self.cog.delete_message_after_delay(message, 5))

class ItemUsagePanelView(ui.View):
    def __init__(self, cog: 'ItemSystem'):
        super().__init__(timeout=None)
        self.cog = cog

    async def setup_buttons(self):
        self.clear_items()
        components = await get_panel_components_from_db("item_usage")
        if not components: return
        
        button_info = components[0]
        button = ui.Button(
            label=button_info.get('label'),
            style=discord.ButtonStyle.success,
            emoji=button_info.get('emoji'),
            custom_id=button_info.get('component_key')
        )
        button.callback = self.on_button_click
        self.add_item(button)
        
    async def on_button_click(self, interaction: discord.Interaction):
        if not isinstance(interaction.user, discord.Member):
            return
            
        view = ui.View(timeout=180)
        dropdown = ItemSelectDropdown(self.cog, interaction.user)
        
        if not dropdown.options:
            return await interaction.response.send_message("ℹ️ 使用できるアイテムを所持していません。", ephemeral=True)
            
        view.add_item(dropdown)
        await interaction.response.send_message("どのアイテムを使用しますか？", view=view, ephemeral=True)


class ItemSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_channel_id: Optional[int] = None
        self.log_channel_id: Optional[int] = None
        self.view_instance: Optional[ItemUsagePanelView] = None
        logger.info("ItemSystem Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        await self.load_configs()
        
    async def register_persistent_views(self):
        self.view_instance = ItemUsagePanelView(self)
        await self.view_instance.setup_buttons()
        self.bot.add_view(self.view_instance)
        logger.info("✅ 아이템 시스템의 영구 View가 성공적으로 등록되었습니다.")
        
    async def load_configs(self):
        self.panel_channel_id = get_id("item_usage_panel_channel_id")
        self.log_channel_id = get_id("log_channel_item")
        logger.info("[ItemSystem Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")

    # [✅ 추가] 메시지를 일정 시간 뒤에 삭제하는 헬퍼 함수
    async def delete_message_after_delay(self, message: discord.InteractionMessage, delay: int):
        await asyncio.sleep(delay)
        try:
            await message.delete()
        except discord.NotFound:
            pass # 유저가 이미 메시지를 닫은 경우
        except Exception as e:
            logger.warning(f"아이템 사용 확인 메시지 삭제 중 오류: {e}")

    # [✅✅✅ 핵심 수정 ✅✅✅]
    # 함수가 UI(메시지 보내기, sleep)를 직접 제어하지 않고,
    # 순수하게 로직만 처리한 뒤 결과(성공여부, 메시지 내용)를 반환하도록 변경합니다.
    async def use_warning_deduction_ticket(self, interaction: discord.Interaction, member: discord.Member, item_role: discord.Role, item_info: dict) -> Tuple[bool, str]:
        current_warnings = await get_total_warning_count(member.id, interaction.guild_id)
        if current_warnings <= 0:
            message_content = f"✅ 累積警告が0回なので、「{item_info['name']}」を使用する必要はありません。"
            return False, message_content
            
        try:
            await member.remove_roles(item_role, reason=f"「{item_info['name']}」アイテム使用")
            await add_warning(
                guild_id=interaction.guild_id,
                user_id=member.id,
                moderator_id=self.bot.user.id,
                reason=f"「{item_info['name']}」アイテム使用",
                amount=item_info['value']
            )
            new_total = await get_total_warning_count(member.id, interaction.guild_id)
            if warning_cog := self.bot.get_cog("WarningSystem"):
                await warning_cog.update_warning_roles(member, new_total)
            
            await self.send_log_message(member, item_info['name'], new_total)
            
            message_content = f"✅ アイテム「{item_info['name']}」を使用しました！ (累積警告: {current_warnings}回 → {new_total}回)"
            return True, message_content
            
        except discord.Forbidden:
            return False, "❌ 役割の変更中にエラーが発生しました。ボットの権限が不足している可能性があります。"
        except Exception as e:
            logger.error(f"아이템 사용 중 오류 발생: {e}", exc_info=True)
            return False, "❌ アイテムの使用中に予期せぬエラーが発生しました。"

    async def send_log_message(self, member: discord.Member, item_name: str, new_total_warnings: int):
        if not self.log_channel_id: return
        log_channel = self.bot.get_channel(self.log_channel_id)
        if not log_channel: return
        
        embed_data = await get_embed_from_db("log_item_use")
        if not embed_data: return
        
        embed = format_embed_from_db(embed_data)
        embed.description = f"{member.mention}さんが**「{item_name}」**を使用しました。"
        embed.add_field(name="結果", value=f"累積警告が **{new_total_warnings}回** に変更されました。", inline=False)
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url if member.display_avatar else None)
        embed.timestamp = datetime.now(timezone.utc)
        await log_channel.send(embed=embed)

    async def regenerate_panel(self, channel: discord.TextChannel, panel_key: str = "panel_item_usage") -> bool:
        base_panel_key = panel_key.replace("panel_", "")
        embed_key = panel_key
        
        if not channel:
            logger.warning(f"아이템 사용 패널 채널을 찾을 수 없어 재생성할 수 없습니다.")
            return False

        try:
            panel_info = get_panel_id(base_panel_key)
            if panel_info and (old_id := panel_info.get('message_id')):
                try:
                    old_message = await channel.fetch_message(old_id)
                    await old_message.delete()
                except (discord.NotFound, discord.Forbidden): pass
            
            embed_data = await get_embed_from_db(embed_key)
            if not embed_data:
                logger.error(f"DB에서 '{embed_key}' 임베드를 찾을 수 없어 패널을 생성할 수 없습니다.")
                return False
                
            embed = discord.Embed.from_dict(embed_data)
            if self.view_instance is None:
                self.view_instance = ItemUsagePanelView(self)
            await self.view_instance.setup_buttons()
            
            new_message = await channel.send(embed=embed, view=self.view_instance)
            await save_panel_id(base_panel_key, new_message.id, channel.id)
            logger.info(f"✅ 아이템 사용 패널을 성공적으로 새로 생성했습니다. (채널: #{channel.name})")
            return True
        except Exception as e:
            logger.error(f"❌ {panel_key} 패널 재설치 중 오류 발생: {e}", exc_info=True)
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(ItemSystem(bot))
