"""승부처 API(docs/SHOWDOWN.md): 조회, 선택, 가위바위보, 제비뽑기, 방장 마감.

기준은 팀 검토 전 제안이다. 서버 계약 하니스(conftest의 srv fixture)를 그대로 쓰고 기존 케이스 기대값은 바꾸지 않는다.
하니스의 문항은 서비스 pool과 달라서, 테스트마다 그 문항에 맞는 규칙 데이터를 끼워 넣는다.
TEST_DATABASE_URL이 없으면 srv fixture가 skip한다.
"""

import json

import pytest

from harness.server import pact_outputs as po
from harness.server.api import assert_error, default_profiles
from travel import showdown

NEUTRAL = ("_any", "_other", "_info")


def _session_headers(submitted):
    return {"X-Session-Id": submitted.session["session_id"]}


def _install_rules(monkeypatch, scenarios):
    """세션 응답의 문항으로 규칙 데이터를 만든다. 표로 세는 선택지는 모두 한쪽 입장이다."""
    templates = {}
    for scenario in scenarios:
        sid = scenario["scenario_id"]
        options = {
            o["option_id"]: {"kind": "side", "tag": f"{o['option_id']} 입장", "rule": f"{o['option_id']} 규칙!"}
            for o in scenario["options"] if not o["option_id"].endswith(NEUTRAL)
        }
        templates[sid] = {"options": options, "compromises": [
            {"type": "alternate", "rule": f"{sid} 번갈아!"}, {"type": "divide", "rule": f"{sid} 나누기!"}]}
    monkeypatch.setattr(showdown, "_rules", {"rules_version": 0, "pool_version": 0, "templates": templates})
    return templates


def _closed_room(app, monkeypatch, party_size):
    """문항마다 사람별로 다른 선택지를 고르게 해 전 문항이 갈린 방을 만든다."""
    _, room = app.create_room(profiles=default_profiles(None, party_size))
    assert room is not None
    app.replay.push("pact", po.pact_item())
    submitted = [app.submit_new(room, p["profile_id"], choose=i) for i, p in enumerate(room.profiles)]
    for s in submitted:
        assert s.resp.status_code == 201, s.resp.text[:300]
    templates = _install_rules(monkeypatch, submitted[0].session["scenarios"])
    app.join()
    return room, submitted, templates


def _get(app, room, submitted=None):
    resp = app.get(f"/api/rooms/{room.code}/showdown", headers=_session_headers(submitted) if submitted else None)
    assert resp.status_code == 200, resp.text[:300]
    return resp.json()


def _post(app, room, scenario_id, action, submitted, **body):
    payload = dict(body)
    if submitted is not None:
        payload["session_id"] = submitted.session["session_id"]
    return app.post(f"/api/rooms/{room.code}/showdown/{scenario_id}/{action}", payload)


def _showdowns(view):
    return [row for row in view["items"] if row["outcome"] == "showdown"]


def test_showdown_is_not_available_before_answers_are_frozen(srv):
    app = srv.open_app()
    _, room = app.create_room()
    assert_error(app.get(f"/api/rooms/{room.code}/showdown"), 409, "invalid_state")


def test_unknown_room_is_not_found(srv):
    app = srv.open_app()
    assert_error(app.get("/api/rooms/no-such-room/showdown"), 404, "not_found")


def test_room_without_rule_data_reports_unavailable(srv):
    # 하니스 문항은 서비스 규칙 데이터에 없다. 규칙을 끼워 넣지 않으면 사용할 수 없다고 답한다.
    app = srv.open_app()
    room, _ = app.ready_room(party_size=2)
    assert _get(app, room) == {"available": False}


def test_view_shows_one_showdown_and_hides_private_data(srv, monkeypatch):
    app = srv.open_app()
    room, submitted, _ = _closed_room(app, monkeypatch, 2)
    view = _get(app, room, submitted[0])
    count = len(submitted[0].session["scenarios"])
    assert view["available"] is True and view["is_participant"] is True
    assert view["summary"] == {"total": count, "settled": count - 1, "showdown": 1, "showdown_open": 1}
    assert [row["outcome"] for row in view["items"]] == ["showdown"] + ["fallback"] * (count - 1)
    card = view["items"][0]["showdown"]
    assert card["phase"] == "voting" and card["mode"] == "rps"
    assert card["voter_count"] == 2 and card["picked_count"] == 0 and card["can_pick"] is True
    text = json.dumps(view, ensure_ascii=False)
    for s in submitted:
        assert s.body["participant_id"] not in text
        assert s.session["session_id"] not in text
        for answer in s.answers:
            assert answer["memo"] not in text
            assert f'"{answer["option_id"]}"' not in text
    for name in room.names.values():
        assert name not in text

    outsider = _get(app, room)
    assert outsider["is_participant"] is False
    assert outsider["items"][0]["showdown"]["can_pick"] is False


def test_same_compromise_is_adopted(srv, monkeypatch):
    app = srv.open_app()
    room, submitted, templates = _closed_room(app, monkeypatch, 2)
    sid = _showdowns(_get(app, room))[0]["scenario_id"]
    first = _post(app, room, sid, "pick", submitted[0], choice="c1")
    assert first.status_code == 200, first.text[:300]
    assert first.json()["items"][0]["showdown"]["picked_count"] == 1
    assert first.json()["items"][0]["showdown"]["my_pick"] == "c1"
    assert _get(app, room, submitted[1])["items"][0]["showdown"]["my_pick"] is None
    second = _post(app, room, sid, "pick", submitted[1], choice="c1").json()
    rule = templates[sid]["compromises"][1]["rule"]
    assert second["items"][0]["rule"] == rule
    assert second["items"][0]["showdown"]["result"] == {"how": "compromise", "rule": rule}
    assert second["summary"]["showdown_open"] == 0
    # 다시 조회해도 같다(저장됨).
    assert _get(app, room)["items"][0]["rule"] == rule
    assert_error(_post(app, room, sid, "pick", submitted[0], choice="c0"), 409, "invalid_state")


def test_two_people_play_rock_paper_scissors(srv, monkeypatch):
    app = srv.open_app()
    room, submitted, templates = _closed_room(app, monkeypatch, 2)
    sid = _showdowns(_get(app, room))[0]["scenario_id"]
    assert_error(_post(app, room, sid, "move", submitted[0], move="rock"), 409, "invalid_state")
    _post(app, room, sid, "pick", submitted[0], choice="duel")
    started = _post(app, room, sid, "pick", submitted[1], choice="c0").json()
    assert started["items"][0]["showdown"]["phase"] == "duel"
    # 한 판 비기고 다시 낸다.
    _post(app, room, sid, "move", submitted[0], move="paper")
    tied = _post(app, room, sid, "move", submitted[1], move="paper").json()
    assert tied["items"][0]["showdown"]["duel"] == {
        "is_player": True, "round": 2, "moved_count": 0, "my_move": None, "last_tie": "paper"}
    _post(app, room, sid, "move", submitted[0], move="scissors")
    assert_error(_post(app, room, sid, "move", submitted[0], move="rock"), 409, "invalid_state")
    done = _post(app, room, sid, "move", submitted[1], move="rock").json()
    rule = templates[sid]["options"][submitted[1].answers[0]["option_id"]]["rule"]
    assert submitted[1].answers[0]["scenario_id"] == sid
    assert done["items"][0]["rule"] == rule
    assert done["items"][0]["showdown"]["result"] == {
        "how": "duel", "rule": rule, "won": True, "my_move": "rock", "other_move": "scissors"}
    loser = _get(app, room, submitted[0])["items"][0]["showdown"]["result"]
    assert loser["won"] is False and loser["my_move"] == "scissors"
    watcher = _get(app, room)["items"][0]["showdown"]["result"]
    assert watcher == {"how": "duel", "rule": rule}


def test_three_people_draw_lots_once(srv, monkeypatch):
    app = srv.open_app()
    room, submitted, templates = _closed_room(app, monkeypatch, 3)
    sid = _showdowns(_get(app, room))[0]["scenario_id"]
    for s in submitted[:2]:
        assert _post(app, room, sid, "pick", s, choice="duel").json()["items"][0]["showdown"]["phase"] == "voting"
    done = _post(app, room, sid, "pick", submitted[2], choice="duel").json()
    card = done["items"][0]
    assert card["showdown"]["mode"] == "lottery" and card["showdown"]["phase"] == "done"
    assert card["showdown"]["result"]["how"] == "lottery"
    assert card["rule"] in {o["rule"] for o in templates[sid]["options"].values()}
    winners = [_get(app, room, s)["items"][0]["showdown"]["result"]["won"] for s in submitted]
    assert sorted(winners) == [False, False, True]
    # 한 번 정하면 다시 뽑지 않는다.
    assert _get(app, room)["items"][0]["rule"] == card["rule"]
    assert_error(_post(app, room, sid, "pick", submitted[0], choice="duel"), 409, "invalid_state")


def test_one_talk_vote_leaves_it_open_for_the_group(srv, monkeypatch):
    app = srv.open_app()
    room, submitted, _ = _closed_room(app, monkeypatch, 2)
    sid = _showdowns(_get(app, room))[0]["scenario_id"]
    _post(app, room, sid, "pick", submitted[0], choice="talk")
    done = _post(app, room, sid, "pick", submitted[1], choice="duel").json()
    assert done["items"][0]["showdown"]["result"] == {"how": "talk", "rule": None}
    assert done["items"][0]["rule"] is None


def test_host_closes_voting_and_others_cannot(srv, monkeypatch):
    app = srv.open_app()
    room, submitted, templates = _closed_room(app, monkeypatch, 3)
    sid = _showdowns(_get(app, room))[0]["scenario_id"]
    path = f"/api/rooms/{room.code}/showdown/{sid}/close"
    assert_error(app.post(path, None), 403, "host_forbidden")
    assert_error(app.post(path, None, room.host), 409, "invalid_state")
    _post(app, room, sid, "pick", submitted[0], choice="c0")
    closed = app.post(path, None, room.host)
    assert closed.status_code == 200, closed.text[:300]
    assert closed.json()["items"][0]["rule"] == templates[sid]["compromises"][0]["rule"]


@pytest.mark.parametrize("body,status,code", [
    ({"choice": "duel"}, 403, "showdown_forbidden"),
    ({"choice": "duel", "session_id": "not-a-uuid"}, 403, "showdown_forbidden"),
    ({"choice": "duel", "session_id": "00000000-0000-4000-8000-000000000000"}, 403, "showdown_forbidden"),
])
def test_pick_needs_a_submitted_session(srv, monkeypatch, body, status, code):
    app = srv.open_app()
    room, _, _ = _closed_room(app, monkeypatch, 2)
    sid = _showdowns(_get(app, room))[0]["scenario_id"]
    assert_error(app.post(f"/api/rooms/{room.code}/showdown/{sid}/pick", body), status, code)


def test_bad_choice_and_non_showdown_question_are_rejected(srv, monkeypatch):
    app = srv.open_app()
    room, submitted, _ = _closed_room(app, monkeypatch, 2)
    view = _get(app, room)
    sid = _showdowns(view)[0]["scenario_id"]
    other = next(row["scenario_id"] for row in view["items"] if row["outcome"] != "showdown")
    assert_error(_post(app, room, sid, "pick", submitted[0], choice="c9"), 422, "invalid_input")
    assert_error(_post(app, room, other, "pick", submitted[0], choice="duel"), 404, "not_found")
    assert_error(_post(app, room, "no_such_scenario", "pick", submitted[0], choice="duel"), 404, "not_found")
    assert _get(app, room)["items"][0]["showdown"]["picked_count"] == 0
