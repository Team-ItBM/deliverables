# Team ItBM · 여행 동행 협약서

친구와 자유여행을 떠나기 전, 같은 가상 상황에 각자 답하고 서로의 바람과 한계를 반영한 추천 협약서를 확인하는 모바일 웹이다. 이 저장소에는 프로젝트의 조사·설계·검증 산출물을 모았다.

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
| 4강 · 기술 타당성 실험 | [문항 선정·각색](docs/spikes/scenario_adaptation.md), [추천 협약서 품질](docs/spikes/grounded_pact.md) |

[질문 pool 50개](src/travel/data/scenario_pool.json) · [남은 작업](TODO.md) · [강의 작성지침](references/course/00_README.md)
