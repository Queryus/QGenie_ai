# src/api/v1/routers/health.py

from fastapi import APIRouter, Depends
from typing import Dict, Any

from services.chat.chatbot_service import ChatbotService, get_chatbot_service
from services.annotation.annotation_service import AnnotationService, get_annotation_service
from services.database.database_service import DatabaseService, get_database_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/health")
async def root_health_check() -> Dict[str, str]:
    """
    루트 헬스체크 엔드포인트, 서버 상태가 정상이면 'ok' 반환합니다.
    
    Returns:
        Dict: 기본 상태 정보
    """
    return {
        "status": "ok", 
        "message": "Welcome to the QGenie Chatbot AI!",
        "version": "2.0.0"
    }

@router.get("/health/detailed")
async def detailed_health_check(
    chatbot_service: ChatbotService = Depends(get_chatbot_service),
    annotation_service: AnnotationService = Depends(get_annotation_service),
    database_service: DatabaseService = Depends(get_database_service)
) -> Dict[str, Any]:
    """
    전체 시스템의 상세 헬스체크를 수행합니다.
    
    Returns:
        Dict: 상세 상태 정보
    """
    try:
        # 모든 서비스의 헬스체크를 병렬로 실행
        import asyncio
        
        chatbot_health, annotation_health, database_health = await asyncio.gather(
            chatbot_service.health_check(),
            annotation_service.health_check(),
            database_service.health_check(),
            return_exceptions=True
        )
        
        # 각 서비스 상태 처리
        services_status = {
            "chatbot": chatbot_health if not isinstance(chatbot_health, Exception) else {"status": "unhealthy", "error": str(chatbot_health)},
            "annotation": annotation_health if not isinstance(annotation_health, Exception) else {"status": "unhealthy", "error": str(annotation_health)},
            "database": {"status": "healthy" if database_health and not isinstance(database_health, Exception) else "unhealthy"}
        }
        
        # 전체 상태 결정
        all_healthy = all(
            service.get("status") == "healthy" 
            for service in services_status.values()
        )
        
        return {
            "status": "healthy" if all_healthy else "partial",
            "services": services_status,
            "timestamp": __import__("datetime").datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": __import__("datetime").datetime.now().isoformat()
        }
