import copy
import importlib
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_PATH = ROOT / "tests" / "harness" / "golden_cases.yaml"
FIXTURE_DIR = ROOT / "tests" / "harness" / "fixtures" / "pact"

if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

ALLOWED_KEYS = {
    "name",
    "fixture",
    "patch",
    "raw_output",
    "expect_valid",
    "must_include_errors",
    "must_not_include_errors",
    "note",
}
REQUIRED_KEYS = {"name", "fixture", "expect_valid"}
PATCH_OPS = {"add", "remove", "replace"}

VALIDATOR = None
IMPORT_ERROR = None
MISSING_REASON = None
try:
    _pact_module = importlib.import_module("travel.pact")
except ModuleNotFoundError as exc:
    if exc.name in ("travel", "travel.pact"):
        MISSING_REASON = f"validate_pact_output 없음: {exc.name} 모듈을 찾을 수 없다"
    else:
        IMPORT_ERROR = exc
except Exception as exc:
    IMPORT_ERROR = exc
else:
    VALIDATOR = getattr(_pact_module, "validate_pact_output", None)
    if VALIDATOR is None:
        MISSING_REASON = "validate_pact_output 없음: travel.pact에 함수가 정의되지 않았다"


def load_golden():
    with GOLDEN_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


GOLDEN = load_golden()
CASES = (GOLDEN.get("cases") or []) if isinstance(GOLDEN, dict) else []
ERROR_CODES = (GOLDEN.get("error_codes") or []) if isinstance(GOLDEN, dict) else []


def case_id(index, case):
    if isinstance(case, dict) and isinstance(case.get("name"), str):
        return case["name"]
    return f"case_{index}"


def unescape(token):
    return token.replace("~1", "/").replace("~0", "~")


def resolve_parent(doc, path):
    if not isinstance(path, str) or not path.startswith("/"):
        raise ValueError(f"JSON Pointer가 아니다: {path!r}")
    tokens = [unescape(t) for t in path[1:].split("/")]
    if tokens[0] not in ("input", "output"):
        raise ValueError(f"경로는 /input 또는 /output으로 시작해야 한다: {path}")
    node = doc
    for token in tokens[:-1]:
        if isinstance(node, list):
            node = node[int(token)]
        elif isinstance(node, dict):
            node = node[token]
        else:
            raise ValueError(f"경로를 따라갈 수 없다: {path}")
    return node, tokens[-1]


def apply_patch(doc, ops):
    for op in ops:
        kind = op.get("op")
        if kind not in PATCH_OPS:
            raise ValueError(f"지원하지 않는 patch 연산: {kind!r}")
        parent, key = resolve_parent(doc, op.get("path"))
        if isinstance(parent, list):
            if kind == "add":
                if "value" not in op:
                    raise ValueError("add에는 value가 필요하다")
                if key == "-":
                    parent.append(op["value"])
                else:
                    index = int(key)
                    if not 0 <= index <= len(parent):
                        raise IndexError(f"배열 범위를 벗어났다: {op['path']}")
                    parent.insert(index, op["value"])
            else:
                index = int(key)
                if not 0 <= index < len(parent):
                    raise IndexError(f"배열 범위를 벗어났다: {op['path']}")
                if kind == "remove":
                    parent.pop(index)
                else:
                    if "value" not in op:
                        raise ValueError("replace에는 value가 필요하다")
                    parent[index] = op["value"]
        elif isinstance(parent, dict):
            if kind == "add":
                if "value" not in op:
                    raise ValueError("add에는 value가 필요하다")
                parent[key] = op["value"]
            else:
                if key not in parent:
                    raise KeyError(f"없는 키: {op['path']}")
                if kind == "remove":
                    del parent[key]
                else:
                    if "value" not in op:
                        raise ValueError("replace에는 value가 필요하다")
                    parent[key] = op["value"]
        else:
            raise ValueError(f"경로의 부모가 객체나 배열이 아니다: {op['path']}")
    return doc


def load_fixture(name):
    path = FIXTURE_DIR / f"{name}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def build_call(case):
    doc = apply_patch(copy.deepcopy(load_fixture(case["fixture"])), case.get("patch") or [])
    if "raw_output" in case:
        raw_output = case["raw_output"]
    else:
        raw_output = json.dumps(doc["output"], ensure_ascii=False)
    return doc["input"], raw_output


def test_golden_file_structure():
    assert isinstance(GOLDEN, dict), "golden_cases.yaml의 최상위는 매핑이어야 한다"
    assert isinstance(GOLDEN.get("cases"), list) and GOLDEN["cases"], "cases는 비어 있지 않은 리스트여야 한다"
    codes = GOLDEN.get("error_codes")
    assert isinstance(codes, list) and codes, "error_codes는 비어 있지 않은 리스트여야 한다"
    assert all(isinstance(c, str) and c for c in codes), "error_codes는 문자열이어야 한다"
    assert len(codes) == len(set(codes)), "error_codes에 중복이 있다"


def test_loader_case_keys():
    problems = []
    for i, case in enumerate(CASES):
        cid = case_id(i, case)
        if not isinstance(case, dict):
            problems.append(f"{cid}: 케이스가 매핑이 아니다")
            continue
        unknown = set(case) - ALLOWED_KEYS
        if unknown:
            problems.append(f"{cid}: 허용하지 않은 키 {sorted(unknown)}")
        missing = REQUIRED_KEYS - set(case)
        if missing:
            problems.append(f"{cid}: 필수 키 없음 {sorted(missing)}")
    assert not problems, "\n".join(problems)


def test_loader_case_values():
    problems = []
    known = set(ERROR_CODES)
    for i, case in enumerate(CASES):
        if not isinstance(case, dict):
            continue
        cid = case_id(i, case)
        if "name" in case and not (isinstance(case["name"], str) and case["name"]):
            problems.append(f"{cid}: name은 비어 있지 않은 문자열이어야 한다")
        if "fixture" in case and not (isinstance(case["fixture"], str) and case["fixture"]):
            problems.append(f"{cid}: fixture는 비어 있지 않은 문자열이어야 한다")
        if "expect_valid" in case and not isinstance(case["expect_valid"], bool):
            problems.append(f"{cid}: expect_valid는 true 또는 false여야 한다")
        if "raw_output" in case and not isinstance(case["raw_output"], str):
            problems.append(f"{cid}: raw_output은 문자열이어야 한다")
        if "patch" in case and not isinstance(case["patch"], list):
            problems.append(f"{cid}: patch는 리스트여야 한다")
        for key in ("must_include_errors", "must_not_include_errors"):
            if key not in case:
                continue
            value = case[key]
            if not isinstance(value, list) or not value:
                problems.append(f"{cid}: {key}는 비어 있지 않은 리스트여야 한다")
                continue
            for code in value:
                if code not in known:
                    problems.append(f"{cid}: {key}의 {code!r}는 error_codes에 없다")
        if case.get("expect_valid") is False and not case.get("must_include_errors"):
            problems.append(f"{cid}: expect_valid가 false면 must_include_errors가 필요하다")
        include = set(case.get("must_include_errors") or [])
        exclude = set(case.get("must_not_include_errors") or [])
        if include & exclude:
            problems.append(f"{cid}: 같은 코드가 must_include_errors와 must_not_include_errors에 모두 있다 {sorted(include & exclude)}")
    assert not problems, "\n".join(problems)


def test_loader_unique_names():
    names = [c.get("name") for c in CASES if isinstance(c, dict)]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    assert not duplicates, f"name 중복: {duplicates}"


def test_loader_fixtures_and_patches():
    problems = []
    for i, case in enumerate(CASES):
        if not isinstance(case, dict) or not isinstance(case.get("fixture"), str):
            continue
        cid = case_id(i, case)
        path = FIXTURE_DIR / f"{case['fixture']}.json"
        if not path.is_file():
            problems.append(f"{cid}: fixture 파일 없음 {path.relative_to(ROOT)}")
            continue
        try:
            doc = load_fixture(case["fixture"])
        except ValueError as exc:
            problems.append(f"{cid}: fixture JSON 오류 {exc}")
            continue
        if not isinstance(doc, dict) or "input" not in doc or ("output" not in doc and "raw_output" not in case):
            problems.append(f"{cid}: fixture에 input 또는 output이 없다")
            continue
        try:
            apply_patch(copy.deepcopy(doc), case.get("patch") or [])
        except Exception as exc:
            problems.append(f"{cid}: patch 적용 실패 {type(exc).__name__}: {exc}")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("case", CASES, ids=[case_id(i, c) for i, c in enumerate(CASES)])
def test_golden_case(case):
    if IMPORT_ERROR is not None:
        raise IMPORT_ERROR
    if VALIDATOR is None:
        pytest.skip(MISSING_REASON)

    pact_input, raw_output = build_call(case)
    result = VALIDATOR(pact_input, raw_output)

    assert isinstance(result, dict), f"결과는 매핑이어야 한다: {type(result).__name__}"
    assert isinstance(result.get("valid"), bool), "결과의 valid는 true 또는 false여야 한다"
    errors = result.get("errors")
    assert isinstance(errors, list), "결과의 errors는 리스트여야 한다"
    assert all(isinstance(e, dict) and "code" in e for e in errors), "errors의 각 항목에는 code가 있어야 한다"
    codes = {e["code"] for e in errors}

    if "expect_valid" in case:
        assert result["valid"] is case["expect_valid"], (
            f"expect_valid={case['expect_valid']} 인데 valid={result['valid']}, codes={sorted(codes)}"
        )
    if "must_include_errors" in case:
        missing = set(case["must_include_errors"]) - codes
        assert not missing, f"must_include_errors 누락 {sorted(missing)}, 실제 codes={sorted(codes)}"
    if "must_not_include_errors" in case:
        present = set(case["must_not_include_errors"]) & codes
        assert not present, f"must_not_include_errors 검출 {sorted(present)}, 실제 codes={sorted(codes)}"
