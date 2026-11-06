"""문항 생성 복구(PR #16 리뷰 2번, AC10). 서버가 재시작해도 방이 `preparing`에 갇히지 않는다.

2026-11-05 사람 승인. 재시도는 기존 `POST /retry`를 넓혔다(§0-B). 방장 권한, 방당 상한, 시도 ID 규칙을 따른다.
앱 A가 문항 호출을 붙잡아 재시작을 흉내 내고, 작업이 없는 앱 B가 멈춤 점검을 부른다(OUT-N06과 같은 구성).
TEST_DATABASE_URL이 없으면 srv fixture가 skip한다.
"""

from harness.server import scenario_outputs as so
from harness.server import db as testdb
from harness.server.api import assert_calls, assert_error, default_profiles, default_trip


def _hold_room(app):
    hold = app.replay.hold("scenarios", so.scenario_item())
    _, room = app.create_room(push_scenario=False, wait=False)
    hold.wait_started()
    return hold, room


def _crashed_room(srv):
    """앱 A가 문항 호출을 붙잡은 방과 작업이 없는 앱 B."""
    crashed = srv.app
    hold, room = _hold_room(crashed)
    restarted = srv.open_app(replay=srv.new_replay())
    return crashed, restarted, hold, room


def _finish(app, hold):
    hold.release()
    app.join()


def test_stalled_preparation_fails_at_limit(srv):
    crashed, restarted, hold, room = _crashed_room(srv)
    started = srv.clock()
    srv.clock.set_after(started, 599)
    restarted.recover_stalled()
    assert restarted.room(room)["scenario_status"] == "preparing"
    srv.clock.set_after(started, 600)
    restarted.recover_stalled()
    assert restarted.room(room)["scenario_status"] == "failed"
    assert_error(restarted.session(room, "p1"), 409, "invalid_state")
    _finish(crashed, hold)


def test_retry_after_stall_reaches_ready(srv):
    """리뷰 재현: 재시작 뒤 멈춤 점검, 재시도, 세션 생성까지 이어진다."""
    crashed, restarted, hold, room = _crashed_room(srv)
    srv.clock.set_after(srv.clock(), 601)
    restarted.recover_stalled()
    restarted.replay.push("scenarios", so.scenario_item())
    resp = restarted.retry(room)
    assert resp.status_code == 202, resp.text[:200]
    assert resp.json() == {"room_status": "open", "scenario_status": "preparing"}
    restarted.join()
    assert restarted.room(room)["scenario_status"] == "ready"
    assert restarted.session(room, "p1").status_code == 201
    _finish(crashed, hold)


def test_late_output_of_old_attempt_is_discarded(srv):
    """이전 시도의 늦은 출력이 재시도의 상태를 덮지 않는다(시도 ID 규칙)."""
    crashed, restarted, hold, room = _crashed_room(srv)
    srv.clock.set_after(srv.clock(), 600)
    restarted.recover_stalled()
    second = restarted.replay.hold("scenarios", so.scenario_item())
    assert restarted.retry(room).status_code == 202
    second.wait_started()
    _finish(crashed, hold)
    assert restarted.room(room)["scenario_status"] == "preparing", "이전 시도가 현재 시도를 덮었다"
    _finish(restarted, second)
    assert restarted.room(room)["scenario_status"] == "ready"


def test_late_output_after_failure_keeps_failed(srv):
    crashed, restarted, hold, room = _crashed_room(srv)
    srv.clock.set_after(srv.clock(), 600)
    restarted.recover_stalled()
    _finish(crashed, hold)
    assert restarted.room(room)["scenario_status"] == "failed"


def test_job_time_limit_applies_to_scenarios(srv):
    app = srv.app
    hold, room = _hold_room(app)
    started = srv.clock()
    srv.clock.set_after(started, 299)
    app.enforce_deadlines()
    assert app.room(room)["scenario_status"] == "preparing"
    srv.clock.set_after(started, 300)
    app.enforce_deadlines()
    assert app.room(room)["scenario_status"] == "failed"
    _finish(app, hold)
    assert app.room(room)["scenario_status"] == "failed"


def test_room_without_start_time_uses_created_at(srv):
    """시작 시각 열이 생기기 전에 만든 방도 복구한다."""
    crashed, restarted, hold, room = _crashed_room(srv)
    testdb.execute(srv.database_url, "UPDATE rooms SET scenario_started_at = NULL, scenario_attempt_id = NULL")
    srv.clock.set_after(srv.clock(), 600)
    restarted.recover_stalled()
    assert restarted.room(room)["scenario_status"] == "failed"
    _finish(crashed, hold)


def test_retry_after_invalid_output(srv):
    """형식 오류로 failed가 된 문항도 같은 경로로 다시 시도한다."""
    app = srv.app
    app.replay.push("scenarios", "{}", "{}")
    _, room = app.create_room(push_scenario=False)
    assert app.room(room)["scenario_status"] == "failed"
    app.replay.push("scenarios", so.scenario_item())
    assert app.retry(room).status_code == 202
    app.join()
    assert app.room(room)["scenario_status"] == "ready"
    assert_calls(app.replay, {"scenarios": 3})


def test_retry_requires_host(srv):
    app = srv.app
    app.replay.push("scenarios", "{}", "{}")
    _, room = app.create_room(push_scenario=False)
    assert_error(app.retry(room, headers={}), 403, "host_forbidden")
    assert app.room(room)["scenario_status"] == "failed"


def test_retry_rejected_while_preparing_or_ready(srv):
    app = srv.app
    hold, room = _hold_room(app)
    assert_error(app.retry(room), 409, "invalid_state")
    _finish(app, hold)
    assert_error(app.retry(room), 409, "invalid_state")


def test_retry_rejected_when_status_needs_new_room(srv):
    """정보 부족·미지원은 재시도로 풀리지 않는다. 여행 정보를 고쳐 새 방을 만든다."""
    app = srv.app
    _, room = app.create_room(scenario=so.fixture_item("s2"))
    assert app.room(room)["scenario_status"] == "needs_information"
    assert_error(app.retry(room), 409, "invalid_state")


def test_retry_respects_room_cap(srv):
    """방당 상한에 닿았으면 재시도해도 모델을 부르지 않고 다시 failed가 된다. 방장은 새 방으로 간다."""
    app = srv.open_app(room_cap_usd=0.20)
    app.replay.push("scenarios", "{}", "{}")
    _, room = app.create_room(profiles=default_profiles(party_size=2), trip=default_trip(2), push_scenario=False)
    room_id = srv.sql("SELECT room_id FROM rooms WHERE room_code = %s", (room.code,))[0]["room_id"]
    testdb.execute(srv.database_url,
                   "INSERT INTO llm_calls (room_id, stage, cost_usd, created_at) VALUES (%s, 'scenarios', 0.20, now())",
                   (room_id,))
    before = app.replay.count("scenarios")
    assert app.retry(room).status_code == 202
    app.join()
    assert app.replay.count("scenarios") == before
    assert app.room(room)["scenario_status"] == "failed"


def test_each_attempt_has_its_own_id(srv):
    app = srv.app
    app.replay.push("scenarios", "{}", "{}")
    _, room = app.create_room(push_scenario=False)
    first = srv.sql("SELECT scenario_attempt_id, scenario_attempt_count FROM rooms")[0]
    assert first["scenario_attempt_count"] == 1 and first["scenario_attempt_id"] is not None
    app.replay.push("scenarios", so.scenario_item())
    assert app.retry(room).status_code == 202
    app.join()
    second = srv.sql("SELECT scenario_attempt_id, scenario_attempt_count FROM rooms")[0]
    assert second["scenario_attempt_count"] == 2
    assert second["scenario_attempt_id"] != first["scenario_attempt_id"]
    rows = srv.sql("SELECT DISTINCT attempt_id FROM llm_calls WHERE stage = 'scenarios'")
    assert {r["attempt_id"] for r in rows} == {first["scenario_attempt_id"], second["scenario_attempt_id"]}


def test_migration_adds_columns_to_existing_rooms(srv):
    """이미 있는 표에 열을 더한다. 스키마 초기화는 여러 번 불러도 같다."""
    srv.app
    for column in ("scenario_started_at", "scenario_attempt_id", "scenario_attempt_count"):
        testdb.execute(srv.database_url, f"ALTER TABLE rooms DROP COLUMN {column}")
    srv.server.db.init_schema(srv.database_url)
    srv.server.db.init_schema(srv.database_url)
    names = {r["column_name"] for r in srv.sql(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'rooms'")}
    assert {"scenario_started_at", "scenario_attempt_id", "scenario_attempt_count"} <= names
