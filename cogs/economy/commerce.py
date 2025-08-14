# cogs/economy/commerce.py (최종 수정본 - 구매 수량 지정 기능 추가)

import discord
from discord.ext import commands
from discord import app_commands, ui
import asyncio
import logging

# 로깅 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

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
        self.item_name = item_name
        self.max_quantity = max_quantity
        self.quantity.placeholder = f"最大 {max_quantity}個まで入力できます"
        self.value = None

    async def on_submit(self, interaction: discord.Interaction):
        try:
            quantity_input = int(self.quantity.value)
            if not (1 <= quantity_input <= self.max_quantity):
                await interaction.response.send_message(f"1から{self.max_quantity}までの数字を入力してください。", ephemeral=True)
                return
            self.value = quantity_input
            await interaction.response.defer()
        except ValueError:
            await interaction.response.send_message("数字のみ入力してください。", ephemeral=True)

# [핵심 1] 구매 수량을 입력받기 위한 Modal 추가
class BuyQuantityModal(ui.Modal, title="購入数量入力"):
    quantity = ui.TextInput(label="購入したい数量を入力してください", placeholder="例: 10", required=True, max_length=5)

    def __init__(self, item_name: str, item_price: int, user_balance: int):
        super().__init__()
        self.item_name = item_name
        self.item_price = item_price
        self.user_balance = user_balance
        max_buyable = user_balance // item_price if item_price > 0 else 0
        self.max_buyable = max_buyable
        self.quantity.label = f"{item_name}の購入数量"
        self.quantity.placeholder = f"最大 {max_buyable}個まで購入可能です (所持金: {user_balance}{CURRENCY_ICON})"
        self.value = None

    async def on_submit(self, interaction: discord.Interaction):
        try:
            quantity_input = int(self.quantity.value)
            if not (1 <= quantity_input <= self.max_buyable):
                await interaction.response.send_message(f"1から{self.max_buyable}個までの数量を入力してください。", ephemeral=True)
                return
            self.value = quantity_input
            await interaction.response.defer()
        except ValueError:
            await interaction.response.send_message("数字のみ入力してください。", ephemeral=True)

class SellItemView(ui.View):
    def __init__(self, user: discord.User):
        super().__init__(timeout=300)
        self.user = user
        self.current_category = SELL_CATEGORIES[0]
        self.message: discord.WebhookMessage | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("自分専用のメニューを操作してください。", ephemeral=True)
            return False
        return True

    async def update_components(self):
        self.clear_items()
        for c in SELL_CATEGORIES:
            btn = ui.Button(label=c, style=discord.ButtonStyle.secondary if self.current_category != c else discord.ButtonStyle.success, custom_id=f"sell_category_{c}")
            btn.callback = self.category_button_callback
            self.add_item(btn)

        options = []
        uid_str = str(self.user.id)
        if self.current_category == "魚":
            user_fish = await get_aquarium(uid_str)
            for fish in user_fish:
                proto = next((item for item in FISHING_LOOT if item['name'] == fish['name']), None)
                if not proto or proto.get("value", 1) == 0: continue
                price = int(proto.get("base_value", 0) + (fish.get('size', 0) * proto.get("size_multiplier", 0)))
                options.append(discord.SelectOption(label=f"{fish['emoji']} {fish['name']} ({fish['size']}cm)", value=f"fish_{fish['id']}", description=f"売却価格: {price}{CURRENCY_ICON}"))
        elif self.current_category == "アイテム":
            user_items = await get_inventory(uid_str)
            for name, count in user_items.items():
                proto = ITEM_DATABASE.get(name, {})
                if not proto.get('sellable'): continue
                price = proto.get('sell_price', 0)
                options.append(discord.SelectOption(label=f"{name} ({count}個)", value=f"item_{name}", description=f"単価: {price}{CURRENCY_ICON}"))

        select_menu = ui.Select(placeholder=f"売却したい{self.current_category}を選択..." if options else "販売できるものがありません。", options=options or [discord.SelectOption(label="...")], disabled=not options, row=1)
        select_menu.callback = self.sell_callback
        self.add_item(select_menu)

    async def category_button_callback(self, i: discord.Interaction):
        self.current_category = i.data['custom_id'].replace("sell_category_", "")
        await self.update_components()
        await i.response.edit_message(view=self)

    async def sell_callback(self, i: discord.Interaction):
        value = i.data['values'][0]
        sell_type, sell_target = value.split('_', 1)
        uid_str = str(self.user.id)

        if sell_type == "fish":
            await i.response.defer(ephemeral=True)
            fish_id = int(sell_target)
            user_fish = await get_aquarium(uid_str)
            sold_fish = next((f for f in user_fish if f.get('id') == fish_id), None)
            if not sold_fish: return await i.followup.send("エラー：その魚は既に売却されたか、存在しません。", ephemeral=True)
            proto = next((it for it in FISHING_LOOT if it['name'] == sold_fish['name']), None)
            if not proto: return await i.followup.send("エラー：魚のデータが見つかりません。", ephemeral=True)
            total_price = int(proto.get("base_value", 0) + (sold_fish.get('size', 0) * proto.get("size_multiplier", 0)))
            sold_item_info = f"**{sold_fish.get('emoji', '🐟')} {sold_fish['name']}** ({sold_fish['size']}cm)"
            await remove_fish_from_aquarium(fish_id)
            await update_wallet(i.user, total_price)
            await i.followup.send(f"{sold_item_info}を売却し、`{total_price}`{CURRENCY_ICON}を獲得しました！", ephemeral=True)

        elif sell_type == "item":
            item_name = sell_target
            user_items = await get_inventory(uid_str)
            max_quantity = user_items.get(item_name, 0)
            if max_quantity == 0: return await i.response.send_message("エラー：所持していないアイテムです。", ephemeral=True)
            modal = SellQuantityModal(item_name, max_quantity)
            await i.response.send_modal(modal)
            await modal.wait()
            if modal.value is None: return
            sell_quantity = modal.value
            proto = ITEM_DATABASE.get(item_name)
            total_price = proto.get('sell_price', 0) * sell_quantity
            sold_item_info = f"**{item_name}** {sell_quantity}個"
            await update_inventory(uid_str, item_name, -sell_quantity)
            await update_wallet(i.user, total_price)
            await i.followup.send(f"{sold_item_info}を売却し、`{total_price}`{CURRENCY_ICON}を獲得しました！", ephemeral=True)

        if self.message:
            await self.update_components()
            await self.message.edit(view=self)

class BuyItemView(ui.View):
    def __init__(self, user: discord.User):
        super().__init__(timeout=300)
        self.user = user
        self.current_category_index = 0
        self.message: discord.WebhookMessage | None = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("自分専用のメニューを操作してください。", ephemeral=True)
            return False
        return True

    def update_components(self):
        self.clear_items()
        is_first_page = self.current_category_index == 0
        is_last_page = self.current_category_index >= len(BUY_CATEGORIES) - 1
        prev_button = ui.Button(label="◀ 前のカテゴリ", style=discord.ButtonStyle.grey, disabled=is_first_page, row=0)
        next_button = ui.Button(label="次のカテゴリ ▶", style=discord.ButtonStyle.grey, disabled=is_last_page, row=0)
        prev_button.callback = self.prev_category_callback
        next_button.callback = self.next_category_callback
        self.add_item(prev_button)
        self.add_item(next_button)

        category = BUY_CATEGORIES[self.current_category_index]
        category_items = {name: data for name, data in ITEM_DATABASE.items() if data.get('category') == category and data.get("buyable", False)}
        options = [discord.SelectOption(label=name, value=name, description=f"{data['price']}{CURRENCY_ICON} - {data.get('description', '')}"[:100], emoji=data.get('emoji')) for name, data in category_items.items()]
        select_menu = ui.Select(placeholder=f"「{category}」カテゴリの商品を選択" if options else "商品準備中...", options=options or [discord.SelectOption(label="...")], disabled=not options, row=1)
        select_menu.callback = self.select_callback
        self.add_item(select_menu)

    def create_embed(self) -> discord.Embed:
        category = BUY_CATEGORIES[self.current_category_index]
        embed = discord.Embed(title=f"🏪 Dico森商店 - 「{category}」", description="下のドロップダウンメニューから購入したい商品を選択してください。", color=discord.Color.from_rgb(173, 216, 230))
        embed.set_footer(text=f"ページ {self.current_category_index + 1}/{len(BUY_CATEGORIES)}")
        return embed

    async def prev_category_callback(self, i: discord.Interaction):
        if self.current_category_index > 0: self.current_category_index -= 1
        await self.update_view(i)

    async def next_category_callback(self, i: discord.Interaction):
        if self.current_category_index < len(BUY_CATEGORIES) - 1: self.current_category_index += 1
        await self.update_view(i)

    async def update_view(self, interaction: discord.Interaction):
        self.update_components()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    # [핵심 3] 구매 로직 전체 수정
    async def select_callback(self, interaction: discord.Interaction):
        item_name = interaction.data['values'][0]
        item_data = ITEM_DATABASE.get(item_name)
        user = interaction.user
        user_id_str = str(user.id)

        if not item_data: return await interaction.response.send_message("エラー：商品データが見つかりません。", ephemeral=True)

        wallet_data = await get_wallet(user.id)
        user_balance = wallet_data.get('balance', 0)
        price = item_data['price']

        if user_balance < price: return await interaction.response.send_message(f"残高が不足しています。", ephemeral=True)

        # 역할 또는 업그레이드 아이템인 경우, 수량 질문 없이 즉시 구매
        if item_data['category'] == '里の役職' or item_data.get("is_upgrade_item"):
            await interaction.response.defer(ephemeral=True)
            try:
                if item_data['category'] == '里の役職':
                    role = interaction.guild.get_role(item_data['id'])
                    if not role: raise ValueError("Role not found.")
                    if role in user.roles: return await interaction.followup.send(f"すでにその役職をお持ちです。", ephemeral=True)
                    await update_wallet(user, -price)
                    await user.add_roles(role)
                    await interaction.followup.send(f"「{role.name}」役職を購入しました！", ephemeral=True)
                else: # is_upgrade_item
                    user_items = await get_inventory(user_id_str)
                    current_rank = -1
                    for i_idx, rod in enumerate(ROD_HIERARCHY):
                        if user_items.get(rod, 0) > 0: current_rank = i_idx
                    target_rank = ROD_HIERARCHY.index(item_name)
                    if target_rank <= current_rank: return await interaction.followup.send("すでにその装備またはより良い装備を持っています。", ephemeral=True)
                    await update_wallet(user, -price)
                    await update_inventory(user_id_str, item_name, 1)
                    await interaction.followup.send(f"**{item_name}**にアップグレードしました！", ephemeral=True)
            except Exception as e:
                logger.error(f"Single item purchase error: {e}", exc_info=True)
                await update_wallet(user, price) # 실패 시 금액 복구
                await interaction.followup.send("購入処理中にエラーが発生しました。", ephemeral=True)

        # 일반 아이템인 경우, 수량 질문
        else:
            modal = BuyQuantityModal(item_name, price, user_balance)
            await interaction.response.send_modal(modal)
            await modal.wait()

            if modal.value is None: return # 사용자가 취소했거나 유효하지 않은 값 입력

            buy_quantity = modal.value
            total_price = price * buy_quantity

            # 최종 잔액 확인
            if user_balance < total_price: return await interaction.followup.send("エラー: 残高が不足しています。", ephemeral=True)

            try:
                await update_wallet(user, -total_price)
                await update_inventory(user_id_str, item_name, buy_quantity)
                await interaction.followup.send(f"**{item_name}**を{buy_quantity}個購入し、持ち物に入れました。", ephemeral=True)
            except Exception as e:
                logger.error(f"Multi-item purchase error: {e}", exc_info=True)
                await update_wallet(user, total_price) # 실패 시 금액 복구
                await interaction.followup.send("購入処理中にエラーが発生しました。", ephemeral=True)

        if self.message:
            self.update_components()
            await self.message.edit(embed=self.create_embed(), view=self)

class CommercePanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @ui.button(label="🏪 商店に入る", style=discord.ButtonStyle.success, custom_id="open_shop_view_v3")
    async def open_shop(self, i: discord.Interaction, button: ui.Button):
        view = BuyItemView(i.user)
        view.update_components()
        await i.response.send_message(embed=view.create_embed(), view=view, ephemeral=True)
        view.message = await i.original_response()
    @ui.button(label="📦 販売所に入る", style=discord.ButtonStyle.danger, custom_id="open_market_view_v3")
    async def open_market(self, i: discord.Interaction, button: ui.Button):
        view = SellItemView(i.user)
        await view.update_components()
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

    async def regenerate_commerce_panel(self, channel: discord.TextChannel):
        old_id = await get_panel_id("commerce_main")
        if old_id:
            try:
                old_message = await channel.fetch_message(old_id)
                await old_message.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
                logger.warning(f"Failed to delete old commerce panel message {old_id}: {e}")
        embed = discord.Embed(
            title="💸 Dico森の暮らし",
            description="下のボタンを押して、商店でアイテムを購入したり、販売所で魚や収穫物を売却したりできます。",
            color=discord.Color.blue()
        )
        msg = await channel.send(embed=embed, view=CommercePanelView())
        await save_panel_id("commerce_main", msg.id)
        logger.info(f"✅ Commerce パネルをチャンネル {channel.name} に設置しました。(ID: {msg.id})")

    @app_commands.command(name="経済パネル設置", description="経済システム（売買）パネルをチャンネルに設置します。")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_commerce_panel_command(self, i: discord.Interaction):
        if self.commerce_panel_channel_id is None:
            await i.response.send_message("エラー: パネル設置チャンネルIDがまだ読み込まれていません。", ephemeral=True)
            return
        if i.channel.id != self.commerce_panel_channel_id:
            await i.response.send_message(f"このコマンドは <#{self.commerce_panel_channel_id}> でのみ使用できます。", ephemeral=True)
            return
        await i.response.defer(ephemeral=True)
        try:
            await self.regenerate_commerce_panel(i.channel)
            await i.followup.send("経済システムパネルを正常に設置しました。", ephemeral=True)
        except Exception as e:
            logger.error(f'Error executing command: {e}', exc_info=True)
            await i.followup.send(f'❌ パネル設置中にエラーが発生しました: {e}', ephemeral=True)

async def setup(bot: commands.Bot):
    cog = Commerce(bot)
    await bot.add_cog(cog)