import { Navigate, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { isNotFound } from "../api/errors";
import type { RoomView } from "../api/types";
import { HostPanel } from "../components/HostPanel";
import { PushOptIn } from "../components/PushOptIn";
import { OpenPact } from "../components/OpenPact";
import { Count, ErrorMessage, RoomNotFound } from "../components/ui";
import { loadSubmitted } from "../lib/answerSession";
import { useHeaderBack } from "../lib/back";
import { useHasResult, useHostToken, usePolling } from "../lib/hooks";
import { FAILURE_TEXT, ROOM_STATUS_TEXT } from "../lib/status";

export function Wait() {
  const { code = "" } = useParams();
  const navigate = useNavigate();
  const token = useHostToken(code);
  const submitted = loadSubmitted(code);
  const roomPath = `/r/${encodeURIComponent(code)}`;
  useHeaderBack(() => navigate(roomPath));
  const { data: room, error, reload } = usePolling<RoomView>(
    () => api.getRoom(code, token),
    (r) => !r || r.room_status !== "ready",
    [code, token]
  );
  const hasResult = useHasResult(code, room?.room_status);

  if (!room && isNotFound(error)) return <RoomNotFound />;
  // 제출한 기기와 방장은 진행 상황을 먼저 보고 직접 협약서를 연다. 그 밖의 사람은 결과로 바로 간다.
  if (hasResult && !token && !submitted) return <Navigate to={`${roomPath}/result`} replace />;

  return (
    <main className="page">
      <h1 className="t-headline-lg">진행 상황</h1>
      {submitted && <p className="secondary">답변을 제출했어요. 제출한 답변은 다른 동행에게 보이지 않아요.</p>}
      {room && (
        <section className="card status-card" aria-live="polite">
          <p>{ROOM_STATUS_TEXT[room.room_status]}</p>
          {room.room_status === "open" && <p className="secondary">다른 동행의 응답을 기다리고 있어요.</p>}
          {room.room_status === "failed" && (
            <>
              {room.failure_reason && <p className="secondary">{FAILURE_TEXT[room.failure_reason]}</p>}
              {!token && <p className="secondary">방장이 같은 응답으로 다시 시도할 수 있어요.</p>}
            </>
          )}
          <Count label={token ? "제출(나 포함)" : "제출"} value={room.submitted_count} total={room.party_size} />
          {(room.room_status === "generating" || room.room_status === "closed") && (
            <div className="progress-track" aria-hidden="true">
              <div className="progress-flow" />
            </div>
          )}
        </section>
      )}
      {error !== null && <ErrorMessage error={error} onRetry={reload} />}
      {room && token && <HostPanel code={code} token={token} room={room} onChanged={reload} showStatus={false} />}
      {submitted && !token && <PushOptIn code={code} role="participant" sessionId={submitted.session_id} />}
      <p className="t-body-sm secondary">이 화면을 닫아도 돼요. 초대 링크로 다시 열면 진행 상황을 볼 수 있어요.</p>
      {hasResult && !token && <OpenPact code={code} />}
    </main>
  );
}
