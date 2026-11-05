// 오류는 언제나 글로 보여 준다(AC14). 서버 오류 형식은 {"error": {"code", "message"}}다(§0-A 4).

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
  /** 서버가 요청을 받고 확정적으로 거절했는지. 네트워크·429·5xx는 결과를 알 수 없다. */
  get definitive(): boolean {
    return this.status >= 400 && this.status < 500 && this.status !== 429 && this.code !== "network";
  }
}

const MESSAGES: Record<string, string> = {
  invalid_input: "입력한 값을 다시 확인해 주세요.",
  needs_information: "필요한 정보가 빠졌어요. 여행 정보와 이름을 확인해 주세요.",
  host_forbidden: "방장 링크로 들어온 기기에서만 할 수 있어요.",
  not_found: "방이나 결과를 찾지 못했어요. 링크를 다시 확인해 주세요.",
  room_closed: "응답이 마감됐어요. 더는 답을 보낼 수 없어요.",
  no_submissions: "아직 제출된 응답이 없어요. 한 명 이상 답한 뒤에 만들 수 있어요.",
  invalid_state: "지금 단계에서는 할 수 없는 일이에요. 잠시 뒤 다시 확인해 주세요.",
  regeneration_limit: "협약서는 한 번만 다시 만들 수 있어요.",
  session_used: "이 답변은 이미 제출됐어요. 새로 답하려면 이름을 다시 골라 주세요.",
  idempotency_conflict: "같은 제출이 다른 내용으로 다시 보내졌어요. 이름을 다시 골라 처음부터 답해 주세요.",
  edit_not_allowed: "문구만 고칠 수 있어요. 조항을 더하거나 빼거나, 적용 대상 이름을 바꿀 수는 없어요.",
  memo_quote: "응답 메모의 문장이 그대로 들어간 부분이 있어요. 다른 말로 바꿔 써 주세요.",
  render_failed: "협약서를 표시하지 못했어요. 잠시 뒤 다시 시도해 주세요.",
  rate_limited: "잠시 뒤 다시 시도해 주세요. 요청이 많아요.",
  network: "연결이 끊겼어요. 인터넷 연결을 확인하고 다시 시도해 주세요.",
  server_error: "서버에 문제가 생겼어요. 잠시 뒤 다시 시도해 주세요.",
};

export function errorText(err: unknown): string {
  if (err instanceof ApiError) {
    return MESSAGES[err.code] ?? (err.message || MESSAGES.server_error!);
  }
  return MESSAGES.server_error!;
}

export function isNotFound(err: unknown): boolean {
  return err instanceof ApiError && err.code === "not_found";
}

/** HTTP 응답을 ApiError로 바꾼다. WAF 차단·429처럼 JSON이 아닌 응답도 처리한다. */
export function toApiError(status: number, body: unknown): ApiError {
  const e = (body as { error?: { code?: unknown; message?: unknown } } | null)?.error;
  if (e && typeof e.code === "string") {
    return new ApiError(status, e.code, typeof e.message === "string" ? e.message : "");
  }
  if (status === 429 || status === 403) return new ApiError(status, "rate_limited", "");
  if (status >= 500) return new ApiError(status, "server_error", "");
  return new ApiError(status, "unknown", "");
}
