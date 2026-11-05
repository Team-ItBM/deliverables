import type { CSSProperties } from "react";

// 복숭아나무 가지(DESIGN.md pact-branch). start·span은 가지 시간(motion.branch)에서의 비율이다.
// 색은 요소마다 속성으로 둔다. 저장 이미지 라이브러리가 CSS로 상속한 fill·stroke를 옮기지 못한다.
const BARK = { stroke: "#8A6A4A", strokeOpacity: 0.3 };
const BLOSSOM = { fill: "#EBB8B1", fillOpacity: 0.45 };
const STEMS = [
  { d: "M172 4C150 14 132 16 112 30", w: 3.4, start: 0, span: 0.35 },
  { d: "M112 30C96 40 82 44 64 62", w: 2.2, start: 0.3, span: 0.35 },
  { d: "M64 62C54 72 44 78 30 84", w: 1.2, start: 0.6, span: 0.35 },
  { d: "M150 12C156 28 154 40 160 56", w: 1.2, start: 0.15, span: 0.35 },
  { d: "M132 18C130 34 134 46 128 62", w: 1.4, start: 0.2, span: 0.35 },
  { d: "M96 40C98 54 92 66 94 84", w: 1.1, start: 0.4, span: 0.35 },
  { d: "M76 48C66 46 56 40 46 40", w: 1, start: 0.5, span: 0.35 },
];

type Kind = "full" | "half" | "bud";
const FLOWERS: { x: number; y: number; kind: Kind; at: number; turn: number }[] = [
  { x: 140, y: 30, kind: "full", at: 0.1, turn: 10 },
  { x: 112, y: 22, kind: "bud", at: 0.2, turn: -30 },
  { x: 160, y: 56, kind: "half", at: 0.25, turn: 170 },
  { x: 128, y: 62, kind: "full", at: 0.3, turn: 40 },
  { x: 118, y: 46, kind: "bud", at: 0.35, turn: 200 },
  { x: 88, y: 36, kind: "half", at: 0.4, turn: -20 },
  { x: 94, y: 84, kind: "full", at: 0.45, turn: 25 },
  { x: 64, y: 62, kind: "full", at: 0.5, turn: 60 },
  { x: 46, y: 40, kind: "half", at: 0.52, turn: -60 },
  { x: 52, y: 78, kind: "half", at: 0.56, turn: 150 },
  { x: 30, y: 84, kind: "bud", at: 0.6, turn: 240 },
];

function Petals({ kind }: { kind: Kind }) {
  if (kind === "bud") return <ellipse rx="2.8" ry="4.2" cy="-1" {...BLOSSOM} />;
  const angles = kind === "full" ? [0, 72, 144, 216, 288] : [-46, 0, 46];
  return (
    <>
      {angles.map((a) => (
        <ellipse key={a} rx="3.6" ry="5.4" cy="-5.2" transform={`rotate(${a})`} {...BLOSSOM} />
      ))}
    </>
  );
}

export function PactBranch({ corner }: { corner: "top" | "bottom" }) {
  return (
    <svg className={`pact-branch pact-branch-${corner}`} viewBox="0 0 172 104" aria-hidden="true">
      <g className="pact-stems">
        {STEMS.map((s) => (
          <path
            key={s.d}
            d={s.d}
            fill="none"
            strokeWidth={s.w}
            strokeLinecap="round"
            {...BARK}
            pathLength={1}
            style={{ "--start": s.start, "--span": s.span } as CSSProperties}
          />
        ))}
      </g>
      {FLOWERS.map((f) => (
        <g key={`${f.x}-${f.y}`} transform={`translate(${f.x} ${f.y}) rotate(${f.turn})`}>
          <g className="pact-flower" style={{ "--start": f.at } as CSSProperties}>
            <Petals kind={f.kind} />
          </g>
        </g>
      ))}
    </svg>
  );
}

const PETALS = [
  { side: "left", x: 0, delay: 0, size: 1, opacity: 0.8 },
  { side: "left", x: 5, delay: 4.5, size: 0.8, opacity: 0.6 },
  { side: "left", x: 2, delay: 8.5, size: 0.9, opacity: 0.5 },
  { side: "right", x: 3, delay: 2, size: 0.9, opacity: 0.7 },
  { side: "right", x: 0, delay: 6.5, size: 1, opacity: 0.55 },
  { side: "right", x: 5, delay: 10.5, size: 0.8, opacity: 0.65 },
] as const;

/** 결과 화면 양옆 가장자리의 꽃잎. 본문을 지나지 않고 저장 이미지에도 들어가지 않는다. */
export function PetalDrift() {
  return (
    <div className="petals" aria-hidden="true">
      {PETALS.map((p, i) => (
        <span
          key={i}
          className="petal"
          style={
            {
              [p.side]: `${p.x}px`,
              "--delay": `${p.delay}s`,
              "--size": p.size,
              "--peak": p.opacity,
            } as CSSProperties
          }
        />
      ))}
    </div>
  );
}
