# src/services/annotation/annotation_service.py

import asyncio
from typing import List, Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

from schemas.api.annotator_schemas import (
    AnnotationRequest, AnnotationResponse,
    Database, Table, Column, Relationship,
    AnnotatedDatabase, AnnotatedTable, AnnotatedColumn, AnnotatedRelationship
)
from core.providers.llm_provider import LLMProvider, get_llm_provider
import logging

logger = logging.getLogger(__name__)

class AnnotationService:
    """어노테이션 생성과 관련된 모든 비즈니스 로직을 담당하는 서비스 클래스"""
    
    def __init__(self, llm_provider: LLMProvider = None):
        self.llm_provider = llm_provider
    
    async def _initialize_dependencies(self):
        """필요한 의존성들을 초기화합니다."""
        if self.llm_provider is None:
            self.llm_provider = await get_llm_provider()
    
    async def _generate_description(self, template: str, **kwargs) -> str:
        """LLM을 비동기적으로 호출하여 설명을 생성하는 헬퍼 함수"""
        try:
            await self._initialize_dependencies()
            
            prompt = ChatPromptTemplate.from_template(template)
            llm = await self.llm_provider.get_llm()
            chain = prompt | llm | StrOutputParser()
            
            result = await chain.ainvoke(kwargs)
            return result.strip()
            
        except Exception as e:
            logger.error(f"Failed to generate description: {e}")
            return f"설명 생성 실패: {e}"
    
    async def _annotate_column(
        self, 
        table_name: str, 
        sample_rows: str, 
        column: Column
    ) -> AnnotatedColumn:
        """단일 컬럼을 비동기적으로 어노테이트합니다."""
        try:
            column_desc = await self._generate_description(
                """
                테이블 '{table_name}'의 컬럼 '{column_name}'(타입: {data_type})의 역할을 한국어로 간결하게 설명해줘.
                샘플 데이터: {sample_rows}
                """,
                table_name=table_name,
                column_name=column.column_name,
                data_type=column.data_type,
                sample_rows=sample_rows
            )
            
            return AnnotatedColumn(
                **column.model_dump(), 
                description=column_desc
            )
            
        except Exception as e:
            logger.error(f"Failed to annotate column {column.column_name}: {e}")
            return AnnotatedColumn(
                **column.model_dump(),
                description=f"설명 생성 실패: {e}"
            )
    
    async def _annotate_table(self, db_name: str, table: Table) -> AnnotatedTable:
        """단일 테이블과 그 컬럼들을 비동기적으로 어노테이트합니다."""
        try:
            sample_rows_str = str(table.sample_rows[:3])
            
            # 테이블 설명 생성과 모든 컬럼 설명을 동시에 병렬로 처리
            table_desc_task = self._generate_description(
                "데이터베이스 '{db_name}'에 속한 테이블 '{table_name}'의 역할을 한국어로 간결하게 설명해줘.",
                db_name=db_name, 
                table_name=table.table_name
            )
            
            column_tasks = [
                self._annotate_column(table.table_name, sample_rows_str, col) 
                for col in table.columns
            ]
            
            # 모든 작업을 병렬 실행
            results = await asyncio.gather(
                table_desc_task, 
                *column_tasks,
                return_exceptions=True
            )
            
            # 결과 처리
            table_desc = results[0] if not isinstance(results[0], Exception) else "테이블 설명 생성 실패"
            annotated_columns = [
                result for result in results[1:] 
                if not isinstance(result, Exception)
            ]
            
            return AnnotatedTable(
                **table.model_dump(exclude={'columns'}), 
                description=table_desc, 
                columns=annotated_columns
            )
            
        except Exception as e:
            logger.error(f"Failed to annotate table {table.table_name}: {e}")
            # 실패 시 기본 어노테이션 반환
            annotated_columns = [
                AnnotatedColumn(**col.model_dump(), description="설명 생성 실패")
                for col in table.columns
            ]
            return AnnotatedTable(
                **table.model_dump(exclude={'columns'}),
                description=f"테이블 설명 생성 실패: {e}",
                columns=annotated_columns
            )
    
    async def _annotate_relationship(self, relationship: Relationship) -> AnnotatedRelationship:
        """단일 관계를 비동기적으로 어노테이트합니다."""
        try:
            rel_desc = await self._generate_description(
                """
                테이블 '{from_table}'이(가) 테이블 '{to_table}'을(를) 참조하고 있습니다.
                이 관계를 한국어 문장으로 설명해줘.
                """,
                from_table=relationship.from_table, 
                to_table=relationship.to_table
            )
            
            return AnnotatedRelationship(
                **relationship.model_dump(), 
                description=rel_desc
            )
            
        except Exception as e:
            logger.error(f"Failed to annotate relationship: {e}")
            return AnnotatedRelationship(
                **relationship.model_dump(),
                description=f"관계 설명 생성 실패: {e}"
            )
    
    async def generate_for_schema(self, request: AnnotationRequest) -> AnnotationResponse:
        """입력된 스키마 전체에 대한 어노테이션을 비동기적으로 생성합니다."""
        try:
            logger.info(f"Starting annotation generation for {len(request.databases)} databases")
            
            annotated_databases = []
            
            for db in request.databases:
                try:
                    # DB 설명, 모든 테이블, 모든 관계 설명을 동시에 병렬로 처리
                    db_desc_task = self._generate_description(
                        "데이터베이스 '{db_name}'의 역할을 한국어로 간결하게 설명해줘.",
                        db_name=db.database_name
                    )
                    
                    table_tasks = [
                        self._annotate_table(db.database_name, table) 
                        for table in db.tables
                    ]
                    
                    relationship_tasks = [
                        self._annotate_relationship(rel) 
                        for rel in db.relationships
                    ]
                    
                    # 모든 작업을 병렬 실행
                    all_results = await asyncio.gather(
                        db_desc_task, 
                        *table_tasks, 
                        *relationship_tasks,
                        return_exceptions=True
                    )
                    
                    # 결과 분리
                    db_desc = all_results[0] if not isinstance(all_results[0], Exception) else "DB 설명 생성 실패"
                    
                    num_tables = len(table_tasks)
                    annotated_tables = [
                        result for result in all_results[1:1+num_tables]
                        if not isinstance(result, Exception)
                    ]
                    
                    annotated_relationships = [
                        result for result in all_results[1+num_tables:]
                        if not isinstance(result, Exception)
                    ]
                    
                    annotated_databases.append(
                        AnnotatedDatabase(
                            database_name=db.database_name,
                            description=db_desc,
                            tables=annotated_tables,
                            relationships=annotated_relationships
                        )
                    )
                    
                    logger.info(f"Completed annotation for database: {db.database_name}")
                    
                except Exception as e:
                    logger.error(f"Failed to annotate database {db.database_name}: {e}")
                    # 실패한 데이터베이스도 기본값으로 포함
                    annotated_databases.append(
                        AnnotatedDatabase(
                            database_name=db.database_name,
                            description=f"데이터베이스 어노테이션 생성 실패: {e}",
                            tables=[],
                            relationships=[]
                        )
                    )
            
            logger.info("Annotation generation completed successfully")
            
            return AnnotationResponse(
                dbms_type=request.dbms_type, 
                databases=annotated_databases
            )
            
        except Exception as e:
            logger.error(f"Failed to generate annotations: {e}")
            # 전체 실패 시 기본 응답 반환
            return AnnotationResponse(
                dbms_type=request.dbms_type,
                databases=[]
            )
    
    async def health_check(self) -> Dict[str, Any]:
        """어노테이션 서비스의 상태를 확인합니다."""
        try:
            await self._initialize_dependencies()
            
            # LLM 연결 테스트
            llm_status = await self.llm_provider.test_connection()
            
            return {
                "status": "healthy" if llm_status else "unhealthy",
                "llm_provider": "connected" if llm_status else "disconnected"
            }
            
        except Exception as e:
            logger.error(f"Annotation service health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }

# 싱글톤 인스턴스
_annotation_service = AnnotationService()

async def get_annotation_service() -> AnnotationService:
    """Annotation Service 인스턴스를 반환합니다."""
    return _annotation_service
