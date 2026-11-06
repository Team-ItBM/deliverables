import { Bell } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";
import { keys, readJSON, writeJSON } from "../lib/storage";
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

function b64ToBytes(b64: string): Uint8Array {
  const pad = "=".repeat((4 - (b64.length % 4)) % 4);
  const raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

/**
 * 알림 켜기. 거부하거나 지원하지 않아도 화면에서 진행 상태를 볼 수 있다(SPEC 처리 정책 "알림").
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
  const [done, setDone] = useState(() => readJSON<boolean>("local", keys.push(code, role)) === true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (done) return <p className="t-body-sm secondary">알림을 켰어요. 상태가 바뀌면 알려 드려요.</p>;
  if (isIosBrowserTab() && !MOCK) {
    return (
      <p className="t-body-sm secondary">
        아이폰에서는 홈 화면에 추가한 앱에서만 알림을 받을 수 있어요. 이 화면을 다시 열면 진행 상황을 볼 수 있어요.
      </p>
    );
  }
  if (!pushSupported() && !MOCK) return null;
  if (!MOCK && Notification.permission === "denied") {
    return <p className="t-body-sm secondary">알림이 꺼져 있어요. 이 화면을 다시 열면 진행 상황을 볼 수 있어요.</p>;
  }

  const enable = async () => {
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
        const reg = await navigator.serviceWorker.ready;
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
      setDone(true);
    } catch {
      setError("알림을 켜지 못했어요. 이 화면을 다시 열면 진행 상황을 볼 수 있어요.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stack-sm">
      <button type="button" className="btn btn-outline" onClick={enable} disabled={busy}>
        <Bell {...ICON} />
        {role === "host" ? "응답 완료·생성 알림 받기" : "결과가 공개되면 알림 받기"}
      </button>
      {error && <ErrorMessage text={error} onRetry={enable} />}
    </div>
  );
}
