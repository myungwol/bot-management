# sync_db.py
# 이 스크립트는 ui_defaults.py의 최신 설정을 Supabase DB로 강제 동기화합니다.
# 봇 실행과 별개로, 딱 한 번만 실행하면 됩니다.

import asyncio
import logging
import os
from dotenv import load_dotenv

# .env 파일이 있다면 환경 변수를 로드합니다.
load_dotenv()

# utils.database 모듈에서 동기화 함수만 가져옵니다.
try:
    from utils.database import sync_defaults_to_db
except ImportError as e:
    print(f"오류: 필요한 파일을 찾을 수 없습니다. 이 스크립트는 봇 프로젝트의 최상위 폴더에서 실행해야 합니다.")
    print(f"Import Error: {e}")
    exit(1)

# 기본적인 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def main():
    """
    메인 동기화 함수를 실행합니다.
    """
    logging.info("최신 설정을 데이터베이스와 동기화하는 작업을 시작합니다...")
    
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_KEY"):
        logging.error("❌ SUPABASE_URL 또는 SUPABASE_KEY 환경 변수가 설정되지 않았습니다.")
        logging.error("   Railway 프로젝트의 Variables 탭에서 환경 변수가 올바르게 설정되었는지 확인해주세요.")
        return

    await sync_defaults_to_db()
    logging.info("✅ 동기화 작업이 성공적으로 완료되었습니다.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.critical(f"🚨 스크립트 실행 중 치명적인 오류 발생: {e}", exc_info=True)
