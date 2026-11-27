import type { ShowdownBoard, ShowdownItem } from "../api/types";

export const HOW_LABEL: Record<"compromise" | "duel" | "lottery" | "talk", string> = {
  compromise: "절충",
  duel: "가위바위보",
  lottery: "제비뽑기",
  talk: "직접 정하기",
};
const OPEN_RULE = "이건 그때 편한 쪽으로 정해요";
export const TALK_RULE = "승부 없이 직접 이야기해서 정하기로 했어요";

function RuleRow({ item, index }: { item: ShowdownItem; index: number }) {
  const how = item.showdown?.result?.how;
  return (
    <li className="rule-row">
      <span className="rule-number" aria-hidden="true">{index + 1}</span>
      <div className="stack-sm">
        {item.title && <p className="t-caption muted">{item.title}</p>}
        <p className="rule-text">{item.rule ?? (how === "talk" ? TALK_RULE : OPEN_RULE)}</p>
        {how && <p className="showdown-badge">{HOW_LABEL[how]}</p>}
      </div>
    </li>
  );
}

/** 협약서 아래에 두는 한 줄 약속 목록. 통한 약속과 승부처에서 정한 결과를 문항 순서로 보여 준다. */
export function ShowdownRules({ board }: { board: ShowdownBoard }) {
  const settled = board.items.filter((item) => !item.showdown || item.showdown.phase === "done");
  if (settled.length === 0) return null;
  return (
    <section className="stack-lg showdown-rules" aria-label="한 줄 약속">
      <h2 className="t-headline-md">한 줄 약속</h2>
      <ol className="rule-list">
        {settled.map((item, index) => (
          <RuleRow key={item.scenario_id} item={item} index={index} />
        ))}
      </ol>
      <p className="t-body-sm secondary">
        각자의 답을 규칙에 따라 한 줄로 정리했어요. 누가 무엇을 골랐는지는 보이지 않아요.
      </p>
    </section>
  );
}
