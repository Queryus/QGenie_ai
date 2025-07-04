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

## 📦 배포 방법

~~~markdown
태그 예시)  
v1.2.3  
1 : 큰 버전(기존에 없던 새로운 도메인 추가)  
2 : 중간 버전(기존 도메인에 새로운 기능 추가)  
3 : 패치 버전(버그 수정, 코드 개선 등)  
~~~

이 프로젝트는 GitHub Actions를 통해 실행 파일 빌드 및 배포가 자동화되어 있습니다.
GitHub에서 새로운 태그를 발행하면 파이프라인이 자동으로 실행됩니다.

~~~markdown
1. 모든 기능 개발과 테스트가 완료된 코드를 main 브랜치에 병합(Merge)합니다.
2. AskQL/AI 저장소의 Releases 탭으로 이동하여 Draft a new release 버튼을 클릭합니다.
3. Choose a tag 항목에서 v1.0.0과 같이 새로운 버전 태그를 입력하고 생성합니다.
4. (가장 중요 ⭐) Target 드롭다운 메뉴에서 반드시 main 브랜치를 선택합니다. 
5. 릴리즈 노트를 작성하고 Publish release 버튼을 클릭합니다. 
6. Target 드롭다운 메뉴에서 반드시 main 브랜치를 선택합니다. 
7. 릴리즈 노트를 작성하고 Publish release 버튼을 클릭합니다.
~~~

버튼을 클릭하는 즉시, 아래의 경고 사항에 설명된 자동 배포 프로세스가 시작됩니다.

🛑 경고: 릴리즈 발행은 되돌릴 수 없습니다
GitHub에서 새로운 릴리즈를 발행하면, 자동으로 프로덕션 배포가 시작됩니다.

이 과정은 중간에 멈출 수 없으며, main 브랜치의 현재 상태가 즉시 Front 리포지토리의 develop 브랜치에 반영됩니다.
잘못된 릴리즈는 서비스에 직접적인 영향을 줄 수 있으니, 반드시 팀의 승인을 받고 신중하게 진행해 주십시오.

---

## ✅ 실행파일로 헬스체크 테스트 하기

이 레포지토리에는 간단한 헬스체크 서버가 포함되어 있습니다. 아래 명령어로 실행 파일을 빌드하여 서버 상태를 확인할 수 있습니다.

```bash
# 실행 파일 빌드
pyinstaller src/main.py --name ai --onefile --noconsole

# 빌드된 파일 실행 (dist 폴더에 생성됨)
./dist/ai

curl http://localhost:33332/health
```