---
description: 추천 출력 검증기 골든 케이스를 실행해 판정 결과를 점검한다 (진단만, 수정 없음)
disable-model-invocation: true
---
`python -m pytest tests/test_pact_validation_golden.py -v -rs`를 실행하고(python 명령이 없으면 python3), tests/harness/golden_cases.yaml 및 src/travel/pact.py와 결과를 대조해줘.
명령을 실행하지 못했다면 실행하지 못한 이유를 보고하고 통과로 추정하지 말 것.
어떤 소스, 테스트, 케이스, fixture 또는 설정 파일도 수정하지 말 것.
케이스별 통과 또는 실패, 실패한 단언문(expect_valid, must_include_errors, must_not_include_errors 중 무엇인지)과 판정 근거, skip 또는 xfail 사유를 표로 보고해.
실패가 있으면 수정할 위치와 이유만 제안해. 실제 구현 수정은 별도의 위임으로 수행한다.
