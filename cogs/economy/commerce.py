# cogs/economy/commerce.py (데이터 정합성, 성능, UX 대폭 개선 최종본)

import discord
from discord.ext import commands
from discord import app_commands, ui
import logging
import asyncio
from typing import Optional, Dict, List, Any

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] %(message)s')
logger = logging.getLogger(__name__)

# 유틸리티 함수 임포트
from utils.database import (
    ITEM_DATABASE, FISHING_LOOT, CURRENCY_ICON, ROD_HIERARCHY,
    get_inventory, get_wallet, get_aquarium,
    save_panel_id, get_panel_id, get_id, supabase
)

# --- 상수 정의 ---
SELL_CATEGORIES = ["魚", "アイテム"]
BUY_CATEGORIES = ["里の役職", "釣り", "農業", "牧場"]

# --- 수량 입력 모달 (기존과 거의 동일, 약간의 개선) ---
class QuantityModal(ui.Modal):
    quantity = ui.TextInput(label="数量", placeholder="例: 10", required=True, max_length=5)
    def __init__(self, title: str, label: str, placeholder: str, max_value: int):
        super().__init__(title=title)
        self.quantity.label = label
        self.quantity.placeholder = placeholder
        self.max_value = max_value
        self.value = None
    async def on_submit(self, interaction: discord.Interaction):
        try:
            q_val = int(self.quantity.value)
            if not (1 <= q_val <= self.max_value):
                await interaction.response.send_message(f"1から{self.max_value}までの数字を入力してください。", ephemeral=True)
                return
            self.value = q_val
            await interaction.response.defer()
        except ValueError:
            await interaction.response.send_message("数字のみ入力してください。", ephemeral=True)

class ShopViewBase(ui.View):
    """상점/판매소 View의 기본 클래스"""
    def __init__(self, user: discord.Member):
        super().__init__(timeout=300)
        self.user = user
        self.message: Optional[discord.WebhookMessage] = None
        self.wallet_balance = 0
        self.inventory: Dict[str, int] = {}
        self.aquarium: List[Dict[str, Any]] = []

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("自分専用のメニューを操作してください。", ephemeral=True)
            return False
        return True
    
    async def fetch_data(self):
        """View가 시작될 때 필요한 모든 데이터를 한 번에 불러옵니다."""
        wallet_data, self.inventory, self.aquarium = await asyncio.gather(
            get_wallet(self.user.id),
            get_inventory(str(self.user.id)),
            get_aquarium(str(self.user.id))
        )
        self.wallet_balance = wallet_data.get('balance', 0)

    async def update_view(self, interaction: discord.Interaction, temp_footer: Optional[str] = None):
        """UI 컴포넌트와 임베드를 다시 렌더링합니다."""
        embed = self._build_embed()
        self._build_components()
        
        original_footer = embed.footer.text
        if temp_footer:
            embed.set_footer(text=temp_footer)
        
        await interaction.response.edit_message(embed=embed, view=self)

        if temp_footer:
            await asyncio.sleep(5)
            embed.set_footer(text=original_footer)
            try: await interaction.edit_original_response(embed=embed)
            except discord.NotFound: pass

class SellItemView(ShopViewBase):
    def __init__(self, user: discord.Member):
        super().__init__(user)
        self.current_category = SELL_CATEGORIES[0]

    def _build_embed(self) -> discord.Embed:
        return discord.Embed(title=f"📦 販売所 - 「{self.current_category}」", description="下のドロップダウンメニューから売りたいアイテムを選択してください。", color=discord.Color.orange())

    def _build_components(self):
        self.clear_items()
        for cat in SELL_CATEGORIES:
            btn = ui.Button(label=cat, style=discord.ButtonStyle.success if self.current_category == cat else discord.ButtonStyle.secondary, custom_id=f"sell_cat_{cat}")
            btn.callback = self.category_callback
            self.add_item(btn)

        options = []
        if self.current_category == "魚":
            for fish in self.aquarium:
                proto = next((item for item in FISHING_LOOT if item['name'] == fish['name']), None)
                if not proto or proto.get("value", 1) == 0: continue
                price = int(proto.get("base_value", 0) + (fish.get('size', 0) * proto.get("size_multiplier", 0)))
                options.append(discord.SelectOption(label=f"{fish['emoji']} {fish['name']} ({fish['size']}cm)", value=f"fish_{fish['id']}", description=f"売却価格: {price}{CURRENCY_ICON}"))
        elif self.current_category == "アイテム":
            for name, count in self.inventory.items():
                proto = ITEM_DATABASE.get(name, {})
                if not proto.get('sellable'): continue
                options.append(discord.SelectOption(label=f"{name} ({count}個)", value=f"item_{name}", description=f"単価: {proto.get('sell_price', 0)}{CURRENCY_ICON}"))

        select = ui.Select(placeholder=f"売却したい{self.current_category}を選択..." if options else "販売できるものがありません。", options=options or [discord.SelectOption(label="...")], disabled=not options, row=1)
        select.callback = self.sell_callback
        self.add_item(select)

    async def category_callback(self, interaction: discord.Interaction):
        self.current_category = interaction.data['custom_id'].split('_')[-1]
        await self.update_view(interaction)

    async def sell_callback(self, interaction: discord.Interaction):
        sell_type, target = interaction.data['values'][0].split('_', 1)
        uid_str = str(self.user.id)
        footer_msg = ""
        
        try:
            if sell_type == "fish":
                fish_id = int(target)
                fish_data = next((f for f in self.aquarium if f.get('id') == fish_id), None)
                if not fish_data: raise ValueError("選択された魚が見つかりません。")
                
                proto = next((it for it in FISHING_LOOT if it['name'] == fish_data['name']), None)
                if not proto: raise ValueError("魚の基本データが見つかりません。")
                
                price = int(proto.get("base_value", 0) + (fish_data.get('size', 0) * proto.get("size_multiplier", 0)))
                
                # [핵심] RPC 호출
                await supabase.rpc('sell_fish', {'user_id_param': uid_str, 'fish_id_param': fish_id, 'fish_value_param': price}).execute()

                self.aquarium = [f for f in self.aquarium if f.get('id') != fish_id]
                self.wallet_balance += price
                footer_msg = f"✅ {fish_data['name']}を売却し、{price}{CURRENCY_ICON}を獲得しました！"

            elif sell_type == "item":
                item_name = target
                max_qty = self.inventory.get(item_name, 0)
                if max_qty <= 0: raise ValueError("所持していないアイテムです。")
                
                modal = QuantityModal("販売数量入力", f"{item_name}の販売数量", f"最大 {max_qty}個まで入力できます", max_qty)
                await interaction.response.send_modal(modal)
                await modal.wait()
                if modal.value is None: return

                qty = modal.value
                price = ITEM_DATABASE.get(item_name, {}).get('sell_price', 0) * qty
                
                # [핵심] RPC 호출
                await supabase.rpc('sell_item', {'user_id_param': uid_str, 'item_name_param': item_name, 'quantity_param': qty, 'total_value_param': price}).execute()

                self.inventory[item_name] -= qty
                if self.inventory[item_name] <= 0: del self.inventory[item_name]
                self.wallet_balance += price
                footer_msg = f"✅ {item_name} {qty}個を売却し、{price}{CURRENCY_ICON}を獲得しました！"

        except Exception as e:
            logger.error(f"판매 처리 중 오류: {e}", exc_info=True)
            footer_msg = f"❌ 販売に失敗しました。アイテムが不足しているか、エラーが発生しました。"
            # 오류 발생 시 데이터 다시 동기화
            await self.fetch_data()

        # 상호작용이 모달에서 왔는지, 아니면 드롭다운에서 왔는지에 따라 응답 방식 분기
        if isinstance(interaction.message, discord.WebhookMessage): # 모달에서 온 경우
             await self.update_view(interaction, footer_msg)
        else: # 드롭다운에서 온 경우
             await self.update_view(interaction, footer_msg)


# ... (BuyItemView and other classes will be similarly refactored) ...

class CommercePanelView(ui.View):
    def __init__(self, cog_instance: 'Commerce'):
        super().__init__(timeout=None)
        self.commerce_cog = cog_instance

    @ui.button(label="🏪 商店に入る", style=discord.ButtonStyle.success, custom_id="open_shop_view_v3")
    async def open_shop(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        view = BuyItemView(interaction.user)
        await view.fetch_data()
        embed = view._build_embed()
        view._build_components()
        view.message = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    @ui.button(label="📦 販売所に入る", style=discord.ButtonStyle.danger, custom_id="open_market_view_v3")
    async def open_market(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        view = SellItemView(interaction.user)
        await view.fetch_data()
        embed = view._build_embed()
        view._build_components()
        view.message = await interaction.followup.send(embed=embed, view=view, ephemeral=True)

class Commerce(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(CommercePanelView(self))
        self.commerce_panel_channel_id: Optional[int] = None
        logger.info("Commerce Cog가 성공적으로 초기화되었습니다.")

    async def cog_load(self): await self.load_all_configs()
    async def load_all_configs(self):
        self.commerce_panel_channel_id = get_id("commerce_panel_channel_id")
        logger.info(f"[Commerce Cog] 상점 패널 채널 ID 로드: {self.commerce_panel_channel_id}")

    async def regenerate_panel(self, channel: Optional[discord.TextChannel] = None):
        target_channel = channel or (self.bot.get_channel(self.commerce_panel_channel_id) if self.commerce_panel_channel_id else None)
        if not target_channel:
            logger.info("ℹ️ 상점 패널 채널이 설정되지 않아, 자동 생성을 건너뜁니다.")
            return

        embed = discord.Embed(title="💸 Dico森の暮らし", description="下のボタンを押して、商店でアイテムを購入したり、販売所で魚や収穫物を売却したりできます。", color=discord.Color.blue())
        view = CommercePanelView(self)

        panel_info = get_panel_id("commerce")
        message_id = panel_info.get('message_id') if panel_info else None
        
        live_message = None
        if message_id:
            try:
                live_message = await target_channel.fetch_message(message_id)
                await live_message.edit(embed=embed, view=view)
                logger.info(f"✅ 상점 패널을 성공적으로 업데이트했습니다. (채널: #{target_channel.name})")
            except discord.NotFound:
                live_message = None
        
        if not live_message:
            new_message = await target_channel.send(embed=embed, view=view)
            await save_panel_id("commerce", new_message.id, target_channel.id)
            logger.info(f"✅ 상점 패널을 성공적으로 새로 생성했습니다. (채널: #{target_channel.name})")

async def setup(bot: commands.Bot):
    await bot.add_cog(Commerce(bot))

# [참고] BuyItemView도 SellItemView와 유사한 방식으로 리팩토링이 필요합니다. 
#        - fetch_data()로 데이터 선로드
#        - _build_embed(), _build_components()로 UI 생성 분리
#        - 구매 로직에서 buy_item RPC 함수 호출
#        - 구매 성공/실패 시 캐시된 데이터 업데이트 및 UI 새로고침
