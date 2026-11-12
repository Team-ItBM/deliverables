import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setTransport, type TransportRequest } from "../api/client";
import type { PushSubscriptionStatus, RoomView } from "../api/types";
import { HostPanel } from "../components/HostPanel";
import { PushOptIn } from "../components/PushOptIn";
import { keys, readJSON, writeJSON } from "../lib/storage";

const endpoint = "https://push.test/device";
const enabledText = "알림을 켰어요. 상태가 바뀌면 알려 드려요.";
const enableHost = "응답 완료·생성 알림 받기";
const swDescriptor = Object.getOwnPropertyDescriptor(navigator, "serviceWorker");

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  if (swDescriptor) Object.defineProperty(navigator, "serviceWorker", swDescriptor);
  else Reflect.deleteProperty(navigator, "serviceWorker");
});
beforeEach(() => setTransport(async () => ({ status: 200, body: { subscribed: false, room_subscribed: false } })));

function browserPush(permission: NotificationPermission = "granted", subscribed = true) {
  const unsubscribe = vi.fn(async () => true);
  const subscription = { endpoint, unsubscribe, toJSON: () => ({ endpoint, keys: { p256dh: "p", auth: "a" } }) };
  const getSubscription = vi.fn(async () => subscribed ? subscription : null);
  const subscribe = vi.fn(async () => subscription);
  const requestPermission = vi.fn(async () => "granted");
  vi.stubGlobal("Notification", { permission, requestPermission });
  vi.stubGlobal("PushManager", class {});
  Object.defineProperty(navigator, "serviceWorker", {
    configurable: true, value: { ready: Promise.resolve({ pushManager: { getSubscription, subscribe } }) },
  });
  return { unsubscribe, getSubscription, subscribe, requestPermission };
}

function servePush(initial: PushSubscriptionStatus, failure?: "status" | "delete" | "register") {
  const seen: TransportRequest[] = [];
  setTransport(async (req) => {
    seen.push(req);
    if (req.path.endsWith("/status")) return { status: failure === "status" ? 503 : 200, body: initial };
    if (req.method === "DELETE") return { status: failure === "delete" ? 503 : 204, body: null };
    if (req.path.endsWith("vapid-public-key")) return { status: 200, body: { public_key: "YWJj" } };
    return { status: failure === "register" ? 503 : 201, body: { subscription_id: "push" } };
  });
  return seen;
}

function push(role: "host" | "participant" = "host", sessionId = "session") {
  return render(<PushOptIn code="c" role={role} hostToken={role === "host" ? "host-token" : undefined} sessionId={role === "participant" ? sessionId : undefined} />);
}

describe("방별 알림 상태", () => {
  it("예전 true도 실제 서버 미등록이면 끈 상태로 바로잡고 기존 등록 요청을 사용한다", async () => {
    const browser = browserPush();
    writeJSON("local", keys.push("c", "host"), true);
    const seen = servePush({ subscribed: false, room_subscribed: false });
    push();
    await waitFor(() => expect((screen.getByRole("button", { name: enableHost }) as HTMLButtonElement).disabled).toBe(false));
    expect(screen.queryByText(enabledText)).toBeNull();
    expect(readJSON("local", keys.push("c", "host"))).toBe(false);
    expect(browser.getSubscription).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: enableHost }));
    await screen.findByText(enabledText);
    expect(seen.find((req) => req.path.endsWith("/push-subscriptions") && req.method === "POST")?.body).toEqual({
      role: "host", subscription: { endpoint, keys: { p256dh: "p", auth: "a" } },
    });
    expect(readJSON("local", keys.push("c", "host"))).toBe(true);
  });

  it("로컬 false여도 현재 역할 등록이 있으면 켠 상태로 표시하고 방 전체 알림만 끈다", async () => {
    const browser = browserPush();
    writeJSON("local", keys.push("c", "host"), false);
    writeJSON("local", keys.push("c", "participant"), true);
    writeJSON("local", keys.push("other", "host"), true);
    const seen = servePush({ subscribed: true, room_subscribed: true });
    push();
    await screen.findByText(enabledText);
    expect(screen.queryByRole("button", { name: enableHost })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "이 방 알림 끄기" }));
    await screen.findByRole("button", { name: enableHost });
    expect(seen.find((req) => req.method === "DELETE")).toEqual({
      method: "DELETE", path: "/api/rooms/c/push-subscriptions", headers: { "X-Host-Token": "host-token" },
      body: { role: "host", endpoint },
    });
    expect(browser.unsubscribe).not.toHaveBeenCalled();
    expect(readJSON("local", keys.push("c", "host"))).toBe(false);
    expect(readJSON("local", keys.push("c", "participant"))).toBe(false);
    expect(readJSON("local", keys.push("other", "host"))).toBe(true);
  });

  it("현재 참여자 세션은 미등록이어도 이 방의 다른 역할·세션 등록을 끌 수 있다", async () => {
    browserPush();
    const seen = servePush({ subscribed: false, room_subscribed: true });
    push("participant", "new-session");
    await screen.findByRole("button", { name: "이 방 알림 끄기" });
    expect((screen.getByRole("button", { name: "결과가 공개되면 알림 받기" }) as HTMLButtonElement).disabled).toBe(false);
    expect(screen.queryByText(enabledText)).toBeNull();
    expect(seen[0]?.body).toEqual({ role: "participant", session_id: "new-session", endpoint });
    fireEvent.click(screen.getByRole("button", { name: "이 방 알림 끄기" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "이 방 알림 끄기" })).toBeNull());
    expect(seen.find((req) => req.method === "DELETE")?.body).toEqual({ role: "participant", session_id: "new-session", endpoint });
  });

  it("상태 조회 실패는 알림 꺼짐으로 단정하지 않고 다시 확인할 수 있다", async () => {
    browserPush();
    writeJSON("local", keys.push("c", "host"), true);
    servePush({ subscribed: false, room_subscribed: false }, "status");
    push();
    await screen.findByText("알림 상태를 확인하지 못했어요. 다시 확인해 주세요.");
    expect((screen.getByRole("button", { name: enableHost }) as HTMLButtonElement).disabled).toBe(true);
    expect(readJSON("local", keys.push("c", "host"))).toBe(true);
    servePush({ subscribed: true, room_subscribed: true });
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    await screen.findByText(enabledText);
  });

  it("알림 해제 실패 시 켠 상태와 로컬 기록을 유지하고 재시도한다", async () => {
    const browser = browserPush();
    servePush({ subscribed: true, room_subscribed: true }, "delete");
    push();
    await screen.findByText(enabledText);
    fireEvent.click(screen.getByRole("button", { name: "이 방 알림 끄기" }));
    await screen.findByText("이 방 알림을 끄지 못했어요. 다시 시도해 주세요.");
    expect(screen.getByText(enabledText)).toBeTruthy();
    expect(readJSON("local", keys.push("c", "host"))).toBe(true);
    servePush({ subscribed: true, room_subscribed: true });
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    await screen.findByRole("button", { name: enableHost });
    expect(browser.unsubscribe).not.toHaveBeenCalled();
  });

  it("다른 탭에서 끈 뒤 화면으로 돌아오면 브라우저 구독과 서버 상태를 다시 확인한다", async () => {
    const browser = browserPush();
    servePush({ subscribed: true, room_subscribed: true });
    push();
    await screen.findByText(enabledText);
    const seen = servePush({ subscribed: false, room_subscribed: false });
    fireEvent(document, new Event("visibilitychange"));
    await screen.findByRole("button", { name: enableHost });
    await waitFor(() => expect((screen.getByRole("button", { name: enableHost }) as HTMLButtonElement).disabled).toBe(false));
    expect(browser.getSubscription).toHaveBeenCalledTimes(2);
    expect(seen.filter((req) => req.path.endsWith("/status"))).toHaveLength(1);
    expect(screen.queryByText(enabledText)).toBeNull();
  });

  it("알림 변경 요청 중 화면 복귀는 상태 조회를 겹치지 않는다", async () => {
    browserPush();
    let finishDelete!: () => void;
    const deleting = new Promise<void>((resolve) => { finishDelete = resolve; });
    const seen: TransportRequest[] = [];
    setTransport(async (req) => {
      seen.push(req);
      if (req.method === "DELETE") {
        await deleting;
        return { status: 204, body: null };
      }
      return { status: 200, body: { subscribed: true, room_subscribed: true } };
    });
    push();
    await screen.findByText(enabledText);
    fireEvent.click(screen.getByRole("button", { name: "이 방 알림 끄기" }));
    fireEvent(document, new Event("visibilitychange"));
    expect(seen.filter((req) => req.path.endsWith("/status"))).toHaveLength(1);
    finishDelete();
    await screen.findByRole("button", { name: enableHost });
    expect(seen.filter((req) => req.path.endsWith("/status"))).toHaveLength(1);
  });

  it.each(["default", "denied"] as const)("브라우저 권한 %s이면 예전 true를 켠 상태로 표시하지 않는다", async (permission) => {
    const browser = browserPush(permission);
    writeJSON("local", keys.push("c", "host"), true);
    const seen = servePush({ subscribed: true, room_subscribed: true });
    push();
    if (permission === "default") await waitFor(() => expect((screen.getByRole("button", { name: enableHost }) as HTMLButtonElement).disabled).toBe(false));
    else expect(screen.getByText(/알림이 꺼져 있어요/)).toBeTruthy();
    expect(screen.queryByText(enabledText)).toBeNull();
    expect(seen).toHaveLength(0);
    expect(browser.getSubscription).not.toHaveBeenCalled();
  });

  it("브라우저 구독이 없으면 서버 상태 조회 없이 켤 수 있다", async () => {
    browserPush("granted", false);
    const seen = servePush({ subscribed: true, room_subscribed: true });
    push();
    await waitFor(() => expect((screen.getByRole("button", { name: enableHost }) as HTMLButtonElement).disabled).toBe(false));
    expect(seen).toHaveLength(0);
  });

  it("미지원 브라우저와 참여자 세션 없는 화면에서는 알림 제어를 노출하지 않는다", () => {
    const first = push();
    expect(screen.queryByRole("button")).toBeNull();
    first.unmount();
    browserPush();
    push("participant", "");
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("아이폰 브라우저 탭에는 홈 화면 안내만 보인다", () => {
    browserPush();
    vi.spyOn(navigator, "userAgent", "get").mockReturnValue("iPhone Safari");
    push();
    expect(screen.getByText(/홈 화면에 추가한 앱에서만/)).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });
});

const room: RoomView = { room_status: "open", scenario_status: "ready", party_size: 2, submitted_count: 1, profiles: [] };
function hostPanel(overrides: Partial<RoomView> = {}) {
  return render(<MemoryRouter initialEntries={["/r/c"]}><Routes>
    <Route path="/r/c" element={<HostPanel code="c" token="host-token" room={{ ...room, ...overrides }} onChanged={() => {}} />} />
    <Route path="/" element={<p>첫 화면</p>} />
  </Routes></MemoryRouter>);
}

describe("방장 방 삭제", () => {
  it.each([204, 404])("확인 시트에서만 삭제하고 %s이면 방 기록을 정리한 뒤 첫 화면으로 간다", async (status) => {
    const seen: TransportRequest[] = [];
    setTransport(async (req) => { seen.push(req); return { status, body: null }; });
    writeJSON("local", keys.host("c"), "host-token");
    writeJSON("session", keys.session("c"), "answer");
    writeJSON("local", keys.push("c", "participant"), true);
    writeJSON("local", keys.host("other"), "keep");
    hostPanel();
    fireEvent.click(screen.getByRole("button", { name: "방 삭제하기" }));
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(/모든 응답과 협약서가 사라지고 초대 링크/)).toBeTruthy();
    expect(within(dialog).getByText(/이미 저장한 협약서 이미지는 남아/)).toBeTruthy();
    expect(seen).toHaveLength(0);
    fireEvent.click(within(dialog).getByRole("button", { name: "그만두기" }));
    expect(seen).toHaveLength(0);
    fireEvent.click(screen.getByRole("button", { name: "방 삭제하기" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "방 삭제하기" }));
    await screen.findByText("첫 화면");
    expect(seen).toEqual([{ method: "DELETE", path: "/api/rooms/c", headers: { "X-Host-Token": "host-token" }, body: undefined }]);
    expect(localStorage.getItem(keys.host("c"))).toBeNull();
    expect(sessionStorage.getItem(keys.session("c"))).toBeNull();
    expect(localStorage.getItem(keys.push("c", "participant"))).toBeNull();
    expect(readJSON("local", keys.host("other"))).toBe("keep");
  });

  it.each([403, 409, 429, 503])("삭제 %s 실패 시 방장 권한과 응답 기록, 현재 화면을 보존한다", async (status) => {
    setTransport(async () => ({ status, body: { error: { code: "invalid_state", message: "x" } } }));
    writeJSON("local", keys.host("c"), "host-token");
    writeJSON("local", keys.submitted("c"), { session_id: "s" });
    hostPanel();
    fireEvent.click(screen.getByRole("button", { name: "방 삭제하기" }));
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "방 삭제하기" }));
    await screen.findByText("지금 단계에서는 할 수 없는 일이에요. 잠시 뒤 다시 확인해 주세요.");
    expect(screen.queryByText("첫 화면")).toBeNull();
    expect(readJSON("local", keys.host("c"))).toBe("host-token");
    expect(readJSON("local", keys.submitted("c"))).toEqual({ session_id: "s" });
  });

  it.each([
    { scenario_status: "preparing" as const },
    { room_status: "closed" as const },
    { room_status: "generating" as const },
  ])("문항·협약서 생성 중에는 삭제가 비활성화된다: %o", (overrides) => {
    hostPanel(overrides);
    expect((screen.getByRole("button", { name: "방 삭제하기" }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "방 삭제하기" }));
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
