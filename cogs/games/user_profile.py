# cogs/games/user_profile.py (최종 수정본 - 제작 중인 기능 안내 추가)

import discord
from discord.ext import commands
from discord import app_commands, ui
from math import ceil
import logging

# 로깅 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

from utils.database import (get_wallet, get_inventory, get_aquarium,
                            get_user_gear, set_user_gear, CURRENCY_ICON,
                            ROLE_PREFIX_MAPPING, ITEM_DATABASE, ROD_HIERARCHY,
                            save_panel_id, get_panel_id,
                            get_channel_id_from_db)

# [수정] 다시 "農業", "ペット" 카테고리를 추가합니다.
CATEGORIES = ["プロフィール", "装備", "アイテム", "魚", "農業", "ペット"]

class GearSelectView(ui.View):
    def __init__(self, user: discord.User, gear_type: str, refresh_callback, inventory_data: dict):
        super().__init__(timeout=180)
        self.user = user
        self.gear_type = gear_type
        self.refresh_callback = refresh_callback
        options = []
        if self.gear_type == "rod":
            options.append(discord.SelectOption(label="古い釣竿", emoji=ITEM_DATABASE.get("古い釣竿", {}).get('emoji', '🎣')))
            for rod_name in ROD_HIERARCHY:
                if rod_name != "古い釣竿" and inventory_data.get(rod_name, 0) > 0:
                    options.append(discord.SelectOption(label=rod_name, emoji=ITEM_DATABASE.get(rod_name, {}).get('emoji', '🎣')))
        elif self.gear_type == "bait":
            for item_name in ["一般の釣りエサ", "高級釣りエサ"]:
                if inventory_data.get(item_name, 0) > 0:
                    options.append(discord.SelectOption(label=item_name, emoji=ITEM_DATABASE.get(item_name, {}).get('emoji', '🐛')))
            options.append(discord.SelectOption(label="エサなし", value="エサなし", emoji="🚫", description="エサを外します。"))

        if not options:
            options.append(discord.SelectOption(label="選択できるアイテムがありません。", value="disabled", default=True))

        select_menu = ui.Select(placeholder=f"装備する{'釣竿' if self.gear_type == 'rod' else 'エサ'}を選択してください...", options=options, disabled=(len(options) == 1 and options[0].value == "disabled"))
        select_menu.callback = self.select_callback
        self.add_item(select_menu)

    async def select_callback(self, i: discord.Interaction):
        if i.user.id != self.user.id:
            await i.response.send_message("自分専用のメニューを操作してください。", ephemeral=True)
            return

        selected_item = i.data['values'][0]
        user_id_str = str(self.user.id)
        try:
            if self.gear_type == "rod":
                await set_user_gear(user_id_str, rod=selected_item)
            elif self.gear_type == "bait":
                await set_user_gear(user_id_str, bait=selected_item)

            await i.response.edit_message(content=f"✅ `{selected_item}`を装備しました！", view=None)
            self.stop()
            if self.refresh_callback:
                await self.refresh_callback()
        except Exception as e:
            logger.error(f"Error selecting gear for {self.user.display_name}: {e}", exc_info=True)
            await i.response.edit_message(content=f"エラーが発生しました: {e}", view=None)

class InventoryView(ui.View):
    def __init__(self, user: discord.Member):
        super().__init__(timeout=300)
        self.user = user
        self.current_category = CATEGORIES[0]
        self.fish_page = 1
        self.message: discord.WebhookMessage | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("自分専用のメニューを操作してください。", ephemeral=True)
            return False
        return True

    async def refresh_from_child(self):
        if self.message:
            try:
                embed, total_fish_pages = await self.get_page_embed()
                self.update_view_components(total_fish_pages=total_fish_pages)
                await self.message.edit(embed=embed, view=self)
            except Exception as e:
                logger.error(f"Error refreshing InventoryView from child: {e}", exc_info=True)

    def update_view_components(self, total_fish_pages: int = 1):
        self.clear_items()

        for i, category_name in enumerate(CATEGORIES):
            button_row = i // 5
            btn = ui.Button(
                label=category_name,
                style=discord.ButtonStyle.success if self.current_category == category_name else discord.ButtonStyle.secondary,
                custom_id=f"inv_category_{category_name}",
                row=button_row
            )
            btn.callback = self.category_button_callback
            self.add_item(btn)

        special_button_row = ceil(len(CATEGORIES) / 5)

        if self.current_category == "装備":
            rod_btn = ui.Button(label="🎣 釣竿を変更", style=discord.ButtonStyle.primary, row=special_button_row)
            bait_btn = ui.Button(label="🐛 エサを変更", style=discord.ButtonStyle.primary, row=special_button_row)
            rod_btn.callback = self.change_rod
            bait_btn.callback = self.change_bait
            self.add_item(rod_btn)
            self.add_item(bait_btn)

        if self.current_category == "魚":
            prev_btn = ui.Button(label="◀ 前のページ", style=discord.ButtonStyle.grey, row=special_button_row, disabled=(self.fish_page <= 1))
            next_btn = ui.Button(label="次のページ ▶", style=discord.ButtonStyle.grey, row=special_button_row, disabled=(self.fish_page >= total_fish_pages))
            prev_btn.callback = self.prev_fish_page
            next_btn.callback = self.next_fish_page
            self.add_item(prev_btn)
            self.add_item(next_btn)

    async def get_page_embed(self) -> tuple[discord.Embed, int]:
        category, user_id_str = self.current_category, str(self.user.id)
        embed = discord.Embed(title=f"📦 {self.user.display_name}様の持ち物 - 「{category}」", color=discord.Color.from_rgb(200, 200, 200))
        embed.set_thumbnail(url=self.user.display_avatar.url)
        total_fish_pages = 1

        if category == "プロフィール":
            wallet_data = await get_wallet(self.user.id)
            balance = wallet_data.get('balance', 0)
            embed.add_field(name="💰 所持金", value=f"`{balance:,}` {CURRENCY_ICON}", inline=False)

            highest_role_prefix = "役職なし"
            sorted_user_roles = sorted(self.user.roles, key=lambda r: r.position, reverse=True)
            for role in sorted_user_roles:
                if role.id in ROLE_PREFIX_MAPPING:
                    highest_role_prefix = ROLE_PREFIX_MAPPING[role.id]
                    break
            embed.add_field(name="📜 等級", value=f"`{highest_role_prefix}`", inline=False)

        elif category == "装備":
            user_gear = await get_user_gear(user_id_str)
            user_items = await get_inventory(user_id_str)
            rod_name = user_gear.get('rod', '素手')
            rod_count = user_items.get(rod_name, 0) if rod_name not in ["素手", "古い釣竿"] else 1
            bait_name = user_gear.get('bait', 'エサなし')
            bait_count = user_items.get(bait_name, 0)
            embed.add_field(name="🎣 装備中の釣竿", value=f"`{rod_name}` (`{rod_count}`個所持)", inline=False)
            embed.add_field(name="🐛 装備中のエサ", value=f"`{bait_name}` (`{bait_count}`個所持)", inline=False)
            embed.set_footer(text="ここで装備したアイテムが釣りの際に自動で使用されます。")
        elif category == "アイテム":
            user_items = await get_inventory(user_id_str)
            if user_items:
                item_list_str = ""
                for name, count in user_items.items():
                    emoji = ITEM_DATABASE.get(name, {}).get('emoji', '❓')
                    item_list_str += f"{emoji} **{name}** : `{count}`個\n"
                embed.description = item_list_str
            else:
                embed.description = "アイテムがありません。"
        elif category == "魚":
            user_fish = await get_aquarium(user_id_str)
            items_per_page = 5
            total_fish_pages = ceil(len(user_fish) / items_per_page) if user_fish else 1
            if self.fish_page > total_fish_pages: self.fish_page = total_fish_pages

            start_index = (self.fish_page - 1) * items_per_page
            page_fish = user_fish[start_index:start_index + items_per_page]

            if page_fish:
                fish_list_str = "".join([f"{f.get('emoji', '❓')} **{f['name']}** - `{f['size']}`cm\n" for f in page_fish])
                embed.description = fish_list_str
            else:
                embed.description = "水槽に魚がいません。"
            embed.set_footer(text=f"ページ {self.fish_page}/{total_fish_pages} | 合計 {len(user_fish)}匹")

        elif category == "農業":
            embed.description = "🌽 **農業機能は現在準備中です。**\n畑を耕し、作物を育てて収穫できるようになります。"
        elif category == "ペット":
            embed.description = "🐾 **ペット機能は現在準備中です。**\n可愛いペットを育て、一緒に冒険できるようになります。"
        else:
            embed.description = "現在、このカテゴリの情報はありません。"

        return embed, total_fish_pages

    async def update_message(self, i: discord.Interaction):
        embed, total_fish_pages = await self.get_page_embed()
        self.update_view_components(total_fish_pages=total_fish_pages)
        await i.response.edit_message(embed=embed, view=self)

    async def category_button_callback(self, i: discord.Interaction):
        new_category = i.data['custom_id'].split('_')[-1]
        if self.current_category != new_category:
            self.current_category = new_category
            self.fish_page = 1
        await self.update_message(i)

    async def change_rod(self, i: discord.Interaction):
        inv = await get_inventory(str(i.user.id))
        await i.response.send_message(view=GearSelectView(self.user, "rod", self.refresh_from_child, inv), ephemeral=True)

    async def change_bait(self, i: discord.Interaction):
        inv = await get_inventory(str(i.user.id))
        await i.response.send_message(view=GearSelectView(self.user, "bait", self.refresh_from_child, inv), ephemeral=True)

    async def prev_fish_page(self, i: discord.Interaction):
        if self.fish_page > 1:
            self.fish_page -= 1
        await self.update_message(i)

    async def next_fish_page(self, i: discord.Interaction):
        self.fish_page += 1
        await self.update_message(i)

class InventoryPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="📦 持ち物を開く", style=discord.ButtonStyle.blurple, custom_id="open_inventory_view_v3")
    async def open_inventory(self, i: discord.Interaction, b: ui.Button):
        await i.response.defer(ephemeral=True, thinking=True)
        try:
            member = i.guild.get_member(i.user.id)
            if not member:
                await i.followup.send("エラー: メンバー情報が見つかりません。", ephemeral=True)
                return

            view = InventoryView(member)
            embed, total_fish_pages = await view.get_page_embed()
            view.update_view_components(total_fish_pages=total_fish_pages)
            view.message = await i.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"Error opening inventory for {i.user.display_name}: {e}", exc_info=True)
            await i.followup.send(f"❌エラー\n`{e}`", ephemeral=True)


class UserProfile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(InventoryPanelView())
        self.inventory_panel_channel_id: int | None = None
        logger.info("UserProfile Cog initialized.")

    async def cog_load(self):
        await self.load_user_profile_channel_config()

    async def load_user_profile_channel_config(self):
        self.inventory_panel_channel_id = await get_channel_id_from_db("inventory_panel_channel_id")
        logger.info(f"[UserProfile Cog] Loaded INVENTORY_PANEL_CHANNEL_ID: {self.inventory_panel_channel_id}")

    async def regenerate_inventory_panel(self, channel: discord.TextChannel):
        old_id = await get_panel_id("inventory")
        if old_id:
            try:
                old_message = await channel.fetch_message(old_id)
                await old_message.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
                logger.warning(f"Failed to delete old inventory panel message {old_id}: {e}")
        embed = discord.Embed(title="📦 持ち物", description="下のボタンを押して、あなたの持ち物を開きます。", color=discord.Color.from_rgb(200, 200, 200))
        msg = await channel.send(embed=embed, view=InventoryPanelView())
        await save_panel_id("inventory", msg.id)
        logger.info(f"✅ Inventory パネルをチャンネル {channel.name} に設置しました。")

    @app_commands.command(name="持ち物パネル設置", description="持ち物を開くパネルをチャンネルに設置します。")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_inventory_panel_command(self, i: discord.Interaction):
        if self.inventory_panel_channel_id is None:
            await i.response.send_message("エラー: パネル設置チャンネルIDがまだ読み込まれていません。", ephemeral=True)
            return
        if i.channel.id != self.inventory_panel_channel_id:
            await i.response.send_message(f"このコマンドは <#{self.inventory_panel_channel_id}> でのみ使用できます。", ephemeral=True)
            return
        await i.response.defer(ephemeral=True)
        try:
            await self.regenerate_inventory_panel(i.channel)
            await i.followup.send("持ち物パネルを正常に設置しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"Error during inventory panel setup command: {e}", exc_info=True)
            await i.followup.send(f"❌ パネル設置中にエラーが発生しました: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    cog = UserProfile(bot)
    await bot.add_cog(cog)