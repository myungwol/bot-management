# cogs/features/prefix_manager.py

import discord
from discord.ext import commands
import logging
from typing import Set
import asyncio 

from utils.database import get_config, get_id

logger = logging.getLogger(__name__)

class PrefixManager(commands.Cog):
    """
    사용자의 역할에 따라 닉네임의 접두사를 자동으로 관리하는 Cog입니다.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("PrefixManager Cog가 성공적으로 초기화되었습니다.")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """역할 변경 감지 시, 닉네임 자동 업데이트"""
        if after.bot or before.roles == after.roles:
            return
        
        await asyncio.sleep(1) 
        
        try:
            new_nick = await self.get_final_nickname(after)
            if after.nick != new_nick:
                await after.edit(nick=new_nick, reason="역할 변경으로 인한 칭호 자동 업데이트")
        except discord.Forbidden:
            pass
        except Exception as e:
            logger.error(f"{after.display_name}의 자동 닉네임 업데이트 중 오류: {e}", exc_info=True)

    async def apply_prefix(self, member: discord.Member, base_name: str) -> str:
        """
        주어진 기본 이름에 올바른 접두사를 붙여 최종 닉네임을 반환하고,
        실제로 유저에게 적용까지 시도하는 공개 메소드.
        """
        final_name = await self.get_final_nickname(member, base_name=base_name)
        try:
            if member.nick != final_name:
                await member.edit(nick=final_name, reason="닉네임 승인 또는 역할 업데이트")
        except discord.Forbidden:
            logger.warning(f"접두사 적용 실패: {member.display_name}의 닉네임을 변경할 권한이 없습니다.")
        except Exception as e:
            logger.error(f"{member.display_name}에게 접두사 적용 중 오류: {e}", exc_info=True)
        return final_name
            
    async def get_final_nickname(self, member: discord.Member, base_name: str = "") -> str:
        """
        멤버의 역할에 따라 최종 닉네임을 계산하여 반환하는 핵심 로직.
        다른 Cog에서도 호출할 수 있도록 분리됨.
        """
        role_configs = get_config("UI_ROLE_KEY_MAP", {})
        member_role_ids = {role.id for role in member.roles}

        # 1. 적용할 접두사 역할 찾기
        user_prefix_roles = [
            config for key, config in role_configs.items()
            if get_id(key) in member_role_ids and config.get("is_prefix")
        ]
        highest_priority_role_config = max(user_prefix_roles, key=lambda r: r.get("priority", 0)) if user_prefix_roles else None

        # 2. 기본 이름(base_name) 결정하기
        base = ""
        if base_name.strip():
            base = base_name.strip()
        else:
            current_nick = member.nick or member.name
            base = current_nick
            all_possible_prefixes = []
            for config in role_configs.values():
                if config.get("is_prefix") and (symbol := config.get("prefix_symbol")):
                    p_format = config.get("prefix_format", "「{symbol}」")
                    s_format = config.get("suffix", "")
                    all_possible_prefixes.append((p_format.format(symbol=symbol), s_format))
            
            for prefix_str, suffix_str in sorted(all_possible_prefixes, key=lambda x: len(x[0]) + len(x[1]), reverse=True):
                if current_nick.startswith(f"{prefix_str} ") and current_nick.endswith(suffix_str):
                    temp_name = current_nick[len(prefix_str) + 1:]
                    base = temp_name[:-len(suffix_str)] if suffix_str else temp_name
                    break

        # ▼▼▼ [핵심 수정] UI_ROLE_KEY_MAP -> role_configs 로 변경 ▼▼▼
        # 3. 접두사 예외 역할 처리
        no_prefix_role_keys = {key for key, config in role_configs.items() if not config.get("is_prefix")}
        # ▲▲▲ [수정 완료] ▲▲▲
        
        no_prefix_role_ids = {get_id(key) for key in no_prefix_role_keys if get_id(key)}
        user_has_no_prefix_role = bool(no_prefix_role_ids.intersection(member_role_ids))

        final_nick = base.strip()

        # 4. 최종 닉네임 조합
        if highest_priority_role_config and not user_has_no_prefix_role:
            if symbol := highest_priority_role_config.get("prefix_symbol"):
                prefix_format = highest_priority_role_config.get("prefix_format", "「{symbol}」")
                suffix = highest_priority_role_config.get("suffix", "")
                full_prefix = prefix_format.format(symbol=symbol)
                final_nick = f"{full_prefix} {base.strip()}{suffix}"
        
        # 5. 길이 제한 처리
        if len(final_nick) > 32:
            prefix_str, suffix_str = "", ""
            if highest_priority_role_config and not user_has_no_prefix_role and (symbol := highest_priority_role_config.get("prefix_symbol")):
                p_format = highest_priority_role_config.get("prefix_format", "「{symbol}」")
                s_format = highest_priority_role_config.get("suffix", "")
                prefix_str = f"{p_format.format(symbol=symbol)} "
                suffix_str = s_format
            
            allowed_base_len = 32 - (len(prefix_str) + len(suffix_str))
            base = base.strip()[:allowed_base_len]
            final_nick = f"{prefix_str}{base}{suffix_str}"
            
        return final_nick

async def setup(bot: commands.Bot):
    await bot.add_cog(PrefixManager(bot))
