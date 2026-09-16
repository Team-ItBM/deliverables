# Team ItBM · Deliverables

프로젝트의 조사·설계·구현·검증 자료를 관리합니다. 인터뷰에서 얻은 근거를 요구사항으로 정리하고, 구현 결과를 판단할 기준으로 연결합니다.

## 팀

| 역할 | 이름 | 학번 |
|---|---|---|
| 팀장 | 전민규 | 202126856 |
| 팀원 | 김민승 | 202020760 |
| 팀원 | 김진수 | 202020821 |

## 문서 안내

- [팀 Notion](https://app.notion.com/p/3cf6c0cfe17f80b88461d1019f9f4bc7): 인터뷰 원자료, 회의록, 할 일
- [작업 규칙](AGENTS.md): 용어, 근거 관리, 변경·검증 기준
- [작성지침](references/course/00_README.md): 산출물 형식과 저장 경로
- [도메인 발견 작성지침](references/course/02/강의02_도메인발견_온톨로지_작성지침.md)
- [구조화 출력 작성지침](references/course/03/강의03_구조화출력_작성지침.md)
- [인터뷰 기록](docs/research/interviews.md), [온톨로지](docs/ontology.yaml)

## 산출물의 연결

```text
인터뷰·관찰 → 문제 정의·Job Story·온톨로지 → 스키마·스펙
스펙의 수용 기준 → 골든 케이스 → 구현 검증·평가 → 개선
```

각 판단에는 원문이나 이전 산출물의 근거를 연결합니다. 앞 단계의 내용이 바뀌면 영향을 받는 뒤 단계도 함께 갱신합니다.

## 작성 위치

산출물을 작성할 때 아래 경로에 추가합니다.

| 내용 | 경로 |
|---|---|
| 인터뷰 프로토콜·로그·분석·관찰·Job Story | `docs/research/interviews.md` |
| 도메인 개념·속성·관계와 근거 | `docs/ontology.yaml` |
| 문제 정의·제품 스펙·수용 기준 | `docs/PROBLEM.md`, `docs/SPEC.md` |
| 기술 타당성 검증·아키텍처 | `docs/spikes/`, `docs/ARCHITECTURE.md` |
| 구조화 출력·제품 프롬프트·도구 구현 | `src/<패키지>/schemas/`, `src/<패키지>/prompts/`, `src/<패키지>/tools/` |
| AI 위임·검증 기록 | `docs/prompts/delegation_examples.md` |
| RAG 설정·예시 데이터 | `config/rag.yaml`, `data/seed/` |
| 골든 케이스·테스트 | `tests/harness/golden_cases.yaml`, `tests/` |
| 평가 설계·데이터셋·실행 결과 | `evals/` |
