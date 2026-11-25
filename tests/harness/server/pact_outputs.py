"""추천 출력 도우미: 서버가 보낸 추천 단계 model_input(고정 입력, 승부처 결과로 만든 judgments)으로 협약서 출력(스키마 v7)을 만든다.

기본 출력(ready)은 정해진 문항(result rule·open)을 조항, 직접 논의 문항(result talk)을 협의 사항으로 쓴다.
판정이 없으면 모든 문항을 조항으로 둔다. 문장은 고정 문구다.
변형은 검증기가 거부해야 하는 출력을 만든다.
"""

import copy
import json

from .replay import Produce, Text

CLAUSE_TEXT = "응답에서 정해진 방향을 여행 중 원칙으로 한다."
DISCUSSION_TEXT = "이 상황에서 무엇을 우선할지는 당사자 간 직접 논의하여 정한다."
QUOTE_LENGTH = 15
MESSAGES = {"needs_information": "채택된 응답 중 빠진 문항이 있어 협약서를 만들지 않았다."}

VARIANTS = (
    "ready", "needs_information",
    "json_truncated", "extra_key", "status_combination", "unknown_scenario", "talk_as_clause",
)
VARIANT_ERRORS = {
    "ready": [],
    "needs_information": ["input_status_mismatch"],
    "json_truncated": ["json_invalid"],
    "extra_key": ["schema_violation"],
    "status_combination": ["status_combination"],
    "unknown_scenario": ["unknown_reference"],
    "talk_as_clause": ["judgment_mismatch"],
}
TRUNCATED_OUTPUT = '{"status":'
UNKNOWN_SCENARIO_ID = "scenario-not-in-input"


def scenario_ids(model_input):
    return [s.get("scenario_id", s.get("template_id")) for s in model_input["scenarios"]]


def token(participant_id):
    return "{{participant:" + participant_id + "}}"


def _subject(model_input):
    ids = list(model_input["participant_ids"])
    if not ids:
        return ""
    return "비슷한 상황이 오면 " + ", ".join(token(p) + "은/는" for p in ids) + " "


def _judgments(model_input):
    if model_input.get("judgments"):
        return model_input["judgments"]
    return [{"scenario_id": sid, "result": "rule"} for sid in scenario_ids(model_input)]


def pact_output(model_input, variant="ready"):
    if variant not in VARIANTS:
        raise ValueError(f"모르는 변형 {variant}")
    if variant == "json_truncated":
        return TRUNCATED_OUTPUT
    if variant == "needs_information":
        return {"status": "needs_information", "clauses": [], "discussion_items": [],
                "message": MESSAGES["needs_information"]}
    clauses = []
    discussion = []
    for item in _judgments(model_input):
        if item["result"] == "talk" and variant != "talk_as_clause":
            discussion.append({"scenario_id": item["scenario_id"], "text": DISCUSSION_TEXT})
        else:
            clauses.append({"scenario_id": item["scenario_id"], "text": _subject(model_input) + CLAUSE_TEXT})
    output = {"status": "ready", "clauses": clauses, "discussion_items": discussion}
    if variant == "extra_key":
        output["invented"] = True
    elif variant == "status_combination":
        output["message"] = "협약서를 만들었다."
    elif variant == "unknown_scenario":
        target = output["clauses"] or output["discussion_items"]
        target[0]["scenario_id"] = UNKNOWN_SCENARIO_ID
    return output


def pact_raw(model_input, variant="ready"):
    output = pact_output(model_input, variant)
    return output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)


def pact_item(variant="ready", response_status="completed"):
    """재생 대기열 항목. 호출될 때 받은 model_input으로 출력을 만든다."""
    return Produce(lambda model_input: Text(pact_raw(model_input, variant), response_status), label=variant)


def incomplete_item():
    """response_status가 incomplete인 응답. 본문은 기본 출력이다(서버는 상태만으로 형식 오류로 처리해야 한다)."""
    return pact_item("ready", response_status="incomplete")


def sample_pact_input(scenarios, participants, memo=True):
    """도우미 검사용 model_input. participants는 participant_id 목록이고 같은 이름 제출도 다른 ID다."""
    scenario_list = []
    for scenario in scenarios:
        item = copy.deepcopy(scenario)
        item.setdefault("scenario_id", item.get("template_id"))
        scenario_list.append(item)
    responses = []
    for p_index, participant_id in enumerate(participants):
        for s_index, scenario in enumerate(scenario_list):
            response = {
                "response_id": f"r-{participant_id}-{s_index}",
                "participant_id": participant_id,
                "scenario_id": scenario["scenario_id"],
                "option_id": scenario["options"][p_index % len(scenario["options"])]["option_id"],
            }
            if memo:
                response["memo"] = f"메모표지{participant_id}{s_index} 보라색 우산을 든 고양이 이야기"
            responses.append(response)
    judgments = [
        {"scenario_id": scenario["scenario_id"], "result": "talk", "sides": ["한쪽", "다른 쪽"]} if i == 0
        else {"scenario_id": scenario["scenario_id"], "result": "rule", "rule": "정해진 규칙!"}
        for i, scenario in enumerate(scenario_list)
    ]
    return {"participant_ids": list(participants), "scenarios": scenario_list, "responses": responses,
            "request": "일행의 응답과 승부처 결과로 협약서를 만들어줘.", "judgments": judgments}


def original_conditions(output):
    return []
