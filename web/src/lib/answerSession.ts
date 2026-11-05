import { api } from "../api/client";
import { ApiError } from "../api/errors";
import type { Answer, SessionResponse, SubmissionBody, SubmissionResponse } from "../api/types";
import { keys, readJSON, remove, writeJSON } from "./storage";
import { uuid } from "./uuid";

/** 제출 전까지의 작성 상태. 본인 기기의 sessionStorage에만 두고 제출하면 지운다. */
export interface AnswerSession extends SessionResponse {
  profile_id: string;
  display_name: string;
  answers: Record<string, { option_id?: string; memo: string }>;
  step: number;
  idempotency_key?: string;
}

export interface SubmittedInfo {
  session_id: string;
  participant_id: string;
}

export function loadSession(code: string): AnswerSession | null {
  return readJSON<AnswerSession>("session", keys.session(code));
}
export function saveSession(code: string, s: AnswerSession): void {
  writeJSON("session", keys.session(code), s);
}
export function clearSession(code: string): void {
  remove("session", keys.session(code));
}
export function loadSubmitted(code: string): SubmittedInfo | null {
  return readJSON<SubmittedInfo>("local", keys.submitted(code));
}

export function buildBody(s: AnswerSession): SubmissionBody {
  const answers: Answer[] = s.scenarios.map((sc) => {
    const a = s.answers[sc.scenario_id];
    const out: Answer = { scenario_id: sc.scenario_id, option_id: a?.option_id ?? "" };
    if (a && a.memo.trim().length > 0) out.memo = a.memo;
    return out;
  });
  return { session_id: s.session_id, answers };
}

/** 작성 세션마다 한 번 만든 키를 재시도에도 그대로 쓴다. */
export function ensureIdempotencyKey(s: AnswerSession): AnswerSession {
  return s.idempotency_key ? s : { ...s, idempotency_key: uuid() };
}

/**
 * 제출한다. 서버가 확정적으로 거절한 경우(4xx, 429 제외)에만 키를 버린다.
 * 연결 끊김·429·5xx는 서버가 받았는지 알 수 없으므로 같은 키로 다시 보낸다.
 */
export async function submitSession(
  code: string,
  s: AnswerSession,
  persist: (next: AnswerSession) => void = (n) => saveSession(code, n)
): Promise<SubmissionResponse> {
  const withKey = ensureIdempotencyKey(s);
  persist(withKey);
  try {
    const res = await api.submit(code, buildBody(withKey), withKey.idempotency_key!);
    writeJSON("local", keys.submitted(code), {
      session_id: withKey.session_id,
      participant_id: res.participant_id,
    } satisfies SubmittedInfo);
    clearSession(code);
    return res;
  } catch (err) {
    if (err instanceof ApiError && err.definitive && err.code !== "idempotency_conflict") {
      const { idempotency_key: _drop, ...rest } = withKey;
      void _drop;
      persist(rest);
    }
    throw err;
  }
}
