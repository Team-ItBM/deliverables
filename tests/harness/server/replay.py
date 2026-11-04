"""저장 출력 재생 클라이언트(§0-E 1·2).

서버의 모델 호출 경계 `await llm_client.generate(stage, model_input, repair_errors=None) -> LLMResult`를 구현한다.
단계(scenarios, pact)마다 대기열이 있고, 호출될 때마다 그 단계의 항목을 하나씩 꺼낸다.
받은 stage·model_input·repair_errors와 돌려준 출력은 모두 calls에 기록한다.
대기열이 비었는데 호출되면 failures에 남기고 예외를 낸다. conftest는 테스트가 끝날 때 failures가 비었는지 확인한다.

항목 종류
  Text(raw_output, response_status="completed")  고정 문자열. response_status로 incomplete·refusal을 지정한다.
  CallError(kind, retry_after=None)              서버의 LLMCallError(kind, retry_after)를 낸다.
  Produce(fn)                                    fn(model_input)이 돌려준 문자열(또는 다른 항목)을 쓴다.
  Hold(item)                                     release()를 부를 때까지 응답하지 않다가 item을 돌려준다.
"""

import asyncio
import copy
import json
import threading
from collections import deque
from dataclasses import dataclass, field

STAGES = ("scenarios", "pact")


class ReplayQueueEmpty(RuntimeError):
    """대기열이 빈 단계가 호출됐다."""


@dataclass
class Text:
    raw_output: str
    response_status: str = "completed"


@dataclass
class CallError:
    kind: str
    retry_after: float | None = None


@dataclass
class Produce:
    fn: object
    label: str = ""


class Hold:
    """호출을 붙잡아 두었다가 release()로 풀어 준다. 이벤트 루프가 다른 스레드에 있어도 풀 수 있다."""

    def __init__(self, item):
        self.item = item
        self.started = threading.Event()
        self._released = threading.Event()
        self._mutex = threading.Lock()
        self._loop = None
        self._event = None

    async def wait(self):
        loop = asyncio.get_running_loop()
        event = asyncio.Event()
        with self._mutex:
            self._loop, self._event = loop, event
            already = self._released.is_set()
        self.started.set()
        if not already:
            await event.wait()
        return self.item

    def wait_started(self, timeout=10):
        if not self.started.wait(timeout):
            raise AssertionError(f"붙잡은 호출이 {timeout}초 안에 시작되지 않았다")

    def release(self, item=None):
        with self._mutex:
            if item is not None:
                self.item = item
            self._released.set()
            loop, event = self._loop, self._event
        if loop is not None and not loop.is_closed():
            try:
                loop.call_soon_threadsafe(event.set)
            except RuntimeError:
                pass

    @property
    def released(self):
        return self._released.is_set()


@dataclass
class Call:
    stage: str
    model_input: object
    repair_errors: object
    raw_output: str | None = None
    response_status: str | None = None
    error: tuple | None = None
    item: object = field(default=None, repr=False)


class _StandInResult:
    def __init__(self, raw_output, response_status):
        self.raw_output = raw_output
        self.response_status = response_status


class _StandInError(Exception):
    def __init__(self, kind, retry_after=None):
        super().__init__(kind)
        self.kind = kind
        self.retry_after = retry_after


def _snapshot(value):
    try:
        return json.loads(json.dumps(value, ensure_ascii=False))
    except (TypeError, ValueError):
        return copy.deepcopy(value)


class ReplayClient:
    """result_factory(raw_output=, response_status=)와 error_factory(kind, retry_after)는 서버 llm.py의 클래스를 넘긴다.
    넘기지 않으면 도우미 검사용 대체 클래스를 쓴다."""

    def __init__(self, result_factory=None, error_factory=None):
        self.result_factory = result_factory or _StandInResult
        self.error_factory = error_factory or _StandInError
        self.queues = {stage: deque() for stage in STAGES}
        self.calls = []
        self.failures = []
        self.holds = []
        self.closed = False
        self._lock = threading.Lock()

    # 대기열
    def push(self, stage, *items):
        if stage not in self.queues:
            raise ValueError(f"모르는 단계 {stage}")
        with self._lock:
            for item in items:
                if isinstance(item, str):
                    item = Text(item)
                if isinstance(item, Hold):
                    self.holds.append(item)
                self.queues[stage].append(item)

    def hold(self, stage, item):
        handle = Hold(item)
        self.push(stage, handle)
        return handle

    def pending(self, stage):
        with self._lock:
            return len(self.queues[stage])

    # 기록 조회
    def calls_for(self, stage):
        with self._lock:
            return [c for c in self.calls if c.stage == stage]

    def count(self, stage):
        return len(self.calls_for(stage))

    def counts(self):
        return {stage: self.count(stage) for stage in STAGES}

    # 정리
    def close(self):
        """남은 Hold를 풀고, 이후 호출은 기록 없이 호출 오류로 끝낸다(테스트 종료 정리용)."""
        with self._lock:
            self.closed = True
            holds = list(self.holds)
        for handle in holds:
            if not handle.released:
                handle.release(CallError("server_error"))

    async def generate(self, stage, model_input, repair_errors=None):
        with self._lock:
            if self.closed:
                raise self.error_factory("server_error", None)
            record = Call(stage=stage, model_input=_snapshot(model_input), repair_errors=_snapshot(repair_errors))
            self.calls.append(record)
            queue = self.queues.get(stage)
            if not queue:
                message = f"재생 대기열이 빈 단계 {stage!r}가 호출됐다(호출 {len(self.calls)}번째)"
                self.failures.append(message)
                raise ReplayQueueEmpty(message)
            item = queue.popleft()
        record.item = item
        if isinstance(item, Hold):
            item = await item.wait()
        while isinstance(item, Produce):
            item = item.fn(copy.deepcopy(record.model_input))
            if isinstance(item, str):
                item = Text(item)
        if isinstance(item, CallError):
            record.error = (item.kind, item.retry_after)
            raise self.error_factory(item.kind, item.retry_after)
        if not isinstance(item, Text):
            message = f"재생 항목 형식 오류: {type(item).__name__}"
            self.failures.append(message)
            raise ReplayQueueEmpty(message)
        record.raw_output = item.raw_output
        record.response_status = item.response_status
        return self.result_factory(raw_output=item.raw_output, response_status=item.response_status)
