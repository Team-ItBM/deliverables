import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { mockTransport } from "../mock/server";
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
