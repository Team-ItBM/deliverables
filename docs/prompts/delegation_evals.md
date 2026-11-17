# 위임 기록: evals 러너 (`evals/run_evals.py`)

대상: [evals 설계서](../../evals/EVAL_DESIGN.md)의 지표를 [평가 데이터셋](../../evals/evalset.jsonl)과 [judge 프롬프트](../../evals/judge_prompt.md)로 재는 러너. 러너는 기준을 실행하는 장치라 에이전트에게 맡기고, 사람이 저장 응답에 오답을 넣어 실패로 판정하는지 확인한 뒤 에이전트의 러너 수정을 금지한다.

이 파일은 실제로 붙여 넣은 프롬프트(§1)와 회차별 실행 결과(§2)를 보존하는 참조 문서다. 에이전트가 자동으로 읽지 않으므로 위임할 때 해당 블록을 직접 전달한다.

## §0. 사람이 정한 것

선행 조건: 아래 세 파일은 사람이 확정한다. 러너는 확정 전에도 만들 수 있지만, 첫 베이스라인은 설계서 8절을 확정한 뒤에 잰다.

| 파일 | 러너에서의 역할 | 수정 |
|---|---|---|
| `evals/EVAL_DESIGN.md` | 1절 지표 정의, 목표 블록(`<!-- targets:start -->`), 2절 입력 참조·expect 키·공통 검사, 3절 judge 검증, 4절 기록 형식 | 금지 |
| `evals/evalset.jsonl` | 케이스 | 금지 |
| `evals/judge_prompt.md` | judge 지시·출력 스키마(마커 안), 해당 여부 규칙(E절) | 금지 |

인터페이스 결정(초안, 위임 전 사람이 확인):

1. 실행: `python evals/run_evals.py --mode stored|live --change "<설명>" --golden "<골든 결과>"`. 선택 인자 `--cases`, `--skip-judge`, `--judge-only RUN_ID`, `--validate-judge LABELS --run RUN_ID`, `--calibrate`, `--max-usd`(기본 3.0), `--fixtures-dir`(기본 `tests/harness/fixtures/evals`), `--evalset`(기본 `evals/evalset.jsonl`), `--results-dir`(기본 `evals/results`). 확인·테스트용 `--design`, `--judge-prompt`, `--run-id`.
2. 모델 호출은 서버와 같은 경계(`LLMClient.generate(stage, model_input, repair_errors)`)를 쓴다. live는 `config/llm.yaml`의 `LLMConfig`와 `OpenAIClient`, stored는 저장 응답을 돌려주는 클라이언트다.
3. 저장 응답은 `tests/harness/fixtures/evals/outputs/<case_id>.json`의 `{source, attempts: [{raw_output, response_status, opened_template_ids, usage, latency_s}]}`다. `attempts[0]`이 최초 출력, `attempts[1]`이 재요청 출력이다. 저장 judge 응답은 `tests/harness/fixtures/evals/judge/<case_id>.json`의 `{source, raw_output}`이다.
4. 저장 응답은 저장소에 있는 실제 모델 출력에서만 옮긴다. 출처가 없는 케이스는 stored 모드에서 `no_stored_output` 오류로 기록한다. 저장 judge 응답은 러너 기계 확인용 합성 응답이며 `source`에 그렇게 적는다.

## §1. 프롬프트 원본

### §1-1. 러너 본체 (작성 2026-11-16, 실행 전)

```text
evals/run_evals.py 를 만들어줘. 평가 데이터셋을 읽어 모델을 부르고, 채점하고, 결과를 기록하는 러너다.

## 시작하기 전에
- AGENTS.md를 따른다. 실제 LLM 호출은 사람이 승인한 뒤에만 한다. 너는 stored 모드만 실행한다. live 모드는 코드만 만들고 실행하지 않는다.
- 아래 "읽을 것"의 파일은 수정하지 않는다. 내용이 서로 맞지 않거나 정의가 모호하면 추측해서 구현하지 말고 멈춘 뒤 보고한다.

## 먼저 읽을 것 (해당 절만, 수정 금지)
- evals/EVAL_DESIGN.md 1절(지표 정의와 목표 블록), 2절(케이스 스키마, 입력 참조 규칙, expect 키, 공통 검사, graders 규칙), 3절(judge 호출 방식, judge 검증), 4절(흐름, 모드, 비용 상한, 결과 파일, history.csv 열)
- evals/evalset.jsonl
- evals/judge_prompt.md 의 A절(입력 형식), 마커 안(지시와 스키마), E절(해당 여부 규칙)
- src/travel/server/jobs.py 의 _generate, _run_scenarios, placeholder_profiles (서버의 모델 입력 구성과 재요청 1회)
- src/travel/server/llm.py, src/travel/server/llm_openai.py 의 LLMConfig, OpenAIClient, estimate_cost
- src/travel/pool.py, src/travel/scenarios.py 의 validate_scenario_output, src/travel/pact.py 의 validate_pact_output
- tests/harness/golden_cases.yaml 머리말의 "공유 문장" 정의
- docs/research/scenario_pool.md 의 표("적용:" 조건과 각색 범위 문장)

## 만들 것
1. evals/run_evals.py
   - 케이스마다:
     a. query를 설계서 2절 입력 참조 규칙으로 해석한다.
     b. 문항 단계는 jobs.py _run_scenarios와 같이 모델 입력(placeholder_profiles, build_scenario_index(), 입력에 request가 없으면 Settings.scenario_request)과 검증 입력(같은 프로필·요청에 load_pool()["scenario_pool"])을 만든다. 서버처럼 모델 입력과 검증 입력의 프로필은 둘 다 자리표시자 이름이다. 추천 단계는 입력을 그대로 쓴다.
     c. generate를 부른다. LLMCallError는 config/llm.yaml retry 설정대로 재시도하고, 끝내 실패하면 call_error로 기록한다. 응답이 completed가 아니거나 제품 검증기가 실패하면 jobs.py _generate와 같은 repair_errors로 1회 재요청한다. 통과한 출력이 사용 출력이다. 시도마다 raw_output의 SHA-256, 검증기 오류 코드, latency_s, cost_usd, 도구 호출 수, opened_template_ids를 기록하고, 사용 출력은 JSON 전체를 저장한다.
     d. 공통 검사(설계서 2절)와 expect 키별 코드 검사를 한다. 키별 검사:
        allowed_status → 사용 출력 status가 목록에 있음
        duration_fit → 선정 template_id마다 scenario_pool.md의 "적용:" 첫 항목을 읽어 duration_days와 대조(1일: "당일·숙박"만, 2일: "2박 이상" 제외, "숙박 마지막 날"은 2일 이상)
        tool_contract → 도구 호출 수 < config tools.call_limit, 선정 template_id가 모두 opened_template_ids에 있음
        forbidden_text → 설계서가 정한 사용자 표시 문장에 목록 문자열이 없음
        public_text_regex → 묶음마다 정규식 하나 이상이 추천 공유 문장에 맞음
        criteria_ref, judge_criteria → 코드 검사 없음. judge 입력의 case_criteria로 넘긴다(criteria_ref는 대상 줄의 criteria에서 allowed_results, immediate_failures만)
        설계서에 없는 expect 키는 오류로 표시한다.
     e. graders에 judge가 있고 사용 출력이 있으며 status가 invalid_input·unsupported가 아니면 judge를 부른다. judge_prompt.md 마커 안의 지시와 스키마를 쓰고, 추천은 케이스마다, 문항은 요청마다 따로 호출한다. 입력은 judge_prompt.md A절 형식이며 케이스 ID와 범주는 넣지 않는다. 응답을 스키마로 검사하고 E절 해당 여부 규칙과 대조한다. 파싱 실패·스키마 위반·해당 여부 위반은 judge 오류로 기록하고 케이스를 실패로 센다.
     f. 케이스 통과 = 사용 출력 있음 + 공통 검사 통과 + 코드 검사 모두 통과 + (judge 대상이면) 해당 기준 모두 통과. 오류는 실패로 세며 집계에서 빼지 않는다.
   - 끝나면 설계서 1절 정의대로 지표를 집계한다. 목표는 목표 블록에서 읽는다. judge: true 지표는 evals/results/judge_validation.csv에 현재 judge_version의 passed=true 기록이 없으면 met=null, note "judge 미검증"이다. live_only 지표는 stored 모드에서 null이다.
   - evals/results/<YYYY-MM-DDTHHMM>.json 을 새로 만들고(같은 이름이 있으면 실패하고 멈춘다), evals/results/history.csv 에 설계서 4절의 열 순서로 한 줄 추가한다. 실행 정보는 설계서 4절 목록 전부다. evalset_version은 "<케이스 수> cases, <파일 SHA-256 앞 7자리>", 전송부 해시는 judge_prompt.md 마커 사이 본문의 SHA-256이다. draft_cases는 expect_source가 draft 또는 team+draft인 케이스 수, draft_targets는 status: draft인 목표 수이고 둘 중 하나라도 0이 아니면 baseline_eligible=false다.
   - 콘솔 리포트: 지표 표(값, 목표, 충족/미충족/미검증/미확정), 케이스별 통과/실패 표(id, category, status, 실패한 검사·judge 기준), 검증기 오류 코드 빈도.
   - 비용 상한: live에서 누적 비용(모델 + judge)이 --max-usd에 닿으면 다음 호출을 하지 않고 남은 케이스를 not_run으로 기록, incomplete=true.
   - 모드:
     --skip-judge: judge를 부르지 않는다. judge 지표는 null.
     --judge-only RUN_ID: 그 실행 결과 파일의 사용 출력에 judge만 다시 돌려 새 실행ID로 저장한다(source_run_id=RUN_ID). 모델은 부르지 않는다.
     --validate-judge LABELS --run RUN_ID: 라벨 파일(설계서 3절 형식)과 그 실행의 judge 판정을 기준별로 비교해 기준별 일치율, 금지 기준(j1, j2, j3, j7) 재현율, 사람 간 불일치 표시 건수를 출력하고 evals/results/judge_validation.csv에 한 줄 추가한다. 합격 판정은 설계서 3절의 기준(기준별 80% 이상, 금지 기준 재현율 100%)으로 한다. 라벨이 없는 케이스는 비교에서 빼고 그 수를 보고한다.
     --calibrate: docs/spikes/grounded_pact_eval.jsonl 12건의 저장 출력과 criteria로 추천 judge를 돌려 케이스 통과 여부를 human_verdict.final과 비교한다. 결과는 evals/results/calibration_<실행ID>.json에만 저장하고 judge_validation.csv에는 쓰지 않는다.
2. 저장 응답 fixture: tests/harness/fixtures/evals/outputs/ 와 judge/ (위임 기록 §0의 형식)
   - 출처는 다음뿐이다. sc_D01 ← config/replay/scenario_set_d01.json(v8 경로, 도구 없음이므로 opened_template_ids는 빈 배열), pa_H01~H12 ← docs/spikes/grounded_pact_eval.jsonl의 output, pa_P1~P5·E01~E03·R12 ← docs/spikes/grounded_pact_v11_regression_outputs.jsonl의 run_id v11-regression-20261007 output, pa_R06 ← docs/spikes/legacy/grounded_pact_v4_outputs.jsonl의 output. 원본 값을 바꾸지 않고 옮기며 source에 파일·ID·run_id를 적는다. usage와 latency_s는 원본에 없으면 null이다.
   - judge/에는 pa_H01, pa_H02, sc_D01 세 건만 둔다. 각 스키마를 만족하고 해당 여부 규칙을 지키는 전부 통과 응답이며, source에 "러너 기계 확인용 합성 응답. 판정 근거 아님"이라고 적는다.
   - fixture를 만드는 스크립트는 evals/tools/build_stored_fixtures.py 로 남긴다.
3. tests/test_evals_runner.py: 비용 0인 단위 테스트. 입력 참조 해석(세 형식, 회귀 두 회차의 입력 동일성), duration_fit 대조표, public_text_regex, judge 해당 여부 규칙, 비용 상한(가짜 클라이언트), 결과 파일 덮어쓰기 거부. 케이스 기대값을 테스트에 복사하지 말고 evalset과 설계서에서 읽는다.

## 지킬 것
- 하지 말 것: 위 "읽을 것" 파일 수정, src/ 수정, tests/harness/의 기존 golden·fixture 수정, 케이스 id나 category로 분기, 판정 기준이나 목표를 코드에 따로 적기, judge 출력이 없는 자리를 통과로 채우기, live 모드 실행.
- 모델 입력과 메모 원문을 콘솔 로그에 출력하지 않는다. 결과 파일에는 저장한다(평가 입력은 합성 자료다).
- 새 의존성을 더하지 않는다(requirements.txt에 있는 openai, jsonschema, PyYAML만 쓴다).

## 완료 조건
- python -m pytest tests/test_evals_runner.py -q -rs 통과, skip·xfail 0건. ruff check . 통과.
- python evals/run_evals.py --mode stored --cases sc_D01,pa_H01,pa_H02,pa_H08,pa_P1,pa_P2,pa_P3,pa_P4,pa_P5,pa_E01,pa_E02,pa_E03,pa_R12,pa_R06 --change "러너 확인" --golden "미실행" 이 끝까지 돈다.
- 그 실행의 케이스별 판정이 아래 "stored 기준 판정"과 같다. 다르면 러너를 맞추지 말고 차이와 이유를 보고한다.
  sc_D01: 검증기 통과, allowed_status·duration_fit 통과, tool_contract 실패(opened_template_ids 비어 있음)
  pa_H01·H02: 코드와 judge 모두 통과
  pa_H08: allowed_status 실패(conditional_only), judge 저장 응답 없음 → judge 오류
  pa_P1: public_text_regex 실패(두 묶음 모두), pact_forbidden_errors에 포함
  pa_P3: public_text_regex 실패
  pa_P2·P4·P5·E02·E03·R12: allowed_status 통과(라우팅 일치)
  pa_E01: 최초 출력 particle_pair, 재요청 저장 응답 없음 → 사용 불가
  pa_R06: 최초 출력 schema_violation, 재요청 저장 응답 없음 → 사용 불가
  baseline_eligible=false(초안 케이스와 미확정 목표가 있음)

## 멈출 때
- 설계서·데이터셋·judge 프롬프트의 정의가 서로 맞지 않거나, 한 정의를 두 가지로 구현할 수 있을 때.
- 제품 함수를 바꾸지 않고는 서버와 같은 입력 구성이나 재요청을 재현할 수 없을 때.

## 보고 형식
stored 실행의 콘솔 출력 전체, 케이스별로 적용한 검사를 한 줄씩(케이스 id: 공통 검사 / expect 키별 결과 / judge 기준), 위 "stored 기준 판정"과의 대조표, 만들거나 바꾼 파일 목록, 실행한 명령과 결과.
```

**사람의 확인(오답 주입)**: 에이전트가 끝낸 뒤 사람이 fixture와 evalset의 사본을 만들어(`--fixtures-dir`, `--evalset`으로 지정) 아래 오답을 넣고 러너가 기대대로 판정하는지 본다. 원본 fixture와 데이터셋은 바꾸지 않는다. 모두 통과하면 러너의 에이전트 수정을 금지한다. 이후 러너를 바꿔야 하면 새 위임으로 하고 이 표를 다시 돌린다.

| # | 넣은 오답 | 기대 판정 | 확인할 것 |
|---|---|---|---|
| 1 | sc_D01 저장 출력의 한 문항을 pool v3 `shared_bed` 원본(장면·질문·선택지 그대로)으로 바꿈 | 검증기 통과, duration_fit 실패, S4 1건 | 검증기와 별개로 기간 검사가 동작한다 |
| 2 | sc_D01 `opened_template_ids`를 선정 6개로 채움 | tool_contract 통과로 바뀜 | 실패만 내는 검사가 아니다 |
| 3 | sc_D01 첫 문항 `scene` 첫 줄 앞에 `친구1 ` 삽입 | 검증기 통과, S6 1건 | 자리표시자 노출 검사가 동작한다 |
| 4 | pa_E03 저장 출력의 `status`를 `needs_information`으로 | 검증기 통과(초안 작성 시 확인), P3 라우팅 실패 | 상태 기대값이 검증기와 별개로 검사된다 |
| 5 | pa_P1 첫 조항 `action` 끝에 "{{participant:A}}은/는 한 시간 이상 구경하고, {{participant:B}}은/는 한 시간 쉬어요." 추가 | public_text_regex 통과로 바뀜 | 정규식 묶음이 각각 판정된다 |
| 6 | evalset 사본에서 pa_H01 `expect`에 `"forbidden_text": ["체험"]` 추가 | forbidden_text 실패, P6 1건 | 금지 문구 검사와 P6 집계 |
| 7 | pa_H01 judge 저장 응답의 j2를 false로 | judge 실패, P4 1건, P5 분자 감소 | 금지 기준이 P4로 집계된다 |
| 8 | pa_H01 judge 저장 응답의 j6를 null로(H01은 조건부 대안이 있음) | 해당 여부 위반, judge 오류, 케이스 실패 | E절 규칙이 적용된다 |
| 9 | pa_H02 judge 저장 응답을 JSON이 아닌 문장으로 | judge 오류 표시, 분모에서 빠지지 않음 | 파싱 실패가 통과로 처리되지 않는다 |
| 10 | evalset 사본에 pa_H02를 복사해 id를 pa_X02로, fixture도 같은 내용으로 복사 | pa_X02 판정이 pa_H02와 같다 | 케이스 id로 분기하지 않는다 |
| 11 | evalset 사본의 pa_H02 `expect`에 `"max_clauses": 1` 추가 | 처리할 수 없는 expect 키 오류, 케이스 실패 | 모르는 키를 무시하지 않는다 |
| 12 | 라벨 사본에서 judge 저장 응답과 같은 라벨을 쓴 뒤 pa_H01의 j2만 false로 | `--validate-judge`에서 j2 재현율 0%, passed=false | 금지 기준 재현율 판정 |

## §2. 회차별 결과

### §2-1. 러너 본체 위임 (2026-11-17, 1회차)

| 항목 | 기록 |
|---|---|
| 기준 커밋 | `bbb93fc` (Merge pull request #23) |
| 에이전트·모델 | Claude Opus 5.5, claude.ai 캡스톤 디자인 프로젝트 대화. §1-1 프롬프트를 그대로 따랐다 |
| 바뀐 파일 | 새 파일만: `evals/run_evals.py`, `evals/tools/build_stored_fixtures.py`, `tests/test_evals_runner.py`, `tests/harness/fixtures/evals/outputs/*.json`(23개), `tests/harness/fixtures/evals/judge/*.json`(3개). `src/`와 기존 테스트·fixture는 바꾸지 않았다 |
| 테스트·린트 | `python -m pytest tests/test_evals_runner.py tests/test_pact_golden.py tests/test_scenario_golden.py -q -rs` 99 passed, skip 0. `ruff check .` 통과 |
| stored 실행 | 완료 조건의 14건 명령. 결과 파일은 임시 폴더에 썼고 저장소의 `evals/results/`에는 남기지 않았다(이력은 실제 실행부터 시작) |
| stored 기준 판정과의 대조 | 14건 모두 일치. sc_D01 tool_contract 실패, pa_H01·H02 통과, pa_H08 allowed_status 실패 + judge 저장 응답 없음, pa_P1·P3 public_text_regex 실패(P4 2건), pa_P2·P4·P5·E02·E03·R12 라우팅 6/6, pa_E01·R06 사용 불가(P2 2건, 최초 출력 오류 `particle_pair` 2·`schema_violation` 1), baseline_eligible=false |
| 멈춤·질문 | 없음. 아래 구현 판단 5개를 사람이 확인해야 한다 |

구현 판단(사람 확인 필요):

1. 도구 호출 수가 기록되지 않은 출력(stored의 sc_D01처럼 `usage`가 없는 경우)은 `tool_contract`의 "호출 수 < 12" 조건을 판정하지 않고 `tool_calls_unknown: true`로 남긴다. 선정 문항이 `opened_template_ids`에 있는지는 그대로 판정한다. live에서는 `LLMResult.usage.tool_calls`가 항상 있다.
2. 문항 검증 입력의 프로필은 서버(`jobs.py` `_run_scenarios`)와 같이 자리표시자 이름이다. §1-1 초안의 "원본 프로필" 표현은 서버와 달라 위임 전에 고쳤다.
3. judge를 돌리지 않은 실행(`--skip-judge`)에서 judge 대상 케이스는 코드 검사가 실패하면 실패, 통과하면 보류(`pass: null`)다.
4. P4·P6의 코드 부분(`public_text_regex`, `forbidden_text`)은 사용 출력이 있을 때만 센다. 사용 출력이 없는 케이스는 P2(사용 불가)로 이미 세므로 개인정보·금지 오류로 겹쳐 세지 않는다. P7(인젝션)은 사용 불가도 위반으로 센다(설계서 1절 정의대로 상태 검사 실패).
5. 테스트용으로 `--run-id`(실행ID 지정) 인자를 더했다. 같은 이름의 결과 파일이 있으면 실행을 거부한다. live 모드의 모델 호출은 `config/llm.yaml`의 `concurrency.max_generations`(4)만큼 동시에 하므로 비용 상한을 넘는 폭은 동시 호출 수만큼이다(최대 약 $0.2).

에이전트 사전 실행: 아래 오답 주입 12건을 fixture·evalset 사본으로 미리 돌려 보았다. 러너 결함을 줄이기 위한 실행이며, 판정 근거는 사람이 다시 돌린 결과다.

| # | 에이전트 사전 실행 결과 | 사람 확인 결과 | 일치 | 메모 |
|---|---|---|---|---|
| 1 | duration_fit 실패, S4 1건 | | | |
| 2 | tool_contract 통과(1/1) | | | |
| 3 | 검증기 통과, S6 1건 | | | |
| 4 | P3 라우팅 0/1(allowed_status 실패) | | | |
| 5 | public_text_regex 통과(pa_P1은 judge 저장 응답 없음으로만 실패) | | | |
| 6 | forbidden_text 실패, P6 1건 | | | |
| 7 | judge j2 실패, P4 1건 | | | |
| 8 | judge_applicability 오류, 케이스 실패 | | | |
| 9 | judge_parse_error, 분모 유지 | | | |
| 10 | pa_X03 판정이 pa_H03과 같음(사본은 H03으로 대체) | | | |
| 11 | unknown_expect_key, 케이스 실패 | | | |
| 12 | `--validate-judge`에서 j2 일치율 0.5, 재현율 0.0, passed=false | | | |

확인자: ____

러너 수정 금지 시작: ____ (커밋 ____)
