# src/api/v1/schemas/chatbot_schemas.py

from pydantic import BaseModel
from typing import List, Optional

class ChatMessage(BaseModel):
    """대화 기록의 단일 메시지를 나타내는 모델"""
    role: str  # "user" 또는 "assistant"
    content: str

class ChatRequest(BaseModel):
    question: str
    chat_history: Optional[List[ChatMessage]] = None

class ChatResponse(BaseModel):
    answer: str
