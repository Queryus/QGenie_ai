# src/agents/sql_agent_graph.py

from typing import List, TypedDict, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END
from langchain.output_parsers.pydantic import PydanticOutputParser
from schemas.sql_schemas import SqlQuery
from core.db_manager import db_instance
from core.llm_provider import llm_instance

MAX_ERROR_COUNT = 3

# Agent 상태 정의
class SqlAgentState(TypedDict):
    question: str
    chat_history: List[BaseMessage]
    db_schema: str
    sql_query: str
    validation_error: Optional[str]
    validation_error_count: int
    execution_result: Optional[str]
    execution_error_count: int
    final_response: str

# --- 노드 함수 정의 ---
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
    
    prompt = f"""
    You are a powerful text-to-SQL model. Your role is to generate a SQL query based on the provided database schema and user question.
    
    {parser.get_format_instructions()}
    
    Schema: {state['db_schema']}
    History: {state['chat_history']}

    {error_feedback}

    Question: {state['question']}
    """

    response = llm_instance.invoke(prompt)
    parsed_query = parser.invoke(response)
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

    if state.get('validation_error_count', 0) >= MAX_ERROR_COUNT:
        message = f"SQL 검증에 {MAX_ERROR_COUNT}회 이상 실패했습니다. 마지막 오류: {state.get('validation_error')}"
    elif state.get('execution_error_count', 0) >= MAX_ERROR_COUNT:
        message = f"SQL 실행에 {MAX_ERROR_COUNT}회 이상 실패했습니다. 마지막 오류: {state.get('execution_result')}"
    else:
        message = f"SQL Result: {state['execution_result']}"

    prompt = f"""
    Question: {state['question']}
    SQL: {state['sql_query']}
    {message}
    
    Based on the information above, provide a final answer to the user in Korean.
    If there was an error, explain the problem to the user in a friendly way.
    사용자 질문과 쿼리가 어떤 관계가 있는지 같이 설명해
    """
    response = llm_instance.invoke(prompt)
    state['final_response'] = response.content
    return state

# --- 엣지 함수 정의 ---
def should_execute_sql(state: SqlAgentState):
    """SQL 검증 후, 실행할지/재생성할지/포기할지 결정합니다."""
    if state.get("validation_error_count", 0) >= MAX_ERROR_COUNT:
        print(f"--- 검증 실패 {MAX_ERROR_COUNT}회 초과: 답변 생성으로 이동 ---")
        return "synthesize_failure"
    if state.get("validation_error"):
        print(f"--- 검증 실패 {state['validation_error_count']}회: SQL 재생성 ---")
        return "regenerate"
    print("--- 검증 성공: SQL 실행 ---")
    return "execute"

def should_retry_or_respond(state: SqlAgentState):
    """SQL 실행 후, 성공/재시도/포기 여부를 결정합니다."""
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
    graph.add_node("sql_generator", sql_generator_node)
    graph.add_node("sql_validator", sql_validator_node)
    graph.add_node("sql_executor", sql_executor_node)
    graph.add_node("response_synthesizer", response_synthesizer_node)
    
    graph.set_entry_point("sql_generator")
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