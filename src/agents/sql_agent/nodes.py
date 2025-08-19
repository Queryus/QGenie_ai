# src/agents/sql_agent/nodes.py

import os
import sys
import asyncio
from typing import List, Optional
from langchain.output_parsers.pydantic import PydanticOutputParser
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import load_prompt

from schemas.agent.sql_schemas import SqlQuery
from services.database.database_service import DatabaseService
from core.providers.llm_provider import LLMProvider
from .state import SqlAgentState
from .exceptions import (
    ValidationException, 
    ExecutionException, 
    DatabaseConnectionException,
    MaxRetryExceededException
)

# 상수 정의
MAX_ERROR_COUNT = 3
PROMPT_VERSION = "v1"
PROMPT_DIR = os.path.join("prompts", PROMPT_VERSION, "sql_agent")

def resource_path(relative_path):
    """PyInstaller 경로 해결 함수"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    return os.path.join(base_path, relative_path)

class SqlAgentNodes:
    """SQL Agent의 모든 노드 로직을 담당하는 클래스"""
    
    def __init__(self, llm_provider: LLMProvider, database_service: DatabaseService):
        self.llm_provider = llm_provider
        self.database_service = database_service
        
        # 프롬프트 로드
        self._load_prompts()
    
    def _load_prompts(self):
        """프롬프트 파일들을 로드합니다."""
        try:
            self.intent_classifier_prompt = load_prompt(
                resource_path(os.path.join(PROMPT_DIR, "intent_classifier.yaml"))
            )
            self.db_classifier_prompt = load_prompt(
                resource_path(os.path.join(PROMPT_DIR, "db_classifier.yaml"))
            )
            self.sql_generator_prompt = load_prompt(
                resource_path(os.path.join(PROMPT_DIR, "sql_generator.yaml"))
            )
            self.response_synthesizer_prompt = load_prompt(
                resource_path(os.path.join(PROMPT_DIR, "response_synthesizer.yaml"))
            )
        except Exception as e:
            raise FileNotFoundError(f"프롬프트 파일 로드 실패: {e}")
    
    async def intent_classifier_node(self, state: SqlAgentState) -> SqlAgentState:
        """사용자 질문의 의도를 분류하는 노드"""
        print("--- 0. 의도 분류 중 ---")
        
        try:
            llm = await self.llm_provider.get_llm()
            
            # 채팅 내역을 활용하여 의도 분류
            input_data = {
                "question": state['question'],
                "chat_history": state.get('chat_history', [])
            }
            
            chain = self.intent_classifier_prompt | llm | StrOutputParser()
            intent = await chain.ainvoke(input_data)
            state['intent'] = intent.strip()
            
            print(f"의도 분류 결과: {state['intent']}")
            return state
            
        except Exception as e:
            print(f"의도 분류 실패: {e}")
            # 기본값으로 SQL 처리
            state['intent'] = "SQL"
            return state
    
    async def unsupported_question_node(self, state: SqlAgentState) -> SqlAgentState:
        """SQL과 관련 없는 질문을 처리하는 노드"""
        print("--- SQL 관련 없는 질문 ---")
        
        state['final_response'] = """죄송합니다, 해당 질문에는 답변할 수 없습니다. 
저는 데이터베이스 관련 질문만 처리할 수 있습니다. 
SQL 쿼리나 데이터 분석과 관련된 질문을 해주세요."""
        
        return state
    
    async def db_classifier_node(self, state: SqlAgentState) -> SqlAgentState:
        """데이터베이스를 분류하고 스키마를 가져오는 노드"""
        print("--- 0.5. DB 분류 중 ---")
        
        try:
            # DBMS 프로필과 어노테이션을 함께 조회
            available_dbs_with_annotations = await self.database_service.get_databases_with_annotations()
            
            if not available_dbs_with_annotations:
                raise DatabaseConnectionException("사용 가능한 DBMS가 없습니다.")
            
            print(f"--- {len(available_dbs_with_annotations)}개의 DBMS 발견 ---")
            
            # 어노테이션 정보를 포함한 DBMS 옵션 생성
            db_options = "\n".join([
                f"- {db['display_name']}: {db['description']}" 
                for db in available_dbs_with_annotations
            ])
            
            # LLM을 사용하여 적절한 DBMS 선택
            llm = await self.llm_provider.get_llm()
            chain = self.db_classifier_prompt | llm | StrOutputParser()
            selected_db_display_name = await chain.ainvoke({
                "db_options": db_options,
                "chat_history": state['chat_history'],
                "question": state['question']
            })
            
            selected_db_display_name = selected_db_display_name.strip()
            
            # 선택된 display_name으로 실제 DBMS 정보 찾기
            selected_db_info = None
            for db in available_dbs_with_annotations:
                if db['display_name'] == selected_db_display_name:
                    selected_db_info = db
                    break
            
            if not selected_db_info:
                # 부분 매칭 시도
                for db in available_dbs_with_annotations:
                    if selected_db_display_name in db['display_name'] or db['display_name'] in selected_db_display_name:
                        selected_db_info = db
                        break
            
            if not selected_db_info:
                print(f"--- 선택된 DBMS를 찾을 수 없음: {selected_db_display_name}, 첫 번째 DBMS 사용 ---")
                selected_db_info = available_dbs_with_annotations[0]
            
            state['selected_db'] = selected_db_info['display_name']
            state['selected_db_profile'] = selected_db_info['profile']
            state['selected_db_annotations'] = selected_db_info['annotations']
            
            print(f'--- 선택된 DBMS: {selected_db_info["display_name"]} ---')
            print(f'--- DBMS 프로필 ID: {selected_db_info["profile"]["id"]} ---')
            
            # 어노테이션 정보를 스키마로 사용
            if selected_db_info['annotations'] and 'data' in selected_db_info['annotations']:
                schema_info = self._convert_annotations_to_schema(selected_db_info['annotations'])
                state['db_schema'] = schema_info
                print(f"--- 어노테이션 기반 스키마 사용 ---")
            else:
                # 어노테이션이 없는 경우 기본 정보로 대체
                schema_info = f"DBMS 유형: {selected_db_info['profile']['type']}\n"
                schema_info += f"호스트: {selected_db_info['profile']['host']}\n"
                schema_info += f"포트: {selected_db_info['profile']['port']}\n"
                schema_info += "상세 스키마 정보가 없습니다. 기본 SQL 구문을 사용하세요."
                state['db_schema'] = schema_info
                print(f"--- 기본 DBMS 정보 사용 ---")
            
            return state
            
        except Exception as e:
            print(f"데이터베이스 분류 실패: {e}")
            print(f"에러 타입: {type(e).__name__}")
            print(f"에러 상세: {str(e)}")
            
            # 폴백 없이 에러를 다시 발생시킴
            raise e
    
    def _convert_annotations_to_schema(self, annotations: dict) -> str:
        """어노테이션 데이터를 스키마 문자열로 변환합니다."""
        try:
            if not annotations or 'data' not in annotations:
                return "어노테이션 스키마 정보가 없습니다."
            
            # 어노테이션 구조에 따라 스키마 정보 추출
            # 실제 어노테이션 응답 구조를 확인 후 구현 필요
            schema_parts = []
            schema_parts.append("=== 어노테이션 기반 스키마 정보 ===")
            
            annotation_data = annotations.get('data', {})
            
            # 어노테이션 데이터가 데이터베이스 정보를 포함하는 경우
            if isinstance(annotation_data, dict):
                for key, value in annotation_data.items():
                    schema_parts.append(f"{key}: {str(value)[:200]}...")
            elif isinstance(annotation_data, list):
                for i, item in enumerate(annotation_data):
                    schema_parts.append(f"항목 {i+1}: {str(item)[:200]}...")
            else:
                schema_parts.append(f"어노테이션 데이터: {str(annotation_data)[:500]}...")
            
            return "\n".join(schema_parts)
            
        except Exception as e:
            print(f"어노테이션 변환 중 오류: {e}")
            return f"어노테이션 변환 실패: {e}"

    async def sql_generator_node(self, state: SqlAgentState) -> SqlAgentState:
        """SQL 쿼리를 생성하는 노드"""
        print("--- 1. SQL 생성 중 ---")
        
        try:
            parser = PydanticOutputParser(pydantic_object=SqlQuery)
            
            # 에러 피드백 컨텍스트 생성
            error_feedback = self._build_error_feedback(state)
            
            prompt = self.sql_generator_prompt.format(
                format_instructions=parser.get_format_instructions(),
                db_schema=state['db_schema'],
                chat_history=state['chat_history'],
                question=state['question'],
                error_feedback=error_feedback
            )
            
            llm = await self.llm_provider.get_llm()
            response = await llm.ainvoke(prompt)
            parsed_query = parser.invoke(response.content)
            
            state['sql_query'] = parsed_query.query
            state['validation_error'] = None
            state['execution_result'] = None
            
            return state
            
        except Exception as e:
            raise ExecutionException(f"SQL 생성 실패: {e}")
    
    def _build_error_feedback(self, state: SqlAgentState) -> str:
        """에러 피드백 컨텍스트를 생성합니다."""
        error_feedback = ""
        
        # 검증 오류가 있었을 경우
        if state.get("validation_error") and state.get("validation_error_count", 0) > 0:
            error_feedback = f"""
            Your previous query was rejected for the following reason: {state['validation_error']}
            Please generate a new, safe query that does not contain forbidden keywords.
            """
        # 실행 오류가 있었을 경우
        elif (state.get("execution_result") and 
              "오류" in state.get("execution_result", "") and 
              state.get("execution_error_count", 0) > 0):
            error_feedback = f"""
            Your previously generated SQL query failed with the following database error:
            FAILED SQL: {state['sql_query']}
            DATABASE ERROR: {state['execution_result']}
            Please correct the SQL query based on the error.
            """
        
        return error_feedback
    
    async def sql_validator_node(self, state: SqlAgentState) -> SqlAgentState:
        """SQL 쿼리의 안전성을 검증하는 노드"""
        print("--- 2. SQL 검증 중 ---")
        
        try:
            query_words = state['sql_query'].lower().split()
            dangerous_keywords = [
                "drop", "delete", "update", "insert", "truncate", 
                "alter", "create", "grant", "revoke"
            ]
            found_keywords = [keyword for keyword in dangerous_keywords if keyword in query_words]
            
            if found_keywords:
                keyword_str = ', '.join(f"'{k}'" for k in found_keywords)
                error_msg = f'위험한 키워드 {keyword_str}가 포함되어 있습니다.'
                state['validation_error'] = error_msg
                state['validation_error_count'] = state.get('validation_error_count', 0) + 1
                
                if state['validation_error_count'] >= MAX_ERROR_COUNT:
                    raise MaxRetryExceededException(
                        f"SQL 검증 실패가 {MAX_ERROR_COUNT}회 반복됨", MAX_ERROR_COUNT
                    )
            else:
                state['validation_error'] = None
                state['validation_error_count'] = 0
                
            return state
            
        except MaxRetryExceededException:
            raise
        except Exception as e:
            raise ValidationException(f"SQL 검증 중 오류 발생: {e}")
    
    async def sql_executor_node(self, state: SqlAgentState) -> SqlAgentState:
        """SQL 쿼리를 실행하는 노드"""
        print("--- 3. SQL 실행 중 ---")
        
        try:
            selected_db = state.get('selected_db', 'default')
            
            # 선택된 DB 프로필에서 실제 DB ID 가져오기
            db_profile = state.get('selected_db_profile')
            if db_profile and 'id' in db_profile:
                user_db_id = db_profile['id']
                print(f"--- 실행용 DB 프로필 ID: {user_db_id} ---")
            else:
                user_db_id = 'TEST-USER-DB-12345'  # 폴백
                print(f"--- DB 프로필이 없어 테스트 ID 사용: {user_db_id} ---")
                        
            result = await self.database_service.execute_query(
                state['sql_query'], 
                database_name=selected_db,
                user_db_id=user_db_id
            )
            
            state['execution_result'] = result
            state['validation_error_count'] = 0
            state['execution_error_count'] = 0
            
            return state
            
        except Exception as e:
            error_msg = f"실행 오류: {e}"
            state['execution_result'] = error_msg
            state['validation_error_count'] = 0
            state['execution_error_count'] = state.get('execution_error_count', 0) + 1
            
            print(f"⚠️ SQL 실행 실패 ({state['execution_error_count']}/{MAX_ERROR_COUNT}): {error_msg}")
            
            # 실행 실패 시에도 상태를 반환하여 엣지에서 판단하도록 함
            return state
    
    async def response_synthesizer_node(self, state: SqlAgentState) -> SqlAgentState:
        """최종 답변을 생성하는 노드"""
        print("--- 4. 최종 답변 생성 중 ---")
        
        try:
            is_failure = (state.get('validation_error_count', 0) >= MAX_ERROR_COUNT or 
                         state.get('execution_error_count', 0) >= MAX_ERROR_COUNT)
            
            if is_failure:
                context_message = self._build_failure_context(state)
            else:
                context_message = f"""
                Successfully executed the SQL query to answer the user's question.
                SQL Query: {state['sql_query']}
                SQL Result: {state['execution_result']}
                """
            
            prompt = self.response_synthesizer_prompt.format(
                question=state['question'],
                chat_history=state['chat_history'],
                context_message=context_message
            )
            
            llm = await self.llm_provider.get_llm()
            response = await llm.ainvoke(prompt)
            state['final_response'] = response.content
            
            return state
            
        except Exception as e:
            # 최종 답변 생성 실패 시 기본 메시지 제공
            state['final_response'] = f"죄송합니다. 답변 생성 중 오류가 발생했습니다: {e}"
            return state
    
    def _build_failure_context(self, state: SqlAgentState) -> str:
        """실패 상황에 대한 컨텍스트 메시지를 생성합니다."""
        if state.get('validation_error_count', 0) >= MAX_ERROR_COUNT:
            error_type = "SQL 검증"
            error_details = state.get('validation_error')
        else:
            error_type = "SQL 실행"
            error_details = state.get('execution_result')
        
        return f"""
        An attempt to answer the user's question failed after multiple retries.
        Failure Type: {error_type}
        Last Error: {error_details}
        """
