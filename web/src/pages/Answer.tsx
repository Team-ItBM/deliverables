import { ArrowLeft, CircleAlert, Lock } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import type { ScenarioOption, SessionScenario } from "../api/types";
import { BottomBar, ErrorMessage, ICON } from "../components/ui";
import { clearSession, loadSession, saveSession, submitSession, type AnswerSession } from "../lib/answerSession";
import { clampMemo, memoLength, MEMO_MAX, splitScene } from "../lib/scene";

export function MemoField({
  id,
  value,
  onChange,
}: {
  id: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="field">
      <label className="field-label" htmlFor={id}>
        메모 (선택)
      </label>
      <textarea
        id={id}
        className="memo"
        value={value}
        rows={3}
        aria-describedby={`${id}-count`}
        onChange={(e) => onChange(clampMemo(e.target.value))}
      />
      <div className="field-help">
        <span>고른 이유나 조건이 있으면 적어 주세요.</span>
        <span id={`${id}-count`} className="t-numeral" aria-label={`${memoLength(value)}자, 최대 ${MEMO_MAX}자`}>
          {memoLength(value)} / {MEMO_MAX}
        </span>
      </div>
    </div>
  );
}

function OptionGroup({
  labelledBy,
  options,
  value,
  onChange,
}: {
  labelledBy: string;
  options: ScenarioOption[];
  value: string | undefined;
  onChange: (id: string) => void;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const idx = options.findIndex((o) => o.option_id === value);
  const onKey = (e: KeyboardEvent, i: number) => {
    const d = e.key === "ArrowDown" || e.key === "ArrowRight" ? 1 : e.key === "ArrowUp" || e.key === "ArrowLeft" ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    const n = (i + d + options.length) % options.length;
    onChange(options[n]!.option_id);
    refs.current[n]?.focus();
  };
  return (
    <div className="options" role="radiogroup" aria-labelledby={labelledBy}>
      {options.map((o, i) => (
        <button
          key={o.option_id}
          ref={(el) => {
            refs.current[i] = el;
          }}
          type="button"
          role="radio"
          aria-checked={o.option_id === value}
          tabIndex={o.option_id === value || (idx < 0 && i === 0) ? 0 : -1}
          className="option-card"
          onClick={() => onChange(o.option_id)}
          onKeyDown={(e) => onKey(e, i)}
        >
          <span className="radio-dot" aria-hidden="true" />
          <span>{o.label}</span>
        </button>
      ))}
    </div>
  );
}

function ScenarioStep({
  scenario,
  answer,
  onPick,
  onMemo,
}: {
  scenario: SessionScenario;
  answer: { option_id?: string; memo: string } | undefined;
  onPick: (id: string) => void;
  onMemo: (v: string) => void;
}) {
  const { lead, details } = splitScene(scenario.scene);
  const qid = `q-${scenario.scenario_id}`;
  return (
    <div className="stack-3xl">
      <div className="stack-lg" style={{ gap: "var(--s-2xl)" }}>
        <div className="scene">
          <p className="scene-lead">{lead}</p>
          {details.length > 0 && (
            <ul className="scene-details">
              {details.map((d, i) => (
                <li key={i}>{d}</li>
              ))}
            </ul>
          )}
        </div>
        <div className="question-block">
          <h1 className="t-headline-md" id={qid}>
            {scenario.question}
          </h1>
          <OptionGroup labelledBy={qid} options={scenario.options} value={answer?.option_id} onChange={onPick} />
        </div>
      </div>
      <MemoField id={`memo-${scenario.scenario_id}`} value={answer?.memo ?? ""} onChange={onMemo} />
    </div>
  );
}

export function Answer() {
  const { code = "" } = useParams();
  const navigate = useNavigate();
  const [s, setS] = useState<AnswerSession | null>(() => loadSession(code));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const topRef = useRef<HTMLDivElement>(null);
  const submittedRef = useRef(false);

  useEffect(() => {
    if (s && !submittedRef.current) saveSession(code, s);
  }, [code, s]);
  useEffect(() => {
    window.scrollTo(0, 0);
    topRef.current?.focus();
  }, [s?.step]);

  if (!s) return <Navigate to={`/r/${encodeURIComponent(code)}`} replace />;

  const total = s.scenarios.length;
  const step = Math.min(s.step, total);
  const isReview = step === total;
  const scenario = s.scenarios[step];
  const answer = scenario ? s.answers[scenario.scenario_id] : undefined;
  const allAnswered = s.scenarios.every((sc) => s.answers[sc.scenario_id]?.option_id);

  const patch = (id: string, p: Partial<{ option_id: string; memo: string }>) =>
    setS((prev) =>
      prev ? { ...prev, answers: { ...prev.answers, [id]: { memo: "", ...prev.answers[id], ...p } } } : prev
    );
  const go = (n: number) => setS((prev) => (prev ? { ...prev, step: n } : prev));

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await submitSession(code, s, (next) => setS(next));
      submittedRef.current = true;
      clearSession(code);
      navigate(`/r/${encodeURIComponent(code)}/wait`, { replace: true });
    } catch (err) {
      setError(err);
      // submitSession이 키를 유지하거나 버린 상태를 setS로 반영했다.
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="page">
      <div className="stack-sm" ref={topRef} tabIndex={-1} style={{ outline: "none" }}>
        <div className="progress">
          <div
            className="progress-track"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={total}
            aria-valuenow={step}
            aria-label="답한 문항"
          >
            <div className="progress-fill" style={{ transform: `scaleX(${total ? step / total : 0})` }} />
          </div>
          <span className="count-label">
            <span className="num">
              {Math.min(step + 1, total)} / {total}
            </span>
          </span>
        </div>
        {step > 0 && (
          <button type="button" className="btn-text" onClick={() => go(step - 1)}>
            <ArrowLeft {...ICON} />
            이전 문항
          </button>
        )}
        {s.duplicate_name_notice && step === 0 && (
          <p className="notice-duplicate-name">
            <CircleAlert {...ICON} />
            <span>이 이름으로 이미 제출된 답변이 있어요. 이번 답변은 따로 반영돼요.</span>
          </p>
        )}
      </div>

      {scenario && !isReview && (
        <ScenarioStep
          key={scenario.scenario_id}
          scenario={scenario}
          answer={answer}
          onPick={(id) => patch(scenario.scenario_id, { option_id: id })}
          onMemo={(v) => patch(scenario.scenario_id, { memo: v })}
        />
      )}

      {isReview && (
        <div className="stack-lg">
          <h1 className="t-headline-md">답을 확인해 주세요</h1>
          <p className="secondary">제출하면 고칠 수 없어요. 고칠 문항이 있으면 눌러서 바꿔 주세요.</p>
          <ol className="stack-sm">
            {s.scenarios.map((sc, i) => {
              const a = s.answers[sc.scenario_id];
              const label = sc.options.find((o) => o.option_id === a?.option_id)?.label;
              return (
                <li key={sc.scenario_id} className="card" style={{ gap: "var(--s-xs)" }}>
                  <p className="t-body-sm secondary">{sc.question}</p>
                  <p>{label ?? "아직 고르지 않았어요"}</p>
                  {a?.memo.trim() && <p className="t-body-sm secondary">메모 {memoLength(a.memo)}자</p>}
                  <button type="button" className="btn-text" onClick={() => go(i)}>
                    {i + 1}번 고치기
                  </button>
                </li>
              );
            })}
          </ol>
        </div>
      )}

      <BottomBar>
        {isReview && (
          <>
            <div className="notice-privacy">
              <Lock {...ICON} />
              <div className="stack-sm">
                <p>{s.privacy_notice}</p>
                <p>메모에는 건강 상태처럼 일정 조율과 상관없는 개인 사정은 적지 말아 주세요.</p>
              </div>
            </div>
            {error !== null && <ErrorMessage error={error} />}
            {!allAnswered && <p className="disabled-reason">모든 문항에 답해야 제출할 수 있어요.</p>}
            <button type="button" className="btn btn-primary" disabled={!allAnswered || busy} onClick={submit}>
              {busy ? "보내는 중이에요" : error !== null ? "다시 제출하기" : "제출하기"}
            </button>
          </>
        )}
        {!isReview && (
          <>
            {!answer?.option_id && <p className="disabled-reason">선택지를 하나 골라 주세요.</p>}
            <button type="button" className="btn btn-primary" disabled={!answer?.option_id} onClick={() => go(step + 1)}>
              {step + 1 === total ? "답 확인하기" : "다음"}
            </button>
          </>
        )}
      </BottomBar>
    </main>
  );
}
