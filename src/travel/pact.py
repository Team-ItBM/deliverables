"""추천 단계 후처리: 모델이 낸 PactRecommendation을 공유 전에 결정적으로 검사한다.

함수 이름과 인자는 src/travel/prompts/generate_pact.md "필드와 함수 인자" 표를 따른다.
오류 코드와 판정 규칙은 tests/harness/golden_cases.yaml 머리말을 따른다.
조율 내용의 품질(의미 판정)은 검사하지 않는다.
입력·출력 문자열은 데이터로만 다루며, 그 내용이 검사 규칙을 바꾸지 않는다.
"""

import json
import re
from pathlib import Path

from jsonschema import Draft7Validator

SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "pact_recommendation.schema.json"

HUMOR_TEXT = "너네 조합 꽝이니 여행 가지 마세요!"
PARTICIPANT_TOKEN = re.compile(r"\{\{participant:([^{}]*)\}\}")
PARTICLE_PAIRS = ("은/는", "이/가", "을/를", "과/와", "으로/로")
# 쌍 표기가 아닐 때 한쪽 조사만 붙었는지 본다. "으로"는 "으"보다 먼저 확인한다.
SINGLE_PARTICLES = ("으로", "은", "는", "이", "가", "을", "를", "과", "와", "로")

# 상태별 처리 분기. needs_information의 positions 필요 여부는 출력의 positions로 정한다.
STATUS_ROUTES = {
    "proposed": {"check_evidence": True, "positions_required": True},
    "conditional_only": {"check_evidence": True, "positions_required": True},
    "needs_information": {"check_evidence": True, "positions_required": None},
    "unresolved": {"check_evidence": True, "positions_required": True},
    "unsupported": {"check_evidence": False, "positions_required": False},
    "invalid_input": {"check_evidence": False, "positions_required": False},
}

_validator = None


def _schema_validator():
    global _validator
    if _validator is None:
        with SCHEMA_PATH.open(encoding="utf-8") as f:
            _validator = Draft7Validator(json.load(f))
    return _validator


def _error(code, path, detail):
    return {"code": code, "path": path, "detail": detail}


def _pointer(*parts):
    return "/" + "/".join(str(p).replace("~", "~0").replace("/", "~1") for p in parts) if parts else ""


class InputIndex:
    """입력의 상황·참여자·응답 ID를 조회한다. 같은 ID가 여러 번 있으면 처음 항목을 쓴다."""

    def __init__(self, pact_input):
        pact_input = pact_input if isinstance(pact_input, dict) else {}
        self.participant_ids = [p for p in pact_input.get("participant_ids") or [] if isinstance(p, str)]
        self.scenarios = {}
        for scenario in pact_input.get("scenarios") or []:
            if not isinstance(scenario, dict):
                continue
            scenario_id = scenario.get("scenario_id", scenario.get("template_id"))
            if isinstance(scenario_id, str):
                self.scenarios.setdefault(scenario_id, scenario)
        self.responses = [r for r in pact_input.get("responses") or [] if isinstance(r, dict)]
        self.response_by_id = {}
        for response in self.responses:
            response_id = response.get("response_id")
            if isinstance(response_id, str):
                self.response_by_id.setdefault(response_id, response)

    def lookup_scenario(self, scenario_id):
        return self.scenarios.get(scenario_id)

    def _option_label(self, response):
        scenario = self.lookup_scenario(response.get("scenario_id"))
        if scenario is None:
            return None
        for option in scenario.get("options") or []:
            if isinstance(option, dict) and option.get("option_id") == response.get("option_id"):
                label = option.get("label")
                return label if isinstance(label, str) else None
        return None

    def lookup_response_evidence(self, ids):
        """응답 ID 목록을 근거 기록으로 바꾼다. 입력에 없는 ID는 None이다."""
        evidence = []
        for response_id in ids:
            response = self.response_by_id.get(response_id)
            if response is None:
                evidence.append(None)
                continue
            evidence.append({
                "response_id": response_id,
                "participant_id": response.get("participant_id"),
                "scenario_id": response.get("scenario_id"),
                "memo": response.get("memo"),
                "option_label": self._option_label(response),
            })
        return evidence

    def missing_responses(self):
        """채택된 제출 건 안에서 상황별 응답이 없는 (participant_id, scenario_id) 목록."""
        answered = {(r.get("participant_id"), r.get("scenario_id")) for r in self.responses}
        return [
            (participant_id, scenario_id)
            for participant_id in self.participant_ids
            for scenario_id in self.scenarios
            if (participant_id, scenario_id) not in answered
        ]


def _is_excerpt(text, source):
    return isinstance(text, str) and isinstance(source, str) and text in source


def validate_original_condition(text, response):
    """original_condition이 응답 memo 또는 고른 선택지 label의 정확한 부분 문자열인지 본다."""
    return _is_excerpt(text, response.get("memo")) or _is_excerpt(text, response.get("option_label"))


def route_pact_result(status):
    return STATUS_ROUTES[status]


def parse_output(raw_output):
    if not isinstance(raw_output, str):
        return None, [_error("json_invalid", "", "출력이 문자열이 아니다")]
    try:
        return json.loads(raw_output), []
    except ValueError as exc:
        return None, [_error("json_invalid", "", f"JSON 파싱 실패: {exc}")]


def validate_schema(output):
    errors = []
    found = sorted(_schema_validator().iter_errors(output), key=lambda e: (list(map(str, e.absolute_path)), e.message))
    for exc in found:
        errors.append(_error("schema_violation", _pointer(*exc.absolute_path), exc.message))
    return errors


def check_status_combination(output):
    """generate_pact.md B절 상태별 필수·금지 필드 조합."""
    status = output["status"]
    errors = []

    def need(key, detail):
        if key not in output:
            errors.append(_error("status_combination", _pointer(key), detail))

    if status == "proposed":
        if output["clauses"] is None:
            errors.append(_error("status_combination", "/clauses", "proposed에는 조항이 하나 이상 필요하다"))
    elif output["clauses"] is not None:
        errors.append(_error("status_combination", "/clauses", f"{status}에서는 clauses=null이어야 한다"))

    if "conditional_alternatives" in output and status not in ("proposed", "conditional_only"):
        errors.append(_error("status_combination", "/conditional_alternatives",
                             f"{status}에는 조건부 대안을 둘 수 없다"))

    if status == "conditional_only":
        need("conditional_alternatives", "conditional_only에는 conditional_alternatives가 필요하다")
        need("unresolved_conditions", "conditional_only에는 unresolved_conditions가 필요하다")
        need("message", "conditional_only에는 message가 필요하다")
    elif status == "needs_information":
        need("message", "needs_information에는 message가 필요하다")
        if output["positions"]:
            need("unresolved_conditions", "응답별 positions가 있는 needs_information에는 unresolved_conditions가 필요하다")
    elif status == "unresolved":
        need("unresolved_conditions", "unresolved에는 unresolved_conditions가 필요하다")
        need("message", "unresolved에는 message가 필요하다")
    elif status in ("unsupported", "invalid_input"):
        need("message", f"{status}에는 message가 필요하다")
        if output["positions"]:
            errors.append(_error("status_combination", "/positions", f"{status}에서는 positions=[]이어야 한다"))
    return errors


def check_input_status(index, output):
    missing = index.missing_responses()
    missing_form = output["status"] == "needs_information" and output["positions"] == []
    if missing and not missing_form:
        pairs = ", ".join(f"{p}/{s}" for p, s in missing)
        return [_error("input_status_mismatch", "/status",
                       f"채택 제출 건의 응답 누락({pairs})이 있으면 needs_information, positions=[]여야 한다")]
    if not missing and missing_form:
        return [_error("input_status_mismatch", "/status",
                       "응답 누락이 없는데 needs_information, positions=[]이다")]
    return []


def _evidence_items(output):
    """(경로 접두사, 항목, 작성자 일치 검사 여부)를 출력 순서대로 낸다."""
    for i, item in enumerate(output.get("clauses") or []):
        yield ("clauses", i), item, True
    for i, item in enumerate(output.get("conditional_alternatives") or []):
        yield ("conditional_alternatives", i), item, True
    for i, item in enumerate(output.get("unresolved_conditions") or []):
        yield ("unresolved_conditions", i), item, False


def check_evidence(index, output):
    """참조(unknown_reference), 근거 일치(evidence_mismatch), original_condition 인용(quote_mismatch)."""
    errors = []
    known_participants = set(index.participant_ids)
    for prefix, item, check_authors in _evidence_items(output):
        scenario_id = item["scenario_id"]
        if index.lookup_scenario(scenario_id) is None:
            errors.append(_error("unknown_reference", _pointer(*prefix, "scenario_id"),
                                 f"입력에 없는 상황 {scenario_id}"))
        participant_ids = item.get("participant_ids")
        if participant_ids is not None:
            for j, participant_id in enumerate(participant_ids):
                if participant_id not in known_participants:
                    errors.append(_error("unknown_reference", _pointer(*prefix, "participant_ids", j),
                                         f"입력에 없는 참여자 {participant_id}"))

        source_ids = item["source_response_ids"]
        evidence = index.lookup_response_evidence(source_ids)
        authors = set()
        for j, (response_id, record) in enumerate(zip(source_ids, evidence)):
            if record is None:
                errors.append(_error("unknown_reference", _pointer(*prefix, "source_response_ids", j),
                                     f"입력에 없는 응답 {response_id}"))
                continue
            authors.add(record["participant_id"])
            if record["scenario_id"] != scenario_id:
                errors.append(_error("evidence_mismatch", _pointer(*prefix, "source_response_ids", j),
                                     f"응답 {response_id}의 상황 {record['scenario_id']}이 항목 상황 {scenario_id}와 다르다"))
        if check_authors and set(participant_ids) != authors:
            errors.append(_error("evidence_mismatch", _pointer(*prefix, "participant_ids"),
                                 f"적용 대상 {sorted(participant_ids)}이 근거 응답 작성자 {sorted(authors)}와 다르다"))

        for j, change in enumerate(item.get("required_changes") or []):
            response_id = change["source_response_id"]
            (record,) = index.lookup_response_evidence([response_id])
            if record is None:
                errors.append(_error("unknown_reference", _pointer(*prefix, "required_changes", j, "source_response_id"),
                                     f"입력에 없는 응답 {response_id}"))
                continue
            if response_id not in source_ids:
                errors.append(_error("evidence_mismatch", _pointer(*prefix, "required_changes", j, "source_response_id"),
                                     f"응답 {response_id}이 항목의 source_response_ids에 없다"))
            if not validate_original_condition(change["original_condition"], record):
                errors.append(_error("quote_mismatch", _pointer(*prefix, "required_changes", j, "original_condition"),
                                     f"응답 {response_id}의 memo·선택지 label의 정확한 발췌가 아니다"))
    return errors


def validate_positions(input, output):
    """positions가 입력 응답마다 정확히 하나인지, 인용 필드가 해당 memo의 정확한 발췌인지 본다."""
    index = input if isinstance(input, InputIndex) else InputIndex(input)
    errors = []
    counts = {}
    for i, entry in enumerate(output["positions"]):
        response_id = entry["response_id"]
        counts[response_id] = counts.get(response_id, 0) + 1
        response = index.response_by_id.get(response_id)
        if response is None:
            errors.append(_error("positions_mismatch", _pointer("positions", i, "response_id"),
                                 f"입력에 없는 응답 {response_id}"))
            continue
        if counts[response_id] > 1:
            errors.append(_error("positions_mismatch", _pointer("positions", i, "response_id"),
                                 f"응답 {response_id}의 입장이 중복됐다"))
        for key in ("condition", "reason", "expressed_content"):
            text = entry["position"].get(key)
            if text is not None and not _is_excerpt(text, response.get("memo")):
                errors.append(_error("quote_mismatch", _pointer("positions", i, "position", key),
                                     f"응답 {response_id}의 memo의 정확한 발췌가 아니다"))
    for response_id in index.response_by_id:
        if response_id not in counts:
            errors.append(_error("positions_mismatch", "/positions", f"응답 {response_id}의 입장이 없다"))
    return errors


def check_linked_responses(index, output):
    linked = set()
    for _, item, _ in _evidence_items(output):
        linked.update(item["source_response_ids"])
    return [
        _error("unlinked_response", "", f"응답 {response_id}이 조항·조건부 대안·미해결 사유에 연결되지 않았다")
        for response_id in index.response_by_id
        if response_id not in linked
    ]


def _shared_sentences(output):
    """공유 문장 = action, proposed_conditions[], proposed_change, unresolved_conditions[].description, message."""
    for kind in ("clauses", "conditional_alternatives"):
        for i, item in enumerate(output.get(kind) or []):
            yield _pointer(kind, i, "action"), item["action"]
            for j, text in enumerate(item["proposed_conditions"]):
                yield _pointer(kind, i, "proposed_conditions", j), text
            for j, change in enumerate(item.get("required_changes") or []):
                yield _pointer(kind, i, "required_changes", j, "proposed_change"), change["proposed_change"]
    for i, item in enumerate(output.get("unresolved_conditions") or []):
        yield _pointer("unresolved_conditions", i, "description"), item["description"]
    if "message" in output:
        yield "/message", output["message"]


def check_participant_tokens(index, output):
    errors = []
    known = set(index.participant_ids)
    for path, text in _shared_sentences(output):
        for match in PARTICIPANT_TOKEN.finditer(text):
            participant_id = match.group(1)
            if participant_id not in known:
                errors.append(_error("token_invalid", path, f"입력에 없는 참여자 토큰 {match.group(0)}"))
            rest = text[match.end():]
            if rest.startswith(PARTICLE_PAIRS):
                continue
            single = next((p for p in SINGLE_PARTICLES if rest.startswith(p)), None)
            if single is not None:
                errors.append(_error("particle_pair", path,
                                     f"{match.group(0)} 뒤에 조사 쌍 대신 '{single}'만 붙었다"))
    return errors


def _strings(node, path=()):
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for key, value in node.items():
            yield from _strings(value, path + (key,))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _strings(value, path + (i,))


def check_humor_text(output):
    return [
        _error("humor_text", _pointer(*path), "모델 출력에 고정 유머 문구가 있다")
        for path, text in _strings(output)
        if HUMOR_TEXT in text
    ]


def validate_pact_output(pact_input, raw_output):
    """모델이 낸 PactRecommendation 문자열을 검사해 {valid, errors[{code, path, detail}]}를 반환한다."""
    output, errors = parse_output(raw_output)
    if errors:
        return {"valid": False, "errors": errors}
    errors = validate_schema(output)
    if errors:
        return {"valid": False, "errors": errors}

    index = InputIndex(pact_input)
    route = route_pact_result(output["status"])
    errors.extend(check_status_combination(output))
    if route["check_evidence"]:
        errors.extend(check_input_status(index, output))
        errors.extend(check_evidence(index, output))
        positions_required = route["positions_required"]
        if positions_required is None:
            positions_required = output["positions"] != []
        if positions_required:
            errors.extend(validate_positions(index, output))
            errors.extend(check_linked_responses(index, output))
    errors.extend(check_participant_tokens(index, output))
    errors.extend(check_humor_text(output))
    return {"valid": not errors, "errors": errors}
