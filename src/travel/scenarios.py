"""문항 단계 후처리: 모델이 낸 ScenarioSet을 문항 표시 전에 결정적으로 검사한다.

함수 이름과 인자는 src/travel/prompts/prepare_scenarios.md "필드와 함수 인자" 표를 따른다.
오류 코드와 판정 규칙은 docs/prompts/delegation_scenarios.md §0·§0-1을 따른다.
검사 순서는 JSON 파싱, 스키마 v2, 상태 조합, 입력 대조다. 파싱이나 스키마에서 실패하면
그 단계에서 멈추고, 상태 조합과 입력 대조의 오류는 모두 모은다.
기간·인원 적합성, 선택지 의미 보존, 개인화 적절성, 토큰 치환, 모델 호출은 검사하지 않는다.
입력·출력 문자열은 데이터로만 다루며, 그 내용이 검사 규칙을 바꾸지 않는다.
"""

import json
import re
from pathlib import Path

from jsonschema import Draft7Validator

SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "scenario_set.schema.json"

# {{, 공백, profile, 공백, :, ID, }} 순서. ID는 공백을 다듬지 않고 그대로 꺼낸다(§0-1 결정 3).
PROFILE_TOKEN = re.compile(r"\{\{\s*profile\s*:([^{}]*)\}\}")

# 상태별 다음 동작. 값은 "필드와 함수 인자" 표의 함수 이름이다.
STATUS_ROUTES = {
    "ready": {"next_action": "render_questions", "check_input": True},
    "needs_information": {"next_action": "ask_missing_information", "check_input": False},
    "unsupported": {"next_action": "show_generation_notice", "check_input": False},
    "invalid_input": {"next_action": "show_generation_notice", "check_input": False},
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


class PoolIndex:
    """입력 scenario_pool과 participant_profiles를 조회한다. 같은 template_id가 여러 번 있으면 처음 항목을 쓴다."""

    def __init__(self, scenario_input):
        scenario_input = scenario_input if isinstance(scenario_input, dict) else {}
        self.templates = {}
        for item in scenario_input.get("scenario_pool") or []:
            if isinstance(item, dict) and isinstance(item.get("template_id"), str):
                self.templates.setdefault(item["template_id"], item)
        self.profile_ids = {
            p["profile_id"]
            for p in scenario_input.get("participant_profiles") or []
            if isinstance(p, dict) and isinstance(p.get("profile_id"), str)
        }
        self.requested_count = scenario_input.get("requested_count")

    def lookup_template(self, template_id):
        """template_id와 정확히 같은 pool 항목을 돌려준다. 대소문자·공백을 정규화하지 않는다."""
        return self.templates.get(template_id)


def route_scenario_result(status):
    """상태별 다음 동작을 {next_action, check_input}으로 돌려준다. 모르는 status는 KeyError를 낸다."""
    return STATUS_ROUTES[status]


def parse_output(raw_output):
    """raw_output을 JSON으로 읽는다. 실패하면 (None, [json_invalid])를 돌려준다."""
    if not isinstance(raw_output, str):
        return None, [_error("json_invalid", "", "출력이 문자열이 아니다")]
    try:
        return json.loads(raw_output), []
    except ValueError as exc:
        return None, [_error("json_invalid", "", f"JSON 파싱 실패: {exc}")]


def validate_schema(output):
    """스키마 v2 위반마다 schema_violation 하나를 낸다. 순서는 경로와 메시지로 고정한다."""
    found = sorted(_schema_validator().iter_errors(output), key=lambda e: (list(map(str, e.absolute_path)), e.message))
    return [_error("schema_violation", _pointer(*e.absolute_path), e.message) for e in found]


def check_status_combination(output):
    """prepare_scenarios.md B절 상태별 필수·금지 필드 조합과 §0-1 결정 1을 검사한다."""
    status = output["status"]
    errors = []

    def need(key, detail):
        if key not in output:
            errors.append(_error("status_combination", _pointer(key), detail))

    if status == "ready":
        if output["scenarios"] is None:
            errors.append(_error("status_combination", "/scenarios", "ready에는 문항이 필요하다"))
        if "clarification_questions" in output:
            errors.append(_error("status_combination", "/clarification_questions",
                                 "ready에는 clarification_questions를 둘 수 없다"))
        return errors

    if output["scenarios"] is not None:
        errors.append(_error("status_combination", "/scenarios", f"{status}에서는 scenarios=null이어야 한다"))
    if status == "needs_information":
        need("clarification_questions", "needs_information에는 clarification_questions가 필요하다")
    need("message", f"{status}에는 message가 필요하다")
    return errors


def check_count(index, scenarios):
    """문항 수가 requested_count와 같은지 본다."""
    if len(scenarios) != index.requested_count:
        return [_error("count_mismatch", "/scenarios",
                       f"문항 {len(scenarios)}개, 요청 수 {index.requested_count}개")]
    return []


def check_templates(index, scenarios):
    """pool에 없는 template_id(unknown_template)와 두 번째 이후로 나온 template_id(duplicate_template)."""
    errors = []
    for i, scenario in enumerate(scenarios):
        template_id = scenario["template_id"]
        if index.lookup_template(template_id) is None:
            errors.append(_error("unknown_template", _pointer("scenarios", i, "template_id"),
                                 f"입력 pool에 없는 문항 {template_id}"))
    seen = set()
    for i, scenario in enumerate(scenarios):
        template_id = scenario["template_id"]
        if template_id in seen:
            errors.append(_error("duplicate_template", _pointer("scenarios", i, "template_id"),
                                 f"문항 {template_id}이 두 번 이상 선정됐다"))
        seen.add(template_id)
    return errors


def check_decisions(index, scenarios):
    """pool에서 조회한 decision_key가 겹치는지 본다. pool에 없는 문항과 문자열이 아닌 키는 세지 않는다."""
    errors = []
    seen = {}
    for i, scenario in enumerate(scenarios):
        template = index.lookup_template(scenario["template_id"])
        if template is None or not isinstance(template.get("decision_key"), str):
            continue
        key = template["decision_key"]
        if key in seen:
            errors.append(_error("duplicate_decision", _pointer("scenarios", i, "template_id"),
                                 f"판단 {key}이 scenarios/{seen[key]}과 겹친다"))
        else:
            seen[key] = i
    return errors


def check_options(index, scenarios):
    """option_id 목록이 원본 pool 문항과 순서·개수까지 같은지 본다. pool에 없는 문항은 건너뛴다."""
    errors = []
    for i, scenario in enumerate(scenarios):
        template = index.lookup_template(scenario["template_id"])
        if template is None:
            continue
        expected = [o.get("option_id") if isinstance(o, dict) else None for o in template.get("options") or []]
        actual = [o["option_id"] for o in scenario["options"]]
        if actual != expected:
            errors.append(_error("option_mismatch", _pointer("scenarios", i, "options"),
                                 "선택지 ID 목록이 원본 문항과 순서·개수까지 같지 않다"))
    return errors


def _token_texts(scenario):
    yield ("scene",), scenario["scene"]
    yield ("question",), scenario["question"]
    for j, option in enumerate(scenario["options"]):
        yield ("options", j, "label"), option["label"]


def check_profile_tokens(index, scenarios):
    """scene, question, options[].label의 {{profile:ID}} ID가 등록 profile_id와 정확히 같은지 본다."""
    errors = []
    for i, scenario in enumerate(scenarios):
        for parts, text in _token_texts(scenario):
            for match in PROFILE_TOKEN.finditer(text):
                if match.group(1) not in index.profile_ids:
                    errors.append(_error("unknown_profile_token", _pointer("scenarios", i, *parts),
                                         f"등록되지 않은 인물 토큰 {match.group(0)}"))
    return errors


def check_scene_lines(index, scenarios):
    """scene에 빈 줄이 없고 줄 수가 원본 pool scene과 같은지 본다. 끝 줄바꿈도 빈 줄로 센다."""
    errors = []
    for i, scenario in enumerate(scenarios):
        template = index.lookup_template(scenario["template_id"])
        if template is None:
            continue
        lines = scenario["scene"].split("\n")
        original = template.get("scene")
        expected = len(original.split("\n")) if isinstance(original, str) else None
        if "" in lines:
            errors.append(_error("scene_line_mismatch", _pointer("scenarios", i, "scene"), "scene에 빈 줄이 있다"))
        elif len(lines) != expected:
            errors.append(_error("scene_line_mismatch", _pointer("scenarios", i, "scene"),
                                 f"scene {len(lines)}줄, 원본 {expected}줄"))
    return errors


INPUT_CHECKS = (check_count, check_templates, check_decisions, check_options, check_profile_tokens, check_scene_lines)


def validate_scenario_output(scenario_input, raw_output):
    """모델이 낸 ScenarioSet 문자열을 검사해 {valid, errors[{code, path, detail}]}를 돌려준다.

    scenario_input은 문항 프롬프트 C절 입력이며 바꾸지 않는다. pool은 입력에서 읽는다.
    입력 대조는 route_scenario_result의 check_input이 참이고 scenarios가 리스트일 때만 한다.
    """
    output, errors = parse_output(raw_output)
    if errors:
        return {"valid": False, "errors": errors}
    errors = validate_schema(output)
    if errors:
        return {"valid": False, "errors": errors}

    errors = check_status_combination(output)
    route = route_scenario_result(output["status"])
    scenarios = output["scenarios"]
    if route["check_input"] and isinstance(scenarios, list):
        index = PoolIndex(scenario_input)
        for check in INPUT_CHECKS:
            errors.extend(check(index, scenarios))
    return {"valid": not errors, "errors": errors}
