"""response_privacy (AC3, 규칙 3): 원문·검증용 인용·선택 프로필 비공개.

공개 금지 키와 메모 표지는 harness.server.privacy.scan_private 하나로 검사한다.
"""

import json

import pytest

from travel.pact import validate_pact_output

from harness.server import pact_outputs as po
from harness.server.api import assert_error, assert_status, error_codes_of
from harness.server.privacy import scan_private

case = pytest.mark.server_case
SUBMISSION_WORDS = ("submission", "response")


def _session(app, room, host):
    return app.post(f"/api/rooms/{room.code}/sessions", {"profile_id": "p1"}, room.host if host else None)


def _visible_payloads(app, room, closed):
    """PRV-N01의 조회 범위. 기본 방에서 두 명이 제출한 뒤(마감 전) 새 세션을 방장 토큰 없이·붙여 만든다.
    세 번째 제출로 ready가 되면 방 조회, 결과, 결과 목록을 부르고, 마감 뒤 새 세션 요청의 오류 응답도 모은다.
    결과 목록은 방장 경로라 토큰을 붙인 호출만 200이다. closed는 마감 뒤 새 세션의 기대(checkpoint closed_session)다."""
    payloads = []
    app.replay.push("pact", po.pact_item())
    for profile in room.profiles[:2]:
        assert app.submit_new(room, profile["profile_id"]).resp.status_code == 201
    for host in (False, True):
        label = "방장" if host else "참여자"
        session = _session(app, room, host)
        assert session.status_code == 201, session.text[:300]
        payloads.append((f"{label} 새 세션(마감 전)", session.json(), False))
    assert app.submit_new(room, room.profiles[2]["profile_id"]).resp.status_code == 201
    app.join()
    for host in (False, True):
        label = "방장" if host else "참여자"
        payloads.append((f"{label} 방 조회", app.room(room, host=host), False))
        result = app.result(room, host=host)
        assert result.status_code == 200, result.text[:300]
        payloads.append((f"{label} 결과", result.json(), True))
    results = app.results(room)
    assert results.status_code == 200, results.text[:300]
    payloads.append(("방장 결과 목록", results.json(), True))
    for host in (False, True):
        label = "방장" if host else "참여자"
        # note: "마감 뒤 새 세션은 409 room_closed이고 그 오류 응답도 같은 검사를 한다"
        late = _session(app, room, host)
        assert_error(late, closed["http_status"], closed["error_code"])
        payloads.append((f"{label} 새 세션(마감 뒤)", late.json(), False))
    return payloads


def _ready_and_scan(srv, targets, closed):
    app = srv.app
    _, room = app.create_room()
    payloads = _visible_payloads(app, room, closed)
    srv.collect_original_conditions()
    assert srv.ctx.memos and srv.ctx.original_conditions, "메모 표지와 original_condition이 준비되지 않았다"
    problems = []
    for where, payload, is_result in payloads:
        problems += scan_private(payload, targets, srv.ctx, where, result_payload=is_result)
    return room, problems


@case("PRV-P01")
def test_prv_p01_privacy_notice(srv, expect):
    app = srv.app
    _, room = app.create_room()
    resp = app.session(room, "p1")
    assert resp.status_code == 201, resp.text[:300]
    assert resp.json()["privacy_notice"] == expect["privacy_notice"]


@case("PRV-N01")
def test_prv_n01_no_private_fields_in_any_get(srv, expect):
    # note: "응답 JSON 어디에도 §0-A 6의 공개 금지 키가 없다 ... 방장 응답도 같다"는 privacy_scan으로 검사한다
    _, problems = _ready_and_scan(srv, expect["privacy_scan"], expect.at("closed_session"))
    assert not problems, "\n".join(problems)


@case("PRV-N02")
def test_prv_n02_no_submission_read_route(srv, expect):
    app = srv.app
    # note: "제출·응답을 돌려주는 GET 경로가 없고"
    offending = []
    for route in app.app.routes:
        methods = getattr(route, "methods", None) or set()
        path = getattr(route, "path", "")
        if "GET" in methods and any(word in path for word in SUBMISSION_WORDS):
            offending.append(path)
    assert not offending, f"제출·응답 GET 경로가 있다: {offending}"
    _, room = app.create_room()
    submitted = app.submit_new(room, "p1")
    assert submitted.resp.status_code == 201, submitted.resp.text[:300]
    participant_id = submitted.body["participant_id"]
    resp = app.get(f"/api/rooms/{room.code}/submissions/{participant_id}")
    assert_status(resp, expect["http_status"])


@case("PRV-N03")
def test_prv_n03_memo_quote_output_never_used(srv, expect):
    app = srv.app
    _, room = app.create_room()
    app.replay.push("pact", po.pact_item("memo_quote"), po.pact_item("memo_quote"))
    for profile in room.profiles:
        assert app.submit_new(room, profile["profile_id"]).resp.status_code == 201
    app.join()
    calls = app.replay.calls_for("pact")
    # note: "두 번 모두 검증기 memo_quote": 두 출력 모두 검증기가 memo_quote로 거부하는지 확인하고,
    # 두 번째 호출의 repair_errors로 서버가 첫 출력의 검증 결과를 넘겼는지 본다
    for call in calls:
        codes = {e["code"] for e in validate_pact_output(call.model_input, call.raw_output)["errors"]}
        assert "memo_quote" in codes, f"재생 출력이 memo_quote로 거부되지 않는다: {codes}"
    assert len(calls) >= 2, f"추천 호출 {len(calls)}회"
    missing = set(expect["repair_error_codes"]) - error_codes_of(calls[1].repair_errors)
    assert not missing, f"두 번째 호출 repair_errors에 {sorted(missing)}가 없다"
    view = app.room(room)
    assert view["room_status"] == expect["room_status"]
    assert view["failure_reason"] == expect["failure_reason"]
    resp = app.result(room)
    assert_error(resp, expect["http_status"], expect["error_code"])
    # note: "그 문장은 어떤 응답에도 없다"
    quotes = {po.memo_quote_text(c.model_input) for c in calls}
    payloads = [resp.text, json.dumps(view, ensure_ascii=False), json.dumps(app.room(room, host=True), ensure_ascii=False),
                app.results(room).text]
    for quote in quotes:
        assert not any(quote in p for p in payloads), "거부된 출력의 메모 인용 문장이 응답에 있다"


@case("PRV-N04")
def test_prv_n04_logs_and_llm_calls_masked(srv, expect, capfd):
    # 검사 범위: PRV-N01 흐름 동안의 표준 출력·표준 오류와 llm_calls 표의 모든 행
    capfd.readouterr()
    _ready_and_scan(srv, ["forbidden_keys"], expect.at("closed_session"))
    captured = capfd.readouterr()
    rows = srv.sql("SELECT * FROM llm_calls")
    problems = scan_private(captured.out, expect["privacy_scan"], srv.ctx, "표준 출력")
    problems += scan_private(captured.err, expect["privacy_scan"], srv.ctx, "표준 오류")
    problems += scan_private(json.dumps(rows, ensure_ascii=False, default=str), expect["privacy_scan"], srv.ctx,
                             "llm_calls")
    assert not problems, "\n".join(problems)
