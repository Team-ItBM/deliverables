"""server_cases.yaml 읽기와 판정 키 사용 추적.

케이스 값은 코드에 복사하지 않고 이 모듈로 읽는다. CaseExpect는 테스트가 읽은 판정 키를 기록하고,
테스트가 끝났을 때 읽지 않은 키가 남았는지 conftest가 확인한다.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
CASES_PATH = ROOT / "tests" / "harness" / "server_cases.yaml"

META_KEYS = {"id", "case_id", "kind", "ac", "basis", "note", "checkpoints"}
JUDGMENT_KEYS = {
    "http_status", "error_code", "concurrent_statuses", "calls", "calls_added", "unchanged",
    "room_status", "scenario_status", "failure_reason", "rooms_created", "expires_after_days",
    "scenario_notice_keys", "privacy_notice", "privacy_scan", "token_display", "same_outside_tokens",
    "text_includes", "text_excludes", "rendered", "rendered_by_submission", "submitted_count",
    "distinct_participant_ids", "model_input_participant_count", "model_input_response_count",
    "included_count", "excluded_names_count", "excluded_names_include_profiles", "duplicate_name_notice",
    "has_submission", "result_attempts", "normal_results", "failed_results", "result_kind", "result_label",
    "source_result", "shared_result", "new_result_rows", "repair_error_codes", "waits", "backoff_waits",
    "has_humor", "humor_text", "humor_explanation", "push_sent", "host_push_text",
    "subscription_by_send_status", "notification_records_per_pair", "push_payload_keys",
}
REQUIRED_KEYS = {"id", "case_id", "kind", "ac", "basis", "note"}
UNCHANGED_NAMES = {
    "room_status", "submitted_count", "included_count", "results", "selected_result", "calls",
    "model_input", "submission", "original_result", "previous_edit",
}
PRIVACY_TARGETS = {
    "forbidden_keys", "profile_keys", "memo_markers", "original_conditions", "profile_values", "names", "option_labels",
}
STAGES = {"scenarios", "pact"}
STATE_KEYS = {"room_status", "scenario_status", "failure_reason"}
PROHIBITION_KEYS = {"privacy_scan", "push_sent", "notification_records_per_pair", "push_payload_keys"}


def load_cases_file(path=CASES_PATH):
    with Path(path).open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def cases_by_id(doc):
    return {c["id"]: c for c in (doc.get("cases") or []) if isinstance(c, dict) and "id" in c}


def iter_expectations(case):
    """(at, 판정 키 매핑)을 낸다. 최상위는 at=None이다."""
    yield None, {k: v for k, v in case.items() if k not in META_KEYS}
    for cp in case.get("checkpoints") or []:
        if isinstance(cp, dict):
            yield cp.get("at"), {k: v for k, v in cp.items() if k != "at"}


class _Section:
    def __init__(self, owner, at, values):
        self._owner = owner
        self._at = at
        self._values = values

    def __contains__(self, key):
        return key in self._values

    def __getitem__(self, key):
        if key not in self._values:
            where = f"checkpoint {self._at}" if self._at else "최상위"
            raise KeyError(f"{self._owner.case['id']}의 {where}에 판정 키 {key}가 없다")
        self._owner.used.add((self._at, key))
        return self._values[key]

    def get(self, key, default=None):
        if key not in self._values:
            return default
        return self[key]

    def keys(self):
        return set(self._values)


class CaseExpect:
    """케이스 하나의 판정 키. expect["key"], expect.at("name")["key"]로 읽으며 읽은 키를 기록한다."""

    def __init__(self, case):
        self.case = case
        self.used = set()
        self._sections = dict(iter_expectations(case))

    @property
    def id(self):
        return self.case["id"]

    def _top(self):
        return _Section(self, None, self._sections[None])

    def __contains__(self, key):
        return key in self._sections[None]

    def __getitem__(self, key):
        return self._top()[key]

    def get(self, key, default=None):
        return self._top().get(key, default)

    def at(self, name):
        if name not in self._sections or name is None:
            raise KeyError(f"{self.case['id']}에 checkpoint {name}이 없다")
        return _Section(self, name, self._sections[name])

    def checkpoint_names(self):
        return [at for at in self._sections if at is not None]

    def unused(self):
        missing = []
        for at, values in self._sections.items():
            for key in values:
                if (at, key) not in self.used:
                    missing.append(f"{at or '최상위'}.{key}")
        for at in self._sections:
            if at is not None and not any(u[0] == at for u in self.used):
                missing.append(f"checkpoint {at}")
        return sorted(set(missing))


def http_ok(expected, actual):
    """판정 키의 정수 또는 목록(그중 하나)과 실제 값을 비교한다."""
    if isinstance(expected, list):
        return actual in expected
    return actual == expected
