"""승부처를 거친 협약서 생성 흐름: 승부처가 남으면 방은 closed로 기다리고, 마지막 승부처가 끝나면 협약서 생성을 시작한다.

하니스 문항은 서비스 규칙 데이터에 없어서 마지막 제출 전에 그 문항에 맞는 규칙 데이터를 끼워 넣는다.
TEST_DATABASE_URL이 없으면 srv fixture가 skip한다.
"""

from harness.server import pact_outputs as po
from harness.server.api import assert_error, default_profiles
from travel import showdown

NEUTRAL = ("_any", "_other", "_info")


def _install_rules(monkeypatch, scenarios):
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


def _waiting_room(app, monkeypatch, party_size=2, submit_count=None):
    _, room = app.create_room(profiles=default_profiles(None, party_size))
    assert room is not None
    count = party_size if submit_count is None else submit_count
    submitted = [app.submit_new(room, p["profile_id"], choose=i) for i, p in enumerate(room.profiles[:count - 1])]
    templates = _install_rules(monkeypatch, submitted[0].session["scenarios"])
    last = room.profiles[count - 1]
    submitted.append(app.submit_new(room, last["profile_id"], choose=count - 1))
    for s in submitted:
        assert s.resp.status_code == 201, s.resp.text[:300]
    return room, submitted, templates


def _pick(app, room, sid, submitted, choice):
    resp = app.post(f"/api/rooms/{room.code}/showdown/{sid}/pick",
                    {"choice": choice, "session_id": submitted.session["session_id"]})
    assert resp.status_code == 200, resp.text[:300]
    return resp.json()


def _showdown_id(app, room):
    view = app.get(f"/api/rooms/{room.code}/showdown").json()
    return next(row["scenario_id"] for row in view["items"] if row["outcome"] == "showdown")


def test_room_waits_for_showdown_before_generating(srv, monkeypatch):
    app = srv.open_app()
    room, submitted, templates = _waiting_room(app, monkeypatch)
    app.join()
    assert app.room(room)["room_status"] == "closed"
    assert app.replay.calls_for("pact") == []
    assert_error(app.result(room), 409, "invalid_state")
    sid = _showdown_id(app, room)
    app.replay.push("pact", po.pact_item())
    _pick(app, room, sid, submitted[0], "c1")
    app.join()
    assert app.room(room)["room_status"] == "closed"
    assert app.replay.calls_for("pact") == []
    _pick(app, room, sid, submitted[1], "c1")
    app.join()
    assert app.room(room)["room_status"] == "ready"
    calls = app.replay.calls_for("pact")
    assert len(calls) == 1
    judgments = calls[0].model_input["judgments"]
    assert judgments[0] == {"scenario_id": sid, "result": "rule", "rule": templates[sid]["compromises"][1]["rule"]}
    assert all(j["result"] == "rule" for j in judgments)
    assert all("memo" not in r for r in calls[0].model_input["responses"])
    body = app.result(room).json()
    decisions = [item["decision"] for item in body["process"]]
    assert decisions == ["승부처에서 절충안으로 정함"] + ["기본 절충안으로 정함"] * (len(judgments) - 1)
    assert all(set(item) == {"label", "scenario_id", "title", "decision"} for item in body["process"])


def test_talk_becomes_discussion_item(srv, monkeypatch):
    app = srv.open_app()
    room, submitted, _ = _waiting_room(app, monkeypatch)
    sid = _showdown_id(app, room)
    app.replay.push("pact", po.pact_item())
    _pick(app, room, sid, submitted[0], "talk")
    _pick(app, room, sid, submitted[1], "c0")
    app.join()
    judgment = app.replay.calls_for("pact")[0].model_input["judgments"][0]
    assert judgment["result"] == "talk" and "rule" not in judgment and len(judgment["sides"]) == 2
    body = app.result(room).json()
    assert [d["scenario_id"] for d in body["discussion_items"]] == [sid]
    assert body["process"][-1]["label"] == "협의 사항"
    assert body["process"][-1]["decision"] == "승부처에서 직접 논의하기로 함"


def test_early_generation_waits_and_host_close_starts_it(srv, monkeypatch):
    app = srv.open_app()
    room, submitted, _ = _waiting_room(app, monkeypatch, party_size=3, submit_count=2)
    resp = app.generate(room)
    assert resp.status_code == 202, resp.text[:300]
    assert resp.json()["room_status"] == "closed"
    app.join()
    assert app.room(room)["room_status"] == "closed"
    sid = _showdown_id(app, room)
    app.replay.push("pact", po.pact_item())
    _pick(app, room, sid, submitted[0], "c0")
    closed = app.post(f"/api/rooms/{room.code}/showdown/{sid}/close", None, room.host)
    assert closed.status_code == 200, closed.text[:300]
    app.join()
    assert app.room(room)["room_status"] == "ready"
    assert len(app.replay.calls_for("pact")) == 1


def test_regeneration_keeps_showdown_results(srv, monkeypatch):
    app = srv.open_app()
    room, submitted, _ = _waiting_room(app, monkeypatch)
    sid = _showdown_id(app, room)
    app.replay.push("pact", po.pact_item(), po.pact_item())
    _pick(app, room, sid, submitted[0], "talk")
    _pick(app, room, sid, submitted[1], "talk")
    app.join()
    resp = app.post(f"/api/rooms/{room.code}/regenerate", None, room.host)
    assert resp.status_code == 202, resp.text[:300]
    app.join()
    calls = app.replay.calls_for("pact")
    assert len(calls) == 2
    assert calls[0].model_input["judgments"] == calls[1].model_input["judgments"]
