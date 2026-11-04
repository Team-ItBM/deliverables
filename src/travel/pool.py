"""문항 pool 로드와 원본 조회.

docs/ARCHITECTURE.md 2·3절의 `pool.py` 중 도구가 연결할 부분만 둔다.
`lookup_template(template_id)`는 src/travel/prompts/prepare_scenarios.md "필드와 함수 인자" 표의 함수다.
목록(`ScenarioIndexEntry`)은 `build_scenario_index()`가 만든다.
pool 문자열은 데이터로만 다루며, 그 내용이 조회 규칙을 바꾸지 않는다.
"""

import copy
import json
from pathlib import Path

POOL_PATH = Path(__file__).resolve().parent / "data" / "scenario_pool.json"

_pool = None


def load_pool():
    """pool 파일을 한 번 읽어 캐시한 객체를 돌려준다. 호출자는 이 객체를 수정하지 않는다."""
    global _pool
    if _pool is None:
        with POOL_PATH.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or not isinstance(data.get("pool_version"), int):
            raise ValueError("pool 파일에 정수 pool_version이 없다")
        items = data.get("scenario_pool")
        if not isinstance(items, list):
            raise ValueError("pool 파일에 scenario_pool 목록이 없다")
        ids = [item.get("template_id") for item in items]
        if len(ids) != len(set(ids)):
            raise ValueError("pool에 template_id 중복이 있다")
        _pool = data
    return _pool


def lookup_template(template_id):
    """template_id에 해당하는 pool 항목의 복사본을 돌려준다.

    pool에 없으면 KeyError, 문자열이 아니면 TypeError를 낸다.
    """
    if not isinstance(template_id, str):
        raise TypeError(f"template_id는 문자열이어야 한다: {type(template_id).__name__}")
    for item in load_pool()["scenario_pool"]:
        if item["template_id"] == template_id:
            return copy.deepcopy(item)
    raise KeyError(template_id)


def build_scenario_index():
    """pool의 목록(`ScenarioIndexEntry`) list를 새로 만들어 돌려준다.

    인자는 없다. 호출할 때마다 load_pool()을 부르고, pool 파일의 scenario_pool 순서대로
    항목마다 template_id, title, purpose, decision_key 네 필드만 담은 새 dict를 만든다.
    값은 원문 그대로 둔다. 반환한 list와 dict를 고쳐도 pool은 바뀌지 않는다.
    """
    return [
        {
            "template_id": item["template_id"],
            "title": item["title"],
            "purpose": item["purpose"],
            "decision_key": item["decision_key"],
        }
        for item in load_pool()["scenario_pool"]
    ]
