import type { ReactNode } from "react";

/**
 * docs/PRIVACY.md를 그리는 작은 마크다운 변환기(제목·문단·목록·표·인용·굵게·링크).
 * 저장소 안 문서 링크(.md, 상대 경로)는 화면에서 열 수 없으므로 글자만 남긴다.
 */
function inline(text: string): ReactNode[] {
  const out: ReactNode[] = [];
  const re = /\*\*([^*]+)\*\*|\[([^\]]+)\]\(([^)]+)\)|`([^`]+)`/g;
  let last = 0;
  let m: RegExpExecArray | null;
  let k = 0;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    if (m[1]) out.push(<strong key={k++}>{m[1]}</strong>);
    else if (m[2]) {
      const href = m[3]!;
      out.push(/^https?:\/\//.test(href) ? <a key={k++} href={href} rel="noreferrer">{m[2]}</a> : m[2]);
    } else if (m[4]) out.push(m[4]);
    last = re.lastIndex;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** "## 7. 이용자의 권리" 또는 "## 제12조(…)" → "sec-7", "sec-12" */
export function headingId(text: string): string | undefined {
  const m = /^(?:제)?(\d+)(?:\.|조)/.exec(text.trim());
  return m ? `sec-${m[1]}` : undefined;
}

/** 삭제 요청 연락처가 있는 절. §12가 있으면 그 절, 없으면 '권리' 절. */
export function contactSectionId(md: string): string | undefined {
  const heads = md.split("\n").filter((l) => l.startsWith("## ")).map((l) => l.slice(3));
  const twelve = heads.find((h) => /^(?:제)?12(?:\.|조)/.test(h));
  const rights = heads.find((h) => h.includes("권리"));
  return headingId(twelve ?? rights ?? "");
}

export function Markdown({ source }: { source: string }) {
  const lines = source.split(/\r?\n/);
  const blocks: ReactNode[] = [];
  let i = 0;
  let k = 0;
  while (i < lines.length) {
    const line = lines[i]!;
    if (!line.trim()) {
      i++;
      continue;
    }
    if (line.startsWith("# ")) {
      blocks.push(<h1 key={k++}>{inline(line.slice(2))}</h1>);
      i++;
    } else if (line.startsWith("## ")) {
      const t = line.slice(3);
      blocks.push(
        <h2 key={k++} id={headingId(t)}>
          {inline(t)}
        </h2>
      );
      i++;
    } else if (line.startsWith(">")) {
      const buf: string[] = [];
      while (i < lines.length && lines[i]!.startsWith(">")) buf.push(lines[i++]!.replace(/^>\s?/, ""));
      blocks.push(<blockquote key={k++}>{inline(buf.join(" "))}</blockquote>);
    } else if (line.startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i]!.startsWith("|")) {
        const cells = lines[i++]!.split("|").slice(1, -1).map((c) => c.trim());
        if (!cells.every((c) => /^:?-+:?$/.test(c))) rows.push(cells);
      }
      const [head, ...body] = rows;
      blocks.push(
        <div className="table-wrap" key={k++}>
          <table>
            <thead>
              <tr>{head?.map((c, j) => <th key={j}>{inline(c)}</th>)}</tr>
            </thead>
            <tbody>
              {body.map((r, ri) => (
                <tr key={ri}>{r.map((c, j) => <td key={j}>{inline(c)}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    } else if (/^[-*] /.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^[-*] /.test(lines[i]!)) items.push(lines[i++]!.slice(2));
      blocks.push(
        <ul key={k++}>
          {items.map((t, j) => (
            <li key={j}>{inline(t)}</li>
          ))}
        </ul>
      );
    } else {
      const buf: string[] = [];
      while (i < lines.length && lines[i]!.trim() && !/^(#|>|\||[-*] )/.test(lines[i]!)) buf.push(lines[i++]!);
      blocks.push(<p key={k++}>{inline(buf.join(" "))}</p>);
    }
  }
  return <div className="doc">{blocks}</div>;
}
