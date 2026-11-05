import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import { setTransport, type TransportRequest } from "../api/client";
import { submitSession, type AnswerSession } from "../lib/answerSession";
import { clampMemo } from "../lib/scene";
import { MemoField } from "../pages/Answer";

function Harness() {
  const [v, setV] = useState("");
  return <MemoField id="m" value={v} onChange={setV} />;
}

describe("메모 300자 제한", () => {
  it("300자를 넘게 입력하면 300자에서 자르고 개수를 보여 준다", () => {
    render(<Harness />);
    const box = screen.getByLabelText("메모 (선택)") as HTMLTextAreaElement;
    fireEvent.change(box, { target: { value: "가".repeat(310) } });
    expect(Array.from(box.value).length).toBe(300);
    expect(screen.getByText("300 / 300")).toBeTruthy();
  });

  it("코드 포인트로 세어 서로게이트 쌍을 반으로 자르지 않는다", () => {
    const s = "𠀀".repeat(301);
    expect(Array.from(clampMemo(s)).length).toBe(300);
  });
});

const session: AnswerSession = {
  session_id: "ses_1",
  duplicate_name_notice: false,
  privacy_notice: "안내",
  scenarios: [{ scenario_id: "free_time", scene: "장면", question: "질문", options: [{ option_id: "o1", label: "가" }] }],
  profile_id: "p1",
  display_name: "민준",
  answers: { free_time: { option_id: "o1", memo: "" } },
  step: 1,
};

describe("제출 멱등 키", () => {
  it("연결이 끊겨 다시 보내도 같은 Idempotency-Key를 쓰고, 빈 메모는 빼고 보낸다", async () => {
    const seen: TransportRequest[] = [];
    let calls = 0;
    setTransport(async (req) => {
      seen.push(req);
      calls += 1;
      if (calls === 1) return { status: 503, body: null };
      return { status: 201, body: { participant_id: "pt_1", submitted_count: 1, party_size: 3 } };
    });
    let stored: AnswerSession = session;
    await expect(submitSession("room1", stored, (n) => (stored = n))).rejects.toBeTruthy();
    const firstKey = seen[0]!.headers["Idempotency-Key"];
    expect(firstKey).toBeTruthy();
    expect(stored.idempotency_key).toBe(firstKey);
    await submitSession("room1", stored, (n) => (stored = n));
    expect(seen[1]!.headers["Idempotency-Key"]).toBe(firstKey);
    expect(seen[1]!.body).toEqual({ session_id: "ses_1", answers: [{ scenario_id: "free_time", option_id: "o1" }] });
  });

  it("서버가 확정적으로 거절하면 키를 버린다", async () => {
    setTransport(async () => ({ status: 422, body: { error: { code: "invalid_input", message: "x" } } }));
    let stored: AnswerSession = session;
    await expect(submitSession("room1", stored, (n) => (stored = n))).rejects.toBeTruthy();
    expect(stored.idempotency_key).toBeUndefined();
  });
});
