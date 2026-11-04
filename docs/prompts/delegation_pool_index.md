# 위임 기록: 문항 목록 생성 (`pool.py`)

대상: `src/travel/pool.py`의 목록(`ScenarioIndexEntry`) 생성 함수와 이미 구현한 `lookup_template`. 목록의 필드는 [아키텍처 설계서](../ARCHITECTURE.md#3-도구-목록) 3절에 있다. 이 문서는 도구 스파이크 전에 목록 생성의 계약 테스트를 정하는 위임 프롬프트, 결함 주입 결과, 수용 기록을 보존한다. 진행 방식은 [도구 위임 기록](delegation_scenario_tools.md)과 같다.

이 파일은 에이전트가 자동으로 읽지 않는다. 위임할 때 해당 블록을 직접 전달한다.

## §0. 사람이 정한 인터페이스 (2026-11-04 확정)

설계서는 목록의 필드만 정했다. 아래 기본안을 전민규가 2026-11-04에 그대로 확정했다. 바꾸면 §1-1 블록도 함께 고친다.

| # | 항목 | 확정안 | 근거 |
|---|---|---|---|
| 1 | 함수 이름·시그니처 | `build_scenario_index() -> list[ScenarioIndexEntry]`, 인자 없음 | 설계서에 이름 없음. 문항 프롬프트 함수 표에도 없다 |
| 2 | 반환 형식 | `ScenarioIndexEntry` dict의 list. `pool_version`은 넣지 않는다 | 3절은 항목 필드만 정했다. 버전은 `config/llm.yaml`과 실행 기록에서 관리한다(5절) |
| 3 | 순서 | pool 파일의 `scenario_pool` 순서를 그대로 둔다. 정렬하지 않으므로 동점 처리가 필요 없다 | AGENTS 5절(정렬은 같은 입력에서 같아야 하고 동점 처리를 명시) |
| 4 | 필터 | 거르지 않는다. 50개 전부를 넣는다 | 4절 "pool은 50개라 목록 전체를 입력". 당일·숙박 적합성 필터는 5절 스파이크 뒤 검토 |
| 5 | `lookup_template` 단독 계약 | 복사본 반환, 없는 ID는 `KeyError`, 비문자열은 `TypeError` | 현재 docstring. §2-3에서 목록 생성 때 함께 정하기로 했다 |

## §1. 프롬프트 원본

### §1-1. 목록 생성 계약 테스트 위임 (작성 2026-11-04, 미실행)

이 블록을 그대로 붙여 넣는다. 고쳐서 넣었다면 실제 텍스트로 바꾸고 이유를 §2에 적는다.

```text
프롬프트 3: pool 목록 생성 계약 테스트 확정

도원결의 저장소(/Users/mingyu/orca/workspaces/deliverables/implementation, 브랜치 implementation)에서 pool 목록(ScenarioIndexEntry) 생성의 계약 테스트를 확정해줘. 강의 6 도구 코드 생성 절차 4단계와 같은 방식이야. 목표는 tests/test_pool.py를 확정해 사람이 수용할 수 있게 만드는 것이고, 목록 생성 함수 구현은 이번 범위가 아니야.

## 먼저 읽을 것 (해당 절만)
1. AGENTS.md 전체
2. docs/ARCHITECTURE.md 2절 pool.py 행, 3절 ScenarioTemplate·ScenarioIndexEntry 문단, 4절 "문항 선정" 문단, 5절 "검증 필요(목록의 적합성 정보)", 7절
3. references/course/05/강의05_위임검증_골든테스트_작성지침.md "C. 테스트 하니스 위임"(결함 주입 검사, 확인 후 수정 금지)
4. docs/prompts/delegation_pool_index.md §0 (사람이 정한 인터페이스)
5. docs/prompts/delegation_scenario_tools.md §2-1·§2-4: 결함 주입 기록 방식과 결과 표 형식
6. src/travel/pool.py, src/travel/data/scenario_pool.json
7. tests/test_tools.py: 스타일, pool 원본을 파일에서 직접 읽는 방식, 대상 함수가 없을 때 skip하는 방식

## 할 일
1. tests/test_pool.py를 새로 만들어. 대상 함수는 §0의 build_scenario_index()이고, travel.pool에 없으면 목록 검사만 skip해. 그 밖의 import 오류는 skip하지 마.
2. 목록 계약 조건을 단언문으로 옮겨. 기대값은 travel.pool을 거치지 않고 pool 파일에서 직접 읽어.
   - 각 항목의 필드가 정확히 template_id, title, purpose, decision_key다. scene, question, options, core_constraints, topic이 없다
   - 값이 pool 원본과 같다. 공백·대소문자 정규화나 요약이 없다
   - 항목 수와 template_id 집합이 pool과 같고 template_id 중복이 없다
   - 순서가 pool 파일의 scenario_pool 순서와 같고, 두 번 호출한 결과가 같다
   - 호출 전후 pool 파일 해시, 메모리 pool의 pool_version·해시가 같다. 반환값을 고쳐도 pool과 다음 호출 결과가 바뀌지 않는다
   - 목록의 모든 template_id가 lookup_template으로 조회되고, 조회한 decision_key가 목록의 값과 같다
   - pool 문자열 속 지시문은 데이터다. travel.pool.load_pool을 대리 함수로 바꿔 title에 지시문이 든 항목을 넣어도 그 문자열이 그대로 나오고 항목 수·필드가 바뀌지 않는다(절대 규칙 4). 이 검사를 위해 함수는 호출할 때 load_pool을 모듈 속성으로 찾아야 한다
3. lookup_template 단독 검사를 같은 파일에 넣어. §0 5번 기준이며 함수가 이미 있으므로 skip 없이 실행돼야 해.
   - 반환값이 pool 원본 항목과 같고, 고쳐도 pool이 바뀌지 않는다
   - 없는 ID(대소문자·끝 공백 변형, 선택지 ID, decision_key 포함)는 KeyError
   - 비문자열 인자(None, int, bool, list, bytes)는 TypeError
4. 결함 주입: .local-work/에 임시 build_scenario_index 구현을 두고 결함마다 기대한 테스트가 실패하는지 확인해. 실행 전에 결함별 기대 결과를 표로 먼저 적고, 실행 후 실제 결과를 나란히 적어. 결함 예시: scene 같은 필드 추가, 필드 누락, 값 strip, 정렬해서 반환, 항목 하나 누락, 캐시 항목을 복사 없이 반환, import 시점에 load_pool을 묶음. 끝나면 주입 전 상태로 되돌리고, 되돌린 뒤 git status --short와 git diff --stat이 주입 전과 같은지 확인해.
5. 결과를 docs/prompts/delegation_pool_index.md §2-1에 적어. 테스트가 도구 코드에 요구하는 인터페이스, 계약 조건과 테스트 대응 표, 결함 주입 표, 사람이 수용할 때 확인할 항목을 포함해.
6. 여기서 멈추고 보고해. 사람이 테스트를 수용하기 전에는 build_scenario_index를 구현하지 마.

## 지킬 것
- src/travel/pool.py, src/travel/data/, tests/test_tools.py, tests/test_pact_golden.py, tests/harness/는 고치지 마.
- docs/는 delegation_pool_index.md §2만 고쳐. ARCHITECTURE의 필드 정의와 §0 기준은 사람이 정한 기준이야. 바꿔야 할 것 같으면 고치지 말고 근거와 함께 제안만 해.
- 당일·숙박 같은 적합성 필드 추가, 필터, 목록 문자열 렌더링, 프롬프트 수정, 모델 호출은 이번 범위가 아니야.
- skip이나 xfail로 기준을 줄이지 마. skip은 build_scenario_index가 없을 때의 목록 검사에만 허용해.
- 새 라이브러리를 추가하지 마. 커밋하지 마.
- 수행하지 않은 검증을 통과로 보고하지 마.

## 완료 조건
- python -m pytest tests/test_pool.py -q -rs: 실패 0, xfail 0. skip은 build_scenario_index 부재 사유로만 나오고, pool 파일 구조 검사와 lookup_template 검사는 통과
- python -m pytest tests/ -q -rs: 기존 56개 통과 유지, 실패 0
- git diff -- tests/test_tools.py tests/test_pact_golden.py tests/harness/ src/ 출력 없음
- git diff --check 출력 없음, git status --short --untracked-files=all에 tests/test_pool.py와 docs/prompts/delegation_pool_index.md 변경만 있음(.local-work/ 제외)

## 멈출 때
- §0 기준이나 ARCHITECTURE 정의만으로 단언문을 정할 수 없을 때
- pool.py를 고쳐야 테스트가 의도대로 동작할 때
- 결함 주입 결과가 기대와 다르고 이유를 설명할 수 없을 때
멈추면 그때까지의 변경과 출력을 그대로 보고해.

## 보고 형식
만든 파일과 이유, 완료 조건 명령의 출력 원문, 수집된 테스트 수(목록 검사·lookup_template 검사·항상 실행 검사 구분), 결함 주입 표(기대와 실제), 사람이 수용할 때 확인할 항목, 미확인 항목.
```

## §2. 회차별 결과

(위임 후 기록)
