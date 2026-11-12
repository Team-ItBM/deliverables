import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { mockTransport } from "../mock/server";
import type { ResultsList, SessionResponse, SharedResult } from "../api/types";
import { serializeSegments } from "../lib/editable";
import type { TransportRequest } from "../api/client";

beforeEach(() => { localStorage.clear(); vi.useFakeTimers(); });
afterEach(() => vi.useRealTimers());

async function call(method: TransportRequest["method"], path: string, body?: unknown, token?: string) {
  const response = mockTransport({ method, path: `/api${path}`, body, headers: token ? { "X-Host-Token": token } : {} });
  await vi.advanceTimersByTimeAsync(250);
  return response;
}

async function create() {
  const response = await call("POST", "/rooms", {
    trip: { destination: "제주", duration_days: 2, party_size: 2, relationship: "친구" },
    participant_profiles: [{ profile_id: "p1", display_name: "가" }, { profile_id: "p2", display_name: "나" }],
  });
  return response.body as { room_code: string; host_token: string };
}

it("모의 방도 생성 중 삭제를 거부하고 준비 후 삭제하면 다시 조회할 수 없다", async () => {
  const room = await create();
  const path = `/rooms/${room.room_code}`;
  expect((await call("DELETE", path)).status).toBe(403);
  expect((await call("DELETE", path, undefined, room.host_token)).status).toBe(409);
  await vi.advanceTimersByTimeAsync(2000);
  expect((await call("DELETE", path, undefined, room.host_token)).status).toBe(204);
  expect((await call("GET", path)).status).toBe(404);
});

it("모의 구독 해제는 같은 기기와 방의 모든 세션만 지운다", async () => {
  const first = await create();
  const other = await create();
  await vi.advanceTimersByTimeAsync(2000);
  const path = `/rooms/${first.room_code}`;
  const otherPath = `/rooms/${other.room_code}`;
  const session = await call("POST", `${path}/sessions`, { profile_id: "p1" });
  const sessionId = (session.body as { session_id: string }).session_id;
  const register = (endpoint: string, role = "host", session_id?: string) => ({ role, session_id, subscription: { endpoint, keys: {} } });
  await call("POST", `${path}/push-subscriptions`, register("mock://one"), first.host_token);
  await call("POST", `${path}/push-subscriptions`, register("mock://one", "participant", sessionId));
  await call("POST", `${path}/push-subscriptions`, register("mock://two"), first.host_token);
  await call("POST", `${otherPath}/push-subscriptions`, register("mock://one"), other.host_token);
  const scope = { role: "participant", session_id: sessionId, endpoint: "mock://one" };
  expect((await call("POST", `${path}/push-subscriptions/status`, scope)).body).toEqual({ subscribed: true, room_subscribed: true });
  expect((await call("DELETE", `${path}/push-subscriptions`, scope)).status).toBe(204);
  expect((await call("DELETE", `${path}/push-subscriptions`, scope)).status).toBe(204);
  expect((await call("POST", `${path}/push-subscriptions/status`, { role: "host", endpoint: "mock://one" }, first.host_token)).body).toEqual({ subscribed: false, room_subscribed: false });
  expect((await call("POST", `${path}/push-subscriptions/status`, { role: "host", endpoint: "mock://two" }, first.host_token)).body).toEqual({ subscribed: true, room_subscribed: true });
  expect((await call("POST", `${otherPath}/push-subscriptions/status`, { role: "host", endpoint: "mock://one" }, other.host_token)).body).toEqual({ subscribed: true, room_subscribed: true });
});

it("모의 편집 응답도 선택한 원본만 초안 표시를 해제한다", async () => {
  const room = await create();
  await vi.advanceTimersByTimeAsync(2000);
  const path = `/rooms/${room.room_code}`;
  const session = (await call("POST", `${path}/sessions`, { profile_id: "p1" })).body as SessionResponse;
  const submitting = mockTransport({ method: "POST", path: `/api${path}/submissions`, headers: { "Idempotency-Key": "first" }, body: {
    session_id: session.session_id,
    answers: session.scenarios.map((s) => ({ scenario_id: s.scenario_id, option_id: s.options[0]!.option_id })),
  } });
  await vi.advanceTimersByTimeAsync(250);
  expect((await submitting).status).toBe(201);
  expect((await call("POST", `${path}/generate`, {}, room.host_token)).status).toBe(202);
  await vi.advanceTimersByTimeAsync(2500);
  expect((await call("POST", `${path}/regenerate`, {}, room.host_token)).status).toBe(202);
  await vi.advanceTimersByTimeAsync(2500);
  const list = (await call("GET", `${path}/results`, undefined, room.host_token)).body as ResultsList;
  expect(list.results).toHaveLength(2);
  const chosen = list.results[0]!.result_id;
  expect((await call("POST", `${path}/results/${chosen}/select`, {}, room.host_token)).status).toBe(200);
  for (const original of list.results) {
    const editable = original.editable![0]!;
    const edit = await call("POST", `${path}/results/${original.result_id}/edits`, {
      edits: [{ path: editable.path, text: serializeSegments(editable.segments) + " 수정" }],
    }, room.host_token);
    expect(edit.status).toBe(201);
    expect((edit.body as SharedResult).draft).toBe(original.result_id !== chosen);
    const updated = (await call("GET", `${path}/results`, undefined, room.host_token)).body as ResultsList;
    expect(updated.results.find((r) => r.result_id === original.result_id)!.draft).toBe((edit.body as SharedResult).draft);
  }
});
