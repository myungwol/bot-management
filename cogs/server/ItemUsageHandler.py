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
            guild_id = int(request['guild_id'])
            user_id = int(request['user_id'])
            item_key = request['item_key']

            guild = self.bot.get_guild(guild_id)
            if not guild:
                raise Exception(f"서버(ID: {guild_id})를 찾을 수 없습니다.")
            
            member = guild.get_member(user_id)
            if not member:
                raise Exception(f"멤버(ID: {user_id})를 서버에서 찾을 수 없습니다.")

            usable_items_config = get_config("USABLE_ITEMS", {})
            item_info = usable_items_config.get(item_key)
            item_role_id = get_id(item_key)

            if not item_info or not item_role_id:
                raise Exception(f"'{item_key}'는 유효하지 않은 아이템입니다.")

            item_type = item_info.get("type")
            success = False

            if item_type == "warning_deduction":
                warning_cog = self.bot.get_cog("WarningSystem")
                if warning_cog and hasattr(warning_cog, 'deduct_warning_points'):
                    success = await warning_cog.deduct_warning_points(
                        moderator=self.bot.user,
                        target=member,
                        amount=item_info.get("value", -1),
                        reason=f"'{item_info['name']}' 아이템 사용"
                    )
            
            # 향후 다른 아이템 타입 추가 가능
            # elif item_type == "some_other_type":
            #     success = await some_other_cog.do_something()

            if success:
                role_to_remove = guild.get_role(item_role_id)
                if role_to_remove:
                    await member.remove_roles(role_to_remove, reason="아이템 사용 완료")
                
                try:
                    await member.send(f"✅ **{guild.name}** 서버에서 사용하신 '{item_info['name']}' 아이템의 효과가 적용되었습니다.")
                except discord.Forbidden:
                    pass # DM 실패는 괜찮음
                
                await supabase.table('item_usage_requests').update({'processed': True}).eq('id', request_id).execute()
                logger.info(f"'{member.display_name}'님의 '{item_info['name']}' 아이템 사용 요청을 성공적으로 처리했습니다.")

            else:
                raise Exception("아이템 효과 적용에 실패했습니다.")

        except Exception as e:
            logger.error(f"아이템 사용 요청(ID: {request_id}) 처리 중 오류: {e}")
            # 실패한 요청은 processed를 True로 설정하여 무한 루프 방지
            await supabase.table('item_usage_requests').update({'processed': True}).eq('id', request_id).execute()

    @check_for_requests.before_loop
    async def before_check_loop(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(ItemUsageHandler(bot))
