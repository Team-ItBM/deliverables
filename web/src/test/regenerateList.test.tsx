import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { setTransport, type Transport } from "../api/client";
import type { RoomView } from "../api/types";
import { keys, writeJSON } from "../lib/storage";
import { Result } from "../pages/Result";

vi.mock("html-to-image", () => ({ toBlob: async () => null }));

beforeEach(() => {
  window.scrollTo = () => {};
});

const room: RoomView = {
  room_status: "ready",
  scenario_status: "ready",
  party_size: 2,
  submitted_count: 2,
  profiles: [{ profile_id: "p1", display_name: "민준", has_submission: true }],
};

const paper = (id: string, attempt: number) => ({
  result_id: id,
  kind: "ai_original",
  source_result_id: null,
  label: null,
  draft: true,
  pact_status: "proposed",
  included_count: 2,
  excluded_names: [],
  clauses: [{ scenario_id: "q1", participant_names: ["민준"], action: `${attempt}번째 조항`, proposed_conditions: [] }],
  conditional_alternatives: [],
  unresolved_conditions: [],
  attempt,
  state: "normal",
  created_at: `2026-11-05T00:0${attempt}:00Z`,
  editable: [],
});

describe("재생성 결과 목록", () => {
  it("재생성이 상태 확인보다 빨리 끝나 generating을 보지 못해도 새 결과가 나온다", async () => {
    writeJSON("local", keys.host("c"), "token");
    let regenerated = false;
    let selected: string | null = null;
    const t: Transport = async (req) => {
      if (req.path.endsWith("/regenerate")) {
        regenerated = true;
        return { status: 202, body: {} };
      }
      if (req.path.endsWith("/select")) {
        selected = "r2";
        return { status: 200, body: { selected_result_id: selected } };
      }
      if (req.path.endsWith("/results")) {
        const results = regenerated ? [paper("r1", 1), paper("r2", 2)] : [paper("r1", 1)];
        return { status: 200, body: { selected_result_id: selected, results: results.map((r) => ({ ...r, draft: r.result_id !== selected })) } };
      }
      if (req.path.endsWith("/result")) return { status: 200, body: paper("r1", 1) };
      return { status: 200, body: { ...room } };
    };
    setTransport(t);
    render(
      <MemoryRouter initialEntries={["/r/c/result"]}>
        <Routes>
          <Route path="/r/:code/result" element={<Result />} />
        </Routes>
      </MemoryRouter>
    );
    fireEvent.click(await screen.findByRole("button", { name: "같은 응답으로 한 번 더 만들기" }));
    expect(await screen.findByRole("tab", { name: "2번째 결과" })).toBeTruthy();
    expect(screen.getByText(/2번째 결과가 나왔어요/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "이 결과로 고르기" }));
    await screen.findByText("이 결과가 동행에게 공개되고 있어요.");
    expect(screen.queryByRole("tab")).toBeNull();
    expect(screen.queryByText(/2번째 결과가 나왔어요/)).toBeNull();
    expect(screen.getByRole("button", { name: "다른 결과 보기" }).getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(screen.getByRole("button", { name: "다른 결과 보기" }));
    expect(screen.getAllByRole("tab")).toHaveLength(2);
    expect(screen.getByRole("tab", { name: "2번째 결과" }).getAttribute("aria-selected")).toBe("true");
    fireEvent.click(screen.getByRole("tab", { name: "1번째 결과" }));
    expect(screen.getByText("선택되지 않은 결과예요. 고르면 동행에게 공개돼요.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "다른 결과 보기" }));
    await waitFor(() => expect(screen.getByText("이 결과가 동행에게 공개되고 있어요.")).toBeTruthy());
  });
  it("두 결과가 있어도 선택한 결과부터 보여 주고 다른 결과는 접어 둔다", async () => {
    writeJSON("local", keys.host("c"), "token");
    setTransport(async (req) => {
      if (req.path.endsWith("/results")) return { status: 200, body: { selected_result_id: "r2", results: [paper("r1", 1), { ...paper("r2", 2), draft: false }] } };
      if (req.path.endsWith("/result")) return { status: 200, body: { ...paper("r2", 2), draft: false } };
      return { status: 200, body: room };
    });
    render(<MemoryRouter initialEntries={["/r/c/result"]}><Routes><Route path="/r/:code/result" element={<Result />} /></Routes></MemoryRouter>);
    await screen.findByText("이 결과가 동행에게 공개되고 있어요.");
    expect(screen.queryByRole("tab")).toBeNull();
    expect(screen.queryByText("1번째 조항")).toBeNull();
    expect(screen.getByRole("button", { name: "다른 결과 보기" })).toBeTruthy();
  });

});
