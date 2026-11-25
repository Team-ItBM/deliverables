"""승부처 분류와 진행: 문항별 응답을 통함·중간 안·승부처로 가르고, 승부처의 선택·승부를 처리한다.

모델을 부르지 않는다. 분류는 같은 입력이면 항상 같은 결과를 낸다. 무작위는 제비뽑기 한 곳에만 쓴다.
규칙 문장과 절충 후보는 src/travel/data/showdown_rules.json에서 읽는다(문항 pool과 template_id·option_id가 같다).
판정 규칙은 docs/SHOWDOWN.md 2절을 따른다. 응답 문자열은 데이터로만 다루며 판정 규칙을 바꾸지 않는다.
"""

import json
import secrets
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


# ---- 승부처 진행 ----
# 상태는 {template_id: entry} dict이며 JSON으로 저장할 수 있다. entry는 _new_entry()의 모양이다.
# 판정 규칙은 docs/SHOWDOWN.md 2절 "승부처 카드"를 따른다.

CHOICES = ("c0", "c1", "duel", "talk")  # 절충 후보 1, 절충 후보 2, 승부하기, 토론해서 정하기
MOVES = ("rock", "paper", "scissors")
_BEATS = {"rock": "scissors", "scissors": "paper", "paper": "rock"}

PHASE_VOTING = "voting"
PHASE_DUEL = "duel"
PHASE_DONE = "done"


class ShowdownError(Exception):
    """승부처 요청을 처리할 수 없다. code는 not_found, forbidden, invalid_input, invalid_state 중 하나다."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def build_board(model_input):
    """고정된 추천 입력(participant_ids, scenarios, responses)에서 문항별 분류와 참여자별 선택을 만든다.

    규칙 파일에 없는 문항이 있으면 KeyError, 없는 선택지가 있으면 ValueError를 낸다.
    """
    participant_ids = list(model_input["participant_ids"])
    known = set(participant_ids)
    answers = {s["template_id"]: {} for s in model_input["scenarios"]}
    for response in model_input["responses"]:
        scenario_answers = answers.get(response["scenario_id"])
        if scenario_answers is not None and response["participant_id"] in known:
            scenario_answers[response["participant_id"]] = response["option_id"]
    scenarios = [
        {"template_id": tid, "option_ids": [answers[tid][pid] for pid in participant_ids if pid in answers[tid]]}
        for tid in answers
    ]
    return {"participant_ids": participant_ids, "answers": answers, "items": classify_room(scenarios)}


def _new_entry():
    return {"phase": PHASE_VOTING, "picks": {}, "round": 1, "moves": {}, "last_tie": None, "result": None}


def _showdown_item(board, template_id):
    for item in board["items"]:
        if item["template_id"] == template_id and item["outcome"] == OUTCOME_SHOWDOWN:
            return item
    raise ShowdownError("not_found")


def duelists(board, template_id):
    """승부에 참여하는 사람: 그 문항에서 표로 세는 선택지를 고른 참여자(제출 순서)."""
    answers = board["answers"].get(template_id, {})
    return [pid for pid in board["participant_ids"] if pid in answers and not is_neutral(answers[pid])]


def _option_rule(template_id, option_id):
    return _template_rules(template_id)["options"][option_id]["rule"]


def _finish_votes(board, item, entry, rng):
    template_id = item["template_id"]
    picks = list(entry["picks"].values())
    if "talk" in picks:
        entry["result"] = {"how": "talk", "rule": None}
    elif len(set(picks)) == 1 and picks[0] in ("c0", "c1"):
        entry["result"] = {"how": "compromise", "rule": item["compromises"][int(picks[0][1])]["rule"]}
    else:
        players = duelists(board, template_id)
        if len(players) == 2:
            entry["phase"] = PHASE_DUEL
            return
        winner = rng.choice(players)
        option_id = board["answers"][template_id][winner]
        entry["result"] = {"how": "lottery", "winner": winner, "option_id": option_id, "rule": _option_rule(template_id, option_id)}
    entry["phase"] = PHASE_DONE


def pick(board, state, template_id, participant_id, choice, rng=None):
    """승부처 카드에서 한 사람의 선택을 기록한다. 전원이 고르면 결과를 정하거나 승부로 넘어간다. state를 고쳐 돌려준다."""
    item = _showdown_item(board, template_id)
    if participant_id not in board["participant_ids"]:
        raise ShowdownError("forbidden")
    if choice not in CHOICES:
        raise ShowdownError("invalid_input")
    entry = state.setdefault(template_id, _new_entry())
    if entry["phase"] != PHASE_VOTING:
        raise ShowdownError("invalid_state")
    entry["picks"][participant_id] = choice
    if all(pid in entry["picks"] for pid in board["participant_ids"]):
        _finish_votes(board, item, entry, rng or secrets.SystemRandom())
    return state


def close_voting(board, state, template_id, rng=None):
    """방장이 지금까지 모인 선택으로 마감한다. 한 명 이상 골라야 한다."""
    item = _showdown_item(board, template_id)
    entry = state.setdefault(template_id, _new_entry())
    if entry["phase"] != PHASE_VOTING or not entry["picks"]:
        raise ShowdownError("invalid_state")
    _finish_votes(board, item, entry, rng or secrets.SystemRandom())
    return state


def move(board, state, template_id, participant_id, hand):
    """가위바위보에서 한 사람의 패를 기록한다. 둘 다 내면 승패를 정하고, 비기면 다음 판으로 넘어간다."""
    _showdown_item(board, template_id)
    entry = state.get(template_id)
    if entry is None or entry["phase"] != PHASE_DUEL:
        raise ShowdownError("invalid_state")
    players = duelists(board, template_id)
    if participant_id not in players:
        raise ShowdownError("forbidden")
    if hand not in MOVES:
        raise ShowdownError("invalid_input")
    if participant_id in entry["moves"]:
        raise ShowdownError("invalid_state")
    entry["moves"][participant_id] = hand
    if len(entry["moves"]) < 2:
        return state
    first, second = players
    if entry["moves"][first] == entry["moves"][second]:
        entry["last_tie"] = hand
        entry["round"] += 1
        entry["moves"] = {}
        return state
    winner = first if _BEATS[entry["moves"][first]] == entry["moves"][second] else second
    option_id = board["answers"][template_id][winner]
    entry["result"] = {"how": "duel", "winner": winner, "option_id": option_id,
                       "rule": _option_rule(template_id, option_id), "moves": dict(entry["moves"])}
    entry["moves"] = {}
    entry["phase"] = PHASE_DONE
    return state


def _showdown_view(board, item, entry, viewer_id, names):
    template_id = item["template_id"]
    players = duelists(board, template_id)
    voters = board["participant_ids"]
    view = {
        "sides": [side["tag"] for side in item["sides"]],
        "compromises": [c["rule"] for c in item["compromises"]],
        "phase": entry["phase"],
        "mode": "rps" if len(players) == 2 else "lottery",
        "voter_count": len(voters),
        "picked_count": len(entry["picks"]),
        "can_pick": viewer_id in voters and entry["phase"] == PHASE_VOTING,
        "my_pick": entry["picks"].get(viewer_id),
    }
    if entry["phase"] == PHASE_DUEL:
        view["duel"] = {
            "is_player": viewer_id in players,
            "round": entry["round"],
            "moved_count": len(entry["moves"]),
            "my_move": entry["moves"].get(viewer_id),
            "last_tie": entry["last_tie"],
        }
    result = entry["result"]
    if result is not None:
        shown = {"how": result["how"], "rule": result["rule"]}
        # 이긴 사람의 이름은 모두에게 보인다(2026-11-25 팀 결정). 본인의 승패와 낸 패는 승부에 참여한 본인에게만 간다.
        if result["how"] in ("duel", "lottery"):
            winner_name = names.get(result["winner"])
            if winner_name:
                shown["winner_name"] = winner_name
        if result["how"] in ("duel", "lottery") and viewer_id in players:
            shown["won"] = result["winner"] == viewer_id
        if result["how"] == "duel" and viewer_id in players:
            other = next(pid for pid in players if pid != viewer_id)
            shown["my_move"] = result["moves"][viewer_id]
            shown["other_move"] = result["moves"][other]
        view["result"] = shown
    return view


def build_view(board, state, viewer_id=None, titles=None, names=None):
    """화면에 줄 응답을 만든다. 입장별 인원수와 진행 중인 선택은 싣지 않는다.

    names는 {participant_id: 표시 이름}이다. 주면 승부가 끝난 뒤 이긴 사람의 이름을 싣는다.
    """
    titles = titles or {}
    names = names or {}
    items = []
    for item in board["items"]:
        template_id = item["template_id"]
        row = {"scenario_id": template_id, "title": titles.get(template_id), "outcome": item["outcome"], "rule": item.get("rule")}
        if item["outcome"] == OUTCOME_SHOWDOWN:
            entry = state.get(template_id) or _new_entry()
            row["showdown"] = _showdown_view(board, item, entry, viewer_id, names)
            if entry["result"] is not None:
                row["rule"] = entry["result"]["rule"]
        items.append(row)
    showdowns = [row for row in items if "showdown" in row]
    return {
        "available": True,
        "is_participant": viewer_id in board["participant_ids"],
        "summary": {
            "total": len(items),
            "settled": sum(1 for row in items if row["rule"] is not None),
            "showdown": len(showdowns),
            "showdown_open": sum(1 for row in showdowns if row["showdown"]["phase"] != PHASE_DONE),
        },
        "items": items,
    }
