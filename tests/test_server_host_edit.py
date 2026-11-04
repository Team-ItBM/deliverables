"""host_edit (AC12, 규칙 2): 방장 권한으로 조항 문구만 고치고, 원본과 구분된 새 행으로 저장한다.

준비는 기본 추천 재생으로 ready인 방이다. 방장이 보내는 문장은 토큰을 유지한 원문이어야 하므로(§0-B 11),
재생 기록의 AI 원본 출력에서 해당 문장을 꺼내 일부 문구만 바꾼다.
"""

import uuid

import pytest

from harness.server import pact_outputs as po
from harness.server.api import SHARED_RESULT_KEYS, VERDICT_KEYS, assert_error, assert_status

case = pytest.mark.server_case
OLD_PHRASE = "비슷한 상황이 오면"
NEW_PHRASE = "같은 상황이 다시 오면"


def _prepared(srv):
    app = srv.app
    room, _ = app.ready_room()
    original = app.result(room)
    assert original.status_code == 200, original.text[:300]
    output = srv.pact_outputs()[0]
    return app, room, original.json(), output


def _edited(text):
    assert OLD_PHRASE in text
    return text.replace(OLD_PHRASE, NEW_PHRASE, 1)


def _row(srv, result_id):
    rows = srv.sql("SELECT * FROM results WHERE result_id::text = %s", (str(result_id),))
    assert len(rows) == 1, f"results 행 {result_id}가 {len(rows)}개"
    return rows[0]


def _row_count(srv):
    return srv.sql("SELECT count(*) AS n FROM results")[0]["n"]


def _list_entry(app, room, result_id):
    for entry in app.results_body(room)["results"]:
        if entry["result_id"] == result_id:
            return entry
    raise AssertionError(f"결과 목록에 {result_id}가 없다")


@case("EDT-P01")
def test_edt_p01_edit_creates_new_row(srv, expect):
    app, room, original, output = _prepared(srv)
    before = {"entry": _list_entry(app, room, original["result_id"]), "row": _row(srv, original["result_id"])}
    resp = app.edit(room, original["result_id"],
                    [{"path": "/clauses/0/action", "text": _edited(output["clauses"][0]["action"])}])
    assert_status(resp, expect["http_status"])
    edited = resp.json()
    assert edited["result_id"] != original["result_id"], "새 result_id가 아니다"
    assert edited["kind"] == expect["result_kind"]
    sources = {"ai_original": original["result_id"]}
    assert edited["source_result_id"] == sources[expect["source_result"]]
    for name in expect["unchanged"]:
        assert name == "original_result", f"모르는 unchanged 이름 {name}"
        assert _list_entry(app, room, original["result_id"]) == before["entry"], "원본의 방장 조회 응답이 바뀌었다"
        assert _row(srv, original["result_id"]) == before["row"], "원본 results 행이 바뀌었다"


@case("EDT-P02")
def test_edt_p02_edited_result_label_and_fields(srv, expect):
    app, room, original, output = _prepared(srv)
    resp = app.edit(room, original["result_id"],
                    [{"path": "/clauses/0/action", "text": _edited(output["clauses"][0]["action"])}])
    assert resp.status_code == 201, resp.text[:300]
    for host in (False, True):
        shown = app.result(room, host=host)
        assert shown.status_code == 200, shown.text[:300]
        body = shown.json()
        assert body["result_id"] == resp.json()["result_id"], "수정본이 조회되지 않는다"
        assert body["label"] == expect["result_label"]
        # note: "검증 결과 필드와 합의·수락 필드가 없다. pact_status는 원본과 같다"
        assert set(body) <= SHARED_RESULT_KEYS, f"§0-C 밖의 키 {sorted(set(body) - SHARED_RESULT_KEYS)}"
        assert not VERDICT_KEYS & set(body)
        assert body["pact_status"] == original["pact_status"]


@case("EDT-P03")
def test_edt_p03_second_edit_starts_from_latest(srv, expect):
    app, room, original, output = _prepared(srv)
    first = app.edit(room, original["result_id"],
                     [{"path": "/clauses/0/action", "text": _edited(output["clauses"][0]["action"])}])
    assert first.status_code == 201, first.text[:300]
    first_body = first.json()
    before = {"original_result": _row(srv, original["result_id"]), "previous_edit": _row(srv, first_body["result_id"])}
    resp = app.edit(room, original["result_id"],
                    [{"path": "/clauses/1/action", "text": _edited(output["clauses"][1]["action"])}])
    assert_status(resp, expect["http_status"])
    second = resp.json()
    sources = {"ai_original": original["result_id"], "latest_edit": first_body["result_id"]}
    assert second["source_result_id"] == sources[expect["source_result"]]
    # note: "새 수정본에 EDT-P01의 /clauses/0/action 변경이 남아 있다"
    assert second["clauses"][0]["action"] == first_body["clauses"][0]["action"]
    assert second["clauses"][1]["action"] != first_body["clauses"][1]["action"]
    after = {"original_result": _row(srv, original["result_id"]), "previous_edit": _row(srv, first_body["result_id"])}
    for name in expect["unchanged"]:
        assert after[name] == before[name], f"{name} 행이 바뀌었다"
    shown = {"latest_edit": second["result_id"]}
    assert app.result(room).json()["result_id"] == shown[expect["shared_result"]]


@case("EDT-N01")
def test_edt_n01_host_routes_need_token(srv, expect):
    app, room, original, output = _prepared(srv)
    session = app.session(room, "p1").json()
    no_token = {}

    def snapshot():
        return {"room_status": app.room(room)["room_status"], "results": app.results_body(room),
                "calls": app.replay.counts()}

    before = snapshot()
    attempts = {
        "generate": lambda: app.generate(room, headers=no_token),
        "retry": lambda: app.retry(room, headers=no_token),
        "regenerate": lambda: app.regenerate(room, headers=no_token),
        "results": lambda: app.results(room, headers=no_token),
        "select": lambda: app.select(room, original["result_id"], headers=no_token),
        "edits": lambda: app.edit(room, original["result_id"],
                                  [{"path": "/clauses/0/action", "text": _edited(output["clauses"][0]["action"])}],
                                  headers=no_token),
        "host subscription": lambda: app.subscribe(room, "host", session_id=session["session_id"], headers=no_token),
    }
    for name, call in attempts.items():
        resp = call()
        assert resp.status_code == expect["http_status"], f"{name}: HTTP {resp.status_code}"
        assert_error(resp, expect["http_status"], expect["error_code"])
    app.join()
    after = snapshot()
    for name in expect["unchanged"]:
        assert after[name] == before[name], f"{name}이 바뀌었다"


@case("EDT-N02")
def test_edt_n02_other_room_token(srv, expect):
    app, room, original, output = _prepared(srv)
    _, other = app.create_room()
    resp = app.edit(room, original["result_id"],
                    [{"path": "/clauses/0/action", "text": _edited(output["clauses"][0]["action"])}], headers=other.host)
    assert_error(resp, expect["http_status"], expect["error_code"])


@case("EDT-N03")
def test_edt_n03_add_clause_rejected(srv, expect):
    app, room, original, output = _prepared(srv)
    rows = _row_count(srv)
    resp = app.edit(room, original["result_id"], [{"path": "/clauses/2/action", "text": _edited(output["clauses"][0]["action"])}])
    assert_error(resp, expect["http_status"], expect["error_code"])
    assert _row_count(srv) - rows == expect["new_result_rows"]


@case("EDT-N04")
def test_edt_n04_delete_clause_text_rejected(srv, expect):
    app, room, original, _ = _prepared(srv)
    resp = app.edit(room, original["result_id"], [{"path": "/clauses/1/action", "text": ""}])
    assert_error(resp, expect["http_status"], expect["error_code"])


@case("EDT-N05")
def test_edt_n05_non_text_paths_rejected(srv, expect):
    app, room, original, _ = _prepared(srv)
    paths = ("/clauses/0/participant_names", "/clauses/0/scenario_id", "/positions/0",
             "/conditional_alternatives/0/required_changes/0/original_condition")
    for path in paths:
        resp = app.edit(room, original["result_id"], [{"path": path, "text": "방장이 바꾼 문장이에요"}])
        assert resp.status_code == expect["http_status"], f"{path}: HTTP {resp.status_code}"
        assert_error(resp, expect["http_status"], expect["error_code"])


@case("EDT-N06")
def test_edt_n06_token_change_rejected(srv, expect):
    app, room, original, output = _prepared(srv)
    action = _edited(output["clauses"][0]["action"])
    target = output["clauses"][0]["participant_ids"][1]
    removed = action.replace(po.token(target), "")
    added = action + f" {po.token('participant-not-in-room')}은/는 함께해요."
    for text in (removed, added):
        resp = app.edit(room, original["result_id"], [{"path": "/clauses/0/action", "text": text}])
        assert_error(resp, expect["http_status"], expect["error_code"])


@case("EDT-N07")
def test_edt_n07_memo_quote_in_edit(srv, expect):
    app, room, original, output = _prepared(srv)
    rows = _row_count(srv)
    quote = srv.ctx.memos[0][:po.QUOTE_LENGTH]
    text = _edited(output["clauses"][0]["action"]) + " " + quote
    resp = app.edit(room, original["result_id"], [{"path": "/clauses/0/action", "text": text}])
    assert_error(resp, expect["http_status"], expect["error_code"])
    assert _row_count(srv) - rows == expect["new_result_rows"]


@case("EDT-N08")
def test_edt_n08_unknown_result(srv, expect):
    app, room, _, output = _prepared(srv)
    resp = app.edit(room, str(uuid.uuid4()), [{"path": "/clauses/0/action", "text": _edited(output["clauses"][0]["action"])}])
    assert_error(resp, expect["http_status"], expect["error_code"])
