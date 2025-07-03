# src/main.py
from health_check.router import app

if __name__ == "__main__":
    # 8080 포트에서 헬스체크 앱 실행
    app.run(host="0.0.0.0", port=33332)