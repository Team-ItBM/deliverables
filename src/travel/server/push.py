"""Web Push 알림(F6, AC18, SPEC 알림 정책).

이벤트 이름이 대상과 중복 방지의 열쇠다.
  ready:<시도 번호>   생성 성공. 방장 구독. 첫 정상 결과일 때만 보낸다(재생성 성공은 알리지 않는다).
  failed:<시도 번호>  생성 실패. 방장 구독. 정상 결과가 없을 때만 보낸다(완료·실패를 묶은 알림 1건).
  selected           방장의 첫 결과 선택. 참여자 구독. 재선택·수정 때는 보내지 않는다.
알림 행은 (subscription_id, event) 유일 제약으로 한 번만 만들어지고, 새로 만든 행만 발송한다.
그래서 dispatch(room_code, event)를 두 번 불러도 다시 보내지 않는다.
본문은 키가 text(상태 문구)와 url(방 링크) 둘인 JSON 객체다. 이름·메모·선택지 문구를 넣지 않는다(결정 25).
410·404는 구독을 지우고, 그 밖의 실패는 상태 코드만 기록한다. 재발송은 하지 않는다.
"""

import asyncio

from . import db
from .logging import log

TEXTS = {
    "ready": "협약서가 준비됐어요. 방에서 확인해 주세요.",
    "failed": "응답은 모두 모였지만 협약서 생성에 실패했어요. 방장 화면에서 다시 시도해 주세요.",
    "selected": "방장이 협약서 결과를 골랐어요. 방에서 확인해 주세요.",
}
EXPIRED_STATUSES = (404, 410)


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
        for item in pending:
            subscription = {"endpoint": item["endpoint"], "keys": item["keys"]}
            try:
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
