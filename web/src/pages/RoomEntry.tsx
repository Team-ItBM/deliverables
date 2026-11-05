import { CircleAlert, Lock } from "lucide-react";
import { useState } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";
import privacyMd from "../../../docs/PRIVACY.md?raw";
import { api } from "../api/client";
import { isNotFound } from "../api/errors";
import type { RoomView } from "../api/types";
import { contactSectionId } from "../components/Markdown";
import { HostPanel } from "../components/HostPanel";
import { OpenPact } from "../components/OpenPact";
import { BottomBar, ConfirmSheet, CopyButton, ErrorMessage, ICON, RoomNotFound, StatusLine } from "../components/ui";
import { clearSession, loadPending, loadSession, loadSubmitted, resendPending, saveSession } from "../lib/answerSession";
import { useHeaderBack } from "../lib/back";
import { useHostToken, usePolling, useResultCheck } from "../lib/hooks";
import { inviteUrl } from "../lib/hostToken";
import { FAILURE_TEXT, SCENARIO_STATUS_TEXT } from "../lib/status";
import { tripMetaText } from "../lib/trip";

const CONTACT = contactSectionId(privacyMd);

function hostTitle(room: RoomView): string {
  if (room.scenario_status === "preparing") return "문항을 준비하고 있어요";
  if (room.scenario_status !== "ready") return "문항을 만들지 못했어요";
  if (room.room_status === "open") return "동행의 답을 모으고 있어요";
  if (room.room_status === "ready") return "협약서가 준비됐어요";
  if (room.room_status === "failed") return "협약서를 만들지 못했어요";
  return "협약서를 만들고 있어요";
}

export function RoomEntry() {
  const { code = "" } = useParams();
  const navigate = useNavigate();
  const token = useHostToken(code);
  useHeaderBack(() => navigate("/"));
  const { data: room, error, reload, loading } = usePolling<RoomView>(
    () => api.getRoom(code, token),
    (r) =>
      !r ||
      r.scenario_status === "preparing" ||
      r.scenario_status === "failed" ||
      r.room_status === "closed" ||
      r.room_status === "generating" ||
      (token !== null && r.room_status !== "ready"),
    [code, token]
  );
  const resultCheck = useResultCheck(code, room?.room_status);
  const hasResult = resultCheck.has;
  const [picked, setPicked] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sessionError, setSessionError] = useState<unknown>(null);
  const [inProgress, setInProgress] = useState(() => loadSession(code));
  const [confirmRestart, setConfirmRestart] = useState(false);
  const [answerAgain, setAnswerAgain] = useState(false);
  // 결과를 모르는 제출이 있으면 새 키로 다시 답하지 못하게 다른 흐름을 막고 그 요청부터 확인한다.
  const [pending, setPending] = useState(() => loadPending(code) !== null);
  const [pendingError, setPendingError] = useState<unknown>(null);
  const submitted = loadSubmitted(code);
  const roomPath = `/r/${encodeURIComponent(code)}`;

  if (loading && !room) return <main className="page"><p className="secondary">방 정보를 불러오고 있어요.</p></main>;
  if (!room && isNotFound(error)) return <RoomNotFound />;
  if (!room) {
    return (
      <main className="page">
        <ErrorMessage error={error} onRetry={reload} />
      </main>
    );
  }

  if (hasResult && !token && !submitted && !pending) return <Navigate to={`${roomPath}/result`} replace />;

  const canAnswer = !pending && room.room_status === "open" && room.scenario_status === "ready";
  const resuming = canAnswer && inProgress !== null;
  const showNames = canAnswer && !resuming && (!submitted || answerAgain);
  const showProgress = !!submitted && !answerAgain && !resuming && !pending;
  const profile = room.profiles.find((p) => p.profile_id === picked);
  const closedForAnswers = !pending && room.scenario_status === "ready" && room.room_status !== "open";

  const start = async () => {
    if (!profile) return;
    setBusy(true);
    setSessionError(null);
    try {
      const s = await api.createSession(code, profile.profile_id);
      saveSession(code, {
        ...s,
        profile_id: profile.profile_id,
        display_name: profile.display_name,
        answers: {},
        step: 0,
      });
      navigate(`${roomPath}/answer`, { state: { fromRoom: true } });
    } catch (err) {
      setSessionError(err);
    } finally {
      setBusy(false);
    }
  };

  const confirmPending = async () => {
    setBusy(true);
    setPendingError(null);
    try {
      await resendPending(code);
      setPending(false);
      navigate(`${roomPath}/wait`);
    } catch (err) {
      setPendingError(err);
      setPending(loadPending(code) !== null);
      setInProgress(loadSession(code));
    } finally {
      setBusy(false);
    }
  };

  const resumeButton = (
    <button
      type="button"
      className="btn btn-primary"
      onClick={() => navigate(`${roomPath}/answer`, { state: { fromRoom: true } })}
    >
      이어서 답하기
    </button>
  );
  const progressButton = (
    <button type="button" className="btn btn-primary" onClick={() => navigate(`${roomPath}/wait`)}>
      진행 상황 보기
    </button>
  );

  return (
    <main className="page">
      <div className="stack-sm">
        <h1 className="t-headline-lg">{token ? hostTitle(room) : "여행 전 질문에 답해 주세요"}</h1>
        {room.trip && <p className="t-label-md">{tripMetaText(room.trip)}</p>}
        {!token && <p className="secondary">같은 상황에 각자 답하면, 서로의 바람과 한계를 담은 추천 협약서를 받아요.</p>}
      </div>

      {token && (
        <section className="status-block" aria-live="polite">
          <StatusLine room={room} host />
          {room.room_status === "failed" && room.failure_reason && <p className="secondary">{FAILURE_TEXT[room.failure_reason]}</p>}
          <CopyButton text={inviteUrl(code)} label="초대 링크 복사" />
        </section>
      )}

      {token && room.scenario_notice && (room.scenario_notice.message || room.scenario_notice.clarification_questions) && (
        <section className="status-block" aria-label="문항 준비 안내">
          {room.scenario_notice.message && <p>{room.scenario_notice.message}</p>}
          {room.scenario_notice.clarification_questions && (
            <ul className="stack-sm">
              {room.scenario_notice.clarification_questions.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ul>
          )}
          <p className="t-body-sm secondary">여행 정보를 고쳐 새 방을 만들어 주세요.</p>
          <Link className="btn-text" to="/new">
            새 방 만들기
          </Link>
        </section>
      )}

      {room.scenario_status !== "ready" && (
        <section className="status-block" aria-live="polite">
          {!(token && room.scenario_status === "preparing") && <p>{SCENARIO_STATUS_TEXT[room.scenario_status]}</p>}
          {room.scenario_status === "preparing" && (
            <div className="progress-track" aria-hidden="true">
              <div className="progress-flow" />
            </div>
          )}
        </section>
      )}

      {resultCheck.failed && (
        <ErrorMessage text="협약서가 있는지 확인하지 못했어요." onRetry={resultCheck.retry} retryLabel="다시 확인" />
      )}

      {pending && (
        <section className="status-block" aria-live="polite">
          <p>이 기기에서 보낸 답변의 제출 결과를 확인하지 못했어요. 먼저 확인해 주세요.</p>
        </section>
      )}
      {pendingError !== null && <ErrorMessage error={pendingError} />}

      {showProgress && (
        <section className="status-block" aria-live="polite">
          <p>이 기기에서 답변을 제출했어요.</p>
          {!token && <StatusLine room={room} />}
          {canAnswer && (
            <button type="button" className="btn-text" onClick={() => setAnswerAgain(true)}>
              다른 이름으로 답하기
            </button>
          )}
        </section>
      )}

      {closedForAnswers && !showProgress && !token && (
        <section className="status-block">
          <p>응답을 마감했어요. 더는 답을 받지 않아요.</p>
        </section>
      )}

      {resuming && (
        <section className="status-block">
          <p>{inProgress.display_name} 이름으로 답하던 중이에요.</p>
          <button type="button" className="btn-text" onClick={() => setConfirmRestart(true)}>
            처음부터 다시 답하기
          </button>
        </section>
      )}

      {showNames && (
        <section className="stack-md">
          <h2 className="t-headline-md" id="names-title">
            내 이름을 골라 주세요
          </h2>
          <div className="options" role="radiogroup" aria-labelledby="names-title">
            {room.profiles.map((p) => (
              <button
                key={p.profile_id}
                type="button"
                role="radio"
                aria-checked={picked === p.profile_id}
                className="option-card"
                onClick={() => setPicked(p.profile_id)}
              >
                <span className="radio-dot" aria-hidden="true" />
                <span>{p.display_name}</span>
              </button>
            ))}
          </div>
          {profile?.has_submission && (
            <p className="notice-duplicate-name" role="status">
              <CircleAlert {...ICON} />
              <span>
                이 이름으로 이미 제출된 답변이 있어요. 계속하면 새 답변으로 따로 반영돼요. 이전 답변은 볼 수도, 고칠 수도
                없어요.
              </span>
            </p>
          )}
        </section>
      )}

      {token && (
        <HostPanel
          code={code}
          token={token}
          room={room}
          onChanged={reload}
          ownPrimary={showNames || resuming || pending}
          hasResult={hasResult}
        />
      )}

      {(showNames || room.scenario_status === "preparing") && (
        <section className="notice-privacy" aria-label="등록 정보 안내">
          <Lock {...ICON} />
          <p>
            방장이 이 여행을 위해 동행의 이름을 등록했어요. 방장이 입력한 경우 성별·나이대·MBTI도 함께 등록돼요. 이 정보는
            각자에게 맞는 문항을 보여 주는 데만 쓰고, 다른 동행에게 보여 주지 않아요. 등록 정보를 지우고 싶으면{" "}
            <Link to={`/privacy${CONTACT ? `#${CONTACT}` : ""}`}>처리방침의 요청 방법</Link>을 확인해 주세요.
          </p>
        </section>
      )}

      {pending && (
        <BottomBar>
          <button type="button" className="btn btn-primary" disabled={busy} onClick={confirmPending}>
            {busy ? "확인하는 중이에요" : "제출 결과 확인하기"}
          </button>
        </BottomBar>
      )}
      {resuming && <BottomBar>{resumeButton}</BottomBar>}
      {showNames && (
        <BottomBar>
          {sessionError !== null && <ErrorMessage error={sessionError} />}
          {!profile && <p className="disabled-reason">이름을 고르면 시작할 수 있어요.</p>}
          <button type="button" className="btn btn-primary" disabled={!profile || busy} onClick={start}>
            {profile ? `${profile.display_name} 이름으로 답하기` : "답하기"}
          </button>
        </BottomBar>
      )}
      {!token && (showProgress || closedForAnswers) && (hasResult ? <OpenPact code={code} /> : <BottomBar>{progressButton}</BottomBar>)}

      {confirmRestart && (
        <ConfirmSheet
          title="처음부터 다시 답할까요?"
          confirmLabel="지우고 다시 답하기"
          cancelLabel="이어서 답하기"
          onConfirm={() => {
            clearSession(code);
            setInProgress(null);
            setConfirmRestart(false);
          }}
          onCancel={() => setConfirmRestart(false)}
        >
          <p>지금까지 고른 답과 메모가 사라져요.</p>
        </ConfirmSheet>
      )}
    </main>
  );
}
