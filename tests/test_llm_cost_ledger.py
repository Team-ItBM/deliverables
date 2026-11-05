"""비용 장부와 호출 기록(PR #16 리뷰 3번·`llm_calls` 필드, ARCHITECTURE 5·8절).

2026-11-05 사람 승인. 실제 API 대신 test_llm_loop의 FakeAPI(httpx.MockTransport)로 "사용량 있는 정상 응답 뒤 503"을 만든다.
과금은 일어나지 않는다. 사용량을 모르는 실패는 usage_status로 구분하고 한도에는 넣지 않는다(사람 결정).
TEST_DATABASE_URL이 없으면 srv fixture가 skip한다.
"""

import asyncio
import json
import threading

import httpx

from harness.server import pact_outputs as po
from harness.server import scenario_outputs as so
from harness.server.api import default_profiles
from test_llm_loop import FakeAPI, function_call, message, reasoning_item, response_body, usage

from travel.server.jobs import input_hash
from travel.server.llm_openai import CostGuard

BIG = usage(input_tokens=100_000, output_tokens=20_000)  # 입력 $0.20 + 출력 $0.20 (config/llm.yaml 단가)
COST = 0.4
UNAVAILABLE = (503, {}, {"error": {"message": "unavailable"}})
TEMPLATE = "paid_activity"


def tool_turn(call_id="call_1"):
    return response_body([reasoning_item(call_id), function_call(TEMPLATE, call_id)], usage=BIG)


def final_turn():
    return response_body([message(so.raw(so.ex1_output()))], usage=BIG)


def scenario_rows(srv):
    return srv.sql("SELECT * FROM llm_calls WHERE stage = 'scenarios' ORDER BY created_at, retry_no")


def open_with(srv, api, **settings):
    return srv.open_app(replay=api.client(), **settings)


def test_mid_loop_failure_keeps_used_cost(srv):
    """리뷰 재현: 정상 응답 뒤 503을 재시도까지 반복해도 응답받은 왕복의 비용이 남는다."""
    api = FakeAPI([tool_turn(), UNAVAILABLE] * 3)
    app = open_with(srv, api)
    _, room = app.create_room(push_scenario=False)
    assert app.room(room)["scenario_status"] == "failed"
    rows = scenario_rows(srv)
    assert [r["error_kind"] for r in rows] == ["server_error"] * 3
    assert [r["usage_status"] for r in rows] == ["partial"] * 3
    assert [float(r["cost_usd"]) for r in rows] == [COST] * 3
    assert [r["input_tokens"] for r in rows] == [100_000] * 3
    total = srv.sql("SELECT sum(cost_usd) AS total FROM llm_calls")[0]["total"]
    assert float(total) == round(COST * 3, 6)


def test_room_cap_counts_failed_round_trips(srv):
    """실패 왕복의 비용이 방당 상한에 잡혀 다음 재시도를 막는다."""
    api = FakeAPI([tool_turn(), UNAVAILABLE] * 2)
    app = open_with(srv, api, room_cap_usd=0.5)
    _, room = app.create_room(push_scenario=False)
    assert app.room(room)["scenario_status"] == "failed"
    rows = scenario_rows(srv)
    assert [r["error_kind"] for r in rows] == ["server_error", "server_error", "budget_exceeded"]
    assert [r["usage_status"] for r in rows] == ["partial", "partial", "not_called"]
    assert len(api.requests) == 4, "상한에 닿은 뒤 모델을 더 불렀다"


def test_daily_cap_counts_failed_round_trips(srv):
    """실패 왕복의 비용이 일일 한도에 잡혀 다음 방의 호출을 막는다."""
    api = FakeAPI([tool_turn(), UNAVAILABLE] * 3)
    client = api.client()
    app = srv.open_app(replay=client)
    client.cost_guard = CostGuard(lambda: app.app.state.db, srv.clock, daily_cap_usd=1.0)
    _, first = app.create_room(push_scenario=False)
    assert app.room(first)["scenario_status"] == "failed"
    sent = len(api.requests)
    _, second = app.create_room(push_scenario=False)
    assert app.room(second)["scenario_status"] == "failed"
    assert len(api.requests) == sent, "일일 한도에 닿은 뒤 모델을 더 불렀다"


def test_unknown_usage_failure_is_marked_and_not_counted(srv):
    """사용량을 모르는 실패는 구분해 기록하고 비용 합에는 넣지 않는다."""
    api = FakeAPI([UNAVAILABLE] * 3)
    app = open_with(srv, api)
    app.create_room(push_scenario=False)
    rows = scenario_rows(srv)
    assert [r["usage_status"] for r in rows] == ["unknown"] * 3
    assert [r["cost_usd"] for r in rows] == [None] * 3
    assert srv.sql("SELECT coalesce(sum(cost_usd), 0) AS total FROM llm_calls")[0]["total"] == 0


def test_timeout_mid_loop_keeps_used_cost(srv):
    api = FakeAPI([tool_turn(), httpx.ReadTimeout("late")] * 3)
    app = open_with(srv, api)
    app.create_room(push_scenario=False)
    rows = scenario_rows(srv)
    assert [r["error_kind"] for r in rows] == ["timeout"] * 3
    assert [float(r["cost_usd"]) for r in rows] == [COST] * 3


class HangingAPI(FakeAPI):
    """첫 왕복은 응답하고 두 번째 왕복은 응답하지 않는다."""

    def __init__(self):
        super().__init__([tool_turn()])
        self.hanging = threading.Event()

    async def async_handler(self, request):
        if self.scripted:
            return self.handler(request)
        self.hanging.set()
        await asyncio.sleep(3600)

    def client(self, config=None):
        from test_llm_loop import CONFIG_PATH, ROOT, LLMConfig, OpenAIClient, pool_module

        http = httpx.AsyncClient(transport=httpx.MockTransport(self.async_handler))
        return OpenAIClient(config or LLMConfig.load(CONFIG_PATH, root=ROOT), api_key="test-key",
                            lookup=pool_module.lookup_template, http_client=http)


def test_stopped_job_keeps_used_cost(srv):
    """작업 한도로 멈춘 호출도 응답받은 왕복의 비용을 남긴다."""
    api = HangingAPI()
    app = open_with(srv, api)
    _, room = app.create_room(push_scenario=False, wait=False)
    assert api.hanging.wait(5), "두 번째 왕복이 시작되지 않았다"
    srv.clock.set_after(srv.clock(), 300)
    app.enforce_deadlines()
    app.join()
    assert app.room(room)["scenario_status"] == "failed"
    rows = scenario_rows(srv)
    assert [(r["error_kind"], r["usage_status"]) for r in rows] == [("stopped", "partial")]
    assert float(rows[0]["cost_usd"]) == COST


def test_successful_loop_records_all_fields(srv):
    api = FakeAPI([tool_turn(), final_turn()])
    app = open_with(srv, api)
    _, room = app.create_room(push_scenario=False)
    assert app.room(room)["scenario_status"] == "ready"
    row = scenario_rows(srv)[0]
    assert row["usage_status"] == "reported"
    assert float(row["cost_usd"]) == COST * 2
    assert row["output_status"] == "ready"
    assert row["violation_codes"] == []
    assert row["tool_call_count"] == 1
    selected = [s["template_id"] for s in so.ex1_output()["scenarios"]]
    assert row["unopened_selection"] == [t for t in selected if t != TEMPLATE]
    assert len(row["input_hash"]) == 64


def test_pact_rows_link_call_to_verdict(srv):
    """재요청 흐름: 1회차 행에 위반 코드, 2회차 행에 통과가 남고 입력 해시는 실제 입력과 같다."""
    app = srv.app
    _, room = app.create_room(profiles=default_profiles(party_size=2))
    app.replay.push("pact", po.pact_item("extra_key"), po.pact_item())
    for profile in room.profiles:
        assert app.submit_new(room, profile["profile_id"]).resp.status_code == 201
    app.join()
    rows = srv.sql("SELECT * FROM llm_calls WHERE stage = 'pact' ORDER BY created_at, repair")
    assert [r["repair"] for r in rows] == [False, True]
    assert rows[0]["violation_codes"], "1회차 위반 코드가 비어 있다"
    assert all(isinstance(c, str) for c in rows[0]["violation_codes"])
    assert rows[1]["violation_codes"] == []
    assert rows[1]["output_status"] == json.loads(po.pact_raw(app.replay.calls_for("pact")[1].model_input))["status"]
    expected = input_hash(app.replay.calls_for("pact")[0].model_input)
    assert [r["input_hash"] for r in rows] == [expected, expected]
    assert rows[0]["unopened_selection"] is None


def test_output_status_keeps_only_schema_values(srv):
    """모델이 낸 임의 문자열을 표에 옮기지 않는다."""
    app = srv.app
    app.replay.push("scenarios", '{"status": "메모표지"}', "not json")
    app.create_room(push_scenario=False)
    rows = scenario_rows(srv)
    assert [r["output_status"] for r in rows] == [None, None]
    assert all(r["violation_codes"] for r in rows)


def test_incomplete_response_is_recorded_as_violation(srv):
    from harness.server.replay import Text

    app = srv.app
    app.replay.push("scenarios", Text("{}", response_status="incomplete"), Text("{}", response_status="incomplete"))
    app.create_room(push_scenario=False)
    rows = scenario_rows(srv)
    assert [r["response_status"] for r in rows] == ["incomplete", "incomplete"]
    assert rows[0]["violation_codes"] == ["response_incomplete"]
