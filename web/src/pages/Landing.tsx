import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { isNotFound } from "../api/errors";
import type { RoomView, SharedResult } from "../api/types";
import { ResultSheet } from "../components/PactSheet";
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

/** 예시 협약서. 실제 종이를 그대로 쓴다. 지어낸 이름과 문장만 넣고 선택·메모·선택 프로필은 넣지 않는다. */
const SAMPLE: Partial<SharedResult> = {
  pact_status: "proposed",
  trip: { destination: "제주", duration_days: 3, party_size: 3 },
  clauses: [
    {
      scenario_id: "sample",
      participant_names: ["민지", "서준", "하늘"],
      action: "오후에 일정이 비면 시간을 나눠 각자 가고 싶은 곳에 다녀와요.",
      proposed_conditions: ["저녁 식사 시간에는 다시 모여요."],
    },
  ],
};

export function Landing() {
  const navigate = useNavigate();
  const rooms = useHostRooms();
  return (
    <main className="page">
      <div className="stack-sm">
        <h1 className="t-headline-lg">
          떠나기 전에,
          <br />
          서로의 마음을 한 장에.
        </h1>
        <p className="secondary">말 못 한 바람도 각자 답하면 추천 협약서에 담겨요.</p>
      </div>

      <figure className="sample" aria-label="예시 협약서">
        <ResultSheet result={SAMPLE} sample />
      </figure>

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
