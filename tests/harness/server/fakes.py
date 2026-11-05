"""가짜 푸시 발송기(§0-E 6), 가짜 대기 함수와 현재 시각 함수(§0-E 4)."""

import asyncio
import json
import threading
from datetime import datetime, timedelta, timezone

START = datetime(2026, 11, 5, 0, 0, 0, tzinfo=timezone.utc)


def _endpoint(subscription):
    if isinstance(subscription, dict):
        return subscription.get("endpoint")
    return getattr(subscription, "endpoint", None)


def payload_object(payload):
    """본문을 JSON 객체로 읽는다. 객체가 아니면 None이다."""
    if isinstance(payload, dict):
        return payload
    try:
        value = json.loads(payload_text(payload))
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def payload_text(payload):
    if isinstance(payload, (bytes, bytearray)):
        return payload.decode("utf-8", errors="replace")
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, default=str)


class FakePushSender:
    """send(subscription, payload) -> status_code. 보낸 구독 endpoint와 본문을 기록한다.
    status_by_endpoint에 지정한 endpoint에는 그 상태(404·410·500)를, 나머지에는 201을 돌려준다."""

    def __init__(self):
        self.sent = []
        self.status_by_endpoint = {}
        self._lock = threading.Lock()

    def send(self, subscription, payload):
        endpoint = _endpoint(subscription)
        with self._lock:
            self.sent.append({"endpoint": endpoint, "payload": payload, "text": payload_text(payload),
                              "object": payload_object(payload)})
            return self.status_by_endpoint.get(endpoint, 201)

    def count(self):
        with self._lock:
            return len(self.sent)

    def since(self, mark):
        with self._lock:
            return list(self.sent[mark:])


class FakeSleeper:
    """await sleeper(seconds). 실제로 기다리지 않고 초를 기록한다."""

    def __init__(self):
        self.waits = []
        self._lock = threading.Lock()

    async def __call__(self, seconds):
        with self._lock:
            self.waits.append(seconds)
        await asyncio.sleep(0)

    def since(self, mark):
        with self._lock:
            return list(self.waits[mark:])

    def mark(self):
        with self._lock:
            return len(self.waits)


class FakeClock:
    """clock() -> 시간대가 있는 UTC datetime. 테스트가 옮기기 전까지 멈춰 있다."""

    def __init__(self, start=START):
        self.start = start
        self.now = start
        self._lock = threading.Lock()

    def __call__(self):
        with self._lock:
            return self.now

    def set(self, moment):
        with self._lock:
            self.now = moment

    def set_after(self, base, seconds):
        self.set(base + timedelta(seconds=seconds))
