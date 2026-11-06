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

/**
 * 결과를 알 수 없는 제출. 키와 그 키로 보낸 본문을 함께 둔다. 새 탭에서도 같은 요청으로 확인해야 해서 localStorage에 둔다.
 * 성공, 충돌 해소, 명확한 거절 때 바로 지우고 24시간이 지나면 버린다. 본문은 다시 보낼 때만 쓰고 화면에 표시하지 않는다.
 */
export interface PendingSubmission {
  idempotency_key: string;
  body: SubmissionBody;
  expires_at: number;
}

const PENDING_TTL_MS = 24 * 60 * 60 * 1000;

/** 다른 작성 세션의 제출 결과를 아직 모른다. 현재 답은 보내지 않았고 초안도 그대로다. */
export class OtherSubmissionPending extends Error {}

/** 결과를 모르는 제출이 이 세션의 것인지 본다. 다른 세션의 것이면 그 제출을 먼저 확인해야 한다. */
export function isOwnPending(pending: PendingSubmission | null, sessionId: string | undefined): boolean {
  return pending !== null && pending.body.session_id === sessionId;
}

/** 보낸 본문의 답을 작성 상태로 옮긴다. 결과를 모르는 동안 확인 화면이 실제로 보낸 답을 보여 주게 한다. */
export function withSentAnswers(s: AnswerSession, pending: PendingSubmission): AnswerSession {
  const answers: AnswerSession["answers"] = {};
  for (const a of pending.body.answers) answers[a.scenario_id] = { option_id: a.option_id, memo: a.memo ?? "" };
  return { ...s, answers };
}

export function loadPending(code: string): PendingSubmission | null {
  const pending = readJSON<PendingSubmission>("local", keys.pending(code));
  if (pending && pending.expires_at <= Date.now()) {
    clearPending(code);
    return null;
  }
  return pending;
}
export function clearPending(code: string): void {
  remove("local", keys.pending(code));
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

function markSubmitted(code: string, sessionId: string, participantId: string): void {
  writeJSON("local", keys.submitted(code), { session_id: sessionId, participant_id: participantId } satisfies SubmittedInfo);
  // 이 탭의 초안이 다른 세션이면 남긴다. 그 답은 아직 제출되지 않았다.
  if (loadSession(code)?.session_id === sessionId) clearSession(code);
  clearPending(code);
}

/**
 * 보존한 요청을 그대로 보낸다. 같은 키의 다른 본문이 이미 저장됐다는 충돌은 처음 보낸 답이 저장됐다는 뜻이므로
 * 제출 완료로 끝낸다(null). 그 밖의 명확한 거절은 저장되지 않았다는 뜻이라 보존을 지운다.
 * 연결 끊김·429·5xx는 서버가 받았는지 알 수 없으므로 보존을 유지한다.
 */
async function sendPending(code: string, pending: PendingSubmission): Promise<SubmissionResponse | null> {
  try {
    const res = await api.submit(code, pending.body, pending.idempotency_key);
    markSubmitted(code, pending.body.session_id, res.participant_id);
    return res;
  } catch (err) {
    if (err instanceof ApiError && err.code === "idempotency_conflict") {
      markSubmitted(code, pending.body.session_id, "");
      return null;
    }
    if (err instanceof ApiError && err.definitive) clearPending(code);
    throw err;
  }
}

/** 작성 세션이 없거나 다른 세션인 화면에서 보존한 제출의 결과를 확인한다. */
export async function resendPending(code: string): Promise<SubmissionResponse | null> {
  const pending = loadPending(code);
  return pending ? sendPending(code, pending) : null;
}

/**
 * 제출한다. 이 세션의 결과를 알 수 없는 제출이 있으면 지금 초안이 아니라 그 요청을 다시 보낸다.
 * 다른 세션의 것이면 아무것도 보내지 않고 OtherSubmissionPending을 낸다. 그 요청의 성공을 현재 제출의 성공으로 처리하면 현재 답이 사라진다.
 * 서버가 확정적으로 거절한 경우(4xx, 429 제외)에만 키를 버린다.
 */
export async function submitSession(
  code: string,
  s: AnswerSession,
  persist: (next: AnswerSession) => void = (n) => saveSession(code, n)
): Promise<SubmissionResponse | null> {
  const kept = loadPending(code);
  if (kept && !isOwnPending(kept, s.session_id)) throw new OtherSubmissionPending();
  const withKey = kept ? { ...s, idempotency_key: kept.idempotency_key } : ensureIdempotencyKey(s);
  persist(withKey);
  const pending: PendingSubmission = kept ?? {
    idempotency_key: withKey.idempotency_key!,
    body: buildBody(withKey),
    expires_at: Date.now() + PENDING_TTL_MS,
  };
  writeJSON("local", keys.pending(code), pending);
  try {
    return await sendPending(code, pending);
  } catch (err) {
    if (err instanceof ApiError && err.definitive) {
      const { idempotency_key: _drop, ...rest } = withKey;
      void _drop;
      persist(rest);
    }
    throw err;
  }
}
