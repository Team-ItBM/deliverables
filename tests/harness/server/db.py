"""테스트 DB 준비. TEST_DATABASE_URL의 PostgreSQL에 테스트마다 새 데이터베이스를 만들고 끝나면 지운다.

TEST_DATABASE_URL은 관리용 데이터베이스(보통 postgres)에 접속하는 URL이다. 예:
  postgresql://postgres:postgres@localhost:55432/postgres
서버에 넘기는 URL은 경로(데이터베이스 이름)만 새 이름으로 바꾼 같은 형식이다.
psycopg는 이 모듈의 함수를 부를 때만 import한다.
"""

import os
import time
import uuid
from contextlib import contextmanager
from urllib.parse import urlsplit, urlunsplit

ENV_NAME = "TEST_DATABASE_URL"


def admin_url():
    return os.environ.get(ENV_NAME) or None


def _psycopg_url(url):
    parts = urlsplit(url)
    scheme = parts.scheme.split("+", 1)[0]
    return urlunsplit((scheme, parts.netloc, parts.path, parts.query, parts.fragment))


def with_database(url, name):
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, "/" + name, parts.query, parts.fragment))


def connect(url, **kwargs):
    import psycopg

    return psycopg.connect(_psycopg_url(url), autocommit=True, **kwargs)


def database_exists(admin, name):
    with connect(admin) as conn:
        row = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone()
    return row is not None


def create_database(admin):
    name = "srvtest_" + uuid.uuid4().hex[:16]
    with connect(admin) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    return name, with_database(admin, name)


def drop_database(admin, name):
    with connect(admin) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@contextmanager
def fresh_database(admin):
    name, url = create_database(admin)
    try:
        yield name, url
    finally:
        drop_database(admin, name)


def query(url, sql, params=()):
    """행을 dict 목록으로 돌려준다."""
    from psycopg.rows import dict_row

    with connect(url, row_factory=dict_row) as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall() if cur.description else []


def execute(url, sql, params=()):
    with connect(url) as conn:
        conn.execute(sql, params)


class RowLock:
    """다른 연결이 행을 잠근 상태를 만든다. 동시 요청이 충돌하는 시점을 테스트가 정할 때 쓴다."""

    def __init__(self, url, sql, params=()):
        self.conn = connect(url)
        self.conn.autocommit = False
        self.conn.execute(sql, params)

    def release(self):
        if not self.conn.closed:
            self.conn.commit()
            self.conn.close()


def wait_for_lock_waiters(url, count, timeout=10):
    """이 데이터베이스에서 잠금을 기다리는 연결이 count개가 될 때까지 기다린다."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        rows = query(url, "SELECT count(*) AS n FROM pg_stat_activity "
                          "WHERE datname = current_database() AND wait_event_type = 'Lock'")
        if rows[0]["n"] >= count:
            return
        time.sleep(0.01)
    raise AssertionError(f"{timeout}초 안에 잠금 대기 연결이 {count}개가 되지 않았다")
