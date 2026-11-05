# 위임 기록: 서비스 구현

대상: 1차 MVP(F1~F6)의 서버, `web/` 화면, `infra/`, CI·배포 워크플로, 모델 호출. 이 문서는 구현 계획 위임 프롬프트와 계획, 회차별 결과, 수용 기록을 보존한다. 서버 계약과 결정은 [서버 위임 기록](delegation_server.md)에 있다.

이 파일은 에이전트가 자동으로 읽지 않는다. 위임할 때 해당 블록을 직접 전달한다.

## §1. 프롬프트 원본

### §1-1. 구현 계획 위임 (작성 2026-11-05, 실행 전)

```text
도원결의 서비스를 구현하려고 합니다. 먼저 저장소를 읽고 구현 계획을 세워 주세요.
이번 단계에서는 파일을 수정하지 않습니다.

## 목표
1차 MVP(F1~F6)를 구현해 `dowonpact.com`에 배포할 수 있는 상태로 만들고, 실제 LLM으로 시연할 수 있게 한다.

범위는 서버, `web/` 화면, `infra/`, CI·배포 워크플로, 모델 호출이다.
F7과 7강 평가는 범위 밖이다.

## 확정된 결정
문항 경로는 v9(목록 + `get_scenario_template` 도구)로 구현한다.
교수 지시로 도구 사용은 필수이며, v8로 돌아가는 경로는 두지 않는다. 품질이 미달이면 v10으로 고친다.

저장소의 일부 문서는 이 결정보다 오래됐다.
`TODO.md`, `docs/SPEC.md`, `docs/ARCHITECTURE.md`, `docs/spikes/scenario_tool_call.md`, `docs/prompts/delegation_server.md`의 "v8 유지", "v8 또는 v9 선택", "판정 전 v8 구현" 서술은 이 결정이 대체한다. 어떤 문서를 어떻게 고칠지 계획에 포함해 달라.

## 먼저 읽을 것
- `AGENTS.md`, `TODO.md`, `docs/SPEC.md`, `docs/ARCHITECTURE.md`, `DESIGN.md`, `docs/PRIVACY.md`
- `docs/AWS_RULES.md`
- `docs/prompts/delegation_server.md`
- `docs/spikes/scenario_tool_call.md`, `.local-work/scenario_tool_call/`의 v9-candidate 자료
- `references/course/05/`와 `references/course/06/`의 작성지침
- `tests/`의 서버 계약 테스트, 도구 계약 테스트, 하니스

읽는 범위는 작업에 맞게 직접 판단해도 된다.

## 계획에서 직접 정할 것
아래는 내가 정하지 않았다. 저장소를 보고 판단하고 근거를 적어 달라.
- 스테이지 구성과 순서, 각 스테이지의 완료 조건
- 병렬로 할 일과 순서를 지켜야 할 일
- subagent 사용 여부, 역할, 모델, 작업 범위, worktree 분리 여부
- 구현과 검증을 어떻게 분리할지
- 결함 주입과 판정 수용을 언제 어떻게 할지
- v9-candidate를 정식 프롬프트로 올리는 절차와 도구 루프의 구현·검증 방법
- 가장 큰 위험과, 일정이 밀릴 때 먼저 줄일 범위

## 지켜야 할 것
- 프롬프트 전송부를 바꾸면 AGENTS의 버전 규칙을 따른다.
- 테스트 코드, 골든 케이스, fixture, 기대값은 사람 승인 없이 바꾸지 않는다. `skip`, `xfail`, 케이스 삭제로 완료 조건을 줄이지 않는다. 위임 기록 결정 16 변경과 도구 루프 테스트 추가도 승인 대상이다.
- 문서가 정하지 않은 제품 정책이나 AC를 임의로 확정하지 않는다.
- 비밀키와 개인정보를 저장소, 로그, 프롬프트에 넣지 않는다.
- 실제 AWS 자원 생성·변경·삭제, 비용이 드는 작업, 실제 LLM 호출, 커밋·푸시·PR은 내 승인 뒤에 한다.
- 수행하지 않은 검증을 통과로 보고하지 않는다.

## 멈추고 물어볼 때
- 문서끼리 충돌하는데 위 결정으로 풀리지 않을 때
- 테스트 기대값이 틀렸다고 판단될 때
- 위 금지 사항을 넘어야 진행할 수 있을 때
- 내가 정해야 하는 항목이 나왔을 때

## 계획 결과
다음을 간결하게 보여 달라.
1. 현재 상태와 전체 접근
2. 스테이지별 작업, 의존성, 완료 조건
3. subagent 전략과 그렇게 정한 이유
4. 검증 방법과 근거가 되는 AC·테스트
5. 일정 위험과 범위 축소안
6. 시작 전에 내가 결정하거나 제공할 것

계획은 내가 승인한 뒤에 실행한다.
```

## §2. 회차별 결과

### §2-1. 구현 계획 (2026-11-05, 에이전트 Claude)

§1-1 블록을 그대로 실행했다. 계획 파일은 세션 밖(`~/.claude/plans/jiggly-bubbling-tide.md`)에 두고, 저장소에는 결정과 결과만 남긴다.

**계획 단계에서 한 일**: 저장소 문서·테스트 하니스·스파이크 자료·강의 05/06 지침을 읽고(탐색 에이전트 3개, 작업·동시성 설계 검토 에이전트 1개), 기준 실행 `python -m pytest tests/ -q -rs` 166 passed·87 skipped를 확인했다.

**사람이 답한 결정**(2026-11-05, 전민규): [서버 위임 기록 결정 38~42](delegation_server.md). 설치·의존성 허용: terraform(1.9+), uvicorn, pywebpush, ruff. `psycopg_pool`은 허용됐지만 수제 풀로 대신한다. subagent 전략은 제안대로 진행.

**스테이지**: S0 문서·프롬프트 v9 승격 → S1 서버(하니스 86개 통과, 메인 세션) ∥ S4 `web/`(에이전트, worktree) ∥ S5 `infra/`·CI(에이전트, worktree) → S2 판정 수용(결함 주입 d0~d28·C2·C7, 별도 검증 에이전트) → S3 모델 호출·도구 루프 → S6 통합·배포·시연 준비.

**S0 결과(2026-11-05)**: `prepare_scenarios.md` 전송부에 v9-candidate(`c4ef3bc5…3dc8`, 해시 대조 일치)를 적용하고 조사 쌍 표기 규칙 한 문장을 더해 `prompt_version` 9로 올렸다(정식 v9 전송부 SHA-256 `26219ab99fadf0ce4d1de7f6e558884b8abe1346e526694d4a971ad7c7d3af2e`, 17,103자). SPEC F2·5절, ARCHITECTURE 1·2·3·5절·변경 영향, TODO 1절, 스파이크 머리말·결정 기록 주석, 서버 위임 기록 결정 38~42를 맞췄다. 테스트 166 passed·87 skipped 유지.

**대상 밖 불일치(발견, 미수정)**: `docs/ARCHITECTURE.md`가 저장소에 없는 `docs/PRIVACY_REVIEW.md`를 두 곳에서 가리킨다. `docs/PRIVACY.md` 제15조 시행일이 비어 있다. `README.md`에 5·6강 산출물 행이 없다. 하니스 OUT-N05·N06은 300초·600초 정각에 실패를 기대하므로 결정 12의 "넘으면"과 달리 서버는 `>=`로 판정한다(기대값은 바꾸지 않는다).

### §2-2. S1 서버 구현 (2026-11-05, 에이전트 Claude, 메인 세션 직접)

하니스(`tests/test_server_*.py`, 케이스 86 + 하니스 검사 30)를 사양으로 삼아 `src/travel/server/`를 구현했다. 테스트·골든 케이스·fixture·검증기는 바꾸지 않았다.

| 파일 | 역할 |
|---|---|
| `app.py` | `Settings`, `create_app(settings=, llm_client=, push_sender=, sleeper=, clock=)`, §0-B 경로 12개와 `/api/health`, 입력 검증(결정 2), 오류 형식(§0-A 4), 방장 토큰 해시 비교 |
| `db.py` | 멱등 DDL `init_schema`, psycopg AsyncConnection 수제 풀, 행 잠금 기반 상태 전환(`close_and_freeze`, `start_attempt`, `finish_attempt`), 알림 행 삽입, `llm_calls` 기록, `python -m travel.server.db --init` |
| `jobs.py` | 문항·추천 백그라운드 태스크, 재시도(1초·2초 + 지터, Retry-After)·재요청 1회, 작업 한도 300초(진행 중 호출 취소)·멈춤 판정 600초, 시도 ID 보호, 첫 정상 결과 전까지만 알림 |
| `push.py` | 이벤트 `ready:N`·`failed:N`(방장)·`selected`(참여자, 첫 선택만), `(subscription_id, event)` 유일 제약으로 중복 방지, 410·404 구독 삭제, `dispatch` |
| `render.py` | 프로필·참여자 토큰 치환, 조사 5쌍(ㄹ 받침 로, 영문·숫자 '님'), 같은 이름 `이름(응답 N)`, 공유 결과(§0-C), `editable` 조각 |
| `llm.py` | `LLMResult`, `LLMCallError`, `LLMClient` 경계. `opened_template_ids`·`usage`는 실제 클라이언트가 채우는 선택 필드 |
| `logging.py` | JSON lines, 접속 로그(IP·시각·경로·상태), 메모·이름·선택 프로필 미기록 |

**실행 결과**(postgres:16 컨테이너, `TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:55432/postgres`):

| 명령 | 결과 |
|---|---|
| `python -m pytest tests/test_server_*.py -q -rs` | 116 passed(케이스 86 + 하니스 30), skip·xfail 0 |
| `python -m pytest tests/ -q -rs` | 253 passed |
| 같은 명령, TEST_DATABASE_URL 없음 | 166 passed, 87 skipped(기존과 같음) |
| `git diff -- tests/ src/travel/pact.py src/travel/scenarios.py src/travel/pool.py src/travel/tools/ src/travel/schemas/ src/travel/data/` | 출력 없음 |
| 실행 뒤 `srvtest_` 데이터베이스 | 0개 |

구현 중 고친 하니스 코드는 없다. 구현이 테스트를 따르느라 정한 것: OUT-N05·N06의 300초·600초 **정각** 판정(`>=`, 결정 12의 "넘으면"과 다름), 결과 목록의 실패 항목은 `result_id`·`kind`·`attempt`·`state`·`created_at`만, `clauses=null`인 출력의 공유 결과는 빈 배열, 방 상태에 `closed`를 따로 저장하지 않고 `closed_at`과 `generating`을 같은 문장에서 쓴다(관찰되는 상태는 ARCHITECTURE 5절과 같다). 이것은 d0(통과 가능 확인)이며 판정 수용(결함 주입 d1~d28, C2·C7)은 §2-3에서 한다.
