# src/core/clients/api_client.py

import httpx
import asyncio
from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel
import logging

# ConnectionMonitor import는 순환 import를 피하기 위해 함수 내에서 처리

# 로깅 설정
logger = logging.getLogger(__name__)

class DatabaseInfo(BaseModel):
    """데이터베이스 정보 모델"""
    connection_name: str
    database_name: str
    description: str

class DBProfileInfo(BaseModel):
    """DB 프로필 정보 모델"""
    id: str
    type: str
    host: Optional[str] = None
    port: Optional[int] = None
    name: Optional[str] = None
    username: Optional[str] = None
    view_name: Optional[str] = None
    created_at: str
    updated_at: str

class DBProfileResponse(BaseModel):
    """DB 프로필 조회 응답 모델"""
    code: str
    message: str
    data: List[DBProfileInfo]

class AnnotationColumn(BaseModel):
    """어노테이션 컬럼 정보 모델"""
    column_name: str
    description: str
    data_type: str

class AnnotationTable(BaseModel):
    """어노테이션 테이블 정보 모델"""
    table_name: str
    description: str
    columns: List[AnnotationColumn]

class AnnotationRelationship(BaseModel):
    """어노테이션 관계 정보 모델"""
    from_table: str
    from_columns: List[str]
    to_table: str
    to_columns: List[str]
    description: Optional[str] = None

class AnnotationDatabase(BaseModel):
    """어노테이션 데이터베이스 정보 모델"""
    db_name: str
    description: str
    tables: List[AnnotationTable]
    relationships: List[AnnotationRelationship]

class AnnotationData(BaseModel):
    """어노테이션 데이터 모델"""
    dbms_type: str
    databases: List[AnnotationDatabase]
    annotation_id: str
    db_profile_id: str
    created_at: str
    updated_at: str

class AnnotationResponse(BaseModel):
    """어노테이션 조회 응답 모델"""
    code: str
    message: str
    data: AnnotationData

class QueryExecutionRequest(BaseModel):
    """쿼리 실행 요청 모델"""
    user_db_id: str
    database: str
    query_text: str

class QueryResultData(BaseModel):
    """쿼리 실행 결과 데이터 모델"""
    columns: List[str]
    data: List[Dict[str, Any]]

class QueryExecutionResponse(BaseModel):
    """쿼리 실행 응답 모델"""
    code: str
    message: str
    data: Union[QueryResultData, str, bool]  # 결과 데이터, 에러 메시지

class APIClient:
    """백엔드 API와 통신하는 클라이언트 클래스"""
    
    def __init__(self, base_url: str = "http://localhost:39722"):
        self.base_url = base_url
        self.timeout = httpx.Timeout(30.0)
        self.headers = {
            "Content-Type": "application/json"
        }
        self._client: Optional[httpx.AsyncClient] = None
        self._connection_monitor = None  # 지연 초기화
    
    async def _get_client(self) -> httpx.AsyncClient:
        """재사용 가능한 HTTP 클라이언트를 반환합니다."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client
    
    def _get_connection_monitor(self):
        """ConnectionMonitor 인스턴스를 지연 로딩으로 가져옵니다."""
        if self._connection_monitor is None:
            from core.monitoring.connection_monitor import get_connection_monitor
            self._connection_monitor = get_connection_monitor()
        return self._connection_monitor
    
    async def close(self):
        """HTTP 클라이언트 연결을 닫습니다."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    async def get_db_profiles(self) -> List[DBProfileInfo]:
        """모든 DBMS 프로필 정보를 가져옵니다."""
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/api/user/db/find/all",
                headers=self.headers
            )
            response.raise_for_status()
            
            data = response.json()
            
            # 응답 구조 검증
            if data.get("code") != "2102":
                logger.warning(f"Unexpected response code: {data.get('code')}")
            
            profiles = [DBProfileInfo(**profile) for profile in data.get("data", [])]
            logger.info(f"Successfully fetched {len(profiles)} DB profiles")
            
            # 연결 복구 확인
            monitor = self._get_connection_monitor()
            await monitor.check_api_call_recovery("DB 프로필 조회")
            
            return profiles
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            monitor = self._get_connection_monitor()
            monitor.mark_api_call_failure("DB 프로필 조회")
            raise
        except httpx.RequestError as e:
            logger.error(f"Request error occurred: {e}")
            monitor = self._get_connection_monitor()
            monitor.mark_api_call_failure("DB 프로필 조회")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            monitor = self._get_connection_monitor()
            monitor.mark_api_call_failure("DB 프로필 조회")
            raise

    async def get_db_annotations(self, db_profile_id: str) -> AnnotationResponse:
        """특정 DBMS의 어노테이션을 조회합니다."""
        try:
            client = await self._get_client()
            response = await client.get(
                f"{self.base_url}/api/annotations/find/hierarchical/{db_profile_id}",
                headers=self.headers
            )
            response.raise_for_status()
            
            data = response.json()
            
            # 응답을 AnnotationResponse 모델로 파싱
            annotation_response = AnnotationResponse(**data)
            logger.info(f"Successfully fetched annotations for DB profile: {db_profile_id}")
            return annotation_response
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                # 404는 어노테이션이 없는 정상적인 상황
                logger.info(f"No annotations found for DB profile {db_profile_id}: {e.response.text}")
                # 빈 어노테이션 응답 생성
                empty_annotation = AnnotationResponse(
                    code="4401",
                    message="어노테이션이 없습니다",
                    data=AnnotationData(
                        dbms_type="unknown",
                        databases=[],
                        annotation_id="",
                        db_profile_id=db_profile_id,
                        created_at="",
                        updated_at=""
                    )
                )
                return empty_annotation
            else:
                logger.error(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
                raise
        except httpx.RequestError as e:
            logger.error(f"Request error occurred: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    async def get_available_databases(self) -> List[DatabaseInfo]:
        """
        [DEPRECATED] 사용 가능한 데이터베이스 목록을 가져옵니다.
        대신 get_db_profiles()를 사용하세요.
        """
        logger.warning("get_available_databases()는 deprecated입니다. get_db_profiles()를 사용하세요.")
        
        # DBMS 프로필 기반으로 DatabaseInfo 형태로 변환하여 호환성 유지
        try:
            profiles = await self.get_db_profiles()
            databases = []
            
            for profile in profiles:
                db_info = DatabaseInfo(
                    connection_name=f"{profile.type}_{profile.host}_{profile.port}",
                    database_name=profile.view_name or f"{profile.type}_db",
                    description=f"{profile.type} 데이터베이스 ({profile.host}:{profile.port})"
                )
                databases.append(db_info)
            
            logger.info(f"Successfully converted {len(databases)} DB profiles to DatabaseInfo")
            return databases
            
        except Exception as e:
            logger.error(f"Failed to convert DB profiles: {e}")
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
            
            response_data = response.json()
            
            # data 필드 타입에 따라 처리
            raw_data = response_data.get("data")
            parsed_data = raw_data
            
            # data가 객체 형태(쿼리 결과)인지 확인
            if isinstance(raw_data, dict) and "columns" in raw_data and "data" in raw_data:
                try:
                    parsed_data = QueryResultData(**raw_data)
                except Exception as e:
                    logger.warning(f"Failed to parse query result data: {e}, using raw data")
                    parsed_data = raw_data
            
            result = QueryExecutionResponse(
                code=response_data.get("code"),
                message=response_data.get("message"),
                data=parsed_data
            )
            
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
            is_healthy = response.status_code == 200
            
            monitor = self._get_connection_monitor()
            if is_healthy:
                # 헬스체크 성공 시 연결 복구 확인
                await monitor.check_api_call_recovery("헬스체크")
            else:
                # 헬스체크 실패 시 상태 업데이트
                monitor.mark_api_call_failure("헬스체크")
            
            return is_healthy
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            monitor = self._get_connection_monitor()
            monitor.mark_api_call_failure("헬스체크")
            return False

    async def get_openai_api_key(self) -> str:
        """백엔드에서 OpenAI API 키를 가져옵니다."""
        try:
            client = await self._get_client()
            
            # 1단계: 암호화된 API 키 조회
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
            
            # 2단계: 복호화된 실제 API 키 조회
            decrypt_response = await client.get(
                f"{self.base_url}/api/keys/find/decrypted/OpenAI",
                headers=self.headers,
                timeout=httpx.Timeout(10.0)
            )
            decrypt_response.raise_for_status()
            
            decrypt_data = decrypt_response.json()
            
            # 복호화된 키 데이터에서 실제 API 키 추출
            data_field = decrypt_data.get("data", {})
            
            if isinstance(data_field, dict) and "api_key" in data_field:
                actual_api_key = data_field["api_key"]
            else:
                raise ValueError("백엔드 응답에서 API 키를 찾을 수 없습니다.")
            
            if not actual_api_key:
                raise ValueError("백엔드에서 복호화된 OpenAI API 키를 가져올 수 없습니다.")
            
            logger.info("Successfully fetched decrypted OpenAI API key from backend")
            return actual_api_key
            
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
