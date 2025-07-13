# src/api/v1/endpoints/chat.py

from fastapi import APIRouter, Depends
from api.v1.schemas import ChatRequest, ChatResponse
from services.chatbot_service import ChatbotService

router = APIRouter()

def get_chatbot_service():
    return ChatbotService()

@router.post("/chat", response_model=ChatResponse)
def handle_chat_request(
    request: ChatRequest,
    service: ChatbotService = Depends(get_chatbot_service)
):
    """
    사용자의 채팅 요청을 받아 챗봇의 답변을 반환합니다.
    Args:
        request: 챗봇 요청
        service: 챗봇 서비스 로직
    
    Returns:
        ChatRespone: 챗봇 응답
    """
    final_answer = service.handle_request(request.question)
    return ChatResponse(answer=final_answer)