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

### §1-2. UI 개선 위임 (2026-11-05)

독립 검토 결과를 바탕으로 한 위임이다. 지시는 항목을 줄여 옮겼고, 승인 답변은 원문에 가깝게 옮겼다.

```text
UI 개선을 진행해 주세요. 독립 검토 결과를 바탕으로 `implementation` 브랜치에서 작업합니다. 푸시, 배포, 실제 LLM 호출, AWS 변경은 내 승인 뒤에 합니다.

1. 바로 고칠 것: 답 확인 화면의 고정 영역, 카드 위 보조 버튼, 대기 화면 진행 막대, 메모 민감정보 안내, 재생성 버튼 숨김, 없는 방 오류, "동행 모두가 정한 약속은 아니에요" 14px 이상.
2. 화면 구조: 초대 링크 복사 상시 제공, 진행 중인 방 이어가기, 공통 뒤로가기, 문항 단계의 브라우저 기록, 이어서 답하기, 확인으로 돌아가기, 방장 결과 화면, 방장 방 화면, 결과가 있을 때의 초대 링크 이동.
3. 첫 인상과 입력: 랜딩, 단계별 방 만들기, 칸별 입력 오류, 초대 링크 공유, OG 태그, manifest.
4. 참여자 여행 정보: 입장 화면과 협약서에 목적지, 기간, 인원을 표시한다. 방·결과 응답의 `trip`, 필요한 테스트, 공유 결과 허용 키 변경을 승인한다. 그 밖의 기대값은 바꾸지 않는다.
5. 발급 연출: `DESIGN.md`를 정확히 따른다. 도장 장면이 사용자가 보는 화면 안에서 끝나게 한다. 효과음이 재생되지 못해도 화면 흐름은 멈추지 않게 한다.

하지 않을 것: 미해결 결과 안내 문구 추가, 방장에게 응답자 명단 표시, 결과를 전원 합의처럼 보이게 하기, 개인 응답·메모·선택 프로필 공개.

검증: `web/`의 typecheck, build, test와 관련 서버 테스트. `dev:mock`으로 390x844, 320x568과 6~8문항을 스크린샷으로 확인한다. 실제 기기, Safari 엔진, 소프트 키보드, 공유 시트, 푸시는 미확인으로 남긴다.
```

계획 보고 뒤 사람이 답한 결정(2026-11-05):

```text
1. 제출 기기와 방장은 결과가 준비돼도 "협약서 보기"를 눌러 시작합니다. 초대 링크로 처음 온 사람은 결과로 바로 가고 소리 없는 연출을 봅니다. 소리 설정은 DESIGN.md를 따릅니다.
2. 답 확인 화면만 적용합니다. DESIGN.md는 이 화면의 예외로 고칩니다.
3. PRIVACY는 이번 배포일을 시행일로 개정 이력에 추가합니다. 실제 사용자가 없어 7일 전 공지는 하지 않으며, 이 판단은 위임 기록에 남깁니다. 시행일은 배포 승인 때 적습니다.
4. `start_url`은 `/`를 유지하고 `id`, `scope`, 아이콘을 추가합니다. 저장소 분리는 실제 기기 확인 항목으로 남깁니다.
5. "추천안 발급"을 SPEC대로 화면에 넣습니다. 위치는 DESIGN.md에 맞추고, 전원 합의처럼 읽히지 않게 합니다.
6. 스테이지별로 커밋합니다. 푸시는 하지 않습니다. 첫 커밋에 현재 `TODO.md` 변경을 포함하고, "화면 결정" 줄은 S2 결과에 맞게 고치거나 해소됐으면 지우세요.
```

### §1-3. UI 개선과 출시 준비 위임 (2026-11-05)

지시는 항목을 줄여 옮겼고, 답변은 원문에 가깝게 옮겼다.

```text
1. 박스 정리: 서로 다른 정리안 2개를 dev:mock에서 보여 주고, 고른 안만 전체 화면에 적용한다. 강조는 주 버튼 하나, 카드는 조작 대상에 쓴다.
2. 랜딩: 주 문구 "떠나기 전에, 서로의 마음을 한 장에." 협약서를 첫 화면에, 3단계를 그 아래에 둔다. 없는 수치·후기·효과를 만들지 않는다.
3. 예시 협약서: 실제 PactSheet 재사용, 도장 포함, 예시 표시, 지어낸 이름, AC3 항목 제외.
4. 초안 표시: "초안"과 그 아래 "방장이 고르기 전이에요". SPEC F5·처리 정책과 resultSheet 기대값 변경을 승인한다.
5. 공유와 나도 만들기: 서비스 링크·결과 이미지 공유, dowonpact.com 바닥글, 공유 문구 분리.
6. SEO와 미리보기, 7. 폰트 직접 호스팅, 8. CSP, 9. 장애 알림.
하지 않을 것: 측정 도구, 미해결 결과 안내 문구 추가, 방장에게 응답자 명단 표시.
```

계획 보고 뒤 사람이 답한 결정:

```text
1. /api/만 robots로 차단하고, /r/은 열어 둔 채 X-Robots-Tag: noindex와 noindex 메타로 막습니다.
2. 본문과 세리프 모두 KS 완성형 2,350자와 영문으로 합니다.
3. Report-Only 단계를 두지 않고 CSP를 강제 모드로 켭니다. csp_enforce 기본값은 true입니다. 로컬에서 같은 CSP를 강제로 걸어 먼저 시험합니다.
4. ECS 태스크 부족은 ALB 정상 대상 수로 대신합니다. Container Insights는 켜지 않습니다.
5. 랜딩 예시에는 도장만 넣고 가지와 꽃은 뺍니다.
6. 안내 단계를 추가하지 마세요. 저장·공유 버튼 근처에 "이미지에 동행 이름이 보여요"를 고정 문구로 둡니다. 저장 이미지에는 넣지 않습니다.
7. 새 PR을 만들지 않고 이번 작업도 PR #16에 넣습니다.
박스 정리는 A안. 초대 링크 복사와 제출 수를 제목 바로 아래로 올리고, 초대 링크 복사는 윤곽선 보조 버튼, 조기 생성은 글자 버튼으로 둡니다. 상태 문구는 한 줄로 줄입니다. 방장 메뉴는 접지 않습니다. 알림 받기는 조금 더 버튼처럼 보입니다.
Terraform apply는 다시 승인받습니다. 승인 뒤 장애 알람은 먼저 적용해도 됩니다. CSP는 PR #16 병합으로 새 폰트가 배포된 뒤에 적용합니다.
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

구현 중 고친 하니스 코드는 없다. 구현이 테스트를 따르느라 정한 것: OUT-N05·N06의 300초·600초 정각 판정(`>=`, 결정 12의 "넘으면"과 다름), 결과 목록의 실패 항목은 `result_id`·`kind`·`attempt`·`state`·`created_at`만, `clauses=null`인 출력의 공유 결과는 빈 배열, 방 상태에 `closed`를 따로 저장하지 않고 `closed_at`과 `generating`을 같은 문장에서 쓴다(관찰되는 상태는 ARCHITECTURE 5절과 같다). 이것은 d0(통과 가능 확인)이며 판정 수용(결함 주입 d1~d28, C2·C7)은 §2-3에서 한다.

### §2-3. S3 모델 호출·도구 루프, S4 화면, S5 인프라·CI (2026-11-05)

**S3 모델 호출** (메인 세션 직접)

| 파일 | 내용 |
|---|---|
| `src/travel/server/llm_openai.py` | openai SDK(`AsyncOpenAI`, `max_retries=0`, 타임아웃 90초)로 Responses API를 부른다. 요청은 `text.format` `strict: false`, 도구 `type: function` + `TOOL_DEFINITION` + `strict: true`, `tool_choice: auto`, `parallel_tool_calls: false`, `store: false`, `include: ["reasoning.encrypted_content"]`, `reasoning: {effort: low}`다. 전송부 해시가 `config/llm.yaml`과 다르면 시작하지 않는다 |
| 같은 파일의 도구 루프 | function_call마다 `get_scenario_template`을 실행해 `function_call_output`으로 되돌리고, 앞 차례의 출력 항목을 다시 넣는다. 호출 수는 코드가 센다. 12번째 요청은 실행하지 않고 도구를 끈 뒤 최종 출력을 1회 요청한다. `incomplete`와 refusal은 `response_status`로 돌려준다. SDK 예외는 `LLMCallError(timeout, rate_limited(Retry-After 포함), server_error)`로 바꾼다. 열어 본 `template_id`는 `LLMResult.opened_template_ids`로 돌려주고, 서버는 열지 않은 문항 선정을 로그 `unopened_selection`에만 남긴다(결정 41) |
| `CostGuard` | `llm_calls`의 일일 비용 합이 한도($5)에 닿으면 `budget_exceeded`를 낸다. `jobs.py`는 이 오류만 재시도하지 않는다 |
| `config/llm.yaml` | 모델, 추론 강도, 전송부 해시(문항 v9 `26219ab9…`, 추천 v12 `bf9f038f…`), 스키마, pool v3 해시, 도구 상한 12, 재시도, 동시 4, 타임아웃 90, 비용 단가와 한도 |
| `src/travel/server/replay.py`, `config/replay/scenario_set_d01.json` | 재생 모드. 문항은 2026-11-05 A''(v8 경로 확인, pool v3, D01 입력)의 실제 Sol 출력 1건을 그대로 돌려준다. 추천은 입력 응답 전부를 조항과 미해결 사유에 묶은 `proposed`를 코드로 만든다. 여행 정보와 무관하게 같은 문항이 나오므로 시연 장애 대비와 로컬 실행에만 쓴다. README에 밝혔다 |
| `src/travel/server/main.py` | 환경변수(2026-11-05 확정 이름)와 `config/llm.yaml`로 `Settings`를 만든다. `LLM_MODE`(live 또는 replay), pywebpush 발송기, `web/dist`가 있을 때의 SPA 정적 서빙을 묶는다 |
| `src/travel/server/admin.py` | `delete-room` 명령. cascade로 지우고 관리자 접속기록을 표준 출력에 남긴다 |

검증:

| 명령 | 결과 |
|---|---|
| `python -m pytest tests/test_llm_loop.py -q` | 8 passed(2026-11-05 사람 승인 케이스 (a)~(h). httpx.MockTransport가 SDK 전송 계층을 대신한다) |
| `python -m pytest tests/ -q`(DB 있음) | 261 passed |
| `ruff check .` | 통과(`ruff.toml`: E·F·W, 줄 길이 150. 기존 하니스와 검증기가 통과하는 값) |
| 로컬 흐름(`LLM_MODE=replay`, `uvicorn travel.server.main:app`) | 방 생성, 문항 ready, 제출 2건, 자동 생성, 결과(초안), 방장 수정, 선택, 재생성까지 HTTP로 확인. 결과와 로그에 메모·MBTI·이름 없음 |
| `docker build --platform linux/arm64 --build-arg SKIP_WEB=1` | 성공 |

실제 Sol 호출은 아직 하지 않았다. 사용자 승인 뒤 D01~D08 C1~C6 점검과 10회 측정을 한다.

**S4 `web/`** (에이전트 A, Opus 5.5, worktree)

Vite + React + TypeScript. 라우트는 `/`, `/r/:code`, `/r/:code/answer`, `/r/:code/wait`, `/r/:code/result`, `/privacy`다. 서비스워커와 mock 모드(`VITE_MOCK=1`)가 있다. `npm run typecheck`, `build`, `test`(vitest 12개)가 통과했다. 에이전트가 headless Chrome으로 mock 흐름 13단계를 눌러 확인했다.

확인하지 않은 것: 실기기(AC14), 실제 서버 연결, 실제 푸시, Web Share.

에이전트가 적은 계약 공백: API에 여행 정보가 없어 결과 종이의 여행 정보 줄은 방을 만든 기기에만 남는다. `label`이 결과 단위라 '방장 수정' 표시가 조항 번호 옆이 아니라 종이 머리에 있다. 실패 항목의 필드, VAPID 응답 형식, 선택 정보 허용값은 가정이다. 에이전트 워크트리가 PR #15 이전 커밋 기준이어서 처리방침 절 번호를 "N." 형식으로만 찾았다. 메인 세션이 "제N조"도 받도록 `Markdown.tsx`를 고쳤고 테스트 12개가 다시 통과했다.

**S5 `infra/`·CI** (에이전트 B, Opus 5.5, worktree)

Terraform 17개 파일(VPC, ALB, ECS Fargate ARM, RDS 16, S3와 CloudFront, CloudFront Function, ACM, 기존 Route 53 영역 참조, WAF 4규칙, Secrets Manager 4개, CloudWatch 30일, GitHub OIDC), `Dockerfile`(python 3.13-slim, non-root, SPA 스테이지는 `SKIP_WEB`로 건너뛸 수 있음), `.github/workflows/pr-check.yml`과 `deploy.yml`을 만들었다.

`terraform fmt -check`와 `validate`가 통과했고, 읽기 전용 `plan`은 68개 생성 예정이었다. 프로필 `itbm`은 `aws login` 세션이라 `credential_process` 우회가 필요했으며 방법은 `infra/README.md`에 있다. 손으로 만든 예산 `dowon-total-20261109-20270112`($300, 80%와 100% 알림)이 이미 있어 Terraform으로 관리하지 않는다. CloudFront 표준 로그와 WAF 로그는 User-Agent를 담으므로 꺼 두었다(처리방침 제11조). 메인 세션이 Dockerfile CMD에 `--no-access-log --proxy-headers`를 더했다. apply는 하지 않았다.

팀장 확인 항목(에이전트 보고):

1. RDS destroy 때 최종 스냅샷을 남길지. 처리방침 제7조 3항은 7일 안에 백업까지 지운다고 한다.
2. 관리자 접속기록 1년 보관 저장 방식. 아직 구성하지 않았다.
3. `origin-verify` 비밀을 사람이 넣을지, Terraform `random_password`로 만들지.
4. 월 $99 추정에 공인 IPv4, WAF 규칙, 비밀 4개 요금이 들어 있는지.
5. us-east-1 생성이 SCP에 막히는지. 읽기는 성공했다.

### §2-4. 실제 호출 측정 10회 (2026-11-05, 사용자 승인 뒤)

로컬 서버를 `LLM_MODE=live`로 띄워 방 10개의 전체 흐름(방 생성, 문항, 제출, 자동 생성)을 돌렸다. 입력은 국내·해외, 1~4일, 2~4명, 친구·연인·가족을 섞었다. 모델은 `gpt-6.1-sol`, 추론 강도 `low`, 문항 v9(도구 루프), 추천 v12다. 원문은 `.local-work/measurements/2026-11-05_live_10rooms.md`와 서버 로그에 있다. 사용자 조건은 1회 뒤 비용 보고, 방당 $0.20 초과 시 중단이었고 초과는 없었다.

| 항목 | 문항 단계(방 10개) | 추천 단계(호출 12회) |
|---|---|---|
| 호출 지연 평균 / 최대 | 31.3초 / 37.7초 | 37.3초 / 53.4초 |
| 비용 평균 / 최대(호출 1회) | $0.0368 / $0.0481 | $0.0387 / $0.0543 |
| 입력 토큰(호출 1회, 차례 합산) | 75,964~101,186 | 8,760~9,895 |
| 출력 토큰 | 1,489~1,773 | 198~4,632 |
| 도구 호출 | 방마다 6~8회. 상한 도달 0, 열지 않은 문항 선정 0 | 없음 |

방당 비용은 $0.045~$0.123, 평균 $0.083, 합계 $0.833이다. 사용자가 기다리는 시간은 문항 약 30초, 추천 약 30~55초였다(재요청이 있으면 약 90초).

관찰:

1. 추천 출력 12회 가운데 2회가 검증기 `particle_pair`(참여자 토큰 뒤에 조사 쌍 대신 한 조사)로 거부돼 재요청 1회로 통과했다. 추천 프롬프트 v12의 품질 항목으로 남긴다(7강 평가·v13 후보).
2. 4명 방 한 건에서 추천이 `invalid_input`("scenarios에 template_id가 없다")을 돌려줬다. 서버가 추천 입력의 문항에 `scenario_id`만 넣었기 때문이다. 추천 프롬프트 v12는 `template_id`를 읽으므로 `scenario_id`와 `template_id`를 둘 다 넣도록 고쳤다(`app.py` `build_frozen`). 하니스 116개를 다시 통과했다. 측정 10회에는 고치기 전 결과가 들어 있다.
3. 문항 단계 입력 토큰이 큰 이유는 도구 차례마다 앞 차례 출력을 다시 보내기 때문이다(`store: false`). 캐시 토큰은 캐시 단가로 셌다.
4. `config/llm.yaml`의 값은 유지한다. 호출 타임아웃 90초는 최대 지연 53초의 1.7배, 작업 한도 300초는 재요청·재시도를 포함해도 남는다. 방당 상한 $0.20과 일일 한도 $5(약 60방)는 측정값 기준으로 여유가 있다. 서비스 예산 $45는 평균 $0.083로 방 약 540개다.

실제 Sol 호출이며 품질 판정(H1~H3)은 하지 않았다. D01~D08 자동 판정은 요청별 판정 기준 고정 뒤에 한다(사용자 결정).

### §2-5. 인프라 결정 반영과 읽기 전용 plan (2026-11-05)

사용자 결정(2026-11-05, 전민규): RDS 삭제 때 최종 스냅샷을 남기지 않는다(`db_skip_final_snapshot` 기본값 true. 처리방침 제7조 3항). `origin-verify` 비밀 값은 Terraform `random_password`가 만들어 Secrets Manager에 쓴다(사람 입력과 2단계 apply를 없앤다). 두 결정을 `infra/`에 반영했다. `terraform fmt -check`, `validate`가 통과했다.

`terraform plan -var aws_profile=itbm-tf`(읽기 전용, state 없음)는 **70개 생성, 변경·삭제 0**이었다. 원문은 `.local-work/infra/plan_2026-11-05.txt`에 있다. 자격 증명은 README의 `itbm-tf` 프로필(`credential_process`)을 `~/.aws/config`에 더해 썼다. 확인한 값: RDS `db.t4g.micro`, 단일 AZ, gp3 20GB, 저장 암호화, 백업 7일, 삭제 보호 켬. ECS Fargate ARM64 태스크 2개. CloudFront `PriceClass_200`. CloudWatch 30일. WAF 규칙 4개(`rate-room-create`, `rate-generation`, `rate-api-post`, `rate-api-all`). 비밀 4개. GitHub OIDC 역할. apply는 하지 않았다.

남은 팀장 확인 항목: 관리자 접속기록 1년 보관 저장 방식(미구성), 월 $99 추정의 항목 대조(공인 IPv4·WAF 규칙·비밀 요금), us-east-1 생성이 SCP에 막히는지(apply 때 드러난다).

계정 ID와 호스팅 영역 ID 처리(2026-11-05, 전민규 결정): 공개 저장소에 두지 않는다. `infra/variables.tf`의 기본값을 빼고 gitignore된 `infra/terraform.tfvars`에 두며, `terraform.tfvars.example`에 자리표시자를 둔다. 두 ID가 들어 있던 로컬 커밋 2개는 푸시 전이어서 `git filter-branch`로 내용을 다시 썼고 백업 ref와 reflog를 지웠다. 모든 ref를 다시 검사해 두 ID가 남지 않음을 확인했다. AWS는 계정 ID를 비밀로 보지 않지만 불필요한 공개를 피하라고 안내한다.

부트스트랩 2단계(2026-11-05): `terraform apply -target`으로 비밀 `dowonpact/openai-api-key`, `dowonpact/vapid` 두 개를 만들었다(값 없음, 기본 KMS 키 `aws/secretsmanager`. AWS 비밀 생성 스킬이 권하는 전용 KMS 키·자동 교체는 MVP에서 쓰지 않는다). state는 `infra/terraform.tfstate`(gitignore)에 있다.

부트스트랩 3단계(2026-11-05): `dowonpact/openai-api-key`에는 `.env`의 `OPENAI_API_KEY`를 셸에서 바로 넘겨 저장했다(에이전트는 값을 읽지 않았다). `dowonpact/vapid`에는 `py_vapid`로 새로 만든 키 쌍을 base64url 원시 키 형식 `{public_key, private_key, subject: mailto:teamitbm@gmail.com}`으로 저장하고 로컬 파일은 지웠다. 두 값 모두 저장소·로그에 없다. 4단계 전체 apply(태스크 0개)는 같은 날 시작했다.

### §2-6. 첫 배포 (2026-11-05)

| 단계 | 결과 |
|---|---|
| 4. 전체 apply(태스크 0개) | 70개 생성, 오류 없음. us-east-1의 ACM·WAF 생성은 SCP에 막히지 않았다 |
| 5. 이미지 | `dowonpact-app:4da1084`(linux/arm64, SPA 스테이지 생략)를 ECR에 `4da1084`·`latest`·`bootstrap` 태그로 푸시 |
| 5. SPA | `web/dist`를 S3 버킷에 동기화하고 CloudFront 무효화 |
| 5. 스키마 | 서비스와 같은 네트워크 설정으로 일회성 Fargate 태스크 `python -m travel.server.db --init` 실행, 종료 코드 0 |
| 6. 서비스 | `terraform apply -var app_desired_count=2 -var image_tag=4da1084`. 태스크 2개 실행, 롤아웃 COMPLETED |
| 7. 스모크 | `https://dowonpact.com/api/health` 200, `/`와 `/r/abc` 200(SPA), `www` 301, `/api/nothing` 404 JSON, VAPID 공개 키 응답 |

실제 모델 스모크(2026-11-05, 사용자 승인): 배포된 주소에서 방 1개(제주 3일, 2명)를 만들어 문항 ready 34초, 제출 2건, 자동 생성 42초, 결과 `proposed`(조항 4, 조건부 대안 2, 초안)까지 확인했다. 결과 응답에 메모 원문은 없었다. 확인 뒤 일회성 Fargate 태스크로 `admin delete-room`을 실행해 그 방을 지웠다(방 조회 404). GitHub Actions 저장소 변수 8개(역할 ARN, 배포 ID, ECR·ECS 이름, 버킷)는 `gh variable set`으로 넣었다. 브랜치는 푸시 전이다. Terraform state는 로컬 `infra/terraform.tfstate`(gitignore)에만 있다. 로컬 확인과 배포 확인을 구분한다. 실기기 확인(AC14)은 아직이다.

### §2-7. 푸시·PR과 관리자 접속기록 (2026-11-05)

**푸시·PR**: `implementation`을 푸시하고 PR #16(main)을 열었다. 첫 `pr-check.yml` 실행은 워크플로 파일 오류로 실패했다. job 단위 `if`에 `hashFiles`를 써서 GitHub Actions가 "Unrecognized function"으로 거절했다. 조건을 지우고(`aaebc00`) 다시 실행해 세 job(python, web, terraform)이 모두 통과했다. python job은 `ruff check .` 통과와 `pytest tests/` 261 passed(서버 케이스 86개 포함, skip·xfail 0), web job은 vitest 12 passed, terraform job은 validate 통과였다. PR은 병합하지 않았다.

**관리자 접속기록**(설계 승인 2026-11-05, 전민규. 추가 요구 6개 반영): `infra/audit.tf`에 전용 S3 버킷(공개 차단, SSE-S3, 버전 관리, HTTPS 전용 정책, 현재·이전 버전 400일 만료, 만료된 삭제 마커·미완성 업로드 정리, `prevent_destroy`), 모든 리전 관리 이벤트 trail(로그 파일 검증 켬), 태스크 역할의 `admin-audit/` PutObject 권한, 태스크 환경변수 `ADMIN_AUDIT_BUCKET`·`ADMIN_AUDIT_PREFIX`를 더했다. `admin.py`는 삭제 기록을 S3에도 쓰고, 실패하면 삭제는 유지한 채 `audit_stored: false`와 이유를 결과에 넣고 종료 코드 3을 낸다. `tests/test_admin_audit.py` 4개(가짜 S3·가짜 삭제)를 추가했다. `boto3==1.39.3`을 의존성에 더했다. 읽기 전용 plan은 10개 생성, 1개 변경(GitHub 배포 역할 정책), 0개 삭제다. apply와 새 이미지 배포는 승인 전이다. 사전 확인: 계정에 trail·Lake 저장소가 없었고, 90일 이벤트 기록에는 일회성 삭제 태스크의 `RunTask`가 실행자·시각과 함께 남아 있었다. README "정리"에 trail 삭제, state 분리, 버킷 유지, 2028-02-16 이후 담당자 삭제 절차와 DB 직접 접속을 하지 않는 전제를 적었다.

**방당 $0.20 상한**(2026-11-05): `Settings.room_cap_usd`(기본 None, `config/llm.yaml`의 `room_cap_usd`로 채움)를 더하고, `jobs.py`가 다음 모델 호출 전에 그 방의 `llm_calls` 비용 합을 읽어 상한에 닿았으면 `budget_exceeded`를 낸다. 재시도하지 않고 기존 호출 실패 경로대로 `failed(call_error)`가 되며, 방장 재시도는 받되 같은 검사로 다시 실패한다(ARCHITECTURE 5절 "초과 시 실행 오류로 중단"). `tests/test_room_cost_cap.py` 6개를 더했다. 설정 필드만 넣고 검사가 없을 때 그중 2개가 실패하는 것을 확인한 뒤 검사를 넣어 통과시켰다. 기존 기대값은 바꾸지 않았다. `tests/` 271 passed(DB 있음).

**처리방침 시행일**(2026-11-05): `docs/PRIVACY.md` 제15조의 "2026년 __월 __일"을 "2026년 11월 5일", 변경 이력의 "(최초 시행)"을 "2026-11-05"로 바꿨다. `web/src/pages/Privacy.tsx`는 이 파일을 빌드 때 그대로 넣어 그리므로 `npm run build` 뒤 번들에 두 문구가 들어 있음을 확인했다. 배포본 반영은 다음 SPA 동기화 때다.

### §2-8. UI 개선 (2026-11-05, 에이전트 Claude, 메인 세션 직접)

| 단계 | 커밋 | 내용 |
|---|---|---|
| S1 바로 고칠 것 | `8aaabef` | 답 확인 고정 영역, 표면 위 보조 버튼(`button-secondary-on-surface`), 대기 막대, 메모 안내, 재생성 버튼, 없는 방 화면, 안내 문장 14px |
| S2 여행 정보 | `f8fe13e` | 방 조회와 공유 결과의 `trip`(서버 위임 기록 결정 47), 입장 화면과 종이·저장 이미지의 여행 정보 줄, SPEC, 처리방침 제14조 |
| S3 화면 구조 | `21d26b3` | 공통 뒤로가기, 문항 기록(`?step=`), 이어서 답하기, 확인 시트, 방장 방·결과 화면, 결과 이동 |
| S4 첫 인상과 입력 | `b708e7c` | 랜딩, `/new` 4단계 입력, 칸별 오류, `/r/:code/created`, OG, 아이콘, manifest |
| S5 발급 연출 | `492165e` | 시간표, 가지, 꽃잎, 효과음, 결과 배경, 줄인 움직임, 추천안 발급 표시, 모의 문항 수 |

**처리방침 공지 판단**: 제14조에 목적지·기간·인원의 공개를 더했다. 개정 이력의 시행일은 사람이 2026-11-06으로 적었다. 별도 배포는 없고 병합으로 `deploy.yml`이 배포한다. 아직 실제 사용자가 없어 제15조의 시행 7일 전 공지는 하지 않는다. 이 판단은 사람이 2026-11-05에 내렸다.

**구현 중 정한 것**:

- 결과가 있는지는 `room_status`가 아니라 `GET /result` 성공으로 판단한다. 재생성이 실패하거나 진행 중이어도 공개 결과가 남기 때문이다.
- 제출한 기기의 방 화면은 대기 화면으로 자동 이동하지 않는다. 자동으로 보내면 대기 화면의 상단 뒤로가기가 제자리를 돈다.
- 방 만들기 입력은 메모리에만 둔다. 화면을 오가도 남고, 새로고침과 탭 닫기는 브라우저 이탈 확인을 거친다.
- 연출은 방마다 이 기기에서 한 번만 재생한다. 수정본은 결과 ID가 달라서 결과 ID로 기록하면 수정할 때마다 다시 재생된다.
- 꽃은 가지 시간 500ms 안에 다 피게 했다. `DESIGN.md`의 "500ms 안에"가 꽃까지 가리키는지 분명하지 않아 좁은 쪽으로 읽었다.
- 추천안 발급은 바닥글 첫 줄에 두고, 바로 아래에 "동행 모두가 정한 약속은 아니에요" 문장을 둔다. 종이가 없는 결과에는 넣지 않는다.

**시험 중 찾아 고친 것**:

- 저장 이미지에서 꽃이 검게, 가지가 빠져 나왔다. 이미지 라이브러리가 CSS로 상속한 `fill`·`stroke`를 옮기지 못했다. 색을 SVG 요소 속성으로 옮겼다.
- 입력 오류 문구가 `label` 안에 있어 입력란의 이름에 오류가 섞였다. 오류를 `label` 밖으로 옮겼다.
- 사용자가 조항이 나타나기 전에 화면을 만지면 자동 스크롤이 멈추지 않았다. 움직임을 기록해 시작 전에도 멈추게 했다.

**검증**(2026-11-05, 로컬):

| 구분 | 명령·방법 | 결과 |
|---|---|---|
| 화면 단위 | `npm run typecheck`, `npm run test`, `npm run build` | 통과, vitest 40개 |
| 서버 | `python -m pytest tests -q -rs`(postgres:16) | 274 통과, skip·xfail 0. `tests/test_server_*.py`는 116개 |
| 린트 | `ruff check .` | 통과 |
| 브라우저 | `dev:mock`, Playwright Chromium, 390x844·320x568, 3·6·8문항 | 흐름 통과, 가로 스크롤 0, 페이지 오류 0 |
| 도장 위치 | 8문항, 도장이 시작될 때 좌표 측정 | 390: 642~755px, 고정 영역 767px. 320: 367~479px, 고정 영역 491px |
| 연출 분기 | 스크롤 중단, 줄인 움직임, 재열람, 오디오 생성 실패, 효과음 켬 | 모두 흐름이 끝남. 효과음을 켠 경우 소리 노드 생성을 확인 |

귀로 듣는 확인은 하지 않았다. 실제 기기, Safari 엔진, 소프트 키보드, 공유 시트, 푸시, 기기 무음 설정은 미확인이다. 배포는 하지 않았다.

**남은 차이**: 도장은 안쪽 테두리선과 바닥글 글자 끝에는 걸치지만, 바닥글 글이 길어 바닥글 헤어라인에는 닿지 않는다(`DESIGN.md` 도장 절).

**보고 뒤 결정**(2026-11-05): '방장 수정'은 종이 머리에 유지하고 `DESIGN.md`를 구현에 맞췄다. 처리방침과 F7은 고치지 않는다. F7은 2026-11-17 이후 구현으로 이미 정해져 있다.

### §2-9. UI 개선과 출시 준비 (2026-11-05, 에이전트 Claude. 인프라는 worktree 에이전트가 쓰고 메인 세션이 검토)

| 단계 | 커밋 | 내용 |
|---|---|---|
| 작업 트리 | `d51b42b` | 처리방침 시행일, TODO |
| S1 박스 시안 | `6ceeff8` | 모의 모드 A·B 전환(S7에서 지움) |
| S2 랜딩·예시·초안 | `4d3653a` | 후킹 문구, 실제 종이 예시, 초안 표시 |
| S3 공유 | `2533a2c` | 결과 이미지·서비스 링크 공유, 문구 분리, 바닥글 주소 |
| S4 SEO | `a11bee6` | robots, sitemap, favicon, canonical, 제목, noindex |
| S5 폰트 | `f490733` | 직접 제공, Google Fonts 제거 |
| S7 박스 적용 | `91cc113` | A안, 버튼 위계, 한 줄 상태, 시안 제거 |
| S6 인프라 | `33e866a` | CSP, `/r/*` 헤더, 알람 8개 |

**robots와 noindex**: robots로 막으면 크롤러가 noindex를 읽지 못한다. 그래서 `/api/`만 막고 `/r/`은 열어 둔다. 방 경로의 첫 HTML은 모든 경로가 공유하는 `index.html`이라, 메타 태그는 스크립트가 넣는다. 스크립트를 돌리지 않는 크롤러는 `X-Robots-Tag` 헤더로 막는다. 이 헤더는 `terraform apply` 뒤에 켜진다.

**폰트 측정**(8문항 결과, 로컬): 파일은 합 1,013 KiB다(본문 215, 253, 251, 세리프 294). 세리프는 화면 고정 글자만 넣으면 70 KiB라 KS 범위로 224 KiB 늘었다. 저장 이미지는 두 방식 모두 773 KiB로 같았다. 첫 저장 시간은 2,636ms에서 352ms로 줄었고, 저장 때 폰트 요청은 406건에서 4건으로 줄었다. 같은 커밋에서 `cacheBust`도 꺼서 폰트만의 효과로 나누지는 못한다. Google Fonts는 쓰는 조각만 받았으므로 첫 화면 폰트 전송량은 늘어난다.

**IBM Plex 이름**: 라이선스가 "Plex"를 예약 글꼴 이름으로 둔다. 줄인 파일은 수정본이라 글꼴 이름을 Dowon Sans로 바꿨다.

**CSP**: 로컬 서버에서 같은 값을 강제로 걸어 시험했고 위반은 0건이다. 처음 계획의 `base-uri 'none'`은 이미지 저장 라이브러리의 기준 주소 설정을 막아 `'self'`로 바꿨다. CSP를 켠 이미지와 끈 이미지는 픽셀까지 같았다. 푸시 구독은 헤드리스 Chromium이 `permission denied`로 거절해 끝까지 시험하지 못했다. 그 과정에서 CSP 위반은 없었다.

**배포 중 알람**: 정상 롤링 배포는 약 108초로 추정하며 기존 태스크를 유지해 울리지 않을 것으로 본다. 교체 배포를 실제로 관찰한 적은 없다. 실패한 배포는 "대상 비정상"이 울릴 수 있고 이는 실제 문제를 알리는 경보다.

**plan**: 추가 12개, 변경 3개, 삭제 0개다. 변경 중 2개(S3 버킷 정책, GitHub 배포 역할 정책)는 배포 ARN을 참조해 `known after apply`로 표시됐다.

### §2-10. PR #16 리뷰 반영 (2026-11-05, 에이전트 Claude)

기준 커밋은 `91665a2`다. 사람이 스테이지 계획과 결정 6건을 승인했다. 회귀 테스트는 먼저 쓰고, `91665a2`를 체크아웃한 별도 워크트리에서 실패하는지 확인한 뒤 고쳤다. 실제 LLM 호출, 푸시, 배포, Terraform apply는 이 회차에서 하지 않았다.

| 스테이지 | 리뷰 항목 | 회귀 테스트 | `91665a2`에서 실패 | 수정 뒤 |
|---|---|---|---|---|
| S1 푸시 | 1 | `tests/test_push_endpoint.py` | 37/42 | 42 통과 |
| S2 DB 풀 | 7 | `tests/test_db_pool.py` | 4/5 | 5 통과 |
| S3 문항 복구 | 2 | `tests/test_scenario_recovery.py` | 10/13 | 13 통과 |
| S4 비용·기록 | 3, 11 | `tests/test_llm_cost_ledger.py` | 10/10 | 10 통과 |
| S5 추천 입력 | 12 | `tests/test_pact_input_constraints.py` | 4/5 | 5 통과 |
| S6 화면 | 4, 5, 6 | `web/src/test/failurePaths.test.tsx` | 16/21 | 21 통과 |
| S7 배포·관측 | 8, 9, 10 | `tests/test_deploy_and_access.py` | 25/26 | 26 통과 |
| S8 하니스 | 13 | 기존 OUT-N05·N07·CLS-N04 | [서버 위임 기록 §2-5](delegation_server.md) | 통과 |

실패하지 않은 테스트는 고치지 않아도 되는 동작을 지키는 검사다. S6의 결과 화면 2개(방장이 실패·재생성 중인 방에서 고르고 저장)는 `91665a2`에서도 통과했다. 그 경로의 문제는 결과 화면이 아니라 거기로 가는 버튼이었다. S7의 일부는 새 스크립트가 없어서 실패한 것이다. 기본 Docker 빌드는 `91665a2`에서 실패하고 수정 뒤 성공하는 것을 로컬에서 따로 확인했다.

**사람 결정**(2026-11-05)

1. 푸시 허용 호스트는 `fcm.googleapis.com`, `*.push.services.mozilla.com`, `*.push.apple.com`이다. 기본값은 이 3곳이고 하니스 설정에만 `push.test`를 더한다.
2. 문항 재시도는 `POST /retry` 확장과 새 방 링크를 모두 둔다.
3. 사용량을 모르는 실패는 구분해 기록하고 한도에 넣지 않는다.
4. 결과가 불명확한 제출의 키와 본문은 그동안만 `localStorage`에 두고 24시간 뒤 만료한다.
5. 이전 자산은 현재 빌드에 없고 S3 업로드 시각에서 7일이 지난 파일을 지운다. 7일은 측정값이 아니고, 배포 뒤 7일 지원을 뜻하지도 않는다.

**구현 판단**

- 접속 IP는 uvicorn에 맡기지 않는다. CIDR로 ALB만 믿으면 CloudFront 엣지 주소가 기록되기 때문이다. `TRUSTED_PROXY_HOPS=2`는 Dockerfile의 `ENV`로 넣어 Terraform 변경이 없다.
- `core_constraints`는 문항을 확정할 때 저장한다. 방이 열린 동안 pool이 바뀌어도 입력이 흔들리지 않는다. 추천 프롬프트 전송부와 v12는 바꾸지 않았다.
- 스키마 버전은 2다. 새 열은 `ALTER ... IF NOT EXISTS`로 더하고, 구독 유일 색인을 만들기 전에 중복을 지운다. 지운 행 수는 스키마 초기화 로그의 `duplicate_push_subscriptions_removed`에 남는다.

**남은 위험**

- 사용량을 모르는 실패는 한도에 들어가지 않는다. 호출 도중 프로세스가 죽으면 그 호출의 사용량 기록이 사라진다.
- 푸시 호스트 이름은 실제 기기에서 확인하지 않았다.
- 7일 기준이 S3 업로드 시각이라, 7일 전에 올린 파일은 빌드에서 빠진 첫 배포에서 바로 지워진다. 그 배포 전에 연 탭은 그 파일을 불러오지 못할 수 있다.
- 배포 스크립트는 가짜 `aws`·`docker`와 로컬 HTTP 서버로만 시험했다. 실제 S3·ECR·CloudFront에서는 돌리지 않았다.
- `core_constraints`가 들어간 현재 입력의 의미 품질은 미검증이다.

### §2-11. PR #16 2차 리뷰 반영 (2026-11-06, 에이전트 Claude)

기준 커밋은 `d597e75`다. 회귀 테스트 `web/src/test/submissionLock.test.tsx` 10개를 먼저 쓰고 그 커밋에서 돌려 9개 실패를 확인했다. 통과한 1개는 명확한 거절 뒤 수정이 풀리는지 보는 검사다. 기존 테스트 기대값은 바꾸지 않았다.

| 항목 | 재현 | 변경 |
|---|---|---|
| 제출 시작 시점의 잠금 | 요청이 끝나기 전에 고치기 버튼이 보였다. 결과를 모르는 동안 확인 화면이 보낸 본문이 아니라 초안을 보여 줬다 | 제출을 시작하면 잠그고, 명확한 거절로 보존이 지워질 때만 푼다. 확인 화면은 보존한 본문을 보여 준다 |
| 다른 세션의 미확인 제출 | `submitSession`이 이전 세션의 요청을 보내고 성공을 돌려줘, 현재 답이 제출되지 않은 채 지워졌다 | 세션이 다르면 아무것도 보내지 않고 초안을 남긴다. "이전 제출 확인하기" 뒤 현재 세션을 새 키로 따로 제출한다. 이전 제출을 확인해도 다른 세션의 초안은 지우지 않는다 |

탭 간 동기화는 `localStorage`의 `storage` 이벤트로 보존 키의 변화만 듣는다. 다른 탭이 확인을 끝내면 막힘이 풀린다. 실제 브라우저 두 탭에서는 확인하지 않았고, jsdom에서 이벤트를 보내 시험했다.

### §2-12. 배포 확인과 실제 기기 (2026-11-06, 전민규·에이전트 Claude)

`deploy.yml` 첫 실행은 AWS 역할 인증에서 실패했다. 저장소가 GitHub 불변 OIDC 주체를 쓰는데 역할은 옛 형식만 허용했기 때문이다. 역할을 고친 뒤 재실행이 성공했고, PR #17로 코드를 맞췄다.

| 항목 | 결과 |
|---|---|
| 배포 | `5e89fce` 성공, 태스크 2개 |
| 중복 구독 정리 | 지운 구독 0건 |
| CloudTrail | 로깅 중, 모든 리전, 로그 파일 검증 켬 |
| CSP, `X-Robots-Tag` | CSP 강제 적용. `/r/*`에 `noindex, nofollow` 적용 |
| 삭제 기록 | 시험 방 삭제, 실행 기록의 S3 저장 확인, 방 조회 404 |
| 검색 등록 | Google, 네이버 완료(전민규 보고) |

실제 기기(전민규 확인): 아이폰 14 Pro(iOS 27.2, Safari 27.2), 삼성 갤럭시 S26(Android 16, Chrome 157.0.8103.38). 응답·생성·편집·저장 흐름, 소프트 키보드, 이미지 저장, 공유 시트, 효과음, 카카오 미리보기, 홈 화면 앱을 확인했고 기능 결함은 보고되지 않았다. 사람이 본 범위이며 웹이나 추천 품질 판정이 아니다.

### §2-13. README 사용자 가이드와 재생성 목록 (2026-11-07, 전민규·에이전트 Claude)

**공개 범위(전민규 결정)**: 2026-11-11~18 동료 평가는 공개한다. 가상 입력으로 하는 체험이고 현재 조합은 품질 판정 전이다. SPEC의 "실제 참여자에게 공개할 조합의 판정은 공개 전에 끝낸다"에서 실제 참여자는 실제 여행 그룹이며, 실제 여행 그룹은 사람 판정 뒤에 받는다. SPEC 6절, README, TODO에 같은 내용을 반영했다.

**재생성 목록**: `web/src/pages/Result.tsx`는 방 상태가 바뀔 때만 결과 목록을 다시 읽었다. 재생성이 상태 확인보다 빨리 끝나면 화면은 `ready`만 보므로 `2번째 결과` 탭이 나오지 않았다. 재생 모드에서 재현했다(15초 대기 4회 중 2회). 방 응답을 받을 때마다 목록을 다시 읽게 고쳤다. 회귀 테스트 `web/src/test/regenerateList.test.tsx`는 수정 전 코드에서 실패하고 수정 뒤 통과했다. 기존 기대값은 바꾸지 않았다. 수정 뒤 재생 모드의 브라우저 재확인은 하지 않았다.

**운영 사이트 체험(사용자 승인)**: 배포 커밋 `5e89fce`에서 README 순서대로 2인 방 1개를 가상 입력으로 돌렸다. 재생성은 하지 않았다.

| 항목 | 결과 |
|---|---|
| 문항 준비 | 33초, 6문항 |
| 자동 생성 | 마지막 제출 뒤 26초, 방장 창에 `협약서 보기` 자동 표시 |
| 결과 | 조항 2개, 아직 풀지 못한 조건 4개, `반영한 응답 2건` |
| 비공개 | 서준 창에 민지·서준 메모 원문 없음 |
| 방장 마무리 | 고르기, 문구 수정, 이미지 저장 통과. 고른 뒤 서준 창의 초안 표시 사라짐 |
| 비용 | 모델 호출 2회, 입력 85,067토큰, 출력 3,982토큰, $0.08836 |
| 삭제 | 일회성 Fargate 태스크로 비용을 읽고 `admin delete-room` 실행, 종료 코드 0, 접속기록 S3 저장, 방 조회 404 |

답은 스크립트가 낱말로 골랐다. 서준은 6문항 중 4문항이 "정보가 더 필요해요"가 되어 README의 답변 기준과 달랐고, 미해결 조건이 많아졌다. 이 결과는 흐름 확인이며 추천 품질 판정이 아니다. 결과 문장의 의미는 사람이 판정하지 않았다.
