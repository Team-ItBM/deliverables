"""FastAPI 앱과 §0-B 사용자 API(docs/prompts/delegation_server.md §0).

create_app(settings=, llm_client=, push_sender=, sleeper=, clock=)으로 만든다. 테스트는 재생 클라이언트·가짜 발송기·
가짜 대기·가짜 시각을 넣고, 운영은 main.py가 실제 구현을 넣는다.
- 오류 응답은 {"error": {"code", "message"}}이며 message에 메모·이름·선택 프로필을 넣지 않는다(§0-A 4).
- 방장 권한은 X-Host-Token 헤더를 해시로 비교한다. 권한 검사는 상태 검사보다 먼저다.
- 공유 응답에는 memo, positions, original_condition, 선택 프로필, source_response_ids, response_id, 결과 속 option_id를
  넣지 않는다(§0-A 6, AC3).
- 입력 검증은 pydantic 모델이 아니라 코드로 한다. 필수 값 누락·해석할 수 없는 값은 needs_information, 형식·범위·ID
  위반은 invalid_input이다(결정 2).
"""

import copy
import hashlib
import hmac
import json
import secrets
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from travel.pact import InputIndex, check_memo_quotes

from . import db, render
from .jobs import JobManager
from .logging import AccessLogMiddleware, log
from .push import DEFAULT_PUSH_HOSTS, Notifier, endpoint_allowed

PRIVACY_NOTICE = ("선택과 메모 원문은 다른 사람에게 공개되지 않아요. "
                  "다만 답변에 담긴 바람과 한계는 선택한 이름과 함께 추천 결과에 반영될 수 있어요.")
ERROR_STATUS = {
    "invalid_input": 422, "needs_information": 422, "host_forbidden": 403, "not_found": 404, "room_closed": 409,
    "no_submissions": 409, "invalid_state": 409, "regeneration_limit": 409, "session_used": 409,
    "idempotency_conflict": 409, "edit_not_allowed": 422, "memo_quote": 422, "render_failed": 500,
}
MESSAGES = {
    "invalid_input": "입력 형식이나 범위가 맞지 않아요.",
    "needs_information": "필요한 정보가 비어 있거나 해석할 수 없어요.",
    "host_forbidden": "방장만 할 수 있어요.",
    "not_found": "찾을 수 없어요.",
    "room_closed": "응답이 마감된 방이에요.",
    "no_submissions": "제출된 응답이 없어 생성할 수 없어요.",
    "invalid_state": "지금 상태에서는 할 수 없는 작업이에요.",
    "regeneration_limit": "정상 결과는 두 번까지만 만들 수 있어요.",
    "session_used": "이미 제출한 세션이에요.",
    "idempotency_conflict": "같은 요청 키로 다른 내용이 왔어요.",
    "edit_not_allowed": "조항 문구만 고칠 수 있어요.",
    "memo_quote": "다른 사람의 메모 원문을 그대로 넣을 수 없어요.",
    "render_failed": "결과를 표시할 수 없어요.",
}
OPTIONAL_PROFILE_KEYS = ("gender", "age_band", "mbti")


@dataclass
class Settings:
    database_url: str
    pool_path: str
    scenario_requested_count: int = 6
    scenario_request: str = "다른 사람의 성향을 정하지 말고 서로 다른 장면을 골라줘."
    pact_request: str = "각자의 조건을 보존하는 추천 조항을 만들어줘."
    retry_backoff_seconds: tuple = (1, 2)
    retry_jitter_seconds: float = 0.5
    job_time_limit_seconds: int = 300
    stall_limit_seconds: int = 600
    llm_timeout_seconds: float = 90
    max_concurrent_generations: int = 4
    pool_size: int = 5
    party_size_min: int = 2
    party_size_max: int = 8
    memo_max_length: int = 300
    expires_days: int = 30
    public_base_url: str = "http://localhost:5173"
    vapid_public_key: str = ""
    model_id: str = "gpt-6.1-sol"
    prompt_versions: dict = field(default_factory=lambda: {"scenarios": "9", "pact": "12"})
    schema_versions: dict = field(default_factory=lambda: {"scenarios": "2", "pact": "4"})
    maintenance_interval_seconds: float = 0
    access_log: bool = True
    trusted_proxy_hops: int = 0  # 앱 앞의 믿는 프록시 구간 수. 운영 이미지는 2(CloudFront, ALB)다
    push_allowed_hosts: tuple = DEFAULT_PUSH_HOSTS
    push_timeout_seconds: float = 10  # 제안값이며 측정값이 아니다. 없으면 pywebpush 기본값 10000초가 쓰인다
    room_cap_usd: float = None  # 방당 비용 상한(config/llm.yaml room_cap_usd). None이면 검사하지 않는다(테스트 기본)

    def __post_init__(self):
        if self.stall_limit_seconds <= self.job_time_limit_seconds:
            raise ValueError("stall_limit_seconds는 job_time_limit_seconds보다 커야 한다(결정 12)")
        if self.room_cap_usd is not None and self.room_cap_usd <= 0:
            raise ValueError("room_cap_usd는 0보다 커야 한다")


class ApiError(Exception):
    def __init__(self, code, message=None):
        super().__init__(code)
        self.code = code
        self.status = ERROR_STATUS[code]
        self.message = message or MESSAGES[code]


def error_response(code, message=None):
    return JSONResponse(status_code=ERROR_STATUS[code], content={"error": {"code": code, "message": message or MESSAGES[code]}})


class ScenarioPool:
    """settings.pool_path의 pool 파일. 목록(ScenarioIndexEntry)·전체 항목·원본 조회를 준다."""

    def __init__(self, path):
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        self.version = data.get("pool_version")
        self._items = data["scenario_pool"]
        self._by_id = {item["template_id"]: item for item in self._items}

    def items(self):
        return copy.deepcopy(self._items)

    def index(self):
        return [{"template_id": i["template_id"], "title": i.get("title"), "purpose": i.get("purpose"),
                 "decision_key": i.get("decision_key")} for i in self._items]

    def lookup(self, template_id):
        return copy.deepcopy(self._by_id[template_id])


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def iso(moment):
    return moment.isoformat()


def create_app(*, settings, llm_client, push_sender, sleeper, clock):
    pool_source = ScenarioPool(settings.pool_path)
    notifier = Notifier(push_sender, settings, clock)
    jobs = JobManager(settings, llm_client, sleeper, clock, notifier, pool_source)

    @asynccontextmanager
    async def lifespan(app):
        app.state.db = db.Pool(settings.database_url, size=settings.pool_size)
        notifier.pool = app.state.db
        jobs.bind(app.state.db)
        ticker = None
        if settings.maintenance_interval_seconds:
            ticker = _start_ticker(jobs, settings.maintenance_interval_seconds)
        try:
            yield
        finally:
            if ticker is not None:
                ticker.cancel()
            await jobs.shutdown()
            await app.state.db.close()

    app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.jobs = jobs
    app.state.notifier = notifier
    app.state.clock = clock

    @app.exception_handler(ApiError)
    async def _api_error(_request, exc):
        return error_response(exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request, _exc):
        return error_response("invalid_input")

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request, exc):
        if exc.status_code == 404:
            return error_response("not_found")
        if exc.status_code == 405:
            return JSONResponse(status_code=405, content={"error": {"code": "method_not_allowed", "message": "허용되지 않는 방법이에요."}})
        return JSONResponse(status_code=exc.status_code, content={"error": {"code": "http_error", "message": "요청을 처리할 수 없어요."}})

    @app.exception_handler(render.RenderError)
    async def _render_error(_request, _exc):
        return error_response("render_failed")

    _register_routes(app, settings, jobs, notifier, clock, pool_source)
    app.add_middleware(AccessLogMiddleware, enabled=settings.access_log, trusted_proxy_hops=settings.trusted_proxy_hops)
    return app


def _start_ticker(jobs, interval):
    import asyncio

    async def tick():
        while True:
            await asyncio.sleep(interval)
            try:
                await jobs.enforce_deadlines()
                await jobs.recover_stalled()
            except Exception as exc:
                log("maintenance_error", error=type(exc).__name__)

    return asyncio.create_task(tick())


# ---- 입력 검증


def _is_nonempty_str(value):
    return isinstance(value, str) and value.strip() != ""


def parse_room_request(body, settings):
    if not isinstance(body, dict):
        raise ApiError("invalid_input")
    trip = body.get("trip")
    profiles = body.get("participant_profiles")
    if not isinstance(trip, dict) or not isinstance(profiles, list):
        raise ApiError("invalid_input")
    party_size = trip.get("party_size")
    if not isinstance(party_size, int) or isinstance(party_size, bool):
        raise ApiError("invalid_input")
    if not settings.party_size_min <= party_size <= settings.party_size_max:
        raise ApiError("invalid_input")
    if len(profiles) != party_size:
        raise ApiError("invalid_input")
    ids = []
    for profile in profiles:
        if not isinstance(profile, dict) or not _is_nonempty_str(profile.get("profile_id")):
            raise ApiError("invalid_input")
        ids.append(profile["profile_id"])
        for key in OPTIONAL_PROFILE_KEYS:
            if key in profile and profile[key] is not None and not isinstance(profile[key], str):
                raise ApiError("invalid_input")
    if len(set(ids)) != len(ids):
        raise ApiError("invalid_input")
    if not _is_nonempty_str(trip.get("destination")) or not _is_nonempty_str(trip.get("relationship")):
        raise ApiError("needs_information")
    duration = trip.get("duration_days")
    if not isinstance(duration, int) or isinstance(duration, bool):
        raise ApiError("needs_information")
    if duration < 1:
        raise ApiError("invalid_input")
    for profile in profiles:
        if not _is_nonempty_str(profile.get("display_name")):
            raise ApiError("needs_information")
    clean_trip = {"destination": trip["destination"], "duration_days": duration, "party_size": party_size,
                  "relationship": trip["relationship"]}
    clean_profiles = []
    for profile in profiles:
        item = {"profile_id": profile["profile_id"], "display_name": profile["display_name"]}
        for key in OPTIONAL_PROFILE_KEYS:
            if profile.get(key) is not None:
                item[key] = profile[key]
        clean_profiles.append(item)
    return clean_trip, clean_profiles


def validate_answers(answers, scenario_set, settings):
    """전체 문항의 답변 묶음인지 본다. 정규화한 [{scenario_id, option_id, memo}]를 돌려준다(memo는 없으면 None)."""
    if not isinstance(answers, list):
        raise ApiError("invalid_input")
    options = {s["template_id"]: {o["option_id"] for o in s["options"]} for s in scenario_set["scenarios"]}
    seen = set()
    rows = []
    for answer in answers:
        if not isinstance(answer, dict):
            raise ApiError("invalid_input")
        sid, oid = answer.get("scenario_id"), answer.get("option_id")
        if sid not in options or oid not in options[sid] or sid in seen:
            raise ApiError("invalid_input")
        seen.add(sid)
        memo = answer.get("memo")
        if memo is not None and (not isinstance(memo, str) or len(memo) > settings.memo_max_length):
            raise ApiError("invalid_input")
        rows.append({"scenario_id": sid, "option_id": oid, "memo": memo})
    if len(rows) != len(options):
        raise ApiError("invalid_input")
    order = {s["template_id"]: i for i, s in enumerate(scenario_set["scenarios"])}
    rows.sort(key=lambda r: order[r["scenario_id"]])
    return rows


def body_hash(session_id, answers):
    return hashlib.sha256(json.dumps({"session_id": session_id, "answers": answers}, ensure_ascii=False,
                                     sort_keys=True).encode("utf-8")).hexdigest()


def parse_uuid(value):
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


# ---- 경로


def _register_routes(app, settings, jobs, notifier, clock, pool_source):
    def pool():
        return app.state.db

    async def read_json(request):
        try:
            body = await request.json()
        except Exception:
            raise ApiError("invalid_input")
        return body

    def host_token(request):
        return request.headers.get("X-Host-Token")

    def require_host(room, request):
        token = host_token(request)
        if not token or not hmac.compare_digest(hash_token(token), room["host_token_hash"]):
            raise ApiError("host_forbidden")

    def is_host(room, request):
        token = host_token(request)
        return bool(token) and hmac.compare_digest(hash_token(token), room["host_token_hash"])

    async def load_room(conn, room_code, for_update=False):
        room = await db.fetch_room_by_code(conn, room_code, for_update=for_update)
        if room is None:
            raise ApiError("not_found")
        return room

    async def roster_of(conn, room):
        subs = await db.fetch_submissions(conn, room["room_id"])
        profiles = {p["profile_id"]: p["display_name"] for p in await db.fetch_profiles(conn, room["room_id"])}
        return [{"participant_id": str(s["participant_id"]), "display_name": profiles[s["profile_id"]]} for s in subs]

    def core_constraints_of(scenario):
        """문항을 확정할 때 저장한 값을 쓴다. 저장 전에 만든 방은 pool에서 조회한다. pool에도 없으면 필드를 뺀다."""
        if "core_constraints" in scenario:
            return scenario["core_constraints"]
        try:
            return pool_source.lookup(scenario["template_id"]).get("core_constraints")
        except KeyError:
            log("core_constraints_missing", template_id=scenario["template_id"])
            return None

    async def build_frozen(conn, room):
        profiles = await db.fetch_profiles(conn, room["room_id"])
        subs = await db.fetch_submissions(conn, room["room_id"])
        responses = await db.fetch_responses(conn, room["room_id"])
        participant_ids = [str(s["participant_id"]) for s in subs]
        # 추천 프롬프트 v12는 scenarios[].template_id를 읽고, SPEC 5절은 scenario_id=template_id로 연결한다. 둘 다 보낸다.
        scenarios = []
        for s in room["scenario_set"]["scenarios"]:
            item = {"scenario_id": s["template_id"], "template_id": s["template_id"], "scene": s["scene"],
                    "question": s["question"],
                    "options": [{"option_id": o["option_id"], "label": o["label"]} for o in s["options"]]}
            constraints = core_constraints_of(s)
            if constraints is not None:
                item["core_constraints"] = constraints
            scenarios.append(item)
        rows = []
        for r in responses:
            item = {"response_id": str(r["response_id"]), "participant_id": str(r["participant_id"]),
                    "scenario_id": r["scenario_id"], "option_id": r["option_id"]}
            if r["memo"] is not None:
                item["memo"] = r["memo"]
            rows.append(item)
        submitted = {s["profile_id"] for s in subs}
        excluded = [p["display_name"] for p in profiles if p["profile_id"] not in submitted]
        model_input = {"participant_ids": participant_ids, "scenarios": scenarios, "responses": rows,
                       "request": settings.pact_request}
        return {"model_input": model_input, "included_count": len(subs), "excluded_names": excluded}

    # 1. 방 생성
    @app.post("/api/rooms", status_code=201)
    async def create_room(request: Request):
        trip, profiles = parse_room_request(await read_json(request), settings)
        now = clock()
        room_id = uuid.uuid4()
        room_code = secrets.token_urlsafe(8).replace("-", "a").replace("_", "b")
        token = secrets.token_hex(16)
        expires = now + timedelta(days=settings.expires_days)
        scenario_attempt_id = uuid.uuid4()
        async with pool().transaction() as conn:
            await conn.execute(
                "INSERT INTO rooms (room_id, room_code, host_token_hash, trip, party_size, status, scenario_status, "
                "scenario_started_at, scenario_attempt_id, scenario_attempt_count, created_at, expires_at) "
                "VALUES (%s, %s, %s, %s, %s, 'open', 'preparing', %s, %s, 1, %s, %s)",
                (room_id, room_code, hash_token(token), db.jsonb(trip), trip["party_size"], now, scenario_attempt_id,
                 now, expires))
            for i, profile in enumerate(profiles):
                await conn.execute(
                    "INSERT INTO profiles (room_id, profile_id, position, display_name, gender, age_band, mbti) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (room_id, profile["profile_id"], i, profile["display_name"], profile.get("gender"),
                     profile.get("age_band"), profile.get("mbti")))
        jobs.start_scenarios(room_id, room_code, scenario_attempt_id, 1, now)
        log("room_created", room_code=room_code, party_size=trip["party_size"])
        return {"room_code": room_code, "host_token": token, "created_at": iso(now), "expires_at": iso(expires),
                "scenario_status": "preparing"}

    # 2. 방 조회
    @app.get("/api/rooms/{room_code}")
    async def get_room(room_code: str, request: Request):
        async with pool().connection() as conn:
            room = await load_room(conn, room_code)
            profiles = await db.fetch_profiles(conn, room["room_id"])
            subs = await db.fetch_submissions(conn, room["room_id"])
        submitted = {s["profile_id"] for s in subs}
        view = {
            "room_status": room["status"],
            "scenario_status": room["scenario_status"],
            "party_size": room["party_size"],
            "trip": render.public_trip(db.as_json(room["trip"])),
            "submitted_count": room["submitted_count"],
            "profiles": [{"profile_id": p["profile_id"], "display_name": p["display_name"],
                          "has_submission": p["profile_id"] in submitted} for p in profiles],
        }
        if room["failure_reason"]:
            view["failure_reason"] = room["failure_reason"]
        if is_host(room, request) and room["scenario_notice"]:
            view["scenario_notice"] = room["scenario_notice"]
        return view

    @app.delete("/api/rooms/{room_code}", status_code=204)
    async def delete_room(room_code: str, request: Request):
        async with pool().transaction() as conn:
            room = await load_room(conn, room_code, for_update=True)
            require_host(room, request)
            if room["scenario_status"] == "preparing" or room["status"] == "generating":
                raise ApiError("invalid_state")
            await conn.execute("UPDATE llm_calls SET room_id = NULL WHERE room_id = %s", (room["room_id"],))
            await conn.execute("DELETE FROM rooms WHERE room_id = %s", (room["room_id"],))
        return Response(status_code=204)

    # 3. 세션(이름 선택)
    @app.post("/api/rooms/{room_code}/sessions", status_code=201)
    async def create_session(room_code: str, request: Request):
        body = await read_json(request)
        profile_id = body.get("profile_id") if isinstance(body, dict) else None
        if not _is_nonempty_str(profile_id):
            raise ApiError("invalid_input")
        now = clock()
        async with pool().transaction() as conn:
            room = await load_room(conn, room_code)
            profiles = await db.fetch_profiles(conn, room["room_id"])
            if profile_id not in {p["profile_id"] for p in profiles}:
                raise ApiError("not_found")
            if room["status"] != "open":
                raise ApiError("room_closed")
            if room["scenario_status"] != "ready" or not room["scenario_set"]:
                raise ApiError("invalid_state")
            subs = await db.fetch_submissions(conn, room["room_id"])
            session_id = uuid.uuid4()
            await conn.execute(
                "INSERT INTO sessions (session_id, room_id, profile_id, created_at) VALUES (%s, %s, %s, %s)",
                (session_id, room["room_id"], profile_id, now))
        scenarios = []
        for s in room["scenario_set"]["scenarios"]:
            scenarios.append({
                "scenario_id": s["template_id"],
                "scene": render.render_profile_tokens(s["scene"], profiles, profile_id),
                "question": render.render_profile_tokens(s["question"], profiles, profile_id),
                "options": [{"option_id": o["option_id"],
                             "label": render.render_profile_tokens(o["label"], profiles, profile_id)}
                            for o in s["options"]],
            })
        return {"session_id": str(session_id),
                "duplicate_name_notice": any(s["profile_id"] == profile_id for s in subs),
                "privacy_notice": PRIVACY_NOTICE, "scenarios": scenarios}

    # 4. 제출
    @app.post("/api/rooms/{room_code}/submissions", status_code=201)
    async def submit(room_code: str, request: Request):
        key = request.headers.get("Idempotency-Key")
        if not _is_nonempty_str(key):
            raise ApiError("invalid_input")
        body = await read_json(request)
        if not isinstance(body, dict):
            raise ApiError("invalid_input")
        session_id = parse_uuid(body.get("session_id"))
        answers = body.get("answers")
        digest = body_hash(str(body.get("session_id")), answers)
        now = clock()
        started = None
        async with pool().transaction() as conn:
            room = await load_room(conn, room_code, for_update=True)
            # 전송 재시도(같은 키·같은 본문)는 마감 뒤에도 같은 건으로 200을 돌려준다(§0-B 4, 결정 43).
            cur = await conn.execute(
                "SELECT participant_id, body_hash FROM submissions WHERE room_id = %s AND idempotency_key = %s",
                (room["room_id"], key))
            existing = await cur.fetchone()
            if existing is not None:
                if existing["body_hash"] != digest:
                    raise ApiError("idempotency_conflict")
                return JSONResponse(status_code=200, content={
                    "participant_id": str(existing["participant_id"]),
                    "submitted_count": room["submitted_count"], "party_size": room["party_size"]})
            if room["status"] != "open":
                raise ApiError("room_closed")
            if session_id is None:
                raise ApiError("not_found")
            cur = await conn.execute("SELECT * FROM sessions WHERE session_id = %s AND room_id = %s",
                                     (session_id, room["room_id"]))
            session = await cur.fetchone()
            if session is None:
                raise ApiError("not_found")
            if session["used_at"] is not None:
                raise ApiError("session_used")
            rows = validate_answers(answers, room["scenario_set"], settings)
            participant_id = uuid.uuid4()
            new_count = room["submitted_count"] + 1
            await conn.execute(
                "INSERT INTO submissions (participant_id, room_id, profile_id, session_id, submission_no, "
                "idempotency_key, body_hash, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (participant_id, room["room_id"], session["profile_id"], session_id, new_count, key, digest, now))
            for i, row in enumerate(rows):
                await conn.execute(
                    "INSERT INTO responses (response_id, participant_id, room_id, position, scenario_id, option_id, memo) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (uuid.uuid4(), participant_id, room["room_id"], i, row["scenario_id"], row["option_id"], row["memo"]))
            await conn.execute("UPDATE sessions SET used_at = %s WHERE session_id = %s", (now, session_id))
            await conn.execute("UPDATE rooms SET submitted_count = %s WHERE room_id = %s", (new_count, room["room_id"]))
            if new_count >= room["party_size"]:
                frozen = await build_frozen(conn, room)
                attempt_id, attempt_no = await db.close_and_freeze(conn, room, frozen, now)
                started = (attempt_id, attempt_no)
        if started is not None:
            jobs.start_pact(room["room_id"], room_code, started[0], started[1], now)
        log("submitted", room_code=room_code, submitted_count=new_count)
        return {"participant_id": str(participant_id), "submitted_count": new_count, "party_size": room["party_size"]}

    # 5. 조기 생성
    @app.post("/api/rooms/{room_code}/generate", status_code=202)
    async def generate(room_code: str, request: Request):
        now = clock()
        async with pool().transaction() as conn:
            room = await load_room(conn, room_code, for_update=True)
            require_host(room, request)
            if room["status"] != "open":
                raise ApiError("room_closed")
            if room["submitted_count"] == 0:
                raise ApiError("no_submissions")
            frozen = await build_frozen(conn, room)
            attempt_id, attempt_no = await db.close_and_freeze(conn, room, frozen, now)
        jobs.start_pact(room["room_id"], room_code, attempt_id, attempt_no, now)
        return {"room_status": "generating", "included_count": frozen["included_count"]}

    # 6. 재시도
    @app.post("/api/rooms/{room_code}/retry", status_code=202)
    async def retry(room_code: str, request: Request):
        now = clock()
        async with pool().transaction() as conn:
            room = await load_room(conn, room_code, for_update=True)
            require_host(room, request)
            scenarios_failed = room["status"] == "open" and room["scenario_status"] == "failed"
            if room["status"] != "failed" and not scenarios_failed:
                raise ApiError("invalid_state")
            if scenarios_failed:
                attempt_id, attempt_no = await db.start_scenario_attempt(conn, room, now)
            else:
                attempt_id, attempt_no = await db.start_attempt(conn, room, now, ("failed",))
        if scenarios_failed:
            jobs.start_scenarios(room["room_id"], room_code, attempt_id, attempt_no, now)
            return {"room_status": "open", "scenario_status": "preparing"}
        jobs.start_pact(room["room_id"], room_code, attempt_id, attempt_no, now)
        return {"room_status": "generating"}

    # 7. 재생성
    @app.post("/api/rooms/{room_code}/regenerate", status_code=202)
    async def regenerate(room_code: str, request: Request):
        now = clock()
        async with pool().transaction() as conn:
            room = await load_room(conn, room_code, for_update=True)
            require_host(room, request)
            if room["status"] in ("open", "generating"):
                raise ApiError("invalid_state")
            normal = await db.normal_result_count(conn, room["room_id"])
            if normal == 0:
                raise ApiError("invalid_state")
            if normal >= 2:
                raise ApiError("regeneration_limit")
            attempt_id, attempt_no = await db.start_attempt(conn, room, now, ("ready", "failed"))
        jobs.start_pact(room["room_id"], room_code, attempt_id, attempt_no, now)
        return {"room_status": "generating"}

    # ---- 결과 공통

    async def ai_results(conn, room_id):
        cur = await conn.execute(
            "SELECT * FROM results WHERE room_id = %s AND kind = 'ai_original' ORDER BY attempt", (room_id,))
        return await cur.fetchall()

    async def latest_edit(conn, origin_id):
        cur = await conn.execute(
            "SELECT * FROM results WHERE origin_result_id = %s AND kind = 'host_edited' ORDER BY seq DESC LIMIT 1",
            (origin_id,))
        return await cur.fetchone()

    def shared(row, room, roster, draft):
        frozen = room["frozen_input"] or {}
        return render.shared_result(
            db.as_json(row["output"]), roster, result_id=row["result_id"], kind=row["kind"],
            source_result_id=row["source_result_id"], draft=draft,
            included_count=frozen.get("included_count", 0), excluded_names=frozen.get("excluded_names", []),
            trip=db.as_json(room["trip"]))

    async def shown_origin(conn, room):
        rows = await ai_results(conn, room["room_id"])
        if room["selected_result_id"] is not None:
            for row in rows:
                if row["result_id"] == room["selected_result_id"]:
                    return row
        for row in rows:
            if row["state"] == "normal":
                return row
        return None

    # 8. 참여자 결과
    @app.get("/api/rooms/{room_code}/result")
    async def get_result(room_code: str):
        async with pool().connection() as conn:
            room = await load_room(conn, room_code)
            origin = await shown_origin(conn, room)
            if origin is None:
                raise ApiError("invalid_state")
            row = await latest_edit(conn, origin["result_id"]) or origin
            roster = await roster_of(conn, room)
        return shared(row, room, roster, draft=room["selected_result_id"] is None)

    # 9. 방장 결과 목록
    @app.get("/api/rooms/{room_code}/results")
    async def list_results(room_code: str, request: Request):
        async with pool().connection() as conn:
            room = await load_room(conn, room_code)
            require_host(room, request)
            rows = await ai_results(conn, room["room_id"])
            roster = await roster_of(conn, room)
            entries = []
            for row in rows:
                if row["state"] != "normal":
                    entries.append({"result_id": str(row["result_id"]), "kind": row["kind"], "attempt": row["attempt"],
                                    "state": "failed", "created_at": iso(row["created_at"])})
                    continue
                entry = shared(row, room, roster, draft=room["selected_result_id"] != row["result_id"])
                base = await latest_edit(conn, row["result_id"]) or row
                entry.update({"attempt": row["attempt"], "state": "normal", "created_at": iso(row["created_at"]),
                              "editable": render.editable_segments(db.as_json(base["output"]), roster)})
                entries.append(entry)
        selected = room["selected_result_id"]
        return {"selected_result_id": str(selected) if selected else None, "results": entries}

    async def load_origin(conn, room, result_id):
        rid = parse_uuid(result_id)
        if rid is None:
            raise ApiError("not_found")
        cur = await conn.execute(
            "SELECT * FROM results WHERE result_id = %s AND room_id = %s AND kind = 'ai_original'", (rid, room["room_id"]))
        row = await cur.fetchone()
        if row is None:
            raise ApiError("not_found")
        return row

    # 10. 결과 선택
    @app.post("/api/rooms/{room_code}/results/{result_id}/select")
    async def select_result(room_code: str, result_id: str, request: Request):
        pending = []
        async with pool().transaction() as conn:
            room = await load_room(conn, room_code, for_update=True)
            require_host(room, request)
            row = await load_origin(conn, room, result_id)
            if row["state"] != "normal":
                raise ApiError("invalid_state")
            first = room["selected_result_id"] is None
            await conn.execute("UPDATE rooms SET selected_result_id = %s WHERE room_id = %s",
                               (row["result_id"], room["room_id"]))
            if first:
                pending = await notifier.enqueue(conn, room["room_id"], "selected")
        if pending:
            await notifier.deliver(room_code, "selected", pending)
        log("result_selected", room_code=room_code)
        return {"selected_result_id": str(row["result_id"])}

    # 11. 방장 편집
    @app.post("/api/rooms/{room_code}/results/{result_id}/edits", status_code=201)
    async def edit_result(room_code: str, result_id: str, request: Request):
        body = await read_json(request)
        edits = body.get("edits") if isinstance(body, dict) else None
        if not isinstance(edits, list) or not edits:
            raise ApiError("edit_not_allowed")
        now = clock()
        async with pool().transaction() as conn:
            room = await load_room(conn, room_code, for_update=True)
            require_host(room, request)
            origin = await load_origin(conn, room, result_id)
            if origin["state"] != "normal":
                raise ApiError("invalid_state")
            base = await latest_edit(conn, origin["result_id"]) or origin
            output = copy.deepcopy(db.as_json(base["output"]))
            roster = await roster_of(conn, room)
            known = {r["participant_id"] for r in roster}
            sentences = dict(render.editable_paths(output))
            new_texts = []
            for edit in edits:
                if not isinstance(edit, dict):
                    raise ApiError("edit_not_allowed")
                path, text = edit.get("path"), edit.get("text")
                if path not in sentences or not isinstance(text, str) or text.strip() == "":
                    raise ApiError("edit_not_allowed")
                old_tokens = sorted(render.participant_tokens(sentences[path]))
                new_tokens = sorted(render.participant_tokens(text))
                if old_tokens != new_tokens or any(t not in known for t in new_tokens):
                    raise ApiError("edit_not_allowed")
                try:
                    render.render_participant_tokens(text, roster)
                except render.RenderError:
                    raise ApiError("edit_not_allowed")
                new_texts.append((path, text))
            frozen = room["frozen_input"] or {}
            index = InputIndex(frozen.get("model_input"))
            probe = {"clauses": [{"action": text, "proposed_conditions": []} for _, text in new_texts]}
            if check_memo_quotes(index, probe):
                raise ApiError("memo_quote")
            for path, text in new_texts:
                render.set_sentence(output, path, text)
            new_id = uuid.uuid4()
            await conn.execute(
                "INSERT INTO results (result_id, room_id, attempt, attempt_id, state, kind, origin_result_id, "
                "source_result_id, output, created_at) VALUES (%s, %s, %s, %s, 'normal', 'host_edited', %s, %s, %s, %s)",
                (new_id, room["room_id"], origin["attempt"], origin["attempt_id"], origin["result_id"],
                 base["result_id"], db.jsonb(output), now))
            cur = await conn.execute("SELECT * FROM results WHERE result_id = %s", (new_id,))
            new_row = await cur.fetchone()
        log("result_edited", room_code=room_code)
        return shared(new_row, room, roster, draft=room["selected_result_id"] != origin["result_id"])

    # 12. 푸시
    @app.get("/api/push/vapid-public-key")
    async def vapid_public_key():
        return {"public_key": settings.vapid_public_key}

    def subscription_scope(body):
        if not isinstance(body, dict) or body.get("role") not in ("host", "participant"):
            raise ApiError("invalid_input")
        role = body["role"]
        session_id = parse_uuid(body["session_id"]) if body.get("session_id") is not None else None
        if role == "participant" and session_id is None:
            raise ApiError("invalid_input")  # 참여자 구독은 세션과 묶는다(결정 11·44)
        return role, session_id

    async def require_subscription_access(conn, room_code, request, role, session_id):
        room = await load_room(conn, room_code)
        if role == "host":
            require_host(room, request)
        if session_id is not None:
            cur = await conn.execute("SELECT 1 FROM sessions WHERE session_id = %s AND room_id = %s",
                                     (session_id, room["room_id"]))
            if await cur.fetchone() is None:
                raise ApiError("not_found")
        return room

    def endpoint_scope(body):
        role, session_id = subscription_scope(body)
        endpoint = body.get("endpoint")
        if not endpoint_allowed(endpoint, settings.push_allowed_hosts):
            raise ApiError("invalid_input")
        return role, session_id, endpoint

    @app.post("/api/rooms/{room_code}/push-subscriptions/status")
    async def subscription_status(room_code: str, request: Request):
        role, session_id, endpoint = endpoint_scope(await read_json(request))
        async with pool().connection() as conn:
            room = await require_subscription_access(conn, room_code, request, role, session_id)
            cur = await conn.execute(
                "SELECT EXISTS (SELECT 1 FROM push_subscriptions WHERE room_id = %s AND role = %s "
                "AND session_id IS NOT DISTINCT FROM %s AND endpoint = %s) AS subscribed, "
                "EXISTS (SELECT 1 FROM push_subscriptions WHERE room_id = %s AND endpoint = %s) AS room_subscribed",
                (room["room_id"], role, session_id, endpoint, room["room_id"], endpoint))
            row = await cur.fetchone()
        return {"subscribed": row["subscribed"], "room_subscribed": row["room_subscribed"]}

    @app.delete("/api/rooms/{room_code}/push-subscriptions", status_code=204)
    async def unsubscribe(room_code: str, request: Request):
        role, session_id, endpoint = endpoint_scope(await read_json(request))
        async with pool().transaction() as conn:
            room = await require_subscription_access(conn, room_code, request, role, session_id)
            # 브라우저의 같은 endpoint를 쓰는 이 방의 다른 역할·세션도 함께 해제한다.
            await conn.execute("DELETE FROM push_subscriptions WHERE room_id = %s AND endpoint = %s",
                               (room["room_id"], endpoint))
        return Response(status_code=204)

    @app.post("/api/rooms/{room_code}/push-subscriptions", status_code=201)
    async def subscribe(room_code: str, request: Request):
        body = await read_json(request)
        role, session_id = subscription_scope(body)
        subscription = body.get("subscription")
        if not isinstance(subscription, dict):
            raise ApiError("invalid_input")
        if not endpoint_allowed(subscription.get("endpoint"), settings.push_allowed_hosts):
            raise ApiError("invalid_input")
        keys = subscription.get("keys")
        if keys is not None and not isinstance(keys, dict):
            raise ApiError("invalid_input")
        now = clock()
        async with pool().transaction() as conn:
            room = await require_subscription_access(conn, room_code, request, role, session_id)
            # 같은 방·역할·세션·endpoint는 한 구독이다. 다시 등록하면 키만 새 값으로 바꾼다.
            cur = await conn.execute(
                "INSERT INTO push_subscriptions (subscription_id, room_id, role, session_id, endpoint, keys, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (room_id, role, session_id, endpoint) DO UPDATE SET keys = EXCLUDED.keys "
                "RETURNING subscription_id, (xmax = 0) AS created",
                (uuid.uuid4(), room["room_id"], role, session_id, subscription["endpoint"],
                 db.jsonb(keys) if keys is not None else None, now))
            row = await cur.fetchone()
        return JSONResponse(status_code=201 if row["created"] else 200,
                            content={"subscription_id": str(row["subscription_id"])})

    @app.get("/api/health")
    async def health():
        return {"status": "ok"}
