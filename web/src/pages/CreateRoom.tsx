import { CircleAlert } from "lucide-react";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import type { ProfileInput } from "../api/types";
import { BottomBar, ErrorMessage, ICON } from "../components/ui";
import { useHeaderBack } from "../lib/back";
import { saveHostToken } from "../lib/hostToken";

interface PersonDraft {
  display_name: string;
  gender: string;
  age_band: string;
  mbti: string;
}

interface Draft {
  destination: string;
  days: string;
  partySize: number;
  relationship: string;
  people: PersonDraft[];
  informed: boolean;
}

const EMPTY_PERSON: PersonDraft = { display_name: "", gender: "", age_band: "", mbti: "" };
const emptyDraft = (): Draft => ({
  destination: "",
  days: "",
  partySize: 3,
  relationship: "",
  people: Array.from({ length: 3 }, () => ({ ...EMPTY_PERSON })),
  informed: false,
});

// 선택 정보의 허용값은 서버 계약에 없다. fixture(ex1_ready)의 값 형태("여성", "20대", "ENFP")를 따른다.
const GENDERS = ["여성", "남성"];
const AGE_BANDS = ["10대", "20대", "30대", "40대", "50대", "60대 이상"];
const STEPS = 4;

// 입력 중인 내용은 화면을 오가도 남도록 메모리에만 둔다. 이름과 선택 정보를 브라우저 저장소에 쓰지 않는다.
let saved: Draft = emptyDraft();
export function resetCreateDraft(): void {
  saved = emptyDraft();
}

type Errors = Record<string, string>;

function hasOptional(d: Draft): boolean {
  return d.people.some((p) => p.gender || p.age_band || p.mbti.trim());
}

function isDirty(d: Draft): boolean {
  return (
    !!d.destination.trim() ||
    !!d.days ||
    !!d.relationship.trim() ||
    d.people.some((p) => p.display_name.trim()) ||
    hasOptional(d)
  );
}

function validate(step: number, d: Draft): Errors {
  const e: Errors = {};
  if (step === 1) {
    if (!d.destination.trim()) e.destination = "목적지를 입력해 주세요.";
    const n = Number(d.days);
    if (!Number.isInteger(n) || n < 1) e.days = "여행 일수는 1 이상의 숫자로 입력해 주세요.";
  }
  if (step === 2 && !d.relationship.trim()) e.relationship = "동행과의 관계를 입력해 주세요.";
  if (step === 3) {
    d.people.forEach((p, i) => {
      if (!p.display_name.trim()) e[`name-${i}`] = "이름이나 별명을 입력해 주세요.";
    });
  }
  if (step === 4) {
    d.people.forEach((p, i) => {
      if (p.mbti.trim() && !/^[EI][SN][TF][JP]$/i.test(p.mbti.trim())) {
        e[`mbti-${i}`] = "네 글자(예: ENFP)로 입력하거나 비워 두세요.";
      }
    });
    if (hasOptional(d) && !d.informed) e.informed = "선택 정보를 입력했다면 동행에게 알렸는지 확인해 주세요.";
  }
  return e;
}

/** 앞 단계에 빈칸이 있으면 그 단계까지만 들어갈 수 있다. */
function reachableStep(wanted: number, d: Draft): number {
  for (let s = 1; s < wanted; s++) if (Object.keys(validate(s, d)).length > 0) return s;
  return wanted;
}

function FieldError({ id, text }: { id: string; text?: string }) {
  if (!text) return null;
  return (
    <p id={id} className="field-error">
      <CircleAlert {...ICON} />
      <span>{text}</span>
    </p>
  );
}

export function CreateRoom() {
  const navigate = useNavigate();
  const location = useLocation();
  const [params] = useSearchParams();
  const depth = ((location.state ?? {}) as { depth?: number }).depth ?? 0;
  const [d, setD] = useState<Draft>(saved);
  const [errors, setErrors] = useState<Errors>({});
  const [focusTick, setFocusTick] = useState(0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [createdCode, setCreatedCode] = useState<string | null>(null);
  const formRef = useRef<HTMLFormElement>(null);

  const wanted = Math.min(Math.max(Number(params.get("step")) || 1, 1), STEPS);
  const step = reachableStep(wanted, d);

  useEffect(() => {
    saved = d;
  }, [d]);
  useEffect(() => {
    window.scrollTo(0, 0);
    setErrors({});
    formRef.current?.querySelector("input, select")?.scrollIntoView?.({ block: "nearest" });
  }, [step]);
  useEffect(() => {
    if (focusTick > 0) formRef.current?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
  }, [focusTick]);
  // 새로고침과 탭 닫기는 메모리의 입력을 지운다.
  useEffect(() => {
    if (!isDirty(d) || createdCode) return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [d, createdCode]);

  useHeaderBack(() => {
    if (depth > 0) navigate(-1);
    else if (step > 1) navigate({ search: `?step=${step - 1}` }, { replace: true });
    else navigate("/");
  });

  if (createdCode) {
    // 입력 단계 기록을 되돌린 뒤 그 자리를 방 안내 화면으로 바꾼다. 뒤로 가도 빈 입력 화면이 나오지 않는다.
    if (depth > 0) return null;
    return <Navigate to={`/r/${encodeURIComponent(createdCode)}/created`} replace />;
  }

  const patch = (p: Partial<Draft>, ...clear: string[]) => {
    setD((prev) => ({ ...prev, ...p }));
    if (clear.length) {
      setErrors((prev) => Object.fromEntries(Object.entries(prev).filter(([k]) => !clear.includes(k))));
    }
  };
  const updatePerson = (i: number, p: Partial<PersonDraft>, ...clear: string[]) => {
    setD((prev) => {
      const people = prev.people.map((x, j) => (j === i ? { ...x, ...p } : x));
      return { ...prev, people };
    });
    setErrors((prev) => Object.fromEntries(Object.entries(prev).filter(([k]) => !clear.includes(k) && k !== "informed")));
  };
  const resize = (n: number) =>
    setD((prev) => ({
      ...prev,
      partySize: n,
      people: Array.from({ length: n }, (_, i) => prev.people[i] ?? { ...EMPTY_PERSON }),
    }));

  const create = async () => {
    setBusy(true);
    setError(null);
    const trip = {
      destination: d.destination.trim(),
      duration_days: Number(d.days),
      party_size: d.partySize,
      relationship: d.relationship.trim(),
    };
    const profiles: ProfileInput[] = d.people.map((p, i) => ({
      profile_id: `p${i + 1}`,
      display_name: p.display_name.trim(),
      ...(p.gender ? { gender: p.gender } : {}),
      ...(p.age_band ? { age_band: p.age_band } : {}),
      ...(p.mbti.trim() ? { mbti: p.mbti.trim().toUpperCase() } : {}),
    }));
    try {
      const res = await api.createRoom(trip, profiles);
      saveHostToken(res.room_code, res.host_token);
      resetCreateDraft();
      setCreatedCode(res.room_code);
      if (depth > 0) navigate(-depth);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (busy) return;
    const found = validate(step, d);
    setErrors(found);
    if (Object.keys(found).length > 0) {
      setFocusTick((t) => t + 1);
      return;
    }
    if (step < STEPS) navigate({ search: `?step=${step + 1}` }, { state: { depth: depth + 1 } });
    else void create();
  };

  const invalid = (key: string) =>
    errors[key] ? ({ "aria-invalid": true, "aria-describedby": `err-${key}` } as const) : {};
  const anyOptional = hasOptional(d);

  return (
    <main className="page">
      <div className="progress">
        <div
          className="progress-track"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={STEPS}
          aria-valuenow={step - 1}
          aria-label="입력한 단계"
        >
          <div className="progress-fill" style={{ transform: `scaleX(${(step - 1) / STEPS})` }} />
        </div>
        <span className="count-label">
          <span className="num">
            {step} / {STEPS}
          </span>
        </span>
      </div>

      <form ref={formRef} className="stack-lg" onSubmit={submit} noValidate id="create-form">
        {step === 1 && (
          <>
            <h1 className="t-headline-lg">어디로 떠나나요?</h1>
            <div className="field">
              <label className="field-label" htmlFor="f-destination">
                목적지
              </label>
              <input
                id="f-destination"
                className="input"
                value={d.destination}
                onChange={(e) => patch({ destination: e.target.value }, "destination")}
                {...invalid("destination")}
              />
              <FieldError id="err-destination" text={errors.destination} />
            </div>
            <div className="field">
              <label className="field-label" htmlFor="f-days">
                여행 일수
              </label>
              <input
                id="f-days"
                className="input"
                inputMode="numeric"
                type="number"
                min={1}
                value={d.days}
                onChange={(e) => patch({ days: e.target.value }, "days")}
                {...invalid("days")}
              />
              <FieldError id="err-days" text={errors.days} />
            </div>
          </>
        )}

        {step === 2 && (
          <>
            <h1 className="t-headline-lg">누구와 함께 가나요?</h1>
            <label className="field">
              <span className="field-label">함께 가는 인원(나 포함)</span>
              <select className="input" value={d.partySize} onChange={(e) => resize(Number(e.target.value))}>
                {[2, 3, 4, 5, 6, 7, 8].map((n) => (
                  <option key={n} value={n}>
                    {n}명
                  </option>
                ))}
              </select>
            </label>
            <div className="field">
              <label className="field-label" htmlFor="f-relationship">
                동행과의 관계
              </label>
              <input
                id="f-relationship"
                className="input"
                value={d.relationship}
                onChange={(e) => patch({ relationship: e.target.value }, "relationship")}
                aria-invalid={errors.relationship ? true : undefined}
                aria-describedby={errors.relationship ? "rel-help err-relationship" : "rel-help"}
              />
              <span id="rel-help" className="field-help">
                예: 친구, 가족, 동아리
              </span>
              <FieldError id="err-relationship" text={errors.relationship} />
            </div>
          </>
        )}

        {step === 3 && (
          <>
            <div className="stack-sm">
              <h1 className="t-headline-lg">답할 사람의 이름을 넣어 주세요</h1>
              <p className="secondary">나를 포함해 모두 적어 주세요. 실명 대신 서로 알아볼 수 있는 별명을 써도 돼요.</p>
            </div>
            {d.people.map((p, i) => (
              <div className="field" key={i}>
                <label className="field-label" htmlFor={`f-name-${i}`}>
                  {i + 1}번째 이름 또는 별명
                </label>
                <input
                  id={`f-name-${i}`}
                  className="input"
                  value={p.display_name}
                  onChange={(e) => updatePerson(i, { display_name: e.target.value }, `name-${i}`)}
                  {...invalid(`name-${i}`)}
                />
                <FieldError id={`err-name-${i}`} text={errors[`name-${i}`]} />
              </div>
            ))}
          </>
        )}

        {step === 4 && (
          <>
            <div className="stack-sm">
              <h1 className="t-headline-lg">선택 정보를 넣을까요?</h1>
              <p className="secondary">
                문항을 각자에게 맞게 바꾸는 데만 써요. 다른 동행과 협약서에는 보이지 않아요. 비워 두고 건너뛰어도 돼요.
              </p>
            </div>
            {d.people.map((p, i) => (
              <fieldset className="person-group" key={i}>
                <legend>{p.display_name.trim() || `${i + 1}번째 동행`}</legend>
                <div className="row-3">
                  <label className="field">
                    <span className="field-label">성별</span>
                    <select className="input" value={p.gender} onChange={(e) => updatePerson(i, { gender: e.target.value })}>
                      <option value="">입력 안 함</option>
                      {GENDERS.map((g) => (
                        <option key={g}>{g}</option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span className="field-label">나이대</span>
                    <select
                      className="input"
                      value={p.age_band}
                      onChange={(e) => updatePerson(i, { age_band: e.target.value })}
                    >
                      <option value="">입력 안 함</option>
                      {AGE_BANDS.map((g) => (
                        <option key={g}>{g}</option>
                      ))}
                    </select>
                  </label>
                  <label className="field">
                    <span className="field-label">MBTI</span>
                    <input
                      className="input"
                      value={p.mbti}
                      maxLength={4}
                      autoCapitalize="characters"
                      onChange={(e) => updatePerson(i, { mbti: e.target.value }, `mbti-${i}`)}
                      {...invalid(`mbti-${i}`)}
                    />
                  </label>
                </div>
                <FieldError id={`err-mbti-${i}`} text={errors[`mbti-${i}`]} />
              </fieldset>
            ))}
            {anyOptional && (
              <div className="stack-sm">
                <label className="check">
                  <input
                    type="checkbox"
                    checked={d.informed}
                    onChange={(e) => patch({ informed: e.target.checked }, "informed")}
                    {...invalid("informed")}
                  />
                  <span>
                    동행에게 알렸어요
                    <span className="t-body-sm secondary" style={{ display: "block" }}>
                      이름과 선택 정보를 대신 입력한다는 사실을 동행에게 미리 알렸어요.
                    </span>
                  </span>
                </label>
                <FieldError id="err-informed" text={errors.informed} />
              </div>
            )}
            <p className="t-body-sm secondary">
              입력한 정보를 어떻게 다루는지는 <Link to="/privacy">개인정보 처리방침</Link>에서 볼 수 있어요.
            </p>
          </>
        )}
      </form>

      <BottomBar>
        {error !== null && <ErrorMessage error={error} />}
        <button type="submit" form="create-form" className="btn btn-primary" disabled={busy}>
          {busy ? "만드는 중이에요" : step < STEPS ? "다음" : anyOptional ? "방 만들기" : "건너뛰고 방 만들기"}
        </button>
      </BottomBar>
    </main>
  );
}
