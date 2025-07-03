# src/health_check/router.py
from flask import Flask, jsonify

app = Flask(__name__)

@app.route("/health")
def health_check():
    """헬스체크 엔드포인트, 서버 상태가 정상이면 'ok'를 반환합니다."""
    return jsonify(status="ok"), 200