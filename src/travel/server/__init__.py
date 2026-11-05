"""도원결의 서버(FastAPI).

docs/ARCHITECTURE.md 2절의 서버 구성과 docs/prompts/delegation_server.md §0 인터페이스를 구현한다.
모델 호출은 llm.py의 경계 뒤에 두고, 검증기(travel.scenarios, travel.pact)는 고치지 않고 부른다.
"""
