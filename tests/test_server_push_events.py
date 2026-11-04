"""push_events (AC18): 허용한 구독에만 보내고, 같은 이벤트의 중복 알림을 막는다.

준비(§0-1): 방장 구독 1개, 참여자 구독 2개(p1·p2 세션에 묶음), 구독하지 않은 참여자 1명(p3). 가짜 푸시 발송기.
발송 수는 가짜 발송기 기록을 endpoint로 나눠 센다. 알림 기록은 notifications(event, subscription_id) 행으로 센다.
"""

import pytest

from harness.server import pact_outputs as po
from harness.server.api import assert_error
from harness.server.privacy import scan_private

case = pytest.mark.server_case
EXPIRED_STATUS = 410
SERVER_ERROR_STATUS = 500


class PushRoom:
    def __init__(self, app):
        self.app = app
        _, self.room = app.create_room()
        assert self.room is not None
        resp = app.subscribe(self.room, "host", endpoint=f"https://push.test/{self.room.code}/host")
        assert resp.status_code == 201, resp.text[:300]
        self.subscription_ids = {"host": resp.json()["subscription_id"]}
        self.endpoints = {"host": f"https://push.test/{self.room.code}/host"}
        self.sessions = {}
        for pid in ("p1", "p2"):
            session = app.session(self.room, pid).json()
            endpoint = f"https://push.test/{self.room.code}/{pid}"
            resp = app.subscribe(self.room, "participant", session_id=session["session_id"], endpoint=endpoint)
            assert resp.status_code == 201, resp.text[:300]
            self.sessions[pid] = session
            self.endpoints[pid] = endpoint
            self.subscription_ids[pid] = resp.json()["subscription_id"]

    def submit(self, pid):
        if pid in self.sessions:
            session = self.sessions.pop(pid)
            answers = self.app.answers(session, memo=lambda i: self.app.harness.memo(f"{self.room.code}{pid}{i}"))
            resp, _ = self.app.submit(self.room, session["session_id"], answers)
        else:
            resp = self.app.submit_new(self.room, pid).resp
        assert resp.status_code == 201, resp.text[:300]

    def submit_all(self):
        for pid in ("p1", "p2", "p3"):
            self.submit(pid)


def _counts(push, mark, push_room):
    sent = push.since(mark)
    by = {role: sum(1 for s in sent if s["endpoint"] == ep) for role, ep in push_room.endpoints.items()}
    return by, len(sent), sent


def _assert_sent(push, mark, push_room, expected):
    by, total, _ = _counts(push, mark, push_room)
    if "host" in expected:
        assert by["host"] == expected["host"], f"방장 구독 {by['host']}건"
    if "participant_each" in expected:
        for pid in ("p1", "p2"):
            assert by[pid] == expected["participant_each"], f"{pid} 구독 {by[pid]}건"
    if "total" in expected:
        assert total == expected["total"], f"전체 {total}건"


def _auto_success(srv, app):
    pr = PushRoom(app)
    mark = srv.push.count()
    app.replay.push("pact", po.pact_item())
    pr.submit_all()
    app.join()
    return pr, mark


def _auto_failure_then_retry(srv, app, expect=None):
    pr = PushRoom(app)
    mark = srv.push.count()
    app.replay.push("pact", po.pact_item("extra_key"), po.pact_item("extra_key"))
    pr.submit_all()
    app.join()
    assert app.room(pr.room)["room_status"] == "failed"
    if expect is not None:
        _assert_sent(srv.push, mark, pr, expect.at("after_failure")["push_sent"])
    mark = srv.push.count()
    app.replay.push("pact", po.pact_item())
    assert app.retry(pr.room).status_code == 202
    app.join()
    if expect is not None:
        _assert_sent(srv.push, mark, pr, expect.at("after_retry_success")["push_sent"])
    return pr


def _early_success(srv, app):
    pr = PushRoom(app)
    pr.submit("p1")
    mark = srv.push.count()
    app.replay.push("pact", po.pact_item())
    assert app.generate(pr.room).status_code == 202
    app.join()
    return pr, mark


@case("PSH-P01")
def test_psh_p01_auto_success_notifies(srv, expect):
    app = srv.app
    pr, mark = _auto_success(srv, app)
    _assert_sent(srv.push, mark, pr, expect["push_sent"])
    _, _, sent = _counts(srv.push, mark, pr)
    host_texts = [(s["object"] or {}).get("text") for s in sent if s["endpoint"] == pr.endpoints["host"]]
    assert host_texts and all(isinstance(t, str) and expect["host_push_text"] in t for t in host_texts), host_texts


@case("PSH-P02")
def test_psh_p02_failure_then_retry_success(srv, expect):
    _auto_failure_then_retry(srv, srv.app, expect)


@case("PSH-P03")
def test_psh_p03_early_success_notifies(srv, expect):
    app = srv.app
    pr, mark = _early_success(srv, app)
    _assert_sent(srv.push, mark, pr, expect["push_sent"])


@case("PSH-P04")
def test_psh_p04_send_failures(srv, expect):
    app = srv.app
    pr = PushRoom(app)
    targets = {EXPIRED_STATUS: "p1", SERVER_ERROR_STATUS: "p2"}
    for status, pid in targets.items():
        srv.push.status_by_endpoint[pr.endpoints[pid]] = status
    mark = srv.push.count()
    app.replay.push("pact", po.pact_item())
    pr.submit_all()
    app.join()
    assert app.room(pr.room)["room_status"] == expect["room_status"]
    kept = {row["id"] for row in srv.sql("SELECT subscription_id::text AS id FROM push_subscriptions")}
    for status, state in expect["subscription_by_send_status"].items():
        sid = str(pr.subscription_ids[targets[int(status)]])
        assert (sid in kept) is {"kept": True, "removed": False}[state], f"{status} 구독이 {state}가 아니다"
    # note: "다른 구독 발송은 그대로": 모든 구독이 같은 횟수로 발송 시도됐다
    by, _, _ = _counts(srv.push, mark, pr)
    assert by["host"] >= 1 and len(set(by.values())) == 1, by


@case("PSH-N01")
def test_psh_n01_reprocessing_does_not_resend(srv, expect):
    app = srv.app
    pr, _ = _auto_success(srv, app)
    events = sorted({row["event"] for row in srv.sql("SELECT event FROM notifications")})
    assert events, "notifications 행이 없다"
    mark = srv.push.count()
    for event in events:
        for _ in range(2):
            app.dispatch(pr.room.code, event)
    app.join()
    _assert_sent(srv.push, mark, pr, expect["push_sent"])
    rows = srv.sql("SELECT event, subscription_id::text AS sid, count(*) AS n FROM notifications GROUP BY event, subscription_id")
    assert rows
    for row in rows:
        assert row["n"] == expect["notification_records_per_pair"], row


@case("PSH-N02")
def test_psh_n02_push_bodies_hold_status_only(srv, expect):
    # 검사 범위: PSH-P01~P03 흐름에서 가짜 발송기가 받은 모든 본문
    app = srv.app
    rooms = [_auto_success(srv, app)[0], _auto_failure_then_retry(srv, app), _early_success(srv, app)[0]]
    assert srv.push.sent, "발송된 본문이 없다"
    room_by_endpoint = {ep: pr.room for pr in rooms for ep in pr.endpoints.values()}
    problems = []
    for i, sent in enumerate(srv.push.sent):
        problems += scan_private(sent["text"], expect["privacy_scan"], srv.ctx, f"푸시 {i}")
        # note: "본문은 키가 text·url 둘인 JSON 객체이고 url에 room_code가 있으며 host_token이 없다"
        body = sent["object"]
        assert body is not None and set(body) == set(expect["push_payload_keys"]), f"푸시 {i} 본문: {sent['text'][:200]}"
        assert all(isinstance(v, str) and v for v in body.values()), f"푸시 {i} 본문 값이 문자열이 아니다"
        room = room_by_endpoint[sent["endpoint"]]
        assert room.code in body["url"], f"푸시 {i}의 url에 room_code가 없다"
        assert room.host_token not in sent["text"], f"푸시 {i} 본문에 host_token이 있다"
    assert not problems, "\n".join(problems)


@case("PSH-N03")
def test_psh_n03_subscription_without_endpoint(srv, expect):
    app = srv.app
    _, room = app.create_room()
    session = app.session(room, "p1").json()
    resp = app.subscribe(room, "participant", session_id=session["session_id"],
                         subscription={"keys": {"p256dh": "test-p256dh", "auth": "test-auth"}})
    assert_error(resp, expect["http_status"], expect["error_code"])
