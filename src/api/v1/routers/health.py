# src/api/v1/routers/health.py

from fastapi import APIRouter, Depends
from typing import Dict, Any

from services.chat.chatbot_service import ChatbotService, get_chatbot_service
from services.annotation.annotation_service import AnnotationService, get_annotation_service
from services.database.database_service import DatabaseService, get_database_service
from core.providers.llm_provider import get_llm_provider
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
        
        # ConnectionMonitor 상태 정보 추가
        try:
            from core.monitoring.connection_monitor import get_connection_monitor
            connection_monitor = get_connection_monitor()
            monitor_status = connection_monitor.get_status()
        except Exception:
            monitor_status = {"error": "ConnectionMonitor 상태를 가져올 수 없습니다"}
        
        return {
            "status": "healthy" if all_healthy else "partial",
            "services": services_status,
            "connection_monitor": monitor_status,
            "timestamp": __import__("datetime").datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": __import__("datetime").datetime.now().isoformat()
        }

@router.post("/refresh-api-key")
async def refresh_api_key() -> Dict[str, str]:
    """
    API 키 캐시를 무효화하여 다음 요청에서 최신 키를 조회하도록 합니다.
    
    Returns:
        Dict: 새로고침 결과
    """
    try:
        llm_provider = await get_llm_provider()
        await llm_provider.refresh_api_key()
        
        logger.info("🔄 API 키 캐시가 무효화되었습니다")
        return {
            "status": "success",
            "message": "API 키 캐시가 무효화되었습니다. 다음 요청부터 최신 키를 조회합니다.",
            "timestamp": __import__("datetime").datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"API 키 새로고침 실패: {e}")
        return {
            "status": "error",
            "message": f"API 키 새로고침 중 오류가 발생했습니다: {str(e)}",
            "timestamp": __import__("datetime").datetime.now().isoformat()
        }
