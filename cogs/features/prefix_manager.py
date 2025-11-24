# cogs/features/prefix_manager.py

import discord
from discord.ext import commands
import logging
from typing import Set
import asyncio 

from utils.database import get_config, get_id
from utils.ui_defaults import ADMIN_ROLE_KEYS

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
        """
        role_configs = get_config("UI_ROLE_KEY_MAP", {})
        member_role_ids = {role.id for role in member.roles}

        # 1. 현재 멤버가 가져야 할 접두사 역할 찾기 (가장 높은 우선순위)
        user_prefix_roles = [
            config for key, config in role_configs.items()
            if get_id(key) in member_role_ids and config.get("is_prefix")
        ]
        highest_priority_role_config = max(user_prefix_roles, key=lambda r: r.get("priority", 0)) if user_prefix_roles else None

        # 2. 기본 이름(base_name) 추출하기
        # base_name이 주어지지 않았다면, 현재 닉네임에서 기존 접두사를 떼어내야 합니다.
        if not base_name.strip():
            current_nick = member.nick or member.name
            temp_name = current_nick.strip()

            # DB에 등록된 모든 가능한 접두사와 접미사 수집
            all_prefixes = []
            all_suffixes = []
            
            for config in role_configs.values():
                if config.get("is_prefix") and (symbol := config.get("prefix_symbol")):
                    p_format = config.get("prefix_format", "「{symbol}」")
                    # 포맷에서 실제 텍스트 생성 후 양옆 공백 제거
                    raw_prefix = p_format.format(symbol=symbol).strip()
                    if raw_prefix:
                        all_prefixes.append(raw_prefix)
                    
                    s_format = config.get("suffix", "").strip()
                    if s_format:
                        all_suffixes.append(s_format)
            
            # 긴 것부터 검사해야 부분 일치 오류를 방지함 (예: '대장' vs '대장군')
            all_prefixes.sort(key=len, reverse=True)
            all_suffixes.sort(key=len, reverse=True)

            # ▼▼▼ [수정 핵심] 접미사 먼저 제거 후 공백 정리
            for s in all_suffixes:
                if temp_name.endswith(s):
                    temp_name = temp_name[:-len(s)].strip()
                    break # 접미사는 하나만 있다고 가정
            
            # ▼▼▼ [수정 핵심] 접두사 제거 후 공백 정리
            # 기존에는 공백까지 정확히 맞아야 했으나, 이제는 텍스트만 맞으면 제거합니다.
            for p in all_prefixes:
                if temp_name.startswith(p):
                    temp_name = temp_name[len(p):].strip()
                    break # 접두사는 하나만 있다고 가정
            
            base = temp_name
        else:
            base = base_name.strip()

        # 3. 접두사 예외 역할 처리 (관리자 역할 등)
        no_prefix_role_keys = set(ADMIN_ROLE_KEYS)
        no_prefix_role_ids = {get_id(key) for key in no_prefix_role_keys if get_id(key)}
        user_has_no_prefix_role = bool(no_prefix_role_ids.intersection(member_role_ids))

        final_nick = base

        # 4. 새로운 접두사/접미사 결합
        if highest_priority_role_config and not user_has_no_prefix_role:
            if symbol := highest_priority_role_config.get("prefix_symbol"):
                prefix_format = highest_priority_role_config.get("prefix_format", "「{symbol}」")
                suffix = highest_priority_role_config.get("suffix", "")
                
                # 여기서 봇이 의도하는 포맷대로 결합 (일반적으로 접두사 뒤에 공백 1개)
                full_prefix = prefix_format.format(symbol=symbol)
                final_nick = f"{full_prefix} {base}{suffix}"
        
        # 5. 길이 제한 처리 (디스코드 닉네임 최대 32자)
        if len(final_nick) > 32:
            prefix_str, suffix_str = "", ""
            # 적용하려던 접두사/접미사 길이 계산
            if highest_priority_role_config and not user_has_no_prefix_role and (symbol := highest_priority_role_config.get("prefix_symbol")):
                p_format = highest_priority_role_config.get("prefix_format", "「{symbol}」")
                s_format = highest_priority_role_config.get("suffix", "")
                prefix_str = f"{p_format.format(symbol=symbol)} "
                suffix_str = s_format
            
            # 기본 이름(base)을 잘라서 길이를 맞춤
            allowed_base_len = 32 - (len(prefix_str) + len(suffix_str))
            if allowed_base_len > 0:
                base = base[:allowed_base_len]
                final_nick = f"{prefix_str}{base}{suffix_str}"
            else:
                # 접두사가 너무 길면 그냥 자름
                final_nick = final_nick[:32]
            
        return final_nick

async def setup(bot: commands.Bot):
    await bot.add_cog(PrefixManager(bot))
