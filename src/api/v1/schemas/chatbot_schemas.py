# src/api/v1/schemas/chatbot_schemas.py

from pydantic import BaseModel

class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer: str