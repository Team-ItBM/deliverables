"""문항 단계 도구 루프와 Sol 클라이언트의 전송 계약(ARCHITECTURE 3·5절, 위임 기록 결정 39·42. 2026-11-05 사람 승인 케이스 8개).

실제 API 대신 httpx.MockTransport를 openai SDK에 끼워 요청 본문을 기록하고 미리 정한 응답을 돌려준다.
서버 계약 하니스(tests/test_server_*.py)와 결정 16은 건드리지 않는다. 여기서는 모델 출력의 의미를 판정하지 않는다.
"""

import json
import sys
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from travel import pool as pool_module  # noqa: E402
from travel.server.llm import LLMCallError  # noqa: E402
from travel.server.llm_openai import LLMConfig, OpenAIClient  # noqa: E402

CONFIG_PATH = ROOT / "config" / "llm.yaml"
MEMO = "메모표지 보라색 우산을 든 고양이 이야기"
NAME = "민준"
MODEL_INPUT = {
    "trip": {"destination": "제주", "duration_days": 3, "party_size": 2, "relationship": "친구"},
    "participant_profiles": [{"profile_id": "p1", "display_name": "친구1"}, {"profile_id": "p2", "display_name": "친구2"}],
    "requested_count": 6,
    "scenario_pool": [],
    "request": "다른 사람의 성향을 정하지 말고 서로 다른 장면을 골라줘.",
}
PACT_INPUT = {"participant_ids": ["A"], "scenarios": [], "responses": [{"response_id": "r1", "participant_id": "A",
              "scenario_id": "paid_activity", "option_id": "paid_activity_1", "memo": MEMO}],
              "request": "각자의 조건을 보존하는 추천 조항을 만들어줘."}
FINAL_TEXT = json.dumps({"status": "ready", "scenarios": []}, ensure_ascii=False)


def usage(input_tokens=100, output_tokens=20, cached=0):
    return {"input_tokens": input_tokens, "output_tokens": output_tokens, "total_tokens": input_tokens + output_tokens,
            "input_tokens_details": {"cached_tokens": cached, "cache_write_tokens": 0},
            "output_tokens_details": {"reasoning_tokens": 0}}


def response_body(output, status="completed", **extra):
    body = {"id": "resp_x", "object": "response", "created_at": 0, "model": "gpt-6.1-sol", "status": status,
            "output": output, "usage": usage(), "parallel_tool_calls": False, "tool_choice": "auto", "tools": []}
    body.update(extra)
    return body


def function_call(template_id, call_id="call_1"):
    return {"type": "function_call", "id": f"fc_{call_id}", "call_id": call_id, "name": "get_scenario_template",
            "arguments": json.dumps({"template_id": template_id}), "status": "completed"}


def reasoning_item(call_id="call_1"):
    return {"type": "reasoning", "id": f"rs_{call_id}", "summary": [], "encrypted_content": f"enc-{call_id}"}


def message(text=FINAL_TEXT, refusal=None):
    content = [{"type": "refusal", "refusal": refusal}] if refusal else [{"type": "output_text", "text": text, "annotations": []}]
    return {"type": "message", "id": "msg_1", "role": "assistant", "status": "completed", "content": content}


class FakeAPI:
    """미리 정한 응답을 순서대로 돌려주고 요청 본문을 기록한다. 항목은 dict(JSON 200), (status, headers, body) 또는 예외다."""

    def __init__(self, scripted):
        self.scripted = list(scripted)
        self.requests = []

    def handler(self, request):
        self.requests.append(json.loads(request.content.decode("utf-8")))
        item = self.scripted.pop(0)
        if isinstance(item, Exception):
            raise item
        if isinstance(item, tuple):
            status, headers, body = item
            return httpx.Response(status, headers=headers, json=body)
        return httpx.Response(200, json=item)

    def client(self, config=None):
        config = config or LLMConfig.load(CONFIG_PATH, root=ROOT)
        http = httpx.AsyncClient(transport=httpx.MockTransport(self.handler))
        return OpenAIClient(config, api_key="test-key", lookup=pool_module.lookup_template, http_client=http)


def run(coro):
    import asyncio

    return asyncio.run(coro)


def outputs_of(request, kind):
    return [item for item in request["input"] if item.get("type") == kind]


# (a) 도구 호출 → 결과 되돌림 → 최종 출력
def test_a_tool_call_round_trip():
    api = FakeAPI([response_body([reasoning_item(), function_call("paid_activity")]), response_body([message()])])
    result = run(api.client().generate("scenarios", MODEL_INPUT))
    assert len(api.requests) == 2
    second = api.requests[1]
    assert outputs_of(second, "reasoning")[0]["encrypted_content"] == "enc-call_1", "앞 차례의 추론 항목을 다시 넣지 않았다"
    assert outputs_of(second, "function_call")[0]["call_id"] == "call_1"
    returned = outputs_of(second, "function_call_output")
    assert len(returned) == 1 and returned[0]["call_id"] == "call_1"
    assert json.loads(returned[0]["output"]) == pool_module.lookup_template("paid_activity")
    assert result.raw_output == FINAL_TEXT and result.response_status == "completed"
    assert result.opened_template_ids == ["paid_activity"]
    assert result.usage["input_tokens"] == 200 and result.usage["output_tokens"] == 40 and result.usage["tool_calls"] == 1
    assert result.usage["cost_usd"] == pytest.approx(2 * (100 * 2.0 + 20 * 10.0) / 1e6)


# (b) 없는 ID는 not_found를 되돌리고 계속한다
def test_b_unknown_template_returns_not_found():
    api = FakeAPI([response_body([function_call("no_such_template")]),
                   response_body([function_call("paid_activity", "call_2")]), response_body([message()])])
    result = run(api.client().generate("scenarios", MODEL_INPUT))
    first_output = json.loads(outputs_of(api.requests[1], "function_call_output")[0]["output"])
    assert first_output["error_code"] == "not_found" and first_output["retryable"] is False
    assert result.opened_template_ids == ["paid_activity"]
    assert result.usage["tool_calls"] == 2


# (c) 12회 상한: 12번째 요청은 실행하지 않고 도구를 끈 뒤 최종 출력 1회
def test_c_tool_limit_disables_tools_then_one_final_request():
    ids = [t["template_id"] for t in pool_module.build_scenario_index()[:12]]
    scripted = [response_body([function_call(tid, f"call_{i}")]) for i, tid in enumerate(ids, 1)]
    scripted.append(response_body([message()]))
    api = FakeAPI(scripted)
    result = run(api.client().generate("scenarios", MODEL_INPUT))
    assert len(api.requests) == 13
    final = api.requests[12]
    assert "tools" not in final and "tool_choice" not in final, "최종 요청에 도구가 남아 있다"
    limit_output = json.loads(outputs_of(final, "function_call_output")[-1]["output"])
    assert limit_output["error_code"] == "limit"
    assert result.opened_template_ids == ids[:11], "11회만 실행해야 한다"
    assert result.usage["tool_calls"] == 12
    assert all("tools" in req for req in api.requests[:12])


# (d) incomplete·refusal은 response_status로 전달한다
def test_d_incomplete_and_refusal_statuses():
    api = FakeAPI([response_body([message()], status="incomplete", incomplete_details={"reason": "max_output_tokens"})])
    result = run(api.client().generate("scenarios", MODEL_INPUT))
    assert result.response_status == "incomplete"
    api = FakeAPI([response_body([message(refusal="답할 수 없어요")])])
    result = run(api.client().generate("pact", PACT_INPUT))
    assert result.response_status == "refusal"


# (e) 429 Retry-After, 타임아웃, 5xx → LLMCallError(kind, retry_after)
def test_e_transient_errors_become_call_errors():
    api = FakeAPI([(429, {"retry-after": "7"}, {"error": {"message": "slow down"}})])
    with pytest.raises(LLMCallError) as info:
        run(api.client().generate("pact", PACT_INPUT))
    assert info.value.kind == "rate_limited" and info.value.retry_after == 7.0
    api = FakeAPI([httpx.ReadTimeout("timed out")])
    with pytest.raises(LLMCallError) as info:
        run(api.client().generate("pact", PACT_INPUT))
    assert info.value.kind == "timeout" and info.value.retry_after is None
    api = FakeAPI([(503, {}, {"error": {"message": "down"}})])
    with pytest.raises(LLMCallError) as info:
        run(api.client().generate("pact", PACT_INPUT))
    assert info.value.kind == "server_error"
    api = FakeAPI([(400, {}, {"error": {"message": "bad schema", "code": "invalid_json_schema"}})])
    with pytest.raises(LLMCallError) as info:
        run(api.client().generate("pact", PACT_INPUT))
    assert info.value.kind == "server_error"


# (f) 전송 본문: strict:false 출력 형식, strict:true 도구, parallel_tool_calls:false, store:false, 전송부·스키마 일치
def test_f_request_body_contract():
    config = LLMConfig.load(CONFIG_PATH, root=ROOT)
    api = FakeAPI([response_body([message()])])
    run(api.client(config).generate("scenarios", MODEL_INPUT))
    req = api.requests[0]
    assert req["model"] == "gpt-6.1-sol"
    assert req["text"]["format"] == {"type": "json_schema", "name": "ScenarioSet", "strict": False,
                                     "schema": json.loads((ROOT / "src/travel/schemas/scenario_set.schema.json").read_text(encoding="utf-8"))}
    assert req["tools"] == [{"type": "function", "name": "get_scenario_template",
                             "description": req["tools"][0]["description"], "parameters": req["tools"][0]["parameters"],
                             "strict": True}]
    assert req["tools"][0]["parameters"]["required"] == ["template_id"]
    assert "enum" not in json.dumps(req["tools"][0]["parameters"])
    assert req["tool_choice"] == "auto" and req["parallel_tool_calls"] is False and req["store"] is False
    assert req["include"] == ["reasoning.encrypted_content"] and req["reasoning"] == {"effort": "low"}
    assert req["instructions"] == config.prompts["scenarios"]["body"]
    assert json.loads(req["input"][0]["content"]) == MODEL_INPUT


# (g) 로그와 usage에 메모·이름이 없다
def test_g_logs_and_usage_do_not_carry_private_text(capfd):
    capfd.readouterr()
    api = FakeAPI([response_body([function_call("paid_activity")]), response_body([message()])])
    model_input = dict(MODEL_INPUT, request=f"{NAME}의 메모: {MEMO}")
    result = run(api.client().generate("scenarios", model_input))
    captured = capfd.readouterr()
    for text in (captured.out, captured.err, json.dumps(result.usage, ensure_ascii=False)):
        assert MEMO not in text and NAME not in text
    assert "tool_call" in captured.out and "llm_response" in captured.out


# (h) 추천 단계는 도구 없이 1회 호출
def test_h_pact_single_call_without_tools():
    api = FakeAPI([response_body([message('{"status":"proposed"}')])])
    result = run(api.client().generate("pact", PACT_INPUT, repair_errors=[{"code": "json_invalid", "path": "", "detail": ""}]))
    assert len(api.requests) == 1
    req = api.requests[0]
    assert "tools" not in req and req["text"]["format"]["name"] == "PactRecommendation"
    assert req["instructions"].startswith("\n\n너는 여행 전 가상 장면에 답한 일행의 응답을")
    assert "json_invalid" in req["input"][1]["content"], "repair_errors를 두 번째 사용자 메시지로 보낸다"
    assert result.raw_output == '{"status":"proposed"}' and result.opened_template_ids == []
