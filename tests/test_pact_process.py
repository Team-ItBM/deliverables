import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from travel.pact import model_input_for_pact  # noqa: E402
from travel.server.render import process_items  # noqa: E402

TALLY = [{"label": "고기국수", "count": 2}, {"label": "갈치조림", "count": 1}]
MODEL_INPUT = {
    "participant_ids": ["A", "B", "C"],
    "scenarios": [{"scenario_id": "separate_menu", "question": "점심?"}, {"scenario_id": "ride_participation"},
                  {"scenario_id": "sunset_window"}, {"scenario_id": "unknown_x", "question": "{{profile:p1}}과/와 같이 할까?"}],
    "responses": [],
    "judgments": [
        {"scenario_id": "separate_menu", "outcome": "challenge", "decided_label": "고기국수",
         "first_tally": [{"label": "고기국수", "count": 1}, {"label": "갈치조림", "count": 1}],
         "challenge_tally": TALLY, "challenged": True},
        {"scenario_id": "ride_participation", "outcome": "majority", "decided_label": "빠른 기구", "first_tally": TALLY},
        {"scenario_id": "sunset_window", "outcome": "discussion", "tied_labels": ["노을", "소품숍"],
         "first_tally": TALLY, "challenge_tally": TALLY, "challenged": True},
        {"scenario_id": "unknown_x", "outcome": "agreed", "decided_label": "함께"},
    ],
}
OUTPUT = {
    "status": "ready",
    "clauses": [
        {"scenario_id": "separate_menu", "basis": "challenge", "text": "가."},
        {"scenario_id": "ride_participation", "basis": "limit", "text": "나."},
        {"scenario_id": "unknown_x", "basis": "agreed", "text": "라."},
    ],
    "discussion_items": [{"scenario_id": "sunset_window", "text": "다."}],
}


def test_process_uses_judgment_tallies_and_hides_limit_counts():
    items = process_items(OUTPUT, MODEL_INPUT)
    assert [i["label"] for i in items] == ["제1조", "제2조", "제3조", "협의 사항"]
    assert items[0]["decision"] == "챌린지로 정함" and items[0]["challenge_tally"] == TALLY
    assert items[1]["decision"] == "일행의 조건을 반영해 정함"
    assert "first_tally" not in items[1] and "challenge_tally" not in items[1]
    assert items[3]["decision"] == "챌린지에서도 갈려 직접 논의" and items[3]["first_tally"] == TALLY
    assert items[2]["title"] == "일행과 같이 할까?"


def test_process_without_judgments_shows_decision_only():
    model_input = {k: v for k, v in MODEL_INPUT.items() if k != "judgments"}
    items = process_items(OUTPUT, model_input)
    assert all("first_tally" not in i for i in items)
    assert items[0]["decision"] == "챌린지로 정함"


def test_model_input_drops_display_fields():
    payload = model_input_for_pact(MODEL_INPUT)
    assert payload["judgments"][0] == {"scenario_id": "separate_menu", "outcome": "challenge", "decided_label": "고기국수"}
    assert "first_tally" in MODEL_INPUT["judgments"][0]
    assert "judgments" not in model_input_for_pact({"scenarios": []})
