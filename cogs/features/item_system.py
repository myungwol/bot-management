
# cogs/features/item_system.py
import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import List, Optional
from datetime import datetime, timezone

from utils.database import get_id, add_warning, get_total_warning_count, get_embed_from_db
from utils.ui_defaults import USABLE_ITEMS
from utils.helpers import format_embed_from_db

logger = logging.getLogger(__name__)

class ItemSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_id: Optional[int] = None
        logger.info("ItemSystem Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self):
        await self.load_configs()

    async def load_configs(self):
        self.log_channel_id = get_id("log_channel_item")
        logger.info("[ItemSystem Cog] 데이터베이스로부터 설정을 성공적으로 로드했습니다.")
        
    async def item_autocomplete(self, interaction: discord.Interaction, current: str) -> List[app_commands.Choice[str]]:
        """사용자가 보유한 아이템만 자동완성 목록에 보여줍니다."""
        choices = []
        if not isinstance(interaction.user, discord.Member):
            return []
            
        member_role_ids = {role.id for role in interaction.user.roles}
        
        for role_key, item_info in USABLE_ITEMS.items():
            role_id = get_id(role_key)
            if role_id in member_role_ids:
                if current.lower() in item_info['name'].lower():
                    choices.append(app_commands.Choice(name=item_info['name'], value=role_key))
        return choices

    @app_commands.command(name="item", description="保有しているアイテムを使用します。")
    @app_commands.describe(action="使用するアイテムを選択してください。")
    @app_commands.autocomplete(action=item_autocomplete)
    async def use_item(self, interaction: discord.Interaction, action: str):
        await interaction.response.defer(ephemeral=True)
        
        member = interaction.user
        if not isinstance(member, discord.Member):
            return # defer 후에는 응답할 수 없으므로 그냥 종료
        
        item_key = action
        item_info = USABLE_ITEMS.get(item_key)
        
        # 1. 유효한 아이템인지, 유저가 보유하고 있는지 확인
        if not item_info:
            return await interaction.followup.send("❌ 無効なアイテムです。", ephemeral=True)
            
        item_role_id = get_id(item_key)
        item_role = interaction.guild.get_role(item_role_id)
        
        if not item_role or item_role not in member.roles:
            return await interaction.followup.send(f"❌ アイテム「{item_info['name']}」を所持していません。", ephemeral=True)
            
        # 2. 아이템 종류에 따라 로직 분기
        if item_info['type'] == 'warning_deduction':
            await self.use_warning_deduction_ticket(interaction, member, item_role, item_info)
        else:
            await interaction.followup.send("❌ このアイテムは現在使用できません。", ephemeral=True)

    async def use_warning_deduction_ticket(self, interaction: discord.Interaction, member: discord.Member, item_role: discord.Role, item_info: dict):
        """경고 차감권 사용 로직"""
        
        # 0. 현재 경고 횟수 확인 (0이면 사용할 수 없음)
        current_warnings = await get_total_warning_count(member.id, interaction.guild_id)
        if current_warnings <= 0:
            return await interaction.followup.send(f"✅ 累積警告が0回なので、「{item_info['name']}」を使用する必要はありません。", ephemeral=True)
            
        try:
            # 1. 아이템(역할) 제거
            await member.remove_roles(item_role, reason=f"「{item_info['name']}」アイテム使用")

            # 2. 경고 차감 기록 추가 (음수 값으로 기록)
            deduction_amount = item_info['value']
            await add_warning(
                guild_id=interaction.guild_id,
                user_id=member.id,
                moderator_id=self.bot.user.id, # 봇 자신이 실행
                reason=f"「{item_info['name']}」アイテム使用",
                amount=deduction_amount
            )

            # 3. 새로운 경고 횟수에 맞춰 역할 업데이트
            new_total = await get_total_warning_count(member.id, interaction.guild_id)
            warning_cog = self.bot.get_cog("WarningSystem")
            if warning_cog:
                await warning_cog.update_warning_roles(member, new_total)
            
            # 4. 로그 남기기
            await self.send_log_message(member, item_info['name'], new_total)
            
            # 5. 사용자에게 성공 메시지 전송
            await interaction.followup.send(f"✅ アイテム「{item_info['name']}」を使用しました！ (累積警告: {current_warnings}回 → {new_total}回)", ephemeral=True)

        except discord.Forbidden:
            await interaction.followup.send("❌ 役割の変更中にエラーが発生しました。ボットの権限が不足している可能性があります。", ephemeral=True)
        except Exception as e:
            logger.error(f"아이템 사용 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send("❌ アイテムの使用中に予期せぬエラーが発生しました。", ephemeral=True)

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


async def setup(bot: commands.Bot):
    await bot.add_cog(ItemSystem(bot))
