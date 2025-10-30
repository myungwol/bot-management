# cogs/server/onboarding.py

import discord
from discord.ext import commands
from discord import ui
import asyncio
import logging
from typing import List, Dict, Any, Optional

from utils.database import (
    get_id, save_panel_id, get_panel_id, get_cooldown, set_cooldown, 
    get_embed_from_db, get_onboarding_steps, get_panel_components_from_db, get_config
)
from utils.helpers import format_embed_from_db, format_seconds_to_hms

logger = logging.getLogger(__name__)

class OnboardingGuideView(ui.View):
    def __init__(self, cog_instance: 'Onboarding', steps_data: List[Dict[str, Any]], user: discord.User):
        super().__init__(timeout=300)
        self.onboarding_cog = cog_instance
        self.steps_data = steps_data
        self.user = user
        self.current_step = 0
        self.message: Optional[discord.WebhookMessage] = None

    async def on_timeout(self) -> None:
        if self.message:
            for item in self.children: item.disabled = True
            try: await self.message.edit(content="案内の有効期限が切れました。最初からやり直してください。", view=self)
            except (discord.NotFound, discord.HTTPException): pass
    
    def stop(self):
        super().stop()

    def _update_components(self):
        self.clear_items()
        step_info = self.steps_data[self.current_step]
        is_first = self.current_step == 0
        is_last = self.current_step == len(self.steps_data) - 1
        
        prev_button = ui.Button(label="◀ 戻る", style=discord.ButtonStyle.secondary, custom_id="onboarding_prev", row=1, disabled=is_first)
        prev_button.callback = self.go_previous
        self.add_item(prev_button)

        step_type = step_info.get("step_type")
        if step_type == "intro":
             # [수정] 마지막 단계에서는 자기소개 패널로 안내하는 버튼을 표시합니다.
             intro_button = ui.Button(label="住民登録証を作成しに行く", style=discord.ButtonStyle.success, custom_id="onboarding_go_to_intro")
             intro_button.callback = self.go_to_introduction
             self.add_item(intro_button)
        else:
            next_button = ui.Button(label="次へ ▶", style=discord.ButtonStyle.primary, custom_id="onboarding_next", disabled=is_last)
            next_button.callback = self.go_next
            self.add_item(next_button)

    def _prepare_next_step_message_content(self) -> dict:
        step_info = self.steps_data[self.current_step]
        embed_data = step_info.get("embed_data", {}).get("embed_data")

        # [수정] 마지막 단계 임베드에 자기소개 채널 링크를 추가합니다.
        introduction_channel_id = get_id("introduction_panel_channel_id")
        
        if not embed_data: 
            embed = discord.Embed(title="エラー", description="このステップの表示データが見つかりません。", color=discord.Color.red())
        else:
            embed = format_embed_from_db(
                embed_data, 
                member_mention=self.user.mention,
                introduction_channel_mention=f"<#{introduction_channel_id}>" if introduction_channel_id else "未設定"
            )
        
        self._update_components()
        return {"embed": embed, "view": self}

    async def go_next(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.current_step < len(self.steps_data) - 1:
            self.current_step += 1
        content = self._prepare_next_step_message_content()
        if self.message:
            await self.message.edit(**content)

    async def go_previous(self, interaction: discord.Interaction):
        await interaction.response.defer()
        if self.current_step > 0: self.current_step -= 1
        content = self._prepare_next_step_message_content()
        if self.message: await self.message.edit(**content)

    async def go_to_introduction(self, interaction: discord.Interaction):
        # [수정] 자기소개 채널 링크와 함께 안내 메시지를 보내고 가이드를 종료합니다.
        introduction_channel_id = get_id("introduction_panel_channel_id")
        if introduction_channel_id:
            message = f"✅ 案内は以上です。<#{introduction_channel_id}> チャンネルに移動して住民登録証を作成してください。"
        else:
            message = "✅ 案内は以上です。管理者が設定した住民登録チャンネルに移動してください。"

        await interaction.response.send_message(message, ephemeral=True)
        if self.message:
            try: await self.message.delete()
            except (discord.NotFound, discord.HTTPException): pass
        self.stop()

class OnboardingPanelView(ui.View):
    def __init__(self, cog_instance: 'Onboarding'):
        super().__init__(timeout=None)
        self.onboarding_cog = cog_instance

    async def setup_buttons(self):
        self.clear_items()
        components_data = await get_panel_components_from_db('server_guide')
        if not components_data:
            logger.warning("サーバー案内のパネルコンポーネントが見つかりませんでした。")
            return
        
        button_info = components_data[0]
        button = ui.Button(
            label=button_info.get('label'),
            style=discord.ButtonStyle.success,
            emoji=button_info.get('emoji'),
            custom_id=button_info.get('component_key')
        )
        button.callback = self.start_guide_callback
        self.add_item(button)

    async def start_guide_callback(self, interaction: discord.Interaction):
        cooldown_key = "onboarding_start"
        cooldown_seconds = int(get_config("ONBOARDING_COOLDOWN_SECONDS", 300))
        
        utc_now = datetime.now(timezone.utc).timestamp()
        last_time = await get_cooldown(interaction.user.id, cooldown_key)
        
        if last_time > 0 and (utc_now - last_time) < cooldown_seconds:
            time_remaining = cooldown_seconds - (utc_now - last_time)
            formatted_time = format_seconds_to_hms(time_remaining)
            await interaction.response.send_message(f"❌ 次の案内は **{formatted_time}** 後に見ることができます。", ephemeral=True)
            return
            
        await interaction.response.defer(ephemeral=True, thinking=True)
        await set_cooldown(interaction.user.id, cooldown_key)
        
        try:
            steps = await get_onboarding_steps()
            if not steps: 
                await interaction.followup.send("現在、案内を準備中です。しばらくお待ちください。", ephemeral=True)
                return
            
            guide_view = OnboardingGuideView(self.onboarding_cog, steps, interaction.user)
            content = guide_view._prepare_next_step_message_content()
            message = await interaction.followup.send(**content, ephemeral=True, wait=True)
            guide_view.message = message
            await guide_view.wait()
        except Exception as e:
            logger.error(f"案内ガイド開始中にエラー: {e}", exc_info=True)
            if not interaction.is_done():
                try: await interaction.followup.send("エラーが発生しました。もう一度お試しください。", ephemeral=True)
                except discord.NotFound: logger.warning("案内ガイド開始エラーメッセージ送信失敗: Interaction not found.")

class Onboarding(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_channel_id: Optional[int] = None
        self.view_instance = None
        logger.info("Onboarding (サーバー案内) Cogが正常に初期化されました。")
        
    async def register_persistent_views(self):
        self.view_instance = OnboardingPanelView(self)
        await self.view_instance.setup_buttons()
        self.bot.add_view(self.view_instance)

    async def cog_load(self): 
        await self.load_configs()

    async def load_configs(self):
        self.panel_channel_id = get_id("server_guide_panel_channel_id")
        logger.info("[Onboarding Cog] データベースから設定を正常にロードしました。")
    
    async def regenerate_panel(self, channel: discord.TextChannel, panel_key: str = "panel_server_guide") -> bool:
        base_panel_key = panel_key.replace("panel_", "")
        embed_key = panel_key

        try:
            panel_info = get_panel_id(base_panel_key)
            if panel_info and (old_id := panel_info.get('message_id')):
                try: 
                    old_message = await channel.fetch_message(old_id)
                    await old_message.delete()
                except (discord.NotFound, discord.HTTPException): pass

            embed_data = await get_embed_from_db(embed_key)
            if not embed_data:
                logger.warning(f"DBで '{embed_key}' の埋め込みデータが見つからず、パネル作成をスキップします。")
                return False
                
            embed = discord.Embed.from_dict(embed_data)
            if self.view_instance is None:
                await self.register_persistent_views()
            
            await self.view_instance.setup_buttons()
            new_message = await channel.send(embed=embed, view=self.view_instance)
            await save_panel_id(base_panel_key, new_message.id, channel.id)
            logger.info(f"✅ {panel_key} パネルを正常に再作成しました。(チャンネル: #{channel.name})")
            return True
        except Exception as e:
            logger.error(f"❌ {panel_key} パネルの再インストール中にエラー発生: {e}", exc_info=True)
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(Onboarding(bot))
