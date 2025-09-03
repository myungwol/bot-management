# cogs/server/ItemUsageHandler.py
import discord
from discord.ext import commands, tasks
import logging

from utils.database import supabase, get_config, get_id

logger = logging.getLogger(__name__)

class ItemUsageHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.check_for_requests.start()
        logger.info("ItemUsageHandler Cog가 성공적으로 초기화되었습니다.")

    def cog_unload(self):
        self.check_for_requests.cancel()

    @tasks.loop(seconds=15.0)
    async def check_for_requests(self):
        try:
            response = await supabase.table('item_usage_requests').select('*').eq('processed', False).execute()
            if not response or not response.data:
                return

            for request in response.data:
                await self.process_request(request)

        except Exception as e:
            logger.error(f"아이템 사용 요청 확인 중 오류 발생: {e}", exc_info=True)

    async def process_request(self, request: dict):
        request_id = request['id']
        try:
            guild = self.bot.get_guild(int(request['guild_id']))
            member = guild.get_member(int(request['user_id'])) if guild else None
            item_key = request['item_key']
            
            if not member:
                raise Exception(f"멤버(ID: {request['user_id']})를 서버(ID: {request['guild_id']})에서 찾을 수 없습니다.")

            usable_items_config = get_config("USABLE_ITEMS", {})
            item_info = usable_items_config.get(item_key)
            item_role = guild.get_role(get_id(item_key))

            if not item_info or not item_role:
                raise Exception(f"'{item_key}'는 유효하지 않은 아이템입니다.")

            success = False
            if item_info['type'] == 'request_to_admin':
                warning_cog = self.bot.get_cog("WarningSystem")
                if warning_cog and hasattr(warning_cog, 'deduct_warning_points'):
                    success = await warning_cog.deduct_warning_points(
                        moderator=self.bot.user,
                        target=member,
                        amount=item_info.get("value", -1),
                        reason=f"'{item_info['name']}' 아이템 사용"
                    )
            
            if success:
                await member.remove_roles(item_role, reason="아이템 사용 완료")
                try:
                    await member.send(f"✅ **{guild.name}** 서버에서 사용하신 '{item_info['name']}' 아이템의 효과가 적용되었습니다.")
                except discord.Forbidden:
                    pass
                
                await supabase.table('item_usage_requests').update({'processed': True}).eq('id', request_id).execute()
                logger.info(f"'{member.display_name}'님의 '{item_info['name']}' 아이템 사용 요청을 성공적으로 처리했습니다.")
            else:
                raise Exception("아이템 효과 적용에 실패했습니다.")

        except Exception as e:
            logger.error(f"아이템 사용 요청(ID: {request_id}) 처리 중 오류: {e}")
            await supabase.table('item_usage_requests').update({'processed': True}).eq('id', request_id).execute()

    @check_for_requests.before_loop
    async def before_check_loop(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(ItemUsageHandler(bot))
