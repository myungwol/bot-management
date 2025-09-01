# utils/helpers.py (양쪽 봇 공용)
"""
봇 프로젝트 전반에서 사용되는 보조 함수들을 모아놓은 파일입니다.
"""
import discord
import copy
import logging
from typing import Any, Dict
import re
from .database import get_config

logger = logging.getLogger(__name__)

# [✅✅✅ 핵심 추가 ✅✅✅]
# 초를 "X시간 Y분 Z초" 형식으로 변환하는 함수
def format_seconds_to_hms(seconds: float) -> str:
    """초를 시, 분, 초 형식의 문자열로 변환합니다."""
    if seconds <= 0:
        return "0초"
    
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}시간")
    if minutes > 0:
        parts.append(f"{minutes}분")
    if secs > 0 or not parts: # 남은 시간이 0초이거나, 전체가 1분 미만일 때 초를 표시
        parts.append(f"{secs}초")
        
    return ' '.join(parts)

def format_embed_from_db(embed_data: Dict[str, Any], **kwargs: Any) -> discord.Embed:
    if not isinstance(embed_data, dict):
        logger.error(f"임베드 데이터가 dict 형식이 아닙니다. 실제 타입: {type(embed_data)}")
        return discord.Embed(title="오류 발생", description="임베드 데이터를 불러오는 데 실패했습니다.", color=discord.Color.red())
    
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
                    if field.get('value') and isinstance(field['value'], str):
                        field['value'] = field['value'].format_map(safe_kwargs)
        return discord.Embed.from_dict(formatted_data)
    except (KeyError, ValueError) as e:
        logger.error(f"임베드 데이터 포맷팅 중 오류 발생: {e}", exc_info=True)
        try:
            return discord.Embed.from_dict(embed_data)
        except Exception as final_e:
            logger.critical(f"원본 임베드 데이터로도 임베드 생성 실패: {final_e}", exc_info=True)
            return discord.Embed(title="치명적 오류", description="임베드 생성에 실패했습니다. 데이터 형식을 확인해주세요.", color=discord.Color.dark_red())

def get_clean_display_name(member: discord.Member) -> str:
    display_name = member.display_name
    prefix_hierarchy = get_config("NICKNAME_PREFIX_HIERARCHY", [])
    for prefix_name in prefix_hierarchy:
        prefix_to_check = f"『 {prefix_name} 』"
        if display_name.startswith(prefix_to_check):
            return re.sub(rf"^{re.escape(prefix_to_check)}\s*", "", display_name).strip()
    return display_name

def calculate_xp_for_level(level: int) -> int:
    if level <= 1:
        return 0
    total_xp = 0
    for l in range(1, level):
        total_xp += 5 * (l ** 2) + (50 * l) + 100
    return total_xp
