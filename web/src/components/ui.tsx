import { CircleAlert, Copy, Check } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { errorText } from "../api/errors";

export const ICON = { size: 20, strokeWidth: 1.5, "aria-hidden": true } as const;

export function Header() {
  return (
    <header className="app-header">
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
  return (
    <main className="page">
      <div className="stack-sm">
        <h1 className="t-headline-lg">방을 찾지 못했어요</h1>
        <p className="secondary">링크가 맞는지 방장에게 확인해 주세요. 새 여행이라면 방을 새로 만들 수 있어요.</p>
      </div>
      <BottomBar>
        <Link className="btn btn-primary" to="/">
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

export function Count({ label, value, total }: { label: string; value: number; total?: number }) {
  return (
    <p className="count-label">
      {label} <span className="num">{total === undefined ? value : `${value} / ${total}`}</span>
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

export function CopyButton({ text, label, primary }: { text: string; label: string; primary?: boolean }) {
  const [state, setState] = useState<"idle" | "done" | "fail">("idle");
  return (
    <div className="stack-sm">
      <button
        type="button"
        className={`btn ${primary ? "btn-primary" : "btn-secondary"}`}
        onClick={async () => setState((await copyText(text)) ? "done" : "fail")}
      >
        {state === "done" ? <Check {...ICON} /> : <Copy {...ICON} />}
        {state === "done" ? "복사했어요" : label}
      </button>
      <p className="sr-only" aria-live="polite">
        {state === "done" ? `${label}: 복사했어요` : ""}
      </p>
      {state === "fail" && (
        <ErrorMessage text="복사하지 못했어요. 아래 주소를 길게 눌러 직접 복사해 주세요." />
      )}
    </div>
  );
}
