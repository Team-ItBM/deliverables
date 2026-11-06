import { cleanup, render } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { pageMetaFor, SITE_TITLE, usePageMeta } from "../lib/pageMeta";

afterEach(cleanup);

function Meta() {
  usePageMeta();
  return null;
}

const open = (path: string) =>
  render(
    <MemoryRouter initialEntries={[path]}>
      <Meta />
    </MemoryRouter>
  );

describe("화면별 메타", () => {
  it("첫 화면은 대표 제목과 canonical을 쓰고 noindex가 없다", () => {
    open("/");
    expect(document.title).toBe(SITE_TITLE);
    expect(document.head.querySelector('link[rel="canonical"]')?.getAttribute("href")).toBe("https://dowonpact.com/");
    expect(document.head.querySelector('meta[name="robots"]')).toBeNull();
  });

  it("방 경로는 noindex이고 canonical이 없으며 제목에 방 코드가 없다", () => {
    for (const path of ["/r/secretcode", "/r/secretcode/answer", "/r/secretcode/wait", "/r/secretcode/result", "/r/secretcode/created"]) {
      cleanup();
      open(path);
      expect(document.head.querySelector('meta[name="robots"]')?.getAttribute("content")).toBe("noindex, nofollow");
      expect(document.head.querySelector('link[rel="canonical"]')).toBeNull();
      expect(document.title).not.toContain("secretcode");
    }
  });

  it("처리방침은 자기 주소를 canonical로 쓴다", () => {
    expect(pageMetaFor("/privacy").canonical).toBe("https://dowonpact.com/privacy");
  });
});
