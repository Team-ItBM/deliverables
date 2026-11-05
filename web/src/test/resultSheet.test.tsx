import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SharedResult } from "../api/types";
import { ResultSheet } from "../components/PactSheet";

const HUMOR = { text: "너네 조합 꽝이니 여행 가지 마세요!", explanation: "이번 응답 조건에서는 추천안을 찾지 못했습니다." };

function base(over: Partial<SharedResult> = {}): SharedResult {
  return {
    result_id: "r1",
    kind: "ai_original",
    source_result_id: null,
    label: null,
    draft: false,
    pact_status: "proposed",
    included_count: 2,
    excluded_names: ["하늘"],
    clauses: [
      { scenario_id: "free_time", participant_names: ["민준", "지수"], action: "카페에서 한 시간 쉬어요.", proposed_conditions: ["피곤하면 먼저 돌아가요."] },
    ],
    conditional_alternatives: [
      {
        scenario_id: "sunset",
        participant_names: ["민준"],
        action: "민준은 노을을 봐요.",
        proposed_conditions: [],
        proposed_changes: ["쇼핑을 다음 날로 옮겨요."],
      },
    ],
    unresolved_conditions: [{ scenario_id: "budget", description: "식비 상한이 서로 달라요." }],
    ...over,
  };
}

/** 계약에 없는 비공개 필드가 응답에 섞여 와도 화면에 나오면 안 된다(AC3). */
function withLeaks(r: SharedResult) {
  return {
    ...r,
    memo: "MEMO_LEAK_MARKER_무릎이아파서오래못걸어요",
    positions: [{ response_id: "rsp_1", position: { reason: "POSITION_LEAK" } }],
    gender: "GENDER_LEAK",
    mbti: "INTJ_LEAK",
    clauses: r.clauses!.map((c) => ({ ...c, source_response_ids: ["RESPONSE_ID_LEAK"], option_id: "OPTION_LEAK" })),
    conditional_alternatives: r.conditional_alternatives!.map((c) => ({
      ...c,
      required_changes: [{ original_condition: "ORIGINAL_CONDITION_LEAK", proposed_change: "x" }],
    })),
  } as unknown as SharedResult;
}

describe("결과 렌더러", () => {
  it("비공개 필드를 그리지 않고 조항·대안·미해결·반영 안내를 그린다", () => {
    const { container } = render(<ResultSheet result={withLeaks(base())} />);
    const text = container.textContent ?? "";
    for (const leak of ["MEMO_LEAK", "POSITION_LEAK", "GENDER_LEAK", "INTJ_LEAK", "RESPONSE_ID_LEAK", "OPTION_LEAK", "ORIGINAL_CONDITION_LEAK", "rsp_1"]) {
      expect(text).not.toContain(leak);
    }
    expect(text).toContain("제1조");
    expect(text).toContain("쇼핑을 다음 날로 옮겨요.");
    expect(text).toContain("식비 상한이 서로 달라요.");
    expect(text).toContain("하늘");
    expect(text).not.toMatch(/합의|동의|수락/);
  });

  it("초안이면 '방장 확인 전 초안', 수정본이면 label을 보여 준다", () => {
    render(<ResultSheet result={base({ draft: true, kind: "host_edited", label: "방장 수정" })} />);
    expect(screen.getByText("방장 확인 전 초안")).toBeTruthy();
    expect(screen.getByText("방장 수정")).toBeTruthy();
  });

  it("초안도 수정본도 아니면 두 표시가 없다", () => {
    const { container } = render(<ResultSheet result={base()} />);
    expect(container.textContent).not.toContain("방장 확인 전 초안");
    expect(container.textContent).not.toContain("방장 수정");
  });

  it("유머 문구는 unresolved일 때만 설명과 함께 보인다", () => {
    const { container, unmount } = render(<ResultSheet result={base({ humor: HUMOR })} />);
    expect(container.textContent).not.toContain(HUMOR.text);
    unmount();
    const r = render(
      <ResultSheet
        result={base({ pact_status: "unresolved", clauses: null, conditional_alternatives: null, humor: HUMOR })}
      />
    );
    expect(r.container.textContent).toContain(HUMOR.text);
    expect(r.container.textContent).toContain(HUMOR.explanation);
    expect(r.container.textContent).toContain("식비 상한이 서로 달라요.");
    expect(r.container.querySelector(".stamp")).toBeNull();
  });

  it("needs_information에는 유머 문구를 보여 주지 않는다", () => {
    const { container } = render(
      <ResultSheet result={base({ pact_status: "needs_information", clauses: null, humor: HUMOR, message: "정보가 부족해요." })} />
    );
    expect(container.textContent).not.toContain(HUMOR.text);
    expect(container.textContent).toContain("정보가 부족해요.");
  });
});
