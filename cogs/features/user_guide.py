2025-11-24 03:27:10 - ERROR - [cogs.features.user_guide] 역할/닉네임 업데이트 중 오류: name 'new_role_ids' is not defined
Traceback (most recent call last):
  File "/app/cogs/features/user_guide.py", line 74, in approve
    if year_map: new_role_ids.append(get_id(year_map['key']))
                 ^^^^^^^^^^^^
NameError: name 'new_role_ids' is not defined
2025-11-24 03:27:21 - ERROR - [cogs.features.user_guide] 역할/닉네임 업데이트 중 오류: name 'new_role_ids' is not defined
Traceback (most recent call last):
  File "/app/cogs/features/user_guide.py", line 74, in approve
    if year_map: new_role_ids.append(get_id(year_map['key']))
                 ^^^^^^^^^^^^
NameError: name 'new_role_ids' is not defined



class GuideThreadView(ui.View):
    def __init__(self, cog: 'UserGuide'):
        super().__init__(timeout=None)
        self.cog = cog
    async def _get_steps_and_page(self, interaction: discord.Interaction):
        steps = await self.cog.get_guide_steps()
        if not interaction.message.embeds: return None, 0
        match = re.search(r"(\d+)/(\d+)", interaction.message.embeds[0].footer.text)
        return steps, int(match.group(1)) - 1 if match else 0
    async def _update_view_state(self, new_page: int, total_pages: int):
        prev, next_btn, intro = [discord.utils.get(self.children, custom_id=cid) for cid in ["guide_persistent_prev", "guide_persistent_next", "guide_persistent_intro"]]
        if prev: prev.disabled = (new_page == 0)
        if next_btn: next_btn.disabled = (new_page == total_pages - 1)
        if intro: intro.disabled = (new_page != total_pages - 1)
    @ui.button(label="◀ 이전", style=discord.ButtonStyle.secondary, custom_id="guide_persistent_prev")
    async def go_previous(self, i: discord.Interaction, b: ui.Button):
        steps, page = await self._get_steps_and_page(i)
        if not steps or page <= 0: return await i.response.defer()
        new_page = page - 1
        await self._update_view_state(new_page, len(steps))
        await i.response.edit_message(embed=format_embed_from_db(steps[new_page], user_mention=i.user.mention), view=self)
    @ui.button(label="다음 ▶", style=discord.ButtonStyle.primary, custom_id="guide_persistent_next")
    async def go_next(self, i: discord.Interaction, b: ui.Button):
        steps, page = await self._get_steps_and_page(i)
        if not steps or page >= len(steps) - 1: return await i.response.defer()
        new_page = page + 1
        await self._update_view_state(new_page, len(steps))
        await i.response.edit_message(embed=format_embed_from_db(steps[new_page], user_mention=i.user.mention), view=self)
    @ui.button(label="자기소개서 작성하기", style=discord.ButtonStyle.success, emoji="📝", custom_id="guide_persistent_intro", disabled=True)
    async def open_intro_form(self, i: discord.Interaction, b: ui.Button):
        await i.response.send_modal(IntroductionFormModal(self.cog))


class UserGuidePanelView(ui.View):
    def __init__(self, cog: 'UserGuide'):
        super().__init__(timeout=None)
        self.cog = cog
    async def setup_buttons(self):
        self.clear_items()
        comps = await get_panel_components_from_db('user_guide')
        comp = comps[0] if comps else {}
        btn = ui.Button(label=comp.get('label', "안내 시작하기"), style=discord.ButtonStyle.success, emoji=comp.get('emoji', "👋"), custom_id=comp.get('component_key', "start_user_guide"))
        btn.callback = self.start_guide_callback
        self.add_item(btn)
    async def start_guide_callback(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        if self.cog.has_active_thread(i.user):
            return await i.followup.send(f"❌ 이미 진행 중인 안내 스레드(<#{self.cog.active_guide_threads.get(i.user.id)}>)가 있습니다.", ephemeral=True)
        try:
            if (guest_rid := get_id("role_guest")) and (guest_role := i.guild.get_role(guest_rid)) and guest_role not in i.user.roles:
                await i.user.add_roles(guest_role, reason="안내 가이드 시작")
            thread = await i.channel.create_thread(name=f"👋ㅣ{i.user.display_name}님의-안내", type=discord.ChannelType.private_thread)
            self.cog.active_guide_threads[i.user.id] = thread.id
            steps = await self.cog.get_guide_steps()
            if not steps: raise ValueError("DB에서 안내 가이드 페이지를 불러올 수 없습니다.")
            guide_view = self.cog.guide_thread_view_instance
            await guide_view._update_view_state(0, len(steps))
            await thread.send(content=f"{i.user.mention}", embed=format_embed_from_db(steps[0], user_mention=i.user.mention), view=guide_view, allowed_mentions=discord.AllowedMentions(users=True, roles=False))
            fu_msg = await i.followup.send(f"✅ 안내 스레드를 생성했습니다: {thread.mention}", ephemeral=True, wait=True)
            await asyncio.sleep(10)
            await fu_msg.delete()
        except Exception as e:
            self.cog.active_guide_threads.pop(i.user.id, None)
            logger.error(f"유저 안내 스레드 생성 중 오류: {e}", exc_info=True)
            await i.followup.send("❌ 스레드 생성 중 오류가 발생했습니다.", ephemeral=True)

class IntroductionFormModal(ui.Modal, title="자기소개서 작성"):
    name = ui.TextInput(label="이름", placeholder="한글/공백 포함 8자 이하", required=True, max_length=8)
    birth_year_str = ui.TextInput(label="출생년도 (YYYY)", placeholder="예: 1998, 2005 (4자리로 입력)", required=True, min_length=4, max_length=4)
    gender = ui.TextInput(label="성별", placeholder="성별을 알려주세요.", required=True, max_length=10)
    join_path = ui.TextInput(label="가입 경로", placeholder="어떻게 우리 서버를 알게 되셨나요?", style=discord.TextStyle.paragraph, required=True)

    def __init__(self, cog: 'UserGuide'):
        super().__init__()
        self.cog = cog

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        name_input = self.name.value
        if len(name_input) > 8 or not re.match(r"^[가-힣 ]+$", name_input):
            return await interaction.followup.send("❌ 이름은 한글과 공백만 사용하여 8자 이하로 입력해주세요.", ephemeral=True)
        
        try:
            year = int(self.birth_year_str.value)
            if not (1950 <= year <= datetime.now().year - 13):
                return await interaction.followup.send("❌ 유효하지 않은 출생년도입니다. (만 13세 이상)", ephemeral=True)
        except ValueError:
            return await interaction.followup.send("❌ 출생년도는 4자리 숫자로 입력해주세요.", ephemeral=True)

        approval_embed = discord.Embed(
            title="📝 자기소개서 제출됨",
            description=f"{interaction.user.mention}님이 자기소개서를 제출했습니다.\n아래 내용을 확인 후 `수락` 버튼을 눌러주세요.",
            color=discord.Color.yellow()
        )
        approval_embed.add_field(name="신청 이름", value=name_input.strip(), inline=True)
        approval_embed.add_field(name="출생년도", value=self.birth_year_str.value, inline=True)
        approval_embed.add_field(name="성별", value=self.gender.value, inline=True)
        approval_embed.add_field(name="가입 경로", value=self.join_path.value, inline=False)
        approval_embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar)
        
        notify_role_id = get_id("role_notify_guide_approval")
        mention_str = f"<@&{notify_role_id}>" if notify_role_id else "스태프 여러분,"
        
        # Cog에 미리 등록된 approval_view_instance를 사용합니다.
        await interaction.channel.send(
            content=mention_str, embed=approval_embed, view=self.cog.approval_view_instance,
            allowed_mentions=discord.AllowedMentions(roles=True)
        )
        await interaction.followup.send("✅ 자기소개서를 제출했습니다. 스태프 확인 후 역할이 지급됩니다.", ephemeral=True)


class UserGuide(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.panel_channel_id: Optional[int] = None
        self.public_intro_channel_id: Optional[int] = None
        self.active_guide_threads: Dict[int, int] = {}
        # ▼▼▼ [핵심 수정 2/3] Cog가 자신의 View 인스턴스를 소유하도록 변경 ▼▼▼
        self.panel_view_instance = UserGuidePanelView(self)
        self.guide_thread_view_instance = GuideThreadView(self)
        self.approval_view_instance = GuideApprovalView()
        # ▲▲▲ [수정 완료] ▲▲▲
        logger.info("UserGuide Cog가 성공적으로 초기화되었습니다.")
        
    async def cog_load(self): 
        await self.load_configs()
        
    # ▼▼▼ [핵심 수정 3/3] register_persistent_views를 올바르게 수정 ▼▼▼
    async def register_persistent_views(self):
        self.bot.add_view(self.panel_view_instance)
        self.bot.add_view(self.guide_thread_view_instance)
        self.bot.add_view(self.approval_view_instance)
        logger.info("✅ 신규 유저 안내 시스템의 영구 View 3개가 성공적으로 등록되었습니다.")
    # ▲▲▲ [수정 완료] ▲▲▲
        
    async def load_configs(self): 
        self.panel_channel_id = get_id("user_guide_panel_channel_id")
        self.public_intro_channel_id = get_id("introduction_public_channel_id")
        logger.info("[UserGuide Cog] DB로부터 설정을 로드했습니다.")
        
    async def get_guide_steps(self) -> List[Dict[str, Any]]:
        keys = ["guide_thread_page_1", "guide_thread_page_2", "guide_thread_page_verification", "guide_thread_page_4", "guide_thread_page_5"]
        return [data for key in keys if (data := await get_embed_from_db(key))]
        
    def has_active_thread(self, user: discord.Member) -> bool:
        tid = self.active_guide_threads.get(user.id)
        if not tid: return False
        if user.guild.get_thread(tid): return True
        else: self.active_guide_threads.pop(user.id, None); return False

    @commands.Cog.listener()
    async def on_thread_delete(self, thread):
        uid = next((uid for uid, tid in self.active_guide_threads.items() if tid == thread.id), None)
        if uid: 
            self.active_guide_threads.pop(uid, None)
            logger.info(f"안내 스레드(ID: {thread.id})가 삭제되어 목록에서 제거되었습니다.")
            
    async def regenerate_panel(self, channel: discord.TextChannel, panel_key: str = "panel_user_guide") -> bool:
        base_key, embed_key = panel_key.replace("panel_", ""), panel_key
        try:
            if (info := get_panel_id(base_key)) and (old_id := info.get('message_id')):
                try: await (await channel.fetch_message(old_id)).delete()
                except (discord.NotFound, discord.Forbidden): pass
            embed_data = await get_embed_from_db(embed_key)
            if not embed_data: 
                logger.warning(f"DB에서 '{embed_key}'를 찾을 수 없어 패널 생성을 건너뜁니다.")
                return False
            await self.panel_view_instance.setup_buttons()
            new_msg = await channel.send(embed=discord.Embed.from_dict(embed_data), view=self.panel_view_instance)
            await save_panel_id(base_key, new_msg.id, channel.id)
            logger.info(f"✅ {panel_key} 패널을 #{channel.name}에 새로 생성했습니다.")
            return True
        except Exception as e: 
            logger.error(f"❌ {panel_key} 패널 재설치 중 오류: {e}", exc_info=True)
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(UserGuide(bot))
