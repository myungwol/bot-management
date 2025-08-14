# cogs/games/user_profile.py (자동 재생성 기능이 적용된 최종본)

import discord
from discord.ext import commands
from discord import app_commands, ui
from math import ceil
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from utils.database import (
    get_wallet, get_inventory, get_aquarium,
    get_user_gear, set_user_gear, CURRENCY_ICON,
    ROLE_PREFIX_MAPPING, ITEM_DATABASE, ROD_HIERARCHY,
    save_panel_id, get_panel_id,
    get_channel_id_from_db
)

CATEGORIES = ["プロフィール", "装備", "アイテム", "魚", "農業", "ペット"]

class GearSelectView(ui.View):
    def __init__(self, user: discord.User, gear_type: str, refresh_callback, inventory_data: dict):
        super().__init__(timeout=180)
        self.user = user; self.gear_type = gear_type; self.refresh_callback = refresh_callback; options = []
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
        select = ui.Select(placeholder=f"装備する{'釣竿' if self.gear_type == 'rod' else 'エサ'}を選択...", options=options, disabled=(len(options) == 1 and options[0].value == "disabled"))
        select.callback = self.select_callback; self.add_item(select)
    async def select_callback(self, i: discord.Interaction):
        if i.user.id != self.user.id:
            return await i.response.send_message("自分専用のメニューを操作してください。", ephemeral=True)
        selected = i.data['values'][0]
        try:
            if self.gear_type == "rod": await set_user_gear(str(self.user.id), rod=selected)
            elif self.gear_type == "bait": await set_user_gear(str(self.user.id), bait=selected)
            await i.response.edit_message(content=f"✅ `{selected}`を装備しました！", view=None); self.stop()
            if self.refresh_callback: await self.refresh_callback()
        except Exception as e:
            logger.error(f"Error selecting gear for {self.user.display_name}: {e}", exc_info=True)
            await i.response.edit_message(content=f"エラーが発生しました。", view=None)

class InventoryView(ui.View):
    def __init__(self, user: discord.Member):
        super().__init__(timeout=300); self.user = user
        self.current_category = CATEGORIES[0]; self.fish_page = 1; self.message: discord.WebhookMessage | None = None
    async def interaction_check(self, i: discord.Interaction) -> bool:
        if i.user.id != self.user.id: await i.response.send_message("自分専用のメニューを操作してください。", ephemeral=True); return False
        return True
    async def refresh_from_child(self):
        if self.message:
            try:
                embed, total_pages = await self.get_page_embed()
                self.update_view_components(total_fish_pages=total_pages)
                await self.message.edit(embed=embed, view=self)
            except Exception as e: logger.error(f"Error refreshing InventoryView from child: {e}", exc_info=True)
    def update_view_components(self, total_fish_pages: int = 1):
        self.clear_items()
        for i, cat_name in enumerate(CATEGORIES):
            btn = ui.Button(label=cat_name, style=discord.ButtonStyle.success if self.current_category == cat_name else discord.ButtonStyle.secondary, custom_id=f"inv_category_{cat_name}", row=i//5)
            btn.callback = self.category_button_callback; self.add_item(btn)
        special_row = ceil(len(CATEGORIES) / 5)
        if self.current_category == "装備":
            rod_btn = ui.Button(label="🎣 釣竿を変更", style=discord.ButtonStyle.primary, row=special_row)
            bait_btn = ui.Button(label="🐛 エサを変更", style=discord.ButtonStyle.primary, row=special_row)
            rod_btn.callback = self.change_rod; bait_btn.callback = self.change_bait; self.add_item(rod_btn); self.add_item(bait_btn)
        if self.current_category == "魚":
            prev_btn = ui.Button(label="◀", style=discord.ButtonStyle.grey, row=special_row, disabled=(self.fish_page <= 1))
            next_btn = ui.Button(label="▶", style=discord.ButtonStyle.grey, row=special_row, disabled=(self.fish_page >= total_fish_pages))
            prev_btn.callback = self.prev_fish_page; next_btn.callback = self.next_fish_page; self.add_item(prev_btn); self.add_item(next_btn)
    async def get_page_embed(self) -> tuple[discord.Embed, int]:
        cat, uid_str = self.current_category, str(self.user.id)
        embed = discord.Embed(title=f"📦 {self.user.display_name}様の持ち物 - 「{cat}」", color=discord.Color.from_rgb(200, 200, 200)); embed.set_thumbnail(url=self.user.display_avatar.url)
        total_pages = 1
        if cat == "プロフィール":
            balance = (await get_wallet(self.user.id)).get('balance', 0)
            embed.add_field(name="💰 所持金", value=f"`{balance:,}` {CURRENCY_ICON}", inline=False)
            prefix = "役職なし"
            for role in sorted(self.user.roles, key=lambda r: r.position, reverse=True):
                if role.id in ROLE_PREFIX_MAPPING: prefix = ROLE_PREFIX_MAPPING[role.id]; break
            embed.add_field(name="📜 等級", value=f"`{prefix}`", inline=False)
        elif cat == "装備":
            gear = await get_user_gear(uid_str); items = await get_inventory(uid_str)
            rod = gear.get('rod', '素手'); rod_count = items.get(rod, 0) if rod not in ["素手", "古い釣竿"] else 1
            bait = gear.get('bait', 'エサなし'); bait_count = items.get(bait, 0)
            embed.add_field(name="🎣 装備中の釣竿", value=f"`{rod}` (`{rod_count}`個所持)", inline=False)
            embed.add_field(name="🐛 装備中のエサ", value=f"`{bait}` (`{bait_count}`個所持)", inline=False)
            embed.set_footer(text="ここで装備したアイテムが釣りの際に自動で使用されます。")
        elif cat == "アイテム":
            items = await get_inventory(uid_str)
            embed.description = "".join([f"{ITEM_DATABASE.get(n, {}).get('emoji', '❓')} **{n}** : `{c}`個\n" for n, c in items.items()]) if items else "アイテムがありません。"
        elif cat == "魚":
            fishes = await get_aquarium(uid_str); per_page = 5
            total_pages = ceil(len(fishes) / per_page) if fishes else 1
            if self.fish_page > total_pages: self.fish_page = total_pages
            page_fishes = fishes[(self.fish_page-1)*per_page : self.fish_page*per_page]
            embed.description = "".join([f"{f.get('emoji', '❓')} **{f['name']}** - `{f['size']}`cm\n" for f in page_fishes]) if page_fishes else "水槽に魚がいません。"
            embed.set_footer(text=f"ページ {self.fish_page}/{total_pages} | 合計 {len(fishes)}匹")
        elif cat == "農業": embed.description = "🌽 **農業機能は現在準備中です。**"
        elif cat == "ペット": embed.description = "🐾 **ペット機能は現在準備中です。**"
        else: embed.description = "現在、このカテゴリの情報はありません。"
        return embed, total_pages
    async def update_message(self, i: discord.Interaction):
        embed, total_pages = await self.get_page_embed()
        self.update_view_components(total_fish_pages=total_pages)
        await i.response.edit_message(embed=embed, view=self)
    async def category_button_callback(self, i: discord.Interaction):
        new_cat = i.data['custom_id'].split('_')[-1]
        if self.current_category != new_cat: self.current_category = new_cat; self.fish_page = 1
        await self.update_message(i)
    async def change_rod(self, i: discord.Interaction):
        inv = await get_inventory(str(i.user.id)); await i.response.send_message(view=GearSelectView(self.user, "rod", self.refresh_from_child, inv), ephemeral=True)
    async def change_bait(self, i: discord.Interaction):
        inv = await get_inventory(str(i.user.id)); await i.response.send_message(view=GearSelectView(self.user, "bait", self.refresh_from_child, inv), ephemeral=True)
    async def prev_fish_page(self, i: discord.Interaction):
        if self.fish_page > 1: self.fish_page -= 1
        await self.update_message(i)
    async def next_fish_page(self, i: discord.Interaction):
        self.fish_page += 1
        await self.update_message(i)

class InventoryPanelView(ui.View):
    def __init__(self): super().__init__(timeout=None)
    @ui.button(label="📦 持ち物を開く", style=discord.ButtonStyle.blurple, custom_id="open_inventory_view_v3")
    async def open_inventory(self, i: discord.Interaction, b: ui.Button):
        await i.response.defer(ephemeral=True, thinking=True)
        try:
            member = i.guild.get_member(i.user.id) if i.guild else i.user
            view = InventoryView(member)
            embed, total_pages = await view.get_page_embed()
            view.update_view_components(total_fish_pages=total_pages)
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
    async def regenerate_panel(self):
        if self.inventory_panel_channel_id and (channel := self.bot.get_channel(self.inventory_panel_channel_id)):
            old_id = await get_panel_id("inventory")
            if old_id:
                try: (await channel.fetch_message(old_id)).delete()
                except (discord.NotFound, discord.Forbidden): pass
            embed = discord.Embed(title="📦 持ち物", description="下のボタンを押して、あなたの持ち物を開きます。", color=discord.Color.from_rgb(200, 200, 200))
            msg = await channel.send(embed=embed, view=InventoryPanelView())
            await save_panel_id("inventory", msg.id, channel.id)
            logger.info(f"✅ Inventory panel auto-regenerated in channel {channel.name}")
        else:
            logger.info("ℹ️ Inventory panel channel not set, skipping auto-regeneration.")
    @app_commands.command(name="持ち物パネル設置", description="持ち物を開くパネルをチャンネルに設置します。")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_inventory_panel_command(self, i: discord.Interaction):
        if not self.inventory_panel_channel_id:
            return await i.response.send_message("エラー: まず `/setup set-channel` で `inventory_panel_channel_id` を設定してください。", ephemeral=True)
        if i.channel.id != self.inventory_panel_channel_id:
            return await i.response.send_message(f"このコマンドは <#{self.inventory_panel_channel_id}> でのみ使用できます。", ephemeral=True)
        await i.response.defer(ephemeral=True)
        try:
            await self.regenerate_panel()
            await i.followup.send("持ち物パネルを正常に設置しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"Error during inventory panel setup command: {e}", exc_info=True)
            await i.followup.send(f"❌ パネル設置中にエラーが発生しました: {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(UserProfile(bot))
