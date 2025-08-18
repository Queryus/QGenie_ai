# src/api/v1/routers/annotator.py

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any

from schemas.api.annotator_schemas import AnnotationRequest, AnnotationResponse
from services.annotation.annotation_service import AnnotationService, get_annotation_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/annotator", response_model=AnnotationResponse)
async def create_annotations(
    request: AnnotationRequest,
    service: AnnotationService = Depends(get_annotation_service)
) -> AnnotationResponse:
    """
    DB 스키마 정보를 받아 각 요소에 대한 설명을 비동기적으로 생성하여 반환합니다.
    
    Args:
        request: 어노테이션 요청 (DB 스키마 정보)
        service: 어노테이션 서비스 로직
    
    Returns:
        AnnotationResponse: 어노테이션이 추가된 스키마 정보
        
    Raises:
        HTTPException: 요청 처리 실패 시
    """
    try:
        logger.info(f"Received annotation request for {len(request.databases)} databases")
        
        response = await service.generate_for_schema(request)
        
        logger.info("Annotation request processed successfully")
        
        return response
        
    except Exception as e:
        logger.error(f"Annotation request failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"어노테이션 생성 중 오류가 발생했습니다: {e}"
        )

@router.get("/annotator/health")
async def annotator_health_check(
    service: AnnotationService = Depends(get_annotation_service)
) -> Dict[str, Any]:
    """
    어노테이션 서비스의 상태를 확인합니다.
    
    Returns:
        Dict: 서비스 상태 정보
    """
    try:
        health_status = await service.health_check()
        return health_status
        
    except Exception as e:
        logger.error(f"Annotator health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }
