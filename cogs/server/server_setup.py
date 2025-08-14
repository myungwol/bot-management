# cogs/server/server_setup.py

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import re
import logging

# 로깅 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)ss - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

from utils.database import save_channel_id_to_db, get_channel_id_from_db

# 새로 정의된 역할 구조
ROLE_STRUCTURE = {
    "職員": [
        ("里長", 0xFF0000, "staff_mayor"),
        ("助役", 0xFF5500, "staff_deputy"),
        ("お巡り", 0x0077FF, "staff_police"),
        ("祭りの委員", 0xFFBB00, "staff_festival"),
        ("広報係", 0xAAAA00, "staff_pr"),
        ("意匠係", 0x88CC00, "staff_design"),
        ("書記", 0xCCCCCC, "staff_clerk"),
        ("役場の職員", 0x888888, "staff_office"),
        ("職員", 0x555555, "staff_general"),
    ],
    "住民": [
        ("1等級住民", 0x990099, "resident_tier1"),
        ("2等級住民", 0xBB00BB, "resident_tier2"),
        ("3等級住民", 0xDD00DD, "resident_tier3"),
        ("住民", 0xEE00EE, "resident_general"),
        ("外部の人", 0xAAAAAA, "resident_outsider"), # '외부인'
    ],
    "情報": [
        ("男性", 0x00A0FF, "info_male"),
        ("女性", 0xFF66B2, "info_female"),
        ("非公開", 0x777777, "info_private"), # '비공개'
        ("70年代生まれ", 0x555555, "info_age_70s"), # '生' -> '生まれ'
        ("80年代生まれ", 0x666666, "info_age_80s"),
        ("90年代生まれ", 0x777777, "info_age_90s"),
        ("00年代生まれ", 0x888888, "info_age_00s"),
    ],
    "通知": [
        ("通話", 0x33FF33, "notify_voice"),
        ("友達", 0x33FFBB, "notify_friends"),
        ("ディスボード", 0x33BBFF, "notify_disboard"),
        ("アップ", 0x9999FF, "notify_up"),
    ],
    "ゲーム": [
        ("マインクラフト", 0xAAAAAA, "game_minecraft"),
        ("ヴァロラント", 0xAAAAAA, "game_valorant"),
        ("オーバーウォッチ", 0xAAAAAA, "game_overwatch"),
        ("リーグ・オブ・レジェンド", 0xAAAAAA, "game_lol"),
        ("麻雀", 0xAAAAAA, "game_mahjong"),
        ("アモングアス", 0xAAAAAA, "game_amongus"),
        ("モンスターハンター", 0xAAAAAA, "game_mh"), # 이름 수정
        ("原神", 0xAAAAAA, "game_genshin"),
        ("エーペックスレジェンズ", 0xAAAAAA, "game_apex"),
        ("スプラトゥーン", 0xAAAAAA, "game_splatoon"),
        ("ゴッドフィールド", 0xAAAAAA, "game_gf"),
        ("スチーム", 0xAAAAAA, "platform_steam"),
        ("スマートフォン", 0xAAAAAA, "platform_smartphone"),
        ("スイッチ", 0xAAAAAA, "platform_switch"),
    ]
}

class ServerSetup(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("ServerSetup Cog initialized (Roles-Only Mode).")

    async def _update_interaction_response(self, interaction: discord.Interaction, response_messages_list: list):
        description_content = "".join(response_messages_list)
        if len(description_content) > 4096:
            description_content = description_content[:4090] + "\n..."
        embed = discord.Embed(
            title="⚙️ Dico森 役割設定",
            description=description_content,
            color=discord.Color.blue()
        )
        embed.set_footer(text="このメッセージは自動的に更新されます。")
        try:
            await interaction.edit_original_response(embed=embed)
        except discord.HTTPException as e:
            logger.error(f"HTTP error during interaction response update: {e}", exc_info=True)

    async def _create_roles(self, guild: discord.Guild, interaction: discord.Interaction, response_messages_list: list):
        logger.info("[_create_roles] Role creation/update process started.")
        response_messages_list.append("\n\n**[ 役割の設置 ]**\n")
        await self._update_interaction_response(interaction, response_messages_list)

        for category_name, roles_data in ROLE_STRUCTURE.items():
            response_messages_list.append(f"\n**{category_name}**\n")
            logger.debug(f"[_create_roles] Processing role category: '{category_name}'")

            for role_name, color_hex, role_key in roles_data:
                logger.debug(f"[_create_roles] Starting to process role '{role_name}' (key: {role_key}).")
                existing_role = discord.utils.get(guild.roles, name=role_name)

                if existing_role:
                    response_messages_list.append(f"　✔️ 役割 **{role_name}** は既に存在します。(ID: `{existing_role.id}`)\n")
                    try:
                        await save_channel_id_to_db(f"role_{role_key}", existing_role.id)
                        logger.debug(f"[_create_roles] Successfully saved role ID for '{role_name}'.")
                    except Exception as db_e:
                        logger.error(f"[_create_roles] Failed to save role ID for '{role_name}' to DB: {db_e}", exc_info=True)
                        response_messages_list.append(f"　❌ 役割 **{role_name}** のDB保存に失敗しました: {db_e}\n")
                else:
                    try:
                        logger.info(f"[_create_roles] Attempting to create new role '{role_name}'...")
                        new_role = await guild.create_role(name=role_name, color=discord.Color(color_hex))
                        response_messages_list.append(f"　✅ 役割 **{role_name}** を作成しました。(ID: `{new_role.id}`)\n")
                        try:
                            await save_channel_id_to_db(f"role_{role_key}", new_role.id)
                            logger.debug(f"[_create_roles] Successfully saved new role ID for '{role_name}'.")
                        except Exception as db_e:
                            logger.error(f"[_create_roles] Failed to save new role ID for '{role_name}' to DB: {db_e}", exc_info=True)
                            response_messages_list.append(f"　❌ 新しい役割 **{role_name}** のDB保存に失敗しました: {db_e}\n")
                        await asyncio.sleep(0.5)
                    except discord.Forbidden:
                        logger.error(f"[_create_roles] Permission error creating role '{role_name}'. Bot lacks 'Manage Roles' permission.", exc_info=True)
                        response_messages_list.append(f"　❌ 役割 **{role_name}** の作成に失敗しました: 権限不足\n")
                    except Exception as e:
                        logger.error(f"[_create_roles] Unexpected error creating role '{role_name}': {e}", exc_info=True)
                        response_messages_list.append(f"　❌ 役割 **{role_name}** の作成に失敗しました: {e}\n")

            await self._update_interaction_response(interaction, response_messages_list)

        logger.info("[_create_roles] Role creation/update process finished.")

    @app_commands.command(name="役割設置", description="サーバーの役割を自動で設置します。")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def setup_command(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        guild = interaction.guild

        response_messages_list = ["⚙️ Dico森 サーバーの役割設定を開始します...\n"]
        await self._update_interaction_response(interaction, response_messages_list)

        logger.info("[setup_command] Initiating server setup (roles only).")

        await self._create_roles(guild, interaction, response_messages_list)

        response_messages_list.append("\n\n✅ 役割の設置が完了しました！")

        await self._update_interaction_response(interaction, response_messages_list)
        logger.info("[setup_command] Server role setup command completed.")

async def setup(bot: commands.Bot):
    await bot.add_cog(ServerSetup(bot))