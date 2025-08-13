# src/api/v1/schemas/annotator_schemas.py

from pydantic import BaseModel, Field
from typing import List, Dict, Any

class Column(BaseModel):
    column_name: str
    data_type: str

class Table(BaseModel):
    table_name: str
    columns: List[Column]
    sample_rows: List[Dict[str, Any]]

class Relationship(BaseModel):
    from_table: str
    from_columns: List[str]
    to_table: str
    to_columns: List[str]

class Database(BaseModel):
    database_name: str
    tables: List[Table]
    relationships: List[Relationship]

class AnnotationRequest(BaseModel):
    dbms_type: str
    databases: List[Database]

class AnnotatedColumn(Column):
    description: str = Field(..., description="AI가 생성한 컬럼 설명")

class AnnotatedTable(Table):
    description: str = Field(..., description="AI가 생성한 테이블 설명")
    columns: List[AnnotatedColumn]

class AnnotatedRelationship(Relationship):
    description: str = Field(..., description="AI가 생성한 관계 설명")

class AnnotatedDatabase(Database):
    description: str = Field(..., description="AI가 생성한 데이터베이스 설명")
    tables: List[AnnotatedTable]
    relationships: List[AnnotatedRelationship]

class AnnotationResponse(BaseModel):
    dbms_type: str
    databases: List[AnnotatedDatabase]
