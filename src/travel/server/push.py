"""Web Push 알림(F6, AC18, SPEC 알림 정책).

이벤트 이름이 대상과 중복 방지의 열쇠다.
  ready:<시도 번호>   생성 성공. 방장 구독. 첫 정상 결과일 때만 보낸다(재생성 성공은 알리지 않는다).
  failed:<시도 번호>  생성 실패. 방장 구독. 정상 결과가 없을 때만 보낸다(완료·실패를 묶은 알림 1건).
  selected           방장의 첫 결과 선택. 참여자 구독. 재선택·수정 때는 보내지 않는다.
알림 행은 (subscription_id, event) 유일 제약으로 한 번만 만들어지고, 새로 만든 행만 발송한다.
그래서 dispatch(room_code, event)를 두 번 불러도 다시 보내지 않는다.
본문은 키가 text(상태 문구)와 url(방 링크) 둘인 JSON 객체다. 이름·메모·선택지 문구를 넣지 않는다(결정 25).
410·404는 구독을 지우고, 그 밖의 실패는 상태 코드만 기록한다. 재발송은 하지 않는다.
구독 주소는 사용자가 보내는 값이라 서버가 그 주소로 요청을 보내면 내부망 접근 통로가 된다. 그래서 등록과 발송 두 곳에서
endpoint_allowed로 검사한다. 발송 때 다시 보는 이유는 제한을 넣기 전에 저장된 구독이 있기 때문이다.
"""

import asyncio
from urllib.parse import urlsplit

from . import db
from .logging import log

# 처리방침 제5조의 브라우저 제공사(Google, Mozilla, Apple)와 같다. "*."는 하위 도메인만 뜻하고 기준 호스트 자체는 뺀다.
DEFAULT_PUSH_HOSTS = ("fcm.googleapis.com", "*.push.services.mozilla.com", "*.push.apple.com")
ENDPOINT_MAX_LENGTH = 2048

TEXTS = {
    "ready": "협약서가 준비됐어요. 방에서 확인해 주세요.",
    "failed": "응답은 모두 모였지만 협약서 생성에 실패했어요. 방장 화면에서 다시 시도해 주세요.",
    "selected": "방장이 협약서 결과를 골랐어요. 방에서 확인해 주세요.",
}
EXPIRED_STATUSES = (404, 410)


def host_allowed(host, allowed_hosts):
    """정확한 일치 또는 점 경계의 하위 도메인만 받는다."""
    for rule in allowed_hosts:
        if rule.startswith("*."):
            suffix = rule[1:]
            if host.endswith(suffix) and len(host) > len(suffix):
                return True
        elif host == rule:
            return True
    return False


def endpoint_allowed(endpoint, allowed_hosts):
    """HTTPS, 포트 443, userinfo 없음, 허용 호스트인 주소만 참이다. 내부·루프백 주소와 IP 표기는 허용 목록에 없어 함께 막힌다."""
    if not isinstance(endpoint, str) or len(endpoint) > ENDPOINT_MAX_LENGTH or not endpoint.isascii():
        return False
    # urlsplit은 탭·개행을 지우고, 브라우저와 파서는 역슬래시를 다르게 읽는다. 해석 차이가 생기기 전에 거절한다.
    if "\\" in endpoint or any(ch <= " " or ch == "\x7f" for ch in endpoint):
        return False
    try:
        parts = urlsplit(endpoint)
        port = parts.port
    except ValueError:
        return False
    if parts.scheme != "https" or parts.username is not None or parts.password is not None:
        return False
    if port not in (None, 443) or "@" in parts.netloc:
        return False
    host = parts.hostname
    return bool(host) and host_allowed(host, allowed_hosts)


def event_kind(event):
    return event.split(":", 1)[0]


def roles_for(event):
    kind = event_kind(event)
    if kind in ("ready", "failed"):
        return ("host",)
    if kind == "selected":
        return ("participant",)
    return ()


class Notifier:
    def __init__(self, sender, settings, clock):
        self.sender = sender
        self.settings = settings
        self.clock = clock
        self.pool = None

    def payload(self, room_code, event):
        return {"text": TEXTS[event_kind(event)], "url": f"{self.settings.public_base_url}/r/{room_code}"}

    async def enqueue(self, conn, room_id, event):
        """호출자의 트랜잭션 안에서 알림 행을 만들고 발송 대상만 돌려준다."""
        roles = roles_for(event)
        if not roles:
            return []
        return await db.enqueue_notifications(conn, room_id, event, roles, self.clock())

    async def deliver(self, room_code, event, pending):
        """커밋 뒤에 보낸다. 실패해도 예외를 내지 않는다."""
        if not pending:
            return
        payload = self.payload(room_code, event)
        # 동시에 보낸다. 순서대로 보내면 응답 없는 구독 하나가 timeout만큼 나머지와 호출자(결과 선택 요청)를 붙잡는다.
        await asyncio.gather(*(self._deliver_one(room_code, event, item, payload) for item in pending))

    async def _deliver_one(self, room_code, event, item, payload):
        subscription = {"endpoint": item["endpoint"], "keys": item["keys"]}
        if not endpoint_allowed(item["endpoint"], self.settings.push_allowed_hosts):
            log("push_blocked", room_code=room_code, push_event=event)  # 주소는 로그에 쓰지 않는다
            status = 0
        else:
            try:
                # enqueue 이후 방/구독이 삭제되거나 이미 발송된 알림이면 건너뛴다.
                # 발송기에 넘긴 뒤 진행 중인 요청까지 취소하지는 않는다.
                async with self.pool.connection() as conn:
                    cur = await conn.execute(
                        "SELECT 1 FROM notifications n JOIN push_subscriptions s "
                        "ON s.subscription_id = n.subscription_id "
                        "WHERE n.notification_id = %s AND s.subscription_id = %s AND n.sent_at IS NULL",
                        (item["notification_id"], item["subscription_id"]))
                    if await cur.fetchone() is None:
                        return
                status = await asyncio.to_thread(self.sender.send, subscription, payload)
            except Exception as exc:  # 발송기 오류는 기록만 한다
                log("push_error", room_code=room_code, push_event=event, error=type(exc).__name__)
                status = 0
        try:
            async with self.pool.transaction() as conn:
                await conn.execute(
                    "UPDATE notifications SET status_code = %s, sent_at = %s WHERE notification_id = %s",
                    (status, self.clock(), item["notification_id"]))
                if status in EXPIRED_STATUSES:
                    await conn.execute("DELETE FROM push_subscriptions WHERE subscription_id = %s",
                                       (item["subscription_id"],))
        except Exception as exc:
            log("push_record_error", room_code=room_code, push_event=event, error=type(exc).__name__)
        log("push_sent", room_code=room_code, push_event=event, status=status)

    async def dispatch(self, room_code, event):
        """이벤트를 다시 처리한다. 이미 보낸 구독에는 다시 보내지 않는다."""
        async with self.pool.transaction() as conn:
            room = await db.fetch_room_by_code(conn, room_code)
            if room is None:
                return
            pending = await self.enqueue(conn, room["room_id"], event)
        await self.deliver(room_code, event, pending)
