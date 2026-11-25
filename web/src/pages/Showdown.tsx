import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api/client";
import { ApiError, isNotFound } from "../api/errors";
import type { ShowdownBoard, ShowdownCard, ShowdownChoice, ShowdownItem, ShowdownMove, ShowdownView } from "../api/types";
import { HOW_LABEL, TALK_RULE } from "../components/ShowdownRules";
import { BottomBar, ErrorMessage, RoomNotFound } from "../components/ui";
import { loadSubmitted } from "../lib/answerSession";
import { useHeaderBack } from "../lib/back";
import { useHostToken, usePolling } from "../lib/hooks";

const HANDS: { move: ShowdownMove; label: string; mark: string }[] = [
  { move: "scissors", label: "가위", mark: "✌️" },
  { move: "rock", label: "바위", mark: "✊" },
  { move: "paper", label: "보", mark: "🖐️" },
];
const HAND_LABEL: Record<ShowdownMove, string> = { scissors: "가위", rock: "바위", paper: "보" };

function contestLine(card: ShowdownCard): string {
  return card.sides.join(" vs ");
}

/** 승부처 카드 한 장. 고르기, 가위바위보, 결과를 단계에 따라 보여 준다. */
function ShowdownCardView({
  item,
  card,
  busy,
  isHost,
  onPick,
  onMove,
  onClose,
}: {
  item: ShowdownItem;
  card: ShowdownCard;
  busy: boolean;
  isHost: boolean;
  onPick: (choice: ShowdownChoice) => void;
  onMove: (move: ShowdownMove) => void;
  onClose: () => void;
}) {
  const duelLabel = card.mode === "rps" ? "가위바위보로 정하기" : "제비뽑기로 정하기";
  const choices: { choice: ShowdownChoice; label: string }[] = [
    ...card.compromises.map((rule, i) => ({ choice: (i === 0 ? "c0" : "c1") as ShowdownChoice, label: rule })),
    { choice: "duel", label: duelLabel },
    { choice: "talk", label: "승부 없이 토론해서 정할게요" },
  ];
  const result = card.result;
  return (
    <section className="card showdown-card" aria-label={`승부처: ${item.title ?? contestLine(card)}`}>
      <div className="stack-sm">
        {item.title && <p className="t-caption muted">{item.title}</p>}
        <h3 className="showdown-vs">{contestLine(card)}</h3>
      </div>

      {card.phase === "voting" && (
        <>
          {card.can_pick ? (
            <div className="options" role="radiogroup" aria-label="어떻게 정할지 고르기">
              {choices.map(({ choice, label }) => (
                <button
                  key={choice}
                  type="button"
                  role="radio"
                  className="option-card"
                  aria-checked={card.my_pick === choice}
                  disabled={busy}
                  onClick={() => onPick(choice)}
                >
                  <span className="radio-dot" aria-hidden="true" />
                  <span>{label}</span>
                </button>
              ))}
            </div>
          ) : (
            <p className="secondary">이 방에 답을 제출한 기기에서 고를 수 있어요.</p>
          )}
          <p className="count-label" role="status">
            <span className="num">{card.voter_count}</span>명 중 <span className="num">{card.picked_count}</span>명이 골랐어요
            {card.my_pick ? ". 모두 고르면 결과가 나와요" : ""}
          </p>
          <p className="t-body-sm secondary">
            모두 같은 절충안을 고르면 그대로 정해요. 한 명이라도 토론을 고르면 직접 정하고, 그 밖에는 {card.mode === "rps" ? "가위바위보" : "제비뽑기"}로 가요.
          </p>
          {isHost && card.picked_count > 0 && (
            <button type="button" className="btn-text" disabled={busy} onClick={onClose}>
              지금까지 고른 걸로 마감하기
            </button>
          )}
        </>
      )}

      {card.phase === "duel" && card.duel && (
        <div className="stack-md" aria-live="polite">
          <p className="showdown-stage">가위바위보 {card.duel.round}번째 판</p>
          {card.duel.last_tie && <p role="status">둘 다 {HAND_LABEL[card.duel.last_tie]}! 비겼어요. 다시 내 주세요.</p>}
          {card.duel.is_player ? (
            card.duel.my_move ? (
              <p role="status">{HAND_LABEL[card.duel.my_move]}를 냈어요. 상대가 내면 결과가 나와요.</p>
            ) : (
              <div className="rps-row" role="group" aria-label="낼 패 고르기">
                {HANDS.map((hand) => (
                  <button key={hand.move} type="button" className="rps-hand" disabled={busy} onClick={() => onMove(hand.move)}>
                    <span className="rps-mark" aria-hidden="true">{hand.mark}</span>
                    <span>{hand.label}</span>
                  </button>
                ))}
              </div>
            )
          ) : (
            <p className="secondary">의견이 갈린 두 사람이 가위바위보를 하고 있어요.</p>
          )}
        </div>
      )}

      {card.phase === "done" && result && (
        <div className="stack-sm" aria-live="polite">
          <p className="showdown-badge">{HOW_LABEL[result.how]}</p>
          {result.how === "duel" && result.my_move && result.other_move && (
            <p>
              나 {HAND_LABEL[result.my_move]} · 상대 {HAND_LABEL[result.other_move]}
            </p>
          )}
          {result.won === true && <p className="showdown-stage">이겼어요!</p>}
          {result.won === false && <p className="showdown-stage">졌어요. 이번엔 양보예요.</p>}
          <p className="rule-text">{result.rule ?? TALK_RULE}</p>
        </div>
      )}
    </section>
  );
}

function Board({
  board,
  busy,
  isHost,
  act,
}: {
  board: ShowdownBoard;
  busy: boolean;
  isHost: boolean;
  act: (run: () => Promise<ShowdownView>) => void;
}) {
  const { code = "" } = useParams();
  const token = useHostToken(code);
  const sessionId = loadSubmitted(code)?.session_id ?? null;
  const cards = board.items.filter((item) => item.showdown);
  const open = cards.filter((item) => item.showdown!.phase !== "done");
  const done = cards.filter((item) => item.showdown!.phase === "done");
  // 이미 고르기 시작했으면 안내를 건너뛴다.
  const touched = cards.some((item) => item.showdown!.my_pick !== null || item.showdown!.phase !== "voting");
  const [started, setStarted] = useState(false);
  const resultPath = `/r/${encodeURIComponent(code)}/result`;

  if (cards.length === 0) {
    return (
      <>
        <section className="status-block">
          <p>의견이 크게 갈린 문항이 없어요. 바로 협약서를 볼 수 있어요.</p>
        </section>
        <BottomBar>
          <Link className="btn btn-primary" to={resultPath}>
            전체 협약서 보기
          </Link>
        </BottomBar>
      </>
    );
  }

  if (open.length > 0 && !started && !touched) {
    return (
      <>
        <section className="status-block" aria-live="polite">
          <p className="showdown-headline">
            의견이 갈린 문항 <span className="num">{open.length}</span>개를 찾았어요
          </p>
          <p className="secondary">협약서를 보기 전에 이 문항만 먼저 정해요.</p>
        </section>
        <ol className="showdown-steps">
          <li>각자 기기에서 절충안, 승부, 토론 중 하나를 골라요.</li>
          <li>모두 같은 절충안을 고르면 그대로 약속이 돼요.</li>
          <li>갈리면 가위바위보나 제비뽑기로 정해요.</li>
          <li>누가 무엇을 골랐는지는 보이지 않아요.</li>
        </ol>
        <BottomBar>
          <button type="button" className="btn btn-primary" onClick={() => setStarted(true)}>
            승부처 시작하기
          </button>
        </BottomBar>
      </>
    );
  }

  const renderCard = (item: ShowdownItem, locked: boolean) => (
    <ShowdownCardView
      key={item.scenario_id}
      item={item}
      card={item.showdown!}
      busy={busy || locked}
      isHost={isHost && !locked}
      onPick={(choice) => {
        if (sessionId) act(() => api.showdownPick(code, item.scenario_id, sessionId, choice));
      }}
      onMove={(move) => {
        if (sessionId) act(() => api.showdownMove(code, item.scenario_id, sessionId, move));
      }}
      onClose={() => {
        if (token) act(() => api.showdownClose(code, item.scenario_id, token, sessionId));
      }}
    />
  );

  return (
    <>
      <section className="status-block" aria-live="polite">
        {open.length > 0 ? (
          <p>승부처가 {open.length}개 남았어요. 각자 기기에서 골라 주세요.</p>
        ) : (
          <p>승부처를 모두 정했어요. 이제 전체 협약서를 볼 수 있어요.</p>
        )}
      </section>
      {open.length > 0 && (
        <section className="stack-lg" aria-label="정할 승부처">
          {open.map((item) => renderCard(item, false))}
        </section>
      )}
      {done.length > 0 && (
        <section className="stack-lg" aria-label="정한 승부처">
          <h2 className="t-headline-md">정한 승부처</h2>
          {done.map((item) => renderCard(item, true))}
        </section>
      )}
      {open.length === 0 && (
        <BottomBar>
          <Link className="btn btn-primary" to={resultPath}>
            전체 협약서 보기
          </Link>
        </BottomBar>
      )}
    </>
  );
}

export function Showdown() {
  const { code = "" } = useParams();
  const navigate = useNavigate();
  const token = useHostToken(code);
  const sessionId = loadSubmitted(code)?.session_id ?? null;
  const roomPath = `/r/${encodeURIComponent(code)}`;
  useHeaderBack(() => navigate(`${roomPath}/wait`));

  const polled = usePolling<ShowdownView>(
    () => api.getShowdown(code, sessionId),
    (data) => !data || (data.available && data.summary.showdown_open > 0),
    [code, sessionId],
    { stopOnError: isNotFound }
  );
  const [view, setView] = useState<ShowdownView | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<unknown>(null);
  useEffect(() => {
    if (polled.data) setView(polled.data);
  }, [polled.data]);

  const act = (run: () => Promise<ShowdownView>) => {
    setBusy(true);
    setActionError(null);
    run()
      .then((next) => setView(next))
      .catch((err: unknown) => {
        setActionError(err);
        polled.reload();
      })
      .finally(() => setBusy(false));
  };

  if (isNotFound(polled.error)) return <RoomNotFound />;
  const notReady = polled.error instanceof ApiError && polled.error.code === "invalid_state";

  return (
    <main className="page">
      <h1 className="t-headline-lg">승부처</h1>
      {notReady && !view && (
        <section className="status-block">
          <p>아직 답을 모으고 있어요. 모두 답하면 볼 수 있어요.</p>
          <Link className="btn-text" to={`${roomPath}/wait`}>
            진행 상황 보기
          </Link>
        </section>
      )}
      {polled.error !== null && !notReady && !view && <ErrorMessage error={polled.error} onRetry={polled.reload} />}
      {actionError !== null && <ErrorMessage error={actionError} />}
      {view && !view.available && (
        <>
          <p className="secondary">이 방에는 승부처가 없어요.</p>
          <BottomBar>
            <Link className="btn btn-primary" to={`${roomPath}/result`}>
              전체 협약서 보기
            </Link>
          </BottomBar>
        </>
      )}
      {view && view.available && <Board board={view} busy={busy} isHost={token !== null} act={act} />}
    </main>
  );
}
