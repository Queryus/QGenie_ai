# src/agents/sql_agent/graph.py

from langgraph.graph import StateGraph, END
from core.providers.llm_provider import LLMProvider
from services.database.database_service import DatabaseService
from .state import SqlAgentState
from .nodes import SqlAgentNodes
from .edges import SqlAgentEdges

class SqlAgentGraph:
    """SQL Agent 그래프를 구성하고 관리하는 클래스"""
    
    def __init__(self, llm_provider: LLMProvider, database_service: DatabaseService):
        self.llm_provider = llm_provider
        self.database_service = database_service
        self.nodes = SqlAgentNodes(llm_provider, database_service)
        self.edges = SqlAgentEdges()
        self._graph = None
    
    def create_graph(self) -> StateGraph:
        """SQL Agent 그래프를 생성하고 구성합니다."""
        if self._graph is not None:
            return self._graph
        
        graph = StateGraph(SqlAgentState)
        
        # 노드 추가
        self._add_nodes(graph)
        
        # 엣지 추가
        self._add_edges(graph)
        
        # 진입점 설정
        graph.set_entry_point("intent_classifier")
        
        # 그래프 컴파일
        self._graph = graph.compile()
        return self._graph
    
    def _add_nodes(self, graph: StateGraph):
        """그래프에 모든 노드를 추가합니다."""
        graph.add_node("intent_classifier", self.nodes.intent_classifier_node)
        graph.add_node("db_classifier", self.nodes.db_classifier_node)
        graph.add_node("unsupported_question", self.nodes.unsupported_question_node)
        graph.add_node("sql_generator", self.nodes.sql_generator_node)
        graph.add_node("sql_validator", self.nodes.sql_validator_node)
        graph.add_node("sql_executor", self.nodes.sql_executor_node)
        graph.add_node("response_synthesizer", self.nodes.response_synthesizer_node)
    
    def _add_edges(self, graph: StateGraph):
        """그래프에 모든 엣지를 추가합니다."""
        # 의도 분류 후 조건부 라우팅
        graph.add_conditional_edges(
            "intent_classifier",
            self.edges.route_after_intent_classification,
            {
                "db_classifier": "db_classifier",
                "unsupported_question": "unsupported_question"
            }
        )
        
        # 지원되지 않는 질문 처리 후 종료
        graph.add_edge("unsupported_question", END)
        
        # DB 분류 후 SQL 생성으로 이동
        graph.add_edge("db_classifier", "sql_generator")
        
        # SQL 생성 후 검증으로 이동
        graph.add_edge("sql_generator", "sql_validator")
        
        # SQL 검증 후 조건부 라우팅
        graph.add_conditional_edges(
            "sql_validator", 
            self.edges.should_execute_sql, 
            {
                "regenerate": "sql_generator",
                "execute": "sql_executor",
                "synthesize_failure": "response_synthesizer"
            }
        )
        
        # SQL 실행 후 조건부 라우팅
        graph.add_conditional_edges(
            "sql_executor", 
            self.edges.should_retry_or_respond, 
            {
                "regenerate": "sql_generator",
                "synthesize_success": "response_synthesizer",
                "synthesize_failure": "response_synthesizer"
            }
        )
        
        # 응답 생성 후 종료
        graph.add_edge("response_synthesizer", END)
    
    async def run(self, initial_state: dict) -> dict:
        """그래프를 실행하고 결과를 반환합니다."""
        try:
            if self._graph is None:
                self.create_graph()
            
            result = await self._graph.ainvoke(initial_state)
            return result
            
        except Exception as e:
            print(f"그래프 실행 중 오류 발생: {e}")
            # 에러 발생 시 기본 응답 반환
            return {
                **initial_state,
                'final_response': f"죄송합니다. 처리 중 오류가 발생했습니다: {e}"
            }
    
    def get_graph_visualization(self) -> bytes:
        """그래프의 시각화 이미지를 반환합니다."""
        if self._graph is None:
            self.create_graph()
        
        try:
            return self._graph.get_graph(xray=True).draw_mermaid_png()
        except Exception as e:
            print(f"그래프 시각화 생성 실패: {e}")
            return None
