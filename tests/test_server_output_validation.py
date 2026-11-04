"""output_validation (AC10): 형식 오류는 이유를 붙여 최대 1회 재요청하고, 다시 실패한 출력은 쓰지 않는다.

시각은 가짜 현재 시각 함수로 옮긴다. 시계는 테스트가 옮기기 전까지 멈춰 있으므로 generating 전환 시각은
붙잡은 호출이 시작될 때의 시계 값이다. OUT-N06은 같은 DB에 앱 두 개를 연다. 앱 A가 호출을 붙잡아 방을
generating에 두고, 앱 B(작업이 없는 새 인스턴스, 재시작한 컨테이너 흉내)가 멈춤 점검과 재시도를 한다(2026-11-05 사람 결정).
"""

import pytest

from harness.server import pact_outputs as po
from harness.server import scenario_outputs as so
from harness.server.api import assert_calls, assert_error, assert_status, error_codes_of
from harness.server.replay import CallError, Text

case = pytest.mark.server_case


def _submit_all(app, room):
    for profile in room.profiles:
        resp = app.submit_new(room, profile["profile_id"]).resp
        assert resp.status_code == 201, resp.text[:300]


def _generated(app, *pact_items):
    _, room = app.create_room()
    app.replay.push("pact", *pact_items)
    _submit_all(app, room)
    app.join()
    return room


def _status(app, room):
    view = app.room(room)
    return view["room_status"], view.get("failure_reason")


def _normal(app, room):
    return sum(1 for r in app.results_body(room)["results"] if r["state"] == "normal")


def _regeneration_accepted(app, room):
    # note: "정상 결과 1개라 재생성할 수 있다"
    app.replay.push("pact", po.pact_item())
    resp = app.regenerate(room)
    assert 200 <= resp.status_code < 300, f"재생성이 거부됐다: HTTP {resp.status_code} {resp.text[:200]}"
    app.join()


def _assert_retry_with_same_input(app, room, expected_status, replay=None, first_input=None):
    replay = replay or app.replay
    replay.push("pact", po.pact_item())
    resp = app.retry(room)
    assert_status(resp, expected_status)
    app.join()
    assert replay.calls_for("pact")[-1].model_input == first_input, "재시도 model_input이 처음과 다르다"


@case("OUT-P01")
def test_out_p01_truncated_json_then_valid(srv, expect):
    app = srv.app
    room = _generated(app, Text(po.TRUNCATED_OUTPUT), po.pact_item())
    assert _status(app, room)[0] == expect["room_status"]
    assert_calls(app.replay, expect["calls"])
    calls = app.replay.calls_for("pact")
    assert not set(expect["repair_error_codes"]) - error_codes_of(calls[1].repair_errors)
    assert calls[1].model_input == calls[0].model_input, "재요청 model_input이 1회차와 다르다"
    assert _normal(app, room) == expect["normal_results"]
    _regeneration_accepted(app, room)


@case("OUT-P02")
def test_out_p02_unknown_reference_then_valid(srv, expect):
    app = srv.app
    room = _generated(app, po.pact_item("unknown_response"), po.pact_item())
    assert _status(app, room)[0] == expect["room_status"]
    assert_calls(app.replay, expect["calls"])
    repair = app.replay.calls_for("pact")[1].repair_errors
    assert not set(expect["repair_error_codes"]) - error_codes_of(repair)


@case("OUT-P03")
def test_out_p03_retry_after_output_failure(srv, expect):
    app = srv.app
    room = _generated(app, po.pact_item("extra_key"), po.pact_item("status_combination"))
    assert _status(app, room)[0] == "failed", "준비(OUT-N01 상태)가 failed가 아니다"
    first_input = app.replay.calls_for("pact")[0].model_input
    _assert_retry_with_same_input(app, room, expect["http_status"], first_input=first_input)
    assert _status(app, room)[0] == expect["room_status"]
    assert _normal(app, room) == expect["normal_results"]
    _regeneration_accepted(app, room)


@case("OUT-P04")
def test_out_p04_rate_limit_waits_retry_after(srv, expect):
    app = srv.app
    _, room = app.create_room()
    app.replay.push("pact", CallError("rate_limited", 5), po.pact_item())
    mark = srv.sleeper.mark()
    _submit_all(app, room)
    app.join()
    assert _status(app, room)[0] == expect["room_status"]
    assert srv.sleeper.since(mark) == expect["waits"]


@case("OUT-N01")
def test_out_n01_second_invalid_output_fails(srv, expect):
    app = srv.app
    room = _generated(app, po.pact_item("extra_key"), po.pact_item("status_combination"))
    status, reason = _status(app, room)
    assert status == expect["room_status"] and reason == expect["failure_reason"]
    assert_calls(app.replay, expect["calls"])
    assert _normal(app, room) == expect["normal_results"]
    # note: "결과 조회와 재생성은 409 invalid_state"
    assert_error(app.result(room), expect["http_status"], expect["error_code"])
    assert_error(app.regenerate(room), expect["http_status"], expect["error_code"])


@case("OUT-N02")
def test_out_n02_timeouts_exhaust_retries(srv, expect):
    app = srv.app
    _, room = app.create_room()
    app.replay.push("pact", CallError("timeout"), CallError("timeout"), CallError("timeout"))
    mark = srv.sleeper.mark()
    _submit_all(app, room)
    app.join()
    status, reason = _status(app, room)
    assert status == expect["room_status"] and reason == expect["failure_reason"]
    assert_calls(app.replay, expect["calls"])
    waits = srv.sleeper.since(mark)
    bases = expect["backoff_waits"]
    jitter = app.settings.retry_jitter_seconds
    assert len(waits) == len(bases), f"대기 기록 {waits}"
    for wait, base in zip(waits, bases):
        assert base <= wait <= base + jitter, f"대기 {wait}초가 {base}초 + 지터 {jitter}초 범위 밖이다"
    assert _normal(app, room) == expect["normal_results"]


@case("OUT-N03")
def test_out_n03_incomplete_twice(srv, expect):
    app = srv.app
    room = _generated(app, po.incomplete_item(), po.incomplete_item())
    status, reason = _status(app, room)
    assert status == expect["room_status"] and reason == expect["failure_reason"]
    assert_calls(app.replay, expect["calls"])


@case("OUT-N04")
def test_out_n04_scenario_output_invalid_twice(srv, expect):
    app = srv.app
    invalid = so.ex1_output()
    invalid["invented"] = True
    app.replay.push("scenarios", so.scenario_item(invalid))
    _, room = app.create_room(scenario=so.scenario_item(invalid))
    assert app.room(room)["scenario_status"] == expect["scenario_status"]
    assert_calls(app.replay, expect["calls"])
    assert_error(app.session(room, "p1"), expect["http_status"], expect["error_code"])


@case("OUT-N05")
def test_out_n05_job_time_limit(srv, expect):
    app = srv.app
    _, room = app.create_room()
    hold = app.replay.hold("pact", po.pact_item())
    _submit_all(app, room)
    hold.wait_started()
    switched = srv.clock()
    for at, seconds in (("4m59s", 299), ("5m", 300)):
        srv.clock.set_after(switched, seconds)
        app.enforce_deadlines()
        checkpoint = expect.at(at)
        if at == "5m":
            app.join()
        status, reason = _status(app, room)
        assert status == checkpoint["room_status"], f"{at}: {status}"
        if "failure_reason" in checkpoint:
            assert reason == checkpoint["failure_reason"]
        if "normal_results" in checkpoint:
            assert _normal(app, room) == checkpoint["normal_results"]
    # note: "뒤늦게 끝난 호출의 출력은 정상 결과로 저장하지 않는다"
    hold.release()
    app.join()
    assert _normal(app, room) == expect.at("after_late_output")["normal_results"]
    first_input = app.replay.calls_for("pact")[0].model_input
    _assert_retry_with_same_input(app, room, expect.at("retry")["http_status"], first_input=first_input)


@case("OUT-N06")
def test_out_n06_stalled_generation_recovered(srv, expect):
    crashed = srv.app
    _, room = crashed.create_room()
    hold = crashed.replay.hold("pact", po.pact_item())
    _submit_all(crashed, room)
    hold.wait_started()
    switched = srv.clock()
    restarted = srv.open_app(replay=srv.new_replay())
    for at, seconds in (("9m59s", 599), ("10m", 600)):
        srv.clock.set_after(switched, seconds)
        restarted.recover_stalled()
        checkpoint = expect.at(at)
        status, reason = _status(restarted, room)
        assert status == checkpoint["room_status"], f"{at}: {status}"
        if "failure_reason" in checkpoint:
            assert reason == checkpoint["failure_reason"]
        if "normal_results" in checkpoint:
            assert _normal(restarted, room) == checkpoint["normal_results"]
    first_input = crashed.replay.calls_for("pact")[0].model_input
    _assert_retry_with_same_input(restarted, room, expect.at("retry")["http_status"], first_input=first_input)
