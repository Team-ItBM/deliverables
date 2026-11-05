import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { setTransport, type Transport } from "../api/client";
import type { RoomView, SessionScenario } from "../api/types";
import { saveSession, type AnswerSession } from "../lib/answerSession";
import { keys, writeJSON } from "../lib/storage";
import { Answer } from "../pages/Answer";
import { RoomEntry } from "../pages/RoomEntry";
import { Wait } from "../pages/Wait";

afterEach(cleanup);
beforeEach(() => {
  window.sessionStorage.clear();
  window.localStorage.clear();
  window.scrollTo = () => {};
});

const scenario = (id: string): SessionScenario => ({
  scenario_id: id,
  scene: "장면",
  question: `${id} 질문`,
  options: [{ option_id: `${id}_a`, label: `${id} 고르기` }],
});

const session = (over: Partial<AnswerSession> = {}): AnswerSession => ({
  session_id: "ses",
  duplicate_name_notice: false,
  privacy_notice: "안내",
  scenarios: [scenario("q1"), scenario("q2")],
  profile_id: "p1",
  display_name: "민준",
  answers: {},
  step: 0,
  ...over,
});

const room = (over: Partial<RoomView> = {}): RoomView => ({
  room_status: "open",
  scenario_status: "ready",
  party_size: 3,
  submitted_count: 1,
  profiles: [{ profile_id: "p1", display_name: "민준", has_submission: false }],
  ...over,
});

function Where() {
  const l = useLocation();
  return <p data-testid="where">{l.pathname + l.search}</p>;
}

function app(start: string[], index?: number) {
  return render(
    <MemoryRouter initialEntries={start} initialIndex={index}>
      <Where />
      <Routes>
        <Route path="/" element={<p>첫 화면</p>} />
        <Route path="/r/:code" element={<RoomEntry />} />
        <Route path="/r/:code/answer" element={<Answer />} />
        <Route path="/r/:code/wait" element={<Wait />} />
        <Route path="/r/:code/result" element={<p>결과 화면</p>} />
      </Routes>
    </MemoryRouter>
  );
}

const where = () => screen.getByTestId("where").textContent;

function serve(view: RoomView, opts: { result?: boolean } = {}) {
  const t: Transport = async (req) => {
    if (req.path.endsWith("/result")) {
      return opts.result
        ? { status: 200, body: {} }
        : { status: 409, body: { error: { code: "invalid_state", message: "x" } } };
    }
    if (req.path.endsWith("/submissions")) {
      return { status: 201, body: { participant_id: "pt", submitted_count: 2, party_size: 3 } };
    }
    return { status: 200, body: view };
  };
  setTransport(t);
}

describe("문항 기록", () => {
  it("문항 단계가 주소에 남고, 답 고치기 뒤 확인으로 돌아간다", async () => {
    saveSession("c", session({ answers: { q1: { option_id: "q1_a", memo: "" }, q2: { option_id: "q2_a", memo: "" } }, step: 2 }));
    app(["/r/c/answer"]);
    await waitFor(() => expect(where()).toBe("/r/c/answer?step=review"));
    fireEvent.click(screen.getByRole("button", { name: "1번 고치기" }));
    await waitFor(() => expect(where()).toBe("/r/c/answer?step=1"));
    fireEvent.click(screen.getByRole("button", { name: "확인으로 돌아가기" }));
    await waitFor(() => expect(where()).toBe("/r/c/answer?step=review"));
  });

  it("주소로 아직 안 고른 문항을 건너뛸 수 없다", async () => {
    saveSession("c", session());
    app(["/r/c/answer?step=review"]);
    await screen.findByText("q1 질문");
  });

  it("제출하면 문항 기록을 걷어 내고 대기 화면으로 간다. 뒤로 가도 답변이 나오지 않는다", async () => {
    serve(room());
    saveSession("c", session());
    app(["/r/c", { pathname: "/r/c/answer", search: "?step=1", state: { fromRoom: true } } as never], 1);
    fireEvent.click(await screen.findByRole("radio", { name: "q1 고르기" }));
    fireEvent.click(screen.getByRole("button", { name: "다음" }));
    fireEvent.click(await screen.findByRole("radio", { name: "q2 고르기" }));
    fireEvent.click(screen.getByRole("button", { name: "답 확인하기" }));
    fireEvent.click(await screen.findByRole("button", { name: "제출하기" }));
    await waitFor(() => expect(where()).toBe("/r/c/wait"));
    expect(window.sessionStorage.getItem(keys.session("c"))).toBeNull();
  });
});

describe("방 첫 화면", () => {
  it("답하던 중이면 이어서 답하기가 주 버튼이고, 다시 시작은 확인을 받는다", async () => {
    serve(room());
    saveSession("c", session({ answers: { q1: { option_id: "q1_a", memo: "쓰던 메모" } } }));
    const { container } = app(["/r/c"]);
    await waitFor(() => expect(container.querySelector(".bottom-bar .btn-primary")?.textContent).toBe("이어서 답하기"));
    fireEvent.click(screen.getByRole("button", { name: "처음부터 다시 답하기" }));
    await screen.findByRole("dialog");
    expect(window.sessionStorage.getItem(keys.session("c"))).toContain("쓰던 메모");
    fireEvent.click(screen.getByRole("button", { name: "지우고 다시 답하기" }));
    await screen.findByText("내 이름을 골라 주세요");
    expect(window.sessionStorage.getItem(keys.session("c"))).toBeNull();
  });

  it("메모를 localStorage에 쓰지 않는다", async () => {
    serve(room());
    saveSession("c", session({ answers: { q1: { option_id: "q1_a", memo: "쓰던 메모" } } }));
    app(["/r/c/answer?step=1"]);
    await screen.findByText("q1 질문");
    expect(JSON.stringify({ ...window.localStorage })).not.toContain("쓰던 메모");
  });

  it("결과가 있으면 초대 링크로 처음 온 사람을 결과로 보낸다", async () => {
    serve(room({ room_status: "ready" }), { result: true });
    app(["/r/c"]);
    await screen.findByText("결과 화면");
  });

  it("재생성이 실패한 방도 공개 결과가 있으면 결과로 보낸다", async () => {
    serve(room({ room_status: "failed", failure_reason: "call_error" }), { result: true });
    app(["/r/c"]);
    await screen.findByText("결과 화면");
  });

  it("제출한 기기는 결과가 있어도 진행 상황을 먼저 보고 직접 연다", async () => {
    serve(room({ room_status: "ready" }), { result: true });
    writeJSON("local", keys.submitted("c"), { session_id: "s", participant_id: "pt" });
    app(["/r/c"]);
    await screen.findByText("이 기기에서 답변을 제출했어요.");
    await screen.findByRole("button", { name: "협약서 보기" });
    expect(where()).toBe("/r/c");
  });

  it("방장 화면에는 방장용 제목과 주 버튼 하나가 있고 초대 링크 복사가 늘 있다", async () => {
    serve(room({ room_status: "ready" }));
    writeJSON("local", keys.host("c"), "token");
    const { container } = app(["/r/c"]);
    await screen.findByRole("heading", { name: "협약서가 준비됐어요" });
    expect(container.querySelectorAll(".bottom-bar .btn-primary").length).toBe(1);
    expect(screen.getByRole("button", { name: "초대 링크 복사" })).toBeTruthy();
    expect(screen.getByText(/나 포함/)).toBeTruthy();
    expect(container.textContent).not.toContain("이름으로 답하기");
  });
});
