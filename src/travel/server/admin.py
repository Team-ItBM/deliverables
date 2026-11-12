"""방 단위 삭제 명령(ARCHITECTURE 2절 admin.py, 처리방침 제7조 삭제 요청 처리). F7 자동 만료의 기반이며 스케줄은 범위 밖이다.

    DATABASE_URL=... python -m travel.server.admin delete-room <room_code> [--yes]

rooms 행을 지우면 profiles, sessions, submissions, responses, results, push_subscriptions, notifications가
외래 키 cascade로 함께 지워진다. llm_calls는 일일 비용 한도를 유지하기 위해 방 연결만 끊고 보존한다.

관리자 접속기록(ARCHITECTURE 8절): 실행 기록(누가·언제·무엇을·삭제 건수. 이름·메모는 없다)을 표준 출력에 남기고,
환경변수 ADMIN_AUDIT_BUCKET이 있으면 같은 JSON을 그 S3 버킷의 ADMIN_AUDIT_PREFIX(기본 admin-audit/) 아래에도 한 건 쓴다.
S3 기록이 실패해도 삭제는 유지하되 결과에 audit_stored=false와 이유를 분명히 표시하고 종료 코드 3을 낸다.
"""

import argparse
import getpass
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import psycopg

from .db import normalize_url

EXIT_OK, EXIT_CANCELLED, EXIT_NOT_FOUND, EXIT_AUDIT_FAILED = 0, 1, 2, 3


def delete_room(database_url, room_code):
    """방과 연결된 자료를 지우고 표별 삭제 건수를 돌려준다. 방이 없으면 None이다."""
    with psycopg.connect(normalize_url(database_url), autocommit=False) as conn:
        row = conn.execute("SELECT room_id, created_at FROM rooms WHERE room_code = %s FOR UPDATE", (room_code,)).fetchone()
        if row is None:
            return None
        counts = {}
        for table in ("profiles", "sessions", "submissions", "results", "push_subscriptions"):
            counts[table] = conn.execute(f"SELECT count(*) FROM {table} WHERE room_id = %s", (row[0],)).fetchone()[0]
        conn.execute("UPDATE llm_calls SET room_id = NULL WHERE room_id = %s", (row[0],))
        counts["llm_calls"] = 0
        conn.execute("DELETE FROM rooms WHERE room_id = %s", (row[0],))
        conn.commit()
        return counts


def audit_key(prefix, moment, record_id):
    prefix = prefix if prefix.endswith("/") else prefix + "/"
    return f"{prefix}{moment:%Y/%m/%d}/{moment:%Y%m%dT%H%M%SZ}-{record_id}.json"


def store_audit(record, bucket, prefix, s3_client=None):
    """기록을 S3에 한 건 쓴다. 성공하면 (True, key), 실패하면 (False, 오류 요약)을 돌려준다. 예외를 내지 않는다."""
    moment = datetime.fromisoformat(record["ts"])
    key = audit_key(prefix, moment, record["record_id"])
    try:
        if s3_client is None:
            import boto3

            s3_client = boto3.client("s3")
        s3_client.put_object(Bucket=bucket, Key=key, Body=json.dumps(record, ensure_ascii=False).encode("utf-8"),
                             ContentType="application/json")
        return True, key
    except Exception as exc:  # 기록 실패는 결과에 표시하고 삭제는 되돌리지 않는다
        return False, f"{type(exc).__name__}: {str(exc)[:200]}"


def build_record(room_code, counts, operator=None, now=None):
    now = now or datetime.now(timezone.utc)
    return {"event": "admin_delete_room", "record_id": uuid.uuid4().hex[:12], "ts": now.isoformat(),
            "operator": operator or getpass.getuser(), "room_code": room_code, "deleted": counts is not None,
            "counts": counts}


def run_delete_room(room_code, database_url, env=None, s3_client=None):
    """삭제 → 기록 → 결과 dict와 종료 코드. CLI와 테스트가 함께 쓴다."""
    env = os.environ if env is None else env
    counts = delete_room(database_url, room_code)
    record = build_record(room_code, counts, operator=env.get("ADMIN_OPERATOR"))
    bucket = env.get("ADMIN_AUDIT_BUCKET")
    if bucket:
        ok, detail = store_audit(record, bucket, env.get("ADMIN_AUDIT_PREFIX", "admin-audit/"), s3_client)
        record["audit_stored"] = ok
        record["audit_key" if ok else "audit_error"] = detail
    else:
        record["audit_stored"] = False
        record["audit_error"] = "ADMIN_AUDIT_BUCKET 미설정(로컬 실행)"
    if counts is None:
        code = EXIT_NOT_FOUND
    elif bucket and not record["audit_stored"]:
        code = EXIT_AUDIT_FAILED
    else:
        code = EXIT_OK
    return record, code


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
            return EXIT_CANCELLED
    record, code = run_delete_room(args.room_code, args.database_url)
    print(json.dumps(record, ensure_ascii=False))
    if code == EXIT_AUDIT_FAILED:
        print("경고: 삭제는 끝났지만 접속기록 S3 저장에 실패했다. 위 기록을 수동으로 보관한다.", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
