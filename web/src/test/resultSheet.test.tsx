import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SharedResult } from "../api/types";
import { PACT_DISCLAIMER, ProcessToggle, ResultSheet } from "../components/PactSheet";

function base(over: Partial<SharedResult> = {}): SharedResult {
  return {
    result_id: "r1",
    kind: "ai_original",
    source_result_id: null,
    label: null,
    draft: false,
    pact_status: "ready",
    included_count: 2,
    excluded_names: ["하늘"],
    clauses: [
      { article: 1, scenario_id: "meal", text: "여행 중 식사 메뉴에는 고기국수를 반드시 포함한다." },
      { article: 2, scenario_id: "ride", text: "놀이기구는 일행 모두가 탈 수 있는 기구를 우선한다." },
    ],
    discussion_items: [{ scenario_id: "sunset", text: "노을 감상과 소품숍 구경 중 무엇을 우선할지는 당사자 간 직접 논의하여 정한다." }],
    process: [
      {
        label: "제1조",
        scenario_id: "meal",
        title: "점심 메뉴",
        decision: "챌린지로 정함",
        first_tally: [
          { label: "고기국수 식당", count: 1 },
          { label: "갈치조림 식당", count: 1 },
        ],
        challenge_tally: [{ label: "고기국수 식당", count: 2 }],
      },
      { label: "제2조", scenario_id: "ride", title: "놀이기구", decision: "일행의 조건을 반영해 정함" },
      {
        label: "협의 사항",
        scenario_id: "sunset",
        title: "노을과 소품숍",
        decision: "챌린지에서도 갈려 직접 논의",
        first_tally: [
          { label: "바로 해변", count: 1 },
          { label: "소품숍 들르기", count: 1 },
        ],
      },
    ],
    ...over,
  };
}

function withLeaks(r: SharedResult) {
  return {
    ...r,
    memo: "MEMO_LEAK_MARKER_무릎이아파서오래못걸어요",
    positions: [{ response_id: "rsp_1", position: { reason: "POSITION_LEAK" } }],
    mbti: "INTJ_LEAK",
    clauses: r.clauses.map((c) => ({ ...c, basis: "BASIS_LEAK", source_response_ids: ["RESPONSE_ID_LEAK"] })),
  } as unknown as SharedResult;
}

describe("협약서 렌더러", () => {
  it("조항을 제n조로, 갈린 문항을 협의 사항으로 그리고 비공개 필드는 그리지 않는다", () => {
    const { container } = render(<ResultSheet result={withLeaks(base())} />);
    const text = container.textContent ?? "";
    for (const leak of ["MEMO_LEAK", "POSITION_LEAK", "INTJ_LEAK", "BASIS_LEAK", "RESPONSE_ID_LEAK", "rsp_1"]) {
      expect(text).not.toContain(leak);
    }
    expect(text).toContain("제1조");
    expect(text).toContain("제2조");
    expect(text).toContain("여행 중 식사 메뉴에는 고기국수를 반드시 포함한다.");
    expect(text).toContain("협의 사항");
    expect(text).toContain("당사자 간 직접 논의하여 정한다.");
    expect(text).toContain("협약 체결");
    expect(text).toContain(PACT_DISCLAIMER);
    expect(text).not.toContain("추천안");
    expect(container.querySelector(".stamp")).not.toBeNull();
  });

  it("협의 사항만 남아도 도장을 찍는다", () => {
    const { container } = render(<ResultSheet result={base({ clauses: [] })} />);
    expect(container.textContent).not.toContain("제1조");
    expect(container.querySelector(".stamp")).not.toBeNull();
  });

  it("정해진 과정 칸에는 조항·협의 사항이 들어가지 않는다", () => {
    const { container } = render(<ResultSheet result={base()} />);
    expect(container.textContent).not.toContain("챌린지로 정함");
    expect(container.textContent).not.toContain("1차");
  });

  it("needs_information은 도장 없이 안내만 보여 준다", () => {
    const { container } = render(
      <ResultSheet result={base({ pact_status: "needs_information", clauses: [], discussion_items: [], process: [], message: "응답이 빠졌다." })} />
    );
    expect(container.textContent).toContain("응답이 빠졌다.");
    expect(container.querySelector(".stamp")).toBeNull();
  });
});

describe("정해진 과정 더보기", () => {
  it("처음에는 접혀 있고 버튼을 누르면 펼쳐지며 한계 반영 조항에는 인원이 없다", () => {
    render(<ProcessToggle result={base()} />);
    const button = screen.getByRole("button", { name: "정해진 과정 더보기" });
    expect(button.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("챌린지로 정함")).toBeNull();
    fireEvent.click(button);
    expect(screen.getByRole("button", { name: "정해진 과정 접기" }).getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText("챌린지로 정함")).toBeTruthy();
    const meal = screen.getByText("제1조 · 점심 메뉴").parentElement!;
    expect(meal.textContent).toContain("1차고기국수 식당1명갈치조림 식당1명");
    expect(meal.textContent).toContain("챌린지고기국수 식당2명");
    const limit = screen.getByText("제2조 · 놀이기구").parentElement!;
    expect(limit.textContent).toContain("일행의 조건을 반영해 정함");
    expect(limit.textContent).not.toContain("1차");
    fireEvent.click(screen.getByRole("button", { name: "정해진 과정 접기" }));
    expect(screen.queryByText("챌린지로 정함")).toBeNull();
  });

  it("ready가 아니거나 과정이 없으면 버튼을 그리지 않는다", () => {
    const { container: a } = render(<ProcessToggle result={base({ pact_status: "needs_information" })} />);
    expect(a.querySelector("button")).toBeNull();
    const { container: b } = render(<ProcessToggle result={base({ process: [] })} />);
    expect(b.querySelector("button")).toBeNull();
  });
});
