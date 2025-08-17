# bot-management/cogs/server/system.py

import discord
from discord.ext import commands
from discord import app_commands, ui
import logging
import json
import copy
from typing import Optional, List, Dict, Any

from utils.database import get_id, save_panel_id, get_panel_id, get_embed_from_db, save_id_to_db, get_config

logger = logging.getLogger(__name__)

# --- (이전과 동일한 코드 생략) ---

# --- ServerSystem Cog ---
class ServerSystem(commands.Cog):
    # ... (이전과 동일한 코드 생략) ...

    # --- [수정] 이 명령어의 선택지와 설명서가 변경되었습니다 ---
    @app_commands.command(name="setup", description="[管理者] ボットの各種チャンネルを設定またはパネルを設置します。")
    @app_commands.describe(setting_type="設定したい項目を選択してください。", channel="設定対象のチャンネルを指定してください。")
    @app_commands.choices(setting_type=[
        # --- 패널 설정 ---
        app_commands.Choice(name="[パネル] 役割パネル", value="panel_roles"), 
        app_commands.Choice(name="[パネル] 案内パネル (オンボーディング)", value="panel_onboarding"),
        app_commands.Choice(name="[パネル] 名前変更パネル", value="panel_nicknames"), 
        # --- 채널 설정 ---
        app_commands.Choice(name="[チャンネル] 自己紹介承認チャンネル", value="channel_onboarding_approval"), 
        app_commands.Choice(name="[チャンネル] 名前変更承認チャンネル", value="channel_nickname_approval"),
        app_commands.Choice(name="[チャンネル] 新規参加者歓迎チャンネル (입장 메시지)", value="channel_new_welcome"), 
        app_commands.Choice(name="[チャンネル] 退場メッセージチャンネル", value="channel_farewell"), 
        app_commands.Choice(name="[チャンネル] メインチャットチャンネル (자기소개 승인 후)", value="channel_main_chat"),
        # --- 로그 채널 설정 ---
        app_commands.Choice(name="[ログ] 名前変更ログ", value="log_nickname"), 
        app_commands.Choice(name="[ログ] 自己紹介承認ログ", value="log_intro_approval"), 
        app_commands.Choice(name="[ログ] 自己紹介拒否ログ", value="log_intro_rejection"),
    ])
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setup_unified(self, interaction: discord.Interaction, setting_type: str, channel: discord.TextChannel):
        await interaction.response.defer(ephemeral=True, thinking=True)
        # [수정] setup_map도 관리 봇에 맞게 수정합니다.
        setup_map = {
            "panel_roles": {"type": "panel", "cog": "ServerSystem", "key": "auto_role_channel_id", "friendly_name": "役割パネル"},
            "panel_onboarding": {"type": "panel", "cog": "Onboarding", "key": "onboarding_panel_channel_id", "friendly_name": "案内パネル"},
            "panel_nicknames": {"type": "panel", "cog": "Nicknames", "key": "nickname_panel_channel_id", "friendly_name": "名前変更パネル"},
            "channel_onboarding_approval": {"type": "channel", "cog_name": "Onboarding", "key": "onboarding_approval_channel_id", "friendly_name": "自己紹介承認チャンネル"},
            "channel_nickname_approval": {"type": "channel", "cog_name": "Nicknames", "key": "nickname_approval_channel_id", "friendly_name": "名前変更承認チャンネル"},
            "channel_new_welcome": {"type": "channel", "cog_name": "ServerSystem", "key": "new_welcome_channel_id", "friendly_name": "新規参加者歓迎チャンネル"},
            "channel_farewell": {"type": "channel", "cog_name": "ServerSystem", "key": "farewell_channel_id", "friendly_name": "退場メッセージチャンネル"},
            "channel_main_chat": {"type": "channel", "cog_name": "Onboarding", "key": "main_chat_channel_id", "friendly_name": "メインチャットチャンネル"},
            "log_nickname": {"type": "channel", "cog_name": "Nicknames", "key": "nickname_log_channel_id", "friendly_name": "名前変更ログ"},
            "log_intro_approval": {"type": "channel", "cog_name": "Onboarding", "key": "introduction_channel_id", "friendly_name": "自己紹介承認ログ"},
            "log_intro_rejection": {"type": "channel", "cog_name": "Onboarding", "key": "introduction_rejection_log_channel_id", "friendly_name": "自己紹介拒否ログ"},
        }
        config = setup_map.get(setting_type);
        if not config: await interaction.followup.send("❌ 無効な設定タイプです。", ephemeral=True); return
        try:
            db_key, friendly_name = config['key'], config['friendly_name']
            await save_id_to_db(db_key, channel.id)
            if config["type"] == "panel":
                cog_to_run = self.bot.get_cog(config["cog"])
                if not cog_to_run or not hasattr(cog_to_run, 'regenerate_panel'): await interaction.followup.send(f"❌ '{config['cog']}' Cogが見つからないか、'regenerate_panel' 関数がありません。", ephemeral=True); return
                await cog_to_run.regenerate_panel(channel); await interaction.followup.send(f"✅ `{channel.mention}` に **{friendly_name}** を設置しました。", ephemeral=True)
            elif config["type"] == "channel":
                target_cog = self.bot.get_cog(config["cog_name"])
                if target_cog and hasattr(target_cog, 'load_configs'): await target_cog.load_configs()
                await interaction.followup.send(f"✅ `{channel.mention}`を**{friendly_name}**として設定しました。", ephemeral=True)
        except Exception as e:
            logger.error(f"통합 설정 명령어({setting_type}) 처리 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send(f"❌ 設定中にエラーが発生しました. 詳細はボットのログを確認してください。", ephemeral=True)

# ... (파일 하단은 이전과 동일하므로 생략) ...
