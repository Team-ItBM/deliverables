"""scenario_input (AC2): 방 생성 입력 검사와 문항 상태 분기.

케이스와 기대값은 tests/harness/server_cases.yaml에서 읽는다. 조작 절차는 §0-1 "입력·조작" 칸을 옮겼다.
"""

from datetime import datetime, timedelta

import pytest

from harness.server import scenario_outputs as so
from harness.server.api import assert_calls, assert_error, assert_status, default_profiles, default_trip

case = pytest.mark.server_case
NOTICE_FIXTURES = ("s2", "s5", "s4")


def _parse(moment):
    return datetime.fromisoformat(moment.replace("Z", "+00:00"))


def _room_count(srv):
    return srv.sql("SELECT count(*) AS n FROM rooms")[0]["n"]


@case("INP-P01")
def test_inp_p01_default_room(srv, expect):
    app = srv.app
    profiles = default_profiles()
    resp, room = app.create_room(profiles=profiles)
    assert_status(resp, expect["http_status"])
    body = resp.json()
    assert _parse(body["expires_at"]) - _parse(body["created_at"]) == timedelta(days=expect["expires_after_days"])
    assert_calls(app.replay, expect["calls"])
    # note: "모델 입력의 participant_profiles가 요청과 같다"
    assert app.replay.calls_for("scenarios")[0].model_input["participant_profiles"] == profiles
    assert app.room(room)["scenario_status"] == expect["scenario_status"]


@case("INP-P02")
def test_inp_p02_profiles_without_optional_fields(srv, expect):
    app = srv.app
    profiles = [{"profile_id": p["profile_id"], "display_name": p["display_name"]} for p in default_profiles()]
    resp, _ = app.create_room(profiles=profiles)
    assert_status(resp, expect["http_status"])
    # note: "모델 입력 프로필에 gender·age_band·mbti 키가 없다(null로 채우지 않는다)"
    sent = app.replay.calls_for("scenarios")[0].model_input["participant_profiles"]
    for profile in sent:
        assert not {"gender", "age_band", "mbti"} & set(profile), f"선택 정보 키가 채워졌다: {profile}"


@case("INP-P03")
def test_inp_p03_party_size_bounds(srv, expect):
    app = srv.app
    for size in (2, 8):
        resp, _ = app.create_room(profiles=default_profiles(party_size=size))
        assert_status(resp, expect["http_status"])


@case("INP-P04")
def test_inp_p04_scenario_status_routes(srv, expect):
    app = srv.app
    for name in NOTICE_FIXTURES:
        checkpoint = expect.at(name)
        resp, room = app.create_room(scenario=so.fixture_item(name))
        assert resp.status_code == 201, resp.text[:300]
        host_view = app.room(room, host=True)
        assert host_view["scenario_status"] == checkpoint["scenario_status"]
        # note: "방장 조회의 scenario_notice에 message가 있고, needs_information이면 clarification_questions도 있다"
        notice = host_view.get("scenario_notice")
        assert isinstance(notice, dict), f"{name}: 방장 조회에 scenario_notice가 없다"
        missing = set(checkpoint["scenario_notice_keys"]) - set(notice)
        assert not missing, f"{name}: scenario_notice에 {sorted(missing)}가 없다"
        # note: "방장 토큰이 없는 조회에는 scenario_notice가 없다"
        assert "scenario_notice" not in app.room(room), f"{name}: 참여자 조회에 scenario_notice가 있다"


@case("INP-N01")
def test_inp_n01_party_size_out_of_range(srv, expect):
    app = srv.app
    for size in (1, 9):
        resp, room = app.create_room(profiles=default_profiles(party_size=size), push_scenario=False)
        assert_error(resp, expect["http_status"], expect["error_code"])
        assert room is None
    assert _room_count(srv) == expect["rooms_created"]
    assert_calls(app.replay, expect["calls"])


@case("INP-N02")
def test_inp_n02_profile_count_mismatch(srv, expect):
    app = srv.app
    resp, _ = app.create_room(profiles=default_profiles(party_size=4), trip=default_trip(3), push_scenario=False)
    assert_error(resp, expect["http_status"], expect["error_code"])
    assert_calls(app.replay, expect["calls"])


@case("INP-N03")
def test_inp_n03_duplicate_profile_id(srv, expect):
    app = srv.app
    profiles = default_profiles()
    profiles[2]["profile_id"] = "p1"
    resp, _ = app.create_room(profiles=profiles, push_scenario=False)
    assert_error(resp, expect["http_status"], expect["error_code"])
    assert_calls(app.replay, expect["calls"])


@case("INP-N04")
def test_inp_n04_missing_display_name(srv, expect):
    app = srv.app
    empty = default_profiles()
    empty[1]["display_name"] = ""
    removed = default_profiles()
    del removed[1]["display_name"]
    for profiles in (empty, removed):
        resp, _ = app.create_room(profiles=profiles, push_scenario=False)
        assert_error(resp, expect["http_status"], expect["error_code"])
    assert_calls(app.replay, expect["calls"])


@case("INP-N05")
def test_inp_n05_missing_destination(srv, expect):
    app = srv.app
    trip = default_trip()
    del trip["destination"]
    resp, _ = app.create_room(trip=trip, push_scenario=False)
    assert_error(resp, expect["http_status"], expect["error_code"])
    assert_calls(app.replay, expect["calls"])


@case("INP-N06")
def test_inp_n06_vague_duration(srv, expect):
    app = srv.app
    trip = default_trip()
    trip["duration_days"] = "며칠 정도"
    resp, _ = app.create_room(trip=trip, push_scenario=False)
    assert_error(resp, expect["http_status"], expect["error_code"])
    assert_calls(app.replay, expect["calls"])


@case("INP-N07")
def test_inp_n07_session_before_ready(srv, expect):
    app = srv.app
    for name in NOTICE_FIXTURES:
        _, room = app.create_room(scenario=so.fixture_item(name))
        resp = app.session(room, "p1")
        assert_error(resp, expect["http_status"], expect["error_code"])
