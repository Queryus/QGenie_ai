# src/services/chat/chatbot_service.py

import asyncio
from typing import List, Optional, Dict, Any
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from schemas.api.chat_schemas import ChatMessage
from agents.sql_agent.graph import SqlAgentGraph
from core.providers.llm_provider import LLMProvider, get_llm_provider
from services.database.database_service import DatabaseService, get_database_service
import logging

logger = logging.getLogger(__name__)

class ChatbotService:
    """챗봇 관련 비즈니스 로직을 담당하는 서비스 클래스"""
    
    def __init__(
        self, 
        llm_provider: LLMProvider = None,
        database_service: DatabaseService = None
    ):
        self.llm_provider = llm_provider
        self.database_service = database_service
        self._sql_agent_graph: Optional[SqlAgentGraph] = None
    
    async def _initialize_dependencies(self):
        """필요한 의존성들을 초기화합니다."""
        if self.llm_provider is None:
            self.llm_provider = await get_llm_provider()
        
        if self.database_service is None:
            self.database_service = await get_database_service()
        
        if self._sql_agent_graph is None:
            self._sql_agent_graph = SqlAgentGraph(
                self.llm_provider, 
                self.database_service
            )
    
    async def handle_request(
        self, 
        user_question: str, 
        chat_history: Optional[List[ChatMessage]] = None
    ) -> str:
        """채팅 요청을 처리하고 응답을 반환합니다."""
        try:
            # 의존성 초기화
            await self._initialize_dependencies()
            
            # 채팅 히스토리를 LangChain 메시지로 변환
            langchain_messages = await self._convert_chat_history(chat_history)
            
            # 초기 상태 구성
            initial_state = {
                "question": user_question,
                "chat_history": langchain_messages,
                "validation_error_count": 0,
                "execution_error_count": 0
            }
            
            # SQL Agent 그래프 실행
            final_state = await self._sql_agent_graph.run(initial_state)
            
            return final_state.get('final_response', "죄송합니다. 응답을 생성할 수 없습니다.")
            
        except Exception as e:
            logger.error(f"Chat request handling failed: {e}")
            # 에러 상황에서는 예외를 다시 발생시켜 라우터에서 HTTP 에러로 처리되도록 함
            raise e
    
    async def _convert_chat_history(
        self, 
        chat_history: Optional[List[ChatMessage]]
    ) -> List[BaseMessage]:
        """채팅 히스토리를 LangChain 메시지 형식으로 변환합니다."""
        langchain_messages: List[BaseMessage] = []
        
        if chat_history:
            for message in chat_history:
                try:
                    if message.role == 'u':
                        langchain_messages.append(HumanMessage(content=message.content))
                    elif message.role == 'a':
                        langchain_messages.append(AIMessage(content=message.content))
                except Exception as e:
                    logger.warning(f"Failed to convert message: {e}")
                    continue
        
        return langchain_messages
    
    async def health_check(self) -> Dict[str, Any]:
        """챗봇 서비스의 상태를 확인합니다."""
        try:
            await self._initialize_dependencies()
            
            # LLM 연결 테스트
            llm_status = await self.llm_provider.test_connection()
            
            # 데이터베이스 서비스 상태 확인
            db_status = await self.database_service.health_check()
            
            overall_status = llm_status and db_status
            
            return {
                "status": "healthy" if overall_status else "unhealthy",
                "llm_provider": "connected" if llm_status else "disconnected",
                "database_service": "connected" if db_status else "disconnected"
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e)
            }
    
    async def get_available_databases(self) -> List[Dict[str, str]]:
        """사용 가능한 데이터베이스 목록을 반환합니다."""
        try:
            await self._initialize_dependencies()
            databases = await self.database_service.get_available_databases()
            
            return [
                {
                    "name": db.database_name,
                    "description": db.description,
                    "connection": db.connection_name
                }
                for db in databases
            ]
            
        except Exception as e:
            logger.error(f"Failed to get available databases: {e}")
            return []

# 싱글톤 인스턴스
_chatbot_service = ChatbotService()

async def get_chatbot_service() -> ChatbotService:
    """Chatbot Service 인스턴스를 반환합니다."""
    return _chatbot_service
