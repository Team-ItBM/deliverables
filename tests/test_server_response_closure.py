"""response_closure (AC4): 제출 수 도달·조기 생성 때 입력을 한 번 고정하고 마감한다.

동시성 케이스(CLS-N03, CLS-N04)는 같은 테스트 DB에 앱 두 개를 열고(컨테이너 두 개를 흉내 낸다),
각 앱의 TestClient로 두 요청을 스레드 장벽에서 같은 순간에 보낸다. 앱마다 DB 연결이 따로라
상태 전환 잠금은 DB에서만 맞춰질 수 있다.
"""

import pytest

from harness.server import db as testdb
from harness.server import pact_outputs as po
from harness.server.api import (assert_calls, assert_error, assert_status, default_profiles, run_concurrently)

case = pytest.mark.server_case
REPEAT = 20  # 결정 18
MEMO_300 = "가나다라마바사아자차" * 30


def _result(app, room):
    resp = app.result(room)
    assert resp.status_code == 200, resp.text[:300]
    return resp.json()


@case("CLS-P01")
def test_cls_p01_auto_generation_on_full_submissions(srv, expect):
    app = srv.app
    _, room = app.create_room()
    hold = app.replay.hold("pact", po.pact_item())
    for profile in room.profiles:
        assert app.submit_new(room, profile["profile_id"]).resp.status_code == 201
    hold.wait_started()
    assert app.room(room)["room_status"] == expect.at("during_generation")["room_status"]
    hold.release()
    app.join()
    done = expect.at("done")
    assert app.room(room)["room_status"] == done["room_status"]
    assert_calls(app.replay, done["calls"])
    model_input = app.replay.calls_for("pact")[0].model_input
    assert len(model_input["participant_ids"]) == done["model_input_participant_count"]
    assert len(model_input["responses"]) == done["model_input_response_count"]
    result = _result(app, room)
    assert result["included_count"] == done["included_count"]
    assert len(result["excluded_names"]) == done["excluded_names_count"]


@case("CLS-P02")
def test_cls_p02_same_name_submissions_counted(srv, expect):
    app = srv.app
    _, room = app.create_room()
    first = app.submit_new(room, "p1")
    second = app.submit_new(room, "p1")
    app.join()
    assert_calls(app.replay, expect.at("after_second")["calls"])
    app.replay.push("pact", po.pact_item())
    third = app.submit_new(room, "p2")
    app.join()
    assert_calls(app.replay, expect.at("after_third")["calls"])
    ids = {s.body["participant_id"] for s in (first, second, third)}
    assert len(ids) == expect["distinct_participant_ids"]
    excluded = _result(app, room)["excluded_names"]
    for pid in expect["excluded_names_include_profiles"]:
        assert room.names[pid] in excluded, f"excluded_names {excluded}에 {pid}의 이름이 없다"


@case("CLS-P03")
def test_cls_p03_early_generation_one_submission(srv, expect):
    app = srv.app
    _, room = app.create_room()
    assert app.submit_new(room, "p1").resp.status_code == 201
    app.replay.push("pact", po.pact_item())
    resp = app.generate(room)
    assert_status(resp, expect["http_status"])
    app.join()
    model_input = app.replay.calls_for("pact")[0].model_input
    assert len(model_input["participant_ids"]) == expect["model_input_participant_count"]
    result = _result(app, room)
    assert result["included_count"] == expect["included_count"]
    assert len(result["excluded_names"]) == expect["excluded_names_count"]


@case("CLS-P04")
def test_cls_p04_memo_bounds_accepted(srv, expect):
    app = srv.app
    _, room = app.create_room()
    variants = (lambda i: MEMO_300, None, lambda i: "")  # 정확히 300자, memo 생략, memo: ""
    assert len(MEMO_300) == 300
    last = None
    for profile, memo in zip(room.profiles, variants):
        if profile is room.profiles[-1]:
            app.replay.push("pact", po.pact_item())
        last = app.submit_new(room, profile["profile_id"], memo=memo)
        assert_status(last.resp, expect["http_status"])
    assert last.body["submitted_count"] == expect["submitted_count"]
    app.join()


@case("CLS-N01")
def test_cls_n01_early_generation_without_submissions(srv, expect):
    app = srv.app
    _, room = app.create_room()
    resp = app.generate(room)
    assert_error(resp, expect["http_status"], expect["error_code"])
    app.join()
    assert app.room(room)["room_status"] == expect["room_status"]
    assert_calls(app.replay, expect["calls"])


def _closure_snapshot(app, room):
    return {
        "submitted_count": app.room(room)["submitted_count"],
        "model_input": [c.model_input for c in app.replay.calls_for("pact")],
        "included_count": _result(app, room)["included_count"],
    }


@case("CLS-N02")
def test_cls_n02_submission_after_closure(srv, expect):
    app = srv.app
    _, room = app.create_room()
    assert app.submit_new(room, "p1").resp.status_code == 201
    late = app.session(room, "p2")
    assert late.status_code == 201
    app.replay.push("pact", po.pact_item())
    assert app.generate(room).status_code == 202
    app.join()
    before = _closure_snapshot(app, room)
    resp, _ = app.submit(room, late.json()["session_id"], app.answers(late.json()))
    assert_error(resp, expect["http_status"], expect["error_code"])
    app.join()
    after = _closure_snapshot(app, room)
    for name in expect["unchanged"]:
        assert after[name] == before[name], f"{name}이 바뀌었다"


@case("CLS-N03")
def test_cls_n03_last_submission_races_early_generation(srv, expect):
    first, second = srv.app, srv.open_app()
    for rep in range(REPEAT):
        submit_app, generate_app = (first, second) if rep % 2 == 0 else (second, first)
        _, room = first.create_room()
        for pid in ("p1", "p2"):
            assert first.submit_new(room, pid).resp.status_code == 201
        late = first.session(room, "p3").json()
        answers = first.answers(late, memo=lambda i: srv.memo(f"race{rep}-{i}"))
        before = srv.replay.counts()
        srv.replay.push("pact", po.pact_item())
        (sub_resp, _), gen_resp = run_concurrently(
            lambda: submit_app.submit(room, late["session_id"], answers),
            lambda: generate_app.generate(room),
        )
        first.join()
        second.join()
        winners = [r for r in (sub_resp, gen_resp) if 200 <= r.status_code < 300]
        losers = [r for r in (sub_resp, gen_resp) if not 200 <= r.status_code < 300]
        assert len(winners) == 1 and len(losers) == 1, (
            f"{rep}회: 제출 {sub_resp.status_code}, 조기 생성 {gen_resp.status_code}")
        assert_error(losers[0], expect["http_status"], expect["error_code"])
        assert_calls(srv.replay, expect["calls"], before=before)
        assert srv.replay.pending("pact") == 0
        results = first.results_body(room)["results"]
        assert len(results) == expect["result_attempts"], f"{rep}회: 결과 시도 {len(results)}개"
        accepted = 2 + (1 if 200 <= sub_resp.status_code < 300 else 0)
        included = _result(first, room)["included_count"]
        assert included in expect["included_count"] and included == accepted, (
            f"{rep}회: included_count {included}, 받아들여진 제출 {accepted}")


@case("CLS-N04")
def test_cls_n04_two_early_generations(srv, expect):
    first, second = srv.app, srv.open_app()
    _, room = first.create_room()
    assert first.submit_new(room, "p1").resp.status_code == 201
    srv.replay.push("pact", po.pact_item())
    # 충돌 시점을 통제한다(2026-11-05 사람 승인, AC4). 방 행을 먼저 잠가 두 요청이 모두 잠금 앞에 선 뒤에 푼다.
    # 잠금 없이 상태를 읽는 구현은 둘 다 open을 본 채 UPDATE에서 기다리다가 함께 이긴다. 1회 경쟁의 운에 맡기지 않는다.
    lock = testdb.RowLock(srv.database_url, "SELECT 1 FROM rooms WHERE room_code = %s FOR UPDATE", (room.code,))

    def release_when_both_wait():
        try:
            testdb.wait_for_lock_waiters(srv.database_url, 2)
        finally:
            lock.release()

    responses = run_concurrently(lambda: first.generate(room), lambda: second.generate(room), release_when_both_wait)[:2]
    # 상태 단언을 join() 앞에 둔다. 둘 다 이긴 구현이 빈 대기열 오류가 아니라 응답 코드로 보고되게 한다.
    assert sorted(r.status_code for r in responses) == expect["concurrent_statuses"]
    loser = max(responses, key=lambda r: r.status_code)
    assert_error(loser, loser.status_code, expect["error_code"])
    first.join()
    second.join()
    assert_calls(srv.replay, expect["calls"])


@case("CLS-N05")
def test_cls_n05_invalid_submissions_rejected(srv, expect):
    app = srv.app
    _, room = app.create_room(profiles=default_profiles(party_size=2))
    assert app.submit_new(room, "p1").resp.status_code == 201

    def attempt(mutate):
        session = app.session(room, "p2").json()
        answers = app.answers(session, memo=lambda i: srv.memo(f"n05{i}"))
        mutate(answers)
        resp, _ = app.submit(room, session["session_id"], answers)
        return resp

    def duplicate_scenario(answers):  # (a) 같은 scenario_id 두 번
        answers.append(dict(answers[0]))

    def other_option(answers):  # (b) 다른 문항의 option_id
        answers[0]["option_id"] = answers[1]["option_id"]

    def unknown_scenario(answers):  # (c) 없는 scenario_id
        answers[0]["scenario_id"] = "scenario-not-in-room"

    def missing_answer(answers):  # (d) 문항 하나 누락
        answers.pop()

    def long_memo(answers):  # (e) memo 301자
        answers[0]["memo"] = "가" * 301

    for mutate in (duplicate_scenario, other_option, unknown_scenario, missing_answer, long_memo):
        assert_error(attempt(mutate), expect["http_status"], expect["error_code"])
    app.join()
    assert app.room(room)["submitted_count"] == expect["submitted_count"]
    assert_calls(app.replay, expect["calls"])
