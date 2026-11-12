import { act, fireEvent, render, renderHook, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { setTransport, type TransportRequest } from "../api/client";
import { keys, writeJSON } from "../lib/storage";
import { Result } from "../pages/Result";
import { usePolling } from "../lib/hooks";

vi.mock("html-to-image", () => ({ toBlob: async () => null }));

function visible(state: "visible" | "hidden") {
  Object.defineProperty(document, "visibilityState", { configurable: true, value: state });
  document.dispatchEvent(new Event("visibilitychange"));
}

beforeEach(() => { vi.useFakeTimers(); visible("visible"); });
afterEach(() => { vi.useRealTimers(); visible("visible"); vi.unstubAllGlobals(); delete (navigator as { serviceWorker?: unknown }).serviceWorker; });

describe("공개 결과 polling", () => {
  it("보이는 동안 갱신하고 숨겨지면 멈추며 돌아오면 바로 다시 읽는다", async () => {
    const fetcher = vi.fn().mockResolvedValue("result");
    const hook = renderHook(() => usePolling(fetcher, () => true, [], { visibleOnly: true }));
    await act(async () => {});
    expect(fetcher).toHaveBeenCalledTimes(1);
    await act(async () => { visible("hidden"); await vi.advanceTimersByTimeAsync(30_000); });
    expect(fetcher).toHaveBeenCalledTimes(1);
    await act(async () => visible("visible"));
    expect(fetcher).toHaveBeenCalledTimes(2);
    expect(hook.result.current.data).toBe("result");
    await act(async () => vi.advanceTimersByTimeAsync(3500));
    expect(fetcher).toHaveBeenCalledTimes(3);
  });

  it("삭제 응답은 기존 데이터를 지우고 polling과 visibility refresh를 멈춘다", async () => {
    const gone = new Error("404");
    const fetcher = vi.fn().mockResolvedValueOnce("old result").mockRejectedValue(gone);
    const hook = renderHook(() => usePolling(fetcher, () => true, [], { visibleOnly: true, stopOnError: (e) => e === gone }));
    await act(async () => {});
    expect(hook.result.current.data).toBe("old result");
    await act(async () => vi.advanceTimersByTimeAsync(3500));
    expect(hook.result.current.data).toBeNull();
    expect(hook.result.current.error).toBe(gone);
    await act(async () => { visible("hidden"); visible("visible"); await vi.advanceTimersByTimeAsync(30_000); });
    expect(fetcher).toHaveBeenCalledTimes(2);
  });
});

const paper = {
  result_id: "r1", kind: "ai_original", source_result_id: null, label: null, draft: true,
  pact_status: "proposed", included_count: 1, excluded_names: [],
  clauses: [{ scenario_id: "q1", participant_names: ["민준"], action: "처음 문구", proposed_conditions: [] }],
  conditional_alternatives: [], unresolved_conditions: [],
};
const app = () => <MemoryRouter initialEntries={["/r/c/result"]}><Routes><Route path="/r/:code/result" element={<Result />} /></Routes></MemoryRouter>;

describe("참여자 결과 화면", () => {
  it("선택과 편집을 polling으로 반영하고 삭제되면 이전 협약서와 반복 요청을 없앤다", async () => {
    let current = { ...paper };
    let gone = false;
    let requests = 0;
    Object.defineProperty(window, "matchMedia", { configurable: true, value: () => ({ matches: true }) });
    setTransport(async () => {
      requests += 1;
      return gone ? { status: 404, body: { error: { code: "not_found" } } } : { status: 200, body: current };
    });
    render(app());
    await act(async () => {});
    expect(screen.getAllByText("선택되지 않은 결과예요")).toHaveLength(2);
    current = { ...paper, result_id: "r2", draft: false };
    await act(async () => vi.advanceTimersByTimeAsync(3500));
    expect(screen.queryByText("선택되지 않은 결과예요")).toBeNull();
    current = { ...current, clauses: [{ ...paper.clauses[0]!, action: "방장이 고친 문구" }] };
    await act(async () => vi.advanceTimersByTimeAsync(4000));
    expect(screen.getAllByText("방장이 고친 문구")).toHaveLength(2);
    gone = true;
    await act(async () => vi.advanceTimersByTimeAsync(4500));
    expect(screen.getByRole("heading", { name: "방을 찾지 못했어요" })).toBeTruthy();
    expect(screen.queryByText("방장이 고친 문구")).toBeNull();
    const count = requests;
    await act(async () => { visible("hidden"); visible("visible"); await vi.advanceTimersByTimeAsync(60_000); });
    expect(requests).toBe(count);
  });

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
