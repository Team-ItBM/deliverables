"""승부처 분류와 규칙 데이터의 계약 테스트: travel.showdown.

판정 기준은 docs/SHOWDOWN.md 2절(분류 규칙)과 3절(규칙 문장 기준)이다. 기준은 팀 검토 전 제안이다.
기대값은 이 파일에 직접 적고, 규칙 문장 자체는 데이터 파일에서 읽어 비교한다.
"""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
POOL_PATH = ROOT / "src" / "travel" / "data" / "scenario_pool.json"
RULES_PATH = ROOT / "src" / "travel" / "data" / "showdown_rules.json"

if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from travel import showdown  # noqa: E402

KINDS = {"side", "middle", "split"}
COMPROMISE_TYPES = {"alternate", "divide", "split", "middle"}
RULE_MAX_LENGTH = 32
# 한 줄 규칙에 쓰지 않는 표현. 결정을 미루거나 응답을 설명하는 말이다.
BANNED_IN_RULE = ("확인해요", "정해요", "조율", "바람", "추천해요", "제안해요", "{{")


def _pool():
    with POOL_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _rules():
    with RULES_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _all_rule_texts():
    for template_id, spec in _rules()["templates"].items():
        for option_id, option in spec["options"].items():
            yield f"{template_id}/{option_id}", option["rule"]
        for index, compromise in enumerate(spec["compromises"]):
            yield f"{template_id}/compromises/{index}", compromise["rule"]


# ---- 규칙 데이터 계약 ----


def test_rules_cover_pool_templates_in_order():
    pool = _pool()
    rules = _rules()
    assert rules["pool_version"] == pool["pool_version"]
    assert list(rules["templates"]) == [item["template_id"] for item in pool["scenario_pool"]]


def test_rules_cover_every_substantive_option():
    rules = _rules()["templates"]
    for item in _pool()["scenario_pool"]:
        expected = [o["option_id"] for o in item["options"] if not showdown.is_neutral(o["option_id"])]
        assert list(rules[item["template_id"]]["options"]) == expected, item["template_id"]


def test_every_template_has_neutral_options_in_pool():
    # 분류가 접미사 규약에 기대므로 pool이 규약을 지키는지 확인한다.
    for item in _pool()["scenario_pool"]:
        ids = [o["option_id"] for o in item["options"]]
        for suffix in showdown.NEUTRAL_SUFFIXES:
            assert f"{item['template_id']}{suffix}" in ids, item["template_id"]


def test_option_and_compromise_fields():
    for template_id, spec in _rules()["templates"].items():
        assert set(spec) == {"options", "compromises"}, template_id
        for option_id, option in spec["options"].items():
            assert set(option) == {"kind", "tag", "rule"}, option_id
            assert option["kind"] in KINDS, option_id
            assert option["tag"].strip() == option["tag"] and option["tag"], option_id
        assert len(spec["compromises"]) == 2, template_id
        for compromise in spec["compromises"]:
            assert set(compromise) == {"type", "rule"}, template_id
            assert compromise["type"] in COMPROMISE_TYPES, template_id
        assert spec["compromises"][0]["rule"] != spec["compromises"][1]["rule"], template_id
        assert sum(1 for o in spec["options"].values() if o["kind"] == "middle") <= 1, template_id


def test_side_tags_are_distinct_within_template():
    for template_id, spec in _rules()["templates"].items():
        tags = [o["tag"] for o in spec["options"].values()]
        assert len(tags) == len(set(tags)), template_id


@pytest.mark.parametrize("path,text", list(_all_rule_texts()))
def test_rule_text_is_one_short_line(path, text):
    assert text == text.strip() and "\n" not in text, path
    assert 0 < len(text) <= RULE_MAX_LENGTH, f"{path}: {len(text)}자"
    for banned in BANNED_IN_RULE:
        assert banned not in text, f"{path}: {banned}"


# ---- 상한 ----


@pytest.mark.parametrize("count,expected", [(0, 0), (2, 0), (3, 1), (5, 1), (6, 1), (7, 1), (8, 2), (10, 2)])
def test_showdown_limit_rounds_twenty_percent(count, expected):
    assert showdown.showdown_limit(count) == expected


@pytest.mark.parametrize("bad", [-1, 6.0, "6", None, True])
def test_showdown_limit_rejects_non_count(bad):
    with pytest.raises(ValueError):
        showdown.showdown_limit(bad)


# ---- 한 문항 분류 ----


def _rule(template_id, option_id):
    return _rules()["templates"][template_id]["options"][option_id]["rule"]


def test_all_same_is_agreed():
    result = showdown.classify_scenario("route_depth", ["route_depth_1", "route_depth_1", "route_depth_1"])
    assert result["outcome"] == "agreed"
    assert result["option_id"] == "route_depth_1"
    assert result["rule"] == _rule("route_depth", "route_depth_1")


def test_neutral_answers_are_not_counted():
    # "어느 쪽이든"과 "다른 의견"은 표로 세지 않는다(2026-11-25 팀 결정 4).
    result = showdown.classify_scenario("separate_menu", ["separate_menu_2", "separate_menu_any", "separate_menu_other"])
    assert result["outcome"] == "agreed"
    assert result["option_id"] == "separate_menu_2"
    assert result["votes"] == 1 and result["neutral"] == 2


def test_only_neutral_answers_is_open():
    result = showdown.classify_scenario("drink_bill", ["drink_bill_any", "drink_bill_info"])
    assert result["outcome"] == "open"
    assert "rule" not in result


def test_split_with_chosen_middle_takes_middle():
    result = showdown.classify_scenario("route_depth", ["route_depth_2", "route_depth_1", "route_depth_3"])
    assert result["outcome"] == "middle"
    assert result["option_id"] == "route_depth_3"
    assert result["rule"] == _rule("route_depth", "route_depth_3")


def test_split_without_middle_is_contested():
    result = showdown.classify_scenario("separate_menu", ["separate_menu_2", "separate_menu_1", "separate_menu_any"])
    assert result["outcome"] == "contested"
    assert [s["tag"] for s in result["sides"]] == ["생선 요리", "면 요리"]
    assert len(result["compromises"]) == 2
    assert "rule" not in result


def test_split_option_counts_as_a_side_unless_unanimous():
    together = showdown.classify_scenario("walk_or_ride", ["walk_or_ride_1", "walk_or_ride_3"])
    assert together["outcome"] == "contested"
    alone = showdown.classify_scenario("walk_or_ride", ["walk_or_ride_3", "walk_or_ride_3"])
    assert alone["outcome"] == "agreed"


def test_result_does_not_expose_who_or_how_many_per_side():
    # 승부처 카드는 누가 어느 쪽인지, 몇 명인지 보여 주지 않는다.
    result = showdown.classify_scenario("separate_menu", ["separate_menu_1", "separate_menu_1", "separate_menu_2"])
    for side in result["sides"]:
        assert set(side) == {"option_id", "tag", "kind"}


def test_answer_order_does_not_change_outcome():
    a = showdown.classify_scenario("paid_activity", ["paid_activity_2", "paid_activity_1", "paid_activity_3"])
    b = showdown.classify_scenario("paid_activity", ["paid_activity_3", "paid_activity_2", "paid_activity_1"])
    assert a == b


def test_unknown_template_and_option_are_rejected():
    with pytest.raises(KeyError):
        showdown.classify_scenario("no_such_template", [])
    with pytest.raises(ValueError):
        showdown.classify_scenario("route_depth", ["separate_menu_1"])


# ---- 방 전체 분류 ----

# 2026-11-25 실제 서비스에서 만든 3인 방의 응답(민지·서준·하늘 순).
TEST_ROOM = [
    {"template_id": "paid_activity", "option_ids": ["paid_activity_2", "paid_activity_1", "paid_activity_3"]},
    {"template_id": "route_depth", "option_ids": ["route_depth_2", "route_depth_1", "route_depth_3"]},
    {"template_id": "separate_menu", "option_ids": ["separate_menu_2", "separate_menu_1", "separate_menu_any"]},
    {"template_id": "planning_roles", "option_ids": ["planning_roles_2", "planning_roles_1", "planning_roles_3"]},
    {"template_id": "night_planning", "option_ids": ["night_planning_3", "night_planning_1", "night_planning_2"]},
    {"template_id": "drink_bill", "option_ids": ["drink_bill_2", "drink_bill_1", "drink_bill_any"]},
]


def test_room_applies_limit_and_keeps_question_order():
    results = showdown.classify_room(TEST_ROOM)
    assert [r["template_id"] for r in results] == [s["template_id"] for s in TEST_ROOM]
    assert [r["outcome"] for r in results] == ["showdown", "middle", "fallback", "fallback", "middle", "fallback"]
    assert showdown.summarize(results) == {"total": 6, "settled": 5, "showdown": 1, "open": 0}


def test_room_showdown_is_the_tightest_question():
    # 세 명이 모두 다른 문항(1위 비율 1/3)이 둘이다. 표 수도 같아 문항 순서가 앞선 쪽이 승부처다.
    results = showdown.classify_room(TEST_ROOM)
    assert results[0]["outcome"] == "showdown"
    assert results[3]["outcome"] == "fallback"
    assert "top_count" not in results[0]


def test_fallback_uses_first_compromise():
    results = showdown.classify_room(TEST_ROOM)
    rules = _rules()["templates"]
    for index in (2, 3, 5):
        template_id = results[index]["template_id"]
        assert results[index]["rule"] == rules[template_id]["compromises"][0]["rule"]


def test_room_classification_is_deterministic():
    assert showdown.classify_room(TEST_ROOM) == showdown.classify_room(TEST_ROOM)


def test_eight_questions_allow_two_showdowns():
    extra = [
        {"template_id": "dine_out_or_in", "option_ids": ["dine_out_or_in_1", "dine_out_or_in_2"]},
        {"template_id": "swim_cleanup", "option_ids": ["swim_cleanup_1", "swim_cleanup_1", "swim_cleanup_2"]},
    ]
    results = showdown.classify_room(TEST_ROOM + extra)
    assert sum(1 for r in results if r["outcome"] == "showdown") == 2
    # 가장 팽팽한 순서: 세 명 모두 다른 문항(1/3) 두 개가 2:1이나 1:1 문항보다 먼저다.
    assert [r["template_id"] for r in results if r["outcome"] == "showdown"] == ["paid_activity", "planning_roles"]


def test_room_with_no_conflict_has_no_showdown():
    scenarios = [
        {"template_id": "route_depth", "option_ids": ["route_depth_3", "route_depth_3"]},
        {"template_id": "drink_bill", "option_ids": ["drink_bill_any", "drink_bill_2"]},
    ]
    results = showdown.classify_room(scenarios)
    assert [r["outcome"] for r in results] == ["agreed", "agreed"]


# ---- 승부처 진행 ----


class FixedChoice:
    """제비뽑기에서 정해 둔 순번의 사람을 뽑는 가짜 난수."""

    def __init__(self, index):
        self.index = index

    def choice(self, seq):
        return seq[self.index]


def _model_input(participants, rows):
    """rows: [(template_id, [option_id per participant])]"""
    return {
        "participant_ids": list(participants),
        "scenarios": [{"template_id": tid} for tid, _ in rows],
        "responses": [
            {"participant_id": pid, "scenario_id": tid, "option_id": option_id}
            for tid, option_ids in rows
            for pid, option_id in zip(participants, option_ids)
        ],
    }


def _two_person_board():
    # 3문항이라 승부처 상한은 1개다. 메뉴 문항이 승부처다.
    return showdown.build_board(_model_input(["a", "b"], [
        ("separate_menu", ["separate_menu_1", "separate_menu_2"]),
        ("route_depth", ["route_depth_3", "route_depth_3"]),
        ("drink_bill", ["drink_bill_any", "drink_bill_2"]),
    ]))


def _three_person_board():
    return showdown.build_board(_model_input(["a", "b", "c"], [
        ("paid_activity", ["paid_activity_2", "paid_activity_1", "paid_activity_3"]),
        ("route_depth", ["route_depth_2", "route_depth_1", "route_depth_3"]),
        ("separate_menu", ["separate_menu_2", "separate_menu_2", "separate_menu_any"]),
    ]))


def _card(view, template_id):
    return next(row for row in view["items"] if row["scenario_id"] == template_id)


def test_board_matches_classification_and_keeps_answers():
    board = _two_person_board()
    assert [item["outcome"] for item in board["items"]] == ["showdown", "agreed", "agreed"]
    assert board["answers"]["separate_menu"] == {"a": "separate_menu_1", "b": "separate_menu_2"}
    assert showdown.duelists(board, "separate_menu") == ["a", "b"]


def test_board_rejects_unknown_template():
    with pytest.raises(KeyError):
        showdown.build_board(_model_input(["a"], [("free_time", ["free_time_1"])]))


def test_initial_view_hides_votes_and_people():
    view = showdown.build_view(_two_person_board(), {}, viewer_id="a", titles={"separate_menu": "먹고 싶은 메뉴가 다를 때"})
    assert view["summary"] == {"total": 3, "settled": 2, "showdown": 1, "showdown_open": 1}
    card = _card(view, "separate_menu")
    assert card["title"] == "먹고 싶은 메뉴가 다를 때"
    assert card["rule"] is None
    assert card["showdown"] == {
        "sides": ["생선 요리", "면 요리"],
        "compromises": [c["rule"] for c in _rules()["templates"]["separate_menu"]["compromises"]],
        "phase": "voting", "mode": "rps", "voter_count": 2, "picked_count": 0, "can_pick": True, "my_pick": None,
    }
    text = json.dumps(view, ensure_ascii=False)
    assert "separate_menu_1" not in text and "separate_menu_2" not in text


def test_same_compromise_from_everyone_is_adopted():
    board, state = _two_person_board(), {}
    showdown.pick(board, state, "separate_menu", "a", "c1")
    view = showdown.build_view(board, state, viewer_id="b")
    assert _card(view, "separate_menu")["showdown"]["picked_count"] == 1
    assert _card(view, "separate_menu")["showdown"]["my_pick"] is None
    showdown.pick(board, state, "separate_menu", "b", "c1")
    card = _card(showdown.build_view(board, state, viewer_id="b"), "separate_menu")
    expected = _rules()["templates"]["separate_menu"]["compromises"][1]["rule"]
    assert card["rule"] == expected
    assert card["showdown"]["result"] == {"how": "compromise", "rule": expected}
    assert card["showdown"]["phase"] == "done"


def test_pick_can_change_until_everyone_has_picked():
    board, state = _two_person_board(), {}
    showdown.pick(board, state, "separate_menu", "a", "duel")
    showdown.pick(board, state, "separate_menu", "a", "c0")
    showdown.pick(board, state, "separate_menu", "b", "c0")
    assert state["separate_menu"]["result"]["how"] == "compromise"
    with pytest.raises(showdown.ShowdownError) as excinfo:
        showdown.pick(board, state, "separate_menu", "a", "c1")
    assert excinfo.value.code == "invalid_state"


def test_one_talk_vote_leaves_it_to_the_group():
    board, state = _two_person_board(), {}
    showdown.pick(board, state, "separate_menu", "a", "duel")
    showdown.pick(board, state, "separate_menu", "b", "talk")
    card = _card(showdown.build_view(board, state, viewer_id="a"), "separate_menu")
    assert card["showdown"]["result"] == {"how": "talk", "rule": None}
    assert card["rule"] is None
    assert showdown.build_view(board, state)["summary"]["showdown_open"] == 0


def test_two_people_go_to_rock_paper_scissors_and_winner_side_is_adopted():
    board, state = _two_person_board(), {}
    showdown.pick(board, state, "separate_menu", "a", "c0")
    showdown.pick(board, state, "separate_menu", "b", "c1")  # 절충 후보가 엇갈리면 승부다
    assert state["separate_menu"]["phase"] == "duel"
    showdown.move(board, state, "separate_menu", "a", "rock")
    waiting = _card(showdown.build_view(board, state, viewer_id="b"), "separate_menu")["showdown"]["duel"]
    assert waiting == {"is_player": True, "round": 1, "moved_count": 1, "my_move": None, "last_tie": None}
    showdown.move(board, state, "separate_menu", "b", "scissors")
    winner = _card(showdown.build_view(board, state, viewer_id="a"), "separate_menu")
    loser = _card(showdown.build_view(board, state, viewer_id="b"), "separate_menu")
    rule = _rule("separate_menu", "separate_menu_1")
    assert winner["rule"] == rule and loser["rule"] == rule
    assert winner["showdown"]["result"] == {"how": "duel", "rule": rule, "won": True, "my_move": "rock", "other_move": "scissors"}
    assert loser["showdown"]["result"] == {"how": "duel", "rule": rule, "won": False, "my_move": "scissors", "other_move": "rock"}


def test_tie_starts_another_round():
    board, state = _two_person_board(), {}
    showdown.pick(board, state, "separate_menu", "a", "duel")
    showdown.pick(board, state, "separate_menu", "b", "duel")
    showdown.move(board, state, "separate_menu", "a", "paper")
    showdown.move(board, state, "separate_menu", "b", "paper")
    duel = _card(showdown.build_view(board, state, viewer_id="a"), "separate_menu")["showdown"]["duel"]
    assert duel == {"is_player": True, "round": 2, "moved_count": 0, "my_move": None, "last_tie": "paper"}
    showdown.move(board, state, "separate_menu", "b", "rock")
    showdown.move(board, state, "separate_menu", "a", "scissors")
    assert state["separate_menu"]["result"]["winner"] == "b"


def test_move_is_rejected_outside_duel_or_twice():
    board, state = _two_person_board(), {}
    with pytest.raises(showdown.ShowdownError) as excinfo:
        showdown.move(board, state, "separate_menu", "a", "rock")
    assert excinfo.value.code == "invalid_state"
    showdown.pick(board, state, "separate_menu", "a", "duel")
    showdown.pick(board, state, "separate_menu", "b", "duel")
    showdown.move(board, state, "separate_menu", "a", "rock")
    with pytest.raises(showdown.ShowdownError) as excinfo:
        showdown.move(board, state, "separate_menu", "a", "paper")
    assert excinfo.value.code == "invalid_state"
    with pytest.raises(showdown.ShowdownError) as excinfo:
        showdown.move(board, state, "separate_menu", "b", "lizard")
    assert excinfo.value.code == "invalid_input"


def test_three_people_draw_lots_and_only_players_learn_if_they_won():
    board, state = _three_person_board(), {}
    assert [item["outcome"] for item in board["items"]] == ["showdown", "middle", "agreed"]
    for pid in ("a", "b"):
        showdown.pick(board, state, "paid_activity", pid, "duel")
    assert state["paid_activity"]["phase"] == "voting"
    showdown.pick(board, state, "paid_activity", "c", "c0", rng=FixedChoice(1))
    rule = _rule("paid_activity", "paid_activity_1")
    assert state["paid_activity"]["result"] == {"how": "lottery", "winner": "b", "option_id": "paid_activity_1", "rule": rule}
    assert _card(showdown.build_view(board, state, viewer_id="b"), "paid_activity")["showdown"]["result"] == {
        "how": "lottery", "rule": rule, "won": True}
    assert _card(showdown.build_view(board, state, viewer_id="a"), "paid_activity")["showdown"]["result"]["won"] is False
    outsider = _card(showdown.build_view(board, state), "paid_activity")["showdown"]
    assert outsider["result"] == {"how": "lottery", "rule": rule}
    assert outsider["mode"] == "lottery" and outsider["can_pick"] is False


def test_host_can_close_voting_with_picks_so_far():
    board, state = _three_person_board(), {}
    with pytest.raises(showdown.ShowdownError) as excinfo:
        showdown.close_voting(board, state, "paid_activity")
    assert excinfo.value.code == "invalid_state"
    showdown.pick(board, state, "paid_activity", "a", "c0")
    showdown.pick(board, state, "paid_activity", "c", "c0")
    showdown.close_voting(board, state, "paid_activity")
    assert state["paid_activity"]["result"] == {
        "how": "compromise", "rule": _rules()["templates"]["paid_activity"]["compromises"][0]["rule"]}


def test_only_showdown_questions_and_participants_are_accepted():
    board, state = _two_person_board(), {}
    for template_id in ("route_depth", "no_such_template"):
        with pytest.raises(showdown.ShowdownError) as excinfo:
            showdown.pick(board, state, template_id, "a", "duel")
        assert excinfo.value.code == "not_found"
    with pytest.raises(showdown.ShowdownError) as excinfo:
        showdown.pick(board, state, "separate_menu", "stranger", "duel")
    assert excinfo.value.code == "forbidden"
    with pytest.raises(showdown.ShowdownError) as excinfo:
        showdown.pick(board, state, "separate_menu", "a", "c2")
    assert excinfo.value.code == "invalid_input"
    assert state == {} or state["separate_menu"]["picks"] == {}


def test_state_survives_json_round_trip():
    board, state = _two_person_board(), {}
    showdown.pick(board, state, "separate_menu", "a", "duel")
    state = json.loads(json.dumps(state))
    showdown.pick(board, state, "separate_menu", "b", "duel")
    state = json.loads(json.dumps(state))
    showdown.move(board, state, "separate_menu", "a", "scissors")
    state = json.loads(json.dumps(state))
    showdown.move(board, state, "separate_menu", "b", "paper")
    assert json.loads(json.dumps(state))["separate_menu"]["result"]["winner"] == "a"
