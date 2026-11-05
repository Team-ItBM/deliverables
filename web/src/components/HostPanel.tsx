import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { RoomView } from "../api/types";
import { inviteUrl } from "../lib/hostToken";
import { FAILURE_TEXT } from "../lib/status";
import { PushOptIn } from "./PushOptIn";
import { BottomBar, ConfirmSheet, CopyButton, Count, ErrorMessage } from "./ui";

/**
 * 방장 토큰이 있는 기기에서만 보이는 메뉴. 생성은 자동으로 다시 시도하지 않는다.
 * room 모드는 상태별 주 동작 하나를 아래 고정 영역에 둔다. 화면이 자기 주 동작을 가지면 ownPrimary로 알린다.
 * result 모드에서는 고정 영역을 결과 화면이 쓰므로 모든 조작을 보조 버튼으로 둔다.
 */
export function HostPanel({
  code,
  token,
  room,
  onChanged,
  mode = "room",
  ownPrimary = false,
  showStatus = true,
}: {
  code: string;
  token: string;
  room: RoomView;
  onChanged: () => void;
  mode?: "room" | "result";
  ownPrimary?: boolean;
  showStatus?: boolean;
}) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [confirmEarly, setConfirmEarly] = useState(false);
  const s = room.room_status;

  // 재생성 가능 여부는 서버 규칙(정상 결과 2개면 거절)과 같은 기준으로 판단한다.
  const [normalCount, setNormalCount] = useState<number | null>(null);
  useEffect(() => {
    if (s !== "ready" || mode !== "result") return;
    let cancelled = false;
    api
      .getResults(code, token)
      .then((l) => !cancelled && setNormalCount(l.results.filter((r) => r.state === "normal").length))
      .catch(() => !cancelled && setNormalCount(null));
    return () => {
      cancelled = true;
    };
  }, [code, token, s, mode]);
  const canRegenerate = normalCount !== null && normalCount < 2;

  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      setConfirmEarly(false);
      onChanged();
    } catch (err) {
      setError(err);
      setConfirmEarly(false);
    } finally {
      setBusy(false);
    }
  };

  const canGenerate = s === "open" && room.scenario_status === "ready";
  const noResponses = room.submitted_count === 0;
  const inBar = mode === "room";

  const generateButton = (primary: boolean) => (
    <button
      type="button"
      className={`btn ${primary ? "btn-primary" : "btn-secondary"}`}
      disabled={busy || noResponses}
      onClick={() => setConfirmEarly(true)}
    >
      지금까지 모인 응답으로 만들기
    </button>
  );
  const retryButton = (primary: boolean) => (
    <button
      type="button"
      className={`btn ${primary ? "btn-primary" : "btn-secondary"}`}
      disabled={busy}
      onClick={() => run(() => api.retry(code, token))}
    >
      같은 응답으로 다시 시도
    </button>
  );

  return (
    <section className="card" aria-labelledby="host-panel-title">
      <h2 id="host-panel-title" className="t-label-md">
        방장 메뉴
      </h2>
      {showStatus && s === "failed" && room.failure_reason && <p className="secondary">{FAILURE_TEXT[room.failure_reason]}</p>}
      {showStatus && <Count label="제출(나 포함)" value={room.submitted_count} total={room.party_size} />}
      {canGenerate && noResponses && <p className="disabled-reason">한 명 이상 답하면 지금 만들 수 있어요.</p>}
      {canGenerate && (!inBar || ownPrimary) && generateButton(false)}
      {s === "failed" && !inBar && retryButton(false)}
      {s === "ready" && !inBar && canRegenerate && (
        <button
          type="button"
          className="btn btn-secondary"
          disabled={busy}
          onClick={() => run(() => api.regenerate(code, token))}
        >
          같은 응답으로 한 번 더 만들기
        </button>
      )}
      <CopyButton text={inviteUrl(code)} label="초대 링크 복사" />
      {error !== null && <ErrorMessage error={error} />}
      <PushOptIn code={code} role="host" hostToken={token} />

      {inBar && canGenerate && !ownPrimary && <BottomBar>{generateButton(true)}</BottomBar>}
      {inBar && s === "failed" && <BottomBar>{retryButton(true)}</BottomBar>}
      {inBar && s === "ready" && (
        <BottomBar>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => navigate(`/r/${encodeURIComponent(code)}/result`, { state: { started: true } })}
          >
            협약서 보기
          </button>
        </BottomBar>
      )}

      {confirmEarly && (
        <ConfirmSheet
          title="지금까지 모인 응답으로 만들까요?"
          confirmLabel="이대로 만들기"
          cancelLabel="그만두기"
          busy={busy}
          onConfirm={() => run(() => api.generate(code, token))}
          onCancel={() => setConfirmEarly(false)}
        >
          <p>
            응답 <span className="t-numeral">{room.submitted_count}</span>건으로 만들어요. 만들기 시작하면 더는 답을 받지
            않아요.
          </p>
        </ConfirmSheet>
      )}
    </section>
  );
}
