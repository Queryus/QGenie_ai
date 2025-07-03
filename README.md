# AI 모델 프로젝트

이 프로젝트는 ...을 위한 AI 모델을 개발합니다.

---

## 🚀 시작하기

### **개발 환경 설정**

이 프로젝트는 가상 환경 사용을 권장합니다.

1.  **저장소 복제**
    ```bash
    git clone https://github.com/AskQL/AI.git
    ```

2.  **가상 환경 생성 및 활성화**
    ```bash
    # 가상 환경 생성 (최초 한 번)
    python3 -m venv .venv

    # 가상 환경 활성화
    source .venv/bin/activate
    ```

3.  **라이브러리 설치**
    프로젝트에 필요한 모든 라이브러리는 `requirements.txt` 파일에 명시되어 있습니다.
    ```bash
    pip install -r requirements.txt
    ```

4.  **실행파일 생성 후 확인**
    ```bash
    # 이전 빌드 결과물 삭제
    rm -rf build dist
    
    # 실행 파일 빌드
    pyinstaller src/main.py --name ai --onefile --noconsole
    
    # 실행 파일 실행
    ./dist/ai
    ```

---

## 📦 배포

`main` 브랜치에 `v`로 시작하는 태그(예: `v1.0.0`, `v1.1.0`)를 푸시하면 GitHub Actions가 자동으로 실행 파일을 빌드하여 **Front** 레포지토리의 실행파일을 업로드합니다.

### **수동 태그 생성 및 푸시 방법**

```bash
# 1. 버전 태그 생성
git tag -a v1.0.0 -m "Release version 1.0.0"

# 2. 원격 저장소에 태그 푸시
git push origin v1.0.0
```

---

## ✅ 헬스체크

이 레포지토리에는 간단한 헬스체크 서버가 포함되어 있습니다. 아래 명령어로 실행 파일을 빌드하여 서버 상태를 확인할 수 있습니다.

```bash
# 헬스체크 실행 파일 빌드
pyinstaller --name health_checker --onefile --noconsole router.py

# 빌드된 파일 실행 (dist 폴더에 생성됨)
./dist/health_checker
```