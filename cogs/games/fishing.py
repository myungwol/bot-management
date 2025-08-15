# cogs/games/fishing.py (실행 순서 문제 해결 최종본)

import discord
from discord.ext import commands
from discord import app_commands, ui
import random
import asyncio
import logging
from typing import Optional, Set, Dict

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] %(message)s')
logger = logging.getLogger(__name__)

# 유틸리티 함수 임포트
from utils.database import (
    update_wallet, get_inventory, update_inventory, add_to_aquarium,
    get_user_gear, set_user_gear, FISHING_LOOT, ITEM_DATABASE,
    CURRENCY_ICON, save_panel_id, get_panel_id, get_id
)

# --- 상수 정의 ---
BIG_CATCH_THRESHOLD = 70.0
BITE_REACTION_TIME = 3.0

class FishingGameView(ui.View):
    def __init__(self, bot: commands.Bot, user: discord.Member, used_rod: str, used_bait: str, remaining_baits: Dict[str, int], active_fishers_set: Set[int]):
        super().__init__(timeout=35)
        self.bot = bot; self.player = user; self.message: Optional[discord.WebhookMessage] = None
        self.game_state = "waiting"; self.game_task: Optional[asyncio.Task] = None
        self.used_rod = used_rod; self.used_bait = used_bait; self.remaining_baits = remaining_baits
        self.active_fishers_set = active_fishers_set
        self.rod_bonus = ITEM_DATABASE.get(self.used_rod, {}).get("good_fish_bonus", 0.0)
        self.bite_range = ITEM_DATABASE.get(self.used_bait, {}).get("bite_time_range", (8.0, 15.0))

    async def start_game(self, interaction: discord.Interaction, embed: discord.Embed):
        self.message = await interaction.followup.send(embed=embed, view=self, ephemeral=True)
        self.game_task = asyncio.create_task(self.game_flow())

    async def game_flow(self):
        try:
            await asyncio.sleep(random.uniform(*self.bite_range))
            if self.is_finished(): return
            self.game_state = "biting"
            if isinstance(catch_button := self.children[0], ui.Button):
                catch_button.style = discord.ButtonStyle.danger; catch_button.label = "釣り上げる！"
            embed = discord.Embed(title="❗ アタリが来た！", description="今だ！ボタンを押して釣り上げよう！", color=discord.Color.red())
            if self.message: await self.message.edit(embed=embed, view=self)
            await asyncio.sleep(BITE_REACTION_TIME)
            if not self.is_finished() and self.game_state == "biting":
                embed = discord.Embed(title="💧 逃げられた…", description=f"{self.player.mention}さんは反応が遅れてしまいました。", color=discord.Color.greyple())
                await self._send_result(embed); self.stop()
        except asyncio.CancelledError: pass
        except Exception as e:
            logger.error(f"{self.player.display_name}의 낚시 게임 흐름 중 오류: {e}", exc_info=True)
            if not self.is_finished():
                error_embed = discord.Embed(title="❌ エラー発生", description="釣りの処理中に予期せぬエラーが発生しました。", color=discord.Color.red())
                await self._send_result(error_embed); self.stop()

    async def _handle_catch_logic(self) -> tuple[discord.Embed, bool, bool]:
        weights = [item['weight'] * (1 + self.rod_bonus if 'base_value' in item else 1) for item in FISHING_LOOT]
        catch_proto = random.choices(FISHING_LOOT, weights=weights, k=1)[0]
        user_mention = self.player.mention; is_big_catch = log_publicly = False
        if "min_size" in catch_proto:
            log_publicly = True
            size = round(random.uniform(catch_proto["min_size"], catch_proto["max_size"]), 1)
            await add_to_aquarium(str(self.player.id), {"name": catch_proto['name'], "size": size, "emoji": catch_proto['emoji']})
            is_big_catch = size >= BIG_CATCH_THRESHOLD
            title = "🏆 大物を釣り上げた！ 🏆" if is_big_catch else "🎉 釣り成功！ 🎉"
            desc = f"{user_mention}さんが、とてつもない大物を釣り上げました！" if is_big_catch else f"{user_mention}さんが釣りに成功し、魚を水槽に入れました。"
            color = discord.Color.gold() if is_big_catch else discord.Color.blue()
            embed = discord.Embed(title=title, description=desc, color=color)
            embed.add_field(name="魚", value=f"{catch_proto['emoji']} **{catch_proto['name']}**", inline=True)
            embed.add_field(name="サイズ", value=f"`{size}`cm", inline=True)
        else:
            value = catch_proto.get('value', 0)
            if value > 0: await update_wallet(self.player, value)
            log_publicly = catch_proto.get("log_publicly", False)
            embed = discord.Embed(title=catch_proto['title'], description=catch_proto['description'].format(user_mention=user_mention, value=value), color=discord.Color(catch_proto['color']))
        return embed, log_publicly, is_big_catch
    
    @ui.button(label="待機中...", style=discord.ButtonStyle.secondary, custom_id="catch_fish_button_v4", emoji="🎣")
    async def catch_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.defer()
        if self.game_task: self.game_task.cancel()
        result_embed, log_publicly, is_big_catch = None, False, False
        if self.game_state == "waiting":
            result_embed = discord.Embed(title="❌ 早すぎ！", description=f"{interaction.user.mention}さんは焦ってしまい、魚に気づかれてしまいました…", color=discord.Color.dark_grey())
        elif self.game_state == "biting":
            self.game_state = "finished"
            result_embed, log_publicly, is_big_catch = await self._handle_catch_logic()
        if result_embed:
            if self.player.display_avatar: result_embed.set_thumbnail(url=self.player.display_avatar.url)
            await self._send_result(result_embed, log_publicly, is_big_catch)
        self.stop()

    async def _send_result(self, embed: discord.Embed, log_publicly: bool = False, is_big_catch: bool = False):
        footer_private = f"残りのエサ: 一般({self.remaining_baits.get('一般の釣りエサ', 0)}個) / 高級({self.remaining_baits.get('高級釣りエサ', 0)}個)"
        footer_public = f"使用した装備: {self.used_rod} / {self.used_bait}"
        if log_publicly and (fishing_cog := self.bot.get_cog("Fishing")) and (log_ch_id := fishing_cog.fishing_log_channel_id) and (log_ch := self.bot.get_channel(log_ch_id)):
            public_embed = embed.copy(); public_embed.set_footer(text=footer_public)
            content = self.player.mention if is_big_catch else None
            allowed_mentions = discord.AllowedMentions(users=True) if is_big_catch else discord.AllowedMentions.none()
            try: await log_ch.send(content=content, embed=public_embed, allowed_mentions=allowed_mentions)
            except Exception as e: logger.error(f"공개 낚시 로그 전송 실패: {e}", exc_info=True)
        embed.set_footer(text=f"{footer_public}\n{footer_private}")
        if self.message:
            try: await self.message.edit(embed=embed, view=None)
            except (discord.NotFound, AttributeError): pass

    async def on_timeout(self):
        if self.game_state != "finished":
            embed = discord.Embed(title="⏱️ 時間切れ", description=f"{self.player.mention}さんは時間内に反応がありませんでした。", color=discord.Color.darker_grey())
            await self._send_result(embed)
        self.stop()
    def stop(self):
        if self.game_task and not self.game_task.done(): self.game_task.cancel()
        self.active_fishers_set.discard(self.player.id); super().stop()

class FishingPanelView(ui.View):
    def __init__(self, bot: commands.Bot, cog_instance: 'Fishing'):
        super().__init__(timeout=None)
        self.bot = bot; self.fishing_cog = cog_instance
        self.user_locks: Dict[int, asyncio.Lock] = {}

    @ui.button(label="釣りをする", style=discord.ButtonStyle.blurple, custom_id="start_fishing_button_v4", emoji="🎣")
    async def start_fishing(self, interaction: discord.Interaction, button: ui.Button):
        user_id = interaction.user.id
        lock = self.user_locks.setdefault(user_id, asyncio.Lock())
        if lock.locked():
            await interaction.response.send_message("現在、以前のリクエストを処理中です。しばらくお待ちください。", ephemeral=True); return
        async with lock:
            if user_id in self.fishing_cog.active_fishing_sessions_by_user:
                await interaction.response.send_message("すでに釣りを開始しています。", ephemeral=True); return
            await interaction.response.defer(ephemeral=True)
            self.fishing_cog.active_fishing_sessions_by_user.add(user_id)
            try:
                uid_str = str(user_id)
                gear, inventory = await asyncio.gather(get_user_gear(uid_str), get_inventory(uid_str))
                rod = gear.get('rod', '素手')
                if rod == "素手" or ITEM_DATABASE.get(rod) is None: raise ValueError("「古い釣竿」以上の釣竿を装備してください。")
                bait = gear.get('bait', 'エサなし')
                if bait != "エサなし":
                    if inventory.get(bait, 0) > 0:
                        await update_inventory(uid_str, bait, -1); inventory[bait] = inventory.get(bait, 0) - 1
                    else: bait = "エサなし"; await set_user_gear(uid_str, bait="エサなし")
                rod_bonus = int(ITEM_DATABASE.get(rod, {}).get("good_fish_bonus", 0.0) * 100)
                min_b, max_b = ITEM_DATABASE.get(bait, {}).get("bite_time_range", (8.0, 15.0))
                desc = f"### ウキを投げました。\n**🎣 使用中の釣竿:** `{rod}` (`+{rod_bonus}%`)\n**🐛 使用中のエサ:** `{bait}` (`{min_b}～{max_b}秒`)"
                embed = discord.Embed(title="🎣 釣りを開始しました！", description=desc, color=discord.Color.light_grey())
                view = FishingGameView(self.bot, interaction.user, rod, bait, inventory, self.fishing_cog.active_fishing_sessions_by_user)
                await view.start_game(interaction, embed)
            except Exception as e:
                self.fishing_cog.active_fishing_sessions_by_user.discard(user_id)
                logger.error(f"낚시 게임 시작 중 오류: {e}", exc_info=True)
                await interaction.followup.send(f"❌ 釣りの開始中にエラーが発生しました。\n`{e}`", ephemeral=True)

class Fishing(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot; self.active_fishing_sessions_by_user: Set[int] = set()
        self.bot.add_view(FishingPanelView(self.bot, self))
        self.fishing_panel_channel_id: Optional[int] = None; self.fishing_log_channel_id: Optional[int] = None
        logger.info("Fishing Cog가 성공적으로 초기화되었습니다.")
    async def cog_load(self): await self.load_all_configs()
    async def load_all_configs(self):
        self.fishing_panel_channel_id = get_id("fishing_panel_channel_id")
        self.fishing_log_channel_id = get_id("fishing_log_channel_id")
        logger.info(f"[Fishing Cog] 낚시 패널/로그 채널 ID 로드 완료.")
    async def regenerate_panel(self, channel: Optional[discord.TextChannel] = None):
        target_channel = channel
        if target_channel is None:
            channel_id = get_id("fishing_panel_channel_id")
            if channel_id: target_channel = self.bot.get_channel(channel_id)
            else: logger.info("ℹ️ 낚시 패널 채널이 설정되지 않아, 자동 생성을 건너뜁니다."); return
        if not target_channel: logger.warning("❌ Fishing panel channel could not be found."); return
        embed = discord.Embed(title="🎣 Dico森 釣り場", description="下のボタンを押して釣りを開始し、コインを獲得しましょう！", color=0x87CEFA)
        view = FishingPanelView(self.bot, self)
        panel_info = get_panel_id("fishing"); message_id = panel_info.get('message_id') if panel_info else None
        live_message = None
        if message_id:
            try:
                live_message = await target_channel.fetch_message(message_id)
                await live_message.edit(embed=embed, view=view)
                logger.info(f"✅ 낚시 패널을 성공적으로 업데이트했습니다. (채널: #{target_channel.name})")
            except discord.NotFound: live_message = None
        if not live_message:
            new_message = await target_channel.send(embed=embed, view=view)
            await save_panel_id("fishing", new_message.id, target_channel.id)
            logger.info(f"✅ 낚시 패널을 성공적으로 새로 생성했습니다. (채널: #{target_channel.name})")

async def setup(bot: commands.Bot):
    await bot.add_cog(Fishing(bot))
