# src/main.py

import socket
from contextlib import closing
import uvicorn
from fastapi import FastAPI
from api.v1.endpoints import chat, annotator

# def find_free_port():
#     """사용 가능한 비어있는 포트를 찾는 함수"""
#     with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
#         s.bind(('', 0))
#         s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
#         return s.getsockname()[1]

# FastAPI 앱 인스턴스 생성
app = FastAPI(
    title="Qgenie - Agentic SQL Chatbot",
    description="LangGraph로 구현된 사전 스키마를 지원하는 SQL 챗봇",
    version="1.0.0"
)

# '/api/v1' 경로에 chat 라우터 포함
app.include_router(
    chat.router, 
    prefix="/api/v1", 
    tags=["Chatbot"]
)

# '/api/v1' 경로에 annotator 라우터 포함
app.include_router(
    annotator.router, 
    prefix="/api/v1", 
    tags=["Annotator"]
)

@app.get("/")
def health_check():
    """헬스체크 엔드포인트, 서버 상태가 정상이면 'ok' 반환합니다."""
    return {"status": "ok", "message": "Welcome to the QGenie Chatbot AI!"}

if __name__ == "__main__":
    # 1. 비어있는 포트 동적 할당
    # free_port = find_free_port()
    free_port = 35816 # 포트 번호 고정

    # 2. 할당된 포트 번호를 콘솔에 특정 형식으로 출력
    print(f"PYTHON_SERVER_PORT:{free_port}")

    # 3. 할당된 포트로 FastAPI 서버 실행
    uvicorn.run(app, host="127.0.0.1", port=free_port, reload=False)