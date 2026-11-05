import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { setTransport, type TransportRequest } from "../api/client";
import type { RoomView } from "../api/types";
import { keys, writeJSON } from "../lib/storage";
import { CreateRoom, resetCreateDraft } from "../pages/CreateRoom";
import { Created } from "../pages/Created";
import { Landing } from "../pages/Landing";

afterEach(cleanup);
beforeEach(() => {
  window.localStorage.clear();
  window.scrollTo = () => {};
  resetCreateDraft();
});

function wizard() {
  return render(
    <MemoryRouter initialEntries={["/new"]}>
      <Routes>
        <Route path="/new" element={<CreateRoom />} />
        <Route path="/r/:code/created" element={<Created />} />
      </Routes>
    </MemoryRouter>
  );
}

const next = () => fireEvent.click(screen.getByRole("button", { name: "다음" }));
const type = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });

async function fillRequired() {
  type("목적지", "제주");
  type("여행 일수", "3");
  next();
  await screen.findByLabelText("동행과의 관계");
  fireEvent.change(screen.getByLabelText("함께 가는 인원(나 포함)"), { target: { value: "2" } });
  type("동행과의 관계", "친구");
  next();
  await screen.findByLabelText("1번째 이름 또는 별명");
  type("1번째 이름 또는 별명", "민지");
  type("2번째 이름 또는 별명", "서준");
  next();
  await screen.findByRole("heading", { name: "선택 정보를 넣을까요?" });
}

function recordRequests() {
  const seen: TransportRequest[] = [];
  setTransport(async (req) => {
    seen.push(req);
    return { status: 201, body: { room_code: "abc", host_token: "tok", created_at: "", expires_at: "", scenario_status: "preparing" } };
  });
  return seen;
}

describe("단계별 방 만들기", () => {
  it("빈칸이면 칸 아래에 오류를 보이고 포커스를 옮기며 aria-invalid를 붙인다", async () => {
    wizard();
    next();
    const box = screen.getByLabelText("목적지");
    await screen.findByText("목적지를 입력해 주세요.");
    expect(box.getAttribute("aria-invalid")).toBe("true");
    expect(box.getAttribute("aria-describedby")).toBe("err-destination");
    await waitFor(() => expect(document.activeElement).toBe(box));
  });

  it("선택 정보를 건너뛰면 확인 없이 마지막에 API를 한 번만 부른다", async () => {
    const seen = recordRequests();
    wizard();
    await fillRequired();
    expect(seen.length).toBe(0);
    expect(screen.queryByText("동행에게 알렸어요")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "건너뛰고 방 만들기" }));
    await screen.findByRole("heading", { name: "방을 만들었어요" });
    expect(seen.length).toBe(1);
    const body = seen[0]!.body as { trip: unknown; participant_profiles: unknown[] };
    expect(body.trip).toEqual({ destination: "제주", duration_days: 3, party_size: 2, relationship: "친구" });
    expect(body.participant_profiles).toEqual([
      { profile_id: "p1", display_name: "민지" },
      { profile_id: "p2", display_name: "서준" },
    ]);
  });

  it("선택 정보를 입력하면 동행에게 알렸어요 확인을 받는다", async () => {
    const seen = recordRequests();
    wizard();
    await fillRequired();
    fireEvent.change(screen.getAllByLabelText("MBTI")[0]!, { target: { value: "enfp" } });
    fireEvent.click(screen.getByRole("button", { name: "방 만들기" }));
    await screen.findByText("선택 정보를 입력했다면 동행에게 알렸는지 확인해 주세요.");
    expect(seen.length).toBe(0);
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "방 만들기" }));
    await screen.findByRole("heading", { name: "방을 만들었어요" });
    expect((seen[0]!.body as { participant_profiles: { mbti?: string }[] }).participant_profiles[0]!.mbti).toBe("ENFP");
  });

  it("이름과 선택 정보를 브라우저 저장소에 쓰지 않는다", async () => {
    recordRequests();
    wizard();
    await fillRequired();
    const stored = JSON.stringify({ ...window.localStorage }) + JSON.stringify({ ...window.sessionStorage });
    expect(stored).not.toContain("민지");
  });
});

describe("방 안내 화면", () => {
  it("공유 동작이 주 버튼이고 방장 링크는 접혀 있다", () => {
    writeJSON("local", keys.host("abc"), "tok");
    const { container } = render(
      <MemoryRouter initialEntries={["/r/abc/created"]}>
        <Routes>
          <Route path="/r/:code/created" element={<Created />} />
        </Routes>
      </MemoryRouter>
    );
    expect(container.querySelector(".bottom-bar .btn-primary")?.textContent).toMatch(/초대 링크/);
    expect(container.querySelector("details")?.hasAttribute("open")).toBe(false);
  });
});

describe("랜딩", () => {
  const view: RoomView = {
    room_status: "open",
    scenario_status: "ready",
    party_size: 3,
    trip: { destination: "오사카", duration_days: 2, party_size: 3 },
    submitted_count: 0,
    profiles: [],
  };

  it("이 기기의 방장 토큰으로 진행 중인 방을 보여 주고, 없는 방의 토큰은 지운다", async () => {
    writeJSON("local", keys.host("live"), "t1");
    writeJSON("local", keys.host("gone"), "t2");
    setTransport(async (req) =>
      req.path.includes("gone")
        ? { status: 404, body: { error: { code: "not_found", message: "x" } } }
        : { status: 200, body: view }
    );
    render(
      <MemoryRouter>
        <Landing />
      </MemoryRouter>
    );
    await screen.findByText("진행 중인 방 이어가기");
    expect(screen.getByRole("link", { name: /오사카 · 2일 · 3명/ }).getAttribute("href")).toBe("/r/live");
    expect(window.localStorage.getItem(keys.host("gone"))).toBeNull();
  });

  it("방장 토큰이 없으면 이어가기가 없고, 예시에 도장·비공개 항목이 없다", () => {
    setTransport(async () => ({ status: 200, body: view }));
    const { container } = render(
      <MemoryRouter>
        <Landing />
      </MemoryRouter>
    );
    expect(container.textContent).not.toContain("진행 중인 방 이어가기");
    expect(container.querySelector(".stamp")).toBeNull();
    expect(container.textContent).not.toMatch(/메모|MBTI|성별|나이대/);
    expect(container.textContent).toContain("동행 모두가 정한 약속은 아니에요");
    expect(screen.getByRole("button", { name: "방 만들기" })).toBeTruthy();
  });
});
