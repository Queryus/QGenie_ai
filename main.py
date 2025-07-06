# 입력된 질의를 바탕으로 SQL 변환 및 작동 Agent 만들어줘
from dotenv import load_dotenv
import os
import sys
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain.agents import AgentExecutor
from langchain_community.agent_toolkits.sql.base import create_sql_agent

# ================================================================
# 1. 환경 변수 설정
# ================================================================
load_dotenv()
required_env_vars = ["OPENAI_API_KEY", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_HOST", "MYSQL_PORT", "MYSQL_DB_NAME"]
for var in required_env_vars:
    if not os.environ.get(var):
        raise ValueError(f"'{var}' 환경 변수를 .env 파일에 설정해주세요.")

MYSQL_USER = os.environ["MYSQL_USER"]
MYSQL_PASSWORD = os.environ["MYSQL_PASSWORD"]
MYSQL_HOST = os.environ["MYSQL_HOST"]
MYSQL_PORT = os.environ["MYSQL_PORT"]
MYSQL_DB_NAME = os.environ["MYSQL_DB_NAME"]

# ================================================================
# 2. 데이터베이스 및 LLM 설정
# ================================================================
# MySQL 데이터베이스 URI 구성
# mysql+mysqlconnector://<user>:<password>@<host>:<port>/<database_name>
DATABASE_URI = f"mysql+mysqlconnector://{MYSQL_USER}:{MYSQL_PASSWORD}@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB_NAME}"

try:
    db = SQLDatabase.from_uri(DATABASE_URI)
    print(f"Successfully connected to MySQL database: {MYSQL_DB_NAME}")
    # 데이터베이스 스키마 정보 미리 로드 (Agent가 더 잘 이해하도록 돕기 위함)
    # db.get_usable_tables()
    # db.get_table_info() # 이 정보는 Agent가 내부적으로 활용합니다.
except Exception as e:
    print(f"Error connecting to MySQL database: {e}")
    print("Please check your MySQL server is running and connection details are correct.")
    sys.exit(1)

# 언어 모델 설정
# 'gpt-4o'가 가장 강력한 성능을 제공합니다. (OpenAI API 비용 발생)
# 'gpt-3.5-turbo'도 테스트용으로 사용할 수 있습니다.
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# ================================================================
# 3. SQL Database Toolkit 및 Agent 생성
# ================================================================
# SQLDatabaseToolkit은 Agent가 데이터베이스와 상호작용하는 데 필요한 도구들을 제공합니다.
# (예: 테이블 목록 조회, 테이블 스키마 조회, SQL 쿼리 실행)
toolkit = SQLDatabaseToolkit(db=db, llm=llm)

# SQL Agent 생성
# verbose=True: Agent의 추론 과정을 상세히 출력하여 디버깅 및 이해를 돕습니다.
# agent_type="openai-tools": 최신 OpenAI Function Calling API를 기반으로 합니다.
agent_executor = create_sql_agent(
    llm=llm,
    toolkit=toolkit,
    verbose=True,
    agent_type="openai-tools",
)

# ================================================================
# 4. Agent 실행 함수 및 대화 루프
# ================================================================
def run_sql_agent_query(query):
    print(f"\n--- 사용자 질의: {query} ---")
    try:
        response = agent_executor.invoke({"input": query})
        print("\n--- Agent 최종 응답 ---")
        print(response["output"])
    except Exception as e:
        print(f"\n--- 오류 발생: {e} ---")
        print("Agent가 쿼리 실행에 실패했거나 응답을 생성하지 못했습니다.")
        print("상세 로그를 확인하여 문제점을 파악하세요.")

if __name__ == "__main__":
    print("==================================================================")
    print("  LangChain SQL Agent with MySQL Sakila Database Demo")
    print("==================================================================")
    print("자연어 질의를 입력하면 Agent가 SQL 쿼리를 생성하고 실행하여 결과를 반환합니다.")
    print(f"현재 연결된 데이터베이스: {MYSQL_DB_NAME} (MySQL)")
    print("데모를 종료하려면 'exit' 또는 'quit'을 입력하세요.")

    print("\n[추천 질의 예시]")
    print("- 모든 직원의 이름과 고용일을 보여줘.")
    print("- 고객 테이블에 있는 상위 5개 국가를 나열하고 각 국가의 고객 수를 보여줘.")
    print("- 제목이 'ACADEMY DINOSAUR'인 영화의 대여 요금은 얼마야?")
    print("- 가장 최근에 대여된 영화의 제목은 뭐야?")
    print("- 모든 영화 카테고리를 나열해줘.")
    print("- 'PENELOPE'라는 배우가 출연한 영화는 무엇인가요?")
    print("- 스태프들의 총 매출액을 알려줘.")


    while True:
        user_query = input("\nSQL 질의를 입력하세요 (또는 'exit'/'quit'): ")
        if user_query.lower() in ["exit", "quit"]:
            print("데모를 종료합니다.")
            break

        run_sql_agent_query(user_query)