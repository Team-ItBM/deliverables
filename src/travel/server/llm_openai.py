"""Sol(OpenAI Responses API) 클라이언트와 문항 단계 도구 루프(ARCHITECTURE 3·5절, 위임 기록 결정 39·42).

- llm.py의 경계 `generate(stage, model_input, repair_errors=None) -> LLMResult`를 구현한다. 서버는 이 안의 도구 루프를 모른다.
- 요청 형태는 스파이크 2회차와 같다: `text.format = {type: json_schema, name, schema, strict: false}`, 도구는
  `type: function` + TOOL_DEFINITION + `strict: true`, `tool_choice: auto`, `parallel_tool_calls: false`, `store: false`,
  `include: ["reasoning.encrypted_content"]`, `reasoning: {effort}`.
- 문항 단계: 응답의 function_call마다 get_scenario_template을 실행해 function_call_output으로 되돌린다. 앞 차례의 출력 항목을
  입력에 다시 넣는다(store: false). 호출 수는 코드가 센다. 상한(12)번째 요청은 실행하지 않고 도구를 끈 뒤 최종 출력을 1회 요청한다.
- `status != completed`와 refusal은 response_status로 돌려 서버가 형식 오류 경로로 처리한다.
- 일시 오류는 LLMCallError(timeout | rate_limited | server_error)로 바꾼다. SDK의 자동 재시도는 끄고 서버가 재시도한다.
- 전송부 해시를 설정과 대조해 프롬프트가 버전 없이 바뀌는 것을 막는다.
- 로그·usage에는 토큰 수, 지연, template_id, 결과 코드만 쓴다. 모델 입출력 원문·메모·이름은 남기지 않는다.
"""

import hashlib
import json
import time
from pathlib import Path

import yaml

from travel.tools import scenario_tools

from .llm import LLMCallError, LLMResult, current_meter
from .logging import log

PROMPT_START = "<!-- prompt:start -->"
PROMPT_END = "<!-- prompt:end -->"
TOOL_LIMIT_MESSAGE = "도구 호출 상한에 닿았습니다. 지금까지 조회한 원본만으로 최종 출력을 만드세요."


def prompt_body(text):
    start = text.index(PROMPT_START) + len(PROMPT_START)
    end = text.index(PROMPT_END)
    return text[start:end]


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class LLMConfig:
    """config/llm.yaml. 경로는 저장소 루트 기준이다."""

    def __init__(self, data, root):
        self.data = data
        self.root = Path(root)
        self.model = data["model"]
        self.reasoning_effort = data.get("reasoning_effort", "low")
        self.store = bool(data.get("store", False))
        self.include = list(data.get("include") or [])
        self.parallel_tool_calls = bool(data.get("parallel_tool_calls", False))
        self.timeout_seconds = float(data.get("timeout_seconds", 90))
        self.tool_call_limit = int(data["tools"]["call_limit"])
        self.cost = data.get("cost") or {}
        self.prompts = {}
        for stage, spec in data["prompts"].items():
            body = prompt_body((self.root / spec["path"]).read_text(encoding="utf-8"))
            digest = sha256_text(body)
            if digest != spec["body_sha256"]:
                raise ValueError(f"{stage} 프롬프트 전송부 해시가 설정과 다르다: {digest[:12]}… (설정 {spec['body_sha256'][:12]}…). "
                                 f"프롬프트를 바꿨으면 prompt_version과 해시를 함께 올린다")
            schema = json.loads((self.root / spec["schema_path"]).read_text(encoding="utf-8"))
            self.prompts[stage] = {"body": body, "version": str(spec["version"]), "schema": schema,
                                   "schema_name": spec["schema_name"], "schema_version": str(spec["schema_version"])}

    @classmethod
    def load(cls, path, root=None):
        path = Path(path)
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return cls(data, root or path.resolve().parent.parent)

    def estimate_cost(self, usage):
        if not usage:
            return None
        details = getattr(usage, "input_tokens_details", None) or {}
        cached = getattr(details, "cached_tokens", None) if not isinstance(details, dict) else details.get("cached_tokens")
        cached = cached or 0
        input_tokens = (getattr(usage, "input_tokens", 0) or 0) - cached
        output_tokens = getattr(usage, "output_tokens", 0) or 0
        rate = self.cost
        return round(input_tokens * rate.get("input_per_million", 0) / 1e6
                     + cached * rate.get("cached_input_per_million", 0) / 1e6
                     + output_tokens * rate.get("output_per_million", 0) / 1e6, 6)


def tool_definition():
    return {"type": "function", **scenario_tools.TOOL_DEFINITION, "strict": True}


def _to_error(exc):
    """openai SDK 예외를 LLMCallError로 바꾼다."""
    import openai

    if isinstance(exc, openai.APITimeoutError):
        return LLMCallError("timeout", None)
    if isinstance(exc, openai.RateLimitError):
        retry_after = None
        headers = getattr(getattr(exc, "response", None), "headers", None)
        if headers is not None and headers.get("retry-after"):
            try:
                retry_after = float(headers.get("retry-after"))
            except ValueError:
                retry_after = None
        return LLMCallError("rate_limited", retry_after)
    if isinstance(exc, openai.APIConnectionError):
        return LLMCallError("server_error", None)
    if isinstance(exc, openai.APIStatusError):
        return LLMCallError("server_error", None)
    return None


class OpenAIClient:
    """실제 Sol 호출. lookup은 template_id -> pool 항목(KeyError면 없음)이며 서버의 pool 파일과 같은 자료를 쓴다."""

    def __init__(self, config, api_key, lookup=None, http_client=None, cost_guard=None):
        import openai

        self.config = config
        self.lookup = lookup
        self.cost_guard = cost_guard
        self._client = openai.AsyncOpenAI(api_key=api_key, max_retries=0, timeout=config.timeout_seconds,
                                          http_client=http_client)

    # ---- 경계

    async def generate(self, stage, model_input, repair_errors=None):
        if stage not in self.config.prompts:
            raise ValueError(f"모르는 단계 {stage}")
        if self.cost_guard is not None:
            await self.cost_guard(stage)
        spec = self.config.prompts[stage]
        items = [{"role": "user", "content": json.dumps(model_input, ensure_ascii=False)}]
        if repair_errors:
            items.append({"role": "user", "content": (
                "이전 출력은 다음 검증 오류로 거부됐다. 같은 입력으로 규칙을 지켜 다시 출력한다: "
                + json.dumps(repair_errors, ensure_ascii=False))})
        if stage == "scenarios":
            return await self._scenario_loop(spec, items)
        response = await self._request(spec, items, tools_on=False)
        return self._final(response, opened=[], tool_calls=0)

    # ---- 요청

    def request_kwargs(self, spec, items, tools_on):
        kwargs = {
            "model": self.config.model,
            "instructions": spec["body"],
            "input": items,
            "text": {"format": {"type": "json_schema", "name": spec["schema_name"], "schema": spec["schema"],
                                "strict": False}},
            "store": self.config.store,
            "reasoning": {"effort": self.config.reasoning_effort},
        }
        if self.config.include:
            kwargs["include"] = self.config.include
        if tools_on:
            kwargs["tools"] = [tool_definition()]
            kwargs["tool_choice"] = "auto"
            kwargs["parallel_tool_calls"] = self.config.parallel_tool_calls
        return kwargs

    async def _request(self, spec, items, tools_on):
        started = time.monotonic()
        meter = current_meter.get()
        if meter is not None:
            meter.request_started()
        try:
            response = await self._client.responses.create(**self.request_kwargs(spec, items, tools_on))
        except Exception as exc:
            error = _to_error(exc)
            if error is None:
                raise
            log("llm_call_error", kind=error.kind, retry_after=error.retry_after, error=type(exc).__name__)
            raise error from exc
        usage = response.usage
        if meter is not None and usage is not None:
            meter.add(getattr(usage, "input_tokens", 0) or 0, getattr(usage, "output_tokens", 0) or 0,
                      self.config.estimate_cost(usage) or 0.0)
        log("llm_response", model=response.model, status=response.status,
            latency_ms=int((time.monotonic() - started) * 1000),
            input_tokens=getattr(usage, "input_tokens", None), output_tokens=getattr(usage, "output_tokens", None),
            tools_on=tools_on)
        return response

    # ---- 응답 해석

    @staticmethod
    def _output_items(response):
        items = []
        for item in response.output or []:
            if hasattr(item, "model_dump"):
                items.append(item.model_dump(exclude_none=True, mode="json"))
            else:
                items.append(dict(item))
        return items

    @staticmethod
    def _final_text(items):
        texts = []
        refusal = False
        for item in items:
            if item.get("type") != "message":
                continue
            for part in item.get("content") or []:
                if part.get("type") == "output_text":
                    texts.append(part.get("text", ""))
                elif part.get("type") == "refusal":
                    refusal = True
        return "".join(texts), refusal

    def _usage(self, response, extra_usage=None, tool_calls=0):
        usage = response.usage
        total = {"model": response.model, "tool_calls": tool_calls,
                 "input_tokens": getattr(usage, "input_tokens", 0) or 0,
                 "output_tokens": getattr(usage, "output_tokens", 0) or 0,
                 "cost_usd": self.config.estimate_cost(usage) or 0.0}
        for prev in extra_usage or []:
            total["input_tokens"] += prev["input_tokens"]
            total["output_tokens"] += prev["output_tokens"]
            total["cost_usd"] = round(total["cost_usd"] + prev["cost_usd"], 6)
        return total

    def _final(self, response, opened, tool_calls, extra_usage=None):
        items = self._output_items(response)
        text, refusal = self._final_text(items)
        if response.status != "completed":
            status = "incomplete"
        elif refusal:
            status = "refusal"
        else:
            status = "completed"
        return LLMResult(raw_output=text, response_status=status, opened_template_ids=list(opened),
                         usage=self._usage(response, extra_usage, tool_calls))

    # ---- 도구 루프

    def _run_tool(self, arguments):
        try:
            args = json.loads(arguments) if isinstance(arguments, str) else arguments
        except ValueError:
            return {"error_code": "validation", "retryable": False, "message": "인자가 JSON이 아닙니다."}, None
        template_id = args.get("template_id") if isinstance(args, dict) else None
        if self.lookup is None:
            return scenario_tools.get_scenario_template(template_id), template_id
        if not isinstance(template_id, str) or template_id == "":
            return {"error_code": "validation", "retryable": False,
                    "message": "template_id는 비어 있지 않은 문자열이어야 합니다."}, template_id
        try:
            return self.lookup(template_id), template_id
        except KeyError:
            return {"error_code": "not_found", "retryable": False,
                    "message": "문항 목록에 없는 template_id입니다. 목록 안에서 다시 고르세요."}, template_id

    async def _scenario_loop(self, spec, items):
        opened = []
        usages = []
        tool_calls = 0
        tools_on = True
        while True:
            response = await self._request(spec, items, tools_on=tools_on)
            output = self._output_items(response)
            calls = [i for i in output if i.get("type") == "function_call"]
            if not calls or response.status != "completed":
                return self._final(response, opened, tool_calls, usages)
            usages.append(self._usage(response))
            items.extend(output)
            for call in calls:
                tool_calls += 1
                if tool_calls >= self.config.tool_call_limit:
                    log("tool_limit", tool_calls=tool_calls)
                    items.append({"type": "function_call_output", "call_id": call.get("call_id"),
                                  "output": json.dumps({"error_code": "limit", "retryable": False,
                                                        "message": TOOL_LIMIT_MESSAGE}, ensure_ascii=False)})
                    tools_on = False
                    continue
                started = time.monotonic()
                result, template_id = self._run_tool(call.get("arguments"))
                code = result.get("error_code", "ok") if isinstance(result, dict) and "error_code" in result else "ok"
                if code == "ok":
                    opened.append(template_id)
                log("tool_call", tool_call_id=call.get("call_id"), name=call.get("name"), template_id=template_id,
                    result_code=code, latency_ms=int((time.monotonic() - started) * 1000))
                items.append({"type": "function_call_output", "call_id": call.get("call_id"),
                              "output": json.dumps(result, ensure_ascii=False)})
            if not tools_on:
                response = await self._request(spec, items, tools_on=False)
                usages.append(self._usage(response))
                return self._final(response, opened, tool_calls, usages[:-1])


class CostGuard:
    """방당·일일 비용 한도(ARCHITECTURE 5절). llm_calls의 cost_usd 합으로 판단하고 넘으면 budget_exceeded를 낸다."""

    def __init__(self, pool_getter, clock, daily_cap_usd):
        self.pool_getter = pool_getter  # 앱 lifespan 뒤에 풀이 생기므로 호출 때 가져온다
        self.clock = clock
        self.daily_cap_usd = daily_cap_usd

    async def __call__(self, stage):
        pool = self.pool_getter()
        if pool is None or self.daily_cap_usd is None:
            return
        day_start = self.clock().replace(hour=0, minute=0, second=0, microsecond=0)
        async with pool.connection() as conn:
            cur = await conn.execute("SELECT coalesce(sum(cost_usd), 0) AS total FROM llm_calls WHERE created_at >= %s",
                                     (day_start,))
            total = float((await cur.fetchone())["total"])
        if total >= self.daily_cap_usd:
            log("budget_exceeded", scope="daily", total_usd=total)
            raise LLMCallError("budget_exceeded", None)
