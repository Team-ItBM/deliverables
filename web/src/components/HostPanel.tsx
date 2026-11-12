import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import type { RoomView } from "../api/types";
import { inviteUrl } from "../lib/hostToken";
import { FAILURE_TEXT } from "../lib/status";
import { clearRoomStorage } from "../lib/storage";
import { OpenPact } from "./OpenPact";
import { PushOptIn } from "./PushOptIn";
import { BottomBar, ConfirmSheet, CopyButton, ErrorMessage } from "./ui";

/**
 * 방장 토큰이 있는 기기에서만 보이는 메뉴. 생성은 자동으로 다시 시도하지 않는다.
 * room 모드는 상태별 주 동작 하나를 아래 고정 영역에 둔다. 화면이 자기 주 동작을 가지면 ownPrimary로 알린다.
 * 제출 수와 초대 링크 복사는 화면이 제목 바로 아래에 둔다.
 * result 모드에서는 고정 영역을 결과 화면이 쓰므로 모든 조작을 보조 버튼으로 둔다.
 * 작업 상태와 기존 결과의 존재는 따로 본다. 재생성 중이거나 실패해도 정상 결과가 있으면 그 결과를 여는 것이 주 동작이다.
 */
export function HostPanel({
  code,
  token,
  room,
  onChanged,
  mode = "room",
  ownPrimary = false,
  hasResult = null,
}: {
  code: string;
  token: string;
  room: RoomView;
  onChanged: () => void;
  mode?: "room" | "result";
  ownPrimary?: boolean;
  hasResult?: boolean | null;
}) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [confirmEarly, setConfirmEarly] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
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
  const canOpen = inBar && (s === "ready" || hasResult === true);
  const scenariosFailed = s === "open" && room.scenario_status === "failed";
  const deleteDisabled = busy || room.scenario_status === "preparing" || s === "generating";
  const deleteRoom = async () => {
    if (deleteDisabled) return;
    setBusy(true);
    setError(null);
    try {
      try {
        await api.deleteRoom(code, token);
      } catch (err) {
        if (!(err instanceof ApiError && err.status === 404)) throw err;
      }
      clearRoomStorage(code);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err);
    } finally {
      setConfirmDelete(false);
      setBusy(false);
    }
  };

  const generateButton = (primary: boolean) => (
    <button
      type="button"
      className={primary ? "btn btn-primary" : "btn-text"}
      disabled={busy || noResponses}
      onClick={() => setConfirmEarly(true)}
    >
      지금까지 모인 응답으로 만들기
    </button>
  );
  const retryButton = (primary: boolean) => (
    <button
      type="button"
      className={`btn ${primary ? "btn-primary" : "btn-outline"}`}
      disabled={busy}
      onClick={() => run(() => api.retry(code, token))}
    >
      같은 응답으로 다시 시도
    </button>
  );

  return (
    <section className="host-menu" aria-labelledby="host-panel-title">
      <h2 id="host-panel-title" className="t-label-md">
        방장 메뉴
      </h2>
      {!inBar && s === "failed" && room.failure_reason && <p className="secondary">{FAILURE_TEXT[room.failure_reason]}</p>}
      {canGenerate && noResponses && <p className="disabled-reason">한 명 이상 답하면 지금 만들 수 있어요.</p>}
      {canGenerate && (!inBar || ownPrimary) && generateButton(false)}
      {s === "failed" && (!inBar || hasResult === true) && retryButton(false)}
      {scenariosFailed && (
        <>
          <p className="t-body-sm secondary">다시 시도해도 안 되면 새 방을 만들어 주세요. 새 방은 초대 링크가 달라져요.</p>
          <Link className="btn-text" to="/new">
            새 방 만들기
          </Link>
        </>
      )}
      {s === "ready" && !inBar && canRegenerate && (
        <button
          type="button"
          className="btn btn-outline"
          disabled={busy}
          onClick={() => run(() => api.regenerate(code, token))}
        >
          같은 응답으로 한 번 더 만들기
        </button>
      )}
      {!inBar && <CopyButton text={inviteUrl(code)} label="초대 링크 복사" />}
      {error !== null && <ErrorMessage error={error} />}
      <PushOptIn code={code} role="host" hostToken={token} />
      <button type="button" className="btn-text" disabled={deleteDisabled} onClick={() => setConfirmDelete(true)}>
        방 삭제하기
      </button>
      {(room.scenario_status === "preparing" || s === "generating") && (
        <p className="t-body-sm secondary">문항이나 협약서를 만드는 동안에는 방을 삭제할 수 없어요.</p>
      )}

      {inBar && canGenerate && !ownPrimary && <BottomBar>{generateButton(true)}</BottomBar>}
      {inBar && s === "failed" && !canOpen && <BottomBar>{retryButton(true)}</BottomBar>}
      {inBar && scenariosFailed && (
        <BottomBar>
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy}
            onClick={() => run(() => api.retry(code, token))}
          >
            문항 다시 만들기
          </button>
        </BottomBar>
      )}
      {canOpen && <OpenPact code={code} />}

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
      {confirmDelete && (
        <ConfirmSheet
          title="방을 삭제할까요?"
          confirmLabel="방 삭제하기"
          cancelLabel="그만두기"
          busy={deleteDisabled}
          onConfirm={deleteRoom}
          onCancel={() => !busy && setConfirmDelete(false)}
        >
          <p>이 방의 모든 응답과 협약서가 사라지고 초대 링크도 더는 열리지 않아요. 삭제한 방은 되돌릴 수 없어요.</p>
          <p>기기에 이미 저장한 협약서 이미지는 남아 있어요.</p>
        </ConfirmSheet>
      )}
    </section>
  );
}
