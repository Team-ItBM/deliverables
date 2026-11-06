"""모델 호출 경계(§0-E 1).

서버는 `await llm_client.generate(stage, model_input, repair_errors=None) -> LLMResult`만 부른다.
stage는 "scenarios" 또는 "pact"다. 호출 실패는 LLMCallError(kind, retry_after)로 받는다.
실제 클라이언트(llm_openai.py)와 테스트의 재생 클라이언트가 이 경계를 구현한다.
문항 단계의 도구 루프는 실제 클라이언트 안에서만 돈다(위임 기록 결정 39).
"""

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Protocol

STAGES = ("scenarios", "pact")
RESPONSE_STATUSES = ("completed", "incomplete", "refusal")
CALL_ERROR_KINDS = ("timeout", "rate_limited", "server_error")


@dataclass
class LLMResult:
    """모델이 돌려준 최종 출력. raw_output은 검증기에 그대로 넘기는 문자열이다.

    opened_template_ids는 문항 단계에서 도구로 성공 조회한 template_id 목록이다(없으면 빈 목록).
    usage는 토큰 사용량 등 기록용 메타데이터다. 둘 다 재생 클라이언트는 채우지 않는다.
    """

    raw_output: str
    response_status: str = "completed"
    opened_template_ids: list = field(default_factory=list)
    usage: dict = field(default_factory=dict)


class LLMCallError(Exception):
    """호출 실패. kind는 timeout, rate_limited, server_error 중 하나다."""

    def __init__(self, kind, retry_after=None):
        super().__init__(kind)
        self.kind = kind
        self.retry_after = retry_after


class UsageMeter:
    """generate 한 번의 왕복 사용량을 모은다. 서버가 만들어 current_meter로 넘기고 클라이언트가 왕복마다 채운다.

    generate가 실패하거나 취소돼도 서버가 이 객체를 들고 있으므로, 이미 응답받은 왕복의 비용이 사라지지 않는다.
    프로세스가 죽으면 메모리와 함께 사라진다(ARCHITECTURE 5절 남은 위험).
    """

    def __init__(self):
        self.requests = 0
        self.reported = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cost_usd = 0.0

    def request_started(self):
        self.requests += 1

    def add(self, input_tokens, output_tokens, cost_usd):
        self.reported += 1
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cost_usd = round(self.cost_usd + cost_usd, 6)

    @property
    def status(self):
        """reported: 모든 요청의 사용량을 안다. partial: 일부만 안다. unknown: 하나도 모른다."""
        if self.reported == 0:
            return "unknown"
        return "reported" if self.reported == self.requests else "partial"


current_meter = ContextVar("llm_usage_meter", default=None)


class LLMClient(Protocol):
    async def generate(self, stage, model_input, repair_errors=None) -> LLMResult: ...
