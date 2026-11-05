import { CircleAlert, Lock } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import privacyMd from "../../../docs/PRIVACY.md?raw";
import { api } from "../api/client";
import { isNotFound } from "../api/errors";
import type { RoomView } from "../api/types";
import { contactSectionId } from "../components/Markdown";
import { HostPanel } from "../components/HostPanel";
import { BottomBar, ErrorMessage, ICON, RoomNotFound } from "../components/ui";
import { loadSession, loadSubmitted, saveSession } from "../lib/answerSession";
import { usePolling, useHostToken } from "../lib/hooks";
import { SCENARIO_STATUS_TEXT } from "../lib/status";

const CONTACT = contactSectionId(privacyMd);

export function RoomEntry() {
  const { code = "" } = useParams();
  const navigate = useNavigate();
  const token = useHostToken(code);
  const { data: room, error, reload, loading } = usePolling<RoomView>(
    () => api.getRoom(code, token),
    (r) => !r || r.scenario_status === "preparing" || (token !== null && r.room_status !== "ready"),
    [code, token]
  );
  const [picked, setPicked] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [sessionError, setSessionError] = useState<unknown>(null);
  const inProgress = loadSession(code);
  const submitted = loadSubmitted(code);

  if (loading && !room) return <main className="page"><p className="secondary">방 정보를 불러오고 있어요.</p></main>;
  if (!room && isNotFound(error)) return <RoomNotFound />;
  if (!room) {
    return (
      <main className="page">
        <ErrorMessage error={error} onRetry={reload} />
      </main>
    );
  }

  const profile = room.profiles.find((p) => p.profile_id === picked);
  const canAnswer = room.room_status === "open" && room.scenario_status === "ready";

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
      navigate(`/r/${encodeURIComponent(code)}/answer`);
    } catch (err) {
      setSessionError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="page">
      <div className="stack-sm">
        <h1 className="t-headline-lg">여행 전 질문에 답해 주세요</h1>
        <p className="secondary">같은 상황에 각자 답하면, 서로의 바람과 한계를 담은 추천 협약서를 받아요.</p>
      </div>

      {token && <HostPanel code={code} token={token} room={room} onChanged={reload} />}
      {token && room.scenario_notice && (room.scenario_notice.message || room.scenario_notice.clarification_questions) && (
        <section className="card" aria-label="문항 준비 안내">
          {room.scenario_notice.message && <p>{room.scenario_notice.message}</p>}
          {room.scenario_notice.clarification_questions && (
            <ul className="stack-sm">
              {room.scenario_notice.clarification_questions.map((q, i) => (
                <li key={i}>{q}</li>
              ))}
            </ul>
          )}
          <p className="t-body-sm secondary">여행 정보를 고쳐 새 방을 만들어 주세요.</p>
          <Link className="btn-text" to="/">
            새 방 만들기
          </Link>
        </section>
      )}

      {room.scenario_status !== "ready" && (
        <section className="card" aria-live="polite">
          <p>{SCENARIO_STATUS_TEXT[room.scenario_status]}</p>
          {room.scenario_status === "preparing" && (
            <div className="progress-track" aria-hidden="true">
              <div className="progress-flow" />
            </div>
          )}
        </section>
      )}

      {room.scenario_status === "ready" && room.room_status !== "open" && (
        <section className="card">
          <p>응답을 마감했어요. 더는 답을 받지 않아요.</p>
          <Link className="btn-text" to={`/r/${encodeURIComponent(code)}/wait`}>
            진행 상황 보기
          </Link>
        </section>
      )}

      {submitted && (
        <section className="card">
          <p>이 기기에서 답변을 제출했어요.</p>
          <Link className="btn-text" to={`/r/${encodeURIComponent(code)}/wait`}>
            진행 상황 보기
          </Link>
        </section>
      )}

      {canAnswer && inProgress && (
        <section className="card">
          <p>{inProgress.display_name} 이름으로 답하던 중이에요.</p>
          <Link className="btn-text" to={`/r/${encodeURIComponent(code)}/answer`}>
            이어서 답하기
          </Link>
        </section>
      )}

      {canAnswer && (
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

      <section className="notice-privacy" aria-label="등록 정보 안내">
        <Lock {...ICON} />
        <p>
          방장이 이 여행을 위해 동행의 이름을 등록했어요. 방장이 입력한 경우 성별·나이대·MBTI도 함께 등록돼요. 이 정보는 각자에게
          맞는 문항을 보여 주는 데만 쓰고, 다른 동행에게 보여 주지 않아요. 등록 정보를 지우고 싶으면{" "}
          <Link to={`/privacy${CONTACT ? `#${CONTACT}` : ""}`}>처리방침의 요청 방법</Link>을 확인해 주세요.
        </p>
      </section>

      {canAnswer && (
        <BottomBar>
          {sessionError !== null && <ErrorMessage error={sessionError} />}
          {!profile && <p className="disabled-reason">이름을 고르면 시작할 수 있어요.</p>}
          <button type="button" className="btn btn-primary" disabled={!profile || busy} onClick={start}>
            {profile ? `${profile.display_name} 이름으로 답하기` : "답하기"}
          </button>
        </BottomBar>
      )}
    </main>
  );
}
