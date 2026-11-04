# 위임 기록: 추천 출력 검증기 (`validate_pact_output`)

대상: `src/travel/pact.py`의 `validate_pact_output(pact_input, raw_output)`. 위임 대상 선정, 골든 케이스, 테스트 하니스 확인 결과는 [강의 5 산출물 문서](강의05_위임대상_골든케이스.md)의 A~C절에 있다.

이 파일은 실제로 붙여 넣은 프롬프트(§1)와 회차별 실행 결과(§2)를 보존하는 참조 문서다. 에이전트가 자동으로 읽지 않으므로 위임할 때 해당 블록을 직접 전달한다.

## §1. 프롬프트 원본

### §1-1. 테스트 하니스 위임

대상 파일: `tests/test_pact_validation_golden.py`. 실제로 붙여 넣은 텍스트 그대로다.

```text
tests/test_pact_validation_golden.py 를 만들어줘.
- 목표: tests/harness/golden_cases.yaml 을 읽어 케이스마다 하나씩 도는 테스트.
  대상 함수는 src/travel/pact.py 의 validate_pact_output(pact_input, raw_output) 이고 {valid, errors[{code, path, detail}]} 를 반환한다.
- 케이스를 코드에 복사하지 말 것. YAML에서 읽고, 케이스 name을 테스트 id로 쓴다.
- 입력 준비: tests/harness/fixtures/pact/<fixture>.json 을 읽어 깊은 복사본에 patch(RFC 6902의 add, remove, replace, 경로는 /input/... 또는 /output/...)를 순서대로 적용한다.
  raw_output 이 있으면 그 문자열을, 없으면 output 을 JSON 문자열로 직렬화해 넘긴다. pact_input 은 문서의 input 이다.
- 검사 항목: 케이스에 있는 키만 검사한다.
  expect_valid → result.valid 와 같음 / must_include_errors → 모두 errors의 code에 있음 / must_not_include_errors → 하나도 없음
- 로더 검사(구현 여부와 무관하게 항상 실행):
  모든 케이스에 name, fixture, expect_valid 가 있음 / expect_valid 가 false면 must_include_errors 가 비어 있지 않음 /
  오류 코드는 YAML 의 error_codes 목록 안에 있음 / 허용하지 않은 키(오타 포함)는 거부 / name 중복 금지 /
  fixture 파일이 있고 patch 가 적용됨.
- validate_pact_output 을 import 할 수 없으면 케이스 테스트는 skip 하되 로더 검사는 실행한다. 그 밖의 예외로 skip 하지 말 것.
- src/, golden_cases.yaml, fixtures/ 는 건드리지 말 것. 테스트 파일만 만든다. 추가 라이브러리는 pytest, PyYAML 만 쓴다.
끝나면 수집된 테스트 목록과 실행 결과를 보여 줘.
```

### §1-2. 기능 위임

대상 파일: `src/travel/pact.py`. 강의 5 D절에서 확정한 뒤 실제로 붙여 넣은 텍스트 그대로 기록한다. (미작성)

## §2. 검증 루프 기록

회차 기록의 단위는 골든 케이스다. 로더 검사 등 보조 검사는 따로 센다.

### §2-1. 테스트 하니스 위임

| 회차 | 결과 | 무엇이 문제였나 | 무엇을 고쳤나 (프롬프트/케이스/테스트 코드) |
|---|---|---|---|
| 1 | 골든 케이스 25개 수집·skip, 로더 검사 5개 통과. 결함 7가지·로더 확인 6가지·YAML 연동 확인 모두 기대대로 검출 | 없음 | 없음 |

- 결함 주입, 로더 확인, 원복 확인의 상세 결과: [강의 5 산출물 문서 C절](강의05_위임대상_골든케이스.md#c-테스트-하니스-위임)
- 보고 전 수정: 에이전트가 결과를 보고하기 전 첫 실행에서, `src/travel/pact.py`가 없을 때 골든 케이스가 skip 대신 실패로 나왔다. `travel` 폴더만 있고 `pact.py`가 없을 때 파이썬이 예상과 다른 종류의 import 오류를 냈기 때문이다. 모듈을 불러오는 방식을 바꿔 해결한 뒤 결과를 보고했다. 사람이 검토하기 전의 수정이라 회차로 세지 않았다.
- 프롬프트에 중단 조건을 두지 않았다. 1회차에 끝났다.
- 기준 커밋: `f99bbb2`(PR #9 병합). 이후 `tests/`의 변경은 사람이 승인한다(AGENTS.md 4절).

### §2-2. 기능 위임

(미실행)
