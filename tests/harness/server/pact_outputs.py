"""추천 출력 도우미: 서버가 보낸 추천 단계 model_input으로 PactRecommendation을 만든다.

model_input은 SPEC 5절 {participant_ids, scenarios, responses, request}다. 문항 ID는 scenarios[].scenario_id
(없으면 template_id)를 쓴다. 기본 출력(proposed)은 §0-1 공통 준비를 따른다.
  조항 2개   : 첫째·둘째 문항. 그 문항의 응답 전부를 근거로, 응답한 참여자 전부를 적용 대상으로 둔다.
  조건부 대안: 셋째 문항. required_changes 하나의 original_condition은 그 문항 응답 메모의 정확한 발췌(앞 16자)다.
               셋째 문항 응답에 메모가 하나도 없으면 고른 선택지 문구를 쓴다(검증기가 허용하는 다른 인용원).
  나머지 문항: unresolved_conditions로 연결해 모든 응답이 어딘가에 연결되게 한다.
문장은 참여자마다 {{participant:ID}}은/는 쌍 표기를 쓴다. 메모 문자열은 데이터로만 다룬다.
"""

import copy
import json

from .replay import Produce, Text

ORIGINAL_CONDITION_LENGTH = 16
QUOTE_LENGTH = 15

CLAUSE_PHRASES = (
    "하고 싶은 일을 먼저 말하고, 서로 필요한 시간을 확인해요",
    "쉬고 싶은 정도를 먼저 말하고, 다시 만날 때를 함께 정해요",
)
ALTERNATIVE_PHRASE = "조건을 조금 바꾸면 함께할 수 있는지 먼저 이야기해요"
PROPOSED_CONDITIONS = (
    "따로 움직이기 전에 다시 만날 시간과 장소를 함께 정해요.",
    "일정을 바꾸기 전에 각자 남은 체력을 한 번 확인해요.",
)
PROPOSED_CHANGE = "원래 바람을 지키되 시간을 조금 줄여 보는 방법을 제안해요."
UNRESOLVED_DESCRIPTION = "응답한 조건이 서로 달라 이 상황의 추천 조항을 정하지 못했어요."
MESSAGES = {
    "conditional_only": "원래 조건을 모두 지키는 조항은 찾지 못해 조건부 대안만 제안해요.",
    "needs_information": "이 응답만으로는 조율 조건을 정하기 어려워요.",
    "unresolved": "검토한 방식으로는 추천안을 찾지 못했어요.",
}

VARIANTS = (
    "proposed", "unresolved", "conditional_only", "needs_information",
    "json_truncated", "extra_key", "status_combination", "unknown_response", "memo_quote",
)
# 변형마다 validate_pact_output이 내야 하는 오류 코드. 빈 목록은 통과해야 한다는 뜻이다.
VARIANT_ERRORS = {
    "proposed": [],
    "unresolved": [],
    "conditional_only": [],
    "needs_information": [],
    "json_truncated": ["json_invalid"],
    "extra_key": ["schema_violation"],
    "status_combination": ["status_combination"],
    "unknown_response": ["unknown_reference"],
    "memo_quote": ["memo_quote"],
}
TRUNCATED_OUTPUT = '{"status":'
UNKNOWN_RESPONSE_ID = "response-not-in-input"


def scenario_ids(model_input):
    ids = []
    for scenario in model_input["scenarios"]:
        sid = scenario.get("scenario_id", scenario.get("template_id"))
        ids.append(sid)
    return ids


def _responses_for(model_input, sid):
    return [r for r in model_input["responses"] if r.get("scenario_id") == sid]


def _participants(model_input, responses):
    authors = {r.get("participant_id") for r in responses}
    ordered = [p for p in model_input["participant_ids"] if p in authors]
    ordered += sorted(a for a in authors if a not in ordered)
    return ordered


def token(participant_id):
    return "{{participant:" + participant_id + "}}"


def _action(participants, phrase):
    parts = [f"{token(p)}은/는 {phrase}" for p in participants]
    return "비슷한 상황이 오면 " + ", ".join(parts) + "."


def _option_label(model_input, response):
    for scenario in model_input["scenarios"]:
        if scenario.get("scenario_id", scenario.get("template_id")) != response.get("scenario_id"):
            continue
        for option in scenario.get("options") or []:
            if option.get("option_id") == response.get("option_id"):
                return option.get("label")
    return None


def _positions(model_input):
    return [
        {"response_id": r["response_id"], "position": {"desired_action": "고른 선택지에 따른 행동을 원한다"}}
        for r in model_input["responses"]
    ]


def _clause(model_input, sid, n):
    responses = _responses_for(model_input, sid)
    participants = _participants(model_input, responses)
    return {
        "scenario_id": sid,
        "action": _action(participants, CLAUSE_PHRASES[n % len(CLAUSE_PHRASES)]),
        "participant_ids": participants,
        "source_response_ids": [r["response_id"] for r in responses],
        "proposed_conditions": [PROPOSED_CONDITIONS[n % len(PROPOSED_CONDITIONS)]],
    }


def original_condition_for(model_input, response):
    memo = response.get("memo")
    if isinstance(memo, str) and memo:
        return memo[:ORIGINAL_CONDITION_LENGTH]
    return _option_label(model_input, response)


def _alternative(model_input, sid):
    responses = _responses_for(model_input, sid)
    participants = _participants(model_input, responses)
    with_memo = [r for r in responses if isinstance(r.get("memo"), str) and r["memo"]]
    target = (with_memo or responses)[0]
    return {
        "scenario_id": sid,
        "action": _action(participants, ALTERNATIVE_PHRASE),
        "participant_ids": participants,
        "source_response_ids": [r["response_id"] for r in responses],
        "proposed_conditions": [],
        "required_changes": [{
            "source_response_id": target["response_id"],
            "original_condition": original_condition_for(model_input, target),
            "proposed_change": PROPOSED_CHANGE,
        }],
    }


def _unresolved(model_input, sids):
    return [
        {
            "scenario_id": sid,
            "source_response_ids": [r["response_id"] for r in _responses_for(model_input, sid)],
            "description": UNRESOLVED_DESCRIPTION,
        }
        for sid in sids
        if _responses_for(model_input, sid)
    ]


def pact_output(model_input, variant="proposed"):
    """변형 이름에 맞는 출력을 dict로 돌려준다. json_truncated는 문자열을 돌려준다."""
    if variant not in VARIANTS:
        raise ValueError(f"모르는 변형 {variant}")
    if variant == "json_truncated":
        return TRUNCATED_OUTPUT
    sids = scenario_ids(model_input)
    if len(sids) < 3:
        raise ValueError("추천 출력 도우미는 문항 3개 이상을 전제로 한다")
    positions = _positions(model_input)

    if variant in ("proposed", "extra_key", "unknown_response", "memo_quote"):
        output = {
            "status": "proposed",
            "clauses": [_clause(model_input, sids[0], 0), _clause(model_input, sids[1], 1)],
            "conditional_alternatives": [_alternative(model_input, sids[2])],
            "positions": positions,
        }
        rest = _unresolved(model_input, sids[3:])
        if rest:
            output["unresolved_conditions"] = rest
        if variant == "extra_key":
            output["invented"] = True
        elif variant == "unknown_response":
            output["clauses"][0]["source_response_ids"].append(UNKNOWN_RESPONSE_ID)
        elif variant == "memo_quote":
            quote = memo_quote_text(model_input)
            output["clauses"][0]["action"] += " " + quote
        return output

    if variant in ("conditional_only", "status_combination"):
        output = {
            "status": "conditional_only",
            "clauses": None,
            "conditional_alternatives": [_alternative(model_input, sids[0])],
            "unresolved_conditions": _unresolved(model_input, sids[1:]),
            "message": MESSAGES["conditional_only"],
            "positions": positions,
        }
        if variant == "status_combination":
            output["clauses"] = [_clause(model_input, sids[1], 0)]
        return output

    # unresolved, needs_information: 조항·대안 없이 모든 응답을 미해결 사유에 연결한다.
    return {
        "status": variant,
        "clauses": None,
        "unresolved_conditions": _unresolved(model_input, sids),
        "message": MESSAGES[variant],
        "positions": positions,
    }


def memo_quote_text(model_input):
    """입력 메모 하나의 앞 15자. 15자 이상인 메모가 없으면 ValueError."""
    for response in model_input["responses"]:
        memo = response.get("memo")
        if isinstance(memo, str) and len(memo) >= QUOTE_LENGTH:
            return memo[:QUOTE_LENGTH]
    raise ValueError("15자 이상인 메모가 없어 메모 인용 변형을 만들 수 없다")


def pact_raw(model_input, variant="proposed"):
    output = pact_output(model_input, variant)
    return output if isinstance(output, str) else json.dumps(output, ensure_ascii=False)


def pact_item(variant="proposed", response_status="completed"):
    """재생 대기열 항목. 호출될 때 받은 model_input으로 출력을 만든다."""
    return Produce(lambda model_input: Text(pact_raw(model_input, variant), response_status), label=variant)


def incomplete_item():
    """response_status가 incomplete인 응답. 본문은 기본 출력이다(서버는 상태만으로 형식 오류로 처리해야 한다)."""
    return pact_item("proposed", response_status="incomplete")


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
    return {"participant_ids": list(participants), "scenarios": scenario_list, "responses": responses,
            "request": "각자의 조건을 보존하는 추천 조항을 만들어줘."}


def original_conditions(output):
    """출력 dict에서 original_condition 값을 모두 꺼낸다."""
    values = []
    for alternative in output.get("conditional_alternatives") or []:
        for change in alternative.get("required_changes") or []:
            values.append(change["original_condition"])
    return values
