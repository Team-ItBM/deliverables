import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { RoomView } from "../api/types";
import { FAILURE_TEXT, ROOM_STATUS_TEXT } from "../lib/status";
import { PushOptIn } from "./PushOptIn";
import { Count, ErrorMessage } from "./ui";

/** 방장 토큰이 있는 기기에서만 보이는 상태·조작. 생성은 자동으로 다시 시도하지 않는다. */
export function HostPanel({
  code,
  token,
  room,
  onChanged,
  showResultLink = true,
}: {
  code: string;
  token: string;
  room: RoomView;
  onChanged: () => void;
  showResultLink?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [confirmEarly, setConfirmEarly] = useState(false);

  const s = room.room_status;

  // 재생성 가능 여부는 서버 규칙(정상 결과 2개면 거절)과 같은 기준으로 판단한다.
  const [normalCount, setNormalCount] = useState<number | null>(null);
  useEffect(() => {
    if (s !== "ready") return;
    let cancelled = false;
    api
      .getResults(code, token)
      .then((l) => !cancelled && setNormalCount(l.results.filter((r) => r.state === "normal").length))
      .catch(() => !cancelled && setNormalCount(null));
    return () => {
      cancelled = true;
    };
  }, [code, token, s]);
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
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="card" aria-labelledby="host-panel-title">
      <h2 id="host-panel-title" className="t-label-md">
        방장 메뉴
      </h2>
      <p>{ROOM_STATUS_TEXT[s]}</p>
      {s === "failed" && room.failure_reason && <p className="secondary">{FAILURE_TEXT[room.failure_reason]}</p>}
      <Count label="제출" value={room.submitted_count} total={room.party_size} />

      {s === "open" && room.scenario_status === "ready" && !confirmEarly && (
        <>
          {room.submitted_count === 0 && (
            <p className="disabled-reason">한 명 이상 답하면 지금 만들 수 있어요.</p>
          )}
          <button
            type="button"
            className="btn btn-secondary"
            disabled={busy || room.submitted_count === 0}
            onClick={() => setConfirmEarly(true)}
          >
            지금까지 모인 응답으로 만들기
          </button>
        </>
      )}
      {s === "open" && confirmEarly && (
        <div className="stack-sm">
          <p>
            지금까지 모인 응답 <span className="t-numeral">{room.submitted_count}</span>건으로 만들어요. 만들기
            시작하면 더는 답을 받지 않아요.
          </p>
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy}
            onClick={() => run(() => api.generate(code, token))}
          >
            이대로 만들기
          </button>
          <button type="button" className="btn-text" onClick={() => setConfirmEarly(false)}>
            그만두기
          </button>
        </div>
      )}
      {s === "failed" && (
        <button
          type="button"
          className="btn btn-secondary"
          disabled={busy}
          onClick={() => run(() => api.retry(code, token))}
        >
          같은 응답으로 다시 시도
        </button>
      )}
      {s === "ready" && canRegenerate && (
        <button
          type="button"
          className="btn btn-secondary"
          disabled={busy}
          onClick={() => run(() => api.regenerate(code, token))}
        >
          같은 응답으로 한 번 더 만들기
        </button>
      )}
      {s === "ready" && showResultLink && (
        <Link className="btn-text" to={`/r/${encodeURIComponent(code)}/result`}>
          결과 보기
        </Link>
      )}
      {error !== null && <ErrorMessage error={error} />}
      <PushOptIn code={code} role="host" hostToken={token} />
    </section>
  );
}
