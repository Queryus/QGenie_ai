# src/agents/sql_agent_graph.py

import os
import sys
from typing import List, TypedDict, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END
from langchain.output_parsers.pydantic import PydanticOutputParser
from langchain_core.output_parsers import StrOutputParser
from langchain.prompts import load_prompt
from schemas.sql_schemas import SqlQuery
from core.db_manager import db_instance
from core.llm_provider import llm_instance

# --- PyInstaller 경로 해결 함수 ---
def resource_path(relative_path):
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # 개발 환경에서는 src 폴더를 기준으로 경로 설정
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    return os.path.join(base_path, relative_path)

# --- 상수 정의 ---
MAX_ERROR_COUNT = 3
PROMPT_VERSION = "v1"
PROMPT_DIR = os.path.join("prompts", PROMPT_VERSION, "sql_agent")

# --- 프롬프트 로드 ---
INTENT_CLASSIFIER_PROMPT = load_prompt(resource_path(os.path.join(PROMPT_DIR, "intent_classifier.yaml")))
DB_CLASSIFIER_PROMPT = load_prompt(resource_path(os.path.join(PROMPT_DIR, "db_classifier.yaml")))
SQL_GENERATOR_PROMPT = load_prompt(resource_path(os.path.join(PROMPT_DIR, "sql_generator.yaml")))
RESPONSE_SYNTHESIZER_PROMPT = load_prompt(resource_path(os.path.join(PROMPT_DIR, "response_synthesizer.yaml")))

# Agent 상태 정의
class SqlAgentState(TypedDict):
    question: str
    chat_history: List[BaseMessage]
    db_schema: str
    intent: str
    sql_query: str
    validation_error: Optional[str]
    validation_error_count: int
    execution_result: Optional[str]
    execution_error_count: int
    final_response: str

# --- 노드 함수 정의 ---
def intent_classifier_node(state: SqlAgentState):
    print("--- 0. 의도 분류 중 ---")
    chain = INTENT_CLASSIFIER_PROMPT | llm_instance | StrOutputParser()
    intent = chain.invoke({"question": state['question']})
    state['intent'] = intent
    return state

def unsupported_question_node(state: SqlAgentState):
    print("--- SQL 관련 없는 질문 ---")
    state['final_response'] = "죄송합니다, 해당 질문에는 답변할 수 없습니다. 데이터베이스 관련 질문만 가능합니다."
    return state

def db_classifier_node(state: SqlAgentState):
    print("--- 0.5. DB 분류 중 ---")
    
    # TODO: BE API 호출로 대체 필요
    available_dbs = [
        {
            "connection_name": "local_mysql",
            "database_name": "sakila",
            "description": "DVD 대여점 비즈니스 모델을 다루는 샘플 데이터베이스로, 영화, 배우, 고객, 대여 기록 등의 정보를 포함합니다."
        },
        {
            "connection_name": "local_mysql",
            "database_name": "ecom_prod",
            "description": "온라인 쇼핑몰의 운영 데이터베이스로, 상품 카탈로그, 고객 주문, 재고 및 배송 정보를 관리합니다."
        },
        {
            "connection_name": "local_mysql",
            "database_name": "hr_analytics",
            "description": "회사의 인사 관리 데이터베이스로, 직원 정보, 급여, 부서, 성과 평가 기록을 포함합니다."
        },
        {
            "connection_name": "local_mysql",
            "database_name": "web_logs",
            "description": "웹사이트 트래픽 분석을 위한 로그 데이터베이스로, 사용자 방문 기록, 페이지 뷰, 에러 로그 등을 저장합니다."
        }
    ]

    db_options = "\n".join([f"- {db['database_name']}: {db['description']}" for db in available_dbs])
    
    chain = DB_CLASSIFIER_PROMPT | llm_instance | StrOutputParser()
    selected_db_name = chain.invoke({
        "db_options": db_options,
        "question": state['question']
    })
    
    state['selected_db'] = selected_db_name.strip()
    
    # 선택된 DB의 스키마 정보를 가져와서 상태에 업데이트합니다.
    print(f'--- 선택된 DB: {selected_db_name} ---')
    
    # TODO: get_schema_for_db
    state['db_schema'] = db_instance.get_schema_for_db(db_name=selected_db_name)
    
    return state

def sql_generator_node(state: SqlAgentState):
    print("--- 1. SQL 생성 중 ---")
    parser = PydanticOutputParser(pydantic_object=SqlQuery)

    # --- 에러 피드백 컨텍스트 생성 ---
    error_feedback = ""
    # 1. 검증 오류가 있었을 경우
    if state.get("validation_error") and state.get("validation_error_count", 0) > 0:
        error_feedback = f"""
        Your previous query was rejected for the following reason: {state['validation_error']}
        Please generate a new, safe query that does not contain forbidden keywords.
        """
    # 2. 실행 오류가 있었을 경우
    elif state.get("execution_result") and "오류" in state.get("execution_result") and state.get("execution_error_count", 0) > 0:
        error_feedback = f"""
        Your previously generated SQL query failed with the following database error:
        FAILED SQL: {state['sql_query']}
        DATABASE ERROR: {state['execution_result']}
        Please correct the SQL query based on the error.
        """
    
    prompt = SQL_GENERATOR_PROMPT.format(
        format_instructions=parser.get_format_instructions(),
        db_schema=state['db_schema'],
        chat_history=state['chat_history'],
        question=state['question'],
        error_feedback=error_feedback
    )

    response = llm_instance.invoke(prompt)
    parsed_query = parser.invoke(response.content)
    state['sql_query'] = parsed_query.query
    state['validation_error'] = None
    state['execution_result'] = None
    return state

def sql_validator_node(state: SqlAgentState):
    print("--- 2. SQL 검증 중 ---")
    query_words = state['sql_query'].lower().split()
    dangerous_keywords = [
        "drop", "delete", "update", "insert", "truncate", 
        "alter", "create", "grant", "revoke"
    ]
    found_keywords = [keyword for keyword in dangerous_keywords if keyword in query_words]

    if found_keywords:
        keyword_str = ', '.join(f"'{k}'" for k in found_keywords)
        state['validation_error'] = f'위험한 키워드 {keyword_str}가 포함되어 있습니다.'
        state['validation_error_count'] += 1 # sql 검증 횟수 추가
    else:
        state['validation_error'] = None
        state['validation_error_count'] = 0 # sql 검증 횟수 초기화
    return state

def sql_executor_node(state: SqlAgentState):
    print("--- 3. SQL 실행 중 ---")
    try:
       result = db_instance.run(state['sql_query'])
       state['execution_result'] = str(result)
       state['validation_error_count'] = 0 # sql 검증 횟수 초기화
       state['execution_error_count'] = 0 # sql 실행 횟수 초기화
    except Exception as e:
       state['execution_result'] = f"실행 오류: {e}"
       state['validation_error_count'] = 0 # sql 검증 횟수 초기화
       state['execution_error_count'] += 1 # sql 실행 횟수 추가
    return state

def response_synthesizer_node(state: SqlAgentState):
    print("--- 4. 최종 답변 생성 중 ---")

    is_failure = state.get('validation_error_count', 0) >= MAX_ERROR_COUNT or \
                 state.get('execution_error_count', 0) >= MAX_ERROR_COUNT

    if is_failure:
        if state.get('validation_error_count', 0) >= MAX_ERROR_COUNT:
            error_type = "SQL 검증"
            error_details = state.get('validation_error')
        else:
            error_type = "SQL 실행"
            error_details = state.get('execution_result')
        
        context_message = f"""
        An attempt to answer the user's question failed after multiple retries.
        Failure Type: {error_type}
        Last Error: {error_details}
        """
    else:
        context_message = f"""
        Successfully executed the SQL query to answer the user's question.
        SQL Query: {state['sql_query']}
        SQL Result: {state['execution_result']}
        """

    prompt = RESPONSE_SYNTHESIZER_PROMPT.format(
        question=state['question'],
        context_message=context_message
    )
    response = llm_instance.invoke(prompt)
    state['final_response'] = response.content
    return state

# --- 엣지 함수 정의 ---
def route_after_intent_classification(state: SqlAgentState):
    if state['intent'] == "SQL":
        print("--- 의도: SQL 관련 질문 ---")
        return "db_classifier"
    print("--- 의도: SQL과 관련 없는 질문 ---")
    return "unsupported_question"

def should_execute_sql(state: SqlAgentState):
    if state.get("validation_error_count", 0) >= MAX_ERROR_COUNT:
        print(f"--- 검증 실패 {MAX_ERROR_COUNT}회 초과: 답변 생성으로 이동 ---")
        return "synthesize_failure"
    if state.get("validation_error"):
        print(f"--- 검증 실패 {state['validation_error_count']}회: SQL 재생성 ---")
        return "regenerate"
    print("--- 검증 성공: SQL 실행 ---")
    return "execute"

def should_retry_or_respond(state: SqlAgentState):
    if state.get("execution_error_count", 0) >= MAX_ERROR_COUNT:
        print(f"--- 실행 실패 {MAX_ERROR_COUNT}회 초과: 답변 생성으로 이동 ---")
        return "synthesize_failure"
    if "오류" in (state.get("execution_result") or ""):
        print(f"--- 실행 실패 {state['execution_error_count']}회: SQL 재생성 ---")
        return "regenerate"
    print("--- 실행 성공: 최종 답변 생성 ---")
    return "synthesize_success"

# --- 그래프 구성 ---
def create_sql_agent_graph() -> StateGraph:
    graph = StateGraph(SqlAgentState)
    
    graph.add_node("intent_classifier", intent_classifier_node)
    graph.add_node("db_classifier", db_classifier_node)
    graph.add_node("unsupported_question", unsupported_question_node)
    graph.add_node("sql_generator", sql_generator_node)
    graph.add_node("sql_validator", sql_validator_node)
    graph.add_node("sql_executor", sql_executor_node)
    graph.add_node("response_synthesizer", response_synthesizer_node)
    
    graph.set_entry_point("intent_classifier")
    
    graph.add_conditional_edges(
        "intent_classifier",
        route_after_intent_classification,
        {
            "db_classifier": "db_classifier",
            "unsupported_question": "unsupported_question"
        }
    )
    graph.add_edge("unsupported_question", END)

    graph.add_edge("db_classifier", "sql_generator")
    
    graph.add_edge("sql_generator", "sql_validator")

    graph.add_conditional_edges("sql_validator", should_execute_sql, {
        "regenerate": "sql_generator",
        "execute": "sql_executor",
        "synthesize_failure": "response_synthesizer"
    })
    graph.add_conditional_edges("sql_executor", should_retry_or_respond, {
        "regenerate": "sql_generator",
        "synthesize_success": "response_synthesizer",
        "synthesize_failure": "response_synthesizer"
    })
    graph.add_edge("response_synthesizer", END)
    
    return graph.compile()

sql_agent_app = create_sql_agent_graph()

# 워크 플로우 그림 작성
# graph_image_bytes = sql_agent_app.get_graph(xray=True).draw_mermaid_png()    
# with open("workflow_graph.png", "wb") as f:
#     f.write(graph_image_bytes)