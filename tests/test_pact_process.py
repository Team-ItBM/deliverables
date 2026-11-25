import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from travel.pact import (  # noqa: E402
    judgments_from_showdown,
    model_input_for_pact,
    pending_showdowns,
    showdown_board,
    validate_pact_output,
    with_judgments,
)
from travel.server.render import process_items  # noqa: E402

FIXTURE = json.loads((ROOT / "tests" / "harness" / "fixtures" / "pact" / "ready_full.json").read_text(encoding="utf-8"))
BASE = {key: value for key, value in FIXTURE["input"].items() if key != "judgments"}


def _done(how, rule=None, winner="A"):
    result = {"how": how, "rule": rule}
    if how in ("duel", "lottery"):
        result.update({"winner": winner, "option_id": "ride_participation_2"})
    return {"ride_participation": {"phase": "done", "picks": {}, "round": 1, "moves": {}, "last_tie": None,
                                   "result": result}}


def test_board_classifies_example_rooms():
    board = showdown_board(BASE)
    outcomes = [(item["template_id"], item["outcome"]) for item in board["items"]]
    assert outcomes == [("separate_menu", "fallback"), ("private_room", "middle"), ("ride_participation", "showdown"),
                        ("settlement_timing", "agreed"), ("sunset_window", "open")]
    assert pending_showdowns(board, {}) == 1
    assert judgments_from_showdown(BASE, {}) is None
    assert "judgments" not in with_judgments(BASE, {})


def test_finished_showdown_becomes_rule_or_talk():
    talk = judgments_from_showdown(BASE, _done("talk"))
    assert talk == FIXTURE["input"]["judgments"]
    lottery = judgments_from_showdown(BASE, _done("lottery", rule="놀이기구는 잔잔한 것만!"))
    assert lottery[2] == {"scenario_id": "ride_participation", "outcome": "showdown", "how": "lottery",
                          "result": "rule", "rule": "놀이기구는 잔잔한 것만!"}
    assert pending_showdowns(showdown_board(BASE), _done("talk")) == 0


def test_unknown_template_gives_no_judgments():
    model_input = json.loads(json.dumps(BASE))
    model_input["scenarios"][0]["template_id"] = "not_in_rules"
    assert showdown_board(model_input) is None
    assert judgments_from_showdown(model_input, {}) is None
    assert pending_showdowns(None, {}) == 0


def test_model_input_drops_memos_and_display_fields():
    payload = model_input_for_pact(FIXTURE["input"])
    assert all("memo" not in r for r in payload["responses"])
    assert any("memo" in r for r in FIXTURE["input"]["responses"])
    assert payload["judgments"][2] == {"scenario_id": "ride_participation", "result": "talk",
                                       "sides": ["빠른 기구도 같이", "잔잔한 것만", "안 타고 쉬기"]}
    assert payload["judgments"][4] == {"scenario_id": "sunset_window", "result": "open"}
    assert "judgments" not in model_input_for_pact({"scenarios": []})


def test_process_shows_decision_without_counts():
    judgments = judgments_from_showdown(BASE, _done("duel", rule="놀이기구는 잔잔한 것만!"))
    output = {"status": "ready", "discussion_items": [], "clauses": [
        {"scenario_id": item["scenario_id"], "text": "일행은 정한 대로 한다."} for item in judgments]}
    assert validate_pact_output({**BASE, "judgments": judgments}, json.dumps(output))["valid"]
    items = process_items(output, BASE, judgments)
    assert [i["decision"] for i in items] == ["기본 절충안으로 정함", "중간 안으로 정함", "승부처에서 가위바위보로 정함",
                                              "의견이 같아 정함", "그때 정하기로 함"]
    assert all(set(i) == {"label", "scenario_id", "title", "decision"} for i in items)


def test_process_without_judgments():
    items = process_items(FIXTURE["output"], BASE)
    assert [i["decision"] for i in items] == ["응답을 정리해 정함"] * 4 + ["의견이 갈려 직접 논의"]
    talk = process_items(FIXTURE["output"], BASE, FIXTURE["input"]["judgments"])
    assert talk[-1] == {"label": "협의 사항", "scenario_id": "ride_participation", "title": talk[-1]["title"],
                        "decision": "승부처에서 직접 논의하기로 함"}
