"""방당 비용 상한(ARCHITECTURE 5절 "방당 $0.20과 전체 예산 한도를 검사해 초과 시 실행 오류로 중단", config/llm.yaml room_cap_usd).

2026-11-05 사람 승인. 서버 계약 하니스(conftest의 srv fixture)를 그대로 쓰고 기존 케이스·기대값은 바꾸지 않는다.
다음 모델 호출 전에 그 방의 llm_calls 비용 합이 상한에 닿았으면 호출하지 않고 failed(call_error)로 끝낸다.
TEST_DATABASE_URL이 없으면 srv fixture가 skip한다.
"""

import pytest

from harness.server import pact_outputs as po
from harness.server.api import assert_calls, default_profiles


def _room_id(srv, room_code):
    return srv.sql("SELECT room_id FROM rooms WHERE room_code = %s", (room_code,))[0]["room_id"]


def _seed_cost(srv, room_code, cost):
    """상한 검사용 비용 행. 실제 호출 기록과 같은 표에 넣는다."""
    from harness.server import db as testdb

    testdb.execute(srv.database_url,
                   "INSERT INTO llm_calls (room_id, stage, cost_usd, created_at) VALUES (%s, 'scenarios', %s, now())",
                   (_room_id(srv, room_code), cost))


def test_room_cap_blocks_next_call(srv):
    app = srv.open_app(room_cap_usd=0.20)
    _, room = app.create_room(profiles=default_profiles(party_size=2))
    _seed_cost(srv, room.code, 0.20)  # 상한에 닿은 상태. 추천 재생 항목은 넣지 않는다(호출이 없어야 한다)
    for profile in room.profiles:
        assert app.submit_new(room, profile["profile_id"]).resp.status_code == 201
    app.join()
    view = app.room(room)
    assert view["room_status"] == "failed" and view["failure_reason"] == "call_error"
    assert_calls(app.replay, {"pact": 0})
    rows = srv.sql("SELECT error_kind FROM llm_calls WHERE room_id = %s AND stage = 'pact'", (_room_id(srv, room.code),))
    assert [r["error_kind"] for r in rows] == ["budget_exceeded"], "상한 도달이 llm_calls에 budget_exceeded로 남아야 한다"
    assert app.result(room).status_code == 409


def test_room_cap_allows_call_below_cap(srv):
    app = srv.open_app(room_cap_usd=0.20)
    _, room = app.create_room(profiles=default_profiles(party_size=2))
    _seed_cost(srv, room.code, 0.19)
    app.replay.push("pact", po.pact_item())
    for profile in room.profiles:
        assert app.submit_new(room, profile["profile_id"]).resp.status_code == 201
    app.join()
    assert app.room(room)["room_status"] == "ready"
    assert_calls(app.replay, {"pact": 1})


def test_room_cap_not_set_means_no_limit(srv):
    app = srv.open_app()
    _, room = app.create_room(profiles=default_profiles(party_size=2))
    _seed_cost(srv, room.code, 5.0)
    app.replay.push("pact", po.pact_item())
    for profile in room.profiles:
        assert app.submit_new(room, profile["profile_id"]).resp.status_code == 201
    app.join()
    assert app.room(room)["room_status"] == "ready"


def test_retry_after_cap_fails_again_without_calling(srv):
    app = srv.open_app(room_cap_usd=0.20)
    _, room = app.create_room(profiles=default_profiles(party_size=2))
    _seed_cost(srv, room.code, 0.25)
    for profile in room.profiles:
        assert app.submit_new(room, profile["profile_id"]).resp.status_code == 201
    app.join()
    assert app.room(room)["room_status"] == "failed"
    resp = app.retry(room)
    assert resp.status_code == 202, "실패 상태라 재시도 요청 자체는 받는다"
    app.join()
    assert app.room(room)["failure_reason"] == "call_error"
    assert_calls(app.replay, {"pact": 0})


@pytest.mark.parametrize("cap", [0, -1])
def test_invalid_cap_rejected(srv, cap):
    with pytest.raises(ValueError):
        srv.settings(room_cap_usd=cap)
