# app/agents/sql_agent_graph.py

from typing import List, TypedDict, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, END
from src.core.db_manager import db_instance
from src.core.llm_provider import llm_instance

# Agent 상태 정의
class SqlAgentState(TypedDict):
    question: str
    chat_history: List[BaseMessage]
    db_schema: str
    sql_query: str
    validation_error: Optional[str]
    execution_result: Optional[str]
    final_response: str

# --- 노드 함수 정의 ---
def sql_generator_node(state: SqlAgentState):
    print("--- 1. SQL 생성 중 ---")
    prompt = f"""
    Schema: {state['db_schema']}
    History: {state['chat_history']}
    Question: {state['question']}
    SQL Query:
    """
    response = llm_instance.invoke(prompt)
    state['sql_query'] = response.content
    state['validation_error'] = None
    return state

def sql_validator_node(state: SqlAgentState):
    print("--- 2. SQL 검증 중 ---")
    query = state['sql_query'].lower()
    if "drop" in query or "delete" in query:
        state['validation_error'] = "위험한 키워드가 포함되어 있습니다."
    else:
        state['validation_error'] = None
    return state

def sql_executor_node(state: SqlAgentState):
    print("--- 3. SQL 실행 중 ---")
    try:
       result = db_instance.run(state['sql_query'])
       state['execution_result'] = str(result)
    except Exception as e:
       state['execution_result'] = f"실행 오류: {e}"
    return state

def response_synthesizer_node(state: SqlAgentState):
    print("--- 4. 최종 답변 생성 중 ---")
    prompt = f"""
    Question: {state['question']}
    SQL Result: {state['execution_result']}
    Final Answer:
    """
    response = llm_instance.invoke(prompt)
    state['final_response'] = response.content
    return state

# --- 엣지 함수 정의 ---
def should_execute_sql(state: SqlAgentState):
    return "regenerate" if state.get("validation_error") else "execute"

def should_retry_or_respond(state: SqlAgentState):
    return "regenerate" if "오류" in (state.get("execution_result") or "") else "synthesize"

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
        "regenerate": "sql_generator", "execute": "sql_executor"
    })
    graph.add_conditional_edges("sql_executor", should_retry_or_respond, {
        "regenerate": "sql_generator", "synthesize": "response_synthesizer"
    })
    graph.add_edge("response_synthesizer", END)
    
    return graph.compile()

sql_agent_app = create_sql_agent_graph()