import json
import re
from pathlib import Path

from jsonschema import Draft7Validator

SCHEMA_PATH = Path(__file__).resolve().parent / "schemas" / "pact_recommendation.schema.json"

PARTICIPANT_TOKEN = re.compile(r"\{\{participant:([^{}]*)\}\}")
PARTICLE_PAIRS = ("은/는", "이/가", "을/를", "과/와", "으로/로")
SINGLE_PARTICLES = ("으로", "은", "는", "이", "가", "을", "를", "과", "와", "로")
MEMO_QUOTE_MIN_LENGTH = 15
MAX_SENTENCES = 2
DISCUSSION_PHRASE = "당사자 간 직접 논의하여 정한다."
SENTENCE_END = re.compile(r"[.?!]")
POLITE = re.compile(r"[가-힣]요(?=[.,?!]|$)")
DIGIT = re.compile(r"[0-9]")
JUDGED_BASIS = ("agreed", "majority", "challenge")
MODEL_JUDGMENT_KEYS = ("scenario_id", "outcome", "decided_label", "any_ok", "tied_labels")

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

    def __init__(self, pact_input):
        pact_input = pact_input if isinstance(pact_input, dict) else {}
        self.participant_ids = [p for p in pact_input.get("participant_ids") or [] if isinstance(p, str)]
        self.scenarios = {}
        self.scenario_order = []
        for scenario in pact_input.get("scenarios") or []:
            if not isinstance(scenario, dict):
                continue
            scenario_id = scenario.get("scenario_id", scenario.get("template_id"))
            if isinstance(scenario_id, str) and scenario_id not in self.scenarios:
                self.scenarios[scenario_id] = scenario
                self.scenario_order.append(scenario_id)
        self.responses = [r for r in pact_input.get("responses") or [] if isinstance(r, dict)]
        self.challenge_responses = [r for r in pact_input.get("challenge_responses") or [] if isinstance(r, dict)]
        self.response_by_id = {}
        for response in self.responses:
            response_id = response.get("response_id")
            if isinstance(response_id, str):
                self.response_by_id.setdefault(response_id, response)
        self.judgments = {}
        for item in pact_input.get("judgments") or []:
            if isinstance(item, dict) and isinstance(item.get("scenario_id"), str):
                self.judgments.setdefault(item["scenario_id"], item)

    def lookup_scenario(self, scenario_id):
        return self.scenarios.get(scenario_id)

    def missing_responses(self):
        answered = {(r.get("participant_id"), r.get("scenario_id")) for r in self.responses}
        return [
            (participant_id, scenario_id)
            for participant_id in self.participant_ids
            for scenario_id in self.scenario_order
            if (participant_id, scenario_id) not in answered
        ]

    def has_memo(self, scenario_id):
        return any(
            isinstance(r.get("memo"), str) and r["memo"].strip()
            for r in self.responses + self.challenge_responses
            if r.get("scenario_id") == scenario_id
        )


def model_input_for_pact(model_input):
    payload = dict(model_input)
    if isinstance(model_input.get("judgments"), list):
        payload["judgments"] = [
            {key: item[key] for key in MODEL_JUDGMENT_KEYS if key in item}
            for item in model_input["judgments"]
            if isinstance(item, dict)
        ]
    return payload


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
    status = output["status"]
    errors = []
    if status == "ready":
        if "message" in output:
            errors.append(_error("status_combination", "/message", "ready에는 message를 두지 않는다"))
        if not output["clauses"] and not output["discussion_items"]:
            errors.append(_error("status_combination", "/clauses", "ready에는 조항이나 협의 사항이 하나 이상 필요하다"))
    else:
        if "message" not in output:
            errors.append(_error("status_combination", "/message", f"{status}에는 message가 필요하다"))
        if output["clauses"] or output["discussion_items"]:
            errors.append(_error("status_combination", "/clauses", f"{status}에서는 두 배열이 비어야 한다"))
    return errors


def check_input_status(index, output):
    missing = index.missing_responses()
    if missing and output["status"] == "ready":
        pairs = ", ".join(f"{p}/{s}" for p, s in missing)
        return [_error("input_status_mismatch", "/status", f"응답 누락({pairs})이 있으면 needs_information이어야 한다")]
    if not missing and output["status"] == "needs_information":
        return [_error("input_status_mismatch", "/status", "응답 누락이 없는데 needs_information이다")]
    return []


def _items(output):
    for i, item in enumerate(output["clauses"]):
        yield ("clauses", i), item
    for i, item in enumerate(output["discussion_items"]):
        yield ("discussion_items", i), item


def check_coverage(index, output):
    errors = []
    seen = {}
    for prefix, item in _items(output):
        scenario_id = item["scenario_id"]
        if scenario_id not in index.scenarios:
            errors.append(_error("unknown_reference", _pointer(*prefix, "scenario_id"), f"입력에 없는 문항 {scenario_id}"))
            continue
        if scenario_id in seen:
            errors.append(_error("coverage_mismatch", _pointer(*prefix, "scenario_id"), f"문항 {scenario_id}이 두 번 나온다"))
        seen[scenario_id] = prefix
    for scenario_id in index.scenario_order:
        if scenario_id not in seen:
            errors.append(_error("coverage_mismatch", "", f"문항 {scenario_id}이 조항과 협의 사항 어디에도 없다"))
    return errors


def check_judgments(index, output):
    errors = []
    for i, item in enumerate(output["clauses"]):
        scenario_id = item["scenario_id"]
        judgment = index.judgments.get(scenario_id)
        if judgment is None:
            continue
        outcome = judgment.get("outcome")
        if item["basis"] == "limit":
            if not index.has_memo(scenario_id):
                errors.append(_error("judgment_mismatch", _pointer("clauses", i, "basis"),
                                     f"문항 {scenario_id}에 메모가 없는데 limit이다"))
        elif outcome == "discussion":
            errors.append(_error("judgment_mismatch", _pointer("clauses", i, "basis"),
                                 f"문항 {scenario_id}은 협의 판정인데 조항으로 썼다"))
        elif item["basis"] != outcome:
            errors.append(_error("judgment_mismatch", _pointer("clauses", i, "basis"),
                                 f"문항 {scenario_id}의 basis {item['basis']}가 판정 {outcome}과 다르다"))
    for i, item in enumerate(output["discussion_items"]):
        scenario_id = item["scenario_id"]
        judgment = index.judgments.get(scenario_id)
        if judgment is None:
            continue
        if judgment.get("outcome") != "discussion" and not index.has_memo(scenario_id):
            errors.append(_error("judgment_mismatch", _pointer("discussion_items", i, "scenario_id"),
                                 f"문항 {scenario_id}은 확정 판정인데 협의 사항으로 썼다"))
    return errors


def _sentences(text):
    parts = [p for p in SENTENCE_END.split(text.strip()) if p.strip()]
    return len(parts)


def check_texts(output):
    errors = []
    for prefix, item in _items(output):
        path = _pointer(*prefix, "text")
        text = item["text"].strip()
        if _sentences(text) > MAX_SENTENCES:
            errors.append(_error("sentence_limit", path, f"{MAX_SENTENCES}문장을 넘는다"))
        if not text.endswith("다.") or "?" in text or "!" in text or POLITE.search(text):
            errors.append(_error("style_violation", path, "협약서체(~다.)가 아니다"))
        if DIGIT.search(PARTICIPANT_TOKEN.sub("", text)):
            errors.append(_error("number_in_text", path, "숫자가 들어 있다"))
        if prefix[0] == "discussion_items" and not text.endswith(DISCUSSION_PHRASE):
            errors.append(_error("discussion_phrase", path, f"\"{DISCUSSION_PHRASE}\"로 끝나지 않는다"))
    return errors


def _shared_sentences(output):
    for prefix, item in _items(output):
        yield _pointer(*prefix, "text"), item["text"]
    if "message" in output:
        yield "/message", output["message"]


def check_participant_tokens(index, output):
    errors = []
    known = set(index.participant_ids)
    for path, text in _shared_sentences(output):
        for match in PARTICIPANT_TOKEN.finditer(text):
            if match.group(1) not in known:
                errors.append(_error("token_invalid", path, f"입력에 없는 참여자 토큰 {match.group(0)}"))
            rest = text[match.end():]
            if rest.startswith(PARTICLE_PAIRS):
                continue
            single = next((p for p in SINGLE_PARTICLES if rest.startswith(p)), None)
            if single is not None:
                errors.append(_error("particle_pair", path, f"{match.group(0)} 뒤에 조사 쌍 대신 '{single}'만 붙었다"))
    return errors


def _public_texts(index):
    texts = []
    for scenario in index.scenarios.values():
        texts.extend(t for t in (scenario.get("scene"), scenario.get("question")) if isinstance(t, str))
        for option in scenario.get("options") or []:
            if isinstance(option, dict) and isinstance(option.get("label"), str):
                texts.append(option["label"])
    return texts


def check_memo_quotes(index, output, min_length=MEMO_QUOTE_MIN_LENGTH):
    errors = []
    public = _public_texts(index)
    memos = [
        (r.get("response_id"), r["memo"])
        for r in index.responses + index.challenge_responses
        if isinstance(r.get("memo"), str) and len(r["memo"]) >= min_length
    ]
    for path, text in _shared_sentences(output):
        for response_id, memo in memos:
            for start in range(len(memo) - min_length + 1):
                window = memo[start:start + min_length]
                if window in text and not any(window in p for p in public):
                    errors.append(_error("memo_quote", path,
                                         f"{response_id} 메모의 연속 {min_length}자 이상이 공유 문장에 그대로 있다"))
                    break
    return errors


def validate_pact_output(pact_input, raw_output):
    output, errors = parse_output(raw_output)
    if errors:
        return {"valid": False, "errors": errors}
    errors = validate_schema(output)
    if errors:
        return {"valid": False, "errors": errors}
    index = InputIndex(pact_input)
    errors.extend(check_status_combination(output))
    if output["status"] in ("ready", "needs_information"):
        errors.extend(check_input_status(index, output))
    if output["status"] == "ready":
        errors.extend(check_coverage(index, output))
        errors.extend(check_judgments(index, output))
        errors.extend(check_texts(output))
    errors.extend(check_participant_tokens(index, output))
    errors.extend(check_memo_quotes(index, output))
    return {"valid": not errors, "errors": errors}
