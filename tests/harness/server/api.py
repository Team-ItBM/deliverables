"""서버 앱을 띄우고 §0-B API를 부르는 도우미.

ServerHarness는 테스트 하나의 재생 클라이언트·가짜 발송기·대기 함수·시각 함수·테스트 DB를 묶는다.
open_app()은 create_app(settings=, llm_client=, push_sender=, sleeper=, clock=)으로 앱을 만들고
FastAPI TestClient를 연다. 같은 DB로 앱을 여러 개 열 수 있다(동시성·재시작 흉내).
백그라운드 작업은 app.state.jobs.join(), 멈춤 점검은 app.state.jobs.recover_stalled(),
작업 한도 점검은 app.state.jobs.enforce_deadlines(), 알림 재처리는 app.state.notifier.dispatch(room_code, event)로 부른다.
"""

import copy
import json
import re
import threading
import uuid
from dataclasses import dataclass, field

import pytest

from . import db as testdb
from . import pact_outputs, scenario_outputs
from .cases import http_ok
from .fakes import FakeClock, FakePushSender, FakeSleeper
from .privacy import PrivateContext
from .replay import ReplayClient

DEFAULT_NAMES = {"p1": "민준", "p2": "지수", "p3": "하늘"}
JOIN_TIMEOUT = 15
MEMO_TAIL = " 보라색 우산을 든 고양이 이야기"


def default_trip(party_size=None):
    trip = copy.deepcopy(scenario_outputs.ex1()["input"]["trip"])
    if party_size is not None:
        trip["party_size"] = party_size
    return trip


def default_profiles(names=None, party_size=3):
    """ex1_ready 입력의 프로필 p1~p3(선택 정보 포함)에 이름을 바꿔 쓴다. 3명보다 많으면 p4부터 이름만 둔다."""
    names = dict(DEFAULT_NAMES, **(names or {}))
    base = copy.deepcopy(scenario_outputs.ex1()["input"]["participant_profiles"])
    profiles = []
    for i in range(party_size):
        pid = f"p{i + 1}"
        profile = base[i] if i < len(base) else {"profile_id": pid}
        profile["display_name"] = names.get(pid, f"친구{i + 1}")
        profiles.append(profile)
    return profiles


def error_code(resp):
    try:
        body = resp.json()
    except ValueError:
        return None
    if isinstance(body, dict) and isinstance(body.get("error"), dict):
        return body["error"].get("code")
    return None


def assert_error(resp, status, code):
    assert http_ok(status, resp.status_code), f"HTTP {resp.status_code}, 기대 {status}: {resp.text[:300]}"
    assert error_code(resp) == code, f"오류 코드 {error_code(resp)!r}, 기대 {code!r}: {resp.text[:300]}"


def assert_status(resp, status):
    assert http_ok(status, resp.status_code), f"HTTP {resp.status_code}, 기대 {status}: {resp.text[:300]}"


# §0-C 공유 결과의 키. 결과 목록 항목은 여기에 RESULT_LIST_EXTRA를 더한다.
SHARED_RESULT_KEYS = {
    "result_id", "kind", "source_result_id", "label", "draft", "pact_status", "included_count", "excluded_names",
    "clauses", "conditional_alternatives", "unresolved_conditions", "message", "humor",
}
RESULT_LIST_EXTRA = {"attempt", "state", "created_at", "editable"}
# §0-B "편집용 응답"(결정 29·34)의 조각 키. 글 조각과 참여자 조각 두 가지다.
TEXT_SEGMENT_KEYS = {"text"}
PARTICIPANT_SEGMENT_KEYS = {"participant_id", "display", "pair"}
# §0-C "검증 결과를 나타내는 필드와 합의·수락을 뜻하는 필드(agreed, accepted 등)는 두지 않는다"의 예시 이름.
VERDICT_KEYS = {"valid", "errors", "validation", "agreed", "accepted"}
PAIR_PATTERN = r"(?:은/는|이/가|을/를|과/와|으로/로)"


def assert_calls(replay, expected, before=None):
    """판정 키 calls(또는 calls_added)와 재생 기록의 단계별 호출 수를 비교한다. before가 있으면 그 뒤로 늘어난 수다."""
    counts = replay.counts()
    for stage, n in expected.items():
        actual = counts[stage] - ((before or {}).get(stage, 0))
        assert actual == n, f"{stage} 호출 {actual}회, 기대 {n}회"


def error_codes_of(errors):
    """repair_errors의 code 집합. 항목은 {code, ...} 또는 문자열이다."""
    codes = set()
    for item in errors or []:
        if isinstance(item, dict):
            codes.add(item.get("code"))
        elif isinstance(item, str):
            codes.add(item)
    return codes


def template_groups(template, rendered, kind):
    """토큰이 든 원문 template과 치환된 rendered를 대조한다. 토큰 밖 문자열이 같으면 [(토큰 ID, 쌍, 치환 문자열)]을,
    다르면 None을 돌려준다. kind는 profile 또는 participant다."""
    token = re.compile(r"\{\{" + kind + r":([^{}]*)\}\}(" + PAIR_PATTERN + ")?")
    pattern, ids, pos = [], [], 0
    for m in token.finditer(template):
        pattern.append(re.escape(template[pos:m.start()]))
        pattern.append("(.+?)")
        ids.append((m.group(1), m.group(2)))
        pos = m.end()
    pattern.append(re.escape(template[pos:]))
    match = re.fullmatch("".join(pattern), rendered, flags=re.DOTALL)
    if match is None:
        return None
    return [(tid, pair, text) for (tid, pair), text in zip(ids, match.groups())]


def editable_paths(shared):
    """결정 4의 편집 가능한 위치 전부를 공유 결과 기준 JSON Pointer로 돌려준다."""
    paths = []
    for kind in ("clauses", "conditional_alternatives"):
        for i, item in enumerate(shared.get(kind) or []):
            paths.append(f"/{kind}/{i}/action")
            for j, _ in enumerate(item.get("proposed_conditions") or []):
                paths.append(f"/{kind}/{i}/proposed_conditions/{j}")
            if kind == "conditional_alternatives":
                for j, _ in enumerate(item.get("proposed_changes") or []):
                    paths.append(f"/{kind}/{i}/proposed_changes/{j}")
    return paths


def pointer_get(doc, path):
    node = doc
    for part in path.lstrip("/").split("/"):
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


def editable_map(entry):
    """결과 목록 항목의 editable을 {path: segments}로 읽는다. 형식이 §0-B "편집용 응답"과 다르면 실패다."""
    editable = entry.get("editable")
    assert isinstance(editable, list) and editable, f"editable이 비어 있지 않은 리스트가 아니다: {editable!r}"
    mapping = {}
    for item in editable:
        assert isinstance(item, dict) and set(item) == {"path", "segments"}, f"editable 항목 형식: {item!r}"
        assert item["path"] not in mapping, f"editable path 중복 {item['path']}"
        segments = item["segments"]
        assert isinstance(segments, list) and segments, f"{item['path']}: segments가 비어 있다"
        for seg in segments:
            assert isinstance(seg, dict) and set(seg) in (TEXT_SEGMENT_KEYS, PARTICIPANT_SEGMENT_KEYS), \
                f"{item['path']}: 조각 형식 {seg!r}"
            if "text" in seg:
                assert isinstance(seg["text"], str), f"{item['path']}: text가 문자열이 아니다"
            else:
                assert isinstance(seg["participant_id"], str) and seg["participant_id"], f"{item['path']}: participant_id"
                assert isinstance(seg["display"], str) and seg["display"], f"{item['path']}: display"
                assert seg["pair"] is None or re.fullmatch(PAIR_PATTERN, seg["pair"]), f"{item['path']}: pair {seg['pair']!r}"
        mapping[item["path"]] = segments
    return mapping


def segments_display(segments):
    """조각의 text와 display를 차례로 이은 문자열(화면에 보이는 문장)."""
    return "".join(seg["text"] if "text" in seg else seg["display"] for seg in segments)


def segments_template(segments, drop_participant=None):
    """참여자 조각을 {{participant:ID}} + pair로 되돌린 편집 요청 문장. drop_participant의 조각은 토큰만 빼고 쌍을 남긴다."""
    parts = []
    for seg in segments:
        if "text" in seg:
            parts.append(seg["text"])
            continue
        if seg["participant_id"] != drop_participant:
            parts.append("{{participant:" + seg["participant_id"] + "}}")
        parts.append(seg["pair"] or "")
    return "".join(parts)


def replace_in_text_segments(segments, old, new):
    """old가 처음 나오는 글 조각 하나만 new로 바꾼 조각 목록을 돌려준다. 참여자 조각은 그대로 둔다."""
    changed = copy.deepcopy(segments)
    for seg in changed:
        if "text" in seg and old in seg["text"]:
            seg["text"] = seg["text"].replace(old, new, 1)
            return changed
    raise AssertionError(f"글 조각에 {old!r}가 없다: {segments_display(segments)!r}")


def editable_problems(mapping, shared):
    """editable의 위치가 결정 4의 필드 전부이고, 조각을 이은 문자열이 공유 결과 문장과 같은지 본다."""
    problems = []
    expected = editable_paths(shared)
    if sorted(mapping) != sorted(expected):
        problems.append(f"editable 위치 {sorted(mapping)}, 기대 {sorted(expected)}")
    for path in expected:
        if path in mapping and segments_display(mapping[path]) != pointer_get(shared, path):
            problems.append(f"{path}: 조각을 이은 문자열이 공유 결과 문장과 다르다")
    return problems


def run_concurrently(*fns, timeout=30):
    """함수들을 스레드에서 같은 순간에 시작하고 결과를 순서대로 돌려준다."""
    barrier = threading.Barrier(len(fns))
    results = [None] * len(fns)
    errors = [None] * len(fns)

    def runner(i, fn):
        try:
            barrier.wait()
            results[i] = fn()
        except BaseException as exc:  # 스레드 예외를 테스트로 넘긴다
            errors[i] = exc

    threads = [threading.Thread(target=runner, args=(i, fn)) for i, fn in enumerate(fns)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout)
        assert not t.is_alive(), "동시 요청이 끝나지 않았다"
    for exc in errors:
        if exc is not None:
            raise exc
    return results


@dataclass
class Room:
    code: str
    host_token: str
    profiles: list
    body: dict
    names: dict = field(default_factory=dict)

    @property
    def host(self):
        return {"X-Host-Token": self.host_token}


@dataclass
class Submitted:
    profile_id: str
    session: dict
    answers: list
    key: str
    resp: object

    @property
    def body(self):
        return self.resp.json()


class AppHandle:
    def __init__(self, harness, app, client, replay):
        self.harness = harness
        self.app = app
        self.client = client
        self.replay = replay

    # 백그라운드 작업 진입점
    def _call(self, fn, *args, timeout=JOIN_TIMEOUT):
        async def runner():
            import anyio

            with anyio.fail_after(timeout):
                return await fn(*args)

        return self.client.portal.call(runner)

    def join(self, timeout=JOIN_TIMEOUT):
        self._call(self.app.state.jobs.join, timeout=timeout)
        self.harness.check_replay()

    def recover_stalled(self):
        return self._call(self.app.state.jobs.recover_stalled)

    def enforce_deadlines(self):
        return self._call(self.app.state.jobs.enforce_deadlines)

    def dispatch(self, room_code, event):
        return self._call(self.app.state.notifier.dispatch, room_code, event)

    # HTTP
    def get(self, path, headers=None):
        return self.client.get(path, headers=headers or {})

    def post(self, path, json_body=None, headers=None):
        return self.client.post(path, json=json_body, headers=headers or {})

    def create_room(self, profiles=None, trip=None, scenario=None, push_scenario=True, wait=True):
        """방을 만든다. 201이면 (resp, Room), 아니면 (resp, None). push_scenario면 문항 재생 항목을 먼저 넣는다."""
        profiles = default_profiles() if profiles is None else profiles
        trip = default_trip(len(profiles)) if trip is None else trip
        if push_scenario:
            self.replay.push("scenarios", scenario or scenario_outputs.scenario_item())
        resp = self.post("/api/rooms", {"trip": trip, "participant_profiles": profiles})
        if resp.status_code != 201:
            return resp, None
        body = resp.json()
        room = Room(code=body["room_code"], host_token=body["host_token"], profiles=profiles, body=body,
                    names={p["profile_id"]: p.get("display_name") for p in profiles})
        self.harness.register_room(room)
        if wait:
            self.join()
        return resp, room

    def room(self, room, host=False):
        resp = self.get(f"/api/rooms/{room.code}", headers=room.host if host else None)
        assert resp.status_code == 200, f"방 조회 HTTP {resp.status_code}: {resp.text[:300]}"
        return resp.json()

    def session(self, room, profile_id):
        return self.post(f"/api/rooms/{room.code}/sessions", {"profile_id": profile_id})

    def answers(self, session_body, choose=0, memo=None):
        """세션 응답의 문항마다 choose번째 선택지를 고른다. memo가 함수면 memo(i)를 메모로 넣는다."""
        answers = []
        for i, scenario in enumerate(session_body["scenarios"]):
            answer = {"scenario_id": scenario["scenario_id"],
                      "option_id": scenario["options"][choose % len(scenario["options"])]["option_id"]}
            value = memo(i) if callable(memo) else memo
            if value is not None:
                answer["memo"] = value
            answers.append(answer)
        return answers

    def submit(self, room, session_id, answers, key="new"):
        headers = {}
        if key == "new":
            key = uuid.uuid4().hex
        if key is not None:
            headers["Idempotency-Key"] = key
        resp = self.post(f"/api/rooms/{room.code}/submissions", {"session_id": session_id, "answers": answers}, headers)
        return resp, key

    def submit_new(self, room, profile_id, choose=0, memo="marker"):
        """세션을 만들고 전체 문항에 답해 제출한다. memo="marker"면 제출·문항마다 다른 메모 표지를 넣는다."""
        resp = self.session(room, profile_id)
        assert resp.status_code == 201, f"세션 생성 HTTP {resp.status_code}: {resp.text[:300]}"
        session = resp.json()
        if memo == "marker":
            tag = uuid.uuid4().hex[:6]
            memo_fn = lambda i: self.harness.memo(f"{tag}{i}")  # noqa: E731
        else:
            memo_fn = memo
        answers = self.answers(session, choose=choose, memo=memo_fn)
        sresp, key = self.submit(room, session["session_id"], answers)
        return Submitted(profile_id, session, answers, key, sresp)

    def generate(self, room, headers="host"):
        return self.post(f"/api/rooms/{room.code}/generate", None, room.host if headers == "host" else headers)

    def retry(self, room, headers="host"):
        return self.post(f"/api/rooms/{room.code}/retry", None, room.host if headers == "host" else headers)

    def regenerate(self, room, headers="host"):
        return self.post(f"/api/rooms/{room.code}/regenerate", None, room.host if headers == "host" else headers)

    def result(self, room, host=False):
        return self.get(f"/api/rooms/{room.code}/result", headers=room.host if host else None)

    def results(self, room, headers="host"):
        return self.get(f"/api/rooms/{room.code}/results", headers=room.host if headers == "host" else headers)

    def results_body(self, room):
        resp = self.results(room)
        assert resp.status_code == 200, f"결과 목록 HTTP {resp.status_code}: {resp.text[:300]}"
        return resp.json()

    def result_entry(self, room, result_id):
        for entry in self.results_body(room)["results"]:
            if entry["result_id"] == result_id:
                return entry
        raise AssertionError(f"결과 목록에 {result_id}가 없다")

    def editable(self, room, result_id):
        """방장 결과 목록에서 그 AI 원본 항목의 editable을 {path: segments}로 읽는다(결정 29·33)."""
        return editable_map(self.result_entry(room, result_id))

    def edited_text(self, room, result_id, path, old, new):
        """editable만으로 만든 편집 요청 문장: 글 조각의 old를 new로 바꾸고 참여자 조각은 토큰과 쌍으로 되돌린다."""
        return segments_template(replace_in_text_segments(self.editable(room, result_id)[path], old, new))

    def select(self, room, result_id, headers="host"):
        return self.post(f"/api/rooms/{room.code}/results/{result_id}/select", None,
                         room.host if headers == "host" else headers)

    def edit(self, room, result_id, edits, headers="host"):
        return self.post(f"/api/rooms/{room.code}/results/{result_id}/edits", {"edits": edits},
                         room.host if headers == "host" else headers)

    def subscribe(self, room, role, session_id=None, endpoint=None, headers=None, subscription=None):
        if subscription is None:
            subscription = {"endpoint": endpoint or f"https://push.test/{uuid.uuid4().hex}",
                            "keys": {"p256dh": "test-p256dh", "auth": "test-auth"}}
        body = {"role": role, "subscription": subscription}
        if session_id is not None:
            body["session_id"] = session_id
        if headers is None:
            headers = room.host if role == "host" else {}
        return self.post(f"/api/rooms/{room.code}/push-subscriptions", body, headers)

    # 자주 쓰는 준비
    def ready_room(self, party_size=3, names=None, pact=None, submit_choose=0):
        """기본 방을 만들고 전원 제출로 자동 생성해 ready까지 기다린다."""
        _, room = self.create_room(profiles=default_profiles(names, party_size))
        assert room is not None, "기본 방 생성 실패"
        self.replay.push("pact", pact or pact_outputs.pact_item())
        submitted = [self.submit_new(room, p["profile_id"], choose=submit_choose) for p in room.profiles]
        for s in submitted:
            assert s.resp.status_code == 201, f"제출 HTTP {s.resp.status_code}: {s.resp.text[:300]}"
        self.join()
        return room, submitted


class ServerHarness:
    """테스트 하나의 서버 실행 환경. conftest의 srv fixture가 만든다."""

    def __init__(self, server, database_url, pool_path):
        self.server = server
        self.database_url = database_url
        self.pool_path = pool_path
        self.push = FakePushSender()
        self.sleeper = FakeSleeper()
        self.clock = FakeClock()
        self.ctx = PrivateContext()
        self.replays = []
        self.handles = []
        self.rooms = []
        self.replay = self.new_replay()
        ex1 = scenario_outputs.ex1_output()
        self.ctx.public_texts.extend(scenario_outputs.public_texts(ex1))
        self.ctx.public_texts.extend(scenario_outputs.public_texts(scenario_outputs.token_output()))
        self.ctx.option_labels.extend(o["label"] for s in ex1["scenarios"] for o in s["options"])
        server.db.init_schema(database_url)
        self._app = None

    # 구성
    def new_replay(self):
        replay = ReplayClient(result_factory=self.server.llm.LLMResult, error_factory=self.server.llm.LLMCallError)
        self.replays.append(replay)
        return replay

    def settings(self, **overrides):
        request = scenario_outputs.ex1()["input"]["request"]
        values = {
            "database_url": self.database_url,
            "pool_path": str(self.pool_path),
            "scenario_requested_count": scenario_outputs.ex1()["input"]["requested_count"],
            "scenario_request": request,
        }
        values.update(overrides)
        return self.server.app.Settings(**values)

    def open_app(self, replay=None, **settings):
        from fastapi.testclient import TestClient

        replay = replay or self.replay
        settings_obj = self.settings(**settings)
        app = self.server.app.create_app(settings=settings_obj, llm_client=replay,
                                         push_sender=self.push, sleeper=self.sleeper, clock=self.clock)
        client = TestClient(app)
        client.__enter__()
        handle = AppHandle(self, app, client, replay)
        handle.settings = settings_obj
        self.handles.append(handle)
        return handle

    @property
    def app(self):
        if self._app is None:
            self._app = self.open_app()
        return self._app

    def close(self):
        for replay in self.replays:
            replay.close()
        for handle in reversed(self.handles):
            try:
                handle._call(handle.app.state.jobs.join, timeout=5)
            except BaseException:
                pass
            try:
                handle.client.__exit__(None, None, None)
            except BaseException:
                pass

    # 기록
    def check_replay(self):
        failures = [f for r in self.replays for f in r.failures]
        if failures:
            pytest.fail("재생 클라이언트 오류: " + "; ".join(failures))

    def register_room(self, room):
        self.rooms.append(room)
        for profile in room.profiles:
            name = profile.get("display_name")
            if isinstance(name, str) and name and name not in self.ctx.names:
                self.ctx.names.append(name)
            for key in ("gender", "age_band", "mbti"):
                value = profile.get(key)
                if isinstance(value, str) and value not in self.ctx.profile_values:
                    self.ctx.profile_values.append(value)

    def memo(self, tag):
        value = f"메모표지{tag}{MEMO_TAIL}"
        self.ctx.add_memo(value)
        return value

    def collect_original_conditions(self):
        for replay in self.replays:
            for call in replay.calls_for("pact"):
                try:
                    output = json.loads(call.raw_output or "")
                except ValueError:
                    continue
                if isinstance(output, dict):
                    self.ctx.add_original_conditions(pact_outputs.original_conditions(output))
        return list(self.ctx.original_conditions)

    def pact_outputs(self, replay=None):
        outputs = []
        for call in (replay or self.replay).calls_for("pact"):
            try:
                outputs.append(json.loads(call.raw_output or ""))
            except ValueError:
                outputs.append(None)
        return outputs

    def sql(self, statement, params=()):
        return testdb.query(self.database_url, statement, params)
