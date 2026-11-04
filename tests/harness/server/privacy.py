"""공개 금지 키와 메모 표지 검사(§0-A 6, AC3, 규칙 3). 모든 케이스가 이 함수 하나를 쓴다.

scan_private(payload, targets, ctx, where)는 문제 목록을 돌려준다. 빈 목록이면 통과다.
payload는 응답 JSON(dict·list), 문자열(로그·푸시 본문) 또는 그 목록이다.
targets는 server_cases.yaml privacy_scan 값이다. 검사 대상이 없는 값(예: 메모 없음)은 건너뛴다.
"""

import json
from dataclasses import dataclass, field

MEMO_WINDOW = 15
FORBIDDEN_KEYS = {
    "memo", "positions", "original_condition", "gender", "age_band", "mbti",
    "source_response_ids", "source_response_id", "response_id",
}
PROFILE_KEYS = {"gender", "age_band", "mbti"}


@dataclass
class PrivateContext:
    """검사에 쓰는 값. 테스트가 방을 만들고 제출할 때 채운다."""

    memos: list = field(default_factory=list)
    original_conditions: list = field(default_factory=list)
    profile_values: list = field(default_factory=list)
    names: list = field(default_factory=list)
    option_labels: list = field(default_factory=list)
    public_texts: list = field(default_factory=list)

    def add_memo(self, memo):
        if isinstance(memo, str) and memo and memo not in self.memos:
            self.memos.append(memo)

    def add_original_conditions(self, values):
        for value in values:
            if value not in self.original_conditions:
                self.original_conditions.append(value)


def _walk_keys(node, path=()):
    if isinstance(node, dict):
        for key, value in node.items():
            yield path, key
            yield from _walk_keys(value, path + (key,))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _walk_keys(value, path + (i,))


def _option_id_allowed(path):
    # path는 option_id 키를 가진 객체의 경로다. 문항 표시의 scenarios[].options[].option_id만 허용한다(§0-A 6).
    return len(path) >= 4 and path[-4] == "scenarios" and path[-2] == "options"


def _text(payload):
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False, default=str)


def _in_public(value, ctx):
    return any(value in text for text in ctx.public_texts)


def scan_private(payload, targets, ctx, where="응답", result_payload=False):
    """result_payload가 참이면 option_id도 금지 키로 본다(결과 응답에는 option_id를 넣지 않는다)."""
    problems = []
    targets = list(targets)
    unknown = set(targets) - {"forbidden_keys", "profile_keys", "memo_markers", "original_conditions",
                              "profile_values", "names", "option_labels"}
    if unknown:
        raise ValueError(f"모르는 privacy_scan 대상 {sorted(unknown)}")
    structured = not isinstance(payload, str)
    if structured and ("forbidden_keys" in targets or "profile_keys" in targets):
        banned = set()
        if "forbidden_keys" in targets:
            banned |= FORBIDDEN_KEYS
        if "profile_keys" in targets:
            banned |= PROFILE_KEYS
        for path, key in _walk_keys(payload):
            if key in banned:
                problems.append(f"{where}: 공개 금지 키 {key} ({'/'.join(map(str, path)) or '루트'})")
            if key == "option_id" and "forbidden_keys" in targets and (result_payload or not _option_id_allowed(path)):
                problems.append(f"{where}: 결과·비문항 위치의 option_id ({'/'.join(map(str, path))})")
    text = _text(payload)
    if "memo_markers" in targets:
        for memo in ctx.memos:
            for start in range(max(len(memo) - MEMO_WINDOW + 1, 0)):
                window = memo[start:start + MEMO_WINDOW]
                if window in text and not _in_public(window, ctx):
                    problems.append(f"{where}: 메모의 연속 {MEMO_WINDOW}자가 그대로 있다")
                    break
    if "original_conditions" in targets:
        for value in ctx.original_conditions:
            if value and value in text and not _in_public(value, ctx):
                problems.append(f"{where}: original_condition 값이 그대로 있다")
    if "profile_values" in targets:
        for value in ctx.profile_values:
            if value and value in text and not _in_public(value, ctx):
                problems.append(f"{where}: 선택 프로필 값 {value!r}이 있다")
    if "names" in targets:
        for value in ctx.names:
            if value and value in text:
                problems.append(f"{where}: 이름·별명 {value!r}이 있다")
    if "option_labels" in targets:
        for value in ctx.option_labels:
            if value and value in text:
                problems.append(f"{where}: 선택지 문구 {value!r}가 있다")
    return problems
