// VITE_MOCK=1 전용 가짜 서버. 12개 경로(§0-B)를 브라우저 안에서 흉내 낸다.
// 실제 모델·AWS·푸시를 부르지 않는다. 상태는 같은 브라우저의 탭끼리 나눠 쓰도록 localStorage에 둔다.
import type { Transport, TransportRequest, TransportResponse } from "../api/client";
import type {
  ConditionalAlternative,
  EditableItem,
  PactStatus,
  ProfileInput,
  ResultEntry,
  SharedResult,
  Trip,
} from "../api/types";
import { renderText, toSegments, tokenSignature } from "./render";

export type MockVariant = "proposed" | "unresolved" | "fail";
export const MOCK_DB = "dowon.mock.db";
export const MOCK_VARIANT = "dowon.mock.variant";
const SCENARIO_DELAY = 2000;
const GENERATE_DELAY = 2500;

interface TplClause {
  scenario_id: string;
  pids: string[];
  action: string;
  proposed_conditions: string[];
}
interface Tpl {
  pact_status: PactStatus;
  clauses: TplClause[] | null;
  conditional_alternatives: (TplClause & { proposed_changes: string[] })[] | null;
  unresolved_conditions: { scenario_id: string; description: string }[] | null;
  message?: string;
  humor?: { text: string; explanation: string };
}
interface Original {
  result_id: string;
  attempt: number;
  state: "normal" | "failed";
  created_at: string;
  included: string[];
  tpl?: Tpl;
  edits: { result_id: string; source_result_id: string; tpl: Tpl }[];
}
interface Room {
  code: string;
  token: string;
  trip: Trip;
  profiles: ProfileInput[];
  scenarioReadyAt: number;
  scenarioStatus: "preparing" | "ready";
  status: "open" | "closed" | "generating" | "ready" | "failed";
  failure_reason?: "call_error";
  generatingUntil?: number;
  variant?: MockVariant;
  submissions: { participant_id: string; profile_id: string; memos: string[] }[];
  sessions: Record<string, { profile_id: string; used: boolean }>;
  idem: Record<string, { body: string; resp: unknown }>;
  originals: Original[];
  included?: string[];
  selected: string | null;
}
type DB = Record<string, Room>;

const rid = (p: string) => `${p}_${Math.random().toString(36).slice(2, 10)}`;
const load = (): DB => {
  try {
    return JSON.parse(localStorage.getItem(MOCK_DB) ?? "{}") as DB;
  } catch {
    return {};
  }
};
const save = (db: DB) => {
  try {
    localStorage.setItem(MOCK_DB, JSON.stringify(db));
  } catch {
    /* 무시 */
  }
};
function variant(): MockVariant {
  try {
    const v = localStorage.getItem(MOCK_VARIANT);
    return v === "unresolved" || v === "fail" ? v : "proposed";
  } catch {
    return "proposed";
  }
}

const ok = (status: number, body: unknown): TransportResponse => ({ status, body: structuredClone(body) });
const err = (status: number, code: string): TransportResponse => ({
  status,
  body: { error: { code, message: "모의 서버 오류" } },
});

const SCENARIOS = [
  {
    scenario_id: "free_time",
    scene: "가려던 곳이 문을 닫았어요\n저녁 약속까지 세 시간이 남았어요\n가까운 곳에 카페와 숙소가 있어요",
    question: "이 시간을 어떻게 보내고 싶어요?",
    options: [
      { option_id: "free_time_1", label: "구경하고 싶어요" },
      { option_id: "free_time_2", label: "카페에서 보내고 싶어요" },
      { option_id: "free_time_3", label: "숙소에서 쉬고 싶어요" },
      { option_id: "free_time_any", label: "어느 쪽이든 괜찮아요" },
    ],
  },
  {
    scenario_id: "sunset",
    scene: "{{profile:OTHER}}이/가 노을을 보러 가자고 해요\n노을까지 40분 남았어요\n쇼핑도 아직 못 했어요",
    question: "남은 시간을 어떻게 쓰고 싶어요?",
    options: [
      { option_id: "sunset_1", label: "쇼핑을 먼저 하고 싶어요" },
      { option_id: "sunset_2", label: "노을을 먼저 보고 싶어요" },
      { option_id: "sunset_3", label: "둘을 짧게 나누고 싶어요" },
    ],
  },
  {
    scenario_id: "budget",
    scene: "둘째 날 저녁 식당을 고르고 있어요\n한 곳은 비싸지만 유명하고, 한 곳은 저렴해요",
    question: "어디로 가고 싶어요?",
    options: [
      { option_id: "budget_1", label: "유명한 곳에 가고 싶어요" },
      { option_id: "budget_2", label: "저렴한 곳에 가고 싶어요" },
      { option_id: "budget_any", label: "어느 쪽이든 괜찮아요" },
    ],
  },
];

function scenariosFor(room: Room, profileId: string) {
  const other = room.profiles.find((p) => p.profile_id !== profileId)!;
  const names: Record<string, string> = {};
  for (const p of room.profiles) names[p.profile_id] = p.profile_id === profileId ? "당신" : p.display_name;
  return SCENARIOS.map((s) => ({
    ...s,
    scene: renderText(s.scene.replace("OTHER", other.profile_id), names),
  }));
}

function participantNames(room: Room): Record<string, string> {
  const names: Record<string, string> = {};
  const counts: Record<string, number> = {};
  const seen: Record<string, number> = {};
  for (const s of room.submissions) counts[s.profile_id] = (counts[s.profile_id] ?? 0) + 1;
  for (const s of room.submissions) {
    const p = room.profiles.find((x) => x.profile_id === s.profile_id)!;
    seen[s.profile_id] = (seen[s.profile_id] ?? 0) + 1;
    names[s.participant_id] = counts[s.profile_id]! > 1 ? `${p.display_name}(응답 ${seen[s.profile_id]})` : p.display_name;
  }
  return names;
}

function makeTpl(v: MockVariant, pids: string[]): Tpl {
  const a = pids[0]!;
  const b = pids[1] ?? a;
  if (v === "unresolved") {
    return {
      pact_status: "unresolved",
      clauses: null,
      conditional_alternatives: null,
      unresolved_conditions: [
        { scenario_id: "budget", description: "하루 식비 상한이 서로 달라 함께 갈 식당을 정하지 못했어요." },
        { scenario_id: "sunset", description: "노을과 쇼핑 중 무엇을 먼저 할지, 시간을 나누는 안도 맞지 않았어요." },
      ],
      humor: { text: "너네 조합 꽝이니 여행 가지 마세요!", explanation: "이번 응답 조건에서는 추천안을 찾지 못했습니다." },
    };
  }
  return {
    pact_status: "proposed",
    clauses: [
      {
        scenario_id: "free_time",
        pids,
        action: "남는 시간에는 카페에서 한 시간 쉬고 나서 함께 구경해요.",
        proposed_conditions: [`{{participant:${a}}}이/가 더 쉬고 싶다고 하면 숙소로 먼저 돌아가요.`],
      },
      {
        scenario_id: "sunset",
        pids,
        action: "노을을 먼저 보고, 쇼핑은 다음 날 오전에 해요.",
        proposed_conditions: [],
      },
    ],
    conditional_alternatives: [
      {
        scenario_id: "sunset",
        pids: [a, b],
        action: `{{participant:${b}}}은/는 쇼핑을 하고 {{participant:${a}}}은/는 노을을 본 뒤 저녁에 만나요.`,
        proposed_conditions: ["저녁 식사 시간에는 다시 모여요."],
        proposed_changes: [`{{participant:${a}}}과/와 함께 노을을 보는 대신 따로 시간을 보내요.`],
      },
    ],
    unresolved_conditions: [
      { scenario_id: "budget", description: "둘째 날 저녁 식당은 예산 조건이 달라 아직 정하지 못했어요." },
    ],
  };
}

function shared(room: Room, o: Original, version?: Original["edits"][number]): SharedResult {
  const names = participantNames(room);
  const tpl = version?.tpl ?? o.tpl!;
  const r = (t: string) => renderText(t, names);
  const clause = (c: TplClause) => ({
    scenario_id: c.scenario_id,
    participant_names: c.pids.map((p) => names[p] ?? "?"),
    action: r(c.action),
    proposed_conditions: c.proposed_conditions.map(r),
  });
  const includedProfiles = new Set(room.submissions.filter((s) => o.included.includes(s.participant_id)).map((s) => s.profile_id));
  return {
    result_id: version?.result_id ?? o.result_id,
    kind: version ? "host_edited" : "ai_original",
    source_result_id: version?.source_result_id ?? null,
    label: version ? "방장 수정" : null,
    draft: room.selected === null,
    pact_status: tpl.pact_status,
    included_count: o.included.length,
    excluded_names: room.profiles.filter((p) => !includedProfiles.has(p.profile_id)).map((p) => p.display_name),
    clauses: tpl.clauses?.map(clause) ?? null,
    conditional_alternatives:
      tpl.conditional_alternatives?.map(
        (c): ConditionalAlternative => ({ ...clause(c), proposed_changes: c.proposed_changes.map(r) })
      ) ?? null,
    unresolved_conditions: tpl.unresolved_conditions,
    ...(tpl.message ? { message: tpl.message } : {}),
    ...(tpl.pact_status === "unresolved" && tpl.humor ? { humor: tpl.humor } : {}),
  };
}

function editablePaths(tpl: Tpl): string[] {
  const out: string[] = [];
  tpl.clauses?.forEach((c, i) => {
    out.push(`/clauses/${i}/action`);
    c.proposed_conditions.forEach((_, j) => out.push(`/clauses/${i}/proposed_conditions/${j}`));
  });
  tpl.conditional_alternatives?.forEach((c, i) => {
    out.push(`/conditional_alternatives/${i}/action`);
    c.proposed_conditions.forEach((_, j) => out.push(`/conditional_alternatives/${i}/proposed_conditions/${j}`));
    c.proposed_changes.forEach((_, j) => out.push(`/conditional_alternatives/${i}/proposed_changes/${j}`));
  });
  return out;
}

function getAt(tpl: Tpl, path: string): string | undefined {
  const v = path
    .split("/")
    .filter(Boolean)
    .reduce<unknown>((cur, k) => (cur && typeof cur === "object" ? (cur as Record<string, unknown>)[k] : undefined), tpl);
  return typeof v === "string" ? v : undefined;
}
function setAt(tpl: Tpl, path: string, value: string) {
  const parts = path.split("/").filter(Boolean);
  let cur = tpl as unknown as Record<string, unknown>;
  for (const k of parts.slice(0, -1)) cur = cur[k] as Record<string, unknown>;
  cur[parts[parts.length - 1]!] = value;
}

function editable(room: Room, o: Original): EditableItem[] {
  const tpl = o.edits[o.edits.length - 1]?.tpl ?? o.tpl!;
  const names = participantNames(room);
  return editablePaths(tpl).map((path) => ({ path, segments: toSegments(getAt(tpl, path)!, names) }));
}

function startGeneration(room: Room) {
  room.status = "generating";
  room.failure_reason = undefined;
  room.generatingUntil = Date.now() + GENERATE_DELAY;
  room.variant = variant();
  if (!room.included) room.included = room.submissions.map((s) => s.participant_id);
}

function advance(room: Room) {
  const now = Date.now();
  if (room.scenarioStatus === "preparing" && now >= room.scenarioReadyAt) room.scenarioStatus = "ready";
  if (room.status === "generating" && room.generatingUntil && now >= room.generatingUntil) {
    const attempt = room.originals.length + 1;
    const base = { result_id: rid("res"), attempt, created_at: new Date().toISOString(), included: room.included!, edits: [] };
    if (room.variant === "fail") {
      room.originals.push({ ...base, state: "failed" });
      room.status = "failed";
      room.failure_reason = "call_error";
      // 다음 재시도는 성공하도록 되돌린다.
      try {
        localStorage.setItem(MOCK_VARIANT, "proposed");
      } catch {
        /* 무시 */
      }
    } else {
      room.originals.push({ ...base, state: "normal", tpl: makeTpl(room.variant ?? "proposed", room.included!) });
      room.status = "ready";
    }
    room.generatingUntil = undefined;
  }
}

function memoQuote(room: Room, text: string): boolean {
  for (const s of room.submissions)
    for (const memo of s.memos)
      for (let i = 0; i + 15 <= memo.length; i++) if (text.includes(memo.slice(i, i + 15))) return true;
  return false;
}

function handle(req: TransportRequest, db: DB): TransportResponse {
  const path = req.path.replace(/^\/api/, "");
  const body = (req.body ?? {}) as Record<string, unknown>;
  if (req.method === "GET" && path === "/push/vapid-public-key") return ok(200, { public_key: "mock" });

  if (req.method === "POST" && path === "/rooms") {
    const trip = body.trip as Trip;
    const profiles = body.participant_profiles as ProfileInput[];
    if (!trip?.destination || !profiles?.every((p) => p.display_name)) return err(422, "needs_information");
    if (trip.party_size < 2 || trip.party_size > 8 || profiles.length !== trip.party_size) return err(422, "invalid_input");
    const code = Math.random().toString(36).slice(2, 10);
    const token = rid("host");
    db[code] = {
      code,
      token,
      trip,
      profiles,
      scenarioReadyAt: Date.now() + SCENARIO_DELAY,
      scenarioStatus: "preparing",
      status: "open",
      submissions: [],
      sessions: {},
      idem: {},
      originals: [],
      selected: null,
    };
    const now = new Date();
    return ok(201, {
      room_code: code,
      host_token: token,
      created_at: now.toISOString(),
      expires_at: new Date(now.getTime() + 30 * 864e5).toISOString(),
      scenario_status: "preparing",
    });
  }

  const m = /^\/rooms\/([^/]+)(\/.*)?$/.exec(path);
  if (!m) return err(404, "not_found");
  const room = db[decodeURIComponent(m[1]!)];
  if (!room) return err(404, "not_found");
  advance(room);
  const sub = m[2] ?? "";
  const isHost = req.headers["X-Host-Token"] === room.token;
  const needHost = () => (isHost ? null : err(403, "host_forbidden"));

  if (req.method === "GET" && sub === "") {
    return ok(200, {
      room_status: room.status,
      scenario_status: room.scenarioStatus,
      party_size: room.trip.party_size,
      submitted_count: room.submissions.length,
      profiles: room.profiles.map((p) => ({
        profile_id: p.profile_id,
        display_name: p.display_name,
        has_submission: room.submissions.some((s) => s.profile_id === p.profile_id),
      })),
      ...(room.failure_reason ? { failure_reason: room.failure_reason } : {}),
    });
  }
  if (req.method === "POST" && sub === "/sessions") {
    if (room.status !== "open") return err(409, "room_closed");
    if (room.scenarioStatus !== "ready") return err(409, "invalid_state");
    const pid = body.profile_id as string;
    if (!room.profiles.some((p) => p.profile_id === pid)) return err(404, "not_found");
    const session_id = rid("ses");
    room.sessions[session_id] = { profile_id: pid, used: false };
    return ok(201, {
      session_id,
      duplicate_name_notice: room.submissions.some((s) => s.profile_id === pid),
      privacy_notice:
        "선택과 메모 원문은 다른 사람에게 공개되지 않아요. 다만 답변에 담긴 바람과 한계는 선택한 이름과 함께 추천 결과에 반영될 수 있어요.",
      scenarios: scenariosFor(room, pid),
    });
  }
  if (req.method === "POST" && sub === "/submissions") {
    const key = req.headers["Idempotency-Key"];
    if (!key) return err(422, "invalid_input");
    const raw = JSON.stringify(body);
    const prev = room.idem[key];
    if (prev) return prev.body === raw ? ok(200, prev.resp) : err(409, "idempotency_conflict");
    const ses = room.sessions[body.session_id as string];
    if (!ses) return err(404, "not_found");
    if (room.status !== "open") return err(409, "room_closed");
    if (ses.used) return err(409, "session_used");
    const answers = body.answers as { scenario_id: string; option_id: string; memo?: string }[];
    const valid =
      answers.length === SCENARIOS.length &&
      SCENARIOS.every((s) => {
        const a = answers.filter((x) => x.scenario_id === s.scenario_id);
        return a.length === 1 && s.options.some((o) => o.option_id === a[0]!.option_id) && (a[0]!.memo ?? "").length <= 300;
      });
    if (!valid) return err(422, "invalid_input");
    ses.used = true;
    const participant_id = rid("pt");
    room.submissions.push({ participant_id, profile_id: ses.profile_id, memos: answers.map((a) => a.memo ?? "").filter(Boolean) });
    const resp = { participant_id, submitted_count: room.submissions.length, party_size: room.trip.party_size };
    room.idem[key] = { body: raw, resp };
    if (room.submissions.length >= room.trip.party_size) startGeneration(room);
    return ok(201, resp);
  }
  if (req.method === "POST" && sub === "/generate") {
    const f = needHost();
    if (f) return f;
    if (room.status !== "open") return err(409, "room_closed");
    if (room.submissions.length === 0) return err(409, "no_submissions");
    startGeneration(room);
    return ok(202, { room_status: "generating", included_count: room.submissions.length });
  }
  if (req.method === "POST" && sub === "/retry") {
    const f = needHost();
    if (f) return f;
    if (room.status !== "failed") return err(409, "invalid_state");
    startGeneration(room);
    return ok(202, {});
  }
  if (req.method === "POST" && sub === "/regenerate") {
    const f = needHost();
    if (f) return f;
    if (room.originals.filter((o) => o.state === "normal").length >= 2) return err(409, "regeneration_limit");
    if (room.status !== "ready") return err(409, "invalid_state");
    startGeneration(room);
    return ok(202, {});
  }
  if (req.method === "GET" && sub === "/result") {
    const o = room.originals.find((x) => x.result_id === room.selected) ?? room.originals.find((x) => x.state === "normal");
    if (!o) return err(409, "invalid_state");
    return ok(200, shared(room, o, o.edits[o.edits.length - 1]));
  }
  if (req.method === "GET" && sub === "/results") {
    const f = needHost();
    if (f) return f;
    const results: ResultEntry[] = room.originals.map((o) =>
      o.state === "failed"
        ? { result_id: o.result_id, attempt: o.attempt, state: "failed", created_at: o.created_at }
        : { ...shared(room, o), attempt: o.attempt, state: "normal", created_at: o.created_at, editable: editable(room, o) }
    );
    return ok(200, { selected_result_id: room.selected, results });
  }
  const rm = /^\/results\/([^/]+)\/(select|edits)$/.exec(sub);
  if (req.method === "POST" && rm) {
    const f = needHost();
    if (f) return f;
    const o = room.originals.find((x) => x.result_id === decodeURIComponent(rm[1]!));
    if (!o) return err(404, "not_found");
    if (rm[2] === "select") {
      if (o.state !== "normal") return err(409, "invalid_state");
      room.selected = o.result_id;
      return ok(200, { selected_result_id: o.result_id });
    }
    if (o.state !== "normal") return err(422, "edit_not_allowed");
    const last = o.edits[o.edits.length - 1];
    const tpl = structuredClone(last?.tpl ?? o.tpl!);
    const allowed = new Set(editablePaths(tpl));
    for (const e of (body.edits as { path: string; text: string }[]) ?? []) {
      const before = getAt(tpl, e.path);
      if (!allowed.has(e.path) || before === undefined || tokenSignature(before) !== tokenSignature(e.text))
        return err(422, "edit_not_allowed");
      if (memoQuote(room, e.text)) return err(422, "memo_quote");
      setAt(tpl, e.path, e.text);
    }
    const version = { result_id: rid("edit"), source_result_id: last?.result_id ?? o.result_id, tpl };
    o.edits.push(version);
    return ok(201, shared(room, o, version));
  }
  if (req.method === "POST" && sub === "/push-subscriptions") {
    if (body.role === "host") {
      const f = needHost();
      if (f) return f;
    }
    return ok(201, { subscription_id: rid("sub") });
  }
  return err(404, "not_found");
}

export const mockTransport: Transport = async (req) => {
  await new Promise((r) => setTimeout(r, 250));
  const db = load();
  const res = handle(req, db);
  save(db);
  return res;
};
