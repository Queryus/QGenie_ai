# src/services/database/database_service.py

import asyncio
from typing import List, Optional, Dict
from core.clients.api_client import APIClient, DatabaseInfo, get_api_client
import logging

logger = logging.getLogger(__name__)

class DatabaseService:
    """데이터베이스 관련 비즈니스 로직을 담당하는 서비스 클래스"""
    
    def __init__(self, api_client: APIClient = None):
        self.api_client = api_client
        self._cached_databases: Optional[List[DatabaseInfo]] = None
        self._cached_schemas: Dict[str, str] = {}
    
    async def _get_api_client(self) -> APIClient:
        """API 클라이언트를 가져옵니다."""
        if self.api_client is None:
            self.api_client = await get_api_client()
        return self.api_client
    
    async def get_available_databases(self) -> List[DatabaseInfo]:
        """사용 가능한 데이터베이스 목록을 가져옵니다."""
        try:
            if self._cached_databases is None:
                api_client = await self._get_api_client()
                self._cached_databases = await api_client.get_available_databases()
                logger.info(f"Cached {len(self._cached_databases)} databases")
            
            return self._cached_databases
            
        except Exception as e:
            logger.error(f"Failed to fetch databases: {e}")
            raise RuntimeError(f"데이터베이스 목록을 가져올 수 없습니다. 백엔드 서버를 확인해주세요: {e}")
    
    async def get_schema_for_db(self, db_name: str) -> str:
        """특정 데이터베이스의 스키마를 가져옵니다."""
        try:
            if db_name not in self._cached_schemas:
                api_client = await self._get_api_client()
                schema = await api_client.get_database_schema(db_name)
                self._cached_schemas[db_name] = schema
                logger.info(f"Cached schema for database: {db_name}")
            
            return self._cached_schemas[db_name]
            
        except Exception as e:
            logger.error(f"Failed to fetch schema for {db_name}: {e}")
            raise RuntimeError(f"데이터베이스 '{db_name}' 스키마를 가져올 수 없습니다. 백엔드 서버를 확인해주세요: {e}")
    
    async def execute_query(self, sql_query: str, database_name: str = None, user_db_id: str = None) -> str:
        """SQL 쿼리를 실행하고 결과를 반환합니다."""
        try:
            if not database_name:
                logger.warning("Database name not provided, using default")
                database_name = "default"
            
            logger.info(f"Executing SQL query on database '{database_name}': {sql_query}")
            
            api_client = await self._get_api_client()
            response = await api_client.execute_query(
                sql_query=sql_query,
                database_name=database_name,
                user_db_id=user_db_id
            )
            
            # 백엔드 응답 코드 확인
            if response.code == "2400":
                logger.info(f"Query executed successfully: {response.message}")
                
                # 응답 데이터 형태에 따라 다른 메시지 반환
                if hasattr(response.data, 'columns') and hasattr(response.data, 'data'):
                    # 쿼리 결과 데이터가 있는 경우
                    row_count = len(response.data.data)
                    col_count = len(response.data.columns)
                    return f"쿼리가 성공적으로 실행되었습니다. {row_count}개 행, {col_count}개 컬럼의 결과를 반환했습니다."
                else:
                    # 일반적인 성공 메시지
                    return "쿼리가 성공적으로 실행되었습니다."
            else:
                # data에 에러 메시지가 있는지 확인
                error_detail = ""
                if isinstance(response.data, str):
                    error_detail = f" 상세: {response.data}"
                
                error_msg = f"쿼리 실행 실패: {response.message} (코드: {response.code}){error_detail}"
                logger.error(error_msg)
                return error_msg
                
        except Exception as e:
            logger.error(f"Error during query execution: {e}")
            return f"쿼리 실행 중 오류 발생: {e}"
    
    async def _get_fallback_databases(self) -> List[DatabaseInfo]:
        """API 실패 시 사용할 폴백 데이터베이스 목록"""
        return [
            DatabaseInfo(
                connection_name="local_mysql",
                database_name="sakila",
                description="DVD 대여점 비즈니스 모델을 다루는 샘플 데이터베이스"
            ),
            DatabaseInfo(
                connection_name="local_mysql", 
                database_name="ecom_prod",
                description="온라인 쇼핑몰의 운영 데이터베이스"
            ),
            DatabaseInfo(
                connection_name="local_mysql",
                database_name="hr_analytics", 
                description="회사의 인사 관리 데이터베이스"
            ),
            DatabaseInfo(
                connection_name="local_mysql",
                database_name="web_logs",
                description="웹사이트 트래픽 분석을 위한 로그 데이터베이스"
            )
        ]
    
    async def get_fallback_schema(self, db_name: str) -> str:
        """API 실패 시 사용할 폴백 스키마"""
        fallback_schemas = {
            "sakila": "CREATE TABLE actor (actor_id INT, first_name VARCHAR(45), last_name VARCHAR(45))",
            "ecom_prod": "CREATE TABLE products (product_id INT, name VARCHAR(100), price DECIMAL(10,2))",
            "hr_analytics": "CREATE TABLE employees (employee_id INT, name VARCHAR(100), department VARCHAR(50))",
            "web_logs": "CREATE TABLE access_logs (log_id INT, timestamp DATETIME, ip_address VARCHAR(45))"
        }
        return fallback_schemas.get(db_name, "Schema information not available")
    
    async def refresh_cache(self):
        """캐시를 새로고침합니다."""
        self._cached_databases = None
        self._cached_schemas.clear()
        logger.info("Database cache refreshed")
    
    async def clear_cache(self):
        """캐시를 클리어합니다."""
        self._cached_databases = None
        self._cached_schemas.clear()
        logger.info("Database cache cleared")
    
    async def health_check(self) -> bool:
        """데이터베이스 서비스 상태를 확인합니다."""
        try:
            api_client = await self._get_api_client()
            return await api_client.health_check()
        except Exception as e:
            logger.error(f"Database service health check failed: {e}")
            return False

# 싱글톤 인스턴스
_database_service = DatabaseService()

async def get_database_service() -> DatabaseService:
    """Database Service 인스턴스를 반환합니다."""
    return _database_service
