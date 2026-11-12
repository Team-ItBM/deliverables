import { Bell } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api/client";
import type { PushSubscriptionScope, PushSubscriptionStatus } from "../api/types";
import { keys, writeJSON } from "../lib/storage";
import { ErrorMessage, ICON } from "./ui";

const MOCK = import.meta.env.VITE_MOCK === "1";

function isIosBrowserTab(): boolean {
  const ua = navigator.userAgent;
  const ios = /iPhone|iPad|iPod/.test(ua) || (ua.includes("Macintosh") && navigator.maxTouchPoints > 1);
  const standalone =
    (navigator as Navigator & { standalone?: boolean }).standalone === true ||
    window.matchMedia?.("(display-mode: standalone)").matches;
  return ios && !standalone;
}

function pushSupported(): boolean {
  return "Notification" in window && "serviceWorker" in navigator && "PushManager" in window;
}

async function readyRegistration(): Promise<ServiceWorkerRegistration> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    return await Promise.race([
      (async () => {
        const registration = await navigator.serviceWorker.getRegistration();
        return registration?.active ? registration : navigator.serviceWorker.ready;
      })(),
      new Promise<never>((_, reject) => {
        timer = setTimeout(() => reject(new Error("service worker activation timed out")), 5000);
      }),
    ]);
  } finally {
    clearTimeout(timer);
  }
}

function b64ToBytes(b64: string): Uint8Array {
  const pad = "=".repeat((4 - (b64.length % 4)) % 4);
  const raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

/**
 * 브라우저 권한·구독과 서버의 방별 등록을 확인한 뒤 알림을 켜고 끈다.
 * 예전 로컬 boolean은 호환을 위해 쓰되 현재 상태의 근거로 사용하지 않는다.
 * 아이폰 Safari 탭에서는 홈 화면 앱에서만 웹 푸시가 되므로 안내 글만 보여 준다.
 */
export function PushOptIn({
  code,
  role,
  sessionId,
  hostToken,
}: {
  code: string;
  role: "host" | "participant";
  sessionId?: string;
  hostToken?: string | null;
}) {
  const [busy, setBusy] = useState(false);
  const [checking, setChecking] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [failedAction, setFailedAction] = useState<"check" | "enable" | "disable">("check");
  const [refresh, setRefresh] = useState(0);
  const [checked, setChecked] = useState<{
    identity: string;
    status: PushSubscriptionStatus;
    endpoint: string | null;
  } | null>(null);
  const identity = JSON.stringify([code, role, sessionId, hostToken]);
  const iosTab = !MOCK && isIosBrowserTab();
  const supported = MOCK || pushSupported();
  const denied = !MOCK && supported && Notification.permission === "denied";
  const authenticated = role === "host" ? Boolean(hostToken) : Boolean(sessionId);
  const current = checked?.identity === identity ? checked : null;
  const checkFailed = Boolean(error && failedAction === "check");

  useEffect(() => {
    const onVisible = () => {
      if (document.visibilityState === "visible" && !busy && !checking) setRefresh((n) => n + 1);
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, [busy, checking]);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    if (iosTab || !supported || denied || !authenticated) {
      setChecking(false);
      return;
    }
    setChecking(true);
    const check = async () => {
      try {
        let endpoint: string | null = MOCK ? "mock://push" : null;
        if (!MOCK && Notification.permission === "granted") {
          const reg = await readyRegistration();
          endpoint = (await reg.pushManager.getSubscription())?.endpoint ?? null;
        }
        const status = endpoint
          ? await api.pushStatus(
              code,
              { role, ...(sessionId ? { session_id: sessionId } : {}), endpoint },
              role === "host" ? hostToken : null
            )
          : { subscribed: false, room_subscribed: false };
        if (!cancelled) {
          writeJSON("local", keys.push(code, role), status.subscribed);
          setChecked({ identity, status, endpoint });
        }
      } catch {
        if (!cancelled) {
          setFailedAction("check");
          setError("알림 상태를 확인하지 못했어요. 다시 확인해 주세요.");
        }
      } finally {
        if (!cancelled) setChecking(false);
      }
    };
    void check();
    return () => {
      cancelled = true;
    };
  }, [code, role, sessionId, hostToken, identity, iosTab, supported, denied, authenticated, refresh]);

  if (iosTab) {
    return (
      <p className="t-body-sm secondary">
        아이폰에서는 홈 화면에 추가한 앱에서만 알림을 받을 수 있어요. 이 화면을 다시 열면 진행 상황을 볼 수 있어요.
      </p>
    );
  }
  if (!supported) return null;
  if (denied) {
    return <p className="t-body-sm secondary">알림이 꺼져 있어요. 이 화면을 다시 열면 진행 상황을 볼 수 있어요.</p>;
  }
  if (!authenticated) return null;

  const enable = async () => {
    if (busy || checking || checkFailed || !current) return;
    setBusy(true);
    setError(null);
    try {
      let subscription = { endpoint: "mock://push", keys: { p256dh: "mock", auth: "mock" } };
      if (!MOCK) {
        const perm = await Notification.requestPermission();
        if (perm !== "granted") {
          setError("알림을 허용하지 않았어요. 이 화면을 다시 열면 진행 상황을 볼 수 있어요.");
          return;
        }
        const reg = await readyRegistration();
        const { public_key } = await api.vapidKey();
        const sub = await reg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: b64ToBytes(public_key) as BufferSource,
        });
        const json = sub.toJSON();
        subscription = {
          endpoint: sub.endpoint,
          keys: { p256dh: json.keys?.p256dh ?? "", auth: json.keys?.auth ?? "" },
        };
      } else {
        await api.vapidKey();
      }
      await api.subscribePush(
        code,
        { role, ...(sessionId ? { session_id: sessionId } : {}), subscription },
        role === "host" ? hostToken : null
      );
      writeJSON("local", keys.push(code, role), true);
      setChecked({ identity, status: { subscribed: true, room_subscribed: true }, endpoint: subscription.endpoint });
    } catch {
      setFailedAction("enable");
      setError("알림을 켜지 못했어요. 이 화면을 다시 열면 진행 상황을 볼 수 있어요.");
    } finally {
      setBusy(false);
    }
  };

  const disable = async () => {
    if (busy || checking || checkFailed || !current?.endpoint || !current.status.room_subscribed) return;
    setBusy(true);
    setError(null);
    try {
      const scope: PushSubscriptionScope = {
        role,
        ...(sessionId ? { session_id: sessionId } : {}),
        endpoint: current.endpoint,
      };
      // 브라우저 구독 자체는 다른 방에서도 쓰므로 unsubscribe()하지 않는다.
      await api.unsubscribePush(code, scope, role === "host" ? hostToken : null);
      writeJSON("local", keys.push(code, "host"), false);
      writeJSON("local", keys.push(code, "participant"), false);
      setChecked({ ...current, status: { subscribed: false, room_subscribed: false } });
    } catch {
      setFailedAction("disable");
      setError("이 방 알림을 끄지 못했어요. 다시 시도해 주세요.");
    } finally {
      setBusy(false);
    }
  };

  const retry = failedAction === "check" ? () => setRefresh((n) => n + 1) : failedAction === "disable" ? disable : enable;

  return (
    <div className="stack-sm">
      {current?.status.subscribed ? (
        !checkFailed && <p className="t-body-sm secondary">{checking ? "알림 상태를 다시 확인하고 있어요." : "알림을 켰어요. 상태가 바뀌면 알려 드려요."}</p>
      ) : (
        <button type="button" className="btn btn-outline" onClick={enable} disabled={busy || checking || checkFailed || !current}>
          <Bell {...ICON} />
          {role === "host" ? "응답 완료·생성 알림 받기" : "결과가 공개되면 알림 받기"}
        </button>
      )}
      {current?.status.room_subscribed && (
        <button type="button" className="btn-text" onClick={disable} disabled={busy || checking || checkFailed}>
          이 방 알림 끄기
        </button>
      )}
      {!current && !error && <p className="t-body-sm secondary" role="status">알림 상태를 확인하고 있어요.</p>}
      {error && <ErrorMessage text={error} onRetry={retry} />}
    </div>
  );
}
