import { ChevronDown } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { CreateRoomResponse, ProfileInput } from "../api/types";
import { BottomBar, CopyButton, ErrorMessage, ICON } from "../components/ui";
import { hostUrl, inviteUrl, saveHostToken } from "../lib/hostToken";

interface PersonDraft {
  display_name: string;
  gender: string;
  age_band: string;
  mbti: string;
}

const EMPTY: PersonDraft = { display_name: "", gender: "", age_band: "", mbti: "" };
// 선택 정보의 허용값은 서버 계약에 없다. fixture(ex1_ready)의 값 형태("여성", "20대", "ENFP")를 따른다.
const GENDERS = ["여성", "남성"];
const AGE_BANDS = ["10대", "20대", "30대", "40대", "50대", "60대 이상"];

export function CreateRoom() {
  const navigate = useNavigate();
  const [destination, setDestination] = useState("");
  const [days, setDays] = useState("");
  const [partySize, setPartySize] = useState(3);
  const [relationship, setRelationship] = useState("");
  const [people, setPeople] = useState<PersonDraft[]>(() => Array.from({ length: 3 }, () => ({ ...EMPTY })));
  const [informed, setInformed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [created, setCreated] = useState<CreateRoomResponse | null>(null);

  const anyOptional = people.some((p) => p.gender || p.age_band || p.mbti.trim());

  const resize = (n: number) => {
    setPartySize(n);
    setPeople((prev) => Array.from({ length: n }, (_, i) => prev[i] ?? { ...EMPTY }));
  };
  const update = (i: number, patch: Partial<PersonDraft>) =>
    setPeople((prev) => prev.map((p, j) => (j === i ? { ...p, ...patch } : p)));

  const validate = (): string | null => {
    if (!destination.trim()) return "목적지를 입력해 주세요.";
    const d = Number(days);
    if (!Number.isInteger(d) || d < 1) return "여행 일수는 1 이상의 숫자로 입력해 주세요.";
    if (!relationship.trim()) return "동행과의 관계를 입력해 주세요.";
    if (people.some((p) => !p.display_name.trim())) return "모든 동행의 이름이나 별명을 입력해 주세요.";
    if (people.some((p) => p.mbti.trim() && !/^[EI][SN][TF][JP]$/i.test(p.mbti.trim())))
      return "MBTI는 네 글자(예: ENFP)로 입력하거나 비워 두세요.";
    if (anyOptional && !informed) return "선택 정보를 입력했다면 동행에게 알렸는지 확인해 주세요.";
    return null;
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    const v = validate();
    setFormError(v);
    if (v) return;
    setBusy(true);
    setError(null);
    const trip = {
      destination: destination.trim(),
      duration_days: Number(days),
      party_size: partySize,
      relationship: relationship.trim(),
    };
    const profiles: ProfileInput[] = people.map((p, i) => ({
      profile_id: `p${i + 1}`,
      display_name: p.display_name.trim(),
      ...(p.gender ? { gender: p.gender } : {}),
      ...(p.age_band ? { age_band: p.age_band } : {}),
      ...(p.mbti.trim() ? { mbti: p.mbti.trim().toUpperCase() } : {}),
    }));
    try {
      const res = await api.createRoom(trip, profiles);
      saveHostToken(res.room_code, res.host_token);
      setCreated(res);
      window.scrollTo(0, 0);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  if (created) {
    const code = created.room_code;
    return (
      <main className="page">
        <h1 className="t-headline-lg">방을 만들었어요</h1>
        <p className="secondary">문항이 준비되면 동행이 초대 링크로 들어와 각자 답할 수 있어요.</p>
        <section className="card">
          <h2 className="t-label-md">동행에게 보낼 링크</h2>
          <p className="link-box">{inviteUrl(code)}</p>
          <CopyButton text={inviteUrl(code)} label="초대 링크 복사" />
        </section>
        <section className="card">
          <h2 className="t-label-md">방장 링크(나만 보관)</h2>
          <p className="t-body-sm secondary">
            이 링크로 들어와야 결과를 고르고 문구를 고칠 수 있어요. 동행에게 보내지 마세요.
          </p>
          <p className="link-box">{hostUrl(code, created.host_token)}</p>
          <CopyButton text={hostUrl(code, created.host_token)} label="방장 링크 복사" />
        </section>
        <BottomBar>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => navigate(`/r/${encodeURIComponent(code)}`)}
          >
            방 화면으로 가기
          </button>
        </BottomBar>
      </main>
    );
  }

  return (
    <main className="page">
      <div className="stack-sm">
        <h1 className="t-headline-lg">여행 방 만들기</h1>
        <p className="secondary">떠나기 전에 같은 상황에 각자 답하고, 추천 협약서를 받아 보세요.</p>
      </div>
      <form className="stack-3xl" onSubmit={submit} noValidate id="create-form">
        <fieldset className="person-group stack-lg">
          <legend className="t-headline-md">여행 정보</legend>
          <label className="field">
            <span className="field-label">목적지</span>
            <input className="input" value={destination} onChange={(e) => setDestination(e.target.value)} required />
          </label>
          <label className="field">
            <span className="field-label">여행 일수</span>
            <input
              className="input"
              inputMode="numeric"
              type="number"
              min={1}
              value={days}
              onChange={(e) => setDays(e.target.value)}
              required
            />
          </label>
          <label className="field">
            <span className="field-label">함께 가는 인원</span>
            <select className="input" value={partySize} onChange={(e) => resize(Number(e.target.value))}>
              {[2, 3, 4, 5, 6, 7, 8].map((n) => (
                <option key={n} value={n}>
                  {n}명
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field-label">동행과의 관계</span>
            <input
              className="input"
              value={relationship}
              onChange={(e) => setRelationship(e.target.value)}
              aria-describedby="rel-help"
              required
            />
            <span id="rel-help" className="field-help">
              예: 친구, 가족, 동아리
            </span>
          </label>
        </fieldset>

        <fieldset className="person-group stack-lg">
          <legend className="t-headline-md">동행 이름</legend>
          <p className="t-body-sm secondary">
            답할 사람 모두의 이름이나 별명을 넣어 주세요. 실명 대신 서로 알아볼 수 있는 별명을 써도 돼요.
          </p>
          {people.map((p, i) => (
            <label className="field" key={i}>
              <span className="field-label">{i + 1}번째 이름 또는 별명</span>
              <input
                className="input"
                value={p.display_name}
                onChange={(e) => update(i, { display_name: e.target.value })}
                required
              />
            </label>
          ))}
        </fieldset>

        <details className="fold">
          <summary>
            <span>선택 정보: 성별·나이대·MBTI</span>
            <ChevronDown {...ICON} />
          </summary>
          <div className="fold-body">
            <p className="t-body-sm secondary">
              문항을 각자에게 맞게 바꾸는 데만 써요. 다른 동행과 협약서에는 보이지 않아요. 비워 둬도 돼요.
            </p>
            {people.map((p, i) => (
              <fieldset className="person-group" key={i}>
                <legend>{p.display_name.trim() || `${i + 1}번째 동행`}</legend>
                <div className="row-3">
                  <label className="field">
                    <span className="field-label">성별</span>
                    <select className="input" value={p.gender} onChange={(e) => update(i, { gender: e.target.value })}>
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
                      onChange={(e) => update(i, { age_band: e.target.value })}
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
                      onChange={(e) => update(i, { mbti: e.target.value })}
                    />
                  </label>
                </div>
              </fieldset>
            ))}
          </div>
        </details>

        {anyOptional && (
          <label className="check">
            <input type="checkbox" checked={informed} onChange={(e) => setInformed(e.target.checked)} />
            <span>
              동행에게 알렸어요
              <span className="t-body-sm secondary" style={{ display: "block" }}>
                이름과 선택 정보를 대신 입력한다는 사실을 동행에게 미리 알렸어요.
              </span>
            </span>
          </label>
        )}

        <p className="t-body-sm secondary">
          입력한 정보를 어떻게 다루는지는 <Link to="/privacy">개인정보 처리방침</Link>에서 볼 수 있어요.
        </p>
      </form>
      <BottomBar>
        {formError && <ErrorMessage text={formError} />}
        {error !== null && <ErrorMessage error={error} />}
        <button type="submit" form="create-form" className="btn btn-primary" disabled={busy}>
          {busy ? "만드는 중이에요" : "방 만들기"}
        </button>
      </BottomBar>
    </main>
  );
}
