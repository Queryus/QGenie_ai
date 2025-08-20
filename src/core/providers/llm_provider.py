# src/core/providers/llm_provider.py

import os
import asyncio
import logging
from typing import Optional
from langchain_openai import ChatOpenAI
from core.clients.api_client import get_api_client

logger = logging.getLogger(__name__)

class LLMProvider:
    """
    LLM 제공자를 관리하는 클래스
    지연 초기화를 지원하여 BE 서버가 늦게 시작되어도 작동합니다.
    """
    
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0):
        self.model_name = model_name
        self.temperature = temperature
        self._llm: Optional[ChatOpenAI] = None
        self._api_key: Optional[str] = None
        self._api_client = None
        self._initialization_attempted: bool = False
        self._initialization_failed: bool = False
    
    async def _load_api_key(self) -> str:
        """백엔드에서 OpenAI API 키를 로드합니다."""
        try:
            if self._api_key is None:
                if self._api_client is None:
                    self._api_client = await get_api_client()
                
                self._api_key = await self._api_client.get_openai_api_key()
                return self._api_key
            
        except Exception as e:
            logger.error(f"Failed to fetch API key from backend: {e}")
            raise ValueError("백엔드에서 OpenAI API 키를 가져올 수 없습니다. 백엔드 서버를 확인해주세요.")
    
    async def get_llm(self) -> ChatOpenAI:
        """
        ChatOpenAI 인스턴스를 반환합니다.
        지연 초기화를 통해 BE 서버 연결이 실패해도 재시도합니다.
        """
        if self._llm is None:
            # 이전에 초기화를 시도했고 실패했다면 재시도
            if self._initialization_failed:
                logger.info("🔄 LLM 초기화 재시도 중...")
                self._initialization_failed = False
                self._initialization_attempted = False
            
            try:
                self._initialization_attempted = True
                self._llm = await self._create_llm()
                self._initialization_failed = False
                logger.info("✅ LLM 초기화 성공")
                
            except Exception as e:
                self._initialization_failed = True
                logger.error(f"❌ LLM 초기화 실패: {e}")
                raise RuntimeError(f"LLM을 초기화할 수 없습니다. 백엔드 서버가 실행 중인지 확인해주세요: {e}")

        return self._llm
    
    async def _create_llm(self) -> ChatOpenAI:
        """ChatOpenAI 인스턴스를 생성합니다."""
        try:
            # API 키를 비동기적으로 로드
            api_key = await self._load_api_key()
            logger.info("✅ 백엔드에서 OpenAI API 키를 성공적으로 가져왔습니다")
            
            llm = ChatOpenAI(
                model=self.model_name,
                temperature=self.temperature,
                api_key=api_key
            )
            return llm
            
        except Exception as e:
            raise RuntimeError(f"LLM 인스턴스 생성 실패: {e}")
    
    def update_model(self, model_name: str, temperature: float = None):
        """모델 설정을 업데이트하고 인스턴스를 재생성합니다."""
        self.model_name = model_name
        if temperature is not None:
            self.temperature = temperature
        self._llm = None  # 다음 호출 시 재생성되도록 함
    
    async def refresh_api_key(self):
        """API 키를 새로고침합니다."""
        self._api_key = None
        self._llm = None  # LLM 인스턴스도 재생성
        self._initialization_attempted = False
        self._initialization_failed = False
        logger.info("API key refreshed")
    
    async def test_connection(self) -> bool:
        """LLM 연결을 테스트합니다."""
        try:
            llm = await self.get_llm()
            test_response = await llm.ainvoke("테스트")
            return test_response is not None
            
        except Exception as e:
            print(f"LLM 연결 테스트 실패: {e}")
            return False

# 싱글톤 인스턴스
_llm_provider = LLMProvider()

async def get_llm_provider() -> LLMProvider:
    """LLM Provider 인스턴스를 반환합니다."""
    return _llm_provider
