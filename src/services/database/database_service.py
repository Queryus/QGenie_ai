# src/services/database/database_service.py

import asyncio
from typing import List, Optional, Dict, Any
from core.clients.api_client import APIClient, DatabaseInfo, DBProfileInfo, AnnotationResponse, get_api_client
import logging

logger = logging.getLogger(__name__)

class DatabaseService:
    """
    데이터베이스 관련 비즈니스 로직을 담당하는 서비스 클래스
    지연 초기화를 지원하여 BE 서버가 늦게 시작되어도 작동합니다.
    """
    
    def __init__(self, api_client: APIClient = None):
        self.api_client = api_client
        self._cached_db_profiles: Optional[List[DBProfileInfo]] = None
        self._cached_annotations: Dict[str, AnnotationResponse] = {}
        # 호환성을 위해 유지하지만 더 이상 사용하지 않음
        self._cached_databases: Optional[List[DatabaseInfo]] = None
        self._cached_schemas: Dict[str, str] = {}
        # 지연 초기화 관련 플래그
        self._connection_attempted: bool = False
        self._connection_failed: bool = False
    
    async def _get_api_client(self) -> APIClient:
        """API 클라이언트를 가져옵니다."""
        if self.api_client is None:
            self.api_client = await get_api_client()
        return self.api_client
    
    async def get_available_databases(self) -> List[DatabaseInfo]:
        """
        [DEPRECATED] 사용 가능한 데이터베이스 목록을 가져옵니다.
        대신 get_databases_with_annotations()를 사용하세요.
        
        APIClient의 동일한 메서드로 위임합니다.
        """
        logger.warning("get_available_databases()는 deprecated입니다. get_databases_with_annotations()를 사용하세요.")
        
        try:
            api_client = await self._get_api_client()
            return await api_client.get_available_databases()
            
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
                    # 쿼리 결과 데이터가 있는 경우 - 실제 데이터를 포함하여 반환
                    columns = response.data.columns
                    data_rows = response.data.data
                    
                    # 테이블 형태로 결과 포매팅
                    result_text = f"쿼리 실행 결과 ({len(data_rows)}개 행, {len(columns)}개 컬럼):\n\n"
                    
                    # 컬럼 헤더 추가
                    header = " | ".join(columns)
                    result_text += header + "\n"
                    result_text += "-" * len(header) + "\n"
                    
                    # 데이터 행 추가 (최대 100행까지만 표시)
                    max_rows = min(100, len(data_rows))
                    for i in range(max_rows):
                        row = data_rows[i]
                        row_text = " | ".join(str(cell) if cell is not None else "NULL" for cell in row)
                        result_text += row_text + "\n"
                    
                    # 행이 잘렸다면 표시
                    if len(data_rows) > max_rows:
                        result_text += f"\n... ({len(data_rows) - max_rows}개 행 더 있음)"
                    
                    return result_text
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
    

    
    async def get_db_profiles(self) -> List[DBProfileInfo]:
        """
        모든 DBMS 프로필 정보를 가져옵니다.
        지연 초기화를 통해 BE 서버 연결이 실패해도 재시도합니다.
        """
        if self._cached_db_profiles is None:
            # 이전에 연결을 시도했고 실패했다면 재시도
            if self._connection_failed:
                logger.info("🔄 DB 프로필 조회 재시도 중...")
                self._connection_failed = False
                self._connection_attempted = False
            
            try:
                self._connection_attempted = True
                api_client = await self._get_api_client()
                self._cached_db_profiles = await api_client.get_db_profiles()
                self._connection_failed = False
                logger.info(f"✅ DB 프로필 조회 성공: {len(self._cached_db_profiles)}개")
                
                # 연결 복구 감지 (이미 APIClient에서 처리되지만 추가 로그)
                if self._connection_failed:
                    logger.info("🎉 DatabaseService: 백엔드 연결이 복구되어 DB 프로필 조회가 성공했습니다!")
                
            except Exception as e:
                self._connection_failed = True
                logger.error(f"❌ DB 프로필 조회 실패: {e}")
                raise RuntimeError(f"DB 프로필 목록을 가져올 수 없습니다. 백엔드 서버가 실행 중인지 확인해주세요: {e}")
        
        return self._cached_db_profiles

    async def get_db_annotations(self, db_profile_id: str) -> AnnotationResponse:
        """특정 DBMS의 어노테이션을 조회합니다."""
        try:
            if db_profile_id not in self._cached_annotations:
                api_client = await self._get_api_client()
                annotations = await api_client.get_db_annotations(db_profile_id)
                self._cached_annotations[db_profile_id] = annotations
                
                if annotations.code == "4401":
                    logger.info(f"No annotations available for DB profile: {db_profile_id}")
                else:
                    logger.info(f"Cached annotations for DB profile: {db_profile_id}")
            
            return self._cached_annotations[db_profile_id]
            
        except Exception as e:
            logger.error(f"Failed to fetch annotations for {db_profile_id}: {e}")
            # 어노테이션이 없어도 기본 정보는 반환하도록 변경
            from core.clients.api_client import AnnotationResponse, AnnotationData
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

    async def get_databases_with_annotations(self) -> List[Dict[str, Any]]:
        """DB 프로필과 어노테이션을 함께 조회합니다."""
        try:
            profiles = await self.get_db_profiles()
            result = []
            
            for profile in profiles:
                annotations = await self.get_db_annotations(profile.id)
                db_info = {
                    "profile": profile.model_dump(),
                    "annotations": annotations,
                    "display_name": profile.view_name or f"{profile.type}_{profile.host}_{profile.port}",
                    "description": self._generate_db_description(profile, annotations)
                }
                result.append(db_info)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to get databases with annotations: {e}")
            raise RuntimeError(f"어노테이션이 포함된 데이터베이스 목록을 가져올 수 없습니다: {e}")

    def _generate_db_description(self, profile: DBProfileInfo, annotations: AnnotationResponse) -> str:
        """DB 프로필과 어노테이션을 기반으로 설명을 생성합니다."""
        try:
            # 기본 설명
            base_desc = f"{profile.type} 데이터베이스"
            
            if profile.view_name:
                base_desc += f" ({profile.view_name})"
            else:
                base_desc += f" ({profile.host}:{profile.port})"
            
            # 어노테이션 정보 확인
            if annotations and annotations.code != "4401" and annotations.data.databases:
                # 실제 어노테이션이 있는 경우
                db_count = len(annotations.data.databases)
                total_tables = sum(len(db.tables) for db in annotations.data.databases)
                base_desc += f" - {db_count}개 DB, {total_tables}개 테이블 어노테이션 포함"
            
            return base_desc
            
        except Exception as e:
            logger.warning(f"Failed to generate description: {e}")
            return f"{profile.type} 데이터베이스"

    async def refresh_cache(self):
        """캐시를 새로고침합니다."""
        self._cached_db_profiles = None
        self._cached_annotations.clear()
        # 호환성을 위해 유지
        self._cached_databases = None
        self._cached_schemas.clear()
        # 지연 초기화 플래그 리셋
        self._connection_attempted = False
        self._connection_failed = False
        logger.info("Database cache refreshed")
    
    async def clear_cache(self):
        """캐시를 클리어합니다."""
        self._cached_db_profiles = None
        self._cached_annotations.clear()
        # 호환성을 위해 유지
        self._cached_databases = None
        self._cached_schemas.clear()
        # 지연 초기화 플래그 리셋
        self._connection_attempted = False
        self._connection_failed = False
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
