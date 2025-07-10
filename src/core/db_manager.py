# src/core/db_manager.py

from langchain_community.utilities import SQLDatabase
import os
from dotenv import load_dotenv

load_dotenv()

def get_db_connection() -> SQLDatabase:
    """SQLDatabase 객체를 생성하고 반환합니다.
    
    Args:
    
    Returns:
        SQLDatabase: DB와 연결된 SQLDatabase 객체
    """
    db_uri = os.getenv("MYSQL_URI")
    if not db_uri:
        raise ValueError("DATABASE_URI 환경 변수가 .env 파일에 설정되지 않았습니다.")
    return SQLDatabase.from_uri(db_uri)

def load_predefined_schema(db: SQLDatabase) -> str:
    """SQLDatabase 객체를 사용하여 모든 테이블의 스키마 정보를 반환합니다.

    Args:
        db: DB와 연결된 SQLDatabase 객체
    
    Returns:
        str: DB에 포함된 모든 Table의 schema

    """
    try:
        all_table_names = db.get_usable_table_names()
        return db.get_table_info(table_names=all_table_names)
    except Exception as e:
        return f"스키마 조회 중 오류 발생: {e}"

# 앱 전체에서 동일한 객체를 참조(싱글턴 패턴)
db_instance = get_db_connection()
schema_instance = load_predefined_schema(db_instance)
