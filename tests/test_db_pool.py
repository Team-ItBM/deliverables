"""DB 연결 풀 복구(PR #16 리뷰 "DB 연결 풀 복구"). 실제 PostgreSQL 연결을 끊어 대기 요청이 깨어나는지 본다.

2026-11-05 사람 승인. 풀 크기 1로 대기자를 만들고, 끊김·연결 실패·취소 뒤 슬롯이 돌아오는지 검사한다.
TEST_DATABASE_URL이 없으면 database_url fixture가 skip한다.
"""

import asyncio

import psycopg
import pytest

from harness.server import db as testdb

WAIT = 3


def _kill_backends(url):
    name = url.rsplit("/", 1)[1]
    testdb.execute(testdb.admin_url(), "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s", (name,))


async def _select_one(conn):
    cur = await conn.execute("SELECT 1 AS n")
    return (await cur.fetchone())["n"]


def test_waiter_recovers_after_connection_in_use_breaks(server, database_url):
    """리뷰 재현: 사용 중 연결이 끊긴 뒤 풀을 기다리던 요청이 새 연결을 받는다."""
    pool = server.db.Pool(database_url, size=1)

    async def scenario():
        conn = await pool.acquire()
        waiter = asyncio.create_task(pool.acquire())
        await asyncio.sleep(0.05)
        assert not waiter.done()
        _kill_backends(database_url)
        with pytest.raises(psycopg.OperationalError):
            await conn.execute("SELECT 1")
        await pool.release(conn)
        fresh = await asyncio.wait_for(waiter, WAIT)
        assert await _select_one(fresh) == 1
        await pool.release(fresh)
        await pool.close()

    asyncio.run(scenario())


def test_idle_connection_broken_by_server_is_replaced(server, database_url):
    """쉬던 연결이 끊겨도(DB 재시작) 첫 요청이 실패하지 않는다."""
    pool = server.db.Pool(database_url, size=1)

    async def scenario():
        async with pool.connection() as conn:
            assert await _select_one(conn) == 1
        _kill_backends(database_url)
        async with pool.connection() as conn:
            assert await _select_one(conn) == 1
        await pool.close()

    asyncio.run(scenario())


def test_waiter_recovers_after_connect_failure(server, database_url, monkeypatch):
    """연결 생성이 실패해 슬롯이 비면 대기자가 깨어나 다시 연결한다."""
    pool = server.db.Pool(database_url, size=1)
    real = psycopg.AsyncConnection.connect
    gate = asyncio.Event
    state = {"calls": 0}

    async def scenario():
        release = gate()

        async def flaky(*args, **kwargs):
            state["calls"] += 1
            if state["calls"] == 1:
                await release.wait()
                raise psycopg.OperationalError("연결 실패")
            return await real(*args, **kwargs)

        monkeypatch.setattr(psycopg.AsyncConnection, "connect", flaky)
        first = asyncio.create_task(pool.acquire())
        await asyncio.sleep(0.01)
        waiter = asyncio.create_task(pool.acquire())
        await asyncio.sleep(0.01)
        release.set()
        with pytest.raises(psycopg.OperationalError):
            await first
        fresh = await asyncio.wait_for(waiter, WAIT)
        assert await _select_one(fresh) == 1
        await pool.release(fresh)
        await pool.close()

    asyncio.run(scenario())


def test_cancelled_connect_returns_slot(server, database_url, monkeypatch):
    """연결 생성 중 요청이 취소돼도 슬롯이 새지 않는다."""
    pool = server.db.Pool(database_url, size=1)
    real = psycopg.AsyncConnection.connect
    state = {"calls": 0}

    async def scenario():
        async def slow(*args, **kwargs):
            state["calls"] += 1
            if state["calls"] == 1:
                await asyncio.sleep(60)
            return await real(*args, **kwargs)

        monkeypatch.setattr(psycopg.AsyncConnection, "connect", slow)
        first = asyncio.create_task(pool.acquire())
        await asyncio.sleep(0.01)
        first.cancel()
        with pytest.raises(asyncio.CancelledError):
            await first
        fresh = await asyncio.wait_for(pool.acquire(), WAIT)
        assert await _select_one(fresh) == 1
        await pool.release(fresh)
        await pool.close()

    asyncio.run(scenario())


def test_pool_size_is_kept_after_many_breaks(server, database_url):
    """끊김이 반복돼도 연결 수가 상한을 넘지 않고, 정상 연결은 재사용한다."""
    pool = server.db.Pool(database_url, size=2)

    async def scenario():
        for _ in range(3):
            conns = [await pool.acquire(), await pool.acquire()]
            _kill_backends(database_url)
            for conn in conns:
                with pytest.raises(psycopg.OperationalError):
                    await conn.execute("SELECT 1")
                await pool.release(conn)
        conn = await asyncio.wait_for(pool.acquire(), WAIT)
        backend = conn.info.backend_pid
        await pool.release(conn)
        again = await pool.acquire()
        assert again.info.backend_pid == backend
        await pool.release(again)
        await pool.close()

    asyncio.run(scenario())
