"""문항 원본 조회 도구.

docs/ARCHITECTURE.md 3절 도구 표의 `get_scenario_template`이며, 연결 함수 `pool.lookup_template`을 호출한다.
인자와 반환된 pool 문자열은 데이터로만 다루며, 그 내용이 조회 규칙을 바꾸지 않는다(AGENTS.md 절대 규칙 4).
"""

from travel import pool

TOOL_NAME = "get_scenario_template"
TOOL_DESCRIPTION = (
    "문항 목록에서 후보를 고른 뒤, 각색하기 전에 그 문항의 원본 장면·질문·선택지·핵심 제약을 확인한다. "
    "목록에 없는 ID는 조회하지 않는다."
)


def _tool_error(error_code, message):
    return {"error_code": error_code, "retryable": False, "message": message}


def get_scenario_template(template_id):
    """문항 목록에서 후보를 고른 뒤, 각색하기 전에 그 문항의 원본 장면·질문·선택지·핵심 제약을 확인한다. 목록에 없는 ID는 조회하지 않는다."""
    if not isinstance(template_id, str) or template_id == "":
        return _tool_error("validation", "template_id는 비어 있지 않은 문자열이어야 합니다.")
    try:
        return pool.lookup_template(template_id)
    except KeyError:
        return _tool_error("not_found", "문항 목록에 없는 template_id입니다. 목록 안에서 다시 고르세요.")


TOOL_DEFINITION = {
    "name": TOOL_NAME,
    "description": TOOL_DESCRIPTION,
    "parameters": {
        "type": "object",
        "properties": {
            "template_id": {"type": "string"},
        },
        "required": ["template_id"],
        "additionalProperties": False,
    },
}
