"""구조화 로그(ARCHITECTURE 8절).

JSON lines를 표준 출력으로 낸다. 메모 원문, 이름·별명, 선택 프로필(성별·나이대·MBTI), 모델 입출력 원문은
어떤 로그에도 넣지 않는다. 식별자(방 코드, 시도 ID, 응답 상태, 오류 코드)만 쓴다.
접속 로그는 요청마다 IP 주소, 시각, 요청 경로, 응답 상태만 남기고 User-Agent는 남기지 않는다(2026-11-05 결정).

접속 IP는 믿을 수 있는 구간이 쓴 값만 쓴다. 운영 경로는 사용자 → CloudFront → ALB → 앱이다. CloudFront가 사용자 주소를,
ALB가 CloudFront 엣지 주소를 X-Forwarded-For 끝에 붙이므로(ALB 기본 append 모드) 앞쪽 값은 사용자가 위조할 수 있다.
그래서 믿는 프록시가 2단(TRUSTED_PROXY_HOPS=2)이면 오른쪽에서 두 번째 값이 실제 사용자 주소다.
항목이 모자라거나 IP가 아니면 프록시 구성이 예상과 다른 것이므로 연결 주소를 쓴다.
"""

import ipaddress
import json
import sys
from datetime import datetime, timezone


def log(event, **fields):
    record = {"ts": datetime.now(timezone.utc).isoformat(), "event": event}
    for key, value in fields.items():
        record[key] = value if isinstance(value, (str, int, float, bool, type(None), list, dict)) else str(value)
    sys.stdout.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    sys.stdout.flush()


def client_ip(scope, trusted_proxy_hops=0):
    client = scope.get("client")
    peer = client[0] if client else None
    if trusted_proxy_hops <= 0:
        return peer
    values = [v.decode("latin-1") for k, v in scope.get("headers") or [] if k == b"x-forwarded-for"]
    entries = [e.strip() for e in ",".join(values).split(",") if e.strip()]
    if len(entries) < trusted_proxy_hops:
        return peer
    candidate = entries[-trusted_proxy_hops]
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return peer
    return candidate


class AccessLogMiddleware:
    """순수 ASGI 미들웨어. BaseHTTPMiddleware는 백그라운드 태스크와 얽혀 쓰지 않는다."""

    def __init__(self, app, enabled=True, trusted_proxy_hops=0):
        self.app = app
        self.enabled = enabled
        self.trusted_proxy_hops = trusted_proxy_hops

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
            log("access", ip=client_ip(scope, self.trusted_proxy_hops), path=scope.get("path"), method=scope.get("method"),
                status=status_holder.get("status"))
