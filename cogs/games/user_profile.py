# cogs/games/user_profile.py (ImportError 수정 및 Nicknames 연동 강화 최종본)

import discord
from discord.ext import commands
from discord import app_commands, ui
from math import ceil
import logging
import asyncio
from typing import Optional, Dict, List, Any

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] %(message)s')
logger = logging.getLogger(__name__)

# 유틸리티 함수 임포트
from utils.database import (
    get_wallet, get_inventory, get_aquarium,
    get_user_gear, set_user_gear, CURRENCY_ICON,
    ITEM_DATABASE, ROD_HIERARCHY,
    save_panel_id, get_panel_id, get_id
)
# [오류 수정] Nicknames Cog에서 칭호 우선순위 목록을 가져옵니다.
from cogs.server.nicknames import NICKNAME_PREFIX_HIERARCHY_NAMES

# --- 상수 정의 ---
CATEGORIES = ["プロフィール", "装備", "アイテム", "魚", "農業", "ペット"]
FISH_PER_PAGE = 5

class InventoryView(ui.View):
    """
    사용자의 모든 정보를 보여주는 다기능, 고성능 View.
    데이터는 처음에 한 번만 불러오고, 이후에는 캐시된 데이터를 사용해 UI만 업데이트합니다.
    """
    def __init__(self, user: discord.Member):
        super().__init__(timeout=300)
        self.user = user
        self.current_category = CATEGORIES[0]
        self.fish_page = 1
        self.message: Optional[discord.WebhookMessage] = None
        
        # 데이터 캐싱을 위한 변수
        self.wallet_data: Dict[str, Any] = {}
        self.inventory_data: Dict[str, int] = {}
        self.aquarium_data: List[Dict[str, Any]] = []
        self.gear_data: Dict[str, str] = {}

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("自分専用のメニューを操作してください。", ephemeral=True)
            return False
        return True

    async def fetch_all_data(self):
        """사용자 관련 모든 데이터를 DB에서 비동기적으로 한 번에 가져와 캐싱합니다."""
        uid_str = str(self.user.id)
        wallet_data, self.inventory_data, self.aquarium_data, self.gear_data = await asyncio.gather(
            get_wallet(self.user.id),
            get_inventory(uid_str),
            get_aquarium(uid_str),
            get_user_gear(uid_str)
        )
        self.wallet_data = wallet_data

    async def _update_embed_and_view(self, interaction: Optional[discord.Interaction] = None):
        """캐시된 데이터를 기반으로 Embed와 View 컴포넌트를 다시 렌더링합니다."""
        embed = self._build_embed()
        self._update_view_components()
        
        if interaction:
            await interaction.response.edit_message(embed=embed, view=self)
        elif self.message:
            await self.message.edit(embed=embed, view=self)

    def _build_embed(self) -> discord.Embed:
        """현재 카테고리에 맞는 Embed를 생성합니다."""
        embed = discord.Embed(title=f"📦 {self.user.display_name}様の持ち物 - 「{self.current_category}」", color=0xC8C8C8)
        if self.user.display_avatar:
            embed.set_thumbnail(url=self.user.display_avatar.url)

        builder = getattr(self, f"_build_{self.current_category.lower()}_embed", self._build_default_embed)
        builder(embed)
        return embed

    def _update_view_components(self):
        """현재 카테고리에 맞게 버튼과 드롭다운을 동적으로 구성합니다."""
        self.clear_items()
        
        for i, cat_name in enumerate(CATEGORIES):
            btn = ui.Button(label=cat_name, style=discord.ButtonStyle.success if self.current_category == cat_name else discord.ButtonStyle.secondary, custom_id=f"inv_cat_{cat_name}")
            btn.callback = self.category_button_callback
            self.add_item(btn)

        if self.current_category == "装備": self._add_gear_selects()
        if self.current_category == "魚":
            total_pages = ceil(len(self.aquarium_data) / FISH_PER_PAGE) if self.aquarium_data else 1
            prev_btn = ui.Button(label="◀", style=discord.ButtonStyle.grey, disabled=(self.fish_page <= 1))
            next_btn = ui.Button(label="▶", style=discord.ButtonStyle.grey, disabled=(self.fish_page >= total_pages))
            prev_btn.callback = self.prev_fish_page; next_btn.callback = self.next_fish_page
            self.add_item(prev_btn); self.add_item(next_btn)
            
    # --- 각 카테고리별 Embed 빌더 함수들 ---
    def _build_プロフィール_embed(self, embed: discord.Embed):
        balance = self.wallet_data.get('balance', 0)
        embed.add_field(name="💰 所持金", value=f"`{balance:,}` {CURRENCY_ICON}", inline=False)
        
        # [오류 수정] 사용자의 역할 목록과 칭호 우선순위를 비교하여 현재 칭호를 찾습니다.
        prefix = "役職なし"
        for role_name in NICKNAME_PREFIX_HIERARCHY_NAMES:
            if discord.utils.get(self.user.roles, name=role_name):
                # DB에서 해당 역할의 칭호를 가져옵니다. (예: 'role_prefix_里長' -> '『里長』')
                db_prefix = get_id(f"role_prefix_{role_name}")
                if db_prefix:
                    prefix = db_prefix.replace('『','').replace('』','') # 괄호 제거
                    break
        embed.add_field(name="📜 等級", value=f"`{prefix}`", inline=False)

    def _build_装備_embed(self, embed: discord.Embed):
        # ... (이하 다른 빌더 함수들은 변경 없음) ...
        rod = self.gear_data.get('rod', '素手')
        rod_count = self.inventory_data.get(rod, 1) if rod in ["素手", "古い釣竿"] else self.inventory_data.get(rod, 0)
        bait = self.gear_data.get('bait', 'エサなし')
        bait_count = self.inventory_data.get(bait, 0)
        embed.add_field(name="🎣 装備中の釣竿", value=f"`{rod}` (`{rod_count}`個所持)", inline=False)
        embed.add_field(name="🐛 装備中のエサ", value=f"`{bait}` (`{bait_count}`個所持)", inline=False)
        embed.set_footer(text="ここで装備したアイテムが釣りの際に自動で使用されます。")

    def _build_アイテム_embed(self, embed: discord.Embed):
        if not self.inventory_data:
            embed.description = "アイテムがありません。"
            return
        desc = "".join([f"{ITEM_DATABASE.get(n, {}).get('emoji', '❓')} **{n}** : `{c}`個\n" for n, c in self.inventory_data.items()])
        embed.description = desc

    def _build_魚_embed(self, embed: discord.Embed):
        total_fishes = len(self.aquarium_data)
        total_pages = ceil(total_fishes / FISH_PER_PAGE) if total_fishes > 0 else 1
        if self.fish_page > total_pages: self.fish_page = total_pages
        
        start_index = (self.fish_page - 1) * FISH_PER_PAGE
        end_index = start_index + FISH_PER_PAGE
        page_fishes = self.aquarium_data[start_index:end_index]
        
        embed.description = "".join([f"{f.get('emoji', '❓')} **{f['name']}** - `{f['size']}`cm\n" for f in page_fishes]) if page_fishes else "水槽に魚がいません。"
        embed.set_footer(text=f"ページ {self.fish_page}/{total_pages} | 合計 {total_fishes}匹")

    def _build_農業_embed(self, embed: discord.Embed): embed.description = "🌽 **農業機能は現在準備中です。**"
    def _build_ペット_embed(self, embed: discord.Embed): embed.description = "🐾 **ペット機能は現在準備中です。**"
    def _build_default_embed(self, embed: discord.Embed): embed.description = "現在、このカテゴリの情報はありません。"

    # ... (이하 UI 컴포넌트 추가 및 콜백 함수들은 변경 없음) ...
    def _add_gear_selects(self):
        rod_options = [discord.SelectOption(label="古い釣竿", emoji="🎣")]
        rod_options.extend(discord.SelectOption(label=r, emoji=ITEM_DATABASE.get(r, {}).get('emoji', '🎣')) for r in ROD_HIERARCHY if r != "古い釣竿" and self.inventory_data.get(r, 0) > 0)
        rod_select = ui.Select(placeholder="装備する釣竿を選択...", options=rod_options, custom_id="gear_rod_select")
        rod_select.callback = self.gear_select_callback
        self.add_item(rod_select)
        bait_options = [discord.SelectOption(label=i, emoji=ITEM_DATABASE.get(i, {}).get('emoji', '🐛')) for i in ["一般の釣りエサ", "高級釣りエサ"] if self.inventory_data.get(i, 0) > 0]
        bait_options.append(discord.SelectOption(label="エサなし", value="エサなし", emoji="🚫"))
        bait_select = ui.Select(placeholder="装備するエサを選択...", options=bait_options, custom_id="gear_bait_select")
        bait_select.callback = self.gear_select_callback
        self.add_item(bait_select)
        
    async def gear_select_callback(self, interaction: discord.Interaction):
        gear_type = "rod" if "rod" in interaction.data["custom_id"] else "bait"
        selected = interaction.data["values"][0]
        try:
            uid_str = str(self.user.id)
            if gear_type == "rod":
                await set_user_gear(uid_str, rod=selected); self.gear_data['rod'] = selected
            else:
                await set_user_gear(uid_str, bait=selected); self.gear_data['bait'] = selected
            await interaction.response.defer()
            self.inventory_data = await get_inventory(uid_str) 
            await self._update_embed_and_view()
        except Exception as e:
            logger.error(f"장비 변경 중 오류: {e}", exc_info=True)
            await interaction.response.send_message("❌ エラーが発生しました。", ephemeral=True)

    async def category_button_callback(self, interaction: discord.Interaction):
        self.current_category = interaction.data['custom_id'].split('_')[-1]
        self.fish_page = 1
        await self._update_embed_and_view(interaction)
        
    async def prev_fish_page(self, interaction: discord.Interaction):
        if self.fish_page > 1: self.fish_page -= 1
        await self._update_embed_and_view(interaction)

    async def next_fish_page(self, interaction: discord.Interaction):
        total_pages = ceil(len(self.aquarium_data) / FISH_PER_PAGE) if self.aquarium_data else 1
        if self.fish_page < total_pages: self.fish_page += 1
        await self._update_embed_and_view(interaction)

class InventoryPanelView(ui.View):
    def __init__(self, cog_instance: 'UserProfile'):
        super().__init__(timeout=None)
        self.user_profile_cog = cog_instance

    @ui.button(label="📦 持ち物を開く", style=discord.ButtonStyle.blurple, custom_id="open_inventory_view_v3")
    async def open_inventory(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            view = InventoryView(interaction.user)
            await view.fetch_all_data()
            embed = view._build_embed()
            view._update_view_components()
            view.message = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"{interaction.user.display_name}의 인벤토리 열기 중 오류: {e}", exc_info=True)
            await interaction.followup.send(f"❌エラーが発生しました。\n`{e}`", ephemeral=True)

class UserProfile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(InventoryPanelView(self))
        self.inventory_panel_channel_id: Optional[int] = None
        logger.info("UserProfile Cog가 성공적으로 초기화되었습니다.")
        
    async def cog_load(self): await self.load_all_configs()
    async def load_all_configs(self):
        self.inventory_panel_channel_id = get_id("inventory_panel_channel_id")
        logger.info(f"[UserProfile Cog] 프로필 패널 채널 ID 로드: {self.inventory_panel_channel_id}")
        
    async def regenerate_panel(self, channel: Optional[discord.TextChannel] = None):
        # ... (regenerate_panel 함수는 변경 없음) ...
        target_channel = channel or (self.bot.get_channel(self.inventory_panel_channel_id) if self.inventory_panel_channel_id else None)
        if not target_channel:
            logger.info("ℹ️ 프로필 패널 채널이 설정되지 않아, 자동 생성을 건너뜁니다.")
            return

        embed = discord.Embed(title="📦 持ち物", description="下のボタンを押して、あなたの持ち物を開きます。", color=0xC8C8C8)
        view = InventoryPanelView(self)

        panel_info = get_panel_id("profile")
        message_id = panel_info.get('message_id') if panel_info else None
        
        live_message = None
        if message_id:
            try:
                live_message = await target_channel.fetch_message(message_id)
                await live_message.edit(embed=embed, view=view)
                logger.info(f"✅ 프로필 패널을 성공적으로 업데이트했습니다. (채널: #{target_channel.name})")
            except discord.NotFound:
                live_message = None
        
        if not live_message:
            new_message = await target_channel.send(embed=embed, view=view)
            await save_panel_id("profile", new_message.id, channel.id)
            logger.info(f"✅ 프로필 패널을 성공적으로 새로 생성했습니다. (채널: #{target_channel.name})")

async def setup(bot: commands.Bot):
    await bot.add_cog(UserProfile(bot))
