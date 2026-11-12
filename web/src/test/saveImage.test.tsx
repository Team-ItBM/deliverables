import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { StrictMode } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { toBlob } from "html-to-image";
import type { SharedResult } from "../api/types";
import { preparePaperImage } from "../lib/saveImage";
import { SheetWithSave } from "../pages/Result";

vi.mock("html-to-image", () => ({ toBlob: vi.fn() }));

const paper: SharedResult = {
  result_id: "r1", kind: "ai_original", source_result_id: null, label: null, draft: false,
  pact_status: "proposed", included_count: 2, excluded_names: [],
  clauses: [{ scenario_id: "q1", participant_names: ["민준"], action: "함께 쉬어요", proposed_conditions: [] }],
  conditional_alternatives: [], unresolved_conditions: [],
};
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => { resolve = r; });
  return { promise, resolve };
}
const png = () => new Blob(["png"], { type: "image/png" });
const share = vi.fn();
const createUrl = vi.fn();
const revokeUrl = vi.fn();
let anchorClick: ReturnType<typeof vi.spyOn>;
function sheet(result = paper) {
  return <MemoryRouter><SheetWithSave code="c" started={false} result={result} saveIsPrimary /></MemoryRouter>;
}
const download = () => screen.getByRole("button", { name: "이미지 다운로드" }) as HTMLButtonElement;

beforeEach(() => {
  vi.mocked(toBlob).mockReset().mockResolvedValue(png());
  share.mockReset().mockResolvedValue(undefined);
  createUrl.mockReset().mockImplementation(() => `blob:image-${createUrl.mock.calls.length}`);
  revokeUrl.mockReset();
  Object.defineProperty(URL, "createObjectURL", { configurable: true, value: createUrl });
  Object.defineProperty(URL, "revokeObjectURL", { configurable: true, value: revokeUrl });
  Object.defineProperty(navigator, "share", { configurable: true, value: share });
  Object.defineProperty(navigator, "canShare", { configurable: true, value: vi.fn(() => true) });
  Object.defineProperty(window, "matchMedia", { configurable: true, value: vi.fn(() => ({ matches: true, addEventListener() {}, removeEventListener() {} })) });
  Object.defineProperty(document, "fonts", { configurable: true, value: { ready: Promise.resolve() } });
  anchorClick = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
});
afterEach(() => { anchorClick.mockRestore(); });

describe("결과 이미지 준비와 동작", () => {
  it("폰트와 캡처가 끝날 때까지 내려받기를 막고 파일만 클릭 즉시 공유한다", async () => {
    const fonts = deferred<void>();
    Object.defineProperty(document, "fonts", { configurable: true, value: { ready: fonts.promise } });
    render(sheet());
    expect(download().disabled).toBe(true);
    expect(toBlob).not.toHaveBeenCalled();
    await act(async () => fonts.resolve());
    await waitFor(() => expect(download().disabled).toBe(false));
    fireEvent.click(screen.getByRole("button", { name: "이미지 공유" }));
    expect(share).toHaveBeenCalledTimes(1);
    const payload = share.mock.calls[0]![0];
    expect(Object.keys(payload)).toEqual(["files"]);
    expect(payload.files[0]).toBeInstanceOf(File);
    expect(payload.files[0].type).toBe("image/png");
    expect(toBlob).toHaveBeenCalledTimes(1);
    expect(anchorClick).not.toHaveBeenCalled();
  });

  it("내려받기는 요청으로 안내하고 미리보기는 같은 준비 파일을 사용한다", async () => {
    const view = render(sheet());
    await waitFor(() => expect(download().disabled).toBe(false));
    fireEvent.click(download());
    expect(anchorClick).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/다운로드를 요청했어요/)).toBeTruthy();
    expect(screen.queryByText("이미지를 저장했어요.")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "저장이 안 되나요?" }));
    expect(screen.getByAltText("저장할 여행 동행 협약서").getAttribute("src")).toBe("blob:image-1");
    expect(screen.getByText(/Safari 또는 Chrome/)).toBeTruthy();
    expect(toBlob).toHaveBeenCalledTimes(1);
    view.unmount();
    expect(revokeUrl).toHaveBeenCalledWith("blob:image-1");
  });

  it.each(["AbortError", "NotAllowedError"])("공유 %s 뒤 자동 다운로드 없이 직접 내려받기를 유지한다", async (name) => {
    share.mockRejectedValue(new DOMException("failed", name));
    render(sheet());
    await waitFor(() => expect(download().disabled).toBe(false));
    fireEvent.click(screen.getByRole("button", { name: "이미지 공유" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "이미지 공유" })).toBeTruthy());
    expect(anchorClick).not.toHaveBeenCalled();
    expect(download().disabled).toBe(false);
    if (name !== "AbortError") expect(screen.getByText(/공유 창을 열지 못했어요/)).toBeTruthy();
    fireEvent.click(download());
    expect(anchorClick).toHaveBeenCalledTimes(1);
  });

  it("공유 미지원이어도 직접 내려받을 수 있고 다운로드 오류를 다시 시도한다", async () => {
    Object.defineProperty(navigator, "canShare", { configurable: true, value: () => false });
    render(sheet());
    await waitFor(() => expect(download().disabled).toBe(false));
    expect(screen.queryByRole("button", { name: "이미지 공유" })).toBeNull();
    anchorClick.mockImplementationOnce(() => { throw new Error("blocked"); });
    fireEvent.click(download());
    expect(screen.getByText(/다운로드를 요청하지 못했어요/)).toBeTruthy();
    expect(download().disabled).toBe(false);
    fireEvent.click(download());
    expect(screen.getByText(/다운로드를 요청했어요/)).toBeTruthy();
  });

  it("같은 내용의 polling은 캡처하지 않고 이름·초안·문구 변경은 새 파일을 만든다", async () => {
    const view = render(sheet());
    await waitFor(() => expect(download().disabled).toBe(false));
    view.rerender(sheet(structuredClone(paper)));
    expect(toBlob).toHaveBeenCalledTimes(1);
    view.rerender(sheet({ ...paper, draft: true, excluded_names: ["하늘"] }));
    expect(download().disabled).toBe(true);
    await waitFor(() => expect(toBlob).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(download().disabled).toBe(false));
    expect(revokeUrl).toHaveBeenCalledWith("blob:image-1");
    view.rerender(sheet({ ...paper, message: "바뀐 문구" }));
    await waitFor(() => expect(toBlob).toHaveBeenCalledTimes(3));
  });

  it("이전 내용의 늦은 캡처를 버리고 해제 후 완료된 캡처의 URL도 만들지 않는다", async () => {
    const old = deferred<Blob | null>();
    const next = deferred<Blob | null>();
    vi.mocked(toBlob).mockReset().mockReturnValueOnce(old.promise).mockReturnValueOnce(next.promise);
    const view = render(sheet());
    await waitFor(() => expect(toBlob).toHaveBeenCalledTimes(1));
    view.rerender(sheet({ ...paper, message: "새 문구" }));
    await waitFor(() => expect(toBlob).toHaveBeenCalledTimes(2));
    await act(async () => next.resolve(png()));
    expect(download().disabled).toBe(false);
    await act(async () => old.resolve(png()));
    expect(createUrl).toHaveBeenCalledTimes(1);
    const late = deferred<Blob | null>();
    vi.mocked(toBlob).mockReturnValueOnce(late.promise);
    view.rerender(sheet({ ...paper, message: "마지막 문구" }));
    await waitFor(() => expect(toBlob).toHaveBeenCalledTimes(3));
    view.unmount();
    await act(async () => late.resolve(png()));
    expect(createUrl).toHaveBeenCalledTimes(1);
  });

  it("캡처 실패 후 다시 준비할 수 있다", async () => {
    vi.mocked(toBlob).mockRejectedValueOnce(new Error("capture"));
    render(sheet());
    fireEvent.click(await screen.findByRole("button", { name: "다시 시도" }));
    await waitFor(() => expect(download().disabled).toBe(false));
    expect(toBlob).toHaveBeenCalledTimes(2);
  });

  it("StrictMode의 재설정 뒤에도 현재 이미지 준비가 끝난다", async () => {
    render(<StrictMode>{sheet()}</StrictMode>);
    await waitFor(() => expect(download().disabled).toBe(false));
    fireEvent.click(screen.getByRole("button", { name: "이미지 공유" }));
    expect(share).toHaveBeenCalledTimes(1);
  });

  it("빈 캡처 결과는 준비 실패로 처리한다", async () => {
    vi.mocked(toBlob).mockResolvedValueOnce(null);
    await expect(preparePaperImage(document.createElement("div"))).rejects.toThrow("capture_failed");
  });
});
