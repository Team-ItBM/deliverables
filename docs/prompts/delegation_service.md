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
