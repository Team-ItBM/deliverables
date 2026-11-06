import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { setTransport, type Transport, type TransportRequest } from "../api/client";
import type { RoomView, SessionScenario } from "../api/types";
import { loadSession, saveSession, submitSession, type AnswerSession } from "../lib/answerSession";
import { keys, writeJSON } from "../lib/storage";
import { Answer } from "../pages/Answer";
import { RoomEntry } from "../pages/RoomEntry";
import { Wait } from "../pages/Wait";

// PR #16 2차 리뷰: 제출 시작 시점의 잠금, 다른 세션의 미확인 제출. 기존 기대값은 바꾸지 않았다.

afterEach(cleanup);
beforeEach(() => {
  window.sessionStorage.clear();
  window.localStorage.clear();
  window.scrollTo = () => {};
});

const scenario: SessionScenario = {
  scenario_id: "q1",
  scene: "장면",
  question: "q1 질문",
  options: [
    { option_id: "q1_a", label: "가 선택지" },
    { option_id: "q1_b", label: "나 선택지" },
  ],
};

const draft = (over: Partial<AnswerSession> = {}): AnswerSession => ({
  session_id: "ses-b",
  duplicate_name_notice: false,
  privacy_notice: "안내",
  scenarios: [scenario],
  profile_id: "p1",
  display_name: "민준",
  answers: { q1: { option_id: "q1_b", memo: "" } },
  step: 1,
  ...over,
});

const room: RoomView = {
  room_status: "open",
  scenario_status: "ready",
  party_size: 3,
  submitted_count: 1,
  profiles: [{ profile_id: "p1", display_name: "민준", has_submission: false }],
};

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
      </Routes>
    </MemoryRouter>
  );
}

const where = () => screen.getByTestId("where").textContent;
const stored = { status: 201, body: { participant_id: "pt", submitted_count: 2, party_size: 3 } };
const lost = { status: 503, body: null };
const rejected = { status: 422, body: { error: { code: "invalid_input", message: "x" } } };
const conflict = { status: 409, body: { error: { code: "idempotency_conflict", message: "x" } } };
type Reply = { status: number; body: unknown };

function serve(submit: (req: TransportRequest) => Reply | Promise<Reply>) {
  const seen: TransportRequest[] = [];
  const t: Transport = async (req) => {
    if (req.path.endsWith("/submissions")) {
      seen.push(req);
      return submit(req);
    }
    if (req.path.endsWith("/result")) return { status: 409, body: { error: { code: "invalid_state", message: "x" } } };
    return { status: 200, body: room };
  };
  setTransport(t);
  return seen;
}

/** 다른 세션(또는 같은 세션)이 남긴 미확인 제출. */
function seedPending(sessionId: string, optionId = "q1_a") {
  writeJSON("local", keys.pending("c"), {
    idempotency_key: "key-a",
    body: { session_id: sessionId, answers: [{ scenario_id: "q1", option_id: optionId }] },
    expires_at: Date.now() + 60_000,
  });
}

describe("제출 시작 시점의 잠금", () => {
  it("리뷰 재현: 요청이 끝나기 전에도 답을 고칠 수 없다", async () => {
    saveSession("c", draft());
    let finish: (r: Reply) => void = () => {};
    serve(() => new Promise<Reply>((resolve) => (finish = resolve)));
    app("/r/c/answer?step=review");
    fireEvent.click(await screen.findByRole("button", { name: "제출하기" }));
    await screen.findByRole("button", { name: "보내는 중이에요" });
    expect(screen.queryByRole("button", { name: "1번 고치기" })).toBeNull();
    await act(async () => finish(lost));
    await screen.findByRole("button", { name: "같은 답으로 다시 보내기" });
  });

  it("리뷰 재현: 미확인 제출의 확인 화면은 초안이 아니라 보존한 본문을 보여 준다", async () => {
    saveSession("c", draft({ session_id: "ses-a" })); // 초안은 나 선택지, 보낸 본문은 가 선택지
    seedPending("ses-a", "q1_a");
    serve(() => lost);
    app("/r/c/answer?step=review");
    await screen.findByText("가 선택지");
    expect(screen.queryByText("나 선택지")).toBeNull();
    expect(screen.getByRole("button", { name: "같은 답으로 다시 보내기" })).toBeTruthy();
  });

  it("명확히 거절되면 잠금이 풀린다", async () => {
    saveSession("c", draft());
    let finish: (r: Reply) => void = () => {};
    serve(() => new Promise<Reply>((resolve) => (finish = resolve)));
    app("/r/c/answer?step=review");
    fireEvent.click(await screen.findByRole("button", { name: "제출하기" }));
    await screen.findByRole("button", { name: "보내는 중이에요" });
    await act(async () => finish(rejected));
    await screen.findByRole("button", { name: "1번 고치기" });
  });
});

describe("다른 세션의 미확인 제출", () => {
  it("리뷰 재현: 현재 제출을 성공으로 끝내지 않고 요청도 보내지 않으며 초안을 보존한다", async () => {
    seedPending("ses-a");
    const seen = serve(() => stored);
    saveSession("c", draft());
    await expect(submitSession("c", draft())).rejects.toBeTruthy();
    expect(seen).toEqual([]);
    expect(loadSession("c")?.answers.q1?.option_id).toBe("q1_b");
    expect(localStorage.getItem(keys.pending("c"))).not.toBeNull();
    expect(localStorage.getItem(keys.submitted("c"))).toBeNull();
  });

  it("이전 제출을 먼저 확인하고, 그 뒤 현재 세션을 따로 제출한다", async () => {
    seedPending("ses-a");
    saveSession("c", draft());
    const seen = serve(() => stored);
    app("/r/c/answer?step=review");
    await screen.findByText(/먼저 보낸 답변/);
    expect(screen.queryByRole("button", { name: "제출하기" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "이전 제출 확인하기" }));
    fireEvent.click(await screen.findByRole("button", { name: "제출하기" }));
    await waitFor(() => expect(where()).toBe("/r/c/wait"));
    expect(seen.length).toBe(2);
    expect(seen[0]!.headers["Idempotency-Key"]).toBe("key-a");
    expect((seen[0]!.body as { session_id: string }).session_id).toBe("ses-a");
    expect(seen[1]!.headers["Idempotency-Key"]).not.toBe("key-a");
    expect(seen[1]!.body).toEqual({ session_id: "ses-b", answers: [{ scenario_id: "q1", option_id: "q1_b" }] });
  });

  it("이전 제출이 아직 불명확하면 계속 막고 초안을 지키며 현재 답은 보내지 않는다", async () => {
    seedPending("ses-a");
    saveSession("c", draft());
    const seen = serve(() => lost);
    app("/r/c/answer?step=review");
    fireEvent.click(await screen.findByRole("button", { name: "이전 제출 확인하기" }));
    await screen.findByRole("alert");
    expect(screen.getByRole("button", { name: "이전 제출 확인하기" })).toBeTruthy();
    expect(seen.length).toBe(1);
    expect(loadSession("c")?.session_id).toBe("ses-b");
  });

  it.each([
    ["명확한 거절", rejected],
    ["키 충돌", conflict],
  ])("이전 제출이 %s로 끝나도 현재 초안은 남고 제출할 수 있다", async (_name, reply) => {
    seedPending("ses-a");
    saveSession("c", draft());
    serve(() => reply);
    app("/r/c/answer?step=review");
    fireEvent.click(await screen.findByRole("button", { name: "이전 제출 확인하기" }));
    await screen.findByRole("button", { name: "제출하기" });
    expect(loadSession("c")?.session_id).toBe("ses-b");
    expect(localStorage.getItem(keys.pending("c"))).toBeNull();
  });

  it("방 화면에서 확인해도 다른 세션의 초안을 지우지 않고 이어서 답할 수 있다", async () => {
    seedPending("ses-a");
    saveSession("c", draft());
    serve(() => stored);
    app("/r/c");
    fireEvent.click(await screen.findByRole("button", { name: "제출 결과 확인하기" }));
    await screen.findByRole("button", { name: "이어서 답하기" });
    expect(where()).toBe("/r/c");
    expect(loadSession("c")?.session_id).toBe("ses-b");
  });

  it("다른 탭이 확인을 끝내면 막힘이 풀린다", async () => {
    seedPending("ses-a");
    saveSession("c", draft());
    serve(() => stored);
    app("/r/c/answer?step=review");
    await screen.findByRole("button", { name: "이전 제출 확인하기" });
    localStorage.removeItem(keys.pending("c"));
    await act(async () => {
      window.dispatchEvent(new StorageEvent("storage", { key: keys.pending("c") }));
    });
    await screen.findByRole("button", { name: "제출하기" });
  });
});
