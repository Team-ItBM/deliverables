import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { setTransport, type Transport } from "../api/client";
import type { RoomView } from "../api/types";
import { keys, writeJSON } from "../lib/storage";
import { Result } from "../pages/Result";

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
    const t: Transport = async (req) => {
      if (req.path.endsWith("/regenerate")) {
        regenerated = true;
        return { status: 202, body: {} };
      }
      if (req.path.endsWith("/results")) {
        const results = regenerated ? [paper("r1", 1), paper("r2", 2)] : [paper("r1", 1)];
        return { status: 200, body: { selected_result_id: null, results } };
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
  });
});
