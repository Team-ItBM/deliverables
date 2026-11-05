import { useEffect } from "react";
import { useLocation } from "react-router-dom";

export const SITE_TITLE = "도원결의 · 떠나기 전에, 서로의 마음을 한 장에";
const SITE_ORIGIN = "https://dowonpact.com";

export interface PageMeta {
  title: string;
  /** 검색에 내보낼 주소. 없으면 canonical을 지우고 noindex를 건다. */
  canonical?: string;
}

/** 제목에 방 코드, 목적지, 이름을 넣지 않는다. */
export function pageMetaFor(pathname: string): PageMeta {
  if (pathname === "/") return { title: SITE_TITLE, canonical: `${SITE_ORIGIN}/` };
  if (pathname === "/privacy") return { title: "개인정보 처리방침 · 도원결의", canonical: `${SITE_ORIGIN}/privacy` };
  if (pathname === "/new") return { title: "방 만들기 · 도원결의" };
  const room = /^\/r\/[^/]+(\/[^/]+)?$/.exec(pathname);
  if (room) {
    const sub = room[1];
    if (sub === "/answer") return { title: "답하기 · 도원결의" };
    if (sub === "/wait") return { title: "진행 상황 · 도원결의" };
    if (sub === "/result") return { title: "추천 협약서 · 도원결의" };
    if (sub === "/created") return { title: "초대 링크 · 도원결의" };
    return { title: "여행 방 · 도원결의" };
  }
  return { title: "페이지를 찾지 못했어요 · 도원결의" };
}

function setHeadLink(href: string | undefined) {
  let el = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
  if (!href) {
    el?.remove();
    return;
  }
  if (!el) {
    el = document.createElement("link");
    el.rel = "canonical";
    document.head.appendChild(el);
  }
  el.href = href;
}

function setRobots(noindex: boolean) {
  let el = document.head.querySelector<HTMLMetaElement>('meta[name="robots"]');
  if (!noindex) {
    el?.remove();
    return;
  }
  if (!el) {
    el = document.createElement("meta");
    el.name = "robots";
    document.head.appendChild(el);
  }
  el.content = "noindex, nofollow";
}

export function usePageMeta(): void {
  const { pathname } = useLocation();
  useEffect(() => {
    const meta = pageMetaFor(pathname);
    document.title = meta.title;
    setHeadLink(meta.canonical);
    setRobots(!meta.canonical);
  }, [pathname]);
}
