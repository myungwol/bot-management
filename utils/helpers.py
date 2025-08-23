# bot-management/utils/helpers.py
"""
봇 프로젝트 전반에서 사용되는 보조 함수들을 모아놓은 파일입니다.
"""
import discord
import copy
import logging
from typing import Any, Dict
import re
# [수정] database.py의 get_config 함수를 불러오기 위한 import문 추가
from .database import get_config

logger = logging.getLogger(__name__)


def format_embed_from_db(embed_data: Dict[str, Any], **kwargs: Any) -> discord.Embed:
    """
    데이터베이스에서 가져온 dict 형식의 임베드 데이터를 실제 discord.Embed 객체로 변환합니다.
    - 임베드의 title, description, field 등에 포함된 플레이스홀더({key})를 kwargs 값으로 안전하게 포맷팅합니다.
    - 원본 데이터가 변경되지 않도록 깊은 복사를 사용합니다.
    - 존재하지 않는 키로 포맷팅을 시도할 경우, 오류를 발생시키지 않고 플레이스홀더를 그대로 남겨둡니다.

    Args:
        embed_data (Dict[str, Any]): DB에서 불러온 임베드 데이터. discord.Embed.from_dict()가 요구하는 형식이어야 합니다.
        **kwargs (Any): 플레이스홀더를 대체할 값들. (예: member_mention="<@123>", member_name="홍길동")

    Returns:
        discord.Embed: 포맷팅이 완료된 discord.Embed 객체. 오류 발생 시 기본 오류 임베드를 반환합니다.
    """
    if not isinstance(embed_data, dict):
        logger.error(f"임베드 데이터가 dict 형식이 아닙니다. 실제 타입: {type(embed_data)}")
        error_embed = discord.Embed(
            title="오류 발생",
            description="임베드 데이터를 불러오는 데 실패했습니다.\n관리자에게 문의해주세요.",
            color=discord.Color.red()
        )
        return error_embed
    
    formatted_data: Dict[str, Any] = copy.deepcopy(embed_data)

    class SafeFormatter(dict):
        def __missing__(self, key: str) -> str:
            return f'{{{key}}}'

    safe_kwargs = SafeFormatter(**kwargs)
    
    try:
        if formatted_data.get('title') and isinstance(formatted_data['title'], str):
            formatted_data['title'] = formatted_data['title'].format_map(safe_kwargs)
            
        if formatted_data.get('description') and isinstance(formatted_data['description'], str):
            formatted_data['description'] = formatted_data['description'].format_map(safe_kwargs)
            
        if formatted_data.get('footer') and isinstance(formatted_data.get('footer'), dict):
            if formatted_data['footer'].get('text') and isinstance(formatted_data['footer']['text'], str):
                formatted_data['footer']['text'] = formatted_data['footer']['text'].format_map(safe_kwargs)
                
        if formatted_data.get('fields') and isinstance(formatted_data.get('fields'), list):
            for field in formatted_data['fields']:
                if isinstance(field, dict):
                    if field.get('name') and isinstance(field['name'], str):
                        field['name'] = field['name'].format_map(safe_kwargs)
                    if field.get('value') and isinstance(field.get('value'), str):
                        field['value'] = field['value'].format_map(safe_kwargs)
                        
        return discord.Embed.from_dict(formatted_data)
        
    except (KeyError, ValueError) as e:
        logger.error(f"임베드 데이터 포맷팅 중 오류 발생: {e}", exc_info=True)
        try:
            return discord.Embed.from_dict(embed_data)
        except Exception as final_e:
            logger.critical(f"원본 임베드 데이터로도 임베드 생성 실패: {final_e}", exc_info=True)
            fatal_error_embed = discord.Embed(
                title="치명적 오류",
                description="임베드 생성에 실패했습니다. 데이터 형식을 확인해주세요.",
                color=discord.Color.dark_red()
            )
            return fatal_error_embed

def get_clean_display_name(member: discord.Member) -> str:
    """
    멤버의 display_name에서 역할 접두사(예: 『칭호』)를 제거한 순수한 이름을 반환합니다.

    Args:
        member (discord.Member): 대상 멤버 객체

    Returns:
        str: 역할 접두사가 제거된 이름
    """
    display_name = member.display_name
    prefix_hierarchy = get_config("NICKNAME_PREFIX_HIERARCHY", [])
    
    for prefix_name in prefix_hierarchy:
        prefix_to_check = f"『 {prefix_name} 』"
        if display_name.startswith(prefix_to_check):
            return re.sub(rf"^{re.escape(prefix_to_check)}\s*", "", display_name).strip()
    return display_name

# --- [✅ 신규 추가] ---
def calculate_xp_for_level(level: int) -> int:
    """
    특정 레벨에 도달하기 위해 필요한 *총* 경험치를 계산합니다.
    (예: level=1 -> 0 XP, level=2 -> 155 XP)
    공식: 5 * (L^2) + 50 * L + 100 (다음 레벨까지 필요한 양)
    """
    if level <= 1:
        return 0
    
    # 1부터 (L-1)까지 각 레벨업에 필요한 경험치를 합산
    total_xp = 0
    for l in range(1, level):
        total_xp += 5 * (l ** 2) + (50 * l) + 100
    return total_xp
