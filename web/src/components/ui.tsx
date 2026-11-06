import { ArrowLeft, CircleAlert, Copy, Check, Share2 } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { errorText } from "../api/errors";
import type { RoomView } from "../api/types";
import { useBackHandler, useHeaderBack } from "../lib/back";
import { STATUS_LINE_TEXT } from "../lib/status";

export const ICON = { size: 20, strokeWidth: 1.5, "aria-hidden": true } as const;

export function Header() {
  const back = useBackHandler();
  return (
    <header className="app-header">
      {back && (
        <button type="button" className="icon-btn" aria-label="뒤로" onClick={back}>
          <ArrowLeft {...ICON} />
        </button>
      )}
      <Link to="/" className="t-wordmark">
        도원결의
      </Link>
    </header>
  );
}

export function BottomBar({ children }: { children: ReactNode }) {
  return (
    <div className="bottom-bar">
      <div className="bottom-bar-inner">{children}</div>
    </div>
  );
}

/** 없는 방의 화면. 재시도로 풀리지 않으므로 다시 시도 버튼을 두지 않는다. */
export function RoomNotFound() {
  const navigate = useNavigate();
  useHeaderBack(() => navigate("/"));
  return (
    <main className="page">
      <div className="stack-sm">
        <h1 className="t-headline-lg">방을 찾지 못했어요</h1>
        <p className="secondary">링크가 맞는지 방장에게 확인해 주세요. 새 여행이라면 방을 새로 만들 수 있어요.</p>
      </div>
      <BottomBar>
        <Link className="btn btn-primary" to="/new">
          새 방 만들기
        </Link>
      </BottomBar>
    </main>
  );
}

export function ErrorMessage({
  error,
  text,
  onRetry,
  retryLabel = "다시 시도",
}: {
  error?: unknown;
  text?: string;
  onRetry?: () => void;
  retryLabel?: string;
}) {
  const msg = text ?? errorText(error);
  return (
    <div className="message-error" role="alert">
      <p className="message-error-line">
        <CircleAlert {...ICON} />
        <span>{msg}</span>
      </p>
      {onRetry && (
        <button type="button" className="btn btn-secondary" onClick={onRetry}>
          {retryLabel}
        </button>
      )}
    </div>
  );
}

/** 진행 상황 한 줄. 예: 제출 1 / 3 · 다른 동행을 기다리고 있어요 */
export function StatusLine({ room, host }: { room: Pick<RoomView, "room_status" | "submitted_count" | "party_size">; host?: boolean }) {
  return (
    <p className="status-line">
      {host ? "제출(나 포함)" : "제출"}{" "}
      <span className="num">
        {room.submitted_count} / {room.party_size}
      </span>{" "}
      · {STATUS_LINE_TEXT[room.room_status]}
    </p>
  );
}

async function copyText(text: string): Promise<boolean> {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text);
      return true;
    }
  } catch {
    /* 아래 방식으로 다시 시도 */
  }
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    const ok = document.execCommand("copy");
    document.body.removeChild(ta);
    return ok;
  } catch {
    return false;
  }
}

export function CopyButton({ text, label }: { text: string; label: string }) {
  const [state, setState] = useState<"idle" | "done" | "fail">("idle");
  return (
    <div className="stack-sm">
      <button
        type="button"
        className="btn btn-outline"
        onClick={async () => setState((await copyText(text)) ? "done" : "fail")}
      >
        {state === "done" ? <Check {...ICON} /> : <Copy {...ICON} />}
        {state === "done" ? "복사했어요" : label}
      </button>
      <p className="sr-only" aria-live="polite">
        {state === "done" ? `${label}: 복사했어요` : ""}
      </p>
      {state === "fail" && (
        <>
          <ErrorMessage text="복사하지 못했어요. 아래 주소를 길게 눌러 직접 복사해 주세요." />
          <p className="link-box">{text}</p>
        </>
      )}
    </div>
  );
}

/** 기기의 공유 시트로 링크를 보낸다. 공유를 못 하는 기기에서는 복사한다. */
export function ShareButton({
  data,
  shareLabel,
  copyLabel,
  secondary,
}: {
  data: ShareData;
  shareLabel: string;
  copyLabel: string;
  secondary?: boolean;
}) {
  const url = data.url ?? "";
  const [state, setState] = useState<"idle" | "copied" | "fail">("idle");
  const canShare = typeof navigator.share === "function";
  const onClick = async () => {
    if (canShare) {
      try {
        await navigator.share(data);
        return;
      } catch (err) {
        if ((err as { name?: string }).name === "AbortError") return;
      }
    }
    setState((await copyText(url)) ? "copied" : "fail");
  };
  return (
    <>
      {state === "fail" && (
        <>
          <ErrorMessage text="복사하지 못했어요. 아래 주소를 길게 눌러 직접 복사해 주세요." />
          <p className="link-box">{url}</p>
        </>
      )}
      <button type="button" className={`btn ${secondary ? "btn-outline" : "btn-primary"}`} onClick={onClick}>
        {state === "copied" ? <Check {...ICON} /> : canShare ? <Share2 {...ICON} /> : <Copy {...ICON} />}
        {state === "copied" ? "복사했어요" : canShare ? shareLabel : copyLabel}
      </button>
      <p className="sr-only" aria-live="polite">
        {state === "copied" ? `${copyLabel}: 복사했어요` : ""}
      </p>
    </>
  );
}

/** 되돌릴 수 없는 동작 앞에 올라오는 확인 시트. 포커스를 안에 가두고 닫으면 돌려준다. */
export function ConfirmSheet({
  title,
  children,
  confirmLabel,
  cancelLabel,
  busy,
  onConfirm,
  onCancel,
}: {
  title: string;
  children: ReactNode;
  confirmLabel: string;
  cancelLabel: string;
  busy?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const sheetRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    sheetRef.current?.querySelector("button")?.focus();
    return () => before?.focus?.();
  }, []);
  const onKey = (e: KeyboardEvent) => {
    if (e.key === "Escape") onCancel();
    if (e.key !== "Tab") return;
    const items = [...(sheetRef.current?.querySelectorAll("button") ?? [])];
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last?.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first?.focus();
    }
  };
  return (
    <div className="sheet-backdrop" onClick={onCancel}>
      <div
        ref={sheetRef}
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="sheet-title"
        onClick={(e) => e.stopPropagation()}
        onKeyDown={onKey}
      >
        <h2 id="sheet-title" className="t-headline-md">
          {title}
        </h2>
        <div className="secondary">{children}</div>
        <button type="button" className="btn btn-primary" disabled={busy} onClick={onConfirm}>
          {confirmLabel}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          {cancelLabel}
        </button>
      </div>
    </div>
  );
}
