import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { setTransport, type TransportRequest } from "../api/client";
import type { ResultEntry, RoomView } from "../api/types";
import { HostPanel } from "../components/HostPanel";
import { saveSession, type AnswerSession } from "../lib/answerSession";
import { Answer } from "../pages/Answer";
import { RoomEntry } from "../pages/RoomEntry";

afterEach(cleanup);
beforeEach(() => {
  window.sessionStorage.clear();
  window.localStorage.clear();
});

const session: AnswerSession = {
  session_id: "ses_1",
  duplicate_name_notice: false,
  privacy_notice: "공개 안내 원문",
  scenarios: [{ scenario_id: "s1", scene: "장면", question: "질문", options: [{ option_id: "o1", label: "가" }] }],
  profile_id: "p1",
  display_name: "민준",
  answers: { s1: { option_id: "o1", memo: "" } },
  step: 1,
};

describe("답 확인 화면", () => {
  it("고정 영역에는 버튼만 있고 공개 안내는 본문에 있다", () => {
    saveSession("room1", session);
    const { container } = render(
      <MemoryRouter initialEntries={["/r/room1/answer"]}>
        <Routes>
          <Route path="/r/:code/answer" element={<Answer />} />
        </Routes>
      </MemoryRouter>
    );
    const bar = container.querySelector(".bottom-bar-inner")!;
    expect(bar.children.length).toBe(1);
    expect(bar.querySelector("button")?.textContent).toBe("제출하기");
    expect(bar.textContent).not.toContain("공개 안내 원문");
    expect(screen.getByText("공개 안내 원문")).toBeTruthy();
  });
});

function entry(id: string, state: "normal" | "failed"): ResultEntry {
  return { result_id: id, attempt: 1, state, created_at: "2026-11-05T00:00:00Z" };
}

const readyRoom: RoomView = {
  room_status: "ready",
  scenario_status: "ready",
  party_size: 2,
  submitted_count: 2,
  profiles: [],
};

function panelWith(results: ResultEntry[]) {
  setTransport(async (req: TransportRequest) => {
    if (req.path.endsWith("/results")) return { status: 200, body: { selected_result_id: null, results } };
    return { status: 200, body: {} };
  });
  return render(
    <MemoryRouter>
      <HostPanel code="room1" token="t" room={readyRoom} onChanged={() => {}} />
    </MemoryRouter>
  );
}

describe("재생성 버튼", () => {
  it("정상 결과가 하나면 보인다", async () => {
    panelWith([entry("r1", "normal")]);
    await screen.findByText("같은 응답으로 한 번 더 만들기");
  });

  it("실패한 시도는 횟수에 넣지 않는다", async () => {
    panelWith([entry("r1", "normal"), entry("r2", "failed")]);
    await screen.findByText("같은 응답으로 한 번 더 만들기");
  });

  it("정상 결과가 두 개면 숨긴다", async () => {
    panelWith([entry("r1", "normal"), entry("r2", "normal")]);
    await waitFor(() => expect(screen.getByText("결과 보기")).toBeTruthy());
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByText("같은 응답으로 한 번 더 만들기")).toBeNull();
  });
});

describe("없는 방", () => {
  it("제목과 새 방 만들기를 보여 준다", async () => {
    setTransport(async () => ({ status: 404, body: { error: { code: "not_found", message: "x" } } }));
    render(
      <MemoryRouter initialEntries={["/r/none"]}>
        <Routes>
          <Route path="/r/:code" element={<RoomEntry />} />
        </Routes>
      </MemoryRouter>
    );
    await screen.findByRole("heading", { name: "방을 찾지 못했어요" });
    expect(screen.getByRole("link", { name: "새 방 만들기" }).getAttribute("href")).toBe("/");
  });
});
