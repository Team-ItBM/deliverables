![도원결의 · 떠나기 전에, 서로의 마음을 한 장에.](docs/assets/readme-banner.png)

# 도원결의 · Team ItBM

도원결의는 친구·연인·가족 등 동행과 자유여행을 떠나기 전, 같은 가상 상황에 각자 답하고 서로의 바람과 한계를 반영한 추천 협약서를 확인하는 모바일 웹이다. 이 저장소에는 프로젝트의 조사·설계·검증 산출물을 모았다.

## 팀

| 역할 | 이름 | 학번 |
|---|---|---|
| 팀장 | 전민규 | 202126856 |
| 팀원 | 김민승 | 202020760 |
| 팀원 | 김진수 | 202020821 |

## 산출물

| 강의 | 문서 |
|---|---|
| 2강 · 도메인 발견 | [인터뷰·관찰·Job Story](docs/research/interviews.md), [온톨로지](docs/ontology.yaml) |
| 3강 · 구조화 출력 | [문항 선정·각색](src/travel/prompts/prepare_scenarios.md), [응답 입장 추출·추천 생성](src/travel/prompts/generate_pact.md), [출력 스키마](src/travel/schemas/) |
| 4강 · 문제 정의와 스펙 | [문제 정의서](docs/PROBLEM.md), [제품 스펙](docs/SPEC.md), [에이전트 작업 규칙](AGENTS.md) |
| 4강 · 기술 타당성 실험 | [문항 선정·각색](docs/spikes/scenario_adaptation.md), [추천 협약서 품질](docs/spikes/grounded_pact.md), [문항 도구 호출](docs/spikes/scenario_tool_call.md) |
| 5강 · 위임·검증 | [골든 케이스·하니스](tests/), [위임 기록](docs/prompts/) |
| 6강 · 아키텍처·도구 | [아키텍처 설계서](docs/ARCHITECTURE.md), [도구](src/travel/tools/), [서버](src/travel/server/), [화면](web/), [인프라](infra/) |

[회의록](docs/meetings/README.md) · [질문 pool 50개](src/travel/data/scenario_pool.json) · [남은 작업](TODO.md) · [강의 작성지침](references/course/00_README.md)

## 사용자 가이드

도원결의는 로그인 없이 쓰는 모바일 웹이다. 배포 주소는 `https://dowonpact.com`이다(2026-11-05 첫 배포). 결과는 추천안이며 동행 전원의 합의가 아니다. 개인정보 처리는 [처리방침](docs/PRIVACY.md)을 따른다.

### 역할과 순서

1. 방장이 `/`에서 여행 정보(목적지, 기간, 인원 2~8, 동행 관계)와 동행 전원의 이름·별명을 넣어 방을 만든다. 성별·나이대·MBTI는 선택이며, 넣으면 '동행에게 알렸어요'를 확인한다. 만든 뒤 초대 링크와 방장 링크가 따로 나온다. 방장 링크는 방장만 보관한다(분실하면 복구할 수 없다).
2. 동행은 초대 링크(`/r/<방 코드>`)에서 자기 이름을 고른다. 이미 제출된 이름이면 빨간 안내가 보이지만 계속할 수 있다. 문항은 방을 만든 직후 AI가 준비하며 보통 수십 초 걸린다.
3. 각자 문항 6~8개에 객관식으로 답하고 필요하면 메모(300자)를 쓴다. 제출 전까지 고칠 수 있고, 제출하면 고칠 수 없다. 선택과 메모 원문은 다른 사람에게 보이지 않는다. 건강 상태처럼 조율에 필요 없는 개인 사정은 메모에 쓰지 않는다.
4. 설정 인원만큼 제출되면 자동으로, 또는 방장이 '지금 만들기'를 누르면 모인 응답으로 추천 협약서를 만든다. 생성은 수십 초 걸리고 화면이 폴링으로 상태를 보여 준다.
5. 결과 화면(`/r/<방 코드>/result`)에서 모두가 협약서를 본다. 방장이 고르기 전에는 '초안'으로 표시된다. 방장은 같은 답변으로 한 번 다시 만들 수 있고 둘 중 하나를 고른다. 조항 문구만 고칠 수 있으며 고친 결과에는 '방장 수정'이 붙는다. 결과는 이미지로 저장·공유할 수 있다.
6. 결과가 `unresolved`면 "너네 조합 꽝이니 여행 가지 마세요!"와 "이번 응답 조건에서는 추천안을 찾지 못했습니다.", 막힌 조건이 함께 보인다. 이번 응답 조건에 대한 결과이며 성격이나 궁합 판정이 아니다.

예시 입력: 목적지 `제주`, 기간 `3`일, 인원 `3`, 관계 `친구`, 이름 `민준`·`지수`·`하늘`.

### 다시 실행과 오류

- 생성이 실패하면(`failed`) 방장 화면의 '다시 시도'로 같은 응답으로 다시 만든다. 응답을 다시 받지 않는다.
- 문항을 만들지 못하면 방장 화면의 '문항 다시 만들기'로 다시 시도한다. 그래도 안 되면 '새 방 만들기'로 새 방을 연다. 새 방은 초대 링크가 다르다.
- 재생성이 진행 중이거나 실패해도 방장은 기존 협약서를 열고 고르고 저장할 수 있다.
- 협약서가 있는지 확인하지 못하면 화면의 '다시 확인'을 누른다.
- 제출 결과를 확인하지 못하면 답을 고칠 수 없다. '같은 답으로 다시 보내기'나 '제출 결과 확인하기'로 처음 보낸 답을 그대로 다시 보낸다. 이 답은 결과를 확인하면 기기에서 지우고, 24시간이 지나도 지운다.
- 같은 기기의 다른 탭이나 다른 이름으로 쓴 답이 있으면 '이전 제출 확인하기'를 먼저 누른다. 지금 쓴 답은 남아 있고, 확인이 끝나면 따로 제출한다.
- 요청이 너무 잦으면 잠시 차단될 수 있다. 화면 안내대로 조금 뒤 다시 시도한다.
- 아이폰 Safari는 홈 화면에 추가한 웹앱에서만 푸시 알림을 받는다. 알림이 없어도 화면에서 진행 상태와 결과를 볼 수 있다.

### 미구현·모의 처리·알려진 한계

- 30일 자동 삭제(F7)는 아직 없다. 삭제 요청은 처리방침 제12조의 연락처로 하며 운영팀이 `python -m travel.server.admin delete-room <방 코드>`로 지운다.
- `LLM_MODE=replay`(재생 모드)는 실제 AI를 부르지 않는다. 문항은 저장된 실제 출력 1건을, 추천은 코드로 합성한 고정 문구를 돌려준다. 시연 장애 대비와 로컬 실행용이며 품질 평가에 쓰지 않는다. `web/`의 `npm run dev:mock`도 브라우저 안의 가짜 서버다.
- 방 화면과 협약서 종이의 여행 정보 줄(목적지, 기간, 인원)은 초대 링크로 들어온 모든 사람에게 보인다. 동행 관계는 보이지 않는다.
- 푸시는 Google, Mozilla, Apple 푸시 서비스의 구독만 받는다. Windows의 Edge처럼 다른 서비스를 쓰는 브라우저에서는 '알림을 켜지 못했어요'가 나오고, 화면에서 진행 상태를 볼 수 있다.
- 실기기(아이폰 Safari·안드로이드 Chrome) 확인과 실제 푸시 발송 확인은 아직 하지 않았다.

### 로컬 실행

```sh
python -m pip install -r requirements-dev.txt
docker run -d --name dowon-test-pg -e POSTGRES_PASSWORD=postgres -p 55432:5432 postgres:16
docker exec dowon-test-pg psql -U postgres -c "CREATE DATABASE dowon_local"
cd web && npm ci && npm run build && cd ..
DATABASE_URL=postgresql://postgres:postgres@localhost:55432/dowon_local LLM_MODE=replay DB_INIT_ON_START=1 \
  PUBLIC_BASE_URL=http://localhost:8000 PYTHONPATH=src python -m uvicorn travel.server.main:app --port 8000
```

`http://localhost:8000`에서 화면이 뜬다. 실제 모델을 쓰려면 `LLM_MODE=live`와 `OPENAI_API_KEY`를 준다(비용이 든다). 설정은 `config/llm.yaml`이다. 환경변수 이름은 `src/travel/server/main.py` 머리말에 있다.

서버는 `.env`를 자동으로 읽지 않는다. 값을 파일로 두려면 `.env.example`을 `.env`로 복사해 채우고, 실행 전에 같은 셸에서 불러온다.

```sh
set -a; source .env; set +a
PYTHONPATH=src python -m uvicorn travel.server.main:app --port 8000
```

### 테스트

```sh
python -m pytest tests/ -q -rs                                   # 골든·도구·pool·도구 루프(서버 케이스는 DB 없으면 skip)
TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:55432/postgres python -m pytest tests/test_server_*.py -q -rs   # 서버 계약 116개
ruff check .
```
