# src/core/providers/llm_provider.py

import os
import asyncio
import logging
from typing import Optional
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from core.clients.api_client import get_api_client

load_dotenv()

logger = logging.getLogger(__name__)

class LLMProvider:
    """LLM 제공자를 관리하는 클래스"""
    
    def __init__(self, model_name: str = "gpt-4o-mini", temperature: float = 0):
        self.model_name = model_name
        self.temperature = temperature
        self._llm: Optional[ChatOpenAI] = None
        self._api_key: Optional[str] = None
        self._api_client = None
        self._api_key_fallback = False  # fallback 사용 여부 추적
    
    async def _load_api_key(self) -> str:
        """백엔드에서 OpenAI API 키를 로드합니다."""
        try:
            if self._api_key is None:
                if self._api_client is None:
                    self._api_client = await get_api_client()
                
                self._api_key = await self._api_client.get_openai_api_key()
                return self._api_key, False  # 백엔드에서 가져옴
            
        except Exception as e:
            # 백엔드 실패 시 환경 변수로 폴백
            logger.warning(f"Failed to fetch API key from backend: {e}, falling back to environment variable")
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OpenAI API 키를 가져올 수 없습니다. 백엔드와 환경 변수 모두 확인해주세요.")
            return api_key, True  # fallback 사용됨
    
    async def get_llm(self) -> ChatOpenAI:
        """LLM 인스턴스를 비동기적으로 반환합니다."""
        if self._llm is None:
            self._llm = await self._create_llm()
        return self._llm
    
    async def _create_llm(self) -> ChatOpenAI:
        """ChatOpenAI 인스턴스를 생성합니다."""
        try:
            # API 키를 비동기적으로 로드
            api_key, is_fallback = await self._load_api_key()
            
            if is_fallback:
                logger.warning("⚠️ 환경 변수에서 OpenAI API 키를 사용합니다 (fallback)")
                self._api_key_fallback = True
            else:
                logger.info("✅ 백엔드에서 OpenAI API 키를 성공적으로 가져왔습니다")
                self._api_key_fallback = False
            
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
