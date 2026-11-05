"""profile_rendering (AC15): 문항의 {{profile:ID}} 토큰을 뷰마다 '당신'과 등록 이름으로 바꾼다.

문항 재생은 scenario_outputs.token_output()이다(§0-1 profile_rendering 준비). 원문 토큰 문장과 치환된 문장을
template_groups로 대조해 토큰 밖 문자열이 같은지, 토큰 자리에 무엇이 들어갔는지 본다.
PRF-P02는 한 방에서 토큰마다 조사가 하나뿐이라, 같은 출력으로 이름을 돌려 가며 방 3개를 만든다(2026-11-05 사람 결정).
"""

import pytest

from harness.server import scenario_outputs as so
from harness.server.api import default_profiles, template_groups
from harness.server.privacy import scan_private

case = pytest.mark.server_case
TEMPLATE = so.token_output()
TEMPLATE_BY_ID = {s["template_id"]: s for s in TEMPLATE["scenarios"]}
PAIRS = {"이/가": ("이", "가"), "은/는": ("은", "는"), "과/와": ("과", "와")}
ROTATIONS = (
    {"p1": "민준", "p2": "지수", "p3": "하늘"},
    {"p1": "지수", "p2": "하늘", "p3": "민준"},
    {"p1": "하늘", "p2": "민준", "p3": "지수"},
)
OTHER_NAMES = {"p1": "서연", "p2": "도윤", "p3": "하람"}


def _token_room(app, names=None, profiles=None):
    resp, room = app.create_room(profiles=profiles or default_profiles(names), scenario=so.scenario_item(TEMPLATE))
    assert resp.status_code == 201, resp.text[:300]
    return room


def _views(app, room, profile_ids=("p1", "p2", "p3")):
    views = {}
    for pid in profile_ids:
        resp = app.session(room, pid)
        assert resp.status_code == 201, resp.text[:300]
        views[pid] = resp.json()
    return views


def _texts(scenario):
    yield "scene", scenario["scene"]
    yield "question", scenario["question"]
    for i, option in enumerate(scenario["options"]):
        yield f"options/{i}/label", option["label"]


def _groups(view):
    """뷰의 문장마다 원문 템플릿과 대조한 결과. 토큰 밖 문자열이 다르면 None이 들어간다."""
    result = {}
    for scenario in view["scenarios"]:
        template = TEMPLATE_BY_ID[scenario["scenario_id"]]
        for (where, text), (_, original) in zip(_texts(scenario), _texts(template)):
            result[(scenario["scenario_id"], where)] = template_groups(original, text, "profile")
    return result


def _structure(view):
    return [(s["scenario_id"], [o["option_id"] for o in s["options"]]) for s in view["scenarios"]]


def _all_text(view):
    return "\n".join(text for s in view["scenarios"] for _, text in _texts(s))


def _assert_same_outside_tokens(views):
    structures = [_structure(v) for v in views]
    assert all(s == structures[0] for s in structures), "뷰마다 scenario_id·option_id 목록이나 순서가 다르다"
    for view in views:
        mismatched = [k for k, g in _groups(view).items() if g is None]
        assert not mismatched, f"토큰 밖 문자열이 원문과 다르다: {mismatched}"


@case("PRF-P01")
def test_prf_p01_self_and_other_views(srv, expect):
    app = srv.app
    room = _token_room(app)
    views = _views(app, room, ("p1", "p2"))
    for viewer, mapping in expect["token_display"].items():
        shown = {}
        for groups in _groups(views[viewer]).values():
            for token_id, pair, text in groups or []:
                shown.setdefault(token_id, set()).add((pair, text))
        for token_id, name in mapping.items():
            assert token_id in shown, f"{viewer} 뷰에 {token_id} 토큰 자리가 없다"
            for pair, text in shown[token_id]:
                allowed = {name} if pair is None else {name + p for p in PAIRS[pair]}
                assert text in allowed, f"{viewer} 뷰의 {token_id}: {text!r}, 기대 {sorted(allowed)}"
    if expect["same_outside_tokens"]:
        _assert_same_outside_tokens(list(views.values()))


@case("PRF-P02")
def test_prf_p02_particles_for_names_and_you(srv, expect):
    app = srv.app
    texts = []
    for names in ROTATIONS:
        room = _token_room(app, names)
        texts.extend(_all_text(v) for v in _views(app, room).values())
    joined = "\n".join(texts)
    for value in expect["text_includes"]:
        assert value in joined, f"어느 뷰에도 {value!r}가 없다"
    for value in expect["text_excludes"]:
        bad = [i for i, t in enumerate(texts) if value in t]
        assert not bad, f"{value!r}가 뷰 {bad}에 있다"


@case("PRF-P03")
def test_prf_p03_name_change_keeps_view(srv, expect):
    app = srv.app
    first = _views(app, _token_room(app))
    second = _views(app, _token_room(app, OTHER_NAMES))
    if expect["same_outside_tokens"]:
        for pid in first:
            _assert_same_outside_tokens([first[pid], second[pid]])


@case("PRF-P04")
def test_prf_p04_token_in_display_name_is_literal(srv, expect):
    app = srv.app
    profiles = default_profiles()
    profiles[2]["display_name"] = "{{profile:p2}}"
    room = _token_room(app, profiles=profiles)
    views = _views(app, room, ("p1", "p2"))
    for viewer, view in views.items():
        scene = view["scenarios"][0]["scene"]
        for value in expect["text_includes"]:
            assert value in scene, f"{viewer} 뷰의 첫 문항 scene에 {value!r}가 글자 그대로 없다: {scene!r}"


@case("PRF-N01")
def test_prf_n01_optional_profile_not_exposed(srv, expect):
    app = srv.app
    room = _token_room(app)
    assert room.profiles[0].get("gender") and room.profiles[0].get("mbti"), "p1에 선택 정보가 있어야 한다"
    # 검사 범위: 방 조회(방장·참여자)와 세 프로필의 세션 생성 응답 전부
    payloads = [("방 조회", app.room(room)), ("방장 방 조회", app.room(room, host=True))]
    payloads += [(f"{pid} 세션", body) for pid, body in _views(app, room).items()]
    problems = []
    for where, payload in payloads:
        problems += scan_private(payload, expect["privacy_scan"], srv.ctx, where)
    assert not problems, "\n".join(problems)


@case("PRF-N02")
def test_prf_n02_unknown_profile_token(srv, expect):
    render = srv.server.render
    profiles = [{"profile_id": p["profile_id"], "display_name": p["display_name"]} for p in default_profiles()]
    with pytest.raises(render.RenderError) as info:
        render.render_profile_tokens("{{profile:p9}}은/는 먼저 쉬고 싶어요", profiles, "p1")
    assert info.value.code == expect["error_code"]
