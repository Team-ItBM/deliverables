import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { setTransport, type TransportRequest } from "../api/client";
import { keys, writeJSON } from "../lib/storage";
import { Result } from "../pages/Result";


function visible(state: "visible" | "hidden") {
  Object.defineProperty(document, "visibilityState", { configurable: true, value: state });
  document.dispatchEvent(new Event("visibilitychange"));
}

beforeEach(() => { vi.useFakeTimers(); visible("visible"); });
afterEach(() => { vi.useRealTimers(); visible("visible"); vi.unstubAllGlobals(); delete (navigator as { serviceWorker?: unknown }).serviceWorker; });

const paper = {
  result_id: "r1", kind: "ai_original", source_result_id: null, label: null, draft: true,
  pact_status: "proposed", included_count: 1, excluded_names: [],
  clauses: [{ scenario_id: "q1", participant_names: ["민준"], action: "처음 문구", proposed_conditions: [] }],
  conditional_alternatives: [], unresolved_conditions: [],
};
const app = () => <MemoryRouter initialEntries={["/r/c/result"]}><Routes><Route path="/r/:code/result" element={<Result />} /></Routes></MemoryRouter>;

describe("참여자 결과 화면", () => {
  it("제출 세션으로 알림 상태를 확인해 결과 화면에서도 이 방 알림을 끈다", async () => {
    writeJSON("local", keys.submitted("c"), { session_id: "submitted-session", participant_id: "p1" });
    vi.stubGlobal("Notification", { permission: "granted" });
    vi.stubGlobal("PushManager", function PushManager() {});
    Object.defineProperty(navigator, "serviceWorker", { configurable: true, value: { ready: Promise.resolve({ pushManager: { getSubscription: async () => ({ endpoint: "https://push.example/device" }) } }) } });
    const requests: TransportRequest[] = [];
    setTransport(async (req) => {
      requests.push(req);
      if (req.path.endsWith("/push-subscriptions/status")) return { status: 200, body: { subscribed: true, room_subscribed: true } };
      if (req.method === "DELETE") return { status: 204, body: null };
      return { status: 200, body: paper };
    });
    render(app());
    await act(async () => {});
    const status = requests.find((req) => req.path.endsWith("/push-subscriptions/status"));
    expect(status?.body).toMatchObject({ role: "participant", session_id: "submitted-session" });
    fireEvent.click(screen.getByRole("button", { name: "이 방 알림 끄기" }));
    await act(async () => {});
    expect(requests.find((req) => req.method === "DELETE")?.body).toMatchObject({ role: "participant", session_id: "submitted-session" });
  });
});
