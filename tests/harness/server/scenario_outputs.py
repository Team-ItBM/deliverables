"""문항 출력 도우미와 문항 fixture 읽기(§0-F, 결정 15).

기본 문항 재생은 ex1_ready 출력이다. 토큰 출력은 §0-1 profile_rendering 준비를 따른다.
scenarios/0/scene 첫 줄 맨 앞에 "{{profile:p1}}이/가 {{profile:p2}}은/는 {{profile:p3}}과/와 "를,
scenarios/0/options/0/label 맨 앞에 "{{profile:p2}} "를 붙인다(앞 하니스 머리말의 "<토큰> " 규칙).
"""

import copy
import json
from pathlib import Path

from .replay import Text

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_DIR = ROOT / "tests" / "harness" / "fixtures" / "scenario"

SCENE_TOKENS = ("{{profile:p1}}이/가", "{{profile:p2}}은/는", "{{profile:p3}}과/와")
LABEL_TOKEN = "{{profile:p2}}"
TEST_POOL_VERSION = 0


def load_fixture(name):
    with (FIXTURE_DIR / f"{name}.json").open(encoding="utf-8") as f:
        return json.load(f)


def ex1():
    return load_fixture("ex1_ready")


def ex1_output():
    return copy.deepcopy(ex1()["output"])


def token_output():
    output = ex1_output()
    first = output["scenarios"][0]
    lines = first["scene"].split("\n")
    lines[0] = " ".join(SCENE_TOKENS) + " " + lines[0]
    first["scene"] = "\n".join(lines)
    first["options"][0]["label"] = LABEL_TOKEN + " " + first["options"][0]["label"]
    return output


def raw(output):
    return json.dumps(output, ensure_ascii=False)


def scenario_item(output=None):
    """재생 대기열 항목. 기본은 ex1_ready 출력이다."""
    return Text(raw(ex1_output() if output is None else output))


def fixture_item(name):
    return Text(raw(load_fixture(name)["output"]))


def write_test_pool(path):
    """ex1_ready 입력의 scenario_pool(8개)을 서비스 pool 파일 형식({pool_version, scenario_pool})으로 쓴다."""
    data = {"pool_version": TEST_POOL_VERSION, "scenario_pool": copy.deepcopy(ex1()["input"]["scenario_pool"])}
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return Path(path)


def public_texts(output):
    """문항 공개 문구(scene, question, options.label). 토큰은 그대로 둔다."""
    texts = []
    for scenario in output.get("scenarios") or []:
        texts.extend([scenario["scene"], scenario["question"]])
        texts.extend(o["label"] for o in scenario["options"])
    return texts
