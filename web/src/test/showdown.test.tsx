import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { setTransport, type TransportRequest } from "../api/client";
import type { ShowdownBoard, ShowdownCard } from "../api/types";
import { keys, writeJSON } from "../lib/storage";
import { Showdown } from "../pages/Showdown";

const votingCard: ShowdownCard = {
  sides: ["생선 요리", "면 요리"],
  compromises: ["밥은 무조건 같이! 메뉴는 끼니마다 돌아가며 정하기", "둘 다 파는 식당을 찾아서 같이 먹기!"],
  phase: "voting",
  mode: "rps",
  voter_count: 2,
  picked_count: 0,
  can_pick: true,
  my_pick: null,
};

function board(card: ShowdownCard, rule: string | null = null): ShowdownBoard {
  const open = card.phase !== "done";
  return {
    available: true,
    is_participant: true,
    summary: { total: 2, settled: rule ? 2 : 1, showdown: 1, showdown_open: open ? 1 : 0 },
    items: [
      { scenario_id: "separate_menu", title: "먹고 싶은 메뉴가 다를 때", outcome: "showdown", rule, showdown: card },
      { scenario_id: "route_depth", title: "여러 곳을 짧게, 한 곳을 길게", outcome: "middle", rule: "오후엔 두 곳만, 남는 시간은 자유!" },
    ],
  };
}

const app = () => (
  <MemoryRouter initialEntries={["/r/c/showdown"]}>
    <Routes>
      <Route path="/r/:code/showdown" element={<Showdown />} />
    </Routes>
  </MemoryRouter>
);

describe("승부처 화면", () => {
  it("통한 약속과 승부처를 보여 주고, 고른 선택을 세션과 함께 보낸다", async () => {
    writeJSON("local", keys.submitted("c"), { session_id: "ses-1", participant_id: "p1" });
    const requests: TransportRequest[] = [];
    setTransport(async (req) => {
      requests.push(req);
      if (req.method === "POST") return { status: 200, body: board({ ...votingCard, picked_count: 1, my_pick: "duel" }) };
      return { status: 200, body: board(votingCard) };
    });
    render(app());
    expect(await screen.findByText("생선 요리 vs 면 요리")).toBeTruthy();
    expect(screen.getByText("오후엔 두 곳만, 남는 시간은 자유!")).toBeTruthy();
    expect(requests[0]!.headers["X-Session-Id"]).toBe("ses-1");

    fireEvent.click(screen.getByRole("radio", { name: "가위바위보로 정하기" }));
    await waitFor(() => expect(screen.getByRole("radio", { name: "가위바위보로 정하기" }).getAttribute("aria-checked")).toBe("true"));
    const post = requests.find((r) => r.method === "POST")!;
    expect(post.path).toBe("/api/rooms/c/showdown/separate_menu/pick");
    expect(post.body).toEqual({ session_id: "ses-1", choice: "duel" });
  });

  it("가위바위보에서 패를 내면 보내고, 끝나면 결과와 정해진 규칙을 보여 준다", async () => {
    writeJSON("local", keys.submitted("c"), { session_id: "ses-1", participant_id: "p1" });
    const duel: ShowdownCard = {
      ...votingCard, phase: "duel", can_pick: false, picked_count: 2, my_pick: "duel",
      duel: { is_player: true, round: 1, moved_count: 0, my_move: null, last_tie: null },
    };
    const rule = "메뉴가 갈려도 밥은 무조건 같이!";
    const done: ShowdownCard = {
      ...votingCard, phase: "done", can_pick: false, picked_count: 2, my_pick: "duel",
      result: { how: "duel", rule, won: true, my_move: "rock", other_move: "scissors" },
    };
    const requests: TransportRequest[] = [];
    setTransport(async (req) => {
      requests.push(req);
      return { status: 200, body: req.method === "POST" ? board(done, rule) : board(duel) };
    });
    render(app());
    fireEvent.click(await screen.findByRole("button", { name: /바위/ }));
    expect(await screen.findByText("이겼어요!")).toBeTruthy();
    expect(screen.getAllByText(rule).length).toBeGreaterThan(0);
    const post = requests.find((r) => r.method === "POST")!;
    expect(post.path).toBe("/api/rooms/c/showdown/separate_menu/move");
    expect(post.body).toEqual({ session_id: "ses-1", move: "rock" });
  });

  it("제출하지 않은 기기는 고를 수 없고, 지원하지 않는 방은 안내만 보여 준다", async () => {
    setTransport(async () => ({ status: 200, body: board({ ...votingCard, can_pick: false }) }));
    const first = render(app());
    expect(await screen.findByText("이 방에 답을 제출한 기기에서 고를 수 있어요.")).toBeTruthy();
    expect(screen.queryByRole("radio")).toBeNull();
    first.unmount();

    setTransport(async () => ({ status: 200, body: { available: false } }));
    render(app());
    expect(await screen.findByText("이 방에서는 한 줄 협약서를 볼 수 없어요.")).toBeTruthy();
  });
});
