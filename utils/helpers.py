# utils/helpers.py

import discord
import copy
import logging

logger = logging.getLogger(__name__)

def format_embed_from_db(embed_data: dict, **kwargs) -> discord.Embed:
    """
    데이터베이스에서 가져온 dict 형식의 임베드 데이터를 실제 discord.Embed 객체로 변환하고,
    플레이스홀더({key})를 kwargs 값으로 안전하게 포맷팅합니다.
    """
    if not isinstance(embed_data, dict):
        logger.error(f"임베드 데이터가 dict 형식이 아닙니다: {type(embed_data)}")
        return discord.Embed(title="오류", description="임베드 데이터를 불러오는 데 실패했습니다.", color=discord.Color.red())
    
    # 원본 데이터가 변경되지 않도록 깊은 복사를 사용합니다.
    formatted_data = copy.deepcopy(embed_data)

    # 존재하지 않는 키를 포맷팅할 때 에러를 발생시키지 않고 {key} 그대로 남겨두는 클래스
    class SafeFormatter(dict):
        def __missing__(self, key):
            return f'{{{key}}}'

    safe_kwargs = SafeFormatter(**kwargs)
    
    try:
        if 'title' in formatted_data and isinstance(formatted_data.get('title'), str):
            formatted_data['title'] = formatted_data['title'].format_map(safe_kwargs)
        if 'description' in formatted_data and isinstance(formatted_data.get('description'), str):
            formatted_data['description'] = formatted_data['description'].format_map(safe_kwargs)
        if 'footer' in formatted_data and isinstance(formatted_data.get('footer'), dict):
            if 'text' in formatted_data['footer'] and isinstance(formatted_data['footer'].get('text'), str):
                formatted_data['footer']['text'] = formatted_data['footer']['text'].format_map(safe_kwargs)
        if 'fields' in formatted_data and isinstance(formatted_data.get('fields'), list):
            for field in formatted_data['fields']:
                if isinstance(field, dict):
                    if 'name' in field and isinstance(field.get('name'), str):
                        field['name'] = field['name'].format_map(safe_kwargs)
                    if 'value' in field and isinstance(field.get('value'), str):
                        field['value'] = field['value'].format_map(safe_kwargs)
                        
        return discord.Embed.from_dict(formatted_data)
    except Exception as e:
        logger.error(f"임베드 최종 생성 중 오류 발생: {e}", exc_info=True)
        # 포맷팅에 실패하더라도, 원본 데이터로 임베드를 생성하여 반환 시도
        return discord.Embed.from_dict(embed_data)
