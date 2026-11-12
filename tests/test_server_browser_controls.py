"""승인된 방 삭제·현재 브라우저 알림 해제·후보 draft 회귀 검사. 실제 격리 PostgreSQL을 쓴다."""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg
import pytest

from harness.server import db as testdb
from harness.server import pact_outputs as po
from harness.server.api import assert_error

from travel.server import admin
from travel.server.llm import LLMCallError
from travel.server.llm_openai import CostGuard

ENDPOINT = "https://push.test/current-browser"
OTHER_ENDPOINT = "https://push.test/other-browser"


def scope(role="host", session_id=None, endpoint=ENDPOINT):
    body = {"role": role, "endpoint": endpoint}
    if session_id is not None:
        body["session_id"] = session_id
    return body


def push_control(app, room, method, body, headers=None):
    suffix = "/status" if method == "POST" else ""
    return app.client.request(method, f"/api/rooms/{room.code}/push-subscriptions{suffix}",
                              json=body, headers=room.host if headers is None else headers)


def delete_room(app, room, headers=None):
    return app.client.delete(f"/api/rooms/{room.code}", headers=room.host if headers is None else headers)


def enqueue(app, room, event="ready:1"):
    async def run():
        async with app.app.state.db.transaction() as conn:
            cur = await conn.execute("SELECT room_id FROM rooms WHERE room_code = %s", (room.code,))
            room_id = (await cur.fetchone())["room_id"]
            return await app.app.state.notifier.enqueue(conn, room_id, event)

    return app._call(run)


@pytest.mark.parametrize("status,scenario_status", [
    ("open", "preparing"), ("generating", "ready"),
])
def test_room_delete_rejects_busy_after_auth(srv, status, scenario_status):
    app = srv.app
    _, room = app.create_room()
    testdb.execute(srv.database_url, "UPDATE rooms SET status = %s, scenario_status = %s WHERE room_code = %s",
                   (status, scenario_status, room.code))
    for headers in ({}, {"X-Host-Token": "wrong"}):
        assert_error(delete_room(app, room, headers), 403, "host_forbidden")
    assert_error(delete_room(app, room), 409, "invalid_state")
    assert app.get(f"/api/rooms/{room.code}").status_code == 200


@pytest.mark.parametrize("status,scenario_status", [("open", "ready"), ("open", "failed"), ("failed", "ready")])
def test_room_delete_accepts_idle_states(srv, status, scenario_status):
    app = srv.app
    _, room = app.create_room()
    testdb.execute(srv.database_url, "UPDATE rooms SET status = %s, scenario_status = %s WHERE room_code = %s",
                   (status, scenario_status, room.code))
    response = delete_room(app, room)
    assert response.status_code == 204 and response.content == b""
    assert_error(delete_room(app, room), 404, "not_found")


def test_room_delete_cascades_private_and_derived_records(srv):
    app = srv.app
    room, submitted = app.ready_room()
    _, other = app.create_room()
    assert app.subscribe(room, "host", endpoint=ENDPOINT).status_code == 201
    assert app.subscribe(room, "participant", session_id=submitted[0].session["session_id"],
                         endpoint=ENDPOINT).status_code == 201
    initial = app.results_body(room)["results"][0]["result_id"]
    assert app.select(room, initial).status_code == 200
    text = app.edited_text(room, initial, "/clauses/0/action", "비슷한 상황이 오면", "같은 상황이 다시 오면")
    assert app.edit(room, initial, [{"path": "/clauses/0/action", "text": text}]).status_code == 201
    enqueue(app, room)
    room_id = srv.sql("SELECT room_id FROM rooms WHERE room_code = %s", (room.code,))[0]["room_id"]
    calls = srv.sql("SELECT * FROM llm_calls WHERE room_id = %s ORDER BY call_id", (room_id,))
    assert calls
    tables = ("profiles", "sessions", "submissions", "responses", "results", "push_subscriptions", "notifications")
    for table in tables:
        assert srv.sql(f"SELECT count(*) AS n FROM {table} WHERE room_id = %s", (room_id,))[0]["n"] > 0, table
    for headers in ({}, other.host):
        assert_error(delete_room(app, room, headers), 403, "host_forbidden")
    response = delete_room(app, room)
    assert response.status_code == 204 and response.content == b""
    for table in ("rooms", *tables):
        assert srv.sql(f"SELECT count(*) AS n FROM {table} WHERE room_id = %s", (room_id,))[0]["n"] == 0, table
    assert srv.sql("SELECT * FROM llm_calls WHERE call_id = ANY(%s) ORDER BY call_id",
                   ([row["call_id"] for row in calls],)) == [{**row, "room_id": None} for row in calls]
    for suffix in ("", "/result", "/results"):
        assert_error(app.get(f"/api/rooms/{room.code}{suffix}", headers=room.host), 404, "not_found")
    assert app.get(f"/api/rooms/{other.code}").status_code == 200


def test_room_delete_locks_before_checking_latest_state(srv):
    app = srv.app
    _, room = app.create_room()
    lock = testdb.RowLock(srv.database_url, "SELECT 1 FROM rooms WHERE room_code = %s FOR UPDATE", (room.code,))
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(delete_room, app, room)
        try:
            testdb.wait_for_lock_waiters(srv.database_url, 1)
            lock.conn.execute("UPDATE rooms SET status = 'generating' WHERE room_code = %s", (room.code,))
        finally:
            lock.release()
        assert_error(future.result(timeout=10), 409, "invalid_state")


@pytest.mark.parametrize("method", ["POST", "DELETE"])
def test_push_controls_validate_same_authority_and_session_as_registration(srv, method):
    app = srv.app
    _, room = app.create_room()
    _, other = app.create_room()
    session_id = app.session(other, "p1").json()["session_id"]
    assert app.subscribe(room, "host", endpoint=ENDPOINT).status_code == 201
    for headers in ({}, other.host):
        assert_error(push_control(app, room, method, scope(), headers), 403, "host_forbidden")
    for body in (None, {}, scope("unknown"), scope("participant"), scope("participant", "bad-uuid"),
                 scope(endpoint="http://127.0.0.1/private")):
        assert_error(push_control(app, room, method, body), 422, "invalid_input")
    for body in (scope("participant", str(uuid.uuid4())), scope("participant", session_id), scope("host", session_id)):
        assert_error(push_control(app, room, method, body), 404, "not_found")
    assert len(srv.sql("SELECT 1 FROM push_subscriptions")) == 1
    assert delete_room(app, other).status_code == 204
    assert_error(push_control(app, other, method, scope()), 404, "not_found")


def test_push_status_and_unsubscribe_scope_browser_to_one_room(srv, capsys):
    app = srv.app
    _, room = app.create_room()
    _, other = app.create_room()
    sessions = [app.session(room, "p1").json()["session_id"] for _ in range(3)]
    assert push_control(app, room, "POST", scope()).json() == {"subscribed": False, "room_subscribed": False}
    assert app.subscribe(room, "host", endpoint=ENDPOINT).status_code == 201
    assert app.subscribe(room, "host", session_id=sessions[0], endpoint=ENDPOINT).status_code == 201
    for session_id in sessions[:2]:
        assert app.subscribe(room, "participant", session_id=session_id, endpoint=ENDPOINT).status_code == 201
        assert push_control(app, room, "POST", scope("participant", session_id)).json() == {
            "subscribed": True, "room_subscribed": True}
    assert push_control(app, room, "POST", scope("participant", sessions[2])).json() == {
        "subscribed": False, "room_subscribed": True}
    assert push_control(app, room, "POST", scope(endpoint=OTHER_ENDPOINT)).json() == {
        "subscribed": False, "room_subscribed": False}
    assert push_control(app, other, "POST", scope()).json() == {"subscribed": False, "room_subscribed": False}
    assert app.subscribe(room, "host", endpoint=OTHER_ENDPOINT).status_code == 201
    assert app.subscribe(other, "host", endpoint=ENDPOINT).status_code == 201
    enqueue(app, room)
    for _ in range(2):
        response = push_control(app, room, "DELETE", scope("participant", sessions[0]), {})
        assert response.status_code == 204 and response.content == b""
    assert push_control(app, room, "POST", scope()).json() == {"subscribed": False, "room_subscribed": False}
    assert push_control(app, room, "POST", scope(endpoint=OTHER_ENDPOINT)).json() == {
        "subscribed": True, "room_subscribed": True}
    assert push_control(app, other, "POST", scope()).json() == {"subscribed": True, "room_subscribed": True}
    assert len(srv.sql("SELECT 1 FROM push_subscriptions")) == 2
    assert len(srv.sql("SELECT 1 FROM notifications")) == 1
    assert ENDPOINT not in capsys.readouterr().out


def test_push_reregister_does_not_replay_past_events(srv):
    app = srv.app
    room, submitted = app.ready_room()
    body = scope("participant", submitted[0].session["session_id"])
    assert app.subscribe(room, "participant", session_id=body["session_id"], endpoint=ENDPOINT).status_code == 201
    result_id = app.results_body(room)["results"][0]["result_id"]
    assert app.select(room, result_id).status_code == 200
    assert srv.push.count() == 1
    assert push_control(app, room, "DELETE", body, {}).status_code == 204
    assert not srv.sql("SELECT 1 FROM notifications")
    for _ in range(2):
        assert app.subscribe(room, "participant", session_id=body["session_id"], endpoint=ENDPOINT).status_code in (200, 201)
    assert app.select(room, result_id).status_code == 200
    assert srv.push.count() == 1
    assert not srv.sql("SELECT 1 FROM notifications")


@pytest.mark.parametrize("remove", ["subscription", "room", "notification"])
def test_pending_push_skips_removed_subscription_room_or_notification(srv, remove):
    app = srv.app
    _, room = app.create_room()
    assert app.subscribe(room, "host", endpoint=ENDPOINT).status_code == 201
    pending = enqueue(app, room)
    assert len(pending) == 1
    if remove == "subscription":
        assert push_control(app, room, "DELETE", scope()).status_code == 204
    elif remove == "room":
        assert delete_room(app, room).status_code == 204
    else:
        testdb.execute(srv.database_url, "DELETE FROM notifications")
    app._call(app.app.state.notifier.deliver, room.code, "ready:1", pending)
    assert srv.push.count() == 0
    assert not srv.sql("SELECT 1 FROM notifications")


def test_completed_pending_push_is_not_sent_again(srv):
    app = srv.app
    _, room = app.create_room()
    assert app.subscribe(room, "host", endpoint=ENDPOINT).status_code == 201
    pending = enqueue(app, room)
    for _ in range(2):
        app._call(app.app.state.notifier.deliver, room.code, "ready:1", pending)
    assert srv.push.count() == 1
    assert srv.sql("SELECT status_code FROM notifications")[0]["status_code"] == 201


def test_unsubscribe_does_not_wait_for_or_recall_inflight_push(srv, monkeypatch):
    app = srv.app
    _, room = app.create_room()
    assert app.subscribe(room, "host", endpoint=ENDPOINT).status_code == 201
    pending = enqueue(app, room)
    started, release = threading.Event(), threading.Event()
    original_send = srv.push.send

    def send(subscription, payload):
        started.set()
        assert release.wait(10), "발송 해제 신호가 없다"
        return original_send(subscription, payload)

    monkeypatch.setattr(srv.push, "send", send)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(app._call, app.app.state.notifier.deliver, room.code, "ready:1", pending)
        try:
            assert started.wait(10)
            assert push_control(app, room, "DELETE", scope()).status_code == 204
        finally:
            release.set()
        future.result(timeout=10)
    assert srv.push.count() == 1
    assert not srv.sql("SELECT 1 FROM notifications")


def test_result_candidates_only_selected_original_is_not_draft(srv):
    app = srv.app
    room, _ = app.ready_room()
    app.replay.push("pact", po.pact_item())
    assert app.regenerate(room).status_code == 202
    app.join()
    entries = app.results_body(room)["results"]
    assert len(entries) == 2 and all(entry["draft"] is True for entry in entries)
    for chosen in (entries[0]["result_id"], entries[1]["result_id"]):
        assert app.select(room, chosen).status_code == 200
        assert {entry["result_id"]: entry["draft"] for entry in app.results_body(room)["results"]} == {
            entry["result_id"]: entry["result_id"] != chosen for entry in entries}
        assert app.result(room).json()["draft"] is False


def test_push_check_error_keeps_notification_unsent(srv, monkeypatch, capsys):
    app = srv.app
    _, room = app.create_room()
    assert app.subscribe(room, "host", endpoint=ENDPOINT).status_code == 201
    pending = enqueue(app, room)
    before = srv.sql("SELECT * FROM notifications")
    assert len(before) == 1 and before[0]["sent_at"] is None
    original_execute = psycopg.AsyncConnection.execute

    async def execute(conn, query, *args, **kwargs):
        if isinstance(query, str) and query.startswith("SELECT 1 FROM notifications"):
            raise psycopg.OperationalError("check unavailable")
        return await original_execute(conn, query, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(psycopg.AsyncConnection, "execute", execute)
        app._call(app.app.state.notifier.deliver, room.code, "ready:1", pending)
    assert srv.push.count() == 0
    assert srv.sql("SELECT * FROM notifications") == before
    output = capsys.readouterr().out
    assert '"event":"push_check_error"' in output.replace(" ", "")
    assert '"event":"push_sent"' not in output.replace(" ", "")
    assert ENDPOINT not in output


def test_edited_candidate_draft_matches_its_original_selection(srv):
    app = srv.app
    room, _ = app.ready_room()
    app.replay.push("pact", po.pact_item())
    assert app.regenerate(room).status_code == 202
    app.join()
    entries = app.results_body(room)["results"]
    selected_id = entries[0]["result_id"]
    assert app.select(room, selected_id).status_code == 200
    for entry in entries:
        origin_id = entry["result_id"]
        text = app.edited_text(room, origin_id, "/clauses/0/action", "비슷한 상황이 오면", "같은 상황이 다시 오면")
        response = app.edit(room, origin_id, [{"path": "/clauses/0/action", "text": text}])
        assert response.status_code == 201
        edited = response.json()
        assert edited["result_id"] != origin_id
        candidate = next(row for row in app.results_body(room)["results"] if row["result_id"] == origin_id)
        assert edited["draft"] is candidate["draft"] is (origin_id != selected_id)
    assert app.result(room).json()["draft"] is False


@pytest.mark.parametrize("method", ["api", "admin"])
def test_delete_keeps_cost_ledger_and_daily_cap(srv, method):
    app = srv.app
    _, room = app.create_room()
    _, other = app.create_room()
    room_id = srv.sql("SELECT room_id FROM rooms WHERE room_code = %s", (room.code,))[0]["room_id"]
    testdb.execute(srv.database_url,
                   "INSERT INTO llm_calls (room_id, stage, cost_usd, input_hash, created_at) "
                   "VALUES (%s, 'scenarios', 1.25, 'kept-input-hash', %s)", (room_id, srv.clock()))
    calls = srv.sql("SELECT * FROM llm_calls WHERE room_id = %s ORDER BY call_id", (room_id,))
    other_calls = srv.sql("SELECT * FROM llm_calls WHERE room_id <> %s ORDER BY call_id", (room_id,))
    total = srv.sql("SELECT sum(cost_usd) AS total FROM llm_calls")[0]["total"]
    guard = CostGuard(lambda: app.app.state.db, srv.clock, daily_cap_usd=1.0)
    with pytest.raises(LLMCallError, match="budget_exceeded"):
        app._call(guard, "scenarios")
    if method == "api":
        assert delete_room(app, room).status_code == 204
    else:
        counts = admin.delete_room(srv.database_url, room.code)
        assert counts["llm_calls"] == 0
        assert counts["profiles"] > 0
    assert srv.sql("SELECT * FROM llm_calls WHERE call_id = ANY(%s) ORDER BY call_id",
                   ([row["call_id"] for row in calls],)) == [{**row, "room_id": None} for row in calls]
    assert srv.sql("SELECT * FROM llm_calls WHERE room_id IS NOT NULL ORDER BY call_id") == other_calls
    assert srv.sql("SELECT sum(cost_usd) AS total FROM llm_calls")[0]["total"] == total
    with pytest.raises(LLMCallError, match="budget_exceeded"):
        app._call(guard, "scenarios")
    assert_error(app.get(f"/api/rooms/{room.code}"), 404, "not_found")
    assert app.get(f"/api/rooms/{other.code}").status_code == 200


@pytest.mark.parametrize("method", ["api", "admin"])
def test_failed_delete_rolls_back_cost_ledger_detachment(srv, monkeypatch, method):
    app = srv.app
    _, room = app.create_room()
    room_id = srv.sql("SELECT room_id FROM rooms WHERE room_code = %s", (room.code,))[0]["room_id"]
    before = srv.sql("SELECT * FROM llm_calls WHERE room_id = %s ORDER BY call_id", (room_id,))
    assert before
    original_async = psycopg.AsyncConnection.execute
    original_sync = psycopg.Connection.execute
    detached = []

    def fail_at_delete(query):
        if query == "UPDATE llm_calls SET room_id = NULL WHERE room_id = %s":
            detached.append(True)
        if query == "DELETE FROM rooms WHERE room_id = %s":
            raise psycopg.OperationalError("delete unavailable")

    async def execute_async(conn, query, *args, **kwargs):
        fail_at_delete(query)
        return await original_async(conn, query, *args, **kwargs)

    def execute_sync(conn, query, *args, **kwargs):
        fail_at_delete(query)
        return original_sync(conn, query, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(psycopg.AsyncConnection, "execute", execute_async)
        patch.setattr(psycopg.Connection, "execute", execute_sync)
        with pytest.raises(psycopg.OperationalError, match="delete unavailable"):
            if method == "api":
                delete_room(app, room)
            else:
                admin.delete_room(srv.database_url, room.code)
    assert detached == [True]
    assert srv.sql("SELECT * FROM llm_calls WHERE room_id = %s ORDER BY call_id", (room_id,)) == before
    assert app.get(f"/api/rooms/{room.code}").status_code == 200
