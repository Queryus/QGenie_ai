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
    
    # ConnectionMonitor 초기화
    from core.monitoring.connection_monitor import get_connection_monitor
    connection_monitor = get_connection_monitor()
    
    # 시작 시 BE 서버 연결 체크
    try:
        from core.clients.api_client import get_api_client
        api_client = await get_api_client()
        
        # BE 서버 상태 확인
        if await api_client.health_check():
            logger.info("✅ 백엔드 서버 연결 성공")
            connection_monitor.mark_initial_success()
        else:
            logger.warning("⚠️ 백엔드 서버에 연결할 수 없습니다. 첫 요청 시 연결을 재시도합니다.")
            connection_monitor.mark_initial_failure()
            
    except Exception as e:
        logger.warning(f"⚠️ 백엔드 서버 초기 연결 실패: {e}")
        logger.info("🔄 서비스는 지연 초기화 모드로 시작됩니다.")
        connection_monitor.mark_initial_failure()
    
    try:
        # 선택적으로 백그라운드 모니터링 시작 (환경변수로 제어 가능)
        import os
        if os.getenv("ENABLE_CONNECTION_MONITORING", "false").lower() == "true":
            # 초기 연결이 실패한 경우에만 모니터링 시작
            if connection_monitor._initial_connection_failed:
                monitoring_interval = int(os.getenv("MONITORING_INTERVAL", "10"))
                logger.info(f"🔍 백엔드 연결 모니터링 활성화 (간격: {monitoring_interval}초)")
                await connection_monitor.start_monitoring(api_client, monitoring_interval)
            else:
                logger.info("✅ 초기 연결이 성공했으므로 모니터링을 시작하지 않습니다.")
        
        logger.info("애플리케이션 초기화 완료")
        yield
    finally:
        # 종료 시 정리 작업
        logger.info("애플리케이션 종료 중...")
        
        # 모니터링 중지
        try:
            await connection_monitor.stop_monitoring()
        except Exception as e:
            logger.error(f"연결 모니터링 중지 실패: {e}")
        
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
    """루트 엔드포인트 - 기본 상태 확인 (백엔드 연결 확인 포함)"""
    try:
        # 백엔드 연결 상태 확인
        from services.database.database_service import get_database_service
        database_service = await get_database_service()
        backend_healthy = await database_service.health_check()
        
        overall_status = "healthy" if backend_healthy else "degraded"
        
        response = {
            "status": overall_status,
            "message": "Welcome to the QGenie Chatbot AI! (Refactored)",
            "version": "2.0.0",
            "backend_connection": "connected" if backend_healthy else "disconnected",
            "endpoints": {
                "chat": "/api/v1/chat",
                "annotator": "/api/v1/annotator", 
                "health": "/api/v1/health",
                "detailed_health": "/api/v1/health/detailed",
                "refresh_api_key": "/api/v1/health/refresh-api-key"
            },
            "timestamp": __import__("datetime").datetime.now().isoformat()
        }
        
        if not backend_healthy:
            response["warning"] = "백엔드 서버 연결이 불안정합니다. 일부 기능이 제한될 수 있습니다."
        
        return response
        
    except Exception as e:
        logger.error(f"Root endpoint health check failed: {e}")
        return {
            "status": "degraded",
            "message": "Welcome to the QGenie Chatbot AI! (Refactored)",
            "version": "2.0.0",
            "backend_connection": "error",
            "endpoints": {
                "chat": "/api/v1/chat",
                "annotator": "/api/v1/annotator", 
                "health": "/api/v1/health",
                "detailed_health": "/api/v1/health/detailed",
                "refresh_api_key": "/api/v1/health/refresh-api-key"
            },
            "warning": "백엔드 연결 상태를 확인할 수 없습니다.",
            "timestamp": __import__("datetime").datetime.now().isoformat()
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