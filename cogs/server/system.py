# cogs/server/system.py (줄바꿈 오류 수정 최종본)

import discord
from discord.ext import commands, tasks
from discord import app_commands, ui
import logging
import asyncio
from typing import Literal

# 로깅 설정
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

from utils.database import (get_channel_id_from_db, get_role_id, 
                           get_counter_configs, add_counter_config, remove_counter_config,
                           add_auto_role_button, remove_auto_role_button, get_auto_role_buttons)

class AutoRoleView(ui.View):
    def __init__(self, buttons_config: list | None = None):
        super().__init__(timeout=None)
        if buttons_config:
            for config in buttons_config:
                style_map = {
                    'primary': discord.ButtonStyle.primary, 'secondary': discord.ButtonStyle.secondary,
                    'success': discord.ButtonStyle.success, 'danger': discord.ButtonStyle.danger,
                }
                button = ui.Button(
                    label=config['button_label'], emoji=config.get('button_emoji'),
                    style=style_map.get(config.get('button_style', 'secondary'), discord.ButtonStyle.secondary),
                    custom_id=f"auto_role:{config['role_id']}"
                )
                button.callback = self.button_callback
                self.add_item(button)

    async def button_callback(self, interaction: discord.Interaction):
        custom_id = interaction.data['custom_id']
        role_id = int(custom_id.split(':')[1])
        if not isinstance(interaction.user, discord.Member):
            return await interaction.response.send_message("エラー: メンバー情報が見つかりません。", ephemeral=True)
        role = interaction.guild.get_role(role_id)
        if not role:
            return await interaction.response.send_message("エラー: この役職はもう存在しません。", ephemeral=True)
        try:
            if role in interaction.user.roles:
                await interaction.user.remove_roles(role)
                await interaction.response.send_message(f"✅ 役職「{role.name}」を解除しました。", ephemeral=True)
            else:
                await interaction.user.add_roles(role)
                await interaction.response.send_message(f"✅ 役職「{role.name}」を付与しました。", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("エラー: 役職を付与/解除する権限がボットにありません。", ephemeral=True)
        except Exception as e:
            logger.error(f"Error changing role for {interaction.user.name}: {e}", exc_info=True)
            await interaction.response.send_message("エラーが発生しました。", ephemeral=True)

class ServerSystem(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.bot.add_view(AutoRoleView(None))
        self.welcome_channel_id: int | None = None
        self.farewell_channel_id: int | None = None
        self.temp_user_role_id: int | None = None
        self.onboarding_panel_channel_id: int | None = None
        self.counter_configs = []
        self.update_tasks: dict[int, asyncio.Task] = {}
        logger.info("ServerSystem Cog initialized.")

    async def cog_load(self):
        await self.load_all_configs()
        self.update_counters_loop.start()

    def cog_unload(self):
        self.update_counters_loop.cancel()
        for task in self.update_tasks.values(): task.cancel()

    async def load_all_configs(self):
        self.welcome_channel_id = await get_channel_id_from_db("welcome_channel_id")
        self.farewell_channel_id = await get_channel_id_from_db("farewell_channel_id")
        self.temp_user_role_id = get_role_id("temp_user_role")
        self.onboarding_panel_channel_id = await get_channel_id_from_db("onboarding_panel_channel_id")
        self.counter_configs = await get_counter_configs()
        logger.info("[ServerSystem Cog] Loaded all configurations.")

    def _schedule_counter_update(self, guild: discord.Guild):
        guild_id = guild.id
        if guild_id in self.update_tasks and not self.update_tasks[guild_id].done(): self.update_tasks[guild_id].cancel()
        self.update_tasks[guild_id] = asyncio.create_task(self.delayed_update(guild))

    async def delayed_update(self, guild: discord.Guild):
        await asyncio.sleep(5)
        await self.update_all_counters(guild)

    async def update_all_counters(self, guild: discord.Guild):
        if not guild: return
        guild_configs = [config for config in self.counter_configs if config['guild_id'] == guild.id]
        if not guild_configs: return
        logger.info(f"Updating {len(guild_configs)} counters for guild {guild.name}...")
        all_members, human_members, bot_members, booster_count = guild.members, [m for m in guild.members if not m.bot], [m for m in guild.members if m.bot], guild.premium_subscription_count
        for config in guild_configs:
            channel = guild.get_channel(config['channel_id'])
            if not channel: continue
            count = 0
            counter_type = config['counter_type']
            if counter_type == 'total': count = len(all_members)
            elif counter_type == 'members': count = len(human_members)
            elif counter_type == 'bots': count = len(bot_members)
            elif counter_type == 'boosters': count = booster_count
            elif counter_type == 'role':
                role = guild.get_role(config['role_id'])
                if role: count = len(role.members)
                else: continue
            new_name = config['format_string'].format(count)
            if channel.name != new_name:
                try:
                    await channel.edit(name=new_name, reason="유저 카운터 자동 업데이트")
                    await asyncio.sleep(2)
                except discord.Forbidden:
                    logger.error(f"Permission denied to edit channel {channel.id}.")
                    break
                except Exception as e:
                    logger.error(f"Failed to update counter for channel {channel.id}: {e}", exc_info=True)

    @tasks.loop(minutes=10)
    async def update_counters_loop(self):
        logger.info("Running scheduled counter update...")
        for guild in self.bot.guilds: await self.update_all_counters(guild)

    @update_counters_loop.before_loop
    async def before_update_counters_loop(self):
        await self.bot.wait_until_ready()
        logger.info("Counter update loop is ready.")

    @commands.Cog.listener()
    async def on_ready(self):
        await asyncio.sleep(5)
        logger.info("Bot is ready. Performing initial counter update.")
        for guild in self.bot.guilds: self._schedule_counter_update(guild)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if member.bot: return
        if self.temp_user_role_id and (temp_role := member.guild.get_role(self.temp_user_role_id)):
            try: await member.add_roles(temp_role, reason="新規メンバーへの一時的な役割付与")
            except Exception as e: logger.error(f"Error adding temp role to {member.display_name}: {e}", exc_info=True)
        if self.welcome_channel_id and (welcome_channel := self.bot.get_channel(self.welcome_channel_id)):
            panel_mention = f"<#{self.onboarding_panel_channel_id}>" if self.onboarding_panel_channel_id else "案内のチャンネル"
            content = f"@everyone 新しい方がいらっしゃいました！{member.mention}さんがDico森にやってきました！"
            embed = discord.Embed(title=f"ようこそ！Dico森の新しい住人さん！ {member.display_name}さん！", description=f"**{member.guild.name}**へようこそ！\n\nまずは{panel_mention}に移動し、「里の案内・住人登録を始める」ボタンを押してガイドを**順番に**確認してください！", color=discord.Color.green())
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text="楽しいDico森での暮らしがあなたを待っています！")
            try: await welcome_channel.send(content=content, embed=embed, allowed_mentions=discord.AllowedMentions(everyone=True, users=True))
            except Exception as e: logger.error(f"Error sending welcome message: {e}", exc_info=True)
        self._schedule_counter_update(member.guild)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        if self.farewell_channel_id and (farewell_channel := self.bot.get_channel(self.farewell_channel_id)):
            content = f"@everyone 皆様にお知らせです。{member.display_name}さんがDico森を離れました。"
            embed = discord.Embed(title="さようなら！Dico森の住人さん...", description=f"**{member.display_name}**さんがDico森を離れました。\n\nまた会える日を楽しみにしています！", color=discord.Color.red())
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"住人: {member.display_name} ({member.id})")
            try: await farewell_channel.send(content=content, embed=embed, allowed_mentions=discord.AllowedMentions(everyone=True))
            except Exception as e: logger.error(f"Error sending farewell message: {e}", exc_info=True)
        self._schedule_counter_update(member.guild)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.roles != after.roles or before.premium_since != after.premium_since:
            self._schedule_counter_update(after.guild)

    counter_group = app_commands.Group(name="counter", description="유저 카운터 채널을 설정합니다.")
    @counter_group.command(name="setup", description="[管理者専用] 特定のチャンネルをユーザーカウンターとして設定します。")
    @app_commands.describe(channel="カウンターとして設定するボイスチャンネル", counter_type="表示する統計の種類", format_string="チャンネル名の表示形式 (例: 「メンバー数: {}」)", role="[役職カウンター用] カウントする役職")
    @app_commands.choices(counter_type=[app_commands.Choice(name="サーバー総メンバー数 (BOT含む)", value="total"), app_commands.Choice(name="メンバー数 (BOT除く)", value="members"), app_commands.Choice(name="BOT数", value="bots"), app_commands.Choice(name="サーバーブースター数", value="boosters"), app_commands.Choice(name="特定の役職を持つメンバー数", value="role")])
    @app_commands.checks.has_permissions(manage_channels=True)
    async def setup_counter(self, interaction: discord.Interaction, channel: discord.VoiceChannel, counter_type: str, format_string: str, role: discord.Role = None):
        if counter_type == 'role' and not role: return await interaction.response.send_message("エラー: 「役職メンバー数」を選択した場合は、役職を指定する必要があります。", ephemeral=True)
        if "{}" not in format_string: return await interaction.response.send_message("エラー: 表示形式には、数字に置き換わる `{}` を含める必要があります。", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        role_id = role.id if role else None
        await add_counter_config(channel.id, interaction.guild.id, counter_type, format_string, role_id)
        await self.load_all_configs()
        self._schedule_counter_update(interaction.guild)
        await interaction.followup.send(f"✅ チャンネル <#{channel.id}> が `{counter_type}` のカウンターとして設定されました。")

    @counter_group.command(name="remove", description="[管理者専用] チャンネルのカウンター設定を解除します。")
    @app_commands.describe(channel="カウンター設定を解除するチャンネル")
    @app_commands.checks.has_permissions(manage_channels=True)
    async def remove_counter(self, interaction: discord.Interaction, channel: discord.VoiceChannel):
        await interaction.response.defer(ephemeral=True)
        await remove_counter_config(channel.id)
        await self.load_all_configs()
        await interaction.followup.send(f"✅ チャンネル <#{channel.id}> のカウンター設定を解除しました。")

    autorole_group = app_commands.Group(name="autorole", description="自動役割付与パネルを管理します。")
    @autorole_group.command(name="panel-create", description="[管理者専用] 新しい自動役割付与パネルを作成します。")
    @app_commands.describe(channel="パネルを設置するチャンネル", title="パネルのタイトル", description="パネルの説明文 (改行は \\n を使用)")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole_panel_create(self, interaction: discord.Interaction, channel: discord.TextChannel, title: str, description: str):
        await interaction.response.defer(ephemeral=True)
        try:
            # [핵심] 받은 description 문자열에서 '\\n'을 실제 줄바꿈 문자인 '\n'으로 변경
            formatted_description = description.replace('\\n', '\n')

            embed = discord.Embed(title=title, description=formatted_description, color=discord.Color.blurple())
            view = AutoRoleView([])
            message = await channel.send(embed=embed, view=view)
            await interaction.followup.send(f"✅ 自動役割付与パネルを作成しました。\n**メッセージID:** `{message.id}`\nこのIDを使ってボタンを追加してください。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ パネル作成中にエラーが発生しました: {e}", ephemeral=True)

    @autorole_group.command(name="button-add", description="[管理者専用] 既存のパネルに役割ボタンを追加します。")
    @app_commands.describe(panel_message_id="ボタンを追加するパネルのメッセージID", role="付与する役職", label="ボタンに表示するテキスト", emoji="ボタンに表示する絵文字 (任意)", style="ボタンの色")
    @app_commands.choices(style=[app_commands.Choice(name="グレー (基本)", value="secondary"), app_commands.Choice(name="青 (おすすめ)", value="primary"), app_commands.Choice(name="緑 (肯定的)", value="success"), app_commands.Choice(name="赤 (注意)", value="danger")])
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole_button_add(self, interaction: discord.Interaction, panel_message_id: str, role: discord.Role, label: str, style: str, emoji: str = None):
        await interaction.response.defer(ephemeral=True)
        try:
            msg_id = int(panel_message_id)
            # [수정] 패널이 어느 채널에 있는지 알 수 없으므로, 명령어를 사용한 채널에서 찾도록 함
            panel_message = await interaction.channel.fetch_message(msg_id)
            if not panel_message or panel_message.author.id != self.bot.user.id:
                return await interaction.followup.send("エラー: 指定されたIDのメッセージが見つからないか、ボットのメッセージではありません。", ephemeral=True)
            await add_auto_role_button(msg_id, role.id, label, emoji, style)
            buttons_config = await get_auto_role_buttons(msg_id)
            new_view = AutoRoleView(buttons_config)
            await panel_message.edit(view=new_view)
            await interaction.followup.send(f"✅ パネルに役職「{role.name}」のボタンを追加しました。", ephemeral=True)
        except ValueError: await interaction.followup.send("エラー: メッセージIDは数字である必要があります。", ephemeral=True)
        except discord.NotFound: await interaction.followup.send("エラー: このチャンネルでそのIDのメッセージを見つけられませんでした。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ ボタン追加中にエラーが発生しました: {e}", exc_info=True)

    @autorole_group.command(name="button-remove", description="[管理者専用] 既存のパネルから役割ボタンを削除します。")
    @app_commands.describe(panel_message_id="ボタンを削除するパネルのメッセージID", role="削除するボタンに対応する役職")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def autorole_button_remove(self, interaction: discord.Interaction, panel_message_id: str, role: discord.Role):
        await interaction.response.defer(ephemeral=True)
        try:
            msg_id = int(panel_message_id)
            panel_message = await interaction.channel.fetch_message(msg_id)
            if not panel_message or panel_message.author.id != self.bot.user.id:
                return await interaction.followup.send("エラー: 指定されたIDのメッセージが見つからないか、ボットのメッセージではありません。", ephemeral=True)
            await remove_auto_role_button(msg_id, role.id)
            buttons_config = await get_auto_role_buttons(msg_id)
            new_view = AutoRoleView(buttons_config)
            await panel_message.edit(view=new_view)
            await interaction.followup.send(f"✅ パネルから役職「{role.name}」のボタンを削除しました。", ephemeral=True)
        except ValueError: await interaction.followup.send("エラー: メッセージIDは数字である必要があります。", ephemeral=True)
        except discord.NotFound: await interaction.followup.send("エラー: このチャンネルでそのIDのメッセージを見つけられませんでした。", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ ボタン削除中にエラーが発生しました: {e}", exc_info=True)

async def setup(bot: commands.Bot):
    cog = ServerSystem(bot)
    await bot.add_cog(cog)