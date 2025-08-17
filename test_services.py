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
        print("💡 API 키 소스는 로그에서 확인하세요 (fallback 사용 시 경고 메시지 표시)")
        
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

async def test_database_service():
    """Database Service 테스트"""
    print("\n🔍 Database Service 테스트 중...")
    try:
        from services.database.database_service import get_database_service
        
        service = await get_database_service()
        print("✅ Database Service 생성 성공")
        
        # 사용 가능한 데이터베이스 목록 조회
        try:
            databases, is_fallback = await service.get_available_databases()
            print(f"🗄️ 사용 가능한 데이터베이스: {len(databases)}개")
            
            if is_fallback:
                print("⚠️ FALLBACK 사용됨: 하드코딩된 데이터베이스 목록")
            else:
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

async def main():
    """메인 테스트 함수"""
    print("🚀 QGenie AI 서비스 테스트 시작\n")
    
    # 각 서비스별 테스트 실행
    await test_llm_provider()
    await test_api_client()
    await test_database_service()
    await test_annotation_service()
    await test_chatbot_service()
    await test_sql_agent()
    
    print("\n✨ 모든 테스트 완료!")

if __name__ == "__main__":
    asyncio.run(main())
