"""승부처 분류: 문항별 응답을 통함·중간 안·승부처로 가른다.

모델을 부르지 않는 결정 함수만 둔다. 같은 입력이면 항상 같은 결과를 낸다.
규칙 문장과 절충 후보는 src/travel/data/showdown_rules.json에서 읽는다(문항 pool과 template_id·option_id가 같다).
판정 규칙은 docs/SHOWDOWN.md 2절을 따른다. 응답 문자열은 데이터로만 다루며 판정 규칙을 바꾸지 않는다.
"""

import json
from fractions import Fraction
from pathlib import Path

RULES_PATH = Path(__file__).resolve().parent / "data" / "showdown_rules.json"

# 표로 세지 않는 선택지(어느 쪽이든·다른 의견·정보 필요). pool의 option_id 접미사 규약을 따른다.
NEUTRAL_SUFFIXES = ("_any", "_other", "_info")
# 승부처 상한 비율(2026-11-25 팀 결정: 문항의 20%).
SHOWDOWN_RATIO_PERCENT = 20

OUTCOME_AGREED = "agreed"  # 표가 모두 같다
OUTCOME_MIDDLE = "middle"  # 갈렸지만 누군가 중간 선택지를 골랐다
OUTCOME_OPEN = "open"  # 표로 셀 응답이 없다
OUTCOME_SHOWDOWN = "showdown"  # 갈렸고 상한 안에 들어 승부처로 올린다
OUTCOME_FALLBACK = "fallback"  # 갈렸지만 상한을 넘어 기본 절충안을 적용한다

_rules = None


def load_rules():
    """규칙 파일을 한 번 읽어 캐시한 객체를 돌려준다. 호출자는 이 객체를 수정하지 않는다."""
    global _rules
    if _rules is None:
        with RULES_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("templates"), dict):
            raise ValueError("규칙 파일에 templates 객체가 없다")
        _rules = data
    return _rules


def is_neutral(option_id):
    """표로 세지 않는 선택지인지 돌려준다."""
    return isinstance(option_id, str) and option_id.endswith(NEUTRAL_SUFFIXES)


def showdown_limit(question_count):
    """문항 수에 대한 승부처 상한. 20%를 반올림한다(6·7문항 1개, 8문항 2개)."""
    if not isinstance(question_count, int) or isinstance(question_count, bool) or question_count < 0:
        raise ValueError(f"question_count는 0 이상의 정수여야 한다: {question_count!r}")
    return (question_count * SHOWDOWN_RATIO_PERCENT + 50) // 100


def _template_rules(template_id):
    templates = load_rules()["templates"]
    if not isinstance(template_id, str) or template_id not in templates:
        raise KeyError(template_id)
    return templates[template_id]


def tally(template_id, option_ids):
    """한 문항의 응답을 선택지별로 센다.

    반환: (positions, neutral_count). positions는 규칙 파일의 선택지 순서를 따르고 표가 있는 선택지만 담는다.
    규칙 파일에 없는 선택지는 ValueError를 낸다.
    """
    options = _template_rules(template_id)["options"]
    counts = {}
    neutral = 0
    for option_id in option_ids:
        if is_neutral(option_id):
            neutral += 1
        elif option_id in options:
            counts[option_id] = counts.get(option_id, 0) + 1
        else:
            raise ValueError(f"{template_id}에 없는 선택지: {option_id!r}")
    positions = [
        {"option_id": option_id, "kind": spec["kind"], "tag": spec["tag"], "count": counts[option_id]}
        for option_id, spec in options.items()
        if option_id in counts
    ]
    return positions, neutral


def classify_scenario(template_id, option_ids):
    """한 문항을 agreed·middle·open·contested 중 하나로 가른다.

    contested는 중간 단계 값이다. classify_room이 상한을 적용해 showdown이나 fallback으로 바꾼다.
    """
    spec = _template_rules(template_id)
    positions, neutral = tally(template_id, option_ids)
    votes = sum(p["count"] for p in positions)
    base = {"template_id": template_id, "votes": votes, "neutral": neutral}
    if not positions:
        return {**base, "outcome": OUTCOME_OPEN}
    if len(positions) == 1:
        option_id = positions[0]["option_id"]
        return {**base, "outcome": OUTCOME_AGREED, "option_id": option_id, "rule": spec["options"][option_id]["rule"]}
    middles = [p for p in positions if p["kind"] == "middle"]
    if middles:
        # 중간 선택지가 둘 이상이면 표가 많은 쪽, 같으면 규칙 파일에서 앞선 쪽(max는 처음 만난 최댓값을 돌려준다).
        option_id = max(middles, key=lambda p: p["count"])["option_id"]
        return {**base, "outcome": OUTCOME_MIDDLE, "option_id": option_id, "rule": spec["options"][option_id]["rule"]}
    return {
        **base,
        "outcome": "contested",
        "sides": [{"option_id": p["option_id"], "tag": p["tag"], "kind": p["kind"]} for p in positions],
        "top_count": max(p["count"] for p in positions),
        "compromises": [dict(c) for c in spec["compromises"]],
    }


def _tightness_key(indexed):
    """팽팽한 문항이 먼저 오게 하는 정렬 키. 1위 표의 비율이 낮을수록, 표가 많을수록, 문항 순서가 앞설수록 먼저다."""
    index, item = indexed
    # 부동소수 오차를 피하려고 Fraction으로 비교한다.
    return (Fraction(item["top_count"], item["votes"]), -item["votes"], index)


def classify_room(scenarios):
    """방 전체 문항을 분류하고 승부처 상한을 적용한다.

    scenarios: [{"template_id": str, "option_ids": [str, ...]}, ...] (문항 표시 순서).
    반환: 같은 순서의 결과 list. 갈린 문항 중 가장 팽팽한 것부터 상한만큼 showdown, 나머지는 fallback(첫 절충 후보 적용)이다.
    """
    results = [classify_scenario(s["template_id"], s["option_ids"]) for s in scenarios]
    limit = showdown_limit(len(results))
    contested = sorted(((i, r) for i, r in enumerate(results) if r["outcome"] == "contested"), key=_tightness_key)
    for rank, (index, item) in enumerate(contested):
        item.pop("top_count")
        if rank < limit:
            item["outcome"] = OUTCOME_SHOWDOWN
        else:
            item["outcome"] = OUTCOME_FALLBACK
            item["rule"] = item["compromises"][0]["rule"]
        results[index] = item
    return results


def summarize(results):
    """결과 화면 머리말에 쓸 개수. settled는 규칙이 정해진 문항(통함·중간 안·기본 절충안) 수다."""
    settled = sum(1 for r in results if r["outcome"] in (OUTCOME_AGREED, OUTCOME_MIDDLE, OUTCOME_FALLBACK))
    return {
        "total": len(results),
        "settled": settled,
        "showdown": sum(1 for r in results if r["outcome"] == OUTCOME_SHOWDOWN),
        "open": sum(1 for r in results if r["outcome"] == OUTCOME_OPEN),
    }
