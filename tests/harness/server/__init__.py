"""서버 계약 테스트 도우미.

tests/harness/server_cases.yaml의 케이스를 실행할 때 쓰는 재생 클라이언트, 가짜 푸시 발송기,
가짜 대기 함수와 현재 시각 함수, 추천·문항 출력 도우미, 공개 금지 검사, 테스트 DB 준비, API 호출 도우미를 둔다.
travel.server는 필요할 때만 import한다. 서버가 없어도 이 패키지는 import할 수 있다.
"""
