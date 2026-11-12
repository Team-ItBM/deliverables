"""관리자 접속기록(ARCHITECTURE 8절): delete-room 기록을 S3에 쓰고, 실패해도 삭제 결과는 유지하며 실패를 표시한다.

2026-11-05 사람 승인(접속기록 설계안 5항). DB는 가짜 delete_room으로 대신하고 S3는 가짜 클라이언트로 대신한다.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from travel.server import admin  # noqa: E402

COUNTS = {"profiles": 2, "sessions": 2, "submissions": 2, "results": 1, "push_subscriptions": 0, "llm_calls": 0}


class FakeS3:
    def __init__(self, fail=False):
        self.fail = fail
        self.puts = []

    def put_object(self, **kwargs):
        if self.fail:
            raise RuntimeError("AccessDenied")
        self.puts.append(kwargs)


def _patched(monkeypatch, counts=COUNTS):
    monkeypatch.setattr(admin, "delete_room", lambda url, code: counts)


def test_audit_record_written_to_bucket(monkeypatch):
    _patched(monkeypatch)
    s3 = FakeS3()
    env = {"ADMIN_AUDIT_BUCKET": "audit-bucket", "ADMIN_AUDIT_PREFIX": "admin-audit/", "ADMIN_OPERATOR": "tester"}
    record, code = admin.run_delete_room("room1", "postgresql://x", env=env, s3_client=s3)
    assert code == admin.EXIT_OK and record["deleted"] is True and record["audit_stored"] is True
    assert len(s3.puts) == 1
    put = s3.puts[0]
    assert put["Bucket"] == "audit-bucket" and put["Key"].startswith("admin-audit/") and put["Key"].endswith(".json")
    body = json.loads(put["Body"].decode("utf-8"))
    assert body["event"] == "admin_delete_room" and body["room_code"] == "room1" and body["operator"] == "tester"
    assert body["counts"] == COUNTS
    assert set(body) <= {"event", "record_id", "ts", "operator", "room_code", "deleted", "counts"}, "기록에 이름·메모가 없어야 한다"


def test_audit_failure_keeps_deletion_and_flags_it(monkeypatch):
    _patched(monkeypatch)
    env = {"ADMIN_AUDIT_BUCKET": "audit-bucket"}
    record, code = admin.run_delete_room("room1", "postgresql://x", env=env, s3_client=FakeS3(fail=True))
    assert record["deleted"] is True, "S3 실패가 삭제 결과를 바꾸면 안 된다"
    assert record["audit_stored"] is False and "AccessDenied" in record["audit_error"]
    assert code == admin.EXIT_AUDIT_FAILED


def test_without_bucket_marks_not_stored(monkeypatch):
    _patched(monkeypatch)
    record, code = admin.run_delete_room("room1", "postgresql://x", env={}, s3_client=FakeS3())
    assert code == admin.EXIT_OK and record["audit_stored"] is False


def test_missing_room_exit_code(monkeypatch):
    _patched(monkeypatch, counts=None)
    record, code = admin.run_delete_room("nope", "postgresql://x", env={"ADMIN_AUDIT_BUCKET": "b"}, s3_client=FakeS3())
    assert record["deleted"] is False and code == admin.EXIT_NOT_FOUND
