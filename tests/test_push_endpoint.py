"""푸시 구독 주소 제한, 발송 timeout, 구독 등록 멱등성(PR #16 리뷰 P1·푸시 중복 등록, AC18).

2026-11-05 사람 승인. 하니스 설정에만 `push.test`를 허용 호스트로 더했고 기본값은 실제 푸시 서비스 3곳이다.
허용 규칙: HTTPS, 포트 443, userinfo 없음, 호스트는 정확한 일치 또는 점 경계의 하위 도메인.
TEST_DATABASE_URL이 없으면 srv fixture를 쓰는 케이스는 skip한다.
"""

import pytest

from harness.server import pact_outputs as po
from harness.server import db as testdb

ALLOWED = [
    "https://fcm.googleapis.com/fcm/send/abc",
    "https://updates.push.services.mozilla.com/wpush/v2/abc",
    "https://web.push.apple.com/abc",
    "https://fcm.googleapis.com:443/fcm/send/abc",
]
BLOCKED = [
    "http://fcm.googleapis.com/fcm/send/abc",           # HTTPS가 아님
    "http://127.0.0.1:9000/internal",                   # 루프백
    "https://127.0.0.1/internal",
    "https://[::1]/internal",
    "https://169.254.169.254/latest/meta-data/",        # 메타데이터 주소
    "https://10.0.0.5/internal",                        # 내부 주소
    "https://2130706433/",                              # 십진 IP 표기
    "https://localhost/internal",
    "https://fcm.googleapis.com:8443/fcm/send/abc",     # 다른 포트
    "https://fcm.googleapis.com:notaport/abc",
    "https://user:pw@fcm.googleapis.com/abc",           # userinfo
    "https://fcm.googleapis.com@evil.example/abc",      # userinfo로 위장
    "https://evil.example\\@fcm.googleapis.com/abc",    # 역슬래시 파서 차이
    "https://evil.example#@fcm.googleapis.com/abc",     # 조각으로 위장
    "https://fcm.googleapis.com.evil.example/abc",      # 뒤에 붙인 이름
    "https://evilfcm.googleapis.com/abc",               # 점 경계 없는 앞 글자
    "https://sub.fcm.googleapis.com/abc",               # 정확 일치 호스트의 하위 도메인
    "https://evilpush.apple.com/abc",                   # 와일드카드의 점 경계 위반
    "https://push.apple.com/abc",                       # 와일드카드 기준 호스트 자체
    "https://notpush.services.mozilla.com/abc",
    "https://web.push.apple.com./abc",                  # 끝 점
    "https://fcm.googleapis.com\t.evil.example/abc",    # 제어 문자
    "https://fcm.googleapis.com\n/abc",
    "https://fсm.googleapis.com/abc",                   # 키릴 문자 с
    "ftp://fcm.googleapis.com/abc",
    "mock://push",
    "//fcm.googleapis.com/abc",
    "https://fcm.googleapis.com/" + "a" * 2100,         # 길이 상한
]


def _subscribe_host(srv, endpoint):
    app = srv.app
    _, room = app.create_room()
    return app.subscribe(room, "host", endpoint=endpoint)


@pytest.mark.parametrize("endpoint", ALLOWED)
def test_real_push_services_are_accepted(srv, endpoint):
    assert _subscribe_host(srv, endpoint).status_code == 201


@pytest.mark.parametrize("endpoint", BLOCKED)
def test_other_endpoints_are_rejected(srv, endpoint):
    resp = _subscribe_host(srv, endpoint)
    assert resp.status_code == 422, resp.text[:200]
    assert resp.json()["error"]["code"] == "invalid_input"
    assert srv.sql("SELECT count(*) AS n FROM push_subscriptions")[0]["n"] == 0


def test_default_hosts_exclude_test_host(server):
    defaults = server.app.Settings(database_url="x", pool_path="x").push_allowed_hosts
    assert set(defaults) == {"fcm.googleapis.com", "*.push.services.mozilla.com", "*.push.apple.com"}


def test_stored_bad_endpoint_is_not_sent(srv):
    """제한을 넣기 전에 저장된 구독은 발송 때 다시 막는다."""
    app = srv.app
    room = next(r for r in app.ready_room() if hasattr(r, "code"))
    session = srv.sql("SELECT room_id FROM rooms WHERE room_code = %s", (room.code,))[0]
    testdb.execute(srv.database_url,
                   "INSERT INTO push_subscriptions (subscription_id, room_id, role, session_id, endpoint, keys, created_at) "
                   "VALUES (gen_random_uuid(), %s, 'host', NULL, 'http://127.0.0.1:9/x', NULL, now())",
                   (session["room_id"],))
    srv.push.sent.clear()
    app.dispatch(room.code, "ready:99")
    assert srv.push.sent == []
    row = srv.sql("SELECT status_code FROM notifications WHERE event = 'ready:99'")[0]
    assert row["status_code"] == 0


def test_host_subscription_is_idempotent(srv):
    app = srv.app
    _, room = app.create_room()
    endpoint = f"https://push.test/{room.code}/same"
    first = app.subscribe(room, "host", endpoint=endpoint)
    second = app.subscribe(room, "host", endpoint=endpoint)
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["subscription_id"] == first.json()["subscription_id"]
    assert srv.sql("SELECT count(*) AS n FROM push_subscriptions")[0]["n"] == 1


def test_participant_duplicate_subscription_sends_once(srv):
    """같은 방·역할·세션·endpoint를 두 번 등록해도 결과 선택 한 번에 한 번만 보낸다."""
    app = srv.app
    _, room = app.create_room()
    session = app.session(room, "p1").json()
    endpoint = f"https://push.test/{room.code}/p1"
    for _ in range(2):
        assert app.subscribe(room, "participant", session_id=session["session_id"], endpoint=endpoint).status_code < 300
    app.replay.push("pact", po.pact_item())
    answers = app.answers(session, memo=lambda i: srv.memo(f"dup{i}"))
    assert app.submit(room, session["session_id"], answers)[0].status_code == 201
    assert app.submit_new(room, "p2").resp.status_code == 201
    assert app.submit_new(room, "p3").resp.status_code == 201
    app.join()
    mark = srv.push.count()
    assert app.select(room, app.result(room).json()["result_id"]).status_code == 200
    assert [s["endpoint"] for s in srv.push.since(mark)] == [endpoint]


def test_resubscribe_updates_keys(srv):
    app = srv.app
    _, room = app.create_room()
    endpoint = f"https://push.test/{room.code}/rotated"
    app.subscribe(room, "host", subscription={"endpoint": endpoint, "keys": {"p256dh": "old", "auth": "old"}})
    app.subscribe(room, "host", subscription={"endpoint": endpoint, "keys": {"p256dh": "new", "auth": "new"}})
    rows = srv.sql("SELECT keys FROM push_subscriptions")
    assert [r["keys"]["p256dh"] for r in rows] == ["new"]


def test_different_sessions_keep_separate_subscriptions(srv):
    """멱등 범위는 방·역할·세션·endpoint다. 세션이 다르면 다른 구독이다."""
    app = srv.app
    _, room = app.create_room()
    endpoint = f"https://push.test/{room.code}/shared-device"
    for pid in ("p1", "p2"):
        session = app.session(room, pid).json()
        assert app.subscribe(room, "participant", session_id=session["session_id"], endpoint=endpoint).status_code == 201
    assert srv.sql("SELECT count(*) AS n FROM push_subscriptions")[0]["n"] == 2


def test_slow_subscription_does_not_serialize_delivery(srv):
    """발송은 구독마다 동시에 진행한다. 한 구독이 늦어도 다른 구독이 그 뒤로 밀리지 않는다."""
    import threading

    app = srv.app
    _, room = app.create_room()
    for name in ("a", "b"):
        assert app.subscribe(room, "host", endpoint=f"https://push.test/{room.code}/{name}").status_code == 201
    barrier = threading.Barrier(2, timeout=5)
    original = srv.push.send

    def send(subscription, payload):
        barrier.wait()  # 둘이 동시에 들어와야 풀린다. 순차 발송이면 BrokenBarrierError로 상태 0이 남는다
        return original(subscription, payload)

    srv.push.send = send
    app.dispatch(room.code, "ready:1")
    assert sorted(r["status_code"] for r in srv.sql("SELECT status_code FROM notifications")) == [201, 201]


def _sender_call(monkeypatch):
    import pywebpush

    from travel.server.main import WebPushSender

    seen = {}

    class Response:
        status_code = 201

    def fake_webpush(**kwargs):
        seen.update(kwargs)
        return Response()

    monkeypatch.setattr(pywebpush, "webpush", fake_webpush)
    sender = WebPushSender("private", "mailto:test@example.com")
    assert sender.send({"endpoint": "https://fcm.googleapis.com/x", "keys": {}}, {"text": "t"}) == 201
    return seen


def test_web_push_sender_sets_timeout(monkeypatch):
    seen = _sender_call(monkeypatch)
    assert isinstance(seen.get("timeout"), (int, float)) and 0 < seen["timeout"] <= 30


def test_web_push_sender_does_not_follow_redirects(monkeypatch):
    import requests
    from requests.adapters import BaseAdapter

    calls = []

    class Redirecting(BaseAdapter):
        def send(self, request, **kwargs):
            calls.append(request.url)
            response = requests.Response()
            response.status_code = 302
            response.url = request.url
            response.headers["Location"] = "http://127.0.0.1:9/internal"
            response.request = request
            response.raw = None
            response._content = b""
            return response

        def close(self):
            pass

    session = _sender_call(monkeypatch).get("requests_session")
    assert session is not None
    session.mount("https://", Redirecting())
    session.mount("http://", Redirecting())
    response = session.post("https://fcm.googleapis.com/x", data=b"")
    assert response.status_code == 302
    assert calls == ["https://fcm.googleapis.com/x"]


def test_schema_migration_removes_duplicates_keeping_oldest(srv):
    """유일 색인 전에 쌓인 중복을 지운다. 먼저 등록한 행이 남고, 지운 수를 돌려준다."""
    server_db = srv.server.db
    app = srv.app
    _, room = app.create_room()
    room_id = srv.sql("SELECT room_id FROM rooms WHERE room_code = %s", (room.code,))[0]["room_id"]
    testdb.execute(srv.database_url, "DROP INDEX push_subscriptions_one_per_device")
    for at in ("2026-11-01", "2026-11-02", "2026-11-03"):
        testdb.execute(srv.database_url,
                       "INSERT INTO push_subscriptions (subscription_id, room_id, role, session_id, endpoint, created_at) "
                       "VALUES (gen_random_uuid(), %s, 'host', NULL, 'https://push.test/dup', %s)", (room_id, at))
    summary = server_db.init_schema(srv.database_url)
    assert summary == {"duplicate_push_subscriptions_removed": 2}
    rows = srv.sql("SELECT created_at::date::text AS day FROM push_subscriptions")
    assert [r["day"] for r in rows] == ["2026-11-01"]
    assert server_db.init_schema(srv.database_url) == {"duplicate_push_subscriptions_removed": 0}
