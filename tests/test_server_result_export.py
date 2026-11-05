"""result_export (AC13): 공유 결과의 참여자 토큰 치환, 제외 안내, 수정 표시, 유머 문구 조건.

함수 단위 케이스는 travel.server.render.render_participant_tokens(text, roster)를 직접 부른다.
roster는 제출 순서대로 놓은 [{participant_id, display_name}]이다.
"""

import json

import pytest

from harness.server import pact_outputs as po
from harness.server import db as testdb
from harness.server.api import assert_error, template_groups
from harness.server.privacy import scan_private

case = pytest.mark.server_case
NAMES = ("민준", "지수", "하늘", "Alex", "7")
PAIRS = ("은/는", "이/가", "을/를", "과/와", "으로/로")
STATUS_VARIANTS = ("unresolved", "proposed", "conditional_only", "needs_information")


def _render(srv, text, roster):
    return srv.server.render.render_participant_tokens(text, roster)


def _early_result(app, room, *pact_items):
    assert app.submit_new(room, "p1").resp.status_code == 201
    app.replay.push("pact", *pact_items)
    assert app.generate(room).status_code == 202
    app.join()


def _sentences(result):
    texts = []
    for kind in ("clauses", "conditional_alternatives"):
        for item in result.get(kind) or []:
            texts.append(item["action"])
            texts.extend(item.get("proposed_conditions") or [])
            texts.extend(item.get("proposed_changes") or [])
    texts.extend(u["description"] for u in result.get("unresolved_conditions") or [])
    if result.get("message"):
        texts.append(result["message"])
    return texts


@case("EXP-P01")
def test_exp_p01_particles_by_name(srv, expect):
    rendered = expect["rendered"]
    assert set(rendered) == set(NAMES), "YAML의 이름과 테스트 입력 이름이 다르다"
    for name in NAMES:
        roster = [{"participant_id": "A", "display_name": name}]
        actual = [_render(srv, "{{participant:A}}" + pair, roster) for pair in PAIRS]
        assert actual == rendered[name], f"{name}: {actual}"


@case("EXP-P02")
def test_exp_p02_same_name_numbered_by_submission(srv, expect):
    app = srv.app
    _, room = app.create_room()
    order = [app.submit_new(room, "p1") for _ in range(2)]
    for s in order:
        assert s.resp.status_code == 201, s.resp.text[:300]
    app.replay.push("pact", po.pact_item())
    assert app.generate(room).status_code == 202
    app.join()
    template = srv.pact_outputs()[0]["clauses"][0]["action"]
    shown = app.result(room).json()["clauses"][0]["action"]
    groups = template_groups(template, shown, "participant")
    assert groups is not None, f"토큰 밖 문자열이 원문과 다르다: {shown!r}"
    by_id = {tid: text for tid, _, text in groups}
    actual = [by_id[s.body["participant_id"]] for s in order]
    assert actual == expect["rendered_by_submission"], actual


@case("EXP-P03")
def test_exp_p03_token_in_display_name_is_literal(srv, expect):
    app = srv.app
    room, _ = app.ready_room(names={"p3": "{{participant:B}}"})
    joined = "\n".join(_sentences(app.result(room).json()))
    for value in expect["text_includes"]:
        assert value in joined, f"공유 결과 문장에 {value!r}가 글자 그대로 없다"


@case("EXP-P04")
def test_exp_p04_shared_result_after_edit(srv, expect):
    app = srv.app
    _, room = app.create_room()
    _early_result(app, room, po.pact_item())
    original = app.result(room).json()
    # 방장이 고르기 전의 수정본이다(결정 31). 편집 문장은 editable만으로 만든다(결정 29).
    text = app.edited_text(room, original["result_id"], "/clauses/0/action", "비슷한 상황이 오면", "같은 상황이 다시 오면")
    edit = app.edit(room, original["result_id"], [{"path": "/clauses/0/action", "text": text}])
    assert edit.status_code == 201, edit.text[:300]
    participant = app.result(room).json()
    host = app.result(room, host=True).json()
    # note: "참여자 응답과 방장 응답의 공유 결과가 같다"
    assert participant == host == edit.json()
    # note: "included_count, excluded_names, proposed_changes, label: 방장 수정이 있다"
    assert "included_count" in participant and "excluded_names" in participant
    assert participant["excluded_names"], "조기 생성인데 excluded_names가 비어 있다"
    assert participant["conditional_alternatives"][0]["proposed_changes"], "proposed_changes가 없다"
    assert participant["label"] == expect["result_label"]
    assert participant["draft"] is expect["draft"]
    srv.collect_original_conditions()
    problems = []
    for where, payload in (("참여자 결과", participant), ("방장 결과", host), ("수정 응답", edit.json())):
        problems += scan_private(payload, expect["privacy_scan"], srv.ctx, where, result_payload=True)
    assert not problems, "\n".join(problems)


@case("EXP-P05")
def test_exp_p05_humor_only_for_unresolved(srv, expect):
    app = srv.app
    for status in STATUS_VARIANTS:
        checkpoint = expect.at(status)
        _, room = app.create_room()
        _early_result(app, room, po.pact_item(status))
        result = app.result(room)
        assert result.status_code == 200, f"{status}: {result.text[:300]}"
        body = result.json()
        assert body["pact_status"] == status
        assert ("humor" in body) is checkpoint["has_humor"], f"{status}: humor 유무"
        if checkpoint["has_humor"]:
            assert body["humor"]["text"] == checkpoint["humor_text"]
            assert body["humor"]["explanation"] == checkpoint["humor_explanation"]
            # note: "unresolved_conditions가 함께 있다"
            assert body["unresolved_conditions"], "unresolved인데 unresolved_conditions가 없다"
    failed = expect.at("failed")
    _, room = app.create_room()
    _early_result(app, room, po.pact_item("extra_key"), po.pact_item("extra_key"))
    assert app.room(room)["room_status"] == "failed"
    payloads = [app.result(room).json(), app.results_body(room)]
    for payload in payloads:
        assert ("humor" in json.dumps(payload, ensure_ascii=False)) is failed["has_humor"], "failed 결과에 humor가 있다"


@case("EXP-N01")
def test_exp_n01_unknown_participant_token(srv, expect):
    roster = [{"participant_id": "A", "display_name": "민준"}]
    with pytest.raises(srv.server.render.RenderError) as info:
        _render(srv, "{{participant:Z}}은/는 먼저 쉬고 싶어요", roster)
    assert info.value.code == expect["error_code"]


@case("EXP-N02")
def test_exp_n02_leftover_tokens(srv, expect):
    roster = [{"participant_id": "A", "display_name": "민준"}]
    for text in ("{{participant:A}은/는 먼저 쉬고 싶어요", "{{profile:p1}}은/는 먼저 쉬고 싶어요"):
        with pytest.raises(srv.server.render.RenderError) as info:
            _render(srv, text, roster)
        assert info.value.code == expect["error_code"], text


@case("EXP-N03")
def test_exp_n03_stored_unknown_token_blocks_result(srv, expect):
    app = srv.app
    room, _ = app.ready_room()
    shown = app.result(room).json()
    rows = srv.sql("SELECT output FROM results WHERE result_id::text = %s", (str(shown["result_id"]),))
    assert len(rows) == 1
    stored = rows[0]["output"]
    output = json.loads(stored) if isinstance(stored, str) else stored
    output["clauses"][0]["action"] += " " + po.token("participant-not-in-room") + "은/는 함께해요."
    if isinstance(stored, str):
        value = json.dumps(output, ensure_ascii=False)
    else:
        from psycopg.types.json import Jsonb

        value = Jsonb(output)
    testdb.execute(srv.database_url, "UPDATE results SET output = %s WHERE result_id::text = %s",
                   (value, str(shown["result_id"])))
    resp = app.result(room)
    assert_error(resp, expect["http_status"], expect["error_code"])
    # note: "응답에 일부 문장도 없다"
    assert set(resp.json()) == {"error"}
    for text in _sentences(shown):
        assert text not in resp.text, "render_failed 응답에 결과 문장이 있다"


@case("EXP-P06")
def test_exp_p06_draft_until_host_selects(srv, expect):
    app = srv.app
    room, _ = app.ready_room()
    initial = app.result(room).json()["result_id"]
    for at in ("before_select", "after_select"):
        if at == "after_select":
            assert app.select(room, initial).status_code == 200
        checkpoint = expect.at(at)
        for host in (False, True):
            resp = app.result(room, host=host)
            assert resp.status_code == 200, resp.text[:300]
            body = resp.json()
            assert body["result_id"] == initial, f"{at}: 최초 정상 결과가 아니다"
            assert body["draft"] is checkpoint["draft"], f"{at}: draft {body.get('draft')!r} (방장 토큰 {host})"
