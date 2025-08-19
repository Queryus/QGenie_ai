# src/main.py

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI

from api.v1.routers import chat, annotator, health

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 라이프사이클 관리"""
    logger.info("QGenie AI Chatbot 시작 중...")
    
    # 시작 시 BE 서버 연결 체크
    try:
        from core.clients.api_client import get_api_client
        api_client = await get_api_client()
        
        # BE 서버 상태 확인
        if await api_client.health_check():
            logger.info("✅ 백엔드 서버 연결 성공")
        else:
            logger.warning("⚠️ 백엔드 서버에 연결할 수 없습니다. 첫 요청 시 연결을 재시도합니다.")
            
    except Exception as e:
        logger.warning(f"⚠️ 백엔드 서버 초기 연결 실패: {e}")
        logger.info("🔄 서비스는 지연 초기화 모드로 시작됩니다.")
    
    try:
        logger.info("애플리케이션 초기화 완료")
        yield
    finally:
        # 종료 시 정리 작업
        logger.info("애플리케이션 종료 중...")
        
        # API 클라이언트 정리
        try:
            from core.clients.api_client import get_api_client
            api_client = await get_api_client()
            await api_client.close()
            logger.info("API 클라이언트 정리 완료")
        except Exception as e:
            logger.error(f"API 클라이언트 정리 실패: {e}")
        
        logger.info("애플리케이션 종료 완료")

# FastAPI 앱 인스턴스 생성
app = FastAPI(
    title="QGenie - Agentic SQL Chatbot",
    description="LangGraph로 구현된 사전 스키마를 지원하는 SQL 챗봇 (리팩터링 버전)",
    version="2.0.0",
    lifespan=lifespan
)

# 라우터 등록
app.include_router(
    health.router,
    prefix="/api/v1",
    tags=["Health"]
)

app.include_router(
    chat.router, 
    prefix="/api/v1", 
    tags=["Chatbot"]
)

app.include_router(
    annotator.router, 
    prefix="/api/v1", 
    tags=["Annotator"]
)

# 루트 엔드포인트
@app.get("/")
async def root():
    """루트 엔드포인트 - 기본 상태 확인"""
    return {
        "status": "ok", 
        "message": "Welcome to the QGenie Chatbot AI! (Refactored)",
        "version": "2.0.0",
        "endpoints": {
            "chat": "/api/v1/chat",
            "annotator": "/api/v1/annotator", 
            "health": "/api/v1/health",
            "detailed_health": "/api/v1/health/detailed"
        }
    }

if __name__ == "__main__":
    import uvicorn
    
    # 포트 번호 고정 (기존 설정 유지)
    free_port = 35816
    
    # 할당된 포트 번호를 콘솔에 특정 형식으로 출력 (Electron 연동을 위해)
    print(f"PYTHON_SERVER_PORT:{free_port}")
    
    # FastAPI 서버 실행
    uvicorn.run(
        app, 
        host="127.0.0.1", 
        port=free_port, 
        reload=False,
        log_level="info"
    )