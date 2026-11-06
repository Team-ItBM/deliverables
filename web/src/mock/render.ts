// 모의 서버 전용: 서버 render.py가 할 일(토큰 치환·조사 선택)을 단순하게 흉내 낸다.
import type { Segment } from "../api/types";

const PAIRS = ["은/는", "이/가", "을/를", "과/와", "으로/로"] as const;
export const TOKEN_RE = /\{\{(participant|profile):([^}]+)\}\}(은\/는|이\/가|을\/를|과\/와|으로\/로)?/g;

function jong(word: string): number | null {
  const ch = word.charCodeAt(word.length - 1);
  if (ch < 0xac00 || ch > 0xd7a3) return null;
  return (ch - 0xac00) % 28;
}

export function withJosa(name: string, pair: string | undefined): string {
  let base = name;
  let j = jong(base.replace(/\(응답 \d+\)$/, ""));
  if (j === null) {
    base = `${name}님`;
    j = jong("님");
  }
  if (!pair) return base;
  const [withB, withoutB] = pair.split("/") as [string, string];
  if (pair === "으로/로") return base + (j !== 0 && j !== 8 ? withB : withoutB);
  return base + (j !== 0 ? withB : withoutB);
}

export function renderText(text: string, names: Record<string, string>): string {
  return text.replace(TOKEN_RE, (_m, _kind, id: string, pair?: string) => withJosa(names[id] ?? "?", pair));
}

export function toSegments(text: string, names: Record<string, string>): Segment[] {
  const segs: Segment[] = [];
  let last = 0;
  for (const m of text.matchAll(TOKEN_RE)) {
    if (m.index! > last) segs.push({ text: text.slice(last, m.index) });
    const id = m[2]!;
    segs.push({ participant_id: id, display: withJosa(names[id] ?? "?", m[3]), pair: m[3] ?? null });
    last = m.index! + m[0].length;
  }
  if (last < text.length) segs.push({ text: text.slice(last) });
  return segs;
}

export function tokenSignature(text: string): string {
  return [...text.matchAll(TOKEN_RE)].map((m) => `${m[1]}:${m[2]}`).sort().join(",");
}

export { PAIRS };
