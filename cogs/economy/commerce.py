# cogs/economy/commerce.py (명령어 통합 최종본)

import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from utils.database import (
    ITEM_DATABASE, FISHING_LOOT, CURRENCY_ICON, ROD_HIERARCHY,
    get_inventory, update_inventory, get_wallet, update_wallet,
    get_aquarium, remove_fish_from_aquarium,
    save_panel_id, get_panel_id,
    get_channel_id_from_db
)

SELL_CATEGORIES = ["魚", "アイテム"]
BUY_CATEGORIES = ["里の役職", "釣り", "農業", "牧場"]

class SellQuantityModal(ui.Modal, title="販売数量入力"):
    quantity = ui.TextInput(label="販売したい数量を入力してください", placeholder="例: 10", required=True, max_length=5)
    def __init__(self, item_name: str, max_quantity: int):
        super().__init__()
        self.item_name = item_name; self.max_quantity = max_quantity
        self.quantity.placeholder = f"最大 {max_quantity}個まで入力できます"; self.value = None
    async def on_submit(self, interaction: discord.Interaction):
        try:
            quantity_input = int(self.quantity.value)
            if not (1 <= quantity_input <= self.max_quantity):
                return await interaction.response.send_message(f"1から{self.max_quantity}までの数字を入力してください。", ephemeral=True)
            self.value = quantity_input; await interaction.response.defer()
        except ValueError: await interaction.response.send_message("数字のみ入力してください。", ephemeral=True)

class BuyQuantityModal(ui.Modal, title="購入数量入力"):
    quantity = ui.TextInput(label="購入したい数量を入力してください", placeholder="例: 10", required=True, max_length=5)
    def __init__(self, item_name: str, item_price: int, user_balance: int):
        super().__init__()
        self.item_name = item_name; self.item_price = item_price; self.user_balance = user_balance
        max_buyable = user_balance // item_price if item_price > 0 else 0
        self.max_buyable = max_buyable
        self.quantity.label = f"{item_name}の購入数量"
        self.quantity.placeholder = f"最大 {max_buyable}個まで購入可能です (所持金: {user_balance}{CURRENCY_ICON})"
        self.value = None
    async def on_submit(self, interaction: discord.Interaction):
        try:
            quantity_input = int(self.quantity.value)
            if not (1 <= quantity_input <= self.max_buyable):
                return await interaction.response.send_message(f"1から{self.max_buyable}個までの数量を入力してください。", ephemeral=True)
            self.value = quantity_input; await interaction.response.defer()
        except ValueError: await interaction.response.send_message("数字のみ入力してください。", ephemeral=True)

class SellItemView(ui.View):
    def __init__(self, user: discord.User):
        super().__init__(timeout=300); self.user = user
        self.current_category = SELL_CATEGORIES[0]; self.message: discord.WebhookMessage | None = None
    async def interaction_check(self, i: discord.Interaction) -> bool:
        if i.user.id != self.user.id: await i.response.send_message("自分専用のメニューを操作してください。", ephemeral=True); return False
        return True
    async def update_components(self):
        self.clear_items()
        for c in SELL_CATEGORIES:
            btn = ui.Button(label=c, style=discord.ButtonStyle.secondary if self.current_category != c else discord.ButtonStyle.success, custom_id=f"sell_category_{c}")
            btn.callback = self.category_button_callback; self.add_item(btn)
        options = []
        uid_str = str(self.user.id)
        if self.current_category == "魚":
            for fish in await get_aquarium(uid_str):
                if not (proto := next((item for item in FISHING_LOOT if item['name'] == fish['name']), None)) or proto.get("value", 1) == 0: continue
                price = int(proto.get("base_value", 0) + (fish.get('size', 0) * proto.get("size_multiplier", 0)))
                options.append(discord.SelectOption(label=f"{fish['emoji']} {fish['name']} ({fish['size']}cm)", value=f"fish_{fish['id']}", description=f"売却価格: {price}{CURRENCY_ICON}"))
        elif self.current_category == "アイテム":
            for name, count in (await get_inventory(uid_str)).items():
                if not (proto := ITEM_DATABASE.get(name, {})).get('sellable'): continue
                options.append(discord.SelectOption(label=f"{name} ({count}個)", value=f"item_{name}", description=f"単価: {proto.get('sell_price', 0)}{CURRENCY_ICON}"))
        select_menu = ui.Select(placeholder=f"売却したい{self.current_category}を選択..." if options else "販売できるものがありません。", options=options or [discord.SelectOption(label="...")], disabled=not options, row=1)
        select_menu.callback = self.sell_callback; self.add_item(select_menu)
    async def category_button_callback(self, i: discord.Interaction):
        self.current_category = i.data['custom_id'].replace("sell_category_", "")
        await self.update_components(); await i.response.edit_message(view=self)
    async def sell_callback(self, i: discord.Interaction):
        value = i.data['values'][0]; sell_type, sell_target = value.split('_', 1); uid_str = str(self.user.id)
        if sell_type == "fish":
            await i.response.defer(ephemeral=True); fish_id = int(sell_target)
            if not (sold_fish := next((f for f in await get_aquarium(uid_str) if f.get('id') == fish_id), None)): return await i.followup.send("エラー：その魚は既に売却されたか、存在しません。", ephemeral=True)
            if not (proto := next((it for it in FISHING_LOOT if it['name'] == sold_fish['name']), None)): return await i.followup.send("エラー：魚のデータが見つかりません。", ephemeral=True)
            price = int(proto.get("base_value", 0) + (sold_fish.get('size', 0) * proto.get("size_multiplier", 0)))
            info = f"**{sold_fish.get('emoji', '🐟')} {sold_fish['name']}** ({sold_fish['size']}cm)"
            await remove_fish_from_aquarium(fish_id); await update_wallet(i.user, price)
            await i.followup.send(f"{info}を売却し、`{price}`{CURRENCY_ICON}を獲得しました！", ephemeral=True)
        elif sell_type == "item":
            item_name = sell_target; max_qty = (await get_inventory(uid_str)).get(item_name, 0)
            if max_qty == 0: return await i.response.send_message("エラー：所持していないアイテムです。", ephemeral=True)
            modal = SellQuantityModal(item_name, max_qty); await i.response.send_modal(modal); await modal.wait()
            if modal.value is None: return
            qty = modal.value; price = ITEM_DATABASE.get(item_name, {}).get('sell_price', 0) * qty
            await update_inventory(uid_str, item_name, -qty); await update_wallet(i.user, price)
            await i.followup.send(f"**{item_name}** {qty}個を売却し、`{price}`{CURRENCY_ICON}を獲得しました！", ephemeral=True)
        if self.message: await self.update_components(); await self.message.edit(view=self)

class BuyItemView(ui.View):
    def __init__(self, user: discord.User):
        super().__init__(timeout=300); self.user = user
        self.current_category_index = 0; self.message: discord.WebhookMessage | None = None
    async def interaction_check(self, i: discord.Interaction) -> bool:
        if i.user.id != self.user.id: await i.response.send_message("自分専用のメニューを操作してください。", ephemeral=True); return False
        return True
    def update_components(self):
        self.clear_items(); is_first = self.current_category_index == 0; is_last = self.current_category_index >= len(BUY_CATEGORIES) - 1
        prev_btn = ui.Button(label="◀ 前", disabled=is_first, row=0); next_btn = ui.Button(label="次 ▶", disabled=is_last, row=0)
        prev_btn.callback = self.prev_category_callback; next_btn.callback = self.next_category_callback; self.add_item(prev_btn); self.add_item(next_btn)
        category = BUY_CATEGORIES[self.current_category_index]
        items = {n: d for n, d in ITEM_DATABASE.items() if d.get('category') == category and d.get("buyable", False)}
        options = [discord.SelectOption(label=n, value=n, description=f"{d['price']}{CURRENCY_ICON} - {d.get('description', '')}"[:100], emoji=d.get('emoji')) for n, d in items.items()]
        select = ui.Select(placeholder=f"「{category}」カテゴリの商品を選択" if options else "商品準備中...", options=options or [discord.SelectOption(label="...")], disabled=not options, row=1)
        select.callback = self.select_callback; self.add_item(select)
    def create_embed(self) -> discord.Embed:
        category = BUY_CATEGORIES[self.current_category_index]
        embed = discord.Embed(title=f"🏪 Dico森商店 - 「{category}」", description="下のドロップダウンメニューから購入したい商品を選択してください。", color=discord.Color.from_rgb(173, 216, 230))
        embed.set_footer(text=f"ページ {self.current_category_index + 1}/{len(BUY_CATEGORIES)}"); return embed
    async def prev_category_callback(self, i: discord.Interaction):
        if self.current_category_index > 0: self.current_category_index -= 1
        await self.update_view(i)
    async def next_category_callback(self, i: discord.Interaction):
        if self.current_category_index < len(BUY_CATEGORIES) - 1: self.current_category_index += 1
        await self.update_view(i)
    async def update_view(self, i: discord.Interaction):
        self.update_components(); await i.response.edit_message(embed=self.create_embed(), view=self)
    async def select_callback(self, i: discord.Interaction):
        name = i.data['values'][0]; data = ITEM_DATABASE.get(name); user = i.user; uid_str = str(user.id)
        if not data: return await i.response.send_message("エラー：商品データが見つかりません。", ephemeral=True)
        balance = (await get_wallet(user.id)).get('balance', 0); price = data['price']
        if balance < price: return await i.response.send_message(f"残高が不足しています。", ephemeral=True)
        if data['category'] == '里の役職' or data.get("is_upgrade_item"):
            await i.response.defer(ephemeral=True)
            try:
                if data['category'] == '里の役職':
                    role = i.guild.get_role(data['id']);
                    if not role: raise ValueError("Role not found.")
                    if role in user.roles: return await i.followup.send(f"すでにその役職をお持ちです。", ephemeral=True)
                    await update_wallet(user, -price); await user.add_roles(role); await i.followup.send(f"「{role.name}」役職を購入しました！", ephemeral=True)
                else: # is_upgrade_item
                    inv = await get_inventory(uid_str); current_rank = -1
                    for idx, rod in enumerate(ROD_HIERARCHY):
                        if inv.get(rod, 0) > 0: current_rank = idx
                    if ROD_HIERARCHY.index(name) <= current_rank: return await i.followup.send("すでにその装備またはより良い装備を持っています。", ephemeral=True)
                    await update_wallet(user, -price); await update_inventory(uid_str, name, 1); await i.followup.send(f"**{name}**にアップグレードしました！", ephemeral=True)
            except Exception as e: logger.error(f"Single item purchase error: {e}", exc_info=True); await update_wallet(user, price); await i.followup.send("購入処理中にエラーが発生しました。", ephemeral=True)
        else:
            modal = BuyQuantityModal(name, price, balance); await i.response.send_modal(modal); await modal.wait()
            if modal.value is None: return
            qty = modal.value; total_price = price * qty
            if (await get_wallet(user.id)).get('balance', 0) < total_price: return await i.followup.send("エラー: 残高が不足しています。", ephemeral=True)
            try:
                await update_wallet(user, -total_price); await update_inventory(uid_str, name, qty)
                await i.followup.send(f"**{name}**を{qty}個購入し、持ち物に入れました。", ephemeral=True)
            except Exception as e: logger.error(f"Multi-item purchase error: {e}", exc_info=True); await update_wallet(user, total_price); await i.followup.send("購入処理中にエラーが発生しました。", ephemeral=True)
        if self.message: self.update_components(); await self.message.edit(embed=self.create_embed(), view=self)

class CommercePanelView(ui.View):
    def __init__(self): super().__init__(timeout=None)
    @ui.button(label="🏪 商店に入る", style=discord.ButtonStyle.success, custom_id="open_shop_view_v3")
    async def open_shop(self, i: discord.Interaction, b: ui.Button):
        view = BuyItemView(i.user); view.update_components()
        await i.response.send_message(embed=view.create_embed(), view=view, ephemeral=True)
        view.message = await i.original_response()
    @ui.button(label="📦 販売所に入る", style=discord.ButtonStyle.danger, custom_id="open_market_view_v3")
    async def open_market(self, i: discord.Interaction, b: ui.Button):
        view = SellItemView(i.user); await view.update_components()
        embed = discord.Embed(title="販売カテゴリ選択", description="上のボタンでカテゴリを選択し、下のドロップダウンメニューから売りたいアイテムを選択してください。", color=discord.Color.orange())
        await i.response.send_message(embed=embed, view=view, ephemeral=True)
        view.message = await i.original_response()

class Commerce(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(CommercePanelView())
        self.commerce_panel_channel_id: int | None = None
        logger.info("Commerce Cog initialized.")

    async def cog_load(self):
        await self.load_commerce_channel_config()

    async def load_commerce_channel_config(self):
        self.commerce_panel_channel_id = await get_channel_id_from_db("commerce_panel_channel_id")
        logger.info(f"[Commerce Cog] Loaded COMMERCE_PANEL_CHANNEL_ID: {self.commerce_panel_channel_id}")

    async def regenerate_panel(self, channel: discord.TextChannel | None = None):
        if channel is None:
            if self.commerce_panel_channel_id: channel = self.bot.get_channel(self.commerce_panel_channel_id)
            else: logger.info("ℹ️ Commerce panel channel not set, skipping auto-regeneration."); return
        if not channel: logger.warning("❌ Commerce panel channel could not be found."); return
        
        # [수정된 부분]
        panel_info = await get_panel_id("commerce_main")
        if panel_info and (old_id := panel_info.get('message_id')):
            try:
                message_to_delete = await channel.fetch_message(old_id)
                await message_to_delete.delete()
            except (discord.NotFound, discord.Forbidden):
                pass
            
        embed = discord.Embed(title="💸 Dico森の暮らし", description="下のボタンを押して、商店でアイテムを購入したり、販売所で魚や収穫物を売却したりできます。", color=discord.Color.blue())
        msg = await channel.send(embed=embed, view=CommercePanelView())
        await save_panel_id("commerce_main", msg.id, channel.id)
        logger.info(f"✅ Commerce panel successfully regenerated in channel {channel.name}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Commerce(bot))
