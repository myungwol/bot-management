# cogs/server/onboarding.py
import discord
from discord.ext import commands
from discord import ui
# ... (다른 import문은 변경 없음) ...

from utils.database import (
    get_id, save_panel_id, get_panel_id, get_cooldown, set_cooldown, 
    get_embed_from_db, get_onboarding_steps, get_panel_components_from_db, get_config
)
# ... (다른 import문은 변경 없음) ...

logger = logging.getLogger(__name__)

# (RejectionReasonModal, IntroductionModal, ApprovalView, OnboardingGuideView, OnboardingPanelView 클래스는 변경 없음)
# ... (기존 클래스 코드 생략) ...

class Onboarding(commands.Cog):
    def __init__(self, bot: commands.Bot):
        # ... (생성자는 변경 없음) ...
    # ... (get_user_lock, approval_channel, register_persistent_views, cog_load, load_configs 등 다른 메서드는 변경 없음) ...
    
    # [수정] regenerate_panel 함수
    async def regenerate_panel(self, channel: discord.TextChannel) -> bool:
        panel_key = "onboarding"
        embed_key = "panel_onboarding"

        try:
            panel_info = get_panel_id(panel_key)
            if panel_info and (old_id := panel_info.get('message_id')):
                try: 
                    old_message = await channel.fetch_message(old_id)
                    await old_message.delete()
                except (discord.NotFound, discord.HTTPException): pass

            embed_data = await get_embed_from_db(embed_key)
            if not embed_data:
                logger.warning(f"DB에서 '{embed_key}' 임베드 데이터를 찾을 수 없어, 패널 생성을 건너뜁니다.")
                return False
                
            embed = discord.Embed.from_dict(embed_data)
            if self.view_instance is None:
                await self.register_persistent_views()
            
            await self.view_instance.setup_buttons()
            new_message = await channel.send(embed=embed, view=self.view_instance)
            await save_panel_id(panel_key, new_message.id, channel.id)
            logger.info(f"✅ {panel_key} 패널을 성공적으로 새로 생성했습니다. (채널: #{channel.name})")
            return True
        except Exception as e:
            logger.error(f"❌ {panel_key} 패널 재설치 중 오류 발생: {e}", exc_info=True)
            return False

async def setup(bot: commands.Bot):
    await bot.add_cog(Onboarding(bot))

# (생략된 클래스들의 전체 코드를 포함하여 파일을 저장해야 합니다)
