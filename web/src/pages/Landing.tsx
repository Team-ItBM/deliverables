import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { isNotFound } from "../api/errors";
import type { RoomView } from "../api/types";
import { BottomBar } from "../components/ui";
import { forgetHostToken, hostRoomCodes, getHostToken } from "../lib/hostToken";
import { ROOM_STATUS_TEXT } from "../lib/status";
import { tripMetaText } from "../lib/trip";

const STEPS = [
  "방을 만들고 동행에게 초대 링크를 보내요.",
  "같은 가상 상황에 각자 답해요. 다른 사람의 답은 보이지 않아요.",
  "서로의 바람과 한계를 담은 추천 협약서를 받아요.",
];

/** 이 기기에 방장 토큰이 남은 방. 서버에 없는 방은 토큰을 지우고 보여 주지 않는다. */
function useHostRooms(): { code: string; room: RoomView }[] {
  const [rooms, setRooms] = useState<{ code: string; room: RoomView }[]>([]);
  useEffect(() => {
    let cancelled = false;
    void Promise.all(
      hostRoomCodes().map(async (code) => {
        const token = getHostToken(code);
        if (!token) return null;
        try {
          return { code, room: await api.getRoom(code, token) };
        } catch (err) {
          if (isNotFound(err)) forgetHostToken(code);
          return null;
        }
      })
    ).then((list) => {
      if (!cancelled) setRooms(list.filter((r) => r !== null));
    });
    return () => {
      cancelled = true;
    };
  }, []);
  return rooms;
}

/** 예시 협약서. 지어낸 이름과 문장만 쓰고 선택·메모·선택 프로필은 넣지 않는다. 도장과 가지는 발급된 종이 전용이다. */
function SamplePaper() {
  return (
    <figure className="sample" aria-label="예시 협약서 일부">
      <article className="pact-paper">
        <div className="pact-head">
          <span className="t-wordmark">도원결의</span>
          <span className="draft-label">예시</span>
        </div>
        <div className="pact-title-block">
          <p className="pact-title">여행 동행 협약서</p>
          <span className="pact-underline" aria-hidden="true" />
          <p className="pact-meta">제주 · 3일 · 3명</p>
        </div>
        <div className="pact-clause">
          <p className="pact-clause-number">제1조</p>
          <p>오후에 일정이 비면 시간을 나눠 각자 가고 싶은 곳에 다녀와요.</p>
          <p className="pact-names">적용 대상: 민지, 서준, 하늘</p>
          <div className="pact-sub">
            <p className="pact-sub-label">제안 조건</p>
            <ul>
              <li>저녁 식사 시간에는 다시 모여요.</li>
            </ul>
          </div>
        </div>
        <p className="pact-disclaimer">AI가 각자의 응답을 바탕으로 만든 추천안이에요. 동행 모두가 정한 약속은 아니에요.</p>
      </article>
    </figure>
  );
}

export function Landing() {
  const navigate = useNavigate();
  const rooms = useHostRooms();
  return (
    <main className="page">
      <h1 className="t-headline-lg">여행을 떠나기 전, 동행과 같은 상황에 각자 답하고 추천 협약서를 받아 보세요.</h1>

      {rooms.length > 0 && (
        <section className="stack-sm" aria-labelledby="my-rooms">
          <h2 id="my-rooms" className="t-headline-md">
            진행 중인 방 이어가기
          </h2>
          <ul className="stack-sm">
            {rooms.map(({ code, room }) => (
              <li key={code}>
                <Link className="room-link" to={`/r/${encodeURIComponent(code)}`}>
                  <span>{room.trip ? tripMetaText(room.trip) : code}</span>
                  <span className="t-body-sm secondary">{ROOM_STATUS_TEXT[room.room_status]}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <ol className="how-steps">
        {STEPS.map((text, i) => (
          <li key={text}>
            <span className="how-step-number t-numeral" aria-hidden="true">
              {i + 1}
            </span>
            <span>{text}</span>
          </li>
        ))}
      </ol>

      <SamplePaper />

      <Link className="btn-text" to="/privacy">
        개인정보 처리방침
      </Link>

      <BottomBar>
        <button type="button" className="btn btn-primary" onClick={() => navigate("/new")}>
          방 만들기
        </button>
      </BottomBar>
    </main>
  );
}
