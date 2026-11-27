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

export function pathLabel(path: string): string {
  const p = path.split("/").filter(Boolean);
  const n = Number(p[1] ?? 0) + 1;
  return p[0] === "clauses" ? `제${n}조` : `협의 사항 ${n}`;
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
