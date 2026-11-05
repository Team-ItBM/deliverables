"""구조화 로그(ARCHITECTURE 8절).

JSON lines를 표준 출력으로 낸다. 메모 원문, 이름·별명, 선택 프로필(성별·나이대·MBTI), 모델 입출력 원문은
어떤 로그에도 넣지 않는다. 식별자(방 코드, 시도 ID, 응답 상태, 오류 코드)만 쓴다.
접속 로그는 요청마다 IP 주소, 시각, 요청 경로, 응답 상태만 남기고 User-Agent는 남기지 않는다(2026-11-05 결정).
"""

import json
import sys
from datetime import datetime, timezone


def log(event, **fields):
    record = {"ts": datetime.now(timezone.utc).isoformat(), "event": event}
    for key, value in fields.items():
        record[key] = value if isinstance(value, (str, int, float, bool, type(None), list, dict)) else str(value)
    sys.stdout.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


class AccessLogMiddleware:
    """순수 ASGI 미들웨어. BaseHTTPMiddleware는 백그라운드 태스크와 얽혀 쓰지 않는다."""

    def __init__(self, app, enabled=True):
        self.app = app
        self.enabled = enabled

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not self.enabled:
            await self.app(scope, receive, send)
            return
        status_holder = {}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["status"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            client = scope.get("client")
            log("access", ip=client[0] if client else None, path=scope.get("path"), method=scope.get("method"),
                status=status_holder.get("status"))
