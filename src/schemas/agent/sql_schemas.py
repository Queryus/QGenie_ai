# src/schemas/agent/sql_schemas.py

from pydantic import BaseModel, Field

class SqlQuery(BaseModel):
    """SQL 쿼리를 나타내는 Pydantic 모델"""
    query: str = Field(description="생성된 SQL 쿼리")
