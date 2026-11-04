"""regeneration (AC17): 같은 고정 입력으로 정상 결과를 한 번 더 만들고 둘 중 하나를 고른다.

정상·실패 결과 수는 방장 결과 목록의 state로 센다. 재생성 실패는 timeout 3회(최초 + 재시도 2회)로 만든다.
재생성 결과는 방장이 고르기 전까지 참여자 결과 조회에 나오지 않는다(결정 28·32, REG-P04).
REG-N04는 response_closure의 동시성 케이스처럼 같은 DB와 같은 재생 클라이언트로 앱 두 개를 연다.
"""

import json
import uuid

import pytest

from harness.server import pact_outputs as po
from harness.server.api import assert_calls, assert_error, assert_status, run_concurrently
from harness.server.replay import CallError

case = pytest.mark.server_case
CONCURRENT_REPEAT = 10  # REG-N04 반복 횟수. [에이전트 안]
OLD_PHRASE = "비슷한 상황이 오면"
NEW_PHRASE = "같은 상황이 다시 오면"


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


@case("REG-P04")
def test_reg_p04_regenerated_hidden_until_selected(srv, expect):
    app = srv.app
    room, _ = app.ready_room()
    initial = app.result(room).json()
    assert _regenerate(app, room).status_code == 202
    regenerated = next(r["result_id"] for r in _results(app, room)
                       if r["state"] == "normal" and r["result_id"] != initial["result_id"])
    shown_ids = {"initial": initial["result_id"]}

    def participant_view():
        resp = app.result(room)
        assert resp.status_code == 200, resp.text[:300]
        return resp

    checkpoint = expect.at("after_regeneration")
    assert _count(app, room, "normal") == checkpoint["normal_results"]
    resp = participant_view()
    assert resp.json()["result_id"] == shown_ids[checkpoint["shared_result"]], "재생성 뒤 참여자 결과가 바뀌었다"
    assert resp.json()["draft"] is checkpoint["draft"]
    # note: "재생성 결과의 result_id가 없다"
    assert regenerated not in resp.text, "참여자 결과에 재생성 결과의 result_id가 있다"

    text = app.edited_text(room, regenerated, "/clauses/0/action", OLD_PHRASE, NEW_PHRASE)
    edit = app.edit(room, regenerated, [{"path": "/clauses/0/action", "text": text}])
    assert edit.status_code == 201, edit.text[:300]
    checkpoint = expect.at("after_edit")
    resp = participant_view()
    assert resp.json()["result_id"] == shown_ids[checkpoint["shared_result"]], "고르지 않은 재생성 결과의 수정본이 공개됐다"
    assert edit.json()["result_id"] not in resp.text and regenerated not in resp.text

    assert app.select(room, regenerated).status_code == 200
    shown_ids["latest_edit"] = edit.json()["result_id"]
    checkpoint = expect.at("after_select")
    body = participant_view().json()
    assert body["result_id"] == shown_ids[checkpoint["shared_result"]], "고른 재생성 결과의 가장 최근 수정본이 보이지 않는다"
    assert body["draft"] is checkpoint["draft"]


@case("REG-N04")
def test_reg_n04_concurrent_retry_and_regenerate(srv, expect):
    first, second = srv.app, srv.open_app()
    for round_no in range(CONCURRENT_REPEAT):
        room, _ = first.ready_room()
        _failed_regeneration(first, room)
        # 준비: 정상 결과 1개, failed. retry(실패한 재생성)와 regenerate(정상 결과 1개) 둘 다 받아들일 수 있는 상태다
        assert first.room(room)["room_status"] == "failed", f"{round_no}회: 준비 상태가 failed가 아니다"
        assert _count(first, room, "normal") == 1
        before = srv.replay.counts()
        srv.replay.push("pact", po.pact_item())
        retrier, regenerator = (first, second) if round_no % 2 == 0 else (second, first)
        responses = run_concurrently(lambda: retrier.retry(room), lambda: regenerator.regenerate(room))
        first.join()
        second.join()
        assert sorted(r.status_code for r in responses) == expect["concurrent_statuses"], \
            f"{round_no}회: {[r.status_code for r in responses]}"
        loser = max(responses, key=lambda r: r.status_code)
        assert_error(loser, loser.status_code, expect["error_code"])
        assert_calls(srv.replay, expect["calls_added"], before=before)
        assert _count(first, room, "normal") == expect["normal_results"], f"{round_no}회: 정상 결과 수"


@case("REG-P05")
def test_reg_p05_failed_regeneration_keeps_shared_result(srv, expect):
    app = srv.app
    room, _ = app.ready_room()
    initial = app.result(room).json()["result_id"]
    _failed_regeneration(app, room)
    checkpoint = expect.at("after_failed_regeneration")
    assert app.room(room)["room_status"] == checkpoint["room_status"]
    assert _count(app, room, "failed") == checkpoint["failed_results"]
    shown_ids = {"initial": initial}
    # note: "결과 조회는 200이고 최초 결과(draft: true) 그대로다"
    for host in (False, True):
        resp = app.result(room, host=host)
        assert resp.status_code == 200, f"재생성 실패 뒤 결과 조회 HTTP {resp.status_code}: {resp.text[:300]}"
        body = resp.json()
        assert body["result_id"] == shown_ids[checkpoint["shared_result"]], "재생성 실패 뒤 공개 결과가 바뀌었다"
        assert body["draft"] is checkpoint["draft"]
