"""방·결과 응답의 공개 여행 정보(SPEC 처리 정책 "응답·결과 공개", 서버 위임 기록 결정 47).

2026-11-05 사람 승인. 서버 계약 하니스(conftest의 srv fixture)를 그대로 쓰고 기존 케이스 기대값은 바꾸지 않는다.
공개하는 값은 목적지, 기간, 인원 세 개뿐이다. 동행 관계와 선택 프로필은 넣지 않는다.
TEST_DATABASE_URL이 없으면 srv fixture가 skip한다.
"""

from harness.server import pact_outputs as po
from harness.server.api import SHARED_RESULT_KEYS, default_trip

PUBLIC_TRIP_KEYS = {"destination", "duration_days", "party_size"}


def _expected():
    trip = default_trip(3)
    return {key: trip[key] for key in PUBLIC_TRIP_KEYS}


def _ready_room(app):
    _, room = app.create_room()
    app.replay.push("pact", po.pact_item())
    for profile in room.profiles:
        assert app.submit_new(room, profile["profile_id"]).resp.status_code == 201
    app.join()
    return room


def test_room_view_has_public_trip_for_everyone(srv):
    app = srv.open_app()
    _, room = app.create_room()
    assert app.room(room)["trip"] == _expected()
    assert app.room(room, host=True)["trip"] == _expected()


def test_every_result_payload_has_same_public_trip(srv):
    app = srv.open_app()
    room = _ready_room(app)
    shown = app.result(room).json()
    assert shown["trip"] == _expected()
    assert set(shown) <= SHARED_RESULT_KEYS
    assert app.result(room, host=True).json()["trip"] == _expected()
    entry = app.results_body(room)["results"][0]
    assert entry["trip"] == _expected()


def test_host_edit_keeps_trip_and_cannot_edit_it(srv):
    app = srv.open_app()
    room = _ready_room(app)
    entry = app.results_body(room)["results"][0]
    assert not [item for item in entry["editable"] if item["path"].startswith("/trip")]
    refused = app.edit(room, entry["result_id"], [{"path": "/trip/destination", "text": "다른 곳"}])
    assert refused.status_code == 422, refused.text[:300]
    assert app.result(room).json()["trip"] == _expected()
