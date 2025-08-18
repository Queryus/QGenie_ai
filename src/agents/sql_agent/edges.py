# src/agents/sql_agent/edges.py

from .state import SqlAgentState

# 상수 정의
MAX_ERROR_COUNT = 3

class SqlAgentEdges:
    """SQL Agent의 모든 엣지 로직을 담당하는 클래스"""
    
    @staticmethod
    def route_after_intent_classification(state: SqlAgentState) -> str:
        """의도 분류 결과에 따라 라우팅을 결정합니다."""
        if state['intent'] == "SQL":
            print("--- 의도: SQL 관련 질문 ---")
            return "db_classifier"
        print("--- 의도: SQL과 관련 없는 질문 ---")
        return "unsupported_question"
    
    @staticmethod
    def should_execute_sql(state: SqlAgentState) -> str:
        """SQL 검증 결과에 따라 다음 단계를 결정합니다."""
        validation_error_count = state.get("validation_error_count", 0)
        
        if validation_error_count >= MAX_ERROR_COUNT:
            print(f"--- 검증 실패 {MAX_ERROR_COUNT}회 초과: 답변 생성으로 이동 ---")
            return "synthesize_failure"
        
        if state.get("validation_error"):
            print(f"--- 검증 실패 {validation_error_count}회: SQL 재생성 ---")
            return "regenerate"
        
        print("--- 검증 성공: SQL 실행 ---")
        return "execute"
    
    @staticmethod
    def should_retry_or_respond(state: SqlAgentState) -> str:
        """SQL 실행 결과에 따라 다음 단계를 결정합니다."""
        execution_error_count = state.get("execution_error_count", 0)
        execution_result = state.get("execution_result", "")
        
        if execution_error_count >= MAX_ERROR_COUNT:
            print(f"--- 실행 실패 {MAX_ERROR_COUNT}회 초과: 답변 생성으로 이동 ---")
            return "synthesize_failure"
        
        if "오류" in execution_result:
            print(f"--- 실행 실패 {execution_error_count}회: SQL 재생성 ---")
            return "regenerate"
        
        print("--- 실행 성공: 최종 답변 생성 ---")
        return "synthesize_success"
