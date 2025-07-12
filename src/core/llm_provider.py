# src/core/llm_provider.py

import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

def get_llm() -> ChatOpenAI:
    """ 사전 설정된 ChatOpenAI 인스턴스를 생성하고 반환합니다.
    Prams:

    Returns:
        llm: 생성된 ChatOpenAI 객체
    """
    # 환경 변수에서 OpenAI API 키를 가져옵니다.
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
    
    # 기본값으로 gpt-4o-mini 모델 사용
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
        api_key=api_key
    )
    
    return llm

llm_instance = get_llm()