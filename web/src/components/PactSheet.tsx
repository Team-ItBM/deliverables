import { PencilLine } from "lucide-react";
import { forwardRef, useId, type CSSProperties } from "react";
import type { Clause, ConditionalAlternative, SharedResult, UnresolvedCondition } from "../api/types";
import { tripMetaText } from "../lib/trip";
import type { IssuePhase } from "../lib/issue";
import { PactBranch } from "./PactBranch";
import { ICON } from "./ui";

/**
 * 공유 결과(§0-C)를 그리는 하나의 컴포넌트. 화면과 저장 이미지가 같은 함수를 쓴다(AC13).
 * 여기서 읽는 필드만 화면에 나온다. 계약에 없는 필드(메모, positions, original_condition 등)는
 * 응답에 섞여 와도 읽지 않는다.
 */
export interface SheetProps {
  result: Partial<SharedResult>;
  /** 발급 연출의 단계. 없거나 done이면 완성 상태다. */
  phase?: IssuePhase;
  capture?: boolean;
  /** 방장 화면에서 수정 문장을 덮어 그린 경우. 서버 label이 없을 때 '방장 수정'을 붙인다. */
  edited?: boolean;
  /** 랜딩의 예시 종이. '예시'를 표시하고 가지와 꽃은 그리지 않는다. */
  sample?: boolean;
}

const HOST_EDITED = "방장 수정";

export function hasPaper(status: SharedResult["pact_status"] | undefined): boolean {
  return status === "proposed" || status === "conditional_only";
}

function InclusionNote({ result }: { result: Partial<SharedResult> }) {
  const excluded = result.excluded_names ?? [];
  return (
    <>
      {typeof result.included_count === "number" && (
        <p>
          반영한 응답 <span className="t-numeral">{result.included_count}</span>건
        </p>
      )}
      {excluded.length > 0 && (
        <p>아직 응답이 반영되지 않은 이름: {excluded.join(", ")}. 이 사람들의 의견은 들어 있지 않아요.</p>
      )}
      <p className="pact-disclaimer">AI가 각자의 응답을 바탕으로 만든 추천안이에요. 동행 모두가 정한 약속은 아니에요.</p>
    </>
  );
}

function Labels({ result, edited, sample }: { result: Partial<SharedResult>; edited?: boolean; sample?: boolean }) {
  const hostLabel = result.kind === "host_edited" ? result.label || HOST_EDITED : edited ? HOST_EDITED : null;
  if (!result.draft && !hostLabel && !sample) return null;
  return (
    <div className="pact-labels">
      {sample && <span className="draft-label">예시</span>}
      {result.draft && (
        <span className="draft-block">
          <span className="draft-label">초안</span>
          <span className="draft-note">방장이 고르기 전이에요</span>
        </span>
      )}
      {hostLabel && (
        <span className="host-label">
          <PencilLine size={16} strokeWidth={1.5} aria-hidden />
          {hostLabel}
        </span>
      )}
    </div>
  );
}

function SubList({ label, items }: { label: string; items: string[] | undefined | null }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="pact-sub">
      <p className="pact-sub-label">{label}</p>
      <ul>
        {items.map((t, i) => (
          <li key={i}>{t}</li>
        ))}
      </ul>
    </div>
  );
}

function Names({ names }: { names: string[] | undefined }) {
  if (!names || names.length === 0) return null;
  return <p className="pact-names">적용 대상: {names.join(", ")}</p>;
}

function UnresolvedList({ items }: { items: UnresolvedCondition[] }) {
  return (
    <ul className="stack-sm">
      {items.map((u, i) => (
        <li key={`${u.scenario_id}-${i}`}>{u.description}</li>
      ))}
    </ul>
  );
}

export function Stamp() {
  const id = useId().replace(/:/g, "");
  return (
    <div className="stamp" aria-hidden="true">
      <svg viewBox="0 0 88 88">
        <defs>
          <filter id={`ink-${id}`} x="-10%" y="-10%" width="120%" height="120%">
            <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="7" result="noise" />
            <feDisplacementMap in="SourceGraphic" in2="noise" scale="1.6" result="rough" />
            <feComponentTransfer in="noise" result="holes">
              <feFuncA type="discrete" tableValues="1 1 1 1 1 1 1 0.75" />
            </feComponentTransfer>
            <feComposite in="rough" in2="holes" operator="in" />
          </filter>
        </defs>
        <g filter={`url(#ink-${id})`} fill="none" stroke="currentColor">
          <circle cx="44" cy="44" r="40" strokeWidth="3" />
          <text
            x="44"
            y="40"
            textAnchor="middle"
            fill="currentColor"
            stroke="none"
            fontFamily="Noto Serif KR, serif"
            fontWeight={600}
            fontSize="18"
          >
            도원
          </text>
          <text
            x="44"
            y="62"
            textAnchor="middle"
            fill="currentColor"
            stroke="none"
            fontFamily="Noto Serif KR, serif"
            fontWeight={600}
            fontSize="18"
          >
            결의
          </text>
        </g>
      </svg>
    </div>
  );
}

function ClauseItem({ clause, index }: { clause: Clause; index: number }) {
  return (
    <li className="pact-clause" style={{ "--i": index } as CSSProperties}>
      <p className="pact-clause-number">제{index + 1}조</p>
      <p>{clause.action}</p>
      <Names names={clause.participant_names} />
      <SubList label="제안 조건" items={clause.proposed_conditions} />
    </li>
  );
}

function AlternativeItem({ alt, index }: { alt: ConditionalAlternative; index: number }) {
  return (
    <li className="pact-clause">
      <p className="pact-sub-label">대안 {index + 1}</p>
      <p>{alt.action}</p>
      <Names names={alt.participant_names} />
      <SubList label="제안 조건" items={alt.proposed_conditions} />
      <SubList label="필요한 변경" items={alt.proposed_changes} />
    </li>
  );
}

export const PactPaper = forwardRef<HTMLDivElement, SheetProps>(function PactPaper(
  { result, phase, capture, edited, sample },
  ref
) {
  const clauses = result.pact_status === "conditional_only" ? [] : (result.clauses ?? []);
  const alts = result.conditional_alternatives ?? [];
  const unresolved = result.unresolved_conditions ?? [];
  const tripMeta = result.trip ? tripMetaText(result.trip) : null;
  return (
    <article
      ref={ref}
      className={`pact-paper${phase && phase !== "done" ? " issue" : ""}${phase === "stamped" ? " stamp-go" : ""}${capture ? " capture" : ""}`}
      aria-label="여행 동행 협약서"
    >
      {!sample && <PactBranch corner="top" />}
      {!sample && <PactBranch corner="bottom" />}
      <div className="pact-head">
        <span className="t-wordmark">도원결의</span>
        <Labels result={result} edited={edited} sample={sample} />
      </div>
      <div className="pact-title-block">
        <h2 className="pact-title">여행 동행 협약서</h2>
        <span className="pact-underline" aria-hidden="true" />
        {tripMeta && <p className="pact-meta">{tripMeta}</p>}
      </div>
      {clauses.length > 0 && (
        <ol className="pact-clauses">
          {clauses.map((c, i) => (
            <ClauseItem key={`${c.scenario_id}-${i}`} clause={c} index={i} />
          ))}
        </ol>
      )}
      {alts.length > 0 && (
        <section className="pact-block" style={{ "--i": clauses.length } as CSSProperties}>
          <h3 className="pact-block-title">조건부 대안</h3>
          <ol className="pact-clauses">
            {alts.map((a, i) => (
              <AlternativeItem key={`${a.scenario_id}-${i}`} alt={a} index={i} />
            ))}
          </ol>
        </section>
      )}
      {unresolved.length > 0 && (
        <section className="pact-block" style={{ "--i": clauses.length + (alts.length > 0 ? 1 : 0) } as CSSProperties}>
          <h3 className="pact-block-title">아직 풀지 못한 조건</h3>
          <UnresolvedList items={unresolved} />
        </section>
      )}
      {result.message && <p className="pact-message">{result.message}</p>}
      <footer className="pact-footer">
        <p className="pact-issued">추천안 발급</p>
        <InclusionNote result={result} />
        <Stamp />
      </footer>
    </article>
  );
});

/** pact_status가 unresolved일 때만. 도장이 없다(DESIGN.md unresolved-panel). */
export const UnresolvedPanel = forwardRef<HTMLDivElement, SheetProps>(function UnresolvedPanel(
  { result, capture, edited },
  ref
) {
  const unresolved = result.unresolved_conditions ?? [];
  const humor = result.pact_status === "unresolved" ? result.humor : null;
  return (
    <section ref={ref} className={`unresolved-panel${capture ? " capture" : ""}`} aria-label="추천 결과">
      <Labels result={result} edited={edited} />
      {humor && <h2 className="t-headline-md">{humor.text}</h2>}
      {humor && <p>{humor.explanation}</p>}
      {unresolved.length > 0 && <UnresolvedList items={unresolved} />}
      {result.message && <p className="pact-message">{result.message}</p>}
      <div className="pact-meta" style={{ textAlign: "left" }}>
        <InclusionNote result={result} />
      </div>
    </section>
  );
});

/** 정보 부족·지원 밖·입력 오류 결과. 유머 문구와 도장을 쓰지 않는다. */
export const StatusPanel = forwardRef<HTMLDivElement, SheetProps>(function StatusPanel(
  { result, capture, edited },
  ref
) {
  const unresolved = result.unresolved_conditions ?? [];
  const heading =
    result.pact_status === "needs_information"
      ? "추천을 만들 정보가 부족했어요"
      : result.pact_status === "unsupported"
        ? "도원결의가 다루지 않는 상황이에요"
        : "입력에 문제가 있어 추천을 만들지 못했어요";
  return (
    <section ref={ref} className={`unresolved-panel${capture ? " capture" : ""}`} aria-label="추천 결과">
      <Labels result={result} edited={edited} />
      <h2 className="t-headline-md">{heading}</h2>
      {result.message && <p>{result.message}</p>}
      {unresolved.length > 0 && <UnresolvedList items={unresolved} />}
      <div className="pact-meta" style={{ textAlign: "left" }}>
        <InclusionNote result={result} />
      </div>
    </section>
  );
});

/** 나타날 묶음 수. 발급 연출의 시간표가 쓴다. */
export function issueItemCount(result: Partial<SharedResult>): number {
  const clauses = result.pact_status === "conditional_only" ? 0 : (result.clauses?.length ?? 0);
  const alts = result.conditional_alternatives?.length ? 1 : 0;
  const unresolved = result.unresolved_conditions?.length ? 1 : 0;
  return clauses + alts + unresolved;
}

export const ResultSheet = forwardRef<HTMLDivElement, SheetProps>(function ResultSheet(props, ref) {
  const s = props.result.pact_status;
  if (hasPaper(s)) return <PactPaper ref={ref} {...props} />;
  if (s === "unresolved") return <UnresolvedPanel ref={ref} {...props} />;
  return <StatusPanel ref={ref} {...props} />;
});

export { ICON };
