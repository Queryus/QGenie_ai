# src/services/chatbot_service.py

from src.agents.sql_agent_graph import sql_agent_app
from src.core.db_manager import schema_instance

class ChatbotService:
    def __init__(self):
        self.db_schema = schema_instance

    def handle_request(self, user_question: str) -> str:
        # 1. 에이전트 그래프에 전달할 초기 상태 구성
        initial_state = {
            "question": user_question,
            "chat_history": [],
            "db_schema": self.db_schema
        }
        
        # 2. 그래프 실행
        final_state = sql_agent_app.invoke(initial_state)
        final_response = final_state['final_response']
        
        return final_response