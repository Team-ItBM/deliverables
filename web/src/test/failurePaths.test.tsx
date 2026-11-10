import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setTransport, type Transport, type TransportRequest } from "../api/client";
import type { RoomView, SessionScenario } from "../api/types";
import { saveSession, type AnswerSession } from "../lib/answerSession";
import { keys, writeJSON } from "../lib/storage";
import { Answer } from "../pages/Answer";
import { Result } from "../pages/Result";
import { RoomEntry } from "../pages/RoomEntry";
import { Wait } from "../pages/Wait";

// PR #16 리뷰 4·5·6번과 문항 재시도. 2026-11-05 사람 승인. 기존 기대값은 바꾸지 않았다.

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});
beforeEach(() => {
  window.sessionStorage.clear();
  window.localStorage.clear();
  window.scrollTo = () => {};
});

const scenario = (id: string): SessionScenario => ({
  scenario_id: id,
  scene: "장면",
  question: `${id} 질문`,
  options: [
    { option_id: `${id}_a`, label: `${id} 가` },
    { option_id: `${id}_b`, label: `${id} 나` },
  ],
});

const answered = (over: Partial<AnswerSession> = {}): AnswerSession => ({
  session_id: "ses",
  duplicate_name_notice: false,
  privacy_notice: "안내",
  scenarios: [scenario("q1")],
  profile_id: "p1",
  display_name: "민준",
  answers: { q1: { option_id: "q1_a", memo: "메모표지" } },
  step: 1,
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

function app(start: string) {
  return render(
    <MemoryRouter initialEntries={[start]}>
      <Where />
      <Routes>
        <Route path="/r/:code" element={<RoomEntry />} />
        <Route path="/r/:code/answer" element={<Answer />} />
        <Route path="/r/:code/wait" element={<Wait />} />
        <Route path="/r/:code/result" element={<p>결과 화면</p>} />
        <Route path="/new" element={<p>새 방 화면</p>} />
      </Routes>
    </MemoryRouter>
  );
}

const where = () => screen.getByTestId("where").textContent;
const noResult = { status: 409, body: { error: { code: "invalid_state", message: "x" } } };
const stored = { status: 201, body: { participant_id: "pt", submitted_count: 2, party_size: 3 } };
const submissions = (seen: TransportRequest[]) => seen.filter((r) => r.path.endsWith("/submissions"));

function serve(view: RoomView, result: () => { status: number; body: unknown }, submit?: () => { status: number; body: unknown }) {
  const seen: TransportRequest[] = [];
  const t: Transport = async (req) => {
    seen.push(req);
    if (req.path.endsWith("/result")) return result();
    if (req.path.endsWith("/submissions")) return (submit ?? (() => stored))();
    if (req.path.endsWith("/retry")) return { status: 202, body: {} };
    return { status: 200, body: view };
  };
  setTransport(t);
  return seen;
}

describe("결과 조회 실패(리뷰 4번)", () => {
  it("리뷰 재현: 첫 조회가 503이면 안내와 다시 확인을 보여 주고, 다시 확인하면 결과 버튼이 나온다", async () => {
    writeJSON("local", keys.submitted("c"), { session_id: "s", participant_id: "pt" });
    let calls = 0;
    serve(room({ room_status: "ready" }), () => (++calls === 1 ? { status: 503, body: null } : { status: 200, body: {} }));
    app("/r/c/wait");
    await screen.findByText("협약서가 있는지 확인하지 못했어요.");
    expect(screen.queryByRole("button", { name: "협약서 보기" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "다시 확인" }));
    await screen.findByRole("button", { name: "협약서 보기" });
    expect(screen.queryByText("협약서가 있는지 확인하지 못했어요.")).toBeNull();
  });

  it("초대 링크로 온 사람도 같은 경로로 결과에 닿는다", async () => {
    let calls = 0;
    serve(room({ room_status: "ready" }), () => (++calls === 1 ? { status: 503, body: null } : { status: 200, body: {} }));
    app("/r/c");
    fireEvent.click(await screen.findByRole("button", { name: "다시 확인" }));
    await screen.findByText("결과 화면");
  });

  it("연결이 끊겨도 확인 실패로 본다", async () => {
    writeJSON("local", keys.submitted("c"), { session_id: "s", participant_id: "pt" });
    const t: Transport = async (req) => {
      if (req.path.endsWith("/result")) throw new TypeError("network");
      return { status: 200, body: room({ room_status: "ready" }) };
    };
    setTransport(t);
    app("/r/c/wait");
    await screen.findByText("협약서가 있는지 확인하지 못했어요.");
  });

  it("일시 오류는 몇 번 자동으로 다시 보고 멈춘다", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    writeJSON("local", keys.submitted("c"), { session_id: "s", participant_id: "pt" });
    const seen = serve(room({ room_status: "ready" }), () => ({ status: 503, body: null }));
    app("/r/c/wait");
    await vi.waitFor(() => expect(seen.filter((r) => r.path.endsWith("/result")).length).toBe(1));
    await vi.advanceTimersByTimeAsync(60_000);
    const count = seen.filter((r) => r.path.endsWith("/result")).length;
    expect(count).toBe(4);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(seen.filter((r) => r.path.endsWith("/result")).length).toBe(count);
  });

  it("서버가 결과가 없다고 답하면 오류를 보이지 않는다", async () => {
    writeJSON("local", keys.submitted("c"), { session_id: "s", participant_id: "pt" });
    serve(room({ room_status: "generating" }), () => noResult);
    app("/r/c/wait");
    await screen.findByText("진행 상황");
    await waitFor(() => expect(screen.queryByText("협약서가 있는지 확인하지 못했어요.")).toBeNull());
  });
});

describe("제출 재시도(리뷰 5번)", () => {
  const lost = () => ({ status: 503, body: null });

  async function submitOnce() {
    fireEvent.click(await screen.findByRole("button", { name: "제출하기" }));
    await screen.findByRole("button", { name: "같은 답으로 다시 보내기" });
  }

  it("결과를 모르는 동안 답을 고칠 수 없다", async () => {
    saveSession("c", answered());
    serve(room(), () => noResult, lost);
    app("/r/c/answer?step=review");
    await submitOnce();
    expect(screen.queryByRole("button", { name: "1번 고치기" })).toBeNull();
  });

  it("리뷰 재현: 재시도는 처음 보낸 키와 본문을 그대로 보낸다", async () => {
    saveSession("c", answered());
    let calls = 0;
    const seen = serve(room(), () => noResult, () => (++calls === 1 ? lost() : stored));
    app("/r/c/answer?step=review");
    await submitOnce();
    fireEvent.click(screen.getByRole("button", { name: "같은 답으로 다시 보내기" }));
    await waitFor(() => expect(where()).toBe("/r/c/wait"));
    const [first, second] = submissions(seen);
    expect(second!.headers["Idempotency-Key"]).toBe(first!.headers["Idempotency-Key"]);
    expect(second!.body).toEqual(first!.body);
  });

  it("초안이 바뀌어 있어도 보존한 본문을 보낸다", async () => {
    saveSession("c", answered());
    let calls = 0;
    const seen = serve(room(), () => noResult, () => (++calls === 1 ? lost() : stored));
    const view = app("/r/c/answer?step=review");
    await submitOnce();
    view.unmount();
    saveSession("c", answered({ answers: { q1: { option_id: "q1_b", memo: "" } } }));
    app("/r/c/answer?step=review");
    fireEvent.click(await screen.findByRole("button", { name: "같은 답으로 다시 보내기" }));
    await waitFor(() => expect(where()).toBe("/r/c/wait"));
    expect(submissions(seen)[1]!.body).toEqual(submissions(seen)[0]!.body);
  });

  it("같은 키가 다른 내용으로 저장돼 있으면 갇히지 않고 제출 완료로 끝낸다", async () => {
    saveSession("c", answered({ idempotency_key: "old-key" }));
    serve(room(), () => noResult, () => ({ status: 409, body: { error: { code: "idempotency_conflict", message: "x" } } }));
    app("/r/c/answer?step=review");
    fireEvent.click(await screen.findByRole("button", { name: "제출하기" }));
    await waitFor(() => expect(where()).toBe("/r/c/wait"));
    expect(localStorage.getItem(keys.pending("c"))).toBeNull();
    expect(localStorage.getItem(keys.submitted("c"))).not.toBeNull();
  });

  it("성공하면 보존을 바로 지운다", async () => {
    saveSession("c", answered());
    serve(room(), () => noResult);
    app("/r/c/answer?step=review");
    fireEvent.click(await screen.findByRole("button", { name: "제출하기" }));
    await waitFor(() => expect(where()).toBe("/r/c/wait"));
    expect(localStorage.getItem(keys.pending("c"))).toBeNull();
  });

  it("명확한 거절이면 보존을 지우고 답을 고칠 수 있다", async () => {
    saveSession("c", answered());
    serve(room(), () => noResult, () => ({ status: 422, body: { error: { code: "invalid_input", message: "x" } } }));
    app("/r/c/answer?step=review");
    fireEvent.click(await screen.findByRole("button", { name: "제출하기" }));
    await screen.findByRole("button", { name: "다시 제출하기" });
    expect(localStorage.getItem(keys.pending("c"))).toBeNull();
    expect(screen.getByRole("button", { name: "1번 고치기" })).toBeTruthy();
  });

  it("새 탭에서는 이름을 고르지 못하고 보존한 요청으로만 확인한다", async () => {
    saveSession("c", answered());
    let calls = 0;
    const seen = serve(room(), () => noResult, () => (++calls === 1 ? lost() : stored));
    const view = app("/r/c/answer?step=review");
    await submitOnce();
    view.unmount();
    sessionStorage.clear(); // 초대 링크를 새 탭으로 연 상태
    app("/r/c");
    const button = await screen.findByRole("button", { name: "제출 결과 확인하기" });
    expect(screen.queryByText("내 이름을 골라 주세요")).toBeNull();
    expect(document.body.textContent).not.toContain("메모표지");
    fireEvent.click(button);
    await waitFor(() => expect(where()).toBe("/r/c/wait"));
    expect(submissions(seen)[1]!.headers["Idempotency-Key"]).toBe(submissions(seen)[0]!.headers["Idempotency-Key"]);
    expect(localStorage.getItem(keys.pending("c"))).toBeNull();
  });

  it("보존은 24시간 뒤 만료한다", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    saveSession("c", answered());
    serve(room(), () => noResult, lost);
    const view = app("/r/c/answer?step=review");
    await submitOnce();
    view.unmount();
    sessionStorage.clear();
    vi.setSystemTime(Date.now() + 24 * 60 * 60 * 1000 + 1);
    app("/r/c");
    await screen.findByText("내 이름을 골라 주세요");
    expect(localStorage.getItem(keys.pending("c"))).toBeNull();
  });
});

describe("방장 결과 경로(리뷰 6번)", () => {
  beforeEach(() => writeJSON("local", keys.host("c"), "token"));

  it("리뷰 재현: 재생성이 실패한 방에 다시 들어와도 기존 결과를 연다", async () => {
    serve(room({ room_status: "failed", failure_reason: "call_error" }), () => ({ status: 200, body: {} }));
    const { container } = app("/r/c");
    await screen.findByRole("button", { name: "협약서 보기" });
    expect(screen.getByRole("button", { name: "같은 응답으로 다시 시도" })).toBeTruthy();
    expect(container.querySelectorAll(".bottom-bar .btn-primary").length).toBe(1);
  });

  it("재생성 중에도 기존 결과를 연다", async () => {
    serve(room({ room_status: "generating" }), () => ({ status: 200, body: {} }));
    app("/r/c");
    await screen.findByRole("button", { name: "협약서 보기" });
  });

  it("대기 화면에서도 기존 결과를 연다", async () => {
    serve(room({ room_status: "failed", failure_reason: "call_error" }), () => ({ status: 200, body: {} }));
    app("/r/c/wait");
    await screen.findByRole("button", { name: "협약서 보기" });
  });

  it("결과가 없으면 재시도가 주 동작이다", async () => {
    serve(room({ room_status: "failed", failure_reason: "call_error" }), () => noResult);
    const { container } = app("/r/c");
    await screen.findByRole("button", { name: "같은 응답으로 다시 시도" });
    await waitFor(() => expect(container.querySelector(".bottom-bar .btn-primary")?.textContent).toContain("다시 시도"));
    expect(screen.queryByRole("button", { name: "협약서 보기" })).toBeNull();
  });
});

describe("방장 결과 화면(리뷰 6번)", () => {
  const paper = {
    result_id: "r1",
    kind: "ai_original",
    source_result_id: null,
    label: null,
    draft: true,
    pact_status: "proposed",
    included_count: 1,
    excluded_names: [],
    clauses: [{ scenario_id: "q1", participant_names: ["민준"], action: "조항 문장", proposed_conditions: [] }],
    conditional_alternatives: [],
    unresolved_conditions: [],
  };

  it.each(["failed", "generating"] as const)("방 상태가 %s여도 기존 결과를 고르고 이미지 저장 버튼을 쓴다", async (status) => {
    writeJSON("local", keys.host("c"), "token");
    const seen: TransportRequest[] = [];
    const t: Transport = async (req) => {
      seen.push(req);
      if (req.path.endsWith("/results")) {
        return {
          status: 200,
          body: {
            selected_result_id: null,
            results: [
              { ...paper, attempt: 1, state: "normal", created_at: "2026-11-05T00:00:00Z", editable: [] },
              { result_id: "r2", kind: "ai_original", attempt: 2, state: "failed", created_at: "2026-11-05T00:01:00Z" },
            ],
          },
        };
      }
      if (req.path.endsWith("/result")) return { status: 200, body: paper };
      if (req.path.endsWith("/select")) return { status: 200, body: { selected_result_id: "r1" } };
      return { status: 200, body: room({ room_status: status, failure_reason: status === "failed" ? "call_error" : undefined }) };
    };
    setTransport(t);
    render(
      <MemoryRouter initialEntries={["/r/c/result"]}>
        <Routes>
          <Route path="/r/:code/result" element={<Result />} />
        </Routes>
      </MemoryRouter>
    );
    await screen.findByRole("button", { name: "이미지 저장·공유" });
    fireEvent.click(await screen.findByRole("button", { name: "이 결과로 고르기" }));
    await waitFor(() => expect(seen.some((r) => r.path.endsWith("/select"))).toBe(true));
  });
});

describe("문항 재시도(리뷰 2번)", () => {
  it("방장은 다시 시도하거나 새 방을 만든다", async () => {
    writeJSON("local", keys.host("c"), "token");
    const seen = serve(room({ scenario_status: "failed" }), () => noResult);
    app("/r/c");
    fireEvent.click(await screen.findByRole("button", { name: "문항 다시 만들기" }));
    await waitFor(() => expect(seen.some((r) => r.path.endsWith("/retry"))).toBe(true));
    fireEvent.click(screen.getByRole("link", { name: "새 방 만들기" }));
    await screen.findByText("새 방 화면");
  });

  it("참여자에게는 재시도 버튼이 없다", async () => {
    serve(room({ scenario_status: "failed" }), () => noResult);
    app("/r/c");
    await screen.findByText("문항을 준비하지 못했어요. 방장에게 알려 주세요.");
    expect(screen.queryByRole("button", { name: "문항 다시 만들기" })).toBeNull();
  });
});
