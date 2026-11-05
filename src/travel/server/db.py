"""PostgreSQL 접근: 스키마, 비동기 연결 풀, 방 상태 전환 SQL.

- `init_schema(database_url)`은 동기이며 멱등 DDL만 실행한다(테스트가 앱을 만들기 전에 한 번 부른다).
- `Pool`은 psycopg AsyncConnection(autocommit) 몇 개를 큐로 돌리는 작은 풀이다. 한 앱의 이벤트 루프 안에서만 쓴다.
- 동시성은 DB에서 맞춘다: 방 행을 `SELECT ... FOR UPDATE`로 잠근 뒤 상태를 검사하고 조건부 UPDATE로 바꾼다.
  같은 DB에 앱 인스턴스가 여러 개 떠도(컨테이너 여러 개) 입력 고정과 최초 생성은 한 번만 일어난다(AC4).
- 시도 종료 쓰기는 `current_attempt_id`와 `status='generating'` 두 조건을 모두 건다. 멈춤 판정·작업 한도가 시도 ID를
  바꾸지 않으므로 status 조건이 없으면 늦은 출력이 failed를 덮는다(위임 기록 결정 30, ARCHITECTURE 5절).
- 메모·이름·선택 프로필은 로그에 쓰지 않는다. 이 모듈은 로그를 남기지 않는다.
"""

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from urllib.parse import urlsplit, urlunsplit

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

SCHEMA_VERSION = 2

DDL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version integer PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS rooms (
    room_id uuid PRIMARY KEY,
    room_code text NOT NULL UNIQUE,
    host_token_hash text NOT NULL,
    trip jsonb NOT NULL,
    party_size integer NOT NULL,
    status text NOT NULL DEFAULT 'open',
    failure_reason text,
    scenario_status text NOT NULL DEFAULT 'preparing',
    scenario_set jsonb,
    scenario_notice jsonb,
    submitted_count integer NOT NULL DEFAULT 0,
    closed_at timestamptz,
    generating_since timestamptz,
    current_attempt_id uuid,
    attempt_count integer NOT NULL DEFAULT 0,
    frozen_input jsonb,
    selected_result_id uuid,
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS profiles (
    room_id uuid NOT NULL REFERENCES rooms(room_id) ON DELETE CASCADE,
    profile_id text NOT NULL,
    position integer NOT NULL,
    display_name text NOT NULL,
    gender text,
    age_band text,
    mbti text,
    PRIMARY KEY (room_id, profile_id)
);
CREATE TABLE IF NOT EXISTS sessions (
    session_id uuid PRIMARY KEY,
    room_id uuid NOT NULL REFERENCES rooms(room_id) ON DELETE CASCADE,
    profile_id text NOT NULL,
    created_at timestamptz NOT NULL,
    used_at timestamptz
);
CREATE TABLE IF NOT EXISTS submissions (
    participant_id uuid PRIMARY KEY,
    room_id uuid NOT NULL REFERENCES rooms(room_id) ON DELETE CASCADE,
    profile_id text NOT NULL,
    session_id uuid NOT NULL,
    submission_no integer NOT NULL,
    idempotency_key text NOT NULL,
    body_hash text NOT NULL,
    created_at timestamptz NOT NULL,
    UNIQUE (room_id, idempotency_key)
);
CREATE TABLE IF NOT EXISTS responses (
    response_id uuid PRIMARY KEY,
    participant_id uuid NOT NULL REFERENCES submissions(participant_id) ON DELETE CASCADE,
    room_id uuid NOT NULL,
    position integer NOT NULL,
    scenario_id text NOT NULL,
    option_id text NOT NULL,
    memo text
);
CREATE TABLE IF NOT EXISTS results (
    result_id uuid PRIMARY KEY,
    seq bigserial NOT NULL,
    room_id uuid NOT NULL REFERENCES rooms(room_id) ON DELETE CASCADE,
    attempt integer NOT NULL,
    attempt_id uuid,
    state text NOT NULL,
    kind text NOT NULL,
    origin_result_id uuid,
    source_result_id uuid,
    output jsonb,
    failure_reason text,
    created_at timestamptz NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS results_one_ai_per_attempt
    ON results (room_id, attempt) WHERE kind = 'ai_original';
CREATE TABLE IF NOT EXISTS push_subscriptions (
    subscription_id uuid PRIMARY KEY,
    room_id uuid NOT NULL REFERENCES rooms(room_id) ON DELETE CASCADE,
    role text NOT NULL,
    session_id uuid,
    endpoint text NOT NULL,
    keys jsonb,
    created_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS notifications (
    notification_id bigserial PRIMARY KEY,
    room_id uuid NOT NULL REFERENCES rooms(room_id) ON DELETE CASCADE,
    subscription_id uuid NOT NULL REFERENCES push_subscriptions(subscription_id) ON DELETE CASCADE,
    event text NOT NULL,
    status_code integer,
    created_at timestamptz NOT NULL,
    sent_at timestamptz,
    UNIQUE (subscription_id, event)
);
CREATE TABLE IF NOT EXISTS llm_calls (
    call_id bigserial PRIMARY KEY,
    room_id uuid REFERENCES rooms(room_id) ON DELETE CASCADE,
    attempt_id uuid,
    stage text NOT NULL,
    model text,
    prompt_version text,
    schema_version text,
    pool_version text,
    input_hash text,
    repair boolean NOT NULL DEFAULT false,
    retry_no integer NOT NULL DEFAULT 0,
    response_status text,
    output_status text,
    error_kind text,
    violation_codes jsonb,
    tool_call_count integer,
    unopened_selection jsonb,
    latency_ms integer,
    input_tokens integer,
    output_tokens integer,
    cost_usd numeric(10, 6),
    created_at timestamptz NOT NULL
);
"""


def normalize_url(url):
    """`postgresql+driver://`처럼 드라이버 접미사가 붙은 URL을 psycopg가 받는 형식으로 바꾼다."""
    parts = urlsplit(url)
    scheme = parts.scheme.split("+", 1)[0]
    return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))


def _migrate_push_subscriptions(conn):
    """구독 유일 색인을 만들기 전에 기존 중복을 지운다. 먼저 등록한 행을 남긴다. 지운 행 수를 돌려준다."""
    with conn.transaction():
        conn.execute("LOCK TABLE push_subscriptions IN SHARE ROW EXCLUSIVE MODE")
        cur = conn.execute(
            "DELETE FROM push_subscriptions a USING push_subscriptions b "
            "WHERE a.room_id = b.room_id AND a.role = b.role AND a.endpoint = b.endpoint "
            "AND a.session_id IS NOT DISTINCT FROM b.session_id "
            "AND (a.created_at, a.subscription_id) > (b.created_at, b.subscription_id)")
        removed = cur.rowcount
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS push_subscriptions_one_per_device "
                     "ON push_subscriptions (room_id, role, session_id, endpoint) NULLS NOT DISTINCT")
    return removed


def init_schema(database_url):
    """표를 만든다. 여러 번 불러도 같다. 마이그레이션이 지운 행 수를 돌려준다."""
    with psycopg.connect(normalize_url(database_url), autocommit=True) as conn:
        conn.execute(DDL)
        removed = _migrate_push_subscriptions(conn)
        conn.execute(
            "INSERT INTO schema_version (version) VALUES (%s) ON CONFLICT (version) DO NOTHING",
            (SCHEMA_VERSION,),
        )
    return {"duplicate_push_subscriptions_removed": removed}


def jsonb(value):
    return Jsonb(value)


def as_json(value):
    """psycopg가 jsonb를 dict로 돌려주지만, text 열이면 문자열이다. 둘 다 받는다."""
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    if isinstance(value, str):
        return json.loads(value)
    return value


class Pool:
    """autocommit 연결의 작은 큐 풀. 트랜잭션은 `transaction()`으로 명시한다.

    대기자는 큐만 기다리므로, 연결 슬롯이 빌 때마다 큐에 None을 넣어 깨운다. 깨어난 대기자는 새 연결을 만든다.
    연결을 내줄 때 살아 있는지 확인해 DB 재시작 뒤 쉬던 연결이 요청을 실패시키지 않게 한다.
    """

    def __init__(self, database_url, size=5):
        self._url = normalize_url(database_url)
        self._size = size
        self._queue = asyncio.Queue()
        self._made = 0
        self._closed = False

    def _free_slot(self):
        self._made -= 1
        self._queue.put_nowait(None)

    def _discard(self, conn):
        """취소 중에도 쓸 수 있게 기다리지 않고 버린다."""
        asyncio.ensure_future(conn.close())
        self._free_slot()

    async def _alive(self, conn):
        if conn.closed:
            return False
        try:
            await conn.execute("SELECT 1")
        except psycopg.Error:
            return False
        except BaseException:
            self._discard(conn)
            raise
        return True

    async def acquire(self):
        while True:
            if self._queue.empty() and self._made < self._size:
                self._made += 1
                try:
                    return await psycopg.AsyncConnection.connect(self._url, autocommit=True, row_factory=dict_row)
                except BaseException:
                    self._free_slot()
                    raise
            conn = await self._queue.get()
            if conn is None:
                continue
            if await self._alive(conn):
                return conn
            self._discard(conn)

    async def release(self, conn):
        if conn.closed:
            self._free_slot()
            return
        if conn.info.transaction_status != psycopg.pq.TransactionStatus.IDLE:
            try:
                await conn.rollback()
            except BaseException as exc:
                self._discard(conn)
                if not isinstance(exc, Exception):
                    raise
                return
        self._queue.put_nowait(conn)

    @asynccontextmanager
    async def connection(self):
        conn = await self.acquire()
        try:
            yield conn
        finally:
            await self.release(conn)

    @asynccontextmanager
    async def transaction(self):
        async with self.connection() as conn:
            async with conn.transaction():
                yield conn

    async def close(self):
        self._closed = True
        while not self._queue.empty():
            conn = self._queue.get_nowait()
            if conn is None:
                continue
            try:
                await conn.close()
            except Exception:
                pass
        self._made = 0


class StaleAttempt(Exception):
    """현재 시도가 아니어서 쓰기를 건너뛰었다."""


async def fetch_room_by_code(conn, room_code, for_update=False):
    suffix = " FOR UPDATE" if for_update else ""
    cur = await conn.execute(f"SELECT * FROM rooms WHERE room_code = %s{suffix}", (room_code,))
    return await cur.fetchone()


async def fetch_room_by_id(conn, room_id, for_update=False):
    suffix = " FOR UPDATE" if for_update else ""
    cur = await conn.execute(f"SELECT * FROM rooms WHERE room_id = %s{suffix}", (room_id,))
    return await cur.fetchone()


async def fetch_profiles(conn, room_id):
    cur = await conn.execute(
        "SELECT profile_id, position, display_name, gender, age_band, mbti FROM profiles "
        "WHERE room_id = %s ORDER BY position", (room_id,))
    return await cur.fetchall()


async def fetch_submissions(conn, room_id):
    cur = await conn.execute(
        "SELECT participant_id, profile_id, submission_no FROM submissions WHERE room_id = %s ORDER BY submission_no",
        (room_id,))
    return await cur.fetchall()


async def fetch_responses(conn, room_id):
    cur = await conn.execute(
        "SELECT r.response_id, r.participant_id, r.scenario_id, r.option_id, r.memo, s.submission_no, r.position "
        "FROM responses r JOIN submissions s ON s.participant_id = r.participant_id "
        "WHERE r.room_id = %s ORDER BY s.submission_no, r.position", (room_id,))
    return await cur.fetchall()


async def normal_result_count(conn, room_id):
    cur = await conn.execute(
        "SELECT count(*) AS n FROM results WHERE room_id = %s AND kind = 'ai_original' AND state = 'normal'",
        (room_id,))
    return (await cur.fetchone())["n"]


async def start_attempt(conn, room, now, status_from):
    """잠긴 방 행을 generating으로 바꾸고 새 시도 ID와 번호를 돌려준다. 호출자가 상태 검사를 끝낸 뒤 부른다."""
    attempt_id = uuid.uuid4()
    cur = await conn.execute(
        "UPDATE rooms SET status = 'generating', failure_reason = NULL, generating_since = %s, "
        "current_attempt_id = %s, attempt_count = attempt_count + 1 "
        "WHERE room_id = %s AND status = ANY(%s) RETURNING attempt_count",
        (now, attempt_id, room["room_id"], list(status_from)))
    row = await cur.fetchone()
    if row is None:
        raise StaleAttempt("상태가 바뀌어 시도를 시작하지 못했다")
    return attempt_id, row["attempt_count"]


async def close_and_freeze(conn, room, frozen_input, now):
    """open인 방을 마감하고 입력을 고정한 뒤 첫 시도를 시작한다. 방 행은 잠겨 있어야 한다."""
    attempt_id = uuid.uuid4()
    cur = await conn.execute(
        "UPDATE rooms SET status = 'generating', closed_at = %s, generating_since = %s, current_attempt_id = %s, "
        "attempt_count = 1, frozen_input = %s WHERE room_id = %s AND status = 'open' RETURNING attempt_count",
        (now, now, attempt_id, jsonb(frozen_input), room["room_id"]))
    row = await cur.fetchone()
    if row is None:
        raise StaleAttempt("방이 이미 마감됐다")
    return attempt_id, row["attempt_count"]


async def finish_attempt(conn, room_id, attempt_id, attempt_no, outcome, now):
    """시도 결과를 한 트랜잭션 안에서 쓴다. outcome은 ("ready", output) 또는 ("failed", failure_reason)이다.

    현재 시도가 아니거나 방이 generating이 아니면 StaleAttempt를 내고 아무것도 쓰지 않는다.
    돌려주는 값은 (result_id, 이 시도 전 정상 결과 수)다.
    """
    status, payload = outcome
    before = await normal_result_count(conn, room_id)
    cur = await conn.execute(
        "UPDATE rooms SET status = %s, failure_reason = %s WHERE room_id = %s AND current_attempt_id = %s "
        "AND status = 'generating' RETURNING room_id",
        (status, None if status == "ready" else payload, room_id, attempt_id))
    if await cur.fetchone() is None:
        raise StaleAttempt("현재 시도가 아니다")
    result_id = uuid.uuid4()
    await conn.execute(
        "INSERT INTO results (result_id, room_id, attempt, attempt_id, state, kind, output, failure_reason, created_at) "
        "VALUES (%s, %s, %s, %s, %s, 'ai_original', %s, %s, %s)",
        (result_id, room_id, attempt_no, attempt_id, "normal" if status == "ready" else "failed",
         jsonb(payload) if status == "ready" else None, None if status == "ready" else payload, now))
    return result_id, before


async def enqueue_notifications(conn, room_id, event, roles, now):
    """이벤트·구독 쌍마다 알림 행을 한 번만 만든다. 새로 만든 행(발송 대상)만 돌려준다."""
    cur = await conn.execute(
        "INSERT INTO notifications (room_id, subscription_id, event, created_at) "
        "SELECT s.room_id, s.subscription_id, %s, %s FROM push_subscriptions s "
        "WHERE s.room_id = %s AND s.role = ANY(%s) ORDER BY s.created_at, s.subscription_id "
        "ON CONFLICT (subscription_id, event) DO NOTHING RETURNING notification_id, subscription_id",
        (event, now, room_id, list(roles)))
    rows = await cur.fetchall()
    pending = []
    for row in rows:
        sub = await conn.execute(
            "SELECT subscription_id, endpoint, keys FROM push_subscriptions WHERE subscription_id = %s",
            (row["subscription_id"],))
        sub_row = await sub.fetchone()
        if sub_row is not None:
            pending.append({"notification_id": row["notification_id"], "subscription_id": sub_row["subscription_id"],
                            "endpoint": sub_row["endpoint"], "keys": sub_row["keys"]})
    return pending


async def record_llm_call(conn, row):
    """llm_calls 한 행. 원문·메모·이름을 넣지 않는다."""
    await conn.execute(
        "INSERT INTO llm_calls (room_id, attempt_id, stage, model, prompt_version, schema_version, pool_version, "
        "input_hash, repair, retry_no, response_status, output_status, error_kind, violation_codes, tool_call_count, "
        "unopened_selection, latency_ms, input_tokens, output_tokens, cost_usd, created_at) "
        "VALUES (%(room_id)s, %(attempt_id)s, %(stage)s, %(model)s, %(prompt_version)s, %(schema_version)s, "
        "%(pool_version)s, %(input_hash)s, %(repair)s, %(retry_no)s, %(response_status)s, %(output_status)s, "
        "%(error_kind)s, %(violation_codes)s, %(tool_call_count)s, %(unopened_selection)s, %(latency_ms)s, "
        "%(input_tokens)s, %(output_tokens)s, %(cost_usd)s, %(created_at)s)",
        row)


def _main(argv=None):
    """`python -m travel.server.db --init`: DATABASE_URL의 데이터베이스에 스키마를 만든다(배포 워크플로가 부른다)."""
    import argparse
    import os

    parser = argparse.ArgumentParser(description="도원결의 DB 스키마")
    parser.add_argument("--init", action="store_true", help="표를 만든다(멱등)")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    args = parser.parse_args(argv)
    if not args.init:
        parser.error("--init을 지정한다")
    if not args.database_url:
        parser.error("DATABASE_URL이 없다")
    summary = init_schema(args.database_url)
    print(json.dumps({"event": "schema_initialized", "version": SCHEMA_VERSION, **summary}))


if __name__ == "__main__":
    _main()
