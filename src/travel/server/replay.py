"""저장 출력 재생 모드(ARCHITECTURE 5절 "저장 출력 재생 모드"). 실제 모델을 부르지 않는다.

- 문항 단계: `config/replay/scenario_set_d01.json`의 실제 Sol 출력(2026-11-05 A'', pool v3)을 그대로 돌려준다.
  여행 정보와 무관하게 같은 문항이 나오므로 시연 장애 대비·로컬 실행용이다. README에 모의 처리임을 밝힌다.
- 추천 단계: 받은 model_input의 판정(judgments)대로 조항과 협의 사항을 고정 문구로 만든다. 판정이 없으면(챌린지 단계
  연결 전) 모든 문항을 의견이 같은 조항으로 둔다. 메모를 인용하지 않는다. 흐름 확인용이다.
요청에 든 메모·이름은 데이터로만 다루고 로그에 남기지 않는다.
"""

import asyncio
import json
from pathlib import Path

from .llm import LLMResult

CLAUSE_TEXT = "이 상황에서는 응답에서 정해진 방향을 여행 중 원칙으로 한다."
DISCUSSION_TEXT = "이 상황에서 무엇을 우선할지는 당사자 간 직접 논의하여 정한다."


def synthesize_pact(model_input):
    clauses = []
    discussion = []
    judgments = model_input.get("judgments") or [
        {"scenario_id": s.get("scenario_id", s.get("template_id")), "outcome": "agreed"} for s in model_input["scenarios"]
    ]
    for item in judgments:
        if item["outcome"] == "discussion":
            discussion.append({"scenario_id": item["scenario_id"], "text": DISCUSSION_TEXT})
        else:
            clauses.append({"scenario_id": item["scenario_id"], "basis": item["outcome"], "text": CLAUSE_TEXT})
    return {"status": "ready", "clauses": clauses, "discussion_items": discussion}


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
