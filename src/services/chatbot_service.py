# src/services/chatbot_service.py

from agents.sql_agent_graph import sql_agent_app
from api.v1.schemas.chatbot_schemas import ChatMessage # --- 추가된 부분 ---
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage # --- 추가된 부분 ---
from typing import List, Optional # --- 추가된 부분 ---
#from core.db_manager import schema_instance

class ChatbotService():
    # TODO: schema API 요청
    # def __init__(self):
    #     self.db_schema = schema_instance

    def handle_request(self, user_question: str, chat_history: Optional[List[ChatMessage]] = None) -> dict:
        
        langchain_messages: List[BaseMessage] = []
        if chat_history:
            for message in chat_history:
                if message.role == 'user':
                    langchain_messages.append(HumanMessage(content=message.content))
                elif message.role == 'assistant':
                    langchain_messages.append(AIMessage(content=message.content))
        
        initial_state = {
            "question": user_question,
            "chat_history": langchain_messages,
            # "db_schema": self.db_schema,
            "validation_error_count": 0,
            "execution_error_count": 0
        }
        
        final_state = sql_agent_app.invoke(initial_state)
        
        return final_state['final_response']