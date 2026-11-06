"""저장 출력 재생 모드(ARCHITECTURE 5절 "저장 출력 재생 모드"). 실제 모델을 부르지 않는다.

- 문항 단계: `config/replay/scenario_set_d01.json`의 실제 Sol 출력(2026-11-05 A'', pool v3)을 그대로 돌려준다.
  여행 정보와 무관하게 같은 문항이 나오므로 시연 장애 대비·로컬 실행용이다. README에 모의 처리임을 밝힌다.
- 추천 단계: 받은 model_input의 응답 전부를 근거로 묶은 `proposed` 출력을 코드로 만든다. 문장은 고정 문구이며
  메모를 인용하지 않는다. 조율 품질이 아니라 흐름 확인용이다.
요청에 든 메모·이름은 데이터로만 다루고 로그에 남기지 않는다.
"""

import asyncio
import json
from pathlib import Path

from .llm import LLMResult

CLAUSE_PHRASES = (
    "하고 싶은 일을 먼저 말하고, 서로 필요한 시간을 확인해요",
    "쉬고 싶은 정도를 먼저 말하고, 다시 만날 때를 함께 정해요",
    "비용이 걱정되면 먼저 말하고, 각자 낼 수 있는 범위를 맞춰요",
)
PROPOSED_CONDITIONS = (
    "따로 움직이기 전에 다시 만날 시간과 장소를 함께 정해요.",
    "일정을 바꾸기 전에 각자 남은 체력을 한 번 확인해요.",
)
UNRESOLVED_DESCRIPTION = "응답한 조건이 서로 달라 이 상황의 추천 조항을 정하지 못했어요."


def token(participant_id):
    return "{{participant:" + participant_id + "}}"


def synthesize_pact(model_input):
    """model_input의 처음 세 상황을 조항으로, 나머지를 미해결 사유로 묶은 proposed 출력(토큰 그대로)."""
    scenario_ids = [s.get("scenario_id", s.get("template_id")) for s in model_input["scenarios"]]
    responses = model_input["responses"]
    participant_ids = model_input["participant_ids"]

    def for_scenario(sid):
        rows = [r for r in responses if r["scenario_id"] == sid]
        authors = [p for p in participant_ids if any(r["participant_id"] == p for r in rows)]
        return rows, authors

    clauses = []
    unresolved = []
    for i, sid in enumerate(scenario_ids):
        rows, authors = for_scenario(sid)
        if not rows:
            continue
        if i < 3:
            action = "비슷한 상황이 오면 " + ", ".join(f"{token(p)}은/는 {CLAUSE_PHRASES[i % 3]}" for p in authors) + "."
            clauses.append({"scenario_id": sid, "action": action, "participant_ids": authors,
                            "source_response_ids": [r["response_id"] for r in rows],
                            "proposed_conditions": [PROPOSED_CONDITIONS[i % 2]]})
        else:
            unresolved.append({"scenario_id": sid, "source_response_ids": [r["response_id"] for r in rows],
                               "description": UNRESOLVED_DESCRIPTION})
    output = {
        "status": "proposed",
        "clauses": clauses,
        "positions": [{"response_id": r["response_id"], "position": {"desired_action": "고른 선택지에 따른 행동을 원한다"}}
                      for r in responses],
    }
    if unresolved:
        output["unresolved_conditions"] = unresolved
    return output


class ReplayClient:
    """llm.py 경계의 재생 구현."""

    def __init__(self, scenario_file):
        data = json.loads(Path(scenario_file).read_text(encoding="utf-8"))
        self.scenario_set = data["scenario_set"] if "scenario_set" in data else data

    async def generate(self, stage, model_input, repair_errors=None):
        await asyncio.sleep(0)
        if stage == "scenarios":
            raw = json.dumps(self.scenario_set, ensure_ascii=False)
        elif stage == "pact":
            raw = json.dumps(synthesize_pact(model_input), ensure_ascii=False)
        else:
            raise ValueError(f"모르는 단계 {stage}")
        return LLMResult(raw_output=raw, response_status="completed", usage={"model": "replay"})
