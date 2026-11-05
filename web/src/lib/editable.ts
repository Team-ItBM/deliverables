import type { EditableItem, Segment } from "../api/types";

export function isParticipant(seg: Segment): seg is Extract<Segment, { participant_id: string }> {
  return (seg as { participant_id?: unknown }).participant_id !== undefined;
}

/** 칩은 "{{participant:ID}}" + pair로 되돌린다. pair가 null이면 아무것도 붙이지 않는다(결정 34). */
export function serializeSegments(segments: Segment[]): string {
  return segments
    .map((s) => (isParticipant(s) ? `{{participant:${s.participant_id}}}${s.pair ?? ""}` : s.text))
    .join("");
}

/** 화면에 보이는 문장. text와 display를 차례로 잇는다. */
export function displaySegments(segments: Segment[]): string {
  return segments.map((s) => (isParticipant(s) ? s.display : s.text)).join("");
}

/** 바뀐 위치만 편집 요청에 넣는다. */
export function changedEdits(
  original: EditableItem[],
  draft: Record<string, Segment[]>
): { path: string; text: string }[] {
  const edits: { path: string; text: string }[] = [];
  for (const item of original) {
    const next = draft[item.path];
    if (!next) continue;
    const before = serializeSegments(item.segments);
    const after = serializeSegments(next);
    if (after !== before) edits.push({ path: item.path, text: after });
  }
  return edits;
}

/** "/clauses/0/proposed_conditions/1" → "제1조 제안 조건 2" */
export function pathLabel(path: string): string {
  const p = path.split("/").filter(Boolean);
  const n = (i: string | undefined) => Number(i ?? 0) + 1;
  const head = p[0] === "clauses" ? `제${n(p[1])}조` : `조건부 대안 ${n(p[1])}`;
  if (p[2] === "action") return `${head} 문장`;
  if (p[2] === "proposed_conditions") return `${head} 제안 조건 ${n(p[3])}`;
  if (p[2] === "proposed_changes") return `${head} 필요한 변경 ${n(p[3])}`;
  return `${head} ${p.slice(2).join(" ")}`;
}

/** 공유 결과 사본의 path 위치 문장을 바꾼다(JSON Pointer, 배열·객체만). */
export function setAtPointer<T>(obj: T, path: string, value: string): T {
  const parts = path.split("/").filter(Boolean);
  const copy = structuredClone(obj) as unknown as Record<string, unknown>;
  let cur: unknown = copy;
  for (let i = 0; i < parts.length - 1; i++) {
    if (cur === null || typeof cur !== "object") return obj;
    cur = (cur as Record<string, unknown>)[parts[i]!];
  }
  if (cur !== null && typeof cur === "object") {
    (cur as Record<string, unknown>)[parts[parts.length - 1]!] = value;
  }
  return copy as unknown as T;
}
