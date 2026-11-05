"""방 단위 삭제 명령(ARCHITECTURE 2절 admin.py, 처리방침 제7조 삭제 요청 처리). F7 자동 만료의 기반이며 스케줄은 범위 밖이다.

    DATABASE_URL=... python -m travel.server.admin delete-room <room_code> [--yes]

rooms 행을 지우면 profiles, sessions, submissions, responses, results, push_subscriptions, notifications, llm_calls가
외래 키 cascade로 함께 지워진다. 실행 기록은 관리자 접속기록으로 표준 출력에 남긴다(누가·언제·무엇을. 이름·메모는 없다).
"""

import argparse
import getpass
import json
import os
import sys
from datetime import datetime, timezone

import psycopg

from .db import normalize_url


def delete_room(database_url, room_code):
    with psycopg.connect(normalize_url(database_url), autocommit=False) as conn:
        row = conn.execute("SELECT room_id, created_at FROM rooms WHERE room_code = %s", (room_code,)).fetchone()
        if row is None:
            return None
        counts = {}
        for table in ("profiles", "sessions", "submissions", "results", "push_subscriptions", "llm_calls"):
            counts[table] = conn.execute(f"SELECT count(*) FROM {table} WHERE room_id = %s", (row[0],)).fetchone()[0]
        conn.execute("DELETE FROM rooms WHERE room_id = %s", (row[0],))
        conn.commit()
        return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description="도원결의 관리 명령")
    sub = parser.add_subparsers(dest="command", required=True)
    d = sub.add_parser("delete-room", help="방과 연결된 자료를 모두 지운다")
    d.add_argument("room_code")
    d.add_argument("--yes", action="store_true", help="확인 없이 실행")
    d.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    args = parser.parse_args(argv)
    if not args.database_url:
        parser.error("DATABASE_URL이 없다")
    if not args.yes:
        answer = input(f"방 {args.room_code}의 자료를 모두 지웁니다. 계속할까요? (yes/no) ")
        if answer.strip().lower() != "yes":
            print("취소했다")
            return 1
    counts = delete_room(args.database_url, args.room_code)
    record = {"event": "admin_delete_room", "ts": datetime.now(timezone.utc).isoformat(), "operator": getpass.getuser(),
              "room_code": args.room_code, "deleted": counts is not None, "counts": counts}
    print(json.dumps(record, ensure_ascii=False))
    return 0 if counts is not None else 2


if __name__ == "__main__":
    sys.exit(main())
