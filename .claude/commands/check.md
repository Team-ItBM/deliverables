---
description: 문서 점검과 테스트를 실행하고 완료 기준의 충족 여부를 보고한다 (수정 없음)
disable-model-invocation: true
---
파일을 수정하지 말고 다음 검사를 순서대로 실행해줘. 첫 검사가 실패해도 실행 가능한 다음 검사는 수행해.
1. `git diff --check`
2. `python -m pytest -q -rs` (python 명령이 없으면 python3)
3. `git status --short`
명령별 종료 상태와 passed / failed / skipped / xfailed를 구분해 보고해.
골든 케이스와 로더 검사 수를 구분하고, 필수 골든 케이스의 skip이나 xfail은 완료로 처리하지 말 것.
tests/ 아래 파일(테스트 코드, golden_cases.yaml, fixture)에 변경이나 새 파일이 있으면 따로 표시해.
실패 시 원인과 수정 제안만 제시해. 최종 수용 여부는 사람이 정한다.
