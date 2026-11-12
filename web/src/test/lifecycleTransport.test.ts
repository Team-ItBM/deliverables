import { afterEach, describe, expect, it, vi } from "vitest";
import { api, fetchTransport, setTransport, type TransportRequest } from "../api/client";
import { clearRoomStorage, keys, writeJSON } from "../lib/storage";

afterEach(() => vi.unstubAllGlobals());

describe("방·알림 수명주기 전송 계약", () => {
  it("인코딩한 방 경로와 권한, 현재 endpoint 범위를 전송하고 빈 204를 받는다", async () => {
    const seen: TransportRequest[] = [];
    setTransport(async (req) => {
      seen.push(req);
      return req.path.endsWith("/status")
        ? { status: 200, body: { subscribed: false, room_subscribed: true } }
        : { status: 204, body: null };
    });
    const scope = { role: "participant" as const, session_id: "session", endpoint: "https://push.test/device" };
    await api.deleteRoom("a b", "host-token");
    expect(await api.pushStatus("a b", scope)).toEqual({ subscribed: false, room_subscribed: true });
    await api.unsubscribePush("a b", scope);
    await api.pushStatus("a b", { role: "host", endpoint: scope.endpoint }, "host-token");
    expect(seen).toEqual([
      { method: "DELETE", path: "/api/rooms/a%20b", headers: { "X-Host-Token": "host-token" }, body: undefined },
      { method: "POST", path: "/api/rooms/a%20b/push-subscriptions/status", headers: {}, body: scope },
      { method: "DELETE", path: "/api/rooms/a%20b/push-subscriptions", headers: {}, body: scope },
      {
        method: "POST", path: "/api/rooms/a%20b/push-subscriptions/status",
        headers: { "X-Host-Token": "host-token" }, body: { role: "host", endpoint: scope.endpoint },
      },
    ]);
  });

  it("fetch도 DELETE의 JSON 본문과 빈 응답을 처리한다", async () => {
    const fetch = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetch);
    const body = { role: "host", endpoint: "https://push.test/device" };
    expect(await fetchTransport({ method: "DELETE", path: "/api/rooms/c/push-subscriptions", headers: {}, body }))
      .toEqual({ status: 204, body: null });
    expect(fetch).toHaveBeenCalledWith("/api/rooms/c/push-subscriptions", {
      method: "DELETE", headers: { Accept: "application/json", "Content-Type": "application/json" }, body: JSON.stringify(body),
    });
  });

  it("방 저장소 정리는 정확히 해당 방의 키만 지운다", () => {
    const removed = [keys.host("c"), keys.session("c"), keys.submitted("c"), keys.pending("c"),
      keys.push("c", "host"), keys.push("c", "participant"), keys.seen("c")];
    for (const area of ["local", "session"] as const) {
      for (const key of removed) writeJSON(area, key, true);
      writeJSON(area, keys.host("c-other"), "other-token");
      writeJSON(area, keys.push("other", "host"), true);
      writeJSON(area, keys.sound, false);
      writeJSON(area, "other.application", "keep");
    }
    clearRoomStorage("c");
    for (const storage of [localStorage, sessionStorage]) {
      for (const key of removed) expect(storage.getItem(key)).toBeNull();
      expect(storage.getItem(keys.host("c-other"))).toBe('"other-token"');
      expect(storage.getItem(keys.push("other", "host"))).toBe("true");
      expect(storage.getItem(keys.sound)).toBe("false");
      expect(storage.getItem("other.application")).toBe('"keep"');
    }
  });
});
