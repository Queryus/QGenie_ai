# src/api/v1/routers/chat.py

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List

from schemas.api.chat_schemas import ChatRequest, ChatResponse
from services.chat.chatbot_service import ChatbotService, get_chatbot_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def handle_chat_request(
    request: ChatRequest,
    service: ChatbotService = Depends(get_chatbot_service)
) -> ChatResponse:
    """
    사용자의 채팅 요청을 받아 챗봇의 답변을 반환합니다.
    
    Args:
        request: 챗봇 요청 (질문과 채팅 히스토리)
        service: 챗봇 서비스 로직
    
    Returns:
        ChatResponse: 챗봇 응답
        
    Raises:
        HTTPException: 요청 처리 실패 시
    """
    try:
        logger.info(f"Received chat request: {request.question[:100]}...")
        
        final_answer = await service.handle_request(
            user_question=request.question,
            chat_history=request.chat_history
        )
        
        logger.info("Chat request processed successfully")
        
        return ChatResponse(answer=final_answer)
        
    except Exception as e:
        logger.error(f"Chat request failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"채팅 요청 처리 중 오류가 발생했습니다: {e}"
        )

@router.get("/chat/health")
async def chat_health_check(
    service: ChatbotService = Depends(get_chatbot_service)
) -> Dict[str, Any]:
    """
    챗봇 서비스의 상태를 확인합니다.
    
    Returns:
        Dict: 서비스 상태 정보
    """
    try:
        health_status = await service.health_check()
        return health_status
        
    except Exception as e:
        logger.error(f"Chat health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@router.get("/chat/databases")
async def get_available_databases(
    service: ChatbotService = Depends(get_chatbot_service)
) -> Dict[str, List[Dict[str, str]]]:
    """
    사용 가능한 데이터베이스 목록을 반환합니다.
    
    Returns:
        Dict: 데이터베이스 목록
    """
    try:
        databases = await service.get_available_databases()
        return {"databases": databases}
        
    except Exception as e:
        logger.error(f"Failed to get databases: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"데이터베이스 목록 조회 중 오류가 발생했습니다: {e}"
        )
