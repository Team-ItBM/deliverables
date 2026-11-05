"""백그라운드 생성 작업(문항·추천)과 재시도·재요청·한도·멈춤 판정(ARCHITECTURE 5·6절, AC10, AC4, AC17).

- 작업은 추적되는 asyncio 태스크다. `join()`은 모두 끝날 때까지 기다린다.
- 모델 호출 한 번은 일시 오류(timeout, rate_limited, server_error)에 최대 2회 재시도한다. 대기는 1초·2초에 더하기 지터,
  rate_limited에 Retry-After가 있으면 그 값이다. 재시도 대기에만 sleeper를 쓴다.
- 출력 형식·후처리 오류와 incomplete·refusal은 검증기 오류를 붙여 1회 재요청한다. 다시 실패하면 output_invalid다.
- 작업 한도(기본 300초)와 멈춤 판정(기본 600초)은 generating 전환 시각부터 clock()으로 잰다. 한도는 진행 중인 호출을 끊고
  failed(call_error)로, 멈춤 판정은 다른 앱에서도 failed(interrupted)로 돌린다. 둘 다 정각(>=)에 적용한다
  (하니스 OUT-N05·N06 기준. 결정 12의 "넘으면"과 다르며 기대값을 따른다).
- 취소는 작업 태스크를 취소하지 않고 작업의 stop 이벤트와 모델 호출 태스크 취소로 한다. DB 쓰기는 끊기지 않는다.
- 시도 종료 쓰기는 db.finish_attempt가 현재 시도·generating을 확인한다. 늦은 결과는 버린다(결정 30).
- 문항 작업도 같은 규칙을 따른다. 작업 한도와 멈춤 판정은 시작 시각(scenario_started_at)부터 재서 scenario_status를 failed로
  돌리고, db.finish_scenarios가 현재 시도·preparing을 확인한다. 실패한 문항은 방장이 POST /retry로 다시 시도하거나 새 방을 만든다.
- 두 번째 이후 호출 전에는 현재 시도인지 확인해, 끝난 시도가 모델을 더 부르지 않게 한다.
- llm_calls는 generate 한 번에 한 행이다. 성공 행은 검증 뒤에 써서 output_status·violation_codes를 함께 남긴다.
  사용량은 UsageMeter로 모아, 실패·타임아웃·중단 때도 응답받은 왕복의 비용을 쓴다. usage_status로 구분한다:
  reported(전부 앎), partial(일부만 앎), unknown(모름), not_called(호출 전 한도로 막힘). 한도는 cost_usd 합만 본다.
"""

import asyncio
import contextlib
import hashlib
import json
import random
from dataclasses import dataclass, field

from travel.pact import validate_pact_output
from travel.scenarios import validate_scenario_output

from . import db
from .llm import LLMCallError, UsageMeter, current_meter
from .logging import log

PLACEHOLDER_NAME = "친구"
# llm_calls.output_status에는 스키마의 값만 쓴다. 모델이 낸 임의 문자열을 표에 옮기지 않는다.
OUTPUT_STATUSES = {
    "scenarios": ("ready", "needs_information", "unsupported", "invalid_input"),
    "pact": ("proposed", "conditional_only", "needs_information", "unresolved", "unsupported", "invalid_input"),
}


class JobStopped(Exception):
    pass


@dataclass
class Job:
    kind: str
    room_id: object
    room_code: str
    attempt_id: object = None
    attempt_no: int = 0
    generating_since: object = None
    stop: asyncio.Event = field(default_factory=asyncio.Event)
    stop_reason: str = None
    task: asyncio.Task = None


def input_hash(model_input):
    return hashlib.sha256(json.dumps(model_input, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def output_status_of(stage, raw_output):
    try:
        status = json.loads(raw_output).get("status")
    except (ValueError, TypeError, AttributeError):
        return None
    return status if isinstance(status, str) and status in OUTPUT_STATUSES[stage] else None


def placeholder_profiles(profiles):
    """문항 모델 입력의 display_name을 배열 순서대로 친구1, 친구2…로 바꾼다. 다른 키는 그대로 둔다(결정 36)."""
    out = []
    for i, profile in enumerate(profiles):
        item = dict(profile)
        item["display_name"] = f"{PLACEHOLDER_NAME}{i + 1}"
        out.append(item)
    return out


class JobManager:
    def __init__(self, settings, llm_client, sleeper, clock, notifier, pool_source):
        self.settings = settings
        self.llm = llm_client
        self.sleeper = sleeper
        self.clock = clock
        self.notifier = notifier
        self.pool_source = pool_source  # ScenarioPool (목록·원본·버전)
        self.db = None  # lifespan 시작 때 Pool을 받는다
        self.jobs = {}
        self.errors = []
        self._semaphore = None
        self._stopping = False

    def bind(self, db_pool):
        self.db = db_pool
        self._semaphore = asyncio.Semaphore(self.settings.max_concurrent_generations)

    # ---- 시작

    def start_scenarios(self, room_id, room_code, attempt_id, attempt_no, started_at):
        job = Job("scenarios", room_id, room_code, attempt_id, attempt_no, started_at)
        self._launch(attempt_id, job, self._run_scenarios(job))

    def start_pact(self, room_id, room_code, attempt_id, attempt_no, generating_since):
        job = Job("pact", room_id, room_code, attempt_id, attempt_no, generating_since)
        self._launch(attempt_id, job, self._run_pact(job))

    def _launch(self, key, job, coro):
        job.task = asyncio.create_task(coro, name=f"{job.kind}:{job.room_code}:{job.attempt_no}")
        self.jobs[key] = job
        job.task.add_done_callback(lambda _t: self.jobs.pop(key, None))

    # ---- 진입점

    async def join(self):
        while True:
            pending = {j.task for j in list(self.jobs.values()) if j.task is not None and not j.task.done()}
            if not pending:
                break
            await asyncio.wait(pending)
        if self.errors:
            raise self.errors.pop(0)

    async def enforce_deadlines(self):
        now = self.clock()
        limit = self.settings.job_time_limit_seconds
        for job in list(self.jobs.values()):
            if job.task.done() or job.generating_since is None:
                continue
            if (now - job.generating_since).total_seconds() < limit:
                continue
            if job.kind == "scenarios":
                await self._finish_scenarios(job, "failed", None, None)
                job.stop_reason = "deadline"
                job.stop.set()
                continue
            pending, before = await self._finish(job, ("failed", "call_error"))
            job.stop_reason = "deadline"
            job.stop.set()
            if pending is not None and before == 0:
                await self.notifier.deliver(job.room_code, f"failed:{job.attempt_no}", pending)

    async def recover_stalled(self):
        now = self.clock()
        limit = self.settings.stall_limit_seconds
        deliveries = []
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                "SELECT room_id, room_code, current_attempt_id, attempt_count, generating_since FROM rooms "
                "WHERE status = 'generating' AND generating_since IS NOT NULL FOR UPDATE SKIP LOCKED")
            rows = await cur.fetchall()
            for row in rows:
                if (now - row["generating_since"]).total_seconds() < limit:
                    continue
                try:
                    _, before = await db.finish_attempt(conn, row["room_id"], row["current_attempt_id"],
                                                        row["attempt_count"], ("failed", "interrupted"), now)
                except db.StaleAttempt:
                    continue
                log("job_interrupted", room_code=row["room_code"], attempt=row["attempt_count"])
                if before == 0:
                    pending = await self.notifier.enqueue(conn, row["room_id"], f"failed:{row['attempt_count']}")
                    deliveries.append((row["room_code"], f"failed:{row['attempt_count']}", pending))
        for room_code, event, pending in deliveries:
            await self.notifier.deliver(room_code, event, pending)
        await self._recover_stalled_scenarios(now, limit)

    async def _recover_stalled_scenarios(self, now, limit):
        """작업 없이 preparing에 남은 방(문항 호출 중 서버 재시작)을 failed로 돌린다. 시작 시각이 없는 옛 방은 생성 시각으로 잰다."""
        async with self.db.transaction() as conn:
            cur = await conn.execute(
                "SELECT room_id, room_code, scenario_attempt_id, coalesce(scenario_started_at, created_at) AS since "
                "FROM rooms WHERE status = 'open' AND scenario_status = 'preparing' FOR UPDATE SKIP LOCKED")
            for row in await cur.fetchall():
                if (now - row["since"]).total_seconds() < limit:
                    continue
                await db.finish_scenarios(conn, row["room_id"], row["scenario_attempt_id"], "failed", None, None)
                log("scenario_interrupted", room_code=row["room_code"])

    async def shutdown(self):
        self._stopping = True
        for job in list(self.jobs.values()):
            job.stop_reason = "shutdown"
            job.stop.set()
        pending = {j.task for j in list(self.jobs.values()) if j.task and not j.task.done()}
        if pending:
            await asyncio.wait(pending, timeout=5)

    # ---- 모델 호출

    async def _llm(self, job, stage, model_input, repair_errors, meter):
        token = current_meter.set(meter)  # 태스크가 지금 컨텍스트를 복사하므로 만든 뒤 바로 되돌린다
        call = asyncio.ensure_future(self.llm.generate(stage, model_input, repair_errors=repair_errors))
        current_meter.reset(token)
        stop = asyncio.ensure_future(job.stop.wait())
        timeout = self.settings.llm_timeout_seconds or None
        try:
            done, _ = await asyncio.wait({call, stop}, return_when=asyncio.FIRST_COMPLETED, timeout=timeout)
        except BaseException:
            call.cancel()
            stop.cancel()
            raise
        if call not in done:
            call.cancel()
            with contextlib.suppress(BaseException):
                await call
            stop.cancel()
            if stop in done:
                raise JobStopped(job.stop_reason)
            raise LLMCallError("timeout", None)
        stop.cancel()
        return call.result()

    async def _assert_current(self, job):
        if job.stop.is_set():
            raise JobStopped(job.stop_reason)
        if job.kind == "pact":
            sql = "SELECT 1 FROM rooms WHERE room_id = %s AND current_attempt_id = %s AND status = 'generating'"
        else:
            sql = "SELECT 1 FROM rooms WHERE room_id = %s AND scenario_attempt_id = %s AND scenario_status = 'preparing'"
        async with self.db.connection() as conn:
            cur = await conn.execute(sql, (job.room_id, job.attempt_id))
            if await cur.fetchone() is None:
                raise JobStopped("stale")

    async def _check_room_cap(self, job):
        """다음 모델 호출 전에 그 방의 llm_calls 비용 합을 보고, 상한에 닿았으면 budget_exceeded를 낸다(ARCHITECTURE 5절)."""
        cap = self.settings.room_cap_usd
        if cap is None:
            return
        async with self.db.connection() as conn:
            cur = await conn.execute("SELECT coalesce(sum(cost_usd), 0) AS total FROM llm_calls WHERE room_id = %s",
                                     (job.room_id,))
            total = float((await cur.fetchone())["total"])
        if total >= cap:
            log("budget_exceeded", scope="room", room_code=job.room_code, total_usd=total, cap_usd=cap)
            raise LLMCallError("budget_exceeded", None)

    async def _call_with_retries(self, job, stage, repair_errors, model_input, record):
        """성공하면 (결과, 검증 뒤 행을 쓰는 함수)를 돌려준다. 실패 행은 여기서 쓴다."""
        bases = list(self.settings.retry_backoff_seconds)
        for attempt in range(len(bases) + 1):
            started = self.clock()
            meter = UsageMeter()
            try:
                await self._check_room_cap(job)
                async with self._semaphore:
                    result = await self._llm(job, stage, model_input, repair_errors, meter)
            except LLMCallError as exc:
                await record(repair_errors, attempt, None, exc.kind, started, meter)
                if attempt == len(bases) or exc.kind == "budget_exceeded":
                    raise
                if exc.kind == "rate_limited" and exc.retry_after is not None:
                    wait = exc.retry_after
                else:
                    wait = bases[attempt] + random.uniform(0, self.settings.retry_jitter_seconds)
                if job.stop.is_set():
                    raise JobStopped(job.stop_reason)
                await self.sleeper(wait)
                await self._assert_current(job)
                continue
            except JobStopped:
                if meter.requests:
                    await record(repair_errors, attempt, None, "stopped", started, meter)
                raise
            except Exception:
                if meter.requests:
                    await record(repair_errors, attempt, None, "internal_error", started, meter)
                raise

            async def finish(output_status=None, violation_codes=None, unopened=None, attempt=attempt, started=started,
                             meter=meter, result=result):
                await record(repair_errors, attempt, result, None, started, meter, output_status, violation_codes, unopened)

            return result, finish, meter
        raise LLMCallError("server_error", None)  # 도달하지 않는다

    def _recorder(self, job, stage, model_input):
        digest = input_hash(model_input)

        async def record(repair_errors, retry_no, result, error_kind, started, meter, output_status=None,
                         violation_codes=None, unopened=None):
            now = self.clock()
            usage = getattr(result, "usage", None) or {}
            if meter.requests:
                tokens = {"input_tokens": meter.input_tokens, "output_tokens": meter.output_tokens,
                          "cost_usd": meter.cost_usd} if meter.reported else {}
                usage_status = meter.status
            else:
                tokens = usage
                usage_status = "not_called" if error_kind == "budget_exceeded" else ("reported" if usage else "unknown")
            row = {
                "room_id": job.room_id, "attempt_id": job.attempt_id, "stage": stage,
                "model": usage.get("model") or self.settings.model_id,
                "prompt_version": self.settings.prompt_versions.get(stage),
                "schema_version": self.settings.schema_versions.get(stage),
                "pool_version": str(self.pool_source.version) if stage == "scenarios" else None,
                "input_hash": digest, "repair": repair_errors is not None, "retry_no": retry_no,
                "response_status": getattr(result, "response_status", None), "output_status": output_status,
                "error_kind": error_kind,
                "violation_codes": db.jsonb(violation_codes) if violation_codes is not None else None,
                "tool_call_count": (usage.get("tool_calls", len(result.opened_template_ids or [])) if result else None),
                "unopened_selection": db.jsonb(unopened) if unopened is not None else None,
                "latency_ms": int((now - started).total_seconds() * 1000), "input_tokens": tokens.get("input_tokens"),
                "output_tokens": tokens.get("output_tokens"), "cost_usd": tokens.get("cost_usd"),
                "usage_status": usage_status, "created_at": now,
            }
            try:
                async with self.db.transaction() as conn:
                    await db.record_llm_call(conn, row)
            except Exception as exc:
                log("llm_call_record_error", room_code=job.room_code, error=type(exc).__name__)
        return record

    async def _generate(self, job, stage, model_input, validate):
        """최초 호출 + 재요청 1회. ("ready", output) 또는 ("failed", 이유)를 돌려준다."""
        record = self._recorder(job, stage, model_input)
        repair_errors = None
        for round_no in range(2):
            try:
                result, finish, meter = await self._call_with_retries(job, stage, repair_errors, model_input, record)
            except LLMCallError:
                return ("failed", "call_error")
            if result.response_status != "completed":
                repair_errors = [{"code": f"response_{result.response_status}", "path": "",
                                  "detail": "모델 응답이 완료되지 않았다"}]
                await finish(violation_codes=[repair_errors[0]["code"]])
            else:
                output_status = output_status_of(stage, result.raw_output)
                try:
                    verdict = validate(result.raw_output)
                except Exception:
                    await finish(output_status)
                    raise
                if verdict["valid"]:
                    output = json.loads(result.raw_output)
                    unopened = self._unopened(job, stage, result, output, meter)
                    await finish(output_status, [], unopened)
                    return ("ready", output)
                repair_errors = verdict["errors"]
                await finish(output_status, [e.get("code") for e in repair_errors if isinstance(e, dict)])
            codes = [e.get("code") for e in repair_errors if isinstance(e, dict)]
            log("output_invalid", room_code=job.room_code, stage=stage, round=round_no, codes=codes)
            if round_no == 0:
                await self._assert_current(job)
        return ("failed", "output_invalid")

    @staticmethod
    def _unopened(job, stage, result, output, meter):
        """도구로 열지 않고 고른 문항. 도구 루프를 돈 호출에만 값이 있다(재생 클라이언트는 None)."""
        if stage != "scenarios" or not meter.requests or not isinstance(output.get("scenarios"), list):
            return None
        opened = set(result.opened_template_ids or [])
        unopened = [s.get("template_id") for s in output["scenarios"] if s.get("template_id") not in opened]
        if unopened:
            log("unopened_selection", room_code=job.room_code, template_ids=unopened)
        return unopened

    # ---- 문항 작업

    async def _run_scenarios(self, job):
        try:
            async with self.db.connection() as conn:
                room = await db.fetch_room_by_id(conn, job.room_id)
                profiles = await db.fetch_profiles(conn, job.room_id)
            raw_profiles = []
            for p in profiles:
                item = {"profile_id": p["profile_id"], "display_name": p["display_name"]}
                for key in ("gender", "age_band", "mbti"):
                    if p[key] is not None:
                        item[key] = p[key]
                raw_profiles.append(item)
            base = {
                "trip": room["trip"],
                "participant_profiles": placeholder_profiles(raw_profiles),
                "requested_count": self.settings.scenario_requested_count,
                "request": self.settings.scenario_request,
            }
            model_input = dict(base, scenario_pool=self.pool_source.index())
            validation_input = dict(base, scenario_pool=self.pool_source.items())
            outcome = await self._generate(job, "scenarios", model_input,
                                           lambda raw: validate_scenario_output(validation_input, raw))
        except JobStopped:
            return
        except Exception as exc:
            self.errors.append(exc)
            log("scenario_job_error", room_code=job.room_code, error=type(exc).__name__)
            outcome = ("failed", "call_error")
        status, payload = outcome
        if status == "ready":
            scenario_status = payload["status"]
            scenario_set = self._with_core_constraints(payload) if payload.get("scenarios") else None
            notice = {k: payload[k] for k in ("message", "clarification_questions") if k in payload}
        else:
            scenario_status, scenario_set, notice = "failed", None, None
        await self._finish_scenarios(job, scenario_status, scenario_set, notice)

    def _with_core_constraints(self, payload):
        """코드가 문항을 확정한 뒤 core_constraints를 pool에서 조회해 함께 저장한다(SPEC 5절). 추천 입력에만 쓴다.
        검증을 통과한 template_id는 pool에 있다. 방이 열린 동안 pool이 바뀌어도 이 값을 쓴다."""
        scenarios = [dict(s, core_constraints=self.pool_source.lookup(s["template_id"]).get("core_constraints", []))
                     for s in payload["scenarios"]]
        return dict(payload, scenarios=scenarios)

    async def _finish_scenarios(self, job, scenario_status, scenario_set, notice):
        try:
            async with self.db.transaction() as conn:
                await db.finish_scenarios(conn, job.room_id, job.attempt_id, scenario_status, scenario_set, notice)
        except db.StaleAttempt:
            log("stale_scenario_attempt", room_code=job.room_code, attempt=job.attempt_no)
            return
        except Exception as exc:
            self.errors.append(exc)
            log("scenario_finish_error", room_code=job.room_code, error=type(exc).__name__)
            return
        log("scenarios_done", room_code=job.room_code, scenario_status=scenario_status)

    # ---- 추천 작업

    async def _run_pact(self, job):
        try:
            async with self.db.connection() as conn:
                room = await db.fetch_room_by_id(conn, job.room_id)
            frozen = room["frozen_input"]
            model_input = frozen["model_input"]
            outcome = await self._generate(job, "pact", model_input,
                                           lambda raw: validate_pact_output(model_input, raw))
        except JobStopped:
            return
        except Exception as exc:
            self.errors.append(exc)
            log("pact_job_error", room_code=job.room_code, error=type(exc).__name__)
            outcome = ("failed", "call_error")
        pending, before = await self._finish(job, outcome)
        if pending is None:
            return
        event = f"{'ready' if outcome[0] == 'ready' else 'failed'}:{job.attempt_no}"
        if before == 0:
            await self.notifier.deliver(job.room_code, event, pending)

    async def _finish(self, job, outcome):
        """시도 종료를 한 트랜잭션으로 쓴다. 늦은 시도면 (None, None)이다. 알림 행은 첫 정상 결과 전에만 만든다."""
        now = self.clock()
        try:
            async with self.db.transaction() as conn:
                _, before = await db.finish_attempt(conn, job.room_id, job.attempt_id, job.attempt_no, outcome, now)
                pending = []
                if before == 0:
                    event = f"{'ready' if outcome[0] == 'ready' else 'failed'}:{job.attempt_no}"
                    pending = await self.notifier.enqueue(conn, job.room_id, event)
        except db.StaleAttempt:
            log("stale_attempt", room_code=job.room_code, attempt=job.attempt_no)
            return None, None
        except Exception as exc:
            self.errors.append(exc)
            log("finish_error", room_code=job.room_code, error=type(exc).__name__)
            return None, None
        log("pact_done", room_code=job.room_code, attempt=job.attempt_no, status=outcome[0],
            reason=None if outcome[0] == "ready" else outcome[1])
        return pending, before
