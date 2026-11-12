import { ApiError, toApiError } from "./errors";
import type {
  CreateRoomResponse,
  ProfileInput,
  PushSubscriptionBody,
  PushSubscriptionScope,
  PushSubscriptionStatus,
  ResultsList,
  RoomView,
  SessionResponse,
  SharedResult,
  SubmissionBody,
  SubmissionResponse,
  Trip,
} from "./types";

export interface TransportRequest {
  method: "GET" | "POST" | "DELETE";
  path: string;
  headers: Record<string, string>;
  body?: unknown;
}
export interface TransportResponse {
  status: number;
  body: unknown;
}
export type Transport = (req: TransportRequest) => Promise<TransportResponse>;

export const fetchTransport: Transport = async (req) => {
  let res: Response;
  try {
    res = await fetch(req.path, {
      method: req.method,
      headers: {
        Accept: "application/json",
        ...(req.body !== undefined ? { "Content-Type": "application/json" } : {}),
        ...req.headers,
      },
      body: req.body !== undefined ? JSON.stringify(req.body) : undefined,
    });
  } catch {
    throw new ApiError(0, "network", "");
  }
  let body: unknown = null;
  const text = await res.text().catch(() => "");
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }
  }
  return { status: res.status, body };
};

let transport: Transport = fetchTransport;
export function setTransport(t: Transport): void {
  transport = t;
}

async function call<T>(
  method: "GET" | "POST" | "DELETE",
  path: string,
  opts: { body?: unknown; hostToken?: string | null; headers?: Record<string, string> } = {}
): Promise<T> {
  const headers: Record<string, string> = { ...(opts.headers ?? {}) };
  if (opts.hostToken) headers["X-Host-Token"] = opts.hostToken;
  const res = await transport({ method, path: `/api${path}`, headers, body: opts.body });
  if (res.status >= 200 && res.status < 300) return res.body as T;
  throw toApiError(res.status, res.body);
}

const room = (code: string) => `/rooms/${encodeURIComponent(code)}`;

export const api = {
  createRoom: (trip: Trip, participant_profiles: ProfileInput[]) =>
    call<CreateRoomResponse>("POST", "/rooms", { body: { trip, participant_profiles } }),
  getRoom: (code: string, hostToken?: string | null) => call<RoomView>("GET", room(code), { hostToken }),
  deleteRoom: (code: string, hostToken: string) => call<void>("DELETE", room(code), { hostToken }),
  createSession: (code: string, profile_id: string) =>
    call<SessionResponse>("POST", `${room(code)}/sessions`, { body: { profile_id } }),
  submit: (code: string, body: SubmissionBody, idempotencyKey: string) =>
    call<SubmissionResponse>("POST", `${room(code)}/submissions`, {
      body,
      headers: { "Idempotency-Key": idempotencyKey },
    }),
  generate: (code: string, hostToken: string) =>
    call<{ room_status: string; included_count: number }>("POST", `${room(code)}/generate`, { hostToken }),
  retry: (code: string, hostToken: string) => call<unknown>("POST", `${room(code)}/retry`, { hostToken }),
  regenerate: (code: string, hostToken: string) =>
    call<unknown>("POST", `${room(code)}/regenerate`, { hostToken }),
  getResult: (code: string) => call<SharedResult>("GET", `${room(code)}/result`),
  getResults: (code: string, hostToken: string) =>
    call<ResultsList>("GET", `${room(code)}/results`, { hostToken }),
  select: (code: string, resultId: string, hostToken: string) =>
    call<{ selected_result_id: string }>(
      "POST",
      `${room(code)}/results/${encodeURIComponent(resultId)}/select`,
      { hostToken }
    ),
  edit: (code: string, resultId: string, edits: { path: string; text: string }[], hostToken: string) =>
    call<SharedResult>("POST", `${room(code)}/results/${encodeURIComponent(resultId)}/edits`, {
      body: { edits },
      hostToken,
    }),
  // 응답 형태가 계약에 없다. {public_key}로 가정한다(README "계약에서 정하지 않은 것").
  vapidKey: () => call<{ public_key: string }>("GET", "/push/vapid-public-key"),
  subscribePush: (code: string, body: PushSubscriptionBody, hostToken?: string | null) =>
    call<{ subscription_id: string }>("POST", `${room(code)}/push-subscriptions`, { body, hostToken }),
  pushStatus: (code: string, body: PushSubscriptionScope, hostToken?: string | null) =>
    call<PushSubscriptionStatus>("POST", `${room(code)}/push-subscriptions/status`, { body, hostToken }),
  unsubscribePush: (code: string, body: PushSubscriptionScope, hostToken?: string | null) =>
    call<void>("DELETE", `${room(code)}/push-subscriptions`, { body, hostToken }),
};
