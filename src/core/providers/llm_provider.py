# src/core/providers/llm_provider.py

import os
import asyncio
import logging
import time
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
        self._api_client = None
        self._initialization_attempted: bool = False
        self._initialization_failed: bool = False
        # 짧은 캐싱을 위한 변수들 (성능 최적화)
        self._cached_api_key: Optional[str] = None
        self._api_key_cache_time: float = 0
        self._api_key_cache_duration: float = 30.0  # 30초 캐싱
    
    async def _load_api_key(self) -> str:
        """백엔드에서 OpenAI API 키를 로드합니다. 짧은 시간 캐싱으로 성능 최적화."""
        try:
            current_time = time.time()
            
            # 캐시된 키가 있고 아직 유효한 경우
            if (self._cached_api_key and 
                current_time - self._api_key_cache_time < self._api_key_cache_duration):
                logger.debug("📋 캐시된 API 키를 사용합니다")
                return self._cached_api_key
            
            # 캐시가 만료되었거나 없는 경우 새로 조회
            if self._api_client is None:
                self._api_client = await get_api_client()
            
            api_key = await self._api_client.get_openai_api_key()
            
            # 캐시 업데이트
            self._cached_api_key = api_key
            self._api_key_cache_time = current_time
            
            logger.debug("🔄 백엔드에서 최신 OpenAI API 키를 조회하고 캐시했습니다")
            return api_key
            
        except Exception as e:
            # 실패 시 캐시 무효화
            self._cached_api_key = None
            self._api_key_cache_time = 0
            logger.error(f"Failed to fetch API key from backend: {e}")
            raise ValueError("백엔드에서 OpenAI API 키를 가져올 수 없습니다. 백엔드 서버를 확인해주세요.")
    
    async def get_llm(self) -> ChatOpenAI:
        """
        ChatOpenAI 인스턴스를 반환합니다.
        매번 최신 API 키로 새로운 인스턴스를 생성합니다.
        """
        # 이전에 초기화를 시도했고 실패했다면 재시도
        if self._initialization_failed:
            logger.info("🔄 LLM 초기화 재시도 중...")
            self._initialization_failed = False
            self._initialization_attempted = False
        
        try:
            self._initialization_attempted = True
            llm = await self._create_llm()
            
            # 연결 복구 감지
            if self._initialization_failed:
                logger.info("🎉 LLMProvider: 백엔드 연결이 복구되어 LLM 초기화가 성공했습니다!")
            
            self._initialization_failed = False
            logger.debug("✅ LLM 인스턴스 생성 성공 (최신 API 키 사용)")
            
            return llm
            
        except Exception as e:
            self._initialization_failed = True
            logger.error(f"❌ LLM 초기화 실패: {e}")
            raise RuntimeError(f"LLM을 초기화할 수 없습니다. 백엔드 서버가 실행 중인지 확인해주세요: {e}")
    
    async def _create_llm(self) -> ChatOpenAI:
        """ChatOpenAI 인스턴스를 생성합니다. 매번 최신 API 키를 사용합니다."""
        try:
            # API 키를 비동기적으로 로드 (매번 최신 키 조회)
            api_key = await self._load_api_key()
            logger.debug("✅ 백엔드에서 최신 OpenAI API 키를 성공적으로 가져왔습니다")
            
            llm = ChatOpenAI(
                model=self.model_name,
                temperature=self.temperature,
                api_key=api_key
            )
            return llm
            
        except Exception as e:
            raise RuntimeError(f"LLM 인스턴스 생성 실패: {e}")
    
    def update_model(self, model_name: str, temperature: float = None):
        """모델 설정을 업데이트합니다. 다음 get_llm() 호출시 새 설정이 적용됩니다."""
        self.model_name = model_name
        if temperature is not None:
            self.temperature = temperature
        logger.info(f"LLM 모델 설정 변경: {model_name}, temperature: {temperature}")
    
    async def refresh_api_key(self):
        """API 키 캐시를 무효화하여 다음 요청에서 최신 키를 조회하도록 합니다."""
        self._cached_api_key = None
        self._api_key_cache_time = 0
        self._initialization_attempted = False
        self._initialization_failed = False
        logger.info("🔄 API 키 캐시 무효화 완료 (다음 요청부터 최신 키 조회)")
    
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
