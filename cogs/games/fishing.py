# cogs/games/fishing.py (명령어 통합 최종본)

import discord
from discord.ext import commands
from discord import app_commands, ui
import random
import asyncio
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from utils.database import (
    update_wallet, get_inventory, update_inventory, add_to_aquarium,
    get_user_gear, set_user_gear, FISHING_LOOT, ITEM_DATABASE,
    CURRENCY_ICON, save_panel_id, get_panel_id,
    get_channel_id_from_db
)

BIG_CATCH_THRESHOLD = 70.0

class FishingGameView(ui.View):
    def __init__(self, bot: commands.Bot, user: discord.User, used_rod: str, used_bait: str, active_fishers_set: set):
        super().__init__(timeout=35)
        self.bot = bot; self.player = user; self.message: discord.WebhookMessage | None = None
        self.game_state = "waiting"; self.game_task: asyncio.Task | None = None
        self.used_rod = used_rod; self.used_bait = used_bait; self.active_fishers_set = active_fishers_set
        rod_data = ITEM_DATABASE.get(self.used_rod, {}); self.rod_bonus = rod_data.get("good_fish_bonus", 0.0)
        bait_data = ITEM_DATABASE.get(self.used_bait, {}); self.bite_range = bait_data.get("bite_time_range", (8.0, 15.0))

    def _get_catch_value(self, catch_proto: dict, size: float = 0) -> int:
        if "base_value" in catch_proto: return int(catch_proto["base_value"] + (size * catch_proto["size_multiplier"]))
        if "value" in catch_proto:
            value = catch_proto["value"]
            return random.randint(value[0], value[1]) if isinstance(value, tuple) else int(value)
        return 0

    async def _send_result(self, embed: discord.Embed, log_publicly: bool = False):
        user_items = await get_inventory(str(self.player.id))
        footer_private = f"残りのエサ: 一般({user_items.get('一般の釣りエサ', 0)}個) / 高級({user_items.get('高級釣りエサ', 0)}個)"
        footer_public = f"使用した装備: {self.used_rod} / {self.used_bait}"
        fishing_cog = self.bot.get_cog("Fishing")
        if log_publicly and fishing_cog and fishing_cog.fishing_log_channel_id and (log_ch := self.bot.get_channel(fishing_cog.fishing_log_channel_id)):
            public_embed = embed.copy(); public_embed.set_footer(text=footer_public)
            try: await log_ch.send(embed=public_embed)
            except Exception as e: logger.error(f"Failed to send public fishing log: {e}", exc_info=True)
        embed.set_footer(text=f"{footer_public}\n{footer_private}")
        if self.message:
            try: await self.message.edit(embed=embed, view=None)
            except (discord.NotFound, AttributeError): pass

    async def game_flow(self):
        try:
            await asyncio.sleep(random.uniform(*self.bite_range))
            if self.is_finished(): return
            self.game_state = "biting"
            catch_button = self.children[0]
            if isinstance(catch_button, ui.Button): catch_button.style = discord.ButtonStyle.danger; catch_button.label = "釣り上げる！"
            embed = discord.Embed(title="❗ アタリが来た！", description="今だ！ボタンを押して釣り上げよう！", color=discord.Color.red())
            if self.message: await self.message.edit(embed=embed, view=self)
            await asyncio.sleep(3.0)
            if not self.is_finished() and self.game_state == "biting":
                self.game_state = "finished"
                embed = discord.Embed(title="💧 逃げられた…", description=f"{self.player.mention}さんは反応が遅れてしまいました。", color=discord.Color.greyple())
                embed.set_thumbnail(url=self.player.display_avatar.url); await self._send_result(embed); self.stop()
        except asyncio.CancelledError: pass
        except Exception as e:
            logger.error(f"Error in fishing game flow for {self.player.display_name}: {e}", exc_info=True)
            if not self.is_finished():
                self.game_state = "finished"
                error_embed = discord.Embed(title="❌ エラー発生", description="釣りの処理中に予期せぬエラーが発生しました。", color=discord.Color.red())
                await self._send_result(error_embed); self.stop()

    @ui.button(label="待機中...", style=discord.ButtonStyle.secondary, custom_id="catch_fish_button_v4", emoji="🎣")
    async def catch_button(self, i: discord.Interaction, b: ui.Button):
        await i.response.defer()
        if self.game_task: self.game_task.cancel()
        user_mention = i.user.mention; result_embed = None; log_publicly = False
        if self.game_state == "waiting":
            result_embed = discord.Embed(title="❌ 早すぎ！", description=f"{user_mention}さんは焦ってしまい、魚に気づかれてしまいました…", color=discord.Color.dark_grey())
        elif self.game_state == "biting":
            self.game_state = "finished"
            weights = [item['weight'] * (1 + self.rod_bonus if 'base_value' in item else 1) for item in FISHING_LOOT]
            catch = random.choices(FISHING_LOOT, weights=weights, k=1)[0]
            if "min_size" in catch:
                log_publicly = True
                size = round(random.uniform(catch["min_size"], catch["max_size"]), 1)
                await add_to_aquarium(str(i.user.id), {"name": catch['name'], "size": size, "emoji": catch['emoji']})
                is_big = size >= BIG_CATCH_THRESHOLD
                title = "🏆 大物を釣り上げた！ 🏆" if is_big else "🎉 釣り成功！ 🎉"
                desc = f"{user_mention}さんが、とてつもない大物を釣り上げました！" if is_big else f"{user_mention}さんが釣りに成功し、魚を水槽に入れました。"
                color = discord.Color.gold() if is_big else discord.Color.blue()
                result_embed = discord.Embed(title=title, description=desc, color=color)
                result_embed.add_field(name="魚", value=f"{catch['emoji']} **{catch['name']}**", inline=True)
                result_embed.add_field(name="サイズ", value=f"`{size}`cm", inline=True)
            else:
                value = self._get_catch_value(catch)
                if value != 0: await update_wallet(i.user, value)
                if catch['name'] == "フグ":
                    log_publicly = True; result_embed = discord.Embed(title="🐡 あっ！フグだ！", description=f"{user_mention}さんがフグに刺されてしまい、治療費として `{abs(value)}`{CURRENCY_ICON}を失いました…", color=discord.Color.yellow())
                elif catch['name'] == "キラキラの宝箱":
                    log_publicly = True; result_embed = discord.Embed(title="💎 宝箱だ！", description=f"{user_mention}さんが宝箱を見つけ、`{value}`{CURRENCY_ICON}を獲得しました！", color=discord.Color.teal())
                else:
                    result_embed = discord.Embed(title="…", description=f"{user_mention}さんは残念ながら、{catch['emoji']}**{catch['name']}**だけを釣り上げました。", color=discord.Color.dark_grey())
        if result_embed:
            result_embed.set_thumbnail(url=i.user.display_avatar.url)
            await self._send_result(result_embed, log_publicly=log_publicly)
        self.stop()

    async def on_timeout(self):
        if not self.is_finished():
            self.game_state = "finished"
            embed = discord.Embed(title="⏱️ 時間切れ", description=f"{self.player.mention}さんは時間内に反応がありませんでした。", color=discord.Color.darker_grey())
            embed.set_thumbnail(url=self.player.display_avatar.url); await self._send_result(embed); self.stop()

    def stop(self):
        if self.game_task and not self.game_task.done(): self.game_task.cancel()
        if self.player.id in self.active_fishers_set: self.active_fishers_set.remove(self.player.id)
        super().stop()

class FishingPanelView(ui.View):
    def __init__(self, bot: commands.Bot, active_fishers: set):
        super().__init__(timeout=None)
        self.bot = bot; self.active_fishers = active_fishers
    @ui.button(label="釣りをする", style=discord.ButtonStyle.blurple, custom_id="start_fishing_button_v4", emoji="🎣")
    async def start_fishing(self, i: discord.Interaction, b: ui.Button):
        await i.response.defer(ephemeral=True)
        if i.user.id in self.active_fishers:
            return await i.followup.send("すでに釣りを開始しています。", ephemeral=True)
        self.active_fishers.add(i.user.id)
        try:
            uid_str = str(i.user.id)
            gear = await get_user_gear(uid_str); rod = gear.get('rod', '素手')
            if rod == "素手" or ITEM_DATABASE.get(rod) is None:
                await i.followup.send("「古い釣竿」以上の釣竿を装備してください。", ephemeral=True)
                if i.user.id in self.active_fishers: self.active_fishers.remove(i.user.id)
                return
            bait = gear.get('bait', 'エサなし')
            if bait != "エサなし":
                if (await get_inventory(uid_str)).get(bait, 0) > 0: await update_inventory(uid_str, bait, -1)
                else: bait = "エサなし"; await set_user_gear(uid_str, bait="エサなし")
            rod_bonus = int(ITEM_DATABASE.get(rod, {}).get("good_fish_bonus", 0.0) * 100)
            min_b, max_b = ITEM_DATABASE.get(bait, {}).get("bite_time_range", (8.0, 15.0))
            desc = f"### ウキを投げました。\n**🎣 使用中の釣竿:** `{rod}` (`+{rod_bonus}%`)\n**🐛 使用中のエサ:** `{bait}` (`{min_b}～{max_b}秒`)"
            embed = discord.Embed(title="🎣 釣りを開始しました！", description=desc, color=discord.Color.light_grey())
            view = FishingGameView(self.bot, i.user, rod, bait, self.active_fishers)
            msg = await i.followup.send(embed=embed, view=view, ephemeral=True)
            view.message = msg; view.game_task = asyncio.create_task(view.game_flow())
        except Exception as e:
            logger.error(f"Error starting fishing game: {e}", exc_info=True)
            await i.followup.send(f"❌ 釣りの開始中にエラーが発生しました。", ephemeral=True)
            if i.user.id in self.active_fishers: self.active_fishers.remove(i.user.id)

class Fishing(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot; self.active_fishing_sessions_by_user = set()
        self.bot.add_view(FishingPanelView(self.bot, self.active_fishing_sessions_by_user))
        self.fishing_panel_channel_id: int | None = None; self.fishing_log_channel_id: int | None = None
        logger.info("Fishing Cog initialized.")
    async def cog_load(self): await self.load_fishing_channel_config()
    async def load_fishing_channel_config(self):
        self.fishing_panel_channel_id = await get_channel_id_from_db("fishing_panel_channel_id")
        self.fishing_log_channel_id = await get_channel_id_from_db("fishing_log_channel_id")
        logger.info(f"[Fishing Cog] Loaded FISHING_PANEL_CHANNEL_ID: {self.fishing_panel_channel_id}")
        logger.info(f"[Fishing Cog] Loaded FISHING_LOG_CHANNEL_ID: {self.fishing_log_channel_id}")
        
    async def regenerate_panel(self, channel: discord.TextChannel | None = None):
        if channel is None:
            if self.fishing_panel_channel_id: channel = self.bot.get_channel(self.fishing_panel_channel_id)
            else: logger.info("ℹ️ Fishing panel channel not set, skipping auto-regeneration."); return
        if not channel: logger.warning("❌ Fishing panel channel could not be found."); return
        
        old_id = await get_panel_id("fishing")
        if old_id:
            try: (await channel.fetch_message(old_id)).delete()
            except (discord.NotFound, discord.Forbidden): pass
        
        embed = discord.Embed(title="🎣 Dico森 釣り場", description="下のボタンを押して釣りを開始し、コインを獲得しましょう！", color=discord.Color.from_rgb(135, 206, 250))
        msg = await channel.send(embed=embed, view=FishingPanelView(self.bot, self.active_fishing_sessions_by_user))
        await save_panel_id("fishing", msg.id, channel.id)
        logger.info(f"✅ Fishing panel successfully regenerated in channel {channel.name}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Fishing(bot))
