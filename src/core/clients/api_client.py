# src/core/clients/api_client.py

import httpx
import asyncio
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
import logging

# 로깅 설정
logger = logging.getLogger(__name__)

class DatabaseInfo(BaseModel):
    """데이터베이스 정보 모델"""
    connection_name: str
    database_name: str
    description: str

class QueryExecutionRequest(BaseModel):
    """쿼리 실행 요청 모델"""
    user_db_id: str
    database: str
    query_text: str

class QueryExecutionResponse(BaseModel):
    """쿼리 실행 응답 모델"""
    code: str
    message: str
    data: bool

class APIClient:
    """백엔드 API와 통신하는 클라이언트 클래스"""
    
    def __init__(self, base_url: str = "http://localhost:39722"):
        self.base_url = base_url
        self.timeout = httpx.Timeout(30.0)
        self.headers = {
            "Content-Type": "application/json"
        }
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """재사용 가능한 HTTP 클라이언트를 반환합니다."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    async def close(self):
        """HTTP 클라이언트 연결을 닫습니다."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    # TODO: DB 어노테이션 조회
    async def get_available_databases(self) -> List[DatabaseInfo]:
        """사용 가능한 데이터베이스 목록을 가져옵니다."""
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/api/v1/databases",
                headers=self.headers
            )
            response.raise_for_status()
            
            data = response.json()
            databases = [DatabaseInfo(**db) for db in data.get("databases", [])]
            logger.info(f"Successfully fetched {len(databases)} databases")
            return databases
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error occurred: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
    # TODO: DB 스키마 조회 API 필요
    async def get_database_schema(self, database_name: str) -> str:
        """특정 데이터베이스의 스키마 정보를 가져옵니다."""
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/api/v1/databases/{database_name}/schema",
                headers=self.headers
            )
            response.raise_for_status()
            
            data = response.json()
            schema = data.get("schema", "")
            logger.info(f"Successfully fetched schema for database: {database_name}")
            return schema
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error occurred: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise
    
    async def execute_query(
        self, 
        sql_query: str, 
        database_name: str, 
        user_db_id: str = None
    ) -> QueryExecutionResponse:
        """SQL 쿼리를 Backend 서버에 전송하여 실행하고 결과를 받아옵니다."""
        try:
            logger.info(f"Sending SQL query to backend: {sql_query}")
            
            request_data = QueryExecutionRequest(
                user_db_id=user_db_id,
                database=database_name,
                query_text=sql_query
            )
            
            client = await self._get_client()
            response = await client.post(
                f"{self.base_url}/api/query/execute/test",
                json=request_data.model_dump(),
                headers=self.headers,
                timeout=httpx.Timeout(35.0)  # 고정 타임아웃
            )
            
            response.raise_for_status()  # HTTP 에러 시 예외 발생
            
            data = response.json()
            result = QueryExecutionResponse(**data)
            
            if result.code == "2400":
                logger.info(f"Query executed successfully: {result.message}")
            else:
                logger.warning(f"Query execution returned non-success code: {result.code} - {result.message}")
            
            return result
                
        except httpx.TimeoutException:
            logger.error("Backend API 요청 시간 초과")
            raise
        except httpx.ConnectError:
            logger.error("Backend 서버 연결 실패")
            raise
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during query execution: {e}")
            raise
    
    async def health_check(self) -> bool:
        """API 서버 상태를 확인합니다."""
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/health",
                timeout=httpx.Timeout(5.0)
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    # TODO: API 키 호출 API 필요
    async def get_openai_api_key(self) -> str:
        """백엔드에서 OpenAI API 키를 가져옵니다."""
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/api/keys/find",
                headers=self.headers,
                timeout=httpx.Timeout(10.0)
            )
            response.raise_for_status()
            
            data = response.json()
            
            # data 배열에서 OpenAI 서비스 찾기
            api_keys = data.get("data", [])
            openai_key = None
            
            # 가장 첫번째 OpenAI 키 사용
            for key_info in api_keys:
                if key_info.get("service_name") == "OpenAI":
                    openai_key = key_info.get("id")
                    break
            
            if not openai_key:
                raise ValueError("백엔드에서 OpenAI API 키를 찾을 수 없습니다.")
            
            logger.info("Successfully fetched OpenAI API key from backend")
            return openai_key
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred while fetching API key: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error occurred while fetching API key: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error while fetching API key: {e}")
            raise
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        await self.close()

# 싱글톤 인스턴스
_api_client = APIClient()

async def get_api_client() -> APIClient:
    """API Client 인스턴스를 반환합니다."""
    return _api_client
