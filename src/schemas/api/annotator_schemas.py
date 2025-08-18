# src/schemas/api/annotator_schemas.py

from pydantic import BaseModel, Field
from typing import List, Dict, Any

class Column(BaseModel):
    """데이터베이스 컬럼 모델"""
    column_name: str
    data_type: str

class Table(BaseModel):
    """데이터베이스 테이블 모델"""
    table_name: str
    columns: List[Column]
    sample_rows: List[Dict[str, Any]]

class Relationship(BaseModel):
    """테이블 관계 모델"""
    from_table: str
    from_columns: List[str]
    to_table: str
    to_columns: List[str]

class Database(BaseModel):
    """데이터베이스 모델"""
    database_name: str
    tables: List[Table]
    relationships: List[Relationship]

class AnnotationRequest(BaseModel):
    """어노테이션 요청 모델"""
    dbms_type: str
    databases: List[Database]

class AnnotatedColumn(BaseModel):
    """어노테이션이 추가된 컬럼 모델"""
    column_name: str
    description: str = Field(..., description="AI가 생성한 컬럼 설명")

class AnnotatedTable(BaseModel):
    """어노테이션이 추가된 테이블 모델"""
    table_name: str
    description: str = Field(..., description="AI가 생성한 테이블 설명")
    columns: List[AnnotatedColumn]

class AnnotatedRelationship(Relationship):
    """어노테이션이 추가된 관계 모델"""
    description: str = Field(..., description="AI가 생성한 관계 설명")

class AnnotatedDatabase(BaseModel):
    """어노테이션이 추가된 데이터베이스 모델"""
    database_name: str
    description: str = Field(..., description="AI가 생성한 데이터베이스 설명")
    tables: List[AnnotatedTable]
    relationships: List[AnnotatedRelationship]

class AnnotationResponse(BaseModel):
    """어노테이션 응답 모델"""
    dbms_type: str
    databases: List[AnnotatedDatabase]
