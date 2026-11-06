import { describe, expect, it } from "vitest";
import type { EditableItem, Segment } from "../api/types";
import { changedEdits, displaySegments, serializeSegments } from "../lib/editable";

const segs: Segment[] = [
  { participant_id: "pt_a", display: "민준은", pair: "은/는" },
  { text: " 카페에서 쉬고, " },
  { participant_id: "pt_b", display: "지수", pair: null },
  { text: " 씨와 저녁에 만나요." },
];

describe("편집 칩 직렬화(결정 34)", () => {
  it("칩을 {{participant:ID}} + pair로 되돌리고, pair가 null이면 아무것도 붙이지 않는다", () => {
    expect(serializeSegments(segs)).toBe(
      "{{participant:pt_a}}은/는 카페에서 쉬고, {{participant:pt_b}} 씨와 저녁에 만나요."
    );
  });

  it("화면 문장은 text와 display를 차례로 이은 것이다", () => {
    expect(displaySegments(segs)).toBe("민준은 카페에서 쉬고, 지수 씨와 저녁에 만나요.");
  });

  it("바뀐 위치만 편집 요청에 넣는다", () => {
    const original: EditableItem[] = [
      { path: "/clauses/0/action", segments: segs },
      { path: "/clauses/1/action", segments: [{ text: "노을을 먼저 봐요." }] },
    ];
    const draft = {
      "/clauses/0/action": segs.map((s, i) => (i === 1 ? { text: " 숙소에서 쉬고, " } : s)),
      "/clauses/1/action": [{ text: "노을을 먼저 봐요." }],
    };
    expect(changedEdits(original, draft)).toEqual([
      {
        path: "/clauses/0/action",
        text: "{{participant:pt_a}}은/는 숙소에서 쉬고, {{participant:pt_b}} 씨와 저녁에 만나요.",
      },
    ]);
  });
});
