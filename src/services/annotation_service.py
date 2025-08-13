# src/services/annotation_service.py

import asyncio
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from api.v1.schemas.annotator_schemas import (
    AnnotationRequest, AnnotationResponse,
    Database, Table, Column, Relationship,
    AnnotatedDatabase, AnnotatedTable, AnnotatedColumn, AnnotatedRelationship
)

class AnnotationService():
    """
    어노테이션 생성과 관련된 모든 비즈니스 로직을 담당하는 서비스 클래스.
    LLM 호출을 비동기적으로 처리하여 성능을 최적화합니다.
    """
    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    async def _generate_description(self, template: str, **kwargs) -> str:
        """LLM을 비동기적으로 호출하여 설명을 생성하는 헬퍼 함수"""
        prompt = ChatPromptTemplate.from_template(template)
        chain = prompt | self.llm | StrOutputParser()
        return await chain.ainvoke(kwargs)

    async def _annotate_column(self, table_name: str, sample_rows: str, column: Column) -> AnnotatedColumn:
        """단일 컬럼을 비동기적으로 어노테이트합니다."""
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
        return AnnotatedColumn(**column.model_dump(), description=column_desc.strip())

    async def _annotate_table(self, db_name: str, table: Table) -> AnnotatedTable:
        """단일 테이블과 그 컬럼들을 비동기적으로 어노테이트합니다."""
        sample_rows_str = str(table.sample_rows[:3])
        
        # 테이블 설명 생성과 모든 컬럼 설명을 동시에 병렬로 처리
        table_desc_task = self._generate_description(
            "데이터베이스 '{db_name}'에 속한 테이블 '{table_name}'의 역할을 한국어로 간결하게 설명해줘.",
            db_name=db_name, table_name=table.table_name
        )
        column_tasks = [self._annotate_column(table.table_name, sample_rows_str, col) for col in table.columns]
        
        results = await asyncio.gather(table_desc_task, *column_tasks)
        
        table_desc = results[0].strip()
        annotated_columns = results[1:]
        
        return AnnotatedTable(**table.model_dump(exclude={'columns'}), description=table_desc, columns=annotated_columns)

    async def _annotate_relationship(self, relationship: Relationship) -> AnnotatedRelationship:
        """단일 관계를 비동기적으로 어노테이트합니다."""
        rel_desc = await self._generate_description(
            """
            테이블 '{from_table}'이(가) 테이블 '{to_table}'을(를) 참조하고 있습니다.
            이 관계를 한국어 문장으로 설명해줘.
            """,
            from_table=relationship.from_table, to_table=relationship.to_table
        )
        return AnnotatedRelationship(**relationship.model_dump(), description=rel_desc.strip())

    async def generate_for_schema(self, request: AnnotationRequest) -> AnnotationResponse:
        """
        입력된 스키마 전체에 대한 어노테이션을 비동기적으로 생성합니다.
        """
        annotated_databases = []
        for db in request.databases:
            # DB 설명, 모든 테이블, 모든 관계 설명을 동시에 병렬로 처리
            db_desc_task = self._generate_description(
                "데이터베이스 '{db_name}'의 역할을 한국어로 간결하게 설명해줘.",
                db_name=db.database_name
            )
            
            table_tasks = [self._annotate_table(db.database_name, table) for table in db.tables]
            relationship_tasks = [self._annotate_relationship(rel) for rel in db.relationships]
            
            db_desc_result, *other_results = await asyncio.gather(db_desc_task, *table_tasks, *relationship_tasks)
            
            num_tables = len(table_tasks)
            annotated_tables = other_results[:num_tables]
            annotated_relationships = other_results[num_tables:]

            annotated_databases.append(
                AnnotatedDatabase(
                    database_name=db.database_name,
                    description=db_desc_result.strip(),
                    tables=annotated_tables,
                    relationships=annotated_relationships
                )
            )
        
        return AnnotationResponse(dbms_type=request.dbms_type, databases=annotated_databases)
