import { act, cleanup, render } from "@testing-library/react";
import { useRef } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SharedResult } from "../api/types";
import { ResultSheet } from "../components/PactSheet";
import { issueTimeline, useIssueSequence } from "../lib/issue";
import { issueSoundFor, setSoundEnabled, SILENT, soundEnabled, unlockSound, type IssueSound } from "../lib/issueSound";

const result: SharedResult = {
  result_id: "r1",
  kind: "ai_original",
  label: null,
  draft: false,
  pact_status: "proposed",
  included_count: 2,
  excluded_names: [],
  trip: { destination: "제주", duration_days: 3, party_size: 2 },
  clauses: [{ scenario_id: "a", participant_names: ["민준"], action: "조항", proposed_conditions: [] }],
  conditional_alternatives: null,
  unresolved_conditions: null,
};

function Sheet({ sound }: { sound: IssueSound }) {
  const ref = useRef<HTMLDivElement>(null);
  const phase = useIssueSequence(true, ref, 1, sound);
  return <ResultSheet ref={ref} result={result} phase={phase} />;
}

beforeEach(() => {
  window.localStorage.clear();
  vi.useFakeTimers();
  window.scrollTo = () => {};
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("발급 시간표", () => {
  it("종이가 펼쳐진 뒤 조항이 이어지고 마지막 조항 다음에 도장을 찍는다", () => {
    const t = issueTimeline(3);
    expect(t.clauseAt(0)).toBe(1100);
    expect(t.clauseAt(2)).toBe(1540);
    expect(t.stampAt).toBe(1100 + 2 * 220 + 640);
  });
});

describe("발급 연출", () => {
  it("도장과 가지가 같은 순간 시작하고 끝나면 완성 상태가 된다", () => {
    const calls: string[] = [];
    const sound: IssueSound = {
      paper: () => calls.push("paper"),
      clause: () => calls.push("clause"),
      stamp: () => calls.push("stamp"),
      branch: () => calls.push("branch"),
    };
    const { container } = render(<Sheet sound={sound} />);
    const paper = () => container.querySelector(".pact-paper")!;
    expect(paper().classList.contains("issue")).toBe(true);
    expect(paper().classList.contains("stamp-go")).toBe(false);
    act(() => {
      vi.advanceTimersByTime(issueTimeline(1).stampAt);
    });
    expect(paper().classList.contains("stamp-go")).toBe(true);
    expect(calls).toEqual(["paper", "clause", "stamp", "branch"]);
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(paper().classList.contains("issue")).toBe(false);
  });

  it("효과음이 없어도 같은 시간에 끝난다", () => {
    const { container } = render(<Sheet sound={SILENT} />);
    act(() => {
      vi.advanceTimersByTime(issueTimeline(1).stampAt + 500);
    });
    expect(container.querySelector(".pact-paper")!.classList.contains("issue")).toBe(false);
  });
});

describe("협약서 종이", () => {
  it("화면과 저장용 모두 도장·가지·발급 표시를 그리고 저장용은 연출 클래스가 없다", () => {
    const { container } = render(<ResultSheet result={result} capture />);
    expect(container.querySelector(".pact-paper")!.className).not.toContain("issue");
    expect(container.querySelectorAll(".pact-branch").length).toBe(2);
    expect(container.querySelector(".stamp")).toBeTruthy();
    const footer = container.querySelector(".pact-footer")!.textContent ?? "";
    expect(footer).toContain("추천안 발급");
    expect(footer).toContain("동행 모두가 정한 약속은 아니에요");
  });
});

describe("효과음", () => {
  it("기본은 꺼짐이고, 직접 연 연출에서 켠 경우에만 재생 객체를 준다", () => {
    expect(soundEnabled()).toBe(false);
    expect(issueSoundFor(true)).toBe(SILENT);
    setSoundEnabled(true);
    expect(issueSoundFor(false)).toBe(SILENT);
    expect(issueSoundFor(true)).not.toBe(SILENT);
  });

  it("오디오를 만들 수 없어도 예외를 내지 않는다", () => {
    setSoundEnabled(true);
    vi.stubGlobal("AudioContext", function broken() {
      throw new Error("no audio");
    });
    expect(() => unlockSound()).not.toThrow();
    const play = issueSoundFor(true);
    expect(() => {
      play.paper();
      play.clause();
      play.stamp();
      play.branch();
    }).not.toThrow();
  });
});
