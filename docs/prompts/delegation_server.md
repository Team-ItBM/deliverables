# 위임 기록: 서버 계약 (`src/travel/server/`)

대상: [아키텍처 설계서](../ARCHITECTURE.md#2-구성-요소) 2절의 FastAPI 서버(`app.py`, `db.py`, `routes/`, `llm.py`, `render.py`, `push.py`)와 서버 계약 테스트(`tests/test_server_*.py`). 진행 방식은 [문항 출력 검증기 위임 기록](delegation_scenarios.md)과 같다. 판정 기준을 먼저 확정하고 구현은 나중에 위임한다.

이 파일은 에이전트가 자동으로 읽지 않는다. 위임할 때 해당 블록을 직접 전달한다.

**사람이 정한 범위** (2026-11-04, 전민규)

- 케이스 ID 10개: `response_privacy`(AC3), `response_closure`(AC4), `host_edit`(AC12), `result_export`(AC13), `duplicate_name`(AC16), `regeneration`(AC17), `push_events`(AC18), `output_validation`(AC10), `scenario_input`(AC2), `profile_rendering`(AC15).
- 제외: `retention`(AC19, F7이라 11/17 이후), `mobile_access`(AC14, 실제 기기에서 사람이 확인), AC6~AC9·AC11(모델 출력 품질이라 스파이크·evals에서 판정).
- 테스트 DB는 실제 PostgreSQL 컨테이너다. AC4 동시 마감을 검사하기 위해서다.
- 모델 호출은 저장 출력 재생 모드로 대신하고 실제 API는 부르지 않는다.

## §0. 인터페이스 기본안 (초안·결정 반영 2026-11-04, 2026-11-04 수용)

에이전트(Claude)가 2026-11-04에 쓴 초안이다. 전민규가 2026-11-04에 기본안을 채택하고 "결정한 것" 2·3·6·12를 따로 정했다. 반영한 문서를 같은 날 수용했다. SPEC 5절은 "프레임워크와 HTTP 경로에 독립적인 논리 입출력 계약"이라 경로·메서드·형식·오류 코드를 정하지 않았다. 표의 근거 칸에 **[에이전트 안]** 이 붙은 부분은 문서에 없어서 에이전트가 정한 것이다. 확정하거나 바꾸면 §0-1 케이스도 함께 고친다.

### §0-A. 공통 형식

| # | 항목 | 기본안 | 근거 |
|---|---|---|---|
| 1 | 전송 형식 | JSON 요청·응답, 경로 접두사 `/api`. 생성 작업은 202로 응답하고 화면은 방 조회를 폴링한다 | ARCHITECTURE 2절 결정(JSON과 폴링), 5절 상태 기계(202 뒤 백그라운드). 접두사는 [에이전트 안] |
| 2 | 방 식별자 | 초대 링크에 들어가는 무작위 `room_code` 하나로 모든 경로를 구분한다. 방장 경로도 같은 `room_code`를 쓰고 권한은 헤더로 확인한다 | SPEC 5절 "방·초대 링크". 식별자를 하나로 둔 것은 [에이전트 안] |
| 3 | 방장 권한 | 방 생성 응답으로만 128비트 난수 `host_token`을 돌려주고 DB에는 해시만 둔다. 방장 경로는 `X-Host-Token` 헤더가 그 방의 토큰과 맞을 때만 실행한다. 이름 선택(작성 세션)은 어떤 권한도 주지 않는다. 방장 URL(`#` 뒤 토큰)과 초대 링크 조립은 SPA가 한다 | ARCHITECTURE 5절 "방장 권한", SPEC 5절 머리말, AC12. URL 조립 위치는 [에이전트 안] |
| 4 | 오류 응답 | `{"error": {"code": "<코드>", "message": "<사용자 안내 문장>"}}`. 테스트는 HTTP 상태와 `code`만 비교한다. `message`에는 메모 원문·이름·선택 프로필을 넣지 않는다 | AC14 "오류를 텍스트로 표시", 절대 규칙 3. 형식은 [에이전트 안] |
| 5 | 상태 값 | `room_status`: `open`, `closed`, `generating`, `ready`, `failed`. `failure_reason`: `output_invalid`, `call_error`, `interrupted`. `scenario_status`: `preparing`, `ready`, `needs_information`, `unsupported`, `invalid_input`, `failed`. 결과 `kind`: `ai_original`, `host_edited` | `room_status`는 ARCHITECTURE 5절. `failure_reason`은 6절 출력 형식 오류·일시 오류·생성 중 중단의 구분. `scenario_status`와 `kind` 이름은 결정 1. `interrupted`는 에이전트가 2026-11-04에 추가하고 같은 날 수용됐다(결정 20) |
| 6 | 공개 금지 키 | 참여자·방장에게 가는 모든 응답과 푸시 본문에 `memo`, `positions`, `original_condition`, `gender`, `age_band`, `mbti`, `source_response_ids`, `source_response_id`, `response_id`를 넣지 않는다. 결과 응답에는 `option_id`도 넣지 않는다(문항 표시의 `options[].option_id`만 허용) | ARCHITECTURE 2절 규칙 3 확인, SPEC 5절 "필드 연결과 검증 경계", AC3. `source_response_ids`·`response_id`·결과의 `option_id` 제외는 [에이전트 안](결정 8) |

### §0-B. API

| # | 메서드·경로 | 권한 | 요청 | 성공 응답 | 오류 코드 | 근거 |
|---|---|---|---|---|---|---|
| 1 | `POST /api/rooms` | 없음 | `{trip: {destination, duration_days, party_size, relationship}, participant_profiles: [{profile_id, display_name, gender?, age_band?, mbti?}]}` | 201 `{room_code, host_token, created_at, expires_at, scenario_status: "preparing"}`. 응답 뒤 문항 생성을 백그라운드로 시작한다 | `invalid_input`, `needs_information` | SPEC 5절 방 생성, F1, ARCHITECTURE 5절 입력 한도(`party_size` 2~8). 문항 생성 시점은 [에이전트 안](결정 1) |
| 2 | `GET /api/rooms/{room_code}` | 없음(방장 토큰이 있으면 방장 정보 추가) | 없음 | 200 `{room_status, scenario_status, party_size, submitted_count, profiles: [{profile_id, display_name, has_submission}], failure_reason?, scenario_notice?}`. 방장에게는 `scenario_notice`로 `message`·`clarification_questions`를 보여준다 | `not_found` | SPEC 5절 입장·이름 선택, 처리 정책 "입장·중복 이름", ARCHITECTURE 5절 폴링. 필드 구성은 [에이전트 안] |
| 3 | `POST /api/rooms/{room_code}/sessions` | 없음 | `{profile_id}` | 201 `{session_id, duplicate_name_notice, privacy_notice, scenarios}`. `scenarios`는 이 `profile_id` 기준으로 토큰을 치환한 문항이다. 이전 제출 내용은 넣지 않는다 | `not_found`, `room_closed`, `invalid_state` | SPEC 5절 "새 응답 작성 세션", AC15, AC16. `privacy_notice`를 서버가 주는 것은 [에이전트 안](결정 13) |
| 4 | `POST /api/rooms/{room_code}/submissions` | 없음. `Idempotency-Key` 헤더 필수 | `{session_id, answers: [{scenario_id, option_id, memo?}]}` | 201 `{participant_id, response_ids: [{scenario_id, response_id}], submitted_count, party_size}`. 같은 키·같은 본문 재전송은 200으로 같은 본문을 돌려준다. 유효 제출 수가 `party_size`에 닿으면 같은 트랜잭션에서 마감하고 생성을 시작한다 | `invalid_input`, `room_closed`, `session_used`, `idempotency_conflict`, `not_found` | SPEC 5절 답변 제출, 처리 정책 "제출·자동 생성", 필드 연결("동일 제출 요청의 전송 재시도는 같은 건"), ARCHITECTURE 5절 멱등 키·`memo` 300자. 헤더 이름·필수 여부·`session_used`는 [에이전트 안](결정 14) |
| 5 | `POST /api/rooms/{room_code}/generate` | 방장 | 없음 | 202 `{room_status: "generating", included_count}` | `host_forbidden`, `no_submissions`, `room_closed` | SPEC 처리 정책 "조기 생성·마감", AC4, ARCHITECTURE 5절 상태 기계 |
| 6 | `POST /api/rooms/{room_code}/retry` | 방장 | 없음 | 202. 실패한 생성(최초·재생성 어느 쪽이든)을 같은 고정 입력으로 다시 실행한다 | `host_forbidden`, `invalid_state` | SPEC 처리 정책 "재생성·실패", 상태별 처리 마지막 문단, ARCHITECTURE 6절 "생성 중 중단". 경로와 방장 전용 여부는 [에이전트 안](결정 10) |
| 7 | `POST /api/rooms/{room_code}/regenerate` | 방장 | 없음 | 202 | `host_forbidden`, `regeneration_limit`, `invalid_state` | SPEC 5절 재생성, AC17, ARCHITECTURE 5절(정상 결과 행 수로 계산) |
| 8 | `GET /api/rooms/{room_code}/result` | 없음 | 없음 | 200 공유 결과(§0-C) 하나. 방장이 고른 결과, 고르기 전에는 최초 정상 결과다. 그 결과에 방장 수정본이 있으면 가장 최근 수정본을 보여준다 | `invalid_state`(정상 결과 없음), `render_failed` | SPEC 5절 결과 선택, F5, 결정 6 |
| 9 | `GET /api/rooms/{room_code}/results` | 방장 | 없음 | 200 `{selected_result_id, results: [공유 결과 + {attempt, state: "normal" \| "failed", created_at}]}`. 방장에게도 공유 결과 형태만 준다 | `host_forbidden`, `render_failed` | AC3(방장도 다른 참여자의 원문을 받지 않는다), AC17 두 결과 보존 |
| 10 | `POST /api/rooms/{room_code}/results/{result_id}/select` | 방장 | 없음 | 200 `{selected_result_id}` | `host_forbidden`, `not_found`, `invalid_state`(실패 결과) | SPEC 5절 재생성·결과 선택, AC17 |
| 11 | `POST /api/rooms/{room_code}/results/{result_id}/edits` | 방장 | `{edits: [{path, text}]}`. `path`는 공유 결과의 문장 위치(JSON Pointer), `text`는 `{{participant:ID}}` 토큰을 유지한 문장 | 201 공유 결과(`kind: "host_edited"`, `source_result_id`). `result_id`는 AI 원본이다. 그 원본의 가장 최근 수정본이 있으면 거기서 시작하고, 없으면 원본에서 시작한다. `source_result_id`는 시작한 판이다. 새 수정본은 새 행이고 원본과 이전 수정본 행은 바꾸지 않는다 | `host_forbidden`, `not_found`, `edit_not_allowed`, `memo_quote` | SPEC 처리 정책 "방장 편집", AC12, AC3(방장 수정본에도 15자 기준), ARCHITECTURE 2절 규칙 2(편집본은 별도 행), 결정 4·5·6 |
| 12 | `GET /api/push/vapid-public-key`, `POST /api/rooms/{room_code}/push-subscriptions` | 구독 `role`이 `host`면 방장 | `{role: "host" \| "participant", session_id?, subscription: {endpoint, keys: {p256dh, auth}}}` | 201 `{subscription_id}` | `invalid_input`, `host_forbidden`, `not_found` | SPEC 5절 푸시 등록·발송, F6, ARCHITECTURE 2절 `push.py`. 요청 형식은 [에이전트 안](결정 11) |

제출 내용을 조회하는 경로는 두지 않는다(ARCHITECTURE 2절 규칙 3 확인, AC16). 방 단위 삭제 명령(`admin.py`)과 만료는 이번 범위가 아니다.

### §0-C. 공유 결과 형식

```
{
  result_id, kind, source_result_id?, label,          // label: kind가 host_edited면 "방장 수정", 아니면 null
  pact_status,                                        // PactRecommendation.status
  included_count, excluded_names: [display_name],     // 반영한 제출 수, 반영되지 않은 등록 이름
  clauses: [{scenario_id, participant_names, action, proposed_conditions}],
  conditional_alternatives: [{scenario_id, participant_names, action, proposed_conditions, proposed_changes}],
  unresolved_conditions: [{scenario_id, description}],
  message?,
  humor?: {text, explanation}                         // pact_status가 unresolved일 때만
}
```

문장 필드는 모두 서버가 `render.py`로 치환한 텍스트다. `proposed_changes`는 `required_changes[].proposed_change`만 옮긴다. 검증 결과를 나타내는 필드와 합의·수락을 뜻하는 필드(`agreed`, `accepted` 등)는 두지 않는다.

근거: SPEC 처리 정책 "조기 생성·마감"(반영 응답 수와 제외 안내), "응답·결과 공개", "방장 편집"(원본 검증 결과를 편집본 품질 보증으로 쓰지 않는다), 5절 필드 연결(`original_condition`·`positions` 제외, 참여자 토큰 치환), 상태별 처리 마지막 문단(유머 문구 조건), ARCHITECTURE 1절(서버가 치환한 공유 문장). 필드 이름과 구조는 [에이전트 안].

### §0-D. 오류 코드

| 코드 | HTTP | 뜻 | 근거 |
|---|---|---|---|
| `invalid_input` | 422 | 형식·범위·ID 위반(`party_size`, 프로필 수, 중복 `profile_id`, `memo` 300자 초과, 없는 문항·선택지, 같은 문항 중복 답변, 답변 누락, 구독 형식) | SPEC 5절, AC2, AC5, ARCHITECTURE 5절 입력 한도, 절대 규칙 5 |
| `needs_information` | 422 | 방 생성의 필수 값 누락(여행 정보, 이름·별명), 해석할 수 없는 기간·목적지 값(`"며칠 정도"` 등) | AC2, 문항 프롬프트 A절("필수 값이 없거나 기간·목적지가 모호하면", 이름·별명 없으면 `needs_information`), D절 S2·S3, 결정 2 |
| `host_forbidden` | 403 | `X-Host-Token`이 없거나 그 방의 토큰이 아니다 | AC12, ARCHITECTURE 5절 |
| `not_found` | 404 | 없는 방·프로필·세션·결과 | [에이전트 안] |
| `room_closed` | 409 | 마감 뒤 세션 생성·제출·조기 생성 | AC4, SPEC 비포함 "생성 시작 후 추가 제출" |
| `no_submissions` | 409 | 완전한 제출 0건에서 조기 생성 | SPEC 처리 정책 "조기 생성·마감", AC4 |
| `invalid_state` | 409 | 지금 상태에서 할 수 없는 작업(문항 준비 전 세션 생성, 생성 중 재생성, 정상 결과 없음, 실패 결과 선택, 실패가 아닌데 재시도) | ARCHITECTURE 5절 상태 기계. 코드 하나로 묶은 것은 [에이전트 안] |
| `regeneration_limit` | 409 | 세 번째 정상 결과 생성 요청 | SPEC 5절 "세 번째 정상 결과 생성은 거부한다", AC17 |
| `session_used` | 409 | 이미 제출한 세션으로 다른 제출을 시도 | SPEC 4절 비포함 "제출 후 답변 수정", AC16. 코드는 [에이전트 안] |
| `idempotency_conflict` | 409 | 같은 `Idempotency-Key`에 다른 본문 | [에이전트 안](결정 14) |
| `edit_not_allowed` | 422 | 조항 추가·삭제, 근거·적용 대상 변경, 편집 대상이 아닌 필드 | SPEC 처리 정책 "방장 편집", AC12 |
| `memo_quote` | 422 | 방장 수정 문장에 메모의 연속 15자 이상이 그대로 있다(문항 공개 문구와 겹친 부분 제외) | AC3. `pact.py`의 `check_memo_quotes`와 같은 기준 |
| `render_failed` | 500 | 표시 문장에 알 수 없는 ID나 치환되지 않은 토큰이 남았다. 일부 문장도 보내지 않는다 | SPEC 5절 "알 수 없는 ID·미해결 토큰은 표시 오류", AC13. HTTP 상태는 [에이전트 안] |

모델 출력 형식 오류와 호출 오류는 HTTP 오류가 아니다. 백그라운드 생성이 `room_status: failed`와 `failure_reason`으로 남기고 화면은 폴링으로 확인한다(ARCHITECTURE 6절).

### §0-E. 저장 출력 재생 모드와 테스트가 서버에 요구하는 형식

| # | 항목 | 기본안 | 근거 |
|---|---|---|---|
| 1 | 모델 호출 경계 | `llm.py`는 `generate(stage, model_input, repair_errors=None) -> LLMResult`를 둔다. `stage`는 `scenarios` 또는 `pact`, `repair_errors`는 재요청 때 붙이는 검증기 `errors`다. `LLMResult`는 `{raw_output, response_status}`(`completed`, `incomplete`, `refusal`)이고 호출 실패는 `LLMCallError(kind, retry_after)`(`timeout`, `rate_limited`, `server_error`)로 낸다 | ARCHITECTURE 5절 모델 호출 계약(`incomplete`·refusal은 형식 오류 경로), 6절 출력 형식 오류·일시 오류, AGENTS 5절(외부 호출은 검증·표시 로직과 분리). 시그니처는 [에이전트 안] |
| 2 | 재생 클라이언트 | 테스트는 위 경계를 구현한 재생 클라이언트를 주입한다. 단계별 대기열에서 응답(문자열, `response_status`, 오류)을 하나씩 꺼내고, 받은 `stage`·`model_input`·`repair_errors`를 모두 기록한다. 대기열 항목은 고정 문자열이거나 받은 `model_input`으로 출력을 만드는 함수다 | ARCHITECTURE 5절 "저장 출력 재생 모드". 함수 항목은 [에이전트 안](결정 16) |
| 3 | 검증기 재사용 | 서버는 `validate_scenario_output`·`validate_pact_output`을 고치지 않고 부른다. 검증 실패는 형식 오류와 같은 재요청 규칙(최대 1회)을 따른다 | ARCHITECTURE 2절, 6절 후처리 위반 행 |
| 4 | 주입 지점 | `create_app(settings, llm_client, push_sender, sleeper, clock)`처럼 앱을 만들 때 재생 클라이언트, 가짜 푸시 발송기, 대기 함수, 현재 시각 함수를 받는다. `settings`로 DB URL, pool 파일 경로, 문항 요청 수와 `request` 문장, 재시도 간격, 생성 작업 한도(기본 5분)와 멈춤 판정 시간(기본 10분)을 바꿀 수 있다 | [에이전트 안]. pool 경로를 바꿔야 하는 이유는 §0-F, 두 시간 값은 결정 12 |
| 5 | 백그라운드 완료 대기 | 테스트가 생성 완료를 기다릴 수 있게 `await app.state.jobs.join()` 같은 대기 수단을 둔다. 멈춤 판정 점검도 테스트가 직접 부를 수 있게 `app.state.jobs.recover_stalled()` 같은 진입점을 둔다. 실제 시간을 기다리지 않는다 | ARCHITECTURE 5절(프로세스 안 백그라운드 태스크, `generating`에 설정 시간 이상 머문 방은 failed). [에이전트 안] |
| 6 | 푸시 발송기 | `send(subscription, payload) -> status_code`. 가짜 발송기는 보낸 구독·이벤트·본문을 기록하고 지정한 구독에 404·410·500을 돌려줄 수 있다 | ARCHITECTURE 6절 푸시 발송 실패. [에이전트 안] |
| 7 | DB | 테스트는 `TEST_DATABASE_URL`의 PostgreSQL 컨테이너에 스키마를 만들고 케이스마다 비운다. 동시성 케이스는 실제 연결 여러 개로 동시에 요청한다 | 사람이 정한 범위(2026-11-04), ARCHITECTURE 2절 CI(서버 테스트용 Postgres 컨테이너) |
| 8 | ID | `room_code`, `session_id`, `participant_id`, `response_id`, `result_id`는 서버가 무작위로 만든다. 테스트는 값을 가정하지 않고 응답과 재생 기록에서 읽는다 | [에이전트 안] |

### §0-F. 기존 fixture를 재생 입력으로 쓸 수 있는가 (2026-11-04 에이전트 확인)

- 문항 단계 `ex1_ready`, `s1_ready`: 출력의 `template_id` 6개(`free_time`, `rest`, `sunset`, `meal`, `photo`, `budget`)가 현재 pool v3(50개)에 없다. 스크립트로 대조했다. 서버가 pool v3를 입력으로 쓰면 `validate_scenario_output`이 `unknown_template`로 거부한다. 테스트에서 pool 경로를 fixture 입력의 `scenario_pool`(8개)로 바꾸면 그대로 쓸 수 있다(결정 15).
- 문항 단계 `ex2_needs_information`, `s2`~`s6`: 상태가 `ready`가 아니면 검증기가 입력 pool을 대조하지 않으므로 상태 분기 확인에 그대로 쓸 수 있다.
- 추천 단계 `tests/harness/fixtures/pact/` 10개: 입력의 `participant_ids`(`A`, `B`, `C`)와 `response_id`(`rA` 등)가 fixture 고유값이고 상황이 1~2개다. 서버는 ID를 무작위로 만들고 6~8개 문항 전부의 응답을 넣으므로, 그대로 재생하면 `unknown_reference`, `unlinked_response` 등으로 거부된다. 추천 단계는 받은 `model_input`으로 출력을 만드는 테스트 도우미가 필요하다. 문장은 fixture의 `action`·`proposed_conditions`를 가져다 쓸 수 있다.

## §0-1. 골든 케이스 후보 (초안·결정 반영 2026-11-04, 2026-11-04 수용)

에이전트(Claude)가 §0 기본안을 전제로 쓴 후보다. 2026-11-04 결정에 따라 INP-N06의 기대값을 바꾸고 EDT-P03, OUT-N05, OUT-N06을 더했다. 채택과 기대값은 사람이 확정한다(강의 5 B절, AGENTS 4절). ID 앞 글자 P는 통과해야 하는 케이스, N은 실패를 정확히 내야 하는 케이스다. 근거 칸의 "규칙 2·3"은 AGENTS 3절 절대 규칙 번호다.

**공통 준비**

- 기본 방: `ex1_ready` 입력의 `trip`(제주·3일·3명·친구)과 프로필 `p1`~`p3`. 이름은 케이스에 따라 `민준`(받침 있음), `지수`(받침 없음), `하늘`(ㄹ 받침)로 바꾼다.
- 문항 재생: `ex1_ready` 출력, 테스트 pool은 `ex1_ready` 입력의 pool(§0-F).
- 추천 재생: 받은 `model_input`으로 만든 출력. 기본은 `proposed`이며 조항 2개와 조건부 대안 1개(메모의 정확한 발췌를 `original_condition`으로 둔다)를 둔다.
- 메모 표지: 제출마다 다른 문항 문구와 겹치지 않는 20자 이상 메모를 넣고, 응답 전수 검사에서 이 문자열의 연속 15자를 찾는다.

### `scenario_input` (AC2)

| ID | 입력·조작 | 기대 결과 | 근거 |
|---|---|---|---|
| INP-P01 | 기본 방 생성 | 201, `expires_at = created_at + 30일`. 문항 호출 1회, 모델 입력의 `participant_profiles`가 요청과 같다. 완료 뒤 `scenario_status: ready` | SPEC 5절 방 생성, F1 |
| INP-P02 | 세 프로필 모두 `profile_id`·`display_name`만 보냄 | 201. 모델 입력 프로필에 `gender`·`age_band`·`mbti` 키가 없다(null로 채우지 않는다) | AC2 "선택 정보 생략", 처리 정책 "프로필·개인화" |
| INP-P03 | `party_size` 2(프로필 2개)와 8(프로필 8개) | 둘 다 201 | ARCHITECTURE 5절 입력 한도 경계 |
| INP-P04 | 문항 재생 출력을 `s2`(`needs_information`), `s5`(`unsupported`), `s4`(`invalid_input`) 출력으로 바꿈 | `scenario_status`가 출력 상태와 같다. 방장 조회의 `scenario_notice`에 `message`가 있고, `needs_information`이면 `clarification_questions`도 있다. 방장 토큰이 없는 조회에는 `scenario_notice`가 없다 | SPEC 상태별 처리 `ScenarioSet` 행, 문항 프롬프트 "필드와 함수 인자"의 `route_scenario_result` |
| INP-N01 | `party_size` 1, 9(프로필 수도 같게) | 422 `invalid_input`. 방을 만들지 않고 문항 호출 0회 | ARCHITECTURE 5절 입력 한도 |
| INP-N02 | `party_size` 3에 프로필 4개 | 422 `invalid_input`, 문항 호출 0회 | AC2 "수 불일치", SPEC 5절 "프로필 수는 설정 인원과 같다" |
| INP-N03 | `p1` 두 번 | 422 `invalid_input`, 문항 호출 0회 | AC2 "중복 ID" |
| INP-N04 | `p2`의 `display_name`을 `""`로, 또는 키 삭제 | 422 `needs_information`, 문항 호출 0회 | AC2 "프로필 누락", F1(이름·별명 필수), 문항 프롬프트 A절, 결정 2 |
| INP-N05 | `trip.destination` 키 삭제(D절 S2) | 422 `needs_information`, 문항 호출 0회 | AC2, 문항 프롬프트 D절 S2, 결정 2 |
| INP-N06 | `trip.duration_days`를 `"며칠 정도"`로(D절 S3) | 422 `needs_information`, 문항 호출 0회 | AC2, 문항 프롬프트 A절("기간·목적지가 모호하면"), D절 S3, 결정 2 |
| INP-N07 | INP-P04 상태의 방에 `POST /sessions` | 409 `invalid_state` | SPEC 상태별 처리("`scenarios=null`"), F3 |

### `profile_rendering` (AC15)

문항 재생 출력에 토큰을 넣는다. `scenarios/0/scene` 첫 줄에 `{{profile:p1}}이/가`, `{{profile:p2}}은/는`, `{{profile:p3}}과/와`를 넣고, `options/0/label`에도 `{{profile:p2}}`를 넣는다. 조사는 추천 문장과 같은 쌍 표기를 쓴다(결정 3). 문항 프롬프트는 이번에 고치지 않으므로, 실제 모델 문항이 쌍 표기를 쓰는지는 이 케이스로 확인되지 않는다.

| ID | 입력·조작 | 기대 결과 | 근거 |
|---|---|---|---|
| PRF-P01 | `p1`(민준), `p2`(지수) 세션 각각 생성 | `p1` 뷰는 `{{profile:p1}}`을 `당신`, `{{profile:p2}}`를 `지수`로, `p2` 뷰는 반대로 바꾼다. 두 뷰의 `scenario_id`, `option_id` 목록·순서, 토큰 밖 문자열이 같다 | AC15, F2, SPEC 5절 필드 연결 |
| PRF-P02 | 이름 `민준`·`지수`·`하늘`과 `당신`에 이/가·은/는·과/와 | `민준이/민준은/민준과`, `지수가/지수는/지수와`, `당신이/당신은/당신과`. 어느 뷰에도 `당신가`·`당신는`·`당신와`가 없다 | AC15 판정 방법 |
| PRF-P03 | 같은 재생 출력으로 이름만 다른 방 두 개 | 같은 프로필 위치의 뷰끼리 이름 치환 부분만 다르고 나머지 구조·문자열이 같다 | AC15 "이름 변경에 따른 뷰 비교" |
| PRF-P04 | `p3`의 `display_name`을 `{{profile:p2}}`로 등록 | 그 이름은 글자 그대로 표시되고 다시 치환되지 않는다 | SPEC 5절 "이름에 포함된 토큰을 다시 해석하지 않는다"(참여자 토큰 문장을 프로필 토큰에도 적용. 결정 3) |
| PRF-N01 | `p1`에 `gender: 여성`, `age_band: 20대`, `mbti: ENFP` | 방 조회·세션 응답 어디에도 세 키가 없다. 세 값은 문항 문장에 이미 있는 경우를 빼고 나오지 않는다 | AC15, AC3, 규칙 3 |
| PRF-N02 | `render_profile_tokens`에 등록되지 않은 `{{profile:p9}}`가 든 문장 | `render_failed`. 부분 치환 문장을 돌려주지 않는다 | AC15 "없는 프로필 토큰을 거부", SPEC 5절. 모델 출력 단계는 검증기 `unknown_profile_token`이 먼저 막는다 |

### `response_privacy` (AC3, 규칙 3)

| ID | 입력·조작 | 기대 결과 | 근거 |
|---|---|---|---|
| PRV-P01 | 세션 생성 | `privacy_notice`가 SPEC 처리 정책 "응답·결과 공개"의 문장과 글자까지 같다 | AC3 판정 방법 첫 문장. 결정 13 |
| PRV-N01 | 기본 방에서 세 명 제출 → `ready`. 방장 토큰 없이, 그리고 방장 토큰을 붙여 GET 경로 전부(방 조회, 새 세션, 결과, 결과 목록)를 호출 | 응답 JSON 어디에도 §0-A 6의 공개 금지 키가 없다. 메모 표지의 연속 15자, `original_condition` 값, 선택 프로필 값이 없다. 방장 응답도 같다 | AC3, ARCHITECTURE 2절 규칙 3 확인 |
| PRV-N02 | 앱의 경로 표 조회, `GET /api/rooms/{room_code}/submissions/{participant_id}` 요청 | 제출·응답을 돌려주는 GET 경로가 없고 요청은 404 또는 405다 | ARCHITECTURE 2절 "제출 후 응답을 조회하는 API는 없다", AC3 "다른 응답 ID 조회" |
| PRV-N03 | 추천 재생 2회 모두 `action`에 한 메모의 연속 15자를 넣음 | 두 번 모두 검증기 `memo_quote`, `room_status: failed`(`output_invalid`). 결과 조회는 409 `invalid_state`이고 그 문장은 어떤 응답에도 없다 | AC3, AC10, ARCHITECTURE 6절 후처리 위반 |
| PRV-N04 | PRV-N01 진행 중의 표준 출력 로그와 `llm_calls` 행 | 메모 표지, 이름·별명, 선택 프로필 값이 없다 | ARCHITECTURE 8절 마스킹. AC3 밖이라 결정 17 |

### `response_closure` (AC4)

| ID | 입력·조작 | 기대 결과 | 근거 |
|---|---|---|---|
| CLS-P01 | 3명 방에 서로 다른 이름으로 3건 제출 | 세 번째 제출 뒤 `generating` → `ready`. 추천 호출 1회, 모델 입력 `participant_ids` 3개, 응답 3×6개. `included_count: 3`, `excluded_names: []` | AC4, F4, 처리 정책 "제출·자동 생성" |
| CLS-P02 | `p1`, `p1`, `p2` 순서로 3건 제출 | 3건째에 자동 생성. `participant_id` 3개가 모두 다르다. `excluded_names`에 `p3`의 이름이 있다 | AC4 "같은 이름의 별도 제출을 각각 집계", SPEC 5절 필드 연결("중복 이름으로 인원이 채워졌다면 안내") |
| CLS-P03 | 1건 제출 뒤 방장 조기 생성 | 202, 모델 입력 `participant_ids` 1개, `included_count: 1`, `excluded_names` 2개 | AC4 "1건 이상은 허용", 처리 정책 "조기 생성·마감" |
| CLS-P04 | `memo` 정확히 300자, `memo` 생략, `memo: ""` | 모두 201이고 제출 수에 들어간다 | ARCHITECTURE 5절 입력 한도, F3 "선택 메모" |
| CLS-N01 | 0건에서 조기 생성 | 409 `no_submissions`. `room_status: open`, 추천 호출 0회 | AC4 "조기 생성 0건은 거부" |
| CLS-N02 | 마감 전에 만든 세션으로 마감 뒤 제출 | 409 `room_closed`. 제출 수·모델 입력·`included_count`가 그대로다 | AC4 "이후 제출·수정은 거부" |
| CLS-N03 | 2건 제출된 3명 방에서 세 번째 제출과 조기 생성을 동시에 보냄. 새 방으로 20회 반복 | 회마다 추천 호출 1회, 최초 결과 시도 1개. `included_count`는 받아들여진 제출 수(2 또는 3)와 같고, 진 요청은 409 `room_closed`다 | AC4 "동시 제출·조기 요청에서도 최초 생성은 한 번", ARCHITECTURE 5절 상태 기계. 반복 횟수는 결정 18 |
| CLS-N04 | 1건 제출 뒤 조기 생성 두 번을 동시에 보냄 | 하나는 202, 하나는 409 `room_closed`. 추천 호출 1회 | AC4, ARCHITECTURE 6절 동시 요청 |
| CLS-N05 | 2명 방에 1건 제출 뒤 (a) 같은 `scenario_id` 두 번, (b) 다른 문항의 `option_id`, (c) 없는 `scenario_id`, (d) 문항 하나 누락, (e) `memo` 301자로 제출 | 모두 422 `invalid_input`. 제출 수 1 그대로, 자동 생성 없음 | AC4 "유효한 제출 수", SPEC 처리 정책 "한 제출 건은 전체 문항의 답변 묶음", AC5, 규칙 5 |

### `duplicate_name` (AC16)

| ID | 입력·조작 | 기대 결과 | 근거 |
|---|---|---|---|
| DUP-P01 | `p1` 1건 제출 뒤 `p1`, `p2` 세션 생성 | `p1`은 `duplicate_name_notice: true`, `p2`는 `false`. 방 조회의 `p1.has_submission: true`. 두 세션 응답 모두 이전 선택·메모가 없다 | AC16, 처리 정책 "입장·중복 이름", AC3 "이름 재선택" |
| DUP-P02 | `p1`로 두 번째 제출 | 201, 첫 제출과 다른 `participant_id`. 제출 수 2 | AC16 "같은 이름의 두 제출은 별도 ID" |
| DUP-P03 | 같은 `Idempotency-Key`·같은 본문 재전송 | 200, 첫 응답과 같은 `participant_id`·`response_ids`. 제출 수 그대로 | AC16 "전송 재시도는 동일 건", SPEC 5절 필드 연결 |
| DUP-N01 | 같은 키에 다른 `option_id` | 409 `idempotency_conflict`. 처음 저장한 제출이 그대로다 | 결정 14 |
| DUP-N02 | 이미 제출한 세션으로 새 키 제출 | 409 `session_used`. 기존 제출이 그대로다 | AC16 "기존 제출 열람·수정은 허용하지 않는다", SPEC 4절 비포함 |
| DUP-N03 | `Idempotency-Key` 없이 제출 | 422 `invalid_input` | 결정 14 |
| DUP-N04 | 등록되지 않은 `profile_id`로 세션 생성 | 404 `not_found` | SPEC 5절 입장·이름 선택 |

### `host_edit` (AC12, 규칙 2)

준비: 기본 추천 재생으로 `ready`인 방.

| ID | 입력·조작 | 기대 결과 | 근거 |
|---|---|---|---|
| EDT-P01 | `/clauses/0/action`의 문구만 바꾸고 토큰은 그대로 | 201, 새 `result_id`, `kind: host_edited`, `source_result_id`는 원본. 원본 결과의 방장 조회 응답과 DB 행이 편집 전과 같다 | AC12, 처리 정책 "방장 편집", ARCHITECTURE 2절 규칙 2 |
| EDT-P02 | EDT-P01의 수정본을 참여자·방장이 조회 | `label: "방장 수정"`. 검증 결과 필드와 합의·수락 필드가 없다. `pact_status`는 원본과 같다 | AC12, 처리 정책 "방장 편집"(원본 검증 결과를 품질 보증으로 쓰지 않는다), 규칙 2 |
| EDT-P03 | EDT-P01 뒤 같은 AI 원본 `result_id`로 `/clauses/1/action`을 수정 | 201, 새 수정본의 `source_result_id`는 EDT-P01 수정본이다. 새 수정본에 EDT-P01의 `/clauses/0/action` 변경이 남아 있다. AI 원본과 EDT-P01 수정본 행은 그대로다. 참여자 결과 조회는 새 수정본을 보여준다 | 결정 6(최신 수정본에서 시작), AC12 원본 보존, 규칙 2 |
| EDT-N01 | 방장 경로 전부(`generate`, `retry`, `regenerate`, `results`, `select`, `edits`, `role: host` 구독)를 이름 선택 세션만 있고 `X-Host-Token` 없이 호출 | 모두 403 `host_forbidden`. 상태·결과·호출 수가 그대로다 | AC12 "방장 이름 선택만 한 요청은 거부", ARCHITECTURE 5절 |
| EDT-N02 | 다른 방의 유효한 `host_token`으로 편집 | 403 `host_forbidden` | ARCHITECTURE 5절(토큰은 방마다 발급) |
| EDT-N03 | 없는 위치 `/clauses/2/action`에 문장 추가 | 422 `edit_not_allowed`, 새 결과 행 없음 | AC12 "추가 막음" |
| EDT-N04 | `/clauses/1/action`을 `""`로 | 422 `edit_not_allowed` | AC12 "삭제 막음" |
| EDT-N05 | `path`를 `/clauses/0/participant_names`, `/clauses/0/scenario_id`, `/positions/0`, `/conditional_alternatives/0/required_changes/0/original_condition`으로 | 각각 422 `edit_not_allowed` | AC12 "근거·적용 대상 변경을 막고", 결정 4 |
| EDT-N06 | 문장에서 `{{participant:<B>}}`를 지우거나 `{{participant:<없는 ID>}}`를 추가 | 422 `edit_not_allowed` | AC12 "적용 대상 변경", 결정 5 |
| EDT-N07 | 수정 문장에 한 메모의 연속 15자를 넣음 | 422 `memo_quote`, 새 결과 행 없음 | AC3 "방장 수정본에 같이 적용", SPEC 5절 "이 기준은 방장 수정본에도 적용", 규칙 3 |
| EDT-N08 | 없는 `result_id` 편집 | 404 `not_found` | [에이전트 안] |

### `regeneration` (AC17)

| ID | 입력·조작 | 기대 결과 | 근거 |
|---|---|---|---|
| REG-P01 | 최초 정상 결과 뒤 방장 재생성 | 202 → 정상 결과 2개. 두 추천 호출의 `model_input`이 정규화한 JSON으로 같다. 최초 결과가 그대로 남는다 | AC17 "입력 불변·두 결과 보존", 처리 정책 "재생성·실패" |
| REG-P02 | 두 번째 결과 선택, 다시 첫 결과 선택 | 각각 200. 참여자 결과 조회가 마지막에 고른 결과를 보여준다 | AC17 "선택", SPEC 5절 |
| REG-P03 | 재생성 호출이 `timeout` 3회로 실패한 뒤 다시 재생성 | 첫 재생성은 실패 행으로 남고 정상 결과는 1개. 다시 요청하면 202이고 성공해 정상 결과 2개 | AC17 "실패 재시도는 재생성 횟수를 소비하지 않는다", ARCHITECTURE 5절(실패 행은 세지 않는다) |
| REG-N01 | 정상 결과 2개 뒤 재생성 | 409 `regeneration_limit`. 추천 호출 수 그대로 | AC17 "세 번째 정상 생성 거부" |
| REG-N02 | 재생성 진행 중(재생 클라이언트를 대기시킨 상태)에 재생성 | 409 `invalid_state`, 추천 호출 1회 추가에 그친다 | ARCHITECTURE 5절 상태 기계 |
| REG-N03 | 없는 `result_id` 선택, 실패 행 선택 | 각각 404 `not_found`, 409 `invalid_state`. 선택이 바뀌지 않는다 | SPEC 5절 결과 선택 |

### `output_validation` (AC10)

| ID | 입력·조작 | 기대 결과 | 근거 |
|---|---|---|---|
| OUT-P01 | 추천 재생 1회차 `{"status":`(절단), 2회차 정상 | `ready`. 추천 호출 2회, 2회차 `repair_errors`에 `json_invalid`가 있고 `model_input`은 1회차와 같다. 정상 결과 1개라 재생성할 수 있다 | AC10, SPEC 상태별 처리 "이유를 붙여 최대 1회 재요청" |
| OUT-P02 | 1회차 출력이 없는 `response_id`를 인용(`unknown_reference`), 2회차 정상 | `ready`, 추천 호출 2회, `repair_errors`에 `unknown_reference` | ARCHITECTURE 6절 후처리 위반 행 |
| OUT-P03 | OUT-N01 뒤 방장 재시도, 재생 정상 | 202 → `ready`. `model_input`이 OUT-N01 1회차와 같다. 정상 결과 1개라 재생성이 1회 남는다 | SPEC 처리 정책 "재생성·실패", 상태별 처리 마지막 문단 |
| OUT-P04 | 1회차 `rate_limited`(`retry_after: 5`), 2회차 정상 | `ready`. 대기 함수가 5초 대기를 한 번 기록한다 | ARCHITECTURE 6절 일시 오류(`Retry-After`) |
| OUT-N01 | 1회차 루트에 `invented: true`, 2회차 `conditional_only`인데 `clauses`가 있음 | `failed`(`output_invalid`). 추천 호출 정확히 2회, 정상 결과 0개. 결과 조회와 재생성은 409 `invalid_state` | AC10 "다시 실패한 출력을 사용하지 않는다", "정상 결과 재생성 횟수 미소비" |
| OUT-N02 | 3회 모두 `timeout` | `failed`(`call_error`). 추천 호출 3회(최초 + 재시도 2회), 대기 기록 1초·2초(지터 범위 안). 정상 결과 0개 | ARCHITECTURE 6절 일시 오류, SPEC 상태별 처리 "호출 실패는 실행 오류" |
| OUT-N03 | 2회 모두 `response_status: incomplete` | `failed`(`output_invalid`), 추천 호출 2회 | ARCHITECTURE 5절 모델 호출 계약 |
| OUT-N04 | 문항 재생 2회 모두 루트에 `invented: true` | `scenario_status: failed`, 문항 호출 2회. 세션 생성은 409 `invalid_state` | AC10을 문항 단계에도 적용(ARCHITECTURE 6절 출력 형식 오류 행) |
| OUT-N05 | 추천 재생 클라이언트를 응답하지 않게 붙잡아 두고, 현재 시각 함수를 `generating` 전환 뒤 4분 59초와 5분으로 옮김. 그 뒤 붙잡은 호출을 정상 출력으로 풀어 줌 | 4분 59초에는 `generating` 그대로. 5분에 작업이 진행 중인 호출과 남은 재시도를 멈추고 `failed`(`call_error`), 정상 결과 0개. 뒤늦게 끝난 호출의 출력은 정상 결과로 저장하지 않는다. 방장 재시도는 202이고 `model_input`이 처음과 같다 | SPEC 상태별 처리("호출 실패는 실행 오류"), ARCHITECTURE 6절 일시 오류, AC4(최초 생성은 한 번), 결정 12 |
| OUT-N06 | `generating`인데 실행 중인 작업이 없는 방(컨테이너 재시작을 흉내 내 작업을 없앤 상태). 현재 시각 함수를 전환 뒤 9분 59초와 10분으로 옮겨 멈춤 점검 실행 | 9분 59초에는 `generating` 그대로. 10분에는 `failed`(`interrupted`), 정상 결과 0개. 방장 재시도는 202이고 `model_input`이 처음과 같다 | ARCHITECTURE 5절("`generating`에 설정 시간 이상 머문 방은 failed"), 6절 생성 중 중단, 결정 12 |

### `result_export` (AC13)

함수 단위 케이스는 `render.py`의 참여자 토큰 치환 함수(이름은 구현에서 정한다)를 직접 부른다.

| ID | 입력·조작 | 기대 결과 | 근거 |
|---|---|---|---|
| EXP-P01 | 토큰 뒤 은/는·이/가·을/를·과/와·으로/로를 이름 `민준`, `지수`, `하늘`, `Alex`, `7`에 적용 | `민준은/이/을/과/으로`, `지수는/가/를/와/로`, `하늘은/이/을/과/로`, `Alex님은/이/을/과/으로`, `7님은/이/을/과/으로` | AC13, SPEC 5절 필드 연결(ㄹ 받침은 로, 영문·숫자 별명은 '님') |
| EXP-P02 | `p1`(민준) 제출 2건 | `민준(응답 1)은`, `민준(응답 2)은`. 번호는 제출 순서, 조사는 이름 기준 | AC13 "같은 이름의 제출 구분", SPEC 5절. 번호 순서는 결정 9 |
| EXP-P03 | 이름 `{{participant:B}}`로 등록하고 제출 | 그 이름이 글자 그대로 나오고 B로 다시 치환되지 않는다 | SPEC 5절 "이름에 포함된 토큰을 다시 해석하지 않는다" |
| EXP-P04 | 조기 생성(1건) + 조건부 대안 + 방장 수정본 | 공유 결과에 `included_count`, `excluded_names`, `proposed_changes`, `label: "방장 수정"`이 있고 `original_condition` 값이 없다. 참여자 응답과 방장 응답의 공유 결과가 같다 | AC13 판정 방법, 처리 정책 "조기 생성·마감" |
| EXP-P05 | 추천 재생 상태를 `unresolved`, `proposed`, `conditional_only`, `needs_information`로 바꿈 | `unresolved`만 `humor.text`(고정 문구), `humor.explanation`("이번 응답 조건에서는 추천안을 찾지 못했습니다."), `unresolved_conditions`가 함께 있다. 나머지와 `failed`에는 `humor`가 없다 | SPEC 상태별 처리 마지막 문단. AC7 범위의 서버 표시 부분이라 결정 19 |
| EXP-N01 | 치환 함수에 명단에 없는 `{{participant:Z}}` | `render_failed` | AC13 "없는 ID는 표시를 막는다" |
| EXP-N02 | 치환 뒤 토큰이 남는 문장(`{{participant:A}` 같은 깨진 토큰, 추천 문장 속 `{{profile:p1}}`) | `render_failed` | AC13 "남은 토큰은 표시를 막는다", SPEC 5절(문항 토큰과 참여자 토큰은 별도 명단) |
| EXP-N03 | DB에 알 수 없는 참여자 토큰이 든 결과 행을 직접 넣고 결과 조회 | 500 `render_failed`. 응답에 일부 문장도 없다 | AC13, SPEC 5절 "표시 오류". 정상 경로에서는 검증기 `token_invalid`가 먼저 막는다 |

### `push_events` (AC18)

준비: 방장 구독 1개, 참여자 구독 2개, 구독하지 않은 참여자 1명. 가짜 푸시 발송기.

| ID | 입력·조작 | 기대 결과 | 근거 |
|---|---|---|---|
| PSH-P01 | 자동 생성 성공 | 방장 구독에 "협약서가 준비됐어요" 1건, 참여자 구독마다 생성 알림 1건. 총 3건 | AC18, F6, 처리 정책 "알림" |
| PSH-P02 | 자동 생성 실패 뒤 방장 재시도 성공 | 실패 때 방장에게 완료·실패를 묶은 알림 1건, 참여자 0건. 성공 때 방장·참여자 구독마다 생성 알림 1건 | 처리 정책 "알림"(실패 시 완료와 실패, 이후 성공 시 생성 알림), AC18 "실패 후 성공 알림" |
| PSH-P03 | 조기 생성 성공 | 방장·참여자 구독마다 생성 알림 1건 | F6, 결정 11 |
| PSH-P04 | 참여자 구독 하나는 410, 하나는 500을 돌려줌 | 410 구독은 삭제, 500 구독은 남고 기록만 한다. 방 상태는 `ready`, 다른 구독 발송은 그대로 | ARCHITECTURE 6절 푸시 발송 실패 |
| PSH-N01 | 같은 생성 완료 이벤트 처리를 두 번 실행 | 추가 발송 0건. 이벤트·구독 쌍마다 알림 기록 1개 | AC18 "이벤트 재처리 시 중복 방지", ARCHITECTURE 6절 알림 중복 |
| PSH-N02 | PSH-P01~P03의 모든 발송 본문 | 이름·별명, 메모 표지, 선택지 문구, 선택 프로필 값이 없고 상태 문구와 방 링크만 있다 | ARCHITECTURE 2절 규칙 3("푸시 본문에는 상태 문구만"), 규칙 3 |
| PSH-N03 | `subscription.endpoint` 없는 구독 등록 | 422 `invalid_input` | SPEC 5절 푸시 등록 |

**케이스 수**: `scenario_input` 11(P4·N7), `profile_rendering` 6(P4·N2), `response_privacy` 5(P1·N4), `response_closure` 9(P4·N5), `duplicate_name` 7(P3·N4), `host_edit` 11(P3·N8), `regeneration` 6(P3·N3), `output_validation` 10(P4·N6), `result_export` 8(P5·N3), `push_events` 7(P4·N3). 합계 80개(통과 35, 실패 45).

**오류 코드별 실패 케이스**

| 코드 | 케이스 |
|---|---|
| `invalid_input` | INP-N01·N02·N03, CLS-N05, DUP-N03, PSH-N03 |
| `needs_information` | INP-N04·N05·N06 |
| `host_forbidden` | EDT-N01·N02 |
| `not_found` | DUP-N04, EDT-N08, REG-N03 |
| `room_closed` | CLS-N02·N03·N04 |
| `no_submissions` | CLS-N01 |
| `invalid_state` | INP-N07, REG-N02·N03, OUT-N01·N04, PRV-N03 |
| `regeneration_limit` | REG-N01 |
| `session_used` | DUP-N02 |
| `idempotency_conflict` | DUP-N01 |
| `edit_not_allowed` | EDT-N03·N04·N05·N06 |
| `memo_quote` | EDT-N07 |
| `render_failed` | PRF-N02, EXP-N01·N02·N03 |

**절대 규칙 2·3을 검사하는 케이스**

- 규칙 2(방장 수정을 합의로 표시하지 않는다, 원본 보존): EDT-P01·P02·P03, EXP-P04, REG-P01. 수정 문장의 합의 표현은 검사하지 않는다(결정 7).
- 규칙 3(원문·검증용 인용·선택 프로필 비공개): PRV 전부, PRF-N01, DUP-P01, EDT-N07, EXP-P04, PSH-N02.

**검사하지 않는 것**

- 화면과 저장 이미지의 일치, DOM 캡처, Web Share는 SPA와 실제 기기 확인(AC13 일부, AC14)이다. 서버 케이스는 화면과 이미지가 같은 공유 결과를 받는다는 데까지만 본다.
- 문항 단계의 도구 루프(`get_scenario_template` 호출 상한 12회)는 재생 모드가 최종 출력만 돌려주므로 실행되지 않는다(결정 16).
- 추천·문항 문장의 의미, 선택 정보로 선호를 추정했는지(AC6~AC9, AC11, AC15 일부)는 evals 범위다.
- 실제 모델 문항이 프로필 토큰 뒤에 조사 쌍 표기를 쓰는지는 검사하지 않는다. 문항 프롬프트를 이번에 고치지 않았다(결정 3).

## 결정한 것 (2026-11-04)

2026-11-04 초안의 "정할 것" 20개 중 1~19에 답했다. 2·3·6·12는 기본안과 다르게 정했고, 나머지는 기본안을 그대로 채택했다. 초안 20(문서 사이 차이)은 아래 22로 처리했다. 20·21은 같은 날 수정본의 "남은 것"에 대한 결정이다.

1. 문항 생성은 방 생성 직후 백그라운드로 시작하고 `scenario_status`를 `room_status`와 따로 둔다.
2. 서버가 모델 호출 전에 입력을 거른다. 필수 값 누락과 해석할 수 없는 기간·목적지 값(`"며칠 정도"` 등)은 `needs_information`, 범위·수·중복 위반은 `invalid_input`이다. 문항 프롬프트 A절("기간·목적지가 모호하면")과 D절 S3를 따른다(INP-N04~N06). 기본안은 타입 오류를 `invalid_input`으로 두었다.
3. 프로필 토큰 뒤 조사도 추천 문장과 같은 쌍 표기(`이/가`, `은/는`, `과/와`)로 치환한다. 이름 안의 토큰은 다시 해석하지 않는다. 문항 프롬프트는 따로 고치지 않는다.
4. 편집할 수 있는 문장은 조항과 조건부 대안의 `action`·`proposed_conditions`·`proposed_change`다.
5. 방장은 토큰을 유지한 문장을 보내고, 토큰의 종류·개수가 시작한 판과 같아야 한다.
6. 방장이 고르기 전에는 최초 정상 결과를 보여준다. 수정본이 있으면 가장 최근 수정본을 보여준다. 다시 고치면 가장 최근 수정본에서 시작해 새 행을 만든다(EDT-P03). 기본안은 늘 AI 원본에서 시작했다.
7. 서버는 `label`과 필드 구조만 보장하고 수정 문장의 합의 표현은 검사하지 않는다.
8. 공유 결과에서 `source_response_ids`, `response_id`, 결과 속 `option_id`를 뺀다.
9. 같은 이름 번호는 제출 순서다. 같은 이름 제출이 하나뿐이면 번호를 붙이지 않는다.
10. 실패 재시도는 방장만 `POST /retry`로 시작한다.
11. 자동 생성 실패 때 방장에게 완료·실패를 묶은 알림 1건을 보낸다. 조기 생성 성공 때 방장에게도 1건을 보낸다. 재생성 성공은 알리지 않는다. 참여자 구독은 세션과 묶는다.
12. 생성 작업 한도와 멈춤 판정을 나눈다. 둘 다 `generating` 전환 시각부터 잰다. 작업 한도는 5분이다. 재시도와 형식 오류 재요청을 포함한 생성 작업 전체가 5분을 넘으면 작업이 스스로 멈추고 `failed`(`call_error`)가 된다(OUT-N05). 멈춤 판정은 10분이다. 작업이 끝나지 않은 채 10분이 지난 방은 `failed`(`interrupted`)가 된다(OUT-N06). 멈춤 판정이 작업 한도보다 길어서 실행 중인 작업이 멈춤으로 판정되지 않는다. 처음 초안은 상한 하나(5분)였다.
13. 제출 전 안내 문구는 서버가 `privacy_notice`로 준다.
14. `Idempotency-Key`는 필수이고, 같은 키에 다른 본문이 오면 409 `idempotency_conflict`다.
15. 테스트에서는 pool 경로를 fixture 입력의 pool로 바꾼다. fixture는 추가하지 않는다.
16. 재생 대기열에 받은 입력으로 출력을 만드는 함수 항목을 허용한다. 문항 도구 루프는 `tests/test_tools.py`와 스파이크에 맡긴다.
17. 로그 마스킹 검사(PRV-N04)를 `response_privacy`에 넣는다.
18. 동시성 케이스(CLS-N03)는 새 방으로 20회 반복한다.
19. 유머 문구 표시(EXP-P05)를 `result_export`에 둔다.

20. `failure_reason`에 `interrupted`를 둔다. ARCHITECTURE 6절 "생성 중 중단"을 형식 오류·호출 오류와 구분한다.
21. 체류 상한 하나 대신 작업 한도와 멈춤 판정을 나눈다(결정 12에 반영). 하나만 두면 재시도가 이어질 때 실행 중인 생성이 실패로 바뀌고 같은 방에 호출이 두 번 나갈 수 있었다. 예를 들어 timeout 재시도 2회를 다 쓰면 호출 하나가 약 4분 33초(90초 × 3 + 대기 1초·2초, 지터 제외)이고, 형식 오류 재요청에서도 같은 일이 생기면 약 9분이다.
22. ARCHITECTURE 2절과 TODO의 서버 테스트 케이스 ID를 이번 범위 10개로 고쳤다(2026-11-04).
23. 작업 한도에 동시 생성 상한(4건) 초과 대기 시간도 들어간다. 두 시간 모두 `generating` 전환 시각부터 재기 때문이다. 사람이 몰리면 모델을 부르기 전에 한도를 넘을 수 있으나, 실제 호출 10회 측정(ARCHITECTURE 5절) 뒤 값을 다시 본다.

## §1. 프롬프트 원본

아직 없음.

## §2. 회차별 결과

아직 없음.
