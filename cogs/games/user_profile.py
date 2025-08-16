# cogs/games/user_profile.py (칭호 시스템 표시 기능 연동)

import discord
from discord.ext import commands
from discord import app_commands, ui
from math import ceil
import logging
import asyncio
from typing import Optional, Dict, List, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] %(message)s')
logger = logging.getLogger(__name__)

from utils.database import (
    get_wallet, get_inventory, get_aquarium,
    get_user_gear, set_user_gear, CURRENCY_ICON,
    ITEM_DATABASE, ROD_HIERARCHY,
    save_panel_id, get_panel_id, get_id, get_embed_from_db,
    get_panel_components_from_db # [추가] 패널 컴포넌트 DB 함수 임포트
)
from cogs.server.nicknames import NICKNAME_PREFIX_HIERARCHY_NAMES
from cogs.admin.panel_manager import BUTTON_STYLES_MAP # [추가] 버튼 스타일 맵 임포트

CATEGORIES = ["プロフィール", "装備", "アイテム", "魚", "農業", "ペット"]
FISH_PER_PAGE = 5

class InventoryView(ui.View):
    def __init__(self, user: discord.Member):
        super().__init__(timeout=300)
        self.user = user; self.current_category = CATEGORIES[0]; self.fish_page = 1
        self.message: Optional[discord.WebhookMessage] = None
        self.wallet_data: Dict[str, Any] = {}; self.inventory_data: Dict[str, int] = {}
        self.aquarium_data: List[Dict[str, Any]] = []; self.gear_data: Dict[str, str] = {}
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("自分専用のメニューを操作してください。", ephemeral=True); return False
        return True
    async def fetch_all_data(self):
        uid_str = str(self.user.id)
        wallet_data, self.inventory_data, self.aquarium_data, self.gear_data = await asyncio.gather(
            get_wallet(self.user.id), get_inventory(uid_str), get_aquarium(uid_str), get_user_gear(uid_str)
        )
        self.wallet_data = wallet_data
    async def _update_embed_and_view(self, interaction: Optional[discord.Interaction] = None):
        embed = self._build_embed(); self._update_view_components()
        if interaction and not interaction.response.is_done():
            await interaction.response.edit_message(embed=embed, view=self)
        elif self.message:
            await self.message.edit(embed=embed, view=self)
    def _build_embed(self) -> discord.Embed:
        embed = discord.Embed(title=f"📦 {self.user.display_name}様の持ち物 - 「{self.current_category}」", color=0xC8C8C8)
        if self.user.display_avatar: embed.set_thumbnail(url=self.user.display_avatar.url)
        builder = getattr(self, f"_build_{self.current_category}_embed", self._build_default_embed)
        builder(embed); return embed
    def _update_view_components(self):
        self.clear_items()
        for i, cat_name in enumerate(CATEGORIES):
            btn = ui.Button(label=cat_name, style=discord.ButtonStyle.success if self.current_category == cat_name else discord.ButtonStyle.secondary, custom_id=f"inv_cat_{cat_name}", row=0)
            btn.callback = self.category_button_callback; self.add_item(btn)
        if self.current_category == "装備": self._add_gear_selects()
        if self.current_category == "魚":
            total_pages = ceil(len(self.aquarium_data) / FISH_PER_PAGE) if self.aquarium_data else 1
            prev_btn = ui.Button(label="◀", style=discord.ButtonStyle.grey, disabled=(self.fish_page <= 1), row=1)
            next_btn = ui.Button(label="▶", style=discord.ButtonStyle.grey, disabled=(self.fish_page >= total_pages), row=1)
            prev_btn.callback = self.prev_fish_page; next_btn.callback = self.next_fish_page
            self.add_item(prev_btn); self.add_item(next_btn)
    
    # [수정] 프로필 탭에 칭호 시스템을 연동합니다.
    def _build_プロフィール_embed(self, embed: discord.Embed):
        balance = self.wallet_data.get('balance', 0)
        embed.add_field(name="💰 所持金", value=f"`{balance:,}` {CURRENCY_ICON}", inline=False)
        
        # 사용자의 역할 목록을 확인하여 가장 높은 등급의 칭호를 찾습니다.
        prefix = "役職なし" # 기본값
        member_role_names = {role.name for role in self.user.roles}
        for prefix_name in NICKNAME_PREFIX_HIERARCHY_NAMES:
            if prefix_name in member_role_names:
                prefix = prefix_name
                break # 가장 높은 등급을 찾으면 중단
        
        # '점검 중' 문구를 제거하고 찾은 칭호를 표시합니다.
        embed.add_field(name="📜 等級", value=f"`{prefix}`", inline=False)

    def _build_装備_embed(self, embed: discord.Embed):
        rod = self.gear_data.get('rod', '素手')
        rod_count = self.inventory_data.get(rod, 1) if rod in ["素手", "古い釣竿"] else self.inventory_data.get(rod, 0)
        bait = self.gear_data.get('bait', 'エサなし'); bait_count = self.inventory_data.get(bait, 0)
        embed.add_field(name="🎣 装備中の釣竿", value=f"`{rod}` (`{rod_count}`個所持)", inline=False)
        embed.add_field(name="🐛 装備中のエサ", value=f"`{bait}` (`{bait_count}`個所持)", inline=False)
        embed.set_footer(text="ここで装備したアイテムが釣りの際に自動で使用されます。")
    def _build_アイテム_embed(self, embed: discord.Embed):
        if not self.inventory_data: embed.description = "アイテムがありません。"; return
        embed.description = "".join([f"{ITEM_DATABASE.get(n, {}).get('emoji', '❓')} **{n}** : `{c}`個\n" for n, c in self.inventory_data.items()])
    def _build_魚_embed(self, embed: discord.Embed):
        total_fishes = len(self.aquarium_data); total_pages = ceil(total_fishes / FISH_PER_PAGE) if total_fishes > 0 else 1
        if self.fish_page > total_pages: self.fish_page = total_pages
        start_index = (self.fish_page - 1) * FISH_PER_PAGE; end_index = start_index + FISH_PER_PAGE
        page_fishes = self.aquarium_data[start_index:end_index]
        embed.description = "".join([f"{f.get('emoji', '❓')} **{f['name']}** - `{f['size']}`cm\n" for f in page_fishes]) if page_fishes else "水槽に魚がいません。"
        embed.set_footer(text=f"ページ {self.fish_page}/{total_pages} | 合計 {total_fishes}匹")
    def _build_農業_embed(self, embed: discord.Embed): embed.description = "🌽 **農業機能は現在準備中です。**"
    def _build_ペット_embed(self, embed: discord.Embed): embed.description = "🐾 **ペット機能は現在準備中です。**"
    def _build_default_embed(self, embed: discord.Embed): embed.description = "現在、このカテゴリの情報はありません。"
    def _add_gear_selects(self):
        rod_options = [discord.SelectOption(label="古い釣竿", emoji="🎣")]
        rod_options.extend(discord.SelectOption(label=r, emoji=ITEM_DATABASE.get(r, {}).get('emoji', '🎣')) for r in ROD_HIERARCHY if r != "古い釣竿" and self.inventory_data.get(r, 0) > 0)
        rod_select = ui.Select(placeholder="装備する釣竿を選択...", options=rod_options, custom_id="gear_rod_select", row=1); rod_select.callback = self.gear_select_callback; self.add_item(rod_select)
        bait_options = [discord.SelectOption(label=i, emoji=ITEM_DATABASE.get(i, {}).get('emoji', '🐛')) for i in ["一般の釣りエサ", "高級釣りエサ"] if self.inventory_data.get(i, 0) > 0]
        bait_options.insert(0, discord.SelectOption(label="エサなし", value="エサなし", emoji="🚫"))
        bait_select = ui.Select(placeholder="装備するエサを選択...", options=bait_options, custom_id="gear_bait_select", row=2); bait_select.callback = self.gear_select_callback; self.add_item(bait_select)
    async def gear_select_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        gear_type = "rod" if "rod" in interaction.data["custom_id"] else "bait"
        selected = interaction.data["values"][0]
        try:
            uid_str = str(self.user.id)
            if gear_type == "rod": await set_user_gear(uid_str, rod=selected); self.gear_data['rod'] = selected
            else: await set_user_gear(uid_str, bait=selected); self.gear_data['bait'] = selected
            self.inventory_data = await get_inventory(uid_str)
            await self._update_embed_and_view()
        except Exception as e:
            logger.error(f"장비 변경 중 오류: {e}", exc_info=True)
            await interaction.followup.send("❌ エラーが発生しました。", ephemeral=True)
    async def category_button_callback(self, interaction: discord.Interaction):
        self.current_category = interaction.data['custom_id'].split('_')[-1]; self.fish_page = 1
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
        
    async def setup_buttons(self):
        self.clear_items()
        components_data = await get_panel_components_from_db('profile')
        if not components_data:
            logger.warning("'profile' 패널에 대한 컴포넌트 데이터가 DB에 없습니다. 기본 버튼을 생성합니다.")
            default_button = ui.Button(label="📦 持ち物を開く", custom_id="open_inventory", style=discord.ButtonStyle.primary)
            default_button.callback = self.open_inventory
            self.add_item(default_button)
            return

        for comp in components_data:
            if comp.get('component_type') == 'button':
                button = ui.Button(
                    label=comp.get('label'),
                    style=BUTTON_STYLES_MAP.get(comp.get('style', 'secondary')),
                    emoji=comp.get('emoji'),
                    row=comp.get('row'),
                    custom_id=comp.get('component_key')
                )
                if comp.get('component_key') == 'open_inventory':
                    button.callback = self.open_inventory
                
                self.add_item(button)

    async def open_inventory(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            view = InventoryView(interaction.user)
            await view.fetch_all_data()
            embed = view._build_embed(); view._update_view_components()
            view.message = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"{interaction.user.display_name}의 인벤토리 열기 중 오류: {e}", exc_info=True)
            await interaction.followup.send(f"❌エラーが発生しました。\n`{e}`", ephemeral=True)

class UserProfile(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.inventory_panel_channel_id: Optional[int] = None
        self.view_instance = None
        logger.info("UserProfile Cog가 성공적으로 초기화되었습니다.")

    async def register_persistent_views(self):
        self.view_instance = InventoryPanelView(self)
        await self.view_instance.setup_buttons()
        self.bot.add_view(self.view_instance)
        
    async def cog_load(self): await self.load_all_configs()
    async def load_all_configs(self):
        self.inventory_panel_channel_id = get_id("inventory_panel_channel_id")
        logger.info(f"[UserProfile Cog] 프로필 패널 채널 ID 로드: {self.inventory_panel_channel_id}")

    async def regenerate_panel(self, channel: Optional[discord.TextChannel] = None):
        target_channel = channel
        if target_channel is None:
            channel_id = get_id("inventory_panel_channel_id")
            if channel_id: target_channel = self.bot.get_channel(channel_id)
            else: logger.info("ℹ️ 프로필 패널 채널이 설정되지 않아, 자동 생성을 건너뜁니다."); return
        if not target_channel: logger.warning("❌ Inventory panel channel could not be found."); return
        
        panel_info = get_panel_id("profile")
        if panel_info and (old_id := panel_info.get('message_id')):
            try:
                old_message = await target_channel.fetch_message(old_id)
                await old_message.delete()
            except (discord.NotFound, discord.Forbidden): pass
            
        embed_data = await get_embed_from_db("panel_profile")
        if not embed_data:
            logger.warning("DB에서 'panel_profile' 임베드 데이터를 찾을 수 없어, 패널 생성을 건너뜁니다.")
            return
        embed = discord.Embed.from_dict(embed_data)
        
        self.view_instance = InventoryPanelView(self)
        await self.view_instance.setup_buttons()
        
        new_message = await target_channel.send(embed=embed, view=self.view_instance)
        await save_panel_id("profile", new_message.id, target_channel.id)
        logger.info(f"✅ 프로필 패널을 성공적으로 새로 생성했습니다. (채널: #{target_channel.name})")

async def setup(bot: commands.Bot):
    await bot.add_cog(UserProfile(bot))
