# 위임 기록: 문항 원본 조회 도구 (`get_scenario_template`)

대상: `src/travel/tools/scenario_tools.py`의 `get_scenario_template(template_id)`. 도구 표와 계약 조건은 [아키텍처 설계서](../ARCHITECTURE.md#3-도구-목록) 3절에 있다. 이 문서는 강의 6 도구 코드 생성 절차 4단계(도구 계약 테스트)의 위임 프롬프트, 결함 주입 결과, 수용 기록을 보존한다. 5단계(도구 코드 위임)와 6단계(도구 코드 수용)도 기록한다(§1-2, §2-5, §3).

이 파일은 에이전트가 자동으로 읽지 않는다. 위임할 때 해당 블록을 직접 전달한다.

## §1. 프롬프트 원본

### §1-1. 도구 계약 테스트 위임 (2026-11-04)

실제로 붙여 넣은 텍스트 그대로다.

```text
프롬프트 1: 도구 계약 테스트 확정

도원결의 저장소(브랜치 implementation)에서 강의 6 "도구 계약 테스트" 단계를 진행해줘. 목표는 tests/test_tools.py를 확정해 사람이 수용할 수 있게 만드는 것이야. 도구 코드(get_scenario_template)는 이번 범위가 아니야.

## 먼저 읽을 것 (순서대로, 해당 절만)
1. AGENTS.md 전체 (절대 규칙, 금지 사항, 완료의 정의, 7절 명령)
2. references/course/00_README.md: 사람이 정하는 것과 AI가 초안을 쓰는 것의 구분, 저장소 표준 구조
3. references/course/06/강의06_아키텍처_RAG_도구_작성지침.md: "B. 도구 목록"의 "도구 코드 생성 절차" 표(1~6단계)와 계약 조건, "제출 전 자가 점검"
4. references/course/05/강의05_위임검증_골든테스트_작성지침.md: "C. 테스트 하니스 위임"(결함 주입 검사, 확인 후 수정 금지), "제출 전 자가 점검"
5. docs/ARCHITECTURE.md: 2절 구성 요소, 3절 도구 표와 "도구 계약 조건", 5절 멈춤 조건, 6절 실패 처리, 변경 영향
6. docs/prompts/강의05_위임대상_골든케이스.md C절: 이 저장소에서 결함 주입을 기록한 방식(임시 검증기를 .local-work/에 두는 방식)
7. src/travel/data/scenario_pool.json (pool v3), src/travel/prompts/prepare_scenarios.md의 "필드와 함수 인자" 표
8. tests/test_pact_golden.py: 기존 테스트의 스타일과, 대상 함수가 없을 때 skip하는 방식
9. TODO.md 6강 항목

## 할 일
1. ARCHITECTURE 3절 "도구 계약 조건" 5개를 테스트 단언문으로 옮긴 tests/test_tools.py를 작성해.
   - 반환 타입: 성공은 ScenarioTemplate(pool 원본 항목과 필드·값이 같음), 실패는 ToolError
   - 호출 전후 pool 데이터와 pool_version·해시가 바뀌지 않음
   - 없는 template_id는 not_found와 retryable=false를 반환하고, 예외로 멈추지 않음
   - 빈 문자열이나 문자열이 아닌 인자는 validation을 반환
   - 도구 정의의 설명 문장이 3절 표와 같음
2. 연결 함수 src/travel/pool.py의 lookup_template이 없으면 ARCHITECTURE 2·3절에 맞게 최소로 구현해. 강의 6 절차상 연결 함수가 도구 코드보다 먼저 있어야 해. 도구 코드가 없을 때 테스트는 test_pact_golden.py처럼 skip돼야 해.
3. 결함 주입: .local-work/에 임시 도구 구현을 두고 결함마다 기대한 테스트가 실패하는지 확인한 뒤, 주입 전 상태로 되돌려. 결함 예시: 원본 변형, 예외 발생, retryable=true, 설명 문장 불일치, 원본과 다른 필드. 결과를 표로 정리해 docs/prompts/에 강의 6 도구 위임 기록 파일로 남겨. 경로는 ARCHITECTURE와 강의 지침의 경로를 따르고, 이름이 애매하면 나에게 물어봐.
4. 여기서 멈추고 보고해. 사람이 테스트를 수용하기 전에는 get_scenario_template을 구현하지 마.

## 지킬 것
- 3절 도구 표(시그니처, 설명, 부작용)와 계약 조건은 사람이 정한 기준이야. 바꿔야 할 것 같으면 고치지 말고 근거와 함께 제안만 해.
- 기존 테스트, 골든 케이스, fixture는 바꾸지 마. skip이나 xfail로 기준을 줄이지 마.
- 수행하지 않은 검증을 통과로 보고하지 마. 구조 검사와 의미 검토를 구분해서 보고해.
- 문서는 최소로 고쳐. 바꾼 문장은 kar-plain과 humanizer 기준(평서문, 대시 없음, 과장 없음)에 맞춰.
- 끝나면 python -m pytest tests/ -q -rs, git diff --check, git status --short를 실행하고 결과를 그대로 보고해.

## 보고 형식
바꾼 파일과 이유, 테스트 결과, 결함 주입 표, 사람이 수용할 때 확인할 항목, 미확인 항목.
```

이 기록 파일의 이름은 위임 중에 사람이 정했다(`delegation_<대상>.md` 형식).

### §1-2. 도구 코드 위임 (작성 2026-11-04, 실행 2026-11-04)

5단계 위임 프롬프트다. 2026-11-04에 이 블록을 고치지 않고 넣었다(§2-5).

판정 기준은 기준 커밋 `c027358`의 `tests/test_tools.py`다. 파라미터 스키마는 ARCHITECTURE 3절에 정했고(2026-11-04, 전민규 승인), 테스트는 이를 검사하지 않아 §3의 9번에서 코드로 확인한다.

```text
프롬프트 2: get_scenario_template 도구 코드 위임

도원결의 저장소(브랜치 implementation)에서 강의 6 도구 코드 생성 절차 5단계를 진행해줘. 목표는 tests/test_tools.py(기준 커밋 c027358)를 고치지 않고 통과하는 get_scenario_template 도구 코드를 만드는 것이야.

## 먼저 읽을 것 (해당 절만)
1. AGENTS.md 전체
2. docs/ARCHITECTURE.md 3절(도구 표, 연결 함수, 출력 계약, 도구 계약 조건), 6절의 "도구 인자 오류" 행, 7절 마지막 문장
3. references/course/06/강의06_아키텍처_RAG_도구_작성지침.md "B. 도구 목록"의 도구 코드 생성 절차 5·6단계
4. tests/test_tools.py 전체. 읽기만 한다
5. src/travel/pool.py
6. docs/prompts/delegation_scenario_tools.md §2-1의 "테스트가 도구 코드에 요구하는 인터페이스"와 §2-4

## 만들 것
src/travel/tools/scenario_tools.py 하나만 만든다.
- get_scenario_template(template_id): 인자는 template_id 하나다.
  1. template_id가 문자열이 아니거나 빈 문자열이면 ToolError {error_code: "validation", retryable: false, message}를 반환한다. bool도 문자열이 아니다.
  2. 그 밖에는 pool.lookup_template(template_id)를 호출하고 반환값을 그대로 돌려준다. 호출할 때 모듈 속성으로 찾아야 한다(from travel import pool 후 pool.lookup_template(...)). from travel.pool import lookup_template로 묶지 않는다.
  3. lookup_template이 KeyError를 내면 ToolError {error_code: "not_found", retryable: false, message}를 반환한다.
  4. 그 밖의 예외는 잡지 않는다. 공백 제거, 대소문자 변환 같은 인자 정규화는 하지 않는다.
- TOOL_DEFINITION: name, description, parameters를 가진 dict.
  - name은 "get_scenario_template"
  - description은 ARCHITECTURE 3절 표의 설명 칸 문장을 한 글자도 바꾸지 않고 쓴다. 함수 docstring에도 같은 문장을 둔다.
  - parameters는 JSON Schema object로, ARCHITECTURE 3절대로 template_id(type string, required) 하나만 두고 additionalProperties는 false로 한다. enum과 strict 모드는 넣지 않는다.
- ToolError의 필드는 error_code, retryable, message 세 개뿐이다. message는 비어 있지 않은 한국어 문장이다.

## 지킬 것
- tests/, tests/harness/, src/travel/pool.py, src/travel/data/, docs/는 고치지 않는다. 테스트가 틀렸다고 판단되면 고치지 말고 근거와 함께 보고한다.
- 도구 표의 시그니처·설명·부작용과 계약 조건은 사람이 정한 기준이다. 바꿔야 할 것 같으면 제안만 한다.
- 표에 없는 도구, 로깅, 호출 상한, 모델 호출, 프롬프트 수정은 이번 범위가 아니다.
- pool 문자열과 인자 값은 데이터로만 다룬다(AGENTS 절대 규칙 4).
- 새 라이브러리를 추가하지 않는다.
- 커밋하지 않는다.

## 완료 조건
- python -m pytest tests/test_tools.py -q -rs 결과가 21 passed, skipped 0, xfailed 0
- python -m pytest tests/ -q -rs 결과가 56 passed, skipped 0, xfailed 0
- git diff c027358 -- tests/ 출력 없음, git status --short --untracked-files=all tests 출력 없음
- git diff --check 출력 없음

## 멈출 때
- 테스트를 고치지 않으면 통과할 수 없다고 판단될 때
- pool.py를 고쳐야 할 때
- 같은 실패를 세 번 고쳐도 통과하지 못할 때
멈추면 그때까지의 변경과 실패 출력을 그대로 보고한다.

## 보고 형식
만든 파일, 위 완료 조건 명령의 출력 원문, ARCHITECTURE 3절 표와 코드의 시그니처·설명 대조, 테스트가 검사하지 않는 부분(parameters 스키마, message 문구), 미확인 항목.
```

## §2. 회차별 결과

### §2-1. 1회차 (2026-11-04): 테스트 작성과 결함 주입

**만든 파일**

- `src/travel/pool.py`: `load_pool()`과 `lookup_template(template_id)`. pool 파일을 한 번 읽어 캐시하고, 조회는 항목의 깊은 복사본을 돌려준다. 없는 ID는 `KeyError`, 문자열이 아닌 인자는 `TypeError`를 낸다. 목록(`ScenarioIndexEntry`) 생성은 범위 밖이라 두지 않았다.
- `tests/test_tools.py`: 계약 조건 5개를 단언문으로 옮겼다. pool 원본은 pool 파일에서 직접 읽고 `travel.pool`을 거치지 않는다. 도구 표의 시그니처·설명·부작용은 테스트 안 상수로 고정했다(§2-2).

**테스트가 도구 코드에 요구하는 인터페이스**

설계서 3절에 없는 형식을 테스트가 정한 부분이다. 수용할 때 사람이 확인한다.

- 모듈 `travel.tools.scenario_tools`에 함수 `get_scenario_template`과 매핑 `TOOL_DEFINITION`(`name`, `description`)을 둔다. 모듈이나 함수가 없으면 도구 테스트를 skip한다. 그 밖의 import 오류는 skip하지 않는다.
- `ScenarioTemplate`과 `ToolError`는 JSON으로 돌려줄 수 있는 dict다. `ToolError`의 필드는 정확히 `error_code`, `retryable`, `message`다.
- 설명 문장은 테스트 상수 `TOOL_DESCRIPTION`과 비교한다. 이 상수가 설계서 3절 표와 같은지는 `test_architecture_tool_row`가 따로 검사한다.

**계약 조건과 테스트 대응**

| 계약 조건 | 테스트 | 검사 내용 |
|---|---|---|
| 1. 반환 타입 | `test_signature_has_single_template_id_argument`, `test_success_returns_pool_original` | 인자가 `template_id` 하나. pool 50개 ID 전부에서 반환값이 원본 항목과 필드·값 모두 같음 |
| 2. 읽기 불변 | `test_calls_do_not_change_pool` | 성공·실패 호출 전후 파일 해시, 파일과 메모리의 `pool_version`, 메모리 pool 해시가 같음. 반환값을 고쳐도 pool이 바뀌지 않음 |
| 3. 없는 ID | `test_unknown_id_returns_not_found` 6개 | 없는 ID, 대문자, 끝 공백, 선택지 ID, `decision_key`, 지시문이 섞인 값에서 예외 없이 `not_found`, `retryable=false` |
| 4. 잘못된 인자 | `test_invalid_argument_returns_validation` 8개 | 빈 문자열, None, int, float, bool, list, dict, bytes에서 예외 없이 `validation`, `retryable=false`(3절 출력 계약) |
| 5. 설명 문장 | `test_tool_definition_matches_architecture` | `TOOL_DEFINITION`의 이름이 같고 설명이 `TOOL_DESCRIPTION`과 같음 |
| (항상 실행) | `test_pool_file_structure`, `test_architecture_tool_row` | pool 항목 필드가 `ScenarioTemplate` 필드와 같고 ID가 고유함. 3절 표의 시그니처·설명·부작용 칸이 테스트 상수와 같음 |

**(1) 수집과 실행 확인**

```bash
python -m pytest tests/test_tools.py --collect-only -q
python -m pytest tests/test_tools.py -q -rs
```

수집 노드 20개(항상 실행 2개, 도구 검사 18개). 도구 미구현 상태에서 passed 2, skipped 18, failed 0이다. skip 사유는 18개 모두 "get_scenario_template 없음: travel.tools 모듈을 찾을 수 없다"이다.

**(2) 결함 주입 및 검출 확인**

임시 구현 `.local-work/fault_injection/tool_fault_stub.py`에 결함 11가지를 모드(`d0`~`d10`)로 넣었다. `.local-work/`는 `.gitignore` 대상이다. 테스트 파일은 고정하고 아래처럼 실행했다.

```bash
mkdir src/travel/tools
cp .local-work/fault_injection/tool_fault_stub.py src/travel/tools/scenario_tools.py
TOOL_FAULT=d0 python -m pytest tests/test_tools.py -q -rs
rm -r src/travel/tools
```

결함별 기대는 임시 구현을 작성하면서 정했고, 실행 전에 문서로 따로 남기지는 않았다. 실제 결과는 실패한 노드 이름과 단언문 메시지로 확인했다.

| # | 주입한 결함 | 실패해야 할 테스트와 단언문 | 실제 결과 |
|---|---|---|---|
| d0 | 통과 가능 확인: 결함 없는 임시 구현 | 없음 | 20 passed, skip 0. 기대와 일치 |
| d1 | 원본 변형: 호출마다 캐시한 pool의 `pool_version`을 1 올림 | `test_calls_do_not_change_pool`의 메모리 `pool_version` 단언 | 1 failed. "메모리 pool의 pool_version이 바뀌었다". 기대와 일치 |
| d2 | 복사본 대신 캐시 객체를 그대로 반환 | `test_calls_do_not_change_pool`의 메모리 해시 단언(반환값 수정이 pool에 반영됨) | 1 failed. "메모리 pool 해시가 바뀌었다". 기대와 일치 |
| d3 | 예외 발생: 없는 ID에서 `KeyError`를 그대로 냄 | `test_unknown_id_returns_not_found` 6개, 실패 호출을 포함한 `test_calls_do_not_change_pool` | 7 failed. 모두 "ToolError를 반환하지 않고 예외로 멈췄다: KeyError". 기대와 일치 |
| d4 | `not_found`를 `retryable=true`로 반환 | `test_unknown_id_returns_not_found` 6개의 retryable 단언 | 6 failed. "not_found는 retryable=false여야 한다". 기대와 일치 |
| d5 | 설명 문장 불일치: 둘째 문장 삭제 | `test_tool_definition_matches_architecture` | 1 failed. "설명 문장이 ARCHITECTURE 3절 표와 다르다". 기대와 일치 |
| d6 | 원본과 다른 필드: `topic` 누락 | `test_success_returns_pool_original`의 필드 단언 | 1 failed. "필드가 다르다 누락=['topic']". 기대와 일치 |
| d7 | 원본과 다른 값: `paid_activity`의 장면에서 금액 변경 | `test_success_returns_pool_original`의 값 단언 | 1 failed. "paid_activity: pool 원본과 값이 다르다 ['scene']". 기대와 일치 |
| d8 | 인자 검증 생략 | `test_invalid_argument_returns_validation` 8개, 실패 호출을 포함한 `test_calls_do_not_change_pool` | 9 failed. 빈 문자열은 "error_code='not_found'", 나머지는 "예외로 멈췄다: TypeError". 기대와 일치 |
| d9 | `ToolError`에 `message` 없음 | 오류를 검사하는 14개(없는 ID 6, 잘못된 인자 8) | 14 failed. "ToolError 필드가 다르다". 기대와 일치 |
| d10 | 인자 이름을 `scenario_id`로 바꿈 | `test_signature_has_single_template_id_argument` | 1 failed. "인자는 template_id 하나여야 한다: ['scenario_id']". 기대와 일치 |

모든 실패는 수집 오류나 무관한 예외가 아니라 위 단언문에서 났다. 결함 d3과 d8에서 `test_calls_do_not_change_pool`이 함께 실패한 것은 이 테스트가 실패 호출도 하기 때문이다.

**(3) 원복 및 재실행 확인**

- 아래 기록은 1회차 테스트 파일 기준이다. 2회차 결과는 §2-2에 있다.
- 체크포인트: 커밋 없이 진행했다. 기준은 HEAD `0478e5a`와 사람이 작업 중이던 미커밋 변경(추적 파일 7개)이다. 주입 전후에 `git status --short`, `git diff | shasum`(`f42ff67…`), `git diff --stat`을 기록해 비교했고 같았다. 새 파일 두 개는 주입 중에 고치지 않았으며 원복 후 SHA-256은 `tests/test_tools.py` `3eaf93cc…`, `src/travel/pool.py` `a24f0d0d…`이다.
- 원복: `src/travel/tools/`를 지웠다. 다시 실행해 passed 2, skipped 18로 미구현 상태로 돌아간 것을 확인했다. 기능 수용이 아니다.

**`lookup_template` 확인**

도구 계약 테스트는 연결 함수의 정확성을 검사하지 않는다. 별도 일회성 명령으로 50개 ID 조회 결과가 파일 원본과 같고, 반환값을 고쳐도 다음 조회가 바뀌지 않으며, 없는 ID·빈 문자열은 `KeyError`, None·int는 `TypeError`를 내는 것을 확인했다. 이 확인은 저장소의 테스트로 남기지 않았다.

**사람이 수용할 때 확인할 항목**

- 위 "테스트가 도구 코드에 요구하는 인터페이스"를 받아들일지
- 끝 공백이 붙은 ID(`"paid_activity "`)를 `not_found`로 보는 판정. 설계서는 공백 정규화를 정하지 않았다
- 반환값 수정이 pool에 반영되지 않아야 한다는 검사를 계약 조건 2에 포함한 해석
- 수용 후에는 `AGENTS.md` 4절에 따라 `tests/test_tools.py` 변경을 사람이 승인한다

### §2-2. 2회차 (2026-11-04): 도구 표 기준값을 테스트 상수로 고정

**걸린 것**: 1회차 테스트는 실행할 때마다 `docs/ARCHITECTURE.md` 3절 표를 읽어 설명 문장의 기대값으로 썼다. 사람이 리뷰에서 이 방식을 지적했다.

**무엇이 문제였나**: 표를 고치면 테스트 파일은 그대로인데 기대값이 바뀐다. 강의 6 수용 단계의 "`git diff`로 테스트 미변경 확인"에 이 변경이 드러나지 않는다. 표 서식이 바뀌어도 계약 위반이 아닌 파싱 실패로 테스트가 깨진다.

**무엇을 고쳤나(테스트 코드)**: 시그니처·설명·부작용을 상수 `TOOL_SIGNATURE`, `TOOL_DESCRIPTION`, `TOOL_SIDE_EFFECT`로 고정했다. `test_tool_definition_matches_architecture`는 도구 정의를 상수와 비교한다. `test_architecture_tool_row`는 표의 칸이 상수와 같은지 검사한다. 표를 고치면 이 검사가 실패하므로, 사람이 승인하고 상수를 함께 고쳐야 하며 그 변경은 `git diff tests/`에 나타난다. 수정 후 SHA-256은 `tests/test_tools.py` `1220c876…`이다.

**재검사 결과**: 같은 임시 구현으로 d0~d10을 다시 실행했다. 실패 개수와 단언문 메시지가 §2-1 표와 모두 같다(d0 20 passed, d5는 "설명 문장이 ARCHITECTURE 3절 표와 다르다" 1 failed). 결함 하나를 추가했다.

| # | 주입한 결함 | 실패해야 할 테스트와 단언문 | 실제 결과 |
|---|---|---|---|
| e1 | 도구는 d0 그대로 두고 설계서 3절 설명 칸만 바꿈("목록에 없는 ID는 조회하지 않는다." → "목록에 없는 ID도 조회한다.") | `test_architecture_tool_row`의 설명 단언. `test_tool_definition_matches_architecture`는 통과 | 1 failed, 19 passed. "표의 설명이 테스트 기준값과 다르다". 기대와 일치 |

e1은 `docs/ARCHITECTURE.md`를 `.local-work/fault_injection/`에 백업하고 고친 뒤, 백업으로 되돌렸다. 되돌린 파일의 SHA-256이 주입 전과 같음을 `shasum -c`로 확인했다. 주입 전후 `git status --short`, `git diff | shasum`, `git diff --stat`도 같았다. `src/travel/tools/`를 지운 뒤 다시 실행해 passed 2, skipped 18을 확인했다.

### §2-3. 수용 (2026-11-04)

전민규가 2회차 테스트를 수용했다. 기준 커밋은 `9b57749`(`tests/test_tools.py`)이고, 연결 함수는 `588cee7`(`src/travel/pool.py`)에 있다. 이후 `tests/test_tools.py` 변경은 `AGENTS.md` 4절에 따라 사람이 승인한다. 도구 코드 수용 때 `git diff 9b57749 -- tests/`로 테스트 미변경을 확인한다.

수용에 포함된 해석은 §2-1 "사람이 수용할 때 확인할 항목"의 세 가지와 `validation`을 `retryable=false`로 보는 판정이다.

남은 결정은 다음과 같다.

- 3절 표에 도구 정의의 파라미터 스키마(`template_id`: string, 필수)를 둘지. 정하기 전까지 테스트는 함수 시그니처만 검사한다.
- `lookup_template` 단독 테스트를 둘지. 지금은 일회성 확인만 했다.

### §2-4. 3회차 (2026-11-04): 연결 함수 호출 검사 추가

**걸린 것**: 수용 후 `lookup_template` 단독 테스트를 검토하다 나온 빈틈이다. 도구가 실제로 `lookup_template`을 호출하는지는 테스트가 보지 않아 6단계 코드 리뷰에만 맡겨져 있었다. 도구가 pool을 따로 읽어도 50개 원본 일치 검사는 통과한다.

**무엇을 고치나(테스트 코드, 전민규 승인)**: `test_tool_delegates_to_lookup_template`를 추가한다.

- `travel.pool.lookup_template`을 대리 함수로 바꾼다. 대리 함수는 `paid_activity` 원본에서 `title`과 `scene`만 표시용 값으로 바꾼 항목을 돌려준다.
- 도구를 `paid_activity`로 한 번 호출해 대리 함수가 그 ID로 정확히 한 번 호출됐는지, 도구가 대리 함수의 반환값을 그대로 돌려주는지 검사한다.
- 도구 코드는 `pool.lookup_template(...)`처럼 호출할 때 모듈 속성을 찾아야 한다. `from travel.pool import lookup_template`로 import 시점에 묶으면 이 검사가 실패한다. 테스트가 도구 코드에 요구하는 인터페이스가 하나 늘어난다.
- `lookup_template`의 오류 동작(`KeyError`, `TypeError`)은 이 검사에 넣지 않는다. 사람이 정한 기준이 없기 때문이다.

**결함별 기대(실행 전 기록)**: 같은 임시 구현에 결함 두 개를 추가한다. 수집 노드는 21개가 된다.

| # | 주입하는 결함 | 기대 결과 |
|---|---|---|
| d0 | 결함 없음 | 21 passed |
| d1, d3, d4, d5, d7, d8, d9, d10 | §2-1과 같음 | §2-1과 같은 실패. 새 검사는 통과(d7은 대리 함수의 장면에 바꿀 금액이 없음) |
| d2 | 캐시 객체를 그대로 반환(`lookup_template`을 거치지 않음) | 불변 검사와 새 검사, 2 failed |
| d6 | `topic` 누락 | 원본 일치 검사와 새 검사(반환값이 대리 함수 결과와 다름), 2 failed |
| d11 | pool 파일을 직접 읽어 같은 결과를 반환 | 새 검사만, 1 failed |
| d12 | `from travel.pool import lookup_template`로 묶어 호출 | 새 검사만, 1 failed |
| e1 | 설계서 3절 설명 칸 변경 | `test_architecture_tool_row`만, 1 failed |

**실제 결과**: 기대와 모두 같다. 변경 후 SHA-256은 `tests/test_tools.py` `50818c55…`이다.

| # | 실제 결과 |
|---|---|
| d0 | 21 passed |
| d1, d3, d4, d5, d7, d8, d9, d10 | §2-1과 같은 테스트가 같은 개수로 실패했다. 새 검사는 통과했다 |
| d2 | 2 failed. "lookup_template을 paid_activity로 한 번 호출해야 한다: []", "메모리 pool 해시가 바뀌었다" |
| d6 | 2 failed. "필드가 다르다 누락=['topic']", "도구가 lookup_template의 반환값을 그대로 돌려주지 않았다" |
| d11 | 1 failed. "lookup_template을 paid_activity로 한 번 호출해야 한다: []" |
| d12 | 1 failed. 메시지는 d11과 같다 |
| e1 | 1 failed(`test_architecture_tool_row`). "표의 설명이 테스트 기준값과 다르다" |

원복은 §2-2와 같은 방법으로 확인했다. 설계서 SHA-256이 주입 전과 같고, 주입 전후 `git status --short`, `git diff | shasum`, `git diff --stat`이 같다. 원복 후 passed 2, skipped 19다.

**새 기준 커밋**: 전민규가 변경안을 승인했고 결과가 실행 전 기대와 모두 같아 `c027358`을 새 기준으로 한다. 도구 코드 수용 때 `git diff c027358 -- tests/`로 테스트 미변경을 확인한다. 도구가 `lookup_template`을 호출하는지는 이제 테스트가 검사하므로 6단계 코드 리뷰 항목에서 뺀다. `lookup_template` 단독 테스트는 목록 생성을 구현할 때 그 계약과 함께 정한다.

### §2-5. 4회차 (2026-11-04): 도구 코드 위임과 수용

**위임**: §1-2 프롬프트를 고치지 않고 새 세션에 넣었다. 에이전트가 `src/travel/tools/scenario_tools.py` 하나를 만들었고, 멈춤 조건에 걸리지 않았다. 처음 실행에서 21 passed였고 테스트를 고친 회차는 없다.

**확인**: §3 체크리스트 1~13을 모두 통과했다. 2~13은 위임한 에이전트가 수용 요청을 받고 명령을 다시 실행하고 코드를 읽어 확인했다. 결과는 §3 결과 칸에 있다. 같은 에이전트가 코드를 쓰고 확인했으므로 독립 리뷰는 아니다. 그 뒤 3~5·7은 전민규가 명령을 다시 실행해 같은 결과를 확인했고, 6은 도구 코드 커밋의 변경 파일로 대신 확인했다.

**수용**: 전민규가 수용했다. 도구 코드 커밋은 `01da8ef`(`scenario_tools.py` SHA-256 `c675e5b7…`)이고, 위임 직전 커밋은 `2fb0b31`, 테스트 기준 커밋은 `c027358`(`tests/test_tools.py` SHA-256 `50818c55…`, 변경 없음)이다.

미확인 항목은 두 가지다. `TOOL_DEFINITION` 형식이 Sol API 도구 정의와 맞는지, 모델이 실제로 이 도구를 호출하는지는 도구 스파이크(TODO 6강)에서 `enum`·strict와 함께 확인한다.

## §3. 6단계 수용 체크리스트 (작성 2026-11-04, 사용 2026-11-04)

§1-2 위임이 끝난 뒤 사람이 확인한다. 에이전트가 보고한 출력을 그대로 믿지 않고 명령을 직접 다시 실행한다. 결과 칸은 실제로 확인한 내용으로만 채우고, 확인하지 못한 항목은 비워 둔 채 이유를 적는다. 꺾쇠 안의 값은 실제 커밋으로 바꾼다.

### 실행 조건

| # | 확인할 것 | 방법 | 통과 조건 | 결과 |
|---|---|---|---|---|
| 1 | 위임을 새 세션에서 실행했는가 | 실행 기록 확인 | 테스트를 작성한 세션과 다른 세션 | 통과. 위임 세션은 §1-2 프롬프트로 시작했고 테스트 작성 이력이 없다. 에이전트 쪽 대화 기준이며, 전민규가 이 한계를 알고 수용했다 |
| 2 | 실제로 넣은 프롬프트가 §1-2와 같은가 | §1-2와 대조 | 같거나, 다르면 §1-2를 실제 텍스트로 바꾸고 이유를 §2에 적음 | 통과. 넣은 텍스트와 §1-2 블록을 `diff`로 비교해 차이가 없다 |

### 명령으로 확인 (구조 검사)

| # | 확인할 것 | 명령 | 통과 조건 | 결과 |
|---|---|---|---|---|
| 3 | 도구 계약 테스트 | `python -m pytest tests/test_tools.py -q -rs` | 21 passed, skipped 0, xfailed 0 | 통과. `21 passed`, skip·xfail 요약 없음 전민규가 2026-11-04에 다시 실행해 같은 결과를 확인했다. |
| 4 | 전체 테스트 | `python -m pytest tests/ -q -rs` | 56 passed, skipped 0, xfailed 0 | 통과. `56 passed`, skip·xfail 요약 없음 전민규가 2026-11-04에 다시 실행해 같은 결과를 확인했다. |
| 5 | 테스트 미변경 | `git diff c027358 -- tests/`, `git status --short --untracked-files=all tests` | 둘 다 출력 없음 | 통과. 둘 다 출력 없음 전민규가 2026-11-04에 다시 실행해 같은 결과를 확인했다. |
| 6 | 변경 범위 | `git status --short --untracked-files=all`, `git diff <위임 직전 커밋> --stat` | 새 파일은 `src/travel/tools/scenario_tools.py` 하나이고 추적 파일 변경 없음 | 통과. 위임 직전 커밋 `2fb0b31` 기준 `--stat` 출력 없음, 미추적은 `src/travel/tools/scenario_tools.py` 하나 |
| 7 | 공백 오류 | `git diff --check` | 출력 없음 | 통과. 출력 없음. 미추적 새 파일은 `git diff --no-index --check /dev/null <파일>`로 따로 보고 출력 없음 전민규가 2026-11-04에 다시 실행해 같은 결과를 확인했다. |

### 코드를 읽고 확인 (테스트가 검사하지 않는 부분)

| # | 확인할 것 | 근거 | 통과 조건 | 결과 |
|---|---|---|---|---|
| 8 | docstring의 설명 문장 | 강의 6 5단계, §1-2 | 함수 docstring이 ARCHITECTURE 3절 표의 설명 칸과 같음. 테스트는 `TOOL_DEFINITION`의 설명만 비교한다 | 통과. 3절 표 설명 칸을 읽어 docstring·`TOOL_DEFINITION.description`과 비교해 둘 다 같다 |
| 9 | 파라미터 스키마 | ARCHITECTURE 3절 | `TOOL_DEFINITION.parameters`에 `template_id`(string, 필수) 하나만 있고 `additionalProperties`가 false이며 `enum`, strict 모드가 없음 | 통과. `{type: object, properties: {template_id: {type: string}}, required: [template_id], additionalProperties: false}`. 최상위 키는 `name`, `description`, `parameters` |
| 10 | 예외 범위 | ARCHITECTURE 6절, §1-2 | `KeyError`만 `not_found`로 바꾸고, `except Exception`처럼 다른 예외를 감추는 코드가 없음 | 통과. `except`는 `except KeyError:` 한 곳뿐이다 |
| 11 | 인자 정규화 | §2-3 수용 해석 | `strip`, `lower` 같은 변환이 없음 | 통과. 문자열 변환 호출 없음 |
| 12 | 부작용 | ARCHITECTURE 3절 부작용 "없음(읽기)" | 파일 쓰기, 전역 상태 변경, 네트워크 호출, 로그 출력이 없음. 테스트는 pool 불변만 본다 | 통과. import는 `travel.pool`뿐이고 `open`, `print`, `logging`, `global`, 네트워크 호출이 없다 |
| 13 | `message` 문구 | AGENTS 절대 규칙 4 | 비어 있지 않은 한국어 문장. 인자 원문을 넣었다면 그대로 둘지 사람이 판단하고 결과 칸에 적음 | 통과. validation "template_id는 비어 있지 않은 문자열이어야 합니다.", not_found "문항 목록에 없는 template_id입니다. 목록 안에서 다시 고르세요." 인자 원문을 넣지 않는다 |

### 수용 후 기록

| # | 할 일 | 위치 | 결과 |
|---|---|---|---|
| 14 | 회차 결과, 수용자, 기준 커밋을 적는다 | 이 문서 §2 | 완료(§2-5) |
| 15 | `scenario_tools.py` 행을 구현됨으로, `test_tools.py` 행의 skip 문구를 실제 결과로 고친다 | ARCHITECTURE 2절 | 완료 |
| 16 | 도구 계약 테스트의 확인 결과를 21개 통과로 고친다 | AGENTS.md 7절 | 완료 |
| 17 | 도구 구현·수용 항목을 완료로 표시한다 | TODO 6강 | 완료 |
| 18 | 도구 코드 커밋과 문서 커밋을 나눠 남긴다 | git | 완료. 도구 코드 `01da8ef`, 문서는 이 기록을 담은 다음 커밋 |

1~13 중 하나라도 통과하지 못하면 수용하지 않는다. 테스트를 고치지 않고 위임 프롬프트를 보완해 다시 위임하며, 그 회차를 §2에 적는다.
