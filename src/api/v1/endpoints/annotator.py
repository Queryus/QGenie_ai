
from fastapi import APIRouter, Depends
from core.llm_provider import llm_instance
from services.annotation_service import AnnotationService
from api.v1.schemas.annotator_schemas import AnnotationRequest, AnnotationResponse

router = APIRouter()

# AnnotationService 인스턴스를 싱글턴으로 관리
annotation_service_instance = AnnotationService(llm=llm_instance)

def get_annotation_service():
    """의존성 주입을 통해 AnnotationService 인스턴스를 제공합니다."""
    return annotation_service_instance

@router.post("/annotator", response_model=AnnotationResponse)
async def create_annotations(
    request: AnnotationRequest,
    service: AnnotationService = Depends(get_annotation_service)
):
    """
    DB 스키마 정보를 받아 각 요소에 대한 설명을 비동기적으로 생성하여 반환합니다.
    """
    return await service.generate_for_schema(request)
