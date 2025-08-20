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
        print("=" * 60)
        print("🔍 [INTENT_CLASSIFIER] 의도 분류 시작")
        print("=" * 60)
        
        try:
            llm = await self.llm_provider.get_llm()
            
            # 채팅 내역을 활용하여 의도 분류
            input_data = {
                "question": state['question'],
                "chat_history": state.get('chat_history', [])
            }
            
            print(f"📝 입력 질문: {input_data['question']}")
            print(f"💬 채팅 히스토리: {len(input_data['chat_history'])}개 항목")
            if input_data['chat_history']:
                for i, chat in enumerate(input_data['chat_history'][-3:]):  # 최근 3개만 출력
                    print(f"   [{i}] {chat}")
            
            chain = self.intent_classifier_prompt | llm | StrOutputParser()
            intent = await chain.ainvoke(input_data)
            state['intent'] = intent.strip()
            
            print(f"✅ 의도 분류 결과: '{state['intent']}'")
            print(f"📊 분류된 노드 경로: {'SQL 처리' if state['intent'] == 'SQL' else '일반 응답'}")
            print("=" * 60)
            return state
            
        except Exception as e:
            print(f"❌ 의도 분류 실패: {e}")
            print(f"🔄 기본값 SQL로 설정")
            # 기본값으로 SQL 처리
            state['intent'] = "SQL"
            print("=" * 60)
            return state
    
    async def unsupported_question_node(self, state: SqlAgentState) -> SqlAgentState:
        """SQL과 관련 없는 질문을 처리하는 노드"""
        print("=" * 60)
        print("🚫 [UNSUPPORTED_QUESTION] SQL 관련 없는 질문 처리")
        print("=" * 60)
        
        print(f"📝 처리된 질문: {state['question']}")
        print(f"🔄 의도 분류 결과: {state.get('intent', 'UNKNOWN')}")
        
        state['final_response'] = """죄송합니다, 해당 질문에는 답변할 수 없습니다. 
저는 데이터베이스 관련 질문만 처리할 수 있습니다. 
SQL 쿼리나 데이터 분석과 관련된 질문을 해주세요."""
        
        print(f"✅ 최종 응답 설정 완료")
        print("=" * 60)
        return state
    
    async def db_classifier_node(self, state: SqlAgentState) -> SqlAgentState:
        """데이터베이스를 분류하고 스키마를 가져오는 노드"""
        print("=" * 60)
        print("🗄️ [DB_CLASSIFIER] 데이터베이스 분류 시작")
        print("=" * 60)
        
        try:
            print(f"📝 분석할 질문: {state['question']}")
            
            # DBMS 프로필과 어노테이션을 함께 조회
            available_dbs_with_annotations = await self.database_service.get_databases_with_annotations()
            
            if not available_dbs_with_annotations:
                raise DatabaseConnectionException("사용 가능한 DBMS가 없습니다.")
            
            print(f"🔍 발견된 DBMS: {len(available_dbs_with_annotations)}개")
            
            # 어노테이션 정보를 포함한 DBMS 옵션 생성
            db_options = "\n".join([
                f"- {db['display_name']}: {db['description']}" 
                for db in available_dbs_with_annotations
            ])
            
            print("📋 사용 가능한 DBMS 목록:")
            for i, db in enumerate(available_dbs_with_annotations):
                print(f"   [{i+1}] {db['display_name']}")
                print(f"       설명: {db['description']}")
                print(f"       타입: {db['profile']['type']}")
                print(f"       호스트: {db['profile']['host']}:{db['profile']['port']}")
                annotation_status = "있음" if (db['annotations'] and db['annotations'].code != "4401") else "없음"
                print(f"       어노테이션: {annotation_status}")
            
            print(f"\n🤖 LLM에게 전달할 DBMS 옵션:")
            print(db_options)
            
            # LLM을 사용하여 적절한 DBMS 선택
            llm = await self.llm_provider.get_llm()
            chain = self.db_classifier_prompt | llm | StrOutputParser()
            selected_db_display_name = await chain.ainvoke({
                "db_options": db_options,
                "chat_history": state['chat_history'],
                "question": state['question']
            })
            
            selected_db_display_name = selected_db_display_name.strip()
            print(f"🎯 LLM이 선택한 DBMS: '{selected_db_display_name}'")
            
            # 선택된 display_name으로 실제 DBMS 정보 찾기
            selected_db_info = None
            for db in available_dbs_with_annotations:
                if db['display_name'] == selected_db_display_name:
                    selected_db_info = db
                    print(f"✅ 정확히 매칭됨: {db['display_name']}")
                    break
            
            if not selected_db_info:
                print(f"⚠️ 정확한 매칭 실패, 부분 매칭 시도...")
                # 부분 매칭 시도
                for db in available_dbs_with_annotations:
                    if selected_db_display_name in db['display_name'] or db['display_name'] in selected_db_display_name:
                        selected_db_info = db
                        print(f"✅ 부분 매칭됨: {db['display_name']}")
                        break
            
            if not selected_db_info:
                print(f"❌ 매칭 실패: '{selected_db_display_name}'")
                print(f"🔄 첫 번째 DBMS 사용: {available_dbs_with_annotations[0]['display_name']}")
                selected_db_info = available_dbs_with_annotations[0]
            
            state['selected_db'] = selected_db_info['display_name']
            state['selected_db_profile'] = selected_db_info['profile']
            state['selected_db_annotations'] = selected_db_info['annotations']
            
            print(f"📊 최종 선택된 DBMS:")
            print(f"   이름: {selected_db_info['display_name']}")
            print(f"   프로필 ID: {selected_db_info['profile']['id']}")
            print(f"   타입: {selected_db_info['profile']['type']}")
            print(f"   연결: {selected_db_info['profile']['host']}:{selected_db_info['profile']['port']}")
            
            # 어노테이션 정보를 스키마로 사용
            annotations = selected_db_info['annotations']
            if annotations and annotations.code != "4401" and annotations.data.databases:
                schema_info = self._convert_annotations_to_schema(annotations)
                state['db_schema'] = schema_info
                print(f"✅ 어노테이션 기반 스키마 사용 ({len(annotations.data.databases)}개 DB)")
                print(f"📄 스키마 요약:")
                for db in annotations.data.databases:
                    print(f"   - {db.db_name}: {len(db.tables)}개 테이블, {len(db.relationships)}개 관계")
            else:
                # 어노테이션이 없는 경우 기본 정보로 대체
                schema_info = f"DBMS 유형: {selected_db_info['profile']['type']}\n"
                schema_info += f"호스트: {selected_db_info['profile']['host']}\n"
                schema_info += f"포트: {selected_db_info['profile']['port']}\n"
                schema_info += "상세 스키마 정보가 없습니다. 기본 SQL 구문을 사용하세요."
                state['db_schema'] = schema_info
                print(f"⚠️ 어노테이션 없음, 기본 DBMS 정보 사용")
            
            print("=" * 60)
            return state
            
        except Exception as e:
            print(f"❌ 데이터베이스 분류 실패: {e}")
            print(f"🔍 에러 타입: {type(e).__name__}")
            print(f"📝 에러 상세: {str(e)}")
            print("=" * 60)
            
            # 폴백 없이 에러를 다시 발생시킴
            raise e
    
    def _convert_annotations_to_schema(self, annotations) -> str:
        """어노테이션 데이터를 스키마 문자열로 변환합니다."""
        try:
            # AnnotationResponse 객체인지 확인
            if hasattr(annotations, 'data') and hasattr(annotations, 'code'):
                if annotations.code == "4401" or not annotations.data.databases:
                    return "어노테이션 스키마 정보가 없습니다."
                
                schema_parts = []
                schema_parts.append(f"=== {annotations.data.dbms_type.upper()} 어노테이션 기반 스키마 정보 ===")
                
                # 각 데이터베이스별 정보 추출
                for db in annotations.data.databases:
                    schema_parts.append(f"\n[데이터베이스: {db.db_name}]")
                    schema_parts.append(f"설명: {db.description}")
                    
                    # 테이블 정보
                    schema_parts.append(f"\n테이블 ({len(db.tables)}개):")
                    for table in db.tables:
                        schema_parts.append(f"\n  • {table.table_name}")
                        schema_parts.append(f"    설명: {table.description}")
                        schema_parts.append(f"    컬럼 ({len(table.columns)}개):")
                        
                        for col in table.columns:
                            schema_parts.append(f"      - {col.column_name} ({col.data_type}): {col.description}")
                    
                    # 관계 정보
                    if db.relationships:
                        schema_parts.append(f"\n관계 ({len(db.relationships)}개):")
                        for rel in db.relationships:
                            rel_desc = rel.description or "관계 설명 없음"
                            schema_parts.append(f"  • {rel.from_table}({', '.join(rel.from_columns)}) → {rel.to_table}({', '.join(rel.to_columns)})")
                            schema_parts.append(f"    설명: {rel_desc}")
                
                return "\n".join(schema_parts)
            
            # 기존 dict 형태 처리 (호환성)
            elif isinstance(annotations, dict):
                if not annotations or annotations.get('code') == "4401":
                    return "어노테이션 스키마 정보가 없습니다."
                
                schema_parts = []
                schema_parts.append("=== 어노테이션 기반 스키마 정보 ===")
                schema_parts.append(f"어노테이션 데이터: {str(annotations)[:500]}...")
                return "\n".join(schema_parts)
            
            else:
                return "어노테이션 스키마 정보가 없습니다."
            
        except Exception as e:
            print(f"어노테이션 변환 중 오류: {e}")
            return f"어노테이션 변환 실패: {e}"

    async def sql_generator_node(self, state: SqlAgentState) -> SqlAgentState:
        """SQL 쿼리를 생성하는 노드"""
        print("=" * 60)
        print("🔧 [SQL_GENERATOR] SQL 쿼리 생성 시작")
        print("=" * 60)
        
        try:
            parser = PydanticOutputParser(pydantic_object=SqlQuery)
            
            print(f"📝 분석할 질문: {state['question']}")
            print(f"🗄️ 선택된 DB: {state.get('selected_db', 'UNKNOWN')}")
            
            # 에러 피드백 컨텍스트 생성
            error_feedback = self._build_error_feedback(state)
            
            if error_feedback:
                print(f"⚠️ 이전 에러 피드백:")
                print(f"   {error_feedback.strip()}")
            else:
                print(f"✅ 첫 번째 SQL 생성 시도")
            
            print(f"\n📄 사용할 스키마 정보:")
            schema_preview = state['db_schema'][:500] + "..." if len(state['db_schema']) > 500 else state['db_schema']
            print(f"   {schema_preview}")
            
            prompt = self.sql_generator_prompt.format(
                format_instructions=parser.get_format_instructions(),
                db_schema=state['db_schema'],
                chat_history=state['chat_history'],
                question=state['question'],
                error_feedback=error_feedback
            )
            
            print(f"\n🤖 LLM에게 SQL 생성 요청 중...")
            llm = await self.llm_provider.get_llm()
            response = await llm.ainvoke(prompt)
            
            print(f"📨 LLM 응답 길이: {len(response.content)}자")
            print(f"📨 LLM 원본 응답:")
            print(f"   {response.content[:300]}...")
            
            parsed_query = parser.invoke(response.content)
            
            state['sql_query'] = parsed_query.query
            state['validation_error'] = None
            state['execution_result'] = None
            
            print(f"\n✅ SQL 쿼리 생성 완료:")
            print(f"   {parsed_query.query}")
            print(f"📊 상태 업데이트:")
            print(f"   - sql_query: 설정됨")
            print(f"   - validation_error: 초기화됨") 
            print(f"   - execution_result: 초기화됨")
            
            print("=" * 60)
            return state
            
        except Exception as e:
            print(f"❌ SQL 생성 실패: {e}")
            print(f"🔍 에러 타입: {type(e).__name__}")
            print("=" * 60)
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
        print("=" * 60)
        print("🔒 [SQL_VALIDATOR] SQL 안전성 검증 시작")
        print("=" * 60)
        
        try:
            sql_query = state['sql_query']
            print(f"🔍 검증할 SQL 쿼리:")
            print(f"   {sql_query}")
            
            query_words = sql_query.lower().split()
            dangerous_keywords = [
                "drop", "delete", "update", "insert", "truncate", 
                "alter", "create", "grant", "revoke"
            ]
            
            print(f"🚫 검사할 위험 키워드: {dangerous_keywords}")
            
            found_keywords = [keyword for keyword in dangerous_keywords if keyword in query_words]
            
            current_retry_count = state.get('validation_error_count', 0)
            print(f"🔄 현재 검증 재시도 횟수: {current_retry_count}/{MAX_ERROR_COUNT}")
            
            if found_keywords:
                keyword_str = ', '.join(f"'{k}'" for k in found_keywords)
                error_msg = f'위험한 키워드 {keyword_str}가 포함되어 있습니다.'
                state['validation_error'] = error_msg
                state['validation_error_count'] = current_retry_count + 1
                
                print(f"❌ 검증 실패:")
                print(f"   발견된 위험 키워드: {found_keywords}")
                print(f"   에러 메시지: {error_msg}")
                print(f"   실패 횟수: {state['validation_error_count']}/{MAX_ERROR_COUNT}")
                
                if state['validation_error_count'] >= MAX_ERROR_COUNT:
                    print(f"🚨 최대 재시도 횟수 초과!")
                    raise MaxRetryExceededException(
                        f"SQL 검증 실패가 {MAX_ERROR_COUNT}회 반복됨", MAX_ERROR_COUNT
                    )
                else:
                    print(f"🔄 SQL 재생성으로 이동")
            else:
                state['validation_error'] = None
                state['validation_error_count'] = 0
                print(f"✅ 검증 성공: 위험한 키워드 없음")
                print(f"📊 상태 업데이트:")
                print(f"   - validation_error: 초기화됨")
                print(f"   - validation_error_count: 0으로 리셋")
                
            print("=" * 60)
            return state
            
        except MaxRetryExceededException:
            print("=" * 60)
            raise
        except Exception as e:
            print(f"❌ SQL 검증 중 오류 발생: {e}")
            print(f"🔍 에러 타입: {type(e).__name__}")
            print("=" * 60)
            raise ValidationException(f"SQL 검증 중 오류 발생: {e}")
    
    async def sql_executor_node(self, state: SqlAgentState) -> SqlAgentState:
        """SQL 쿼리를 실행하는 노드"""
        print("=" * 60)
        print("⚡ [SQL_EXECUTOR] SQL 쿼리 실행 시작")
        print("=" * 60)
        
        try:
            sql_query = state['sql_query']
            selected_db = state.get('selected_db', 'default')
            
            print(f"🔍 실행할 SQL 쿼리:")
            print(f"   {sql_query}")
            print(f"🗄️ 대상 데이터베이스: {selected_db}")
            
            # 선택된 DB 프로필에서 실제 DB ID 가져오기
            db_profile = state.get('selected_db_profile')
            if db_profile and 'id' in db_profile:
                user_db_id = db_profile['id']
                print(f"📋 사용할 DB 프로필:")
                print(f"   - ID: {user_db_id}")
                print(f"   - 타입: {db_profile.get('type', 'UNKNOWN')}")
                print(f"   - 호스트: {db_profile.get('host', 'UNKNOWN')}")
                print(f"   - 포트: {db_profile.get('port', 'UNKNOWN')}")
            else:
                user_db_id = 'TEST-USER-DB-12345'  # 폴백
                print(f"⚠️ DB 프로필 없음, 테스트 ID 사용: {user_db_id}")
            
            current_retry_count = state.get('execution_error_count', 0)
            print(f"🔄 현재 실행 재시도 횟수: {current_retry_count}/{MAX_ERROR_COUNT}")
            
            print(f"\n🚀 SQL 실행 중...")
            result = await self.database_service.execute_query(
                sql_query, 
                database_name=selected_db,
                user_db_id=user_db_id
            )
            
            state['execution_result'] = result
            state['validation_error_count'] = 0
            state['execution_error_count'] = 0
            
            print(f"✅ SQL 실행 성공!")
            print(f"📊 실행 결과:")
            if isinstance(result, str) and len(result) > 500:
                print(f"   {result[:500]}...")
                print(f"   (총 {len(result)}자, 잘림)")
            else:
                print(f"   {result}")
        
            print(f"📈 상태 업데이트:")
            print(f"   - execution_result: 설정됨")
            print(f"   - validation_error_count: 0으로 리셋")
            print(f"   - execution_error_count: 0으로 리셋")
            
            print("=" * 60)
            return state
            
        except Exception as e:
            error_msg = f"실행 오류: {e}"
            state['execution_result'] = error_msg
            state['validation_error_count'] = 0
            state['execution_error_count'] = state.get('execution_error_count', 0) + 1
            
            print(f"❌ SQL 실행 실패:")
            print(f"   에러 메시지: {error_msg}")
            print(f"   실패 횟수: {state['execution_error_count']}/{MAX_ERROR_COUNT}")
            print(f"   에러 타입: {type(e).__name__}")
            
            if state['execution_error_count'] >= MAX_ERROR_COUNT:
                print(f"🚨 최대 재시도 횟수 도달!")
            else:
                print(f"🔄 SQL 재생성으로 이동")
            
            print(f"📈 상태 업데이트:")
            print(f"   - execution_result: 에러 메시지 설정")
            print(f"   - validation_error_count: 0으로 리셋")
            print(f"   - execution_error_count: {state['execution_error_count']}로 증가")
            
            print("=" * 60)
            # 실행 실패 시에도 상태를 반환하여 엣지에서 판단하도록 함
            return state
    
    async def response_synthesizer_node(self, state: SqlAgentState) -> SqlAgentState:
        """최종 답변을 생성하는 노드"""
        print("=" * 60)
        print("📝 [RESPONSE_SYNTHESIZER] 최종 답변 생성 시작")
        print("=" * 60)
        
        try:
            print(f"📝 원본 질문: {state['question']}")
            
            is_failure = (state.get('validation_error_count', 0) >= MAX_ERROR_COUNT or 
                         state.get('execution_error_count', 0) >= MAX_ERROR_COUNT)
            
            print(f"📊 처리 상태 분석:")
            print(f"   - validation_error_count: {state.get('validation_error_count', 0)}")
            print(f"   - execution_error_count: {state.get('execution_error_count', 0)}")
            print(f"   - 최대 재시도 횟수: {MAX_ERROR_COUNT}")
            print(f"   - 실패 상태: {is_failure}")
            
            if is_failure:
                context_message = self._build_failure_context(state)
                print(f"❌ 실패 컨텍스트 사용:")
                print(f"   {context_message.strip()}")
            else:
                context_message = f"""
                Successfully executed the SQL query to answer the user's question.
                SQL Query: {state['sql_query']}
                SQL Result: {state['execution_result']}
                """
                print(f"✅ 성공 컨텍스트 사용:")
                print(f"   SQL: {state['sql_query']}")
                result_preview = str(state['execution_result'])
                if len(result_preview) > 200:
                    result_preview = result_preview[:200] + "..."
                print(f"   결과: {result_preview}")
            
            prompt = self.response_synthesizer_prompt.format(
                question=state['question'],
                chat_history=state['chat_history'],
                context_message=context_message
            )
            
            print(f"\n🤖 LLM에게 답변 생성 요청 중...")
            llm = await self.llm_provider.get_llm()
            response = await llm.ainvoke(prompt)
            state['final_response'] = response.content
            
            print(f"✅ 최종 답변 생성 완료!")
            print(f"📄 생성된 답변 (미리보기):")
            response_preview = response.content[:300] + "..." if len(response.content) > 300 else response.content
            print(f"   {response_preview}")
            print(f"📊 답변 길이: {len(response.content)}자")
            
            print("=" * 60)
            return state
            
        except Exception as e:
            print(f"❌ 답변 생성 실패: {e}")
            print(f"🔍 에러 타입: {type(e).__name__}")
            # 최종 답변 생성 실패 시 기본 메시지 제공
            state['final_response'] = f"죄송합니다. 답변 생성 중 오류가 발생했습니다: {e}"
            print(f"🔄 기본 에러 메시지 설정")
            print("=" * 60)
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
