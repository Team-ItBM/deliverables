"""regeneration (AC17): 같은 고정 입력으로 정상 결과를 한 번 더 만들고 둘 중 하나를 고른다.

정상·실패 결과 수는 방장 결과 목록의 state로 센다. 재생성 실패는 timeout 3회(최초 + 재시도 2회)로 만든다.
"""

import json
import uuid

import pytest

from harness.server import pact_outputs as po
from harness.server.api import assert_calls, assert_error, assert_status
from harness.server.replay import CallError

case = pytest.mark.server_case


def _results(app, room):
    return sorted(app.results_body(room)["results"], key=lambda r: r["attempt"])


def _count(app, room, state):
    return sum(1 for r in _results(app, room) if r["state"] == state)


def _row(srv, result_id):
    return srv.sql("SELECT * FROM results WHERE result_id::text = %s", (str(result_id),))


def _normalized(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _regenerate(app, room, *items):
    app.replay.push("pact", *(items or (po.pact_item(),)))
    resp = app.regenerate(room)
    app.join()
    return resp


def _failed_regeneration(app, room):
    return _regenerate(app, room, CallError("timeout"), CallError("timeout"), CallError("timeout"))


@case("REG-P01")
def test_reg_p01_regeneration_keeps_both(srv, expect):
    app = srv.app
    room, _ = app.ready_room()
    first = _results(app, room)[0]
    before = {"original_result": (first, _row(srv, first["result_id"]))}
    resp = _regenerate(app, room)
    assert_status(resp, expect["http_status"])
    assert _count(app, room, "normal") == expect["normal_results"]
    # note: "두 추천 호출의 model_input이 정규화한 JSON으로 같다"
    inputs = [_normalized(c.model_input) for c in app.replay.calls_for("pact")]
    assert len(inputs) == 2 and inputs[0] == inputs[1], "재생성 model_input이 최초와 다르다"
    after = {"original_result": (next(r for r in _results(app, room) if r["result_id"] == first["result_id"]),
                                 _row(srv, first["result_id"]))}
    for name in expect["unchanged"]:
        assert after[name] == before[name], f"{name}이 바뀌었다"


@case("REG-P02")
def test_reg_p02_select_between_results(srv, expect):
    app = srv.app
    room, _ = app.ready_room()
    assert _regenerate(app, room).status_code == 202
    first, second = [r["result_id"] for r in _results(app, room) if r["state"] == "normal"]
    shown = {}
    for chosen in (second, first):
        resp = app.select(room, chosen)
        assert_status(resp, expect["http_status"])
        shown["last_selected"] = chosen
        assert app.result(room).json()["result_id"] == shown[expect["shared_result"]]


@case("REG-P03")
def test_reg_p03_failed_regeneration_not_counted(srv, expect):
    app = srv.app
    room, _ = app.ready_room()
    _failed_regeneration(app, room)
    failed = expect.at("after_failed_regeneration")
    assert _count(app, room, "failed") == failed["failed_results"]
    assert _count(app, room, "normal") == failed["normal_results"]
    again = expect.at("after_second_regeneration")
    resp = _regenerate(app, room)
    assert_status(resp, again["http_status"])
    assert _count(app, room, "normal") == again["normal_results"]


@case("REG-N01")
def test_reg_n01_third_normal_rejected(srv, expect):
    app = srv.app
    room, _ = app.ready_room()
    assert _regenerate(app, room).status_code == 202
    before = {"calls": app.replay.counts()}
    resp = app.regenerate(room)
    app.join()
    assert_error(resp, expect["http_status"], expect["error_code"])
    after = {"calls": app.replay.counts()}
    for name in expect["unchanged"]:
        assert after[name] == before[name], f"{name}이 바뀌었다"


@case("REG-N02")
def test_reg_n02_regeneration_while_generating(srv, expect):
    app = srv.app
    room, _ = app.ready_room()
    before = app.replay.counts()
    hold = app.replay.hold("pact", po.pact_item())
    assert app.regenerate(room).status_code == 202
    hold.wait_started()
    resp = app.regenerate(room)
    assert_error(resp, expect["http_status"], expect["error_code"])
    hold.release()
    app.join()
    assert_calls(app.replay, expect["calls_added"], before=before)


@case("REG-N03")
def test_reg_n03_invalid_selection(srv, expect):
    app = srv.app
    room, _ = app.ready_room()
    _failed_regeneration(app, room)
    failed_id = next(r["result_id"] for r in _results(app, room) if r["state"] == "failed")
    before = {"selected_result": app.result(room).json()["result_id"]}
    targets = {"unknown_result": str(uuid.uuid4()), "failed_result": failed_id}
    for at, result_id in targets.items():
        checkpoint = expect.at(at)
        assert_error(app.select(room, result_id), checkpoint["http_status"], checkpoint["error_code"])
    after = {"selected_result": app.result(room).json()["result_id"]}
    for name in expect["unchanged"]:
        assert after[name] == before[name], f"{name}이 바뀌었다"
