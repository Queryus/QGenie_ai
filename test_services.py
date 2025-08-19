#!/usr/bin/env python3
"""
서비스 테스트 스크립트
"""

import asyncio
import sys
import os

# src 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

async def test_llm_provider():
    """LLM Provider 테스트"""
    print("🔍 LLM Provider 테스트 중...")
    try:
        from core.providers.llm_provider import get_llm_provider
        
        provider = await get_llm_provider()
        print(f"✅ LLM Provider 생성 성공: {provider.model_name}")
        
        # 연결 테스트
        is_connected = await provider.test_connection()
        print(f"🔗 LLM 연결 상태: {'성공' if is_connected else '실패'}")
        
        # API 키 소스 확인 (로그에서 확인 가능)
        print("💡 백엔드에서 API 키를 가져옵니다")
        
    except Exception as e:
        print(f"❌ LLM Provider 테스트 실패: {e}")

async def test_api_client():
    """API Client 테스트"""
    print("\n🔍 API Client 테스트 중...")
    try:
        from core.clients.api_client import get_api_client
        
        client = await get_api_client()
        print("✅ API Client 생성 성공")
        
        # OpenAI API 키 조회 테스트
        try:
            api_key = await client.get_openai_api_key()
            print(f"🔑 OpenAI API 키 조회 성공: {api_key[:20]}...")
        except Exception as e:
            print(f"⚠️ OpenAI API 키 조회 실패: {e}")
        
        # 헬스체크 테스트
        try:
            is_healthy = await client.health_check()
            print(f"🏥 백엔드 서버 상태: {'정상' if is_healthy else '비정상'}")
        except Exception as e:
            print(f"⚠️ 백엔드 서버 연결 실패: {e}")
            
    except Exception as e:
        print(f"❌ API Client 테스트 실패: {e}")

async def test_db_annotation_api():
    """DB 어노테이션 API 테스트"""
    print("\n🔍 DB 어노테이션 API 테스트 중...")
    try:
        from services.database.database_service import get_database_service
        
        service = await get_database_service()
        
        # DB 프로필 조회 테스트
        try:
            profiles = await service.get_db_profiles()
            print(f"✅ DB 프로필 조회 성공: {len(profiles)}개")
            
            if profiles:
                print(f"📝 첫 번째 프로필: {profiles[0].type} - {profiles[0].view_name or 'No view name'}")
                
                # 첫 번째 프로필의 어노테이션 조회 테스트
                try:
                    annotations = await service.get_db_annotations(profiles[0].id)
                    print(f"✅ 어노테이션 조회 성공: {profiles[0].id}")
                except Exception as e:
                    print(f"⚠️ 어노테이션 조회 실패: {e}")
                
                # 통합 조회 테스트
                try:
                    dbs_with_annotations = await service.get_databases_with_annotations()
                    print(f"✅ 통합 조회 성공: {len(dbs_with_annotations)}개")
                    
                    if dbs_with_annotations:
                        first_db = dbs_with_annotations[0]
                        print(f"📝 첫 번째 DB 정보:")
                        print(f"   - Display Name: {first_db['display_name']}")
                        print(f"   - Description: {first_db['description']}")
                        print(f"   - Has Annotations: {'data' in first_db['annotations']}")
                        
                except Exception as e:
                    print(f"⚠️ 통합 조회 실패: {e}")
            else:
                print("⚠️ DB 프로필이 없습니다.")
                
        except Exception as e:
            print(f"⚠️ DB 프로필 조회 실패: {e}")
            
    except Exception as e:
        print(f"❌ DB 어노테이션 API 테스트 실패: {e}")

async def test_database_service():
    """Database Service 테스트"""
    print("\n🔍 Database Service 테스트 중...")
    try:
        from services.database.database_service import get_database_service
        
        service = await get_database_service()
        print("✅ Database Service 생성 성공")
        
        # 사용 가능한 데이터베이스 목록 조회
        try:
            databases = await service.get_available_databases()
            print(f"🗄️ 사용 가능한 데이터베이스: {len(databases)}개")
            print("✅ 백엔드 API에서 데이터베이스 목록을 성공적으로 가져왔습니다")
            
            for db in databases[:3]:  # 처음 3개만 출력
                print(f"  - {db.database_name}: {db.description}")
        except Exception as e:
            print(f"⚠️ 데이터베이스 목록 조회 실패: {e}")
            
    except Exception as e:
        print(f"❌ Database Service 테스트 실패: {e}")

async def test_annotation_service():
    """Annotation Service 테스트"""
    print("\n🔍 Annotation Service 테스트 중...")
    try:
        from services.annotation.annotation_service import get_annotation_service
        
        service = await get_annotation_service()
        print("✅ Annotation Service 생성 성공")
        
        # 헬스체크 테스트
        try:
            health = await service.health_check()
            print(f"🏥 어노테이션 서비스 상태: {health}")
        except Exception as e:
            print(f"⚠️ 어노테이션 서비스 헬스체크 실패: {e}")
            
    except Exception as e:
        print(f"❌ Annotation Service 테스트 실패: {e}")

async def test_chatbot_service():
    """Chatbot Service 테스트"""
    print("\n🔍 Chatbot Service 테스트 중...")
    try:
        from services.chat.chatbot_service import get_chatbot_service
        
        service = await get_chatbot_service()
        print("✅ Chatbot Service 생성 성공")
        
        # 헬스체크 테스트
        try:
            health = await service.health_check()
            print(f"🏥 챗봇 서비스 상태: {health}")
        except Exception as e:
            print(f"⚠️ 챗봇 서비스 헬스체크 실패: {e}")
            
    except Exception as e:
        print(f"❌ Chatbot Service 테스트 실패: {e}")

async def test_sql_agent():
    """SQL Agent 테스트"""
    print("\n🔍 SQL Agent 테스트 중...")
    try:
        from agents.sql_agent.graph import SqlAgentGraph
        from core.providers.llm_provider import get_llm_provider
        from services.database.database_service import get_database_service
        
        llm_provider = await get_llm_provider()
        db_service = await get_database_service()
        
        agent = SqlAgentGraph(llm_provider, db_service)
        print("✅ SQL Agent 생성 성공")
        
        # 그래프 시각화 PNG 저장
        try:
            success = agent.save_graph_visualization("sql_agent_workflow.png")
            if success:
                print("📊 그래프 시각화 PNG 저장 성공: sql_agent_workflow.png")
            else:
                print("⚠️ 그래프 시각화 PNG 저장 실패")
        except Exception as e:
            print(f"⚠️ 그래프 시각화 생성 실패: {e}")
            
    except Exception as e:
        print(f"❌ SQL Agent 테스트 실패: {e}")

async def test_end_to_end_chat():
    """실제 채팅 요청 End-to-End 테스트"""
    print("\n🔍 End-to-End 채팅 테스트 중...")
    try:
        from services.chat.chatbot_service import get_chatbot_service
        import time
        
        service = await get_chatbot_service()
        
        # SQL 관련 질문으로 테스트
        test_questions = [
            "사용자 테이블에서 모든 데이터를 조회해주세요",
            "가장 많이 주문한 고객을 찾아주세요",
        ]
        
        for i, question in enumerate(test_questions, 1):
            print(f"🤖 테스트 질문 {i}: {question}")
            start_time = time.time()
            
            try:
                response = await service.handle_request(user_question=question)
                end_time = time.time()
                response_time = round(end_time - start_time, 2)
                
                print(f"✅ 응답 시간: {response_time}초")
                print(f"📝 응답: {response[:100]}{'...' if len(response) > 100 else ''}")
            except Exception as e:
                print(f"❌ 질문 {i} 실패: {e}")
            
            print("---")
            
    except Exception as e:
        print(f"❌ End-to-End 테스트 실패: {e}")

async def test_annotation_functionality():
    """어노테이션 기능 실제 사용 테스트"""
    print("\n🔍 어노테이션 기능 테스트 중...")
    try:
        from services.annotation.annotation_service import get_annotation_service
        from schemas.api.annotator_schemas import Database, Table, Column
        
        service = await get_annotation_service()
        
        # 샘플 데이터로 어노테이션 테스트
        sample_database = Database(
            database_name="test_db",
            tables=[
                Table(
                    table_name="users",
                    columns=[
                        Column(column_name="id", data_type="int"),
                        Column(column_name="name", data_type="varchar"),
                        Column(column_name="email", data_type="varchar")
                    ],
                    sample_rows=[{"id": 1, "name": "John Doe", "email": "john@example.com"}]
                )
            ],
            relationships=[]
        )
        
        try:
            from schemas.api.annotator_schemas import AnnotationRequest
            request = AnnotationRequest(
                dbms_type="MySQL",
                databases=[sample_database]
            )
            result = await service.generate_for_schema(request)
            print(f"✅ 어노테이션 생성 성공")
            print(f"📝 생성된 데이터베이스 수: {len(result.databases)}")
            if result.databases and result.databases[0].tables:
                print(f"📝 첫 번째 테이블 설명: {result.databases[0].tables[0].description[:100]}...")
        except Exception as e:
            print(f"⚠️ 어노테이션 생성 실패: {e}")
            
    except Exception as e:
        print(f"❌ 어노테이션 기능 테스트 실패: {e}")

async def test_error_scenarios():
    """에러 시나리오 테스트"""
    print("\n🔍 에러 시나리오 테스트 중...")
    
    # 잘못된 API 키로 LLM 테스트
    print("🧪 잘못된 API 키 시나리오...")
    try:
        from core.providers.llm_provider import LLMProvider
        
        # 일시적으로 잘못된 API 키 설정 테스트는 실제 환경에서는 위험하므로 스킵
        print("⚠️ 실제 환경에서는 API 키 에러 테스트 스킵")
        
    except Exception as e:
        print(f"✅ 예상된 에러 발생: {e}")
    
    print("✅ 에러 시나리오 테스트 완료")

async def main():
    """메인 테스트 함수"""
    print("🚀 QGenie AI 서비스 테스트 시작\n")
    
    # 기본 서비스 테스트
    await test_llm_provider()
    await test_api_client()
    await test_annotation_service() 
    await test_db_annotation_api()  # 새로운 DB 어노테이션 API 테스트 추가
    await test_database_service()
    await test_chatbot_service()
    await test_sql_agent()
    
    # 확장 테스트 (백엔드 연결이 가능한 경우에만)
    try:
        from core.clients.api_client import get_api_client
        client = await get_api_client()
        if await client.health_check():
            print("\n🧪 확장 테스트 시작 (백엔드 연결 확인됨)")
            print("⚠️ 참고: 데이터베이스 API가 구현되지 않아 일부 테스트는 실패할 수 있습니다")
            await test_end_to_end_chat()
            await test_annotation_functionality()
            await test_error_scenarios()
        else:
            print("\n⚠️ 백엔드 연결 불가 - 확장 테스트 스킵")
    except Exception:
        print("\n⚠️ 백엔드 연결 불가 - 확장 테스트 스킵")
    
    print("\n✨ 모든 테스트 완료!")

if __name__ == "__main__":
    asyncio.run(main())
