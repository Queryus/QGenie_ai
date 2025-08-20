# src/agents/sql_agent/exceptions.py

class SqlAgentException(Exception):
    """SQL Agent 관련 기본 예외 클래스"""
    pass

class ValidationException(SqlAgentException):
    """SQL 검증 실패 예외"""
    def __init__(self, message: str, error_count: int = 0):
        super().__init__(message)
        self.error_count = error_count

class ExecutionException(SqlAgentException):
    """SQL 실행 실패 예외"""
    def __init__(self, message: str, error_count: int = 0):
        super().__init__(message)
        self.error_count = error_count

class DatabaseConnectionException(SqlAgentException):
    """데이터베이스 연결 실패 예외"""
    pass

class LLMProviderException(SqlAgentException):
    """LLM 제공자 관련 예외"""
    pass

class MaxRetryExceededException(SqlAgentException):
    """최대 재시도 횟수 초과 예외"""
    def __init__(self, message: str, max_retries: int):
        super().__init__(f"{message} (최대 재시도 {max_retries}회 초과)")
        self.max_retries = max_retries
