"""duplicate_name (AC16): 같은 이름의 새 제출은 허용하고 별도 ID로 저장한다. 전송 재시도는 같은 건이다.

제출 내용을 읽는 API가 없으므로(§0-B), "처음 저장한 제출이 그대로다"는 조기 생성 뒤 추천 model_input의
그 참여자 응답(option_id, memo)으로 확인한다.
"""

import pytest

from harness.server import pact_outputs as po
from harness.server.api import assert_error, assert_status
from harness.server.privacy import scan_private

case = pytest.mark.server_case


def _stored_answers(app, room, participant_id):
    """조기 생성으로 입력을 고정하고, 추천 model_input에 들어간 그 참여자 응답을 문항 순서로 돌려준다."""
    app.replay.push("pact", po.pact_item())
    assert app.generate(room).status_code == 202
    app.join()
    model_input = app.replay.calls_for("pact")[-1].model_input
    rows = [r for r in model_input["responses"] if r["participant_id"] == participant_id]
    return model_input, sorted((r["scenario_id"], r["option_id"], r.get("memo")) for r in rows)


def _sent(answers):
    return sorted((a["scenario_id"], a["option_id"], a.get("memo")) for a in answers)


@case("DUP-P01")
def test_dup_p01_notice_for_submitted_name(srv, expect):
    app = srv.app
    _, room = app.create_room()
    fresh = app.session(room, "p1").json()
    assert app.submit_new(room, "p1").resp.status_code == 201
    sessions = {pid: app.session(room, pid) for pid in ("p1", "p2")}
    for pid, resp in sessions.items():
        assert resp.status_code == 201, resp.text[:300]
    for pid, notice in expect["duplicate_name_notice"].items():
        assert sessions[pid].json()["duplicate_name_notice"] is notice, f"{pid}의 duplicate_name_notice"
    profiles = {p["profile_id"]: p for p in app.room(room)["profiles"]}
    for pid, flag in expect["has_submission"].items():
        assert profiles[pid]["has_submission"] is flag, f"{pid}의 has_submission"
    # note: "두 세션 응답 모두 이전 선택·메모가 없다". 메모는 privacy_scan으로, 선택은 제출 전 세션과 같은지로 본다
    problems = []
    for pid, resp in sessions.items():
        problems += scan_private(resp.json(), expect["privacy_scan"], srv.ctx, f"{pid} 세션")
    assert not problems, "\n".join(problems)
    again = sessions["p1"].json()
    assert set(again) == set(fresh), f"제출 뒤 세션 응답의 키가 다르다: {sorted(set(again) ^ set(fresh))}"
    assert again["scenarios"] == fresh["scenarios"], "제출 뒤 세션 문항이 제출 전과 다르다"


@case("DUP-P02")
def test_dup_p02_second_submission_same_name(srv, expect):
    app = srv.app
    _, room = app.create_room()
    first = app.submit_new(room, "p1")
    second = app.submit_new(room, "p1")
    assert_status(second.resp, expect["http_status"])
    assert second.body["participant_id"] != first.body["participant_id"]
    assert second.body["submitted_count"] == expect["submitted_count"]


@case("DUP-P03")
def test_dup_p03_retransmission_is_same_submission(srv, expect):
    app = srv.app
    _, room = app.create_room()
    first = app.submit_new(room, "p1")
    assert first.resp.status_code == 201
    before = {"submitted_count": app.room(room)["submitted_count"]}
    resp, _ = app.submit(room, first.session["session_id"], first.answers, key=first.key)
    assert_status(resp, expect["http_status"])
    assert resp.json()["participant_id"] == first.body["participant_id"]
    after = {"submitted_count": app.room(room)["submitted_count"]}
    for name in expect["unchanged"]:
        assert after[name] == before[name], f"{name}이 바뀌었다"


@case("DUP-N01")
def test_dup_n01_same_key_different_body(srv, expect):
    app = srv.app
    _, room = app.create_room()
    first = app.submit_new(room, "p1")
    assert first.resp.status_code == 201
    changed = [dict(a) for a in first.answers]
    options = [o["option_id"] for o in first.session["scenarios"][0]["options"]]
    changed[0]["option_id"] = next(o for o in options if o != changed[0]["option_id"])
    resp, _ = app.submit(room, first.session["session_id"], changed, key=first.key)
    assert_error(resp, expect["http_status"], expect["error_code"])

    def submission():
        _, stored = _stored_answers(app, room, first.body["participant_id"])
        assert stored == _sent(first.answers), "처음 저장한 제출이 바뀌었다"

    for name in expect["unchanged"]:
        {"submission": submission}[name]()


@case("DUP-N02")
def test_dup_n02_used_session(srv, expect):
    app = srv.app
    _, room = app.create_room()
    first = app.submit_new(room, "p1")
    assert first.resp.status_code == 201
    other = app.answers(first.session, choose=1, memo=lambda i: srv.memo(f"dupn02{i}"))
    resp, _ = app.submit(room, first.session["session_id"], other)
    assert_error(resp, expect["http_status"], expect["error_code"])

    def submission():
        model_input, stored = _stored_answers(app, room, first.body["participant_id"])
        assert stored == _sent(first.answers), "기존 제출이 바뀌었다"
        assert model_input["participant_ids"] == [first.body["participant_id"]]

    for name in expect["unchanged"]:
        {"submission": submission}[name]()


@case("DUP-N03")
def test_dup_n03_missing_idempotency_key(srv, expect):
    app = srv.app
    _, room = app.create_room()
    session = app.session(room, "p1").json()
    resp, _ = app.submit(room, session["session_id"], app.answers(session), key=None)
    assert_error(resp, expect["http_status"], expect["error_code"])


@case("DUP-N04")
def test_dup_n04_unknown_profile(srv, expect):
    app = srv.app
    _, room = app.create_room()
    assert_error(app.session(room, "p9"), expect["http_status"], expect["error_code"])
