"""문항 출력 검증기 골든 테스트.

tests/harness/scenario_cases.yaml의 케이스마다 validate_scenario_output을 한 번씩 실행한다.
케이스는 코드에 복사하지 않고 YAML에서 읽으며, 케이스 name을 테스트 id로 쓴다.
로더 검사는 검증기 구현 여부와 관계없이 항상 실행한다.
travel.scenarios를 찾을 수 없거나 validate_scenario_output이 없으면 케이스 테스트만 skip한다.
그 밖의 import 오류는 skip하지 않고 실패로 드러낸다.
"""

import copy
import importlib
import json
import re
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "tests" / "harness" / "scenario_cases.yaml"
FIXTURE_DIR = ROOT / "tests" / "harness" / "fixtures" / "scenario"
SCHEMA_PATH = ROOT / "src" / "travel" / "schemas" / "scenario_set.schema.json"

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
FIXTURE_KEYS = {"source", "input", "output"}

# §0-1이 정한 케이스 수. 케이스를 늘리거나 줄이면 사람이 승인하고 이 값도 함께 바꾼다.
EXPECTED_CASE_COUNT = 46
EXPECTED_V_COUNT = 12
EXPECTED_N_COUNT = 34
EXPECTED_BASELINE_FIXTURES = 8
NAME_PATTERN = re.compile(r"^(V|N)\d{2}_")

VALIDATOR = None
IMPORT_ERROR = None
MISSING_REASON = None
try:
    _scenarios_module = importlib.import_module("travel.scenarios")
except ModuleNotFoundError as exc:
    if exc.name in ("travel", "travel.scenarios"):
        MISSING_REASON = f"validate_scenario_output 없음: {exc.name} 모듈을 찾을 수 없다"
    else:
        IMPORT_ERROR = exc
except Exception as exc:
    IMPORT_ERROR = exc
else:
    VALIDATOR = getattr(_scenarios_module, "validate_scenario_output", None)
    if VALIDATOR is None:
        MISSING_REASON = "validate_scenario_output 없음: travel.scenarios에 함수가 정의되지 않았다"


def load_cases_file():
    with CASES_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


GOLDEN = load_cases_file()
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
    if len(tokens) < 2:
        raise ValueError(f"/input 또는 /output 자체는 바꿀 수 없다: {path}")
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
    """RFC 6902의 add, remove, replace를 순서대로 적용한다. 없는 경로나 범위 밖 인덱스는 예외로 낸다."""
    for op in ops:
        if not isinstance(op, dict):
            raise ValueError(f"patch 연산은 매핑이어야 한다: {op!r}")
        kind = op.get("op")
        if kind not in PATCH_OPS:
            raise ValueError(f"지원하지 않는 patch 연산: {kind!r}")
        parent, key = resolve_parent(doc, op.get("path"))
        if kind in ("add", "replace") and "value" not in op:
            raise ValueError(f"{kind}에는 value가 필요하다: {op['path']}")
        if isinstance(parent, list):
            if kind == "add":
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
                    parent[index] = op["value"]
        elif isinstance(parent, dict):
            if kind == "add":
                parent[key] = op["value"]
            else:
                if key not in parent:
                    raise KeyError(f"없는 키: {op['path']}")
                if kind == "remove":
                    del parent[key]
                else:
                    parent[key] = op["value"]
        else:
            raise ValueError(f"경로의 부모가 객체나 배열이 아니다: {op['path']}")
    return doc


def load_fixture(name):
    path = FIXTURE_DIR / f"{name}.json"
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def build_call(case):
    """fixture 깊은 복사본에 patch를 적용해 (scenario_input, raw_output)을 만든다."""
    doc = apply_patch(copy.deepcopy(load_fixture(case["fixture"])), case.get("patch") or [])
    if "raw_output" in case:
        raw_output = case["raw_output"]
    else:
        raw_output = json.dumps(doc["output"], ensure_ascii=False)
    return doc["input"], raw_output


def baseline_cases():
    return [c for c in CASES if isinstance(c, dict) and not c.get("patch") and "raw_output" not in c]


def test_cases_file_structure():
    assert isinstance(GOLDEN, dict), "scenario_cases.yaml의 최상위는 매핑이어야 한다"
    assert set(GOLDEN) == {"error_codes", "cases"}, f"최상위 키는 error_codes와 cases뿐이어야 한다: {sorted(GOLDEN)}"
    assert isinstance(GOLDEN.get("cases"), list) and GOLDEN["cases"], "cases는 비어 있지 않은 리스트여야 한다"
    codes = GOLDEN.get("error_codes")
    assert isinstance(codes, list) and codes, "error_codes는 비어 있지 않은 리스트여야 한다"
    assert all(isinstance(c, str) and c for c in codes), "error_codes는 문자열이어야 한다"
    assert len(codes) == len(set(codes)), "error_codes에 중복이 있다"
    assert len(codes) == 10, f"error_codes는 §0 오류 코드 10개여야 한다: {len(codes)}개"


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
        if "raw_output" in case and case.get("patch"):
            problems.append(f"{cid}: raw_output과 patch를 함께 쓰지 않는다")
        if "patch" in case and not (isinstance(case["patch"], list) and case["patch"]):
            problems.append(f"{cid}: patch는 비어 있지 않은 리스트여야 한다")
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
        if case.get("expect_valid") is True and "must_include_errors" in case:
            problems.append(f"{cid}: expect_valid가 true인 케이스에 must_include_errors를 두지 않는다")
        include = set(case.get("must_include_errors") or [])
        exclude = set(case.get("must_not_include_errors") or [])
        if include & exclude:
            problems.append(f"{cid}: 같은 코드가 must_include_errors와 must_not_include_errors에 모두 있다 {sorted(include & exclude)}")
    assert not problems, "\n".join(problems)


def test_loader_unique_names():
    names = [c.get("name") for c in CASES if isinstance(c, dict)]
    duplicates = sorted({n for n in names if names.count(n) > 1})
    assert not duplicates, f"name 중복: {duplicates}"


def test_loader_case_counts():
    """§0-1의 V01~V12, N01~N34 46개가 빠짐없이 있는지 이름 접두어로 센다."""
    problems = []
    v_count = n_count = 0
    for i, case in enumerate(CASES):
        if not isinstance(case, dict) or not isinstance(case.get("name"), str):
            continue
        cid = case_id(i, case)
        match = NAME_PATTERN.match(case["name"])
        if not match:
            problems.append(f"{cid}: name은 V01_ 또는 N01_ 형식의 ID로 시작해야 한다")
            continue
        if match.group(1) == "V":
            v_count += 1
            if case.get("expect_valid") is not True:
                problems.append(f"{cid}: V 케이스는 expect_valid가 true여야 한다")
        else:
            n_count += 1
            if case.get("expect_valid") is not False:
                problems.append(f"{cid}: N 케이스는 expect_valid가 false여야 한다")
    ids = [c["name"][:3] for c in CASES if isinstance(c, dict) and isinstance(c.get("name"), str) and NAME_PATTERN.match(c["name"])]
    duplicated_ids = sorted({x for x in ids if ids.count(x) > 1})
    if duplicated_ids:
        problems.append(f"ID 중복: {duplicated_ids}")
    expected_ids = {f"V{n:02d}" for n in range(1, EXPECTED_V_COUNT + 1)} | {f"N{n:02d}" for n in range(1, EXPECTED_N_COUNT + 1)}
    if set(ids) != expected_ids:
        problems.append(f"ID가 V01~V12, N01~N34와 다르다. 없음 {sorted(expected_ids - set(ids))}, 추가 {sorted(set(ids) - expected_ids)}")
    if len(CASES) != EXPECTED_CASE_COUNT:
        problems.append(f"케이스 수 {len(CASES)}개, 기대 {EXPECTED_CASE_COUNT}개")
    if (v_count, n_count) != (EXPECTED_V_COUNT, EXPECTED_N_COUNT):
        problems.append(f"V·N 개수 {v_count}·{n_count}개, 기대 {EXPECTED_V_COUNT}·{EXPECTED_N_COUNT}개")
    assert not problems, "\n".join(problems)


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
        if not isinstance(doc, dict) or set(doc) != FIXTURE_KEYS:
            problems.append(f"{cid}: fixture 최상위 키는 source, input, output이어야 한다")
            continue
        if not case.get("patch"):
            continue
        try:
            patched = apply_patch(copy.deepcopy(doc), case["patch"])
        except Exception as exc:
            problems.append(f"{cid}: patch 적용 실패 {type(exc).__name__}: {exc}")
            continue
        if patched == doc:
            problems.append(f"{cid}: patch를 적용해도 fixture가 바뀌지 않는다")
    assert not problems, "\n".join(problems)


def test_loader_baseline_fixtures_pass_schema():
    """patch·raw_output이 없는 기준 케이스의 fixture 8개가 모두 쓰이고, 그 output이 스키마 v2를 통과하는지 본다."""
    with SCHEMA_PATH.open(encoding="utf-8") as f:
        schema = json.load(f)
    validator = jsonschema.Draft7Validator(schema)
    problems = []
    names = [c.get("fixture") for c in baseline_cases()]
    on_disk = sorted(p.stem for p in FIXTURE_DIR.glob("*.json"))
    if len(names) != EXPECTED_BASELINE_FIXTURES or len(set(names)) != len(names):
        problems.append(f"기준 케이스의 fixture가 서로 다른 {EXPECTED_BASELINE_FIXTURES}개가 아니다: {names}")
    if sorted(set(names)) != on_disk:
        problems.append(f"기준 케이스의 fixture와 폴더의 fixture가 다르다: 케이스 {sorted(set(names))}, 폴더 {on_disk}")
    for name in names:
        if not isinstance(name, str) or not (FIXTURE_DIR / f"{name}.json").is_file():
            continue
        errors = [e.message for e in validator.iter_errors(load_fixture(name).get("output"))]
        if errors:
            problems.append(f"{name}: 스키마 v2 위반 {errors}")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("case", CASES, ids=[case_id(i, c) for i, c in enumerate(CASES)])
def test_scenario_case(case):
    if IMPORT_ERROR is not None:
        raise IMPORT_ERROR
    if VALIDATOR is None:
        pytest.skip(MISSING_REASON)

    scenario_input, raw_output = build_call(case)
    result = VALIDATOR(scenario_input, raw_output)

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
