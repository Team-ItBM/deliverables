"""추천 입력의 core_constraints(PR #16 리뷰 강의 6, SPEC 108행 "core_constraints를 pool에서 조회한다").

2026-11-05 사람 승인. 프롬프트 v12가 이미 이 필드를 읽으므로 전송부와 기존 기대값은 바꾸지 않는다.
문항을 확정할 때 저장하고, 저장 전에 만든 방은 마감 때 pool에서 조회한다.
TEST_DATABASE_URL이 없으면 srv fixture가 skip한다.
"""

import json

from harness.server import db as testdb
from harness.server import pact_outputs as po
from harness.server.api import default_profiles


def _pool(srv):
    data = json.loads(srv.pool_path.read_text(encoding="utf-8"))
    return {item["template_id"]: item["core_constraints"] for item in data["scenario_pool"]}


def _close(srv, app, room):
    app.replay.push("pact", po.pact_item())
    assert app.submit_new(room, "p1").resp.status_code == 201
    assert app.generate(room).status_code == 202
    app.join()
    return app.replay.calls_for("pact")[-1].model_input


def test_pact_input_has_pool_constraints(srv):
    app = srv.app
    _, room = app.create_room()
    model_input = _close(srv, app, room)
    pool = _pool(srv)
    assert model_input["scenarios"], "문항이 비어 있다"
    for scenario in model_input["scenarios"]:
        assert scenario["core_constraints"] == pool[scenario["template_id"]]
        assert scenario["core_constraints"], "pool 제약이 비어 있다"


def test_room_without_stored_constraints_uses_pool(srv):
    """저장 전에 만든 방은 마감 때 pool에서 조회한다."""
    app = srv.app
    _, room = app.create_room()
    stored = srv.sql("SELECT scenario_set FROM rooms WHERE room_code = %s", (room.code,))[0]["scenario_set"]
    for scenario in stored["scenarios"]:
        scenario.pop("core_constraints", None)
    testdb.execute(srv.database_url, "UPDATE rooms SET scenario_set = %s WHERE room_code = %s",
                   (json.dumps(stored, ensure_ascii=False), room.code))
    model_input = _close(srv, app, room)
    pool = _pool(srv)
    assert all(s["core_constraints"] == pool[s["template_id"]] for s in model_input["scenarios"])


def test_constraints_survive_pool_change(srv):
    """방을 연 뒤 pool에서 항목이 빠져도 확정할 때 저장한 제약을 쓴다."""
    app = srv.app
    _, room = app.create_room()
    expected = _pool(srv)
    app.app.state.jobs.pool_source._by_id.clear()
    model_input = _close(srv, app, room)
    assert all(s["core_constraints"] == expected[s["template_id"]] for s in model_input["scenarios"])


def test_constraints_stay_out_of_participant_views(srv):
    """모델 입력용 값이다. 응답 화면과 공개 결과로 나가지 않는다."""
    app = srv.app
    _, room = app.create_room(profiles=default_profiles(party_size=2))
    session = app.session(room, "p1")
    assert "core_constraints" not in session.text
    assert "core_constraints" not in str(app.room(room, host=True))
    _close(srv, app, room)
    assert "core_constraints" not in app.result(room).text
    assert "core_constraints" not in app.results(room).text


def test_retry_keeps_frozen_constraints(srv):
    """재시도 입력은 처음 고정한 입력과 같다(AC4)."""
    app = srv.app
    _, room = app.create_room()
    app.replay.push("pact", po.pact_item("extra_key"), po.pact_item("extra_key"))
    assert app.submit_new(room, "p1").resp.status_code == 201
    assert app.generate(room).status_code == 202
    app.join()
    first = app.replay.calls_for("pact")[0].model_input
    app.replay.push("pact", po.pact_item())
    assert app.retry(room).status_code == 202
    app.join()
    assert app.replay.calls_for("pact")[-1].model_input == first
    assert "core_constraints" in first["scenarios"][0]
