# src/agents/sql_agent/state.py

from typing import List, TypedDict, Optional, Dict, Any
from langchain_core.messages import BaseMessage

class SqlAgentState(TypedDict):
    """SQL Agent의 상태를 정의하는 TypedDict"""
    
    # 입력 정보
    question: str
    chat_history: List[BaseMessage]
    
    # 데이터베이스 관련
    selected_db: Optional[str]
    db_schema: str
    selected_db_profile: Optional[Dict[str, Any]]  # DB 프로필 정보
    selected_db_annotations: Optional[Dict[str, Any]]  # DB 어노테이션 정보
    
    # 의도 분류 결과
    intent: str
    
    # SQL 생성 및 검증
    sql_query: str
    validation_error: Optional[str]
    validation_error_count: int
    
    # SQL 실행 결과
    execution_result: Optional[str]
    execution_error_count: int
    
    # 최종 응답
    final_response: str
