# src/main.py
import socket
from contextlib import closing
from health_check.router import app

def find_free_port():
    """사용 가능한 비어있는 포트를 찾는 함수"""
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(('', 0))
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        return s.getsockname()[1]

if __name__ == "__main__":
    # 1. 비어있는 포트 동적 할당
    free_port = find_free_port()

    # 2. 할당된 포트 번호를 콘솔에 특정 형식으로 출력
    print(f"PYTHON_SERVER_PORT:{free_port}")

    # 3. 할당된 포트로 Flask 서버 실행
    app.run(host="127.0.0.1", port=free_port, debug=False, use_reloader=False)