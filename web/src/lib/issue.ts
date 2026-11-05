import { useEffect, useRef, useState, type RefObject } from "react";
import type { IssueSound } from "./issueSound";
import { keys, readJSON, writeJSON } from "./storage";

// DESIGN.md motion 토큰과 같은 값이다. tokens.css를 고치면 함께 고친다.
const PAPER = 1100;
const CLAUSE = 640;
const STAMP = 420;
const STAGGER = 220;
const BRANCH = 500;

export type IssuePhase = "issue" | "stamped" | "done";

/** 종이가 펼쳐진 뒤 조항이 차례로 나타나고, 마지막 조항이 끝나면 도장을 찍는다. n은 나타날 묶음 수다. */
export function issueTimeline(n: number) {
  const items = Math.max(n, 1);
  return {
    clauseAt: (i: number) => PAPER + i * STAGGER,
    stampAt: PAPER + (items - 1) * STAGGER + CLAUSE,
    endAfterStamp: Math.max(STAMP, BRANCH),
  };
}

export function issueSeen(code: string): boolean {
  return readJSON<boolean>("local", keys.seen(code)) === true;
}

export function markIssueSeen(code: string): void {
  writeJSON("local", keys.seen(code), true);
}

function barHeight(): number {
  return document.querySelector(".bottom-bar")?.getBoundingClientRect().height ?? 0;
}

function inView(el: Element): boolean {
  const r = el.getBoundingClientRect();
  return r.top >= 0 && r.bottom <= window.innerHeight - barHeight();
}

/**
 * 연출의 순서를 맡는다. 시간표는 소리와 상관없이 흐른다.
 * 조항이 나타나는 동안 화면을 도장 자리까지 따라 내리고, 사용자가 직접 움직이면 멈춘다.
 * 도장은 그 자리가 화면에 들어왔을 때 찍는다.
 */
export function useIssueSequence(
  active: boolean,
  paperRef: RefObject<HTMLElement>,
  n: number,
  sound: IssueSound
): IssuePhase {
  const [phase, setPhase] = useState<IssuePhase>(active ? "issue" : "done");
  const nRef = useRef(n);
  const soundRef = useRef(sound);

  useEffect(() => {
    if (!active) return;
    const paper = paperRef.current;
    const stampEl = paper?.querySelector(".stamp");
    if (!paper || !stampEl) {
      setPhase("done");
      return;
    }
    const line = issueTimeline(nRef.current);
    const play = soundRef.current;
    const timers: ReturnType<typeof setTimeout>[] = [];
    let frame = 0;
    let observer: IntersectionObserver | undefined;
    let stamped = false;
    let userMoved = false;

    const stopFollowing = () => {
      userMoved = true;
      cancelAnimationFrame(frame);
    };
    const moved = ["wheel", "touchstart", "keydown"] as const;
    moved.forEach((e) => window.addEventListener(e, stopFollowing, { passive: true }));

    const follow = (duration: number) => {
      if (userMoved) return;
      const from = window.scrollY;
      const gap = stampEl.getBoundingClientRect().bottom - (window.innerHeight - barHeight() - 16);
      if (gap <= 0) return;
      const began = performance.now();
      const tick = (now: number) => {
        const p = Math.min((now - began) / duration, 1);
        window.scrollTo(0, from + gap * p * (2 - p));
        if (p < 1) frame = requestAnimationFrame(tick);
      };
      frame = requestAnimationFrame(tick);
    };

    const stamp = () => {
      if (stamped) return;
      stamped = true;
      observer?.disconnect();
      setPhase("stamped");
      play.stamp();
      play.branch();
      timers.push(setTimeout(() => setPhase("done"), line.endAfterStamp));
    };

    const stampWhenVisible = () => {
      if (inView(stampEl) || typeof IntersectionObserver === "undefined") {
        stamp();
        return;
      }
      observer = new IntersectionObserver(
        (entries) => {
          if (entries.some((e) => e.isIntersecting)) stamp();
        },
        { rootMargin: `0px 0px -${Math.round(barHeight())}px 0px`, threshold: 0.9 }
      );
      observer.observe(stampEl);
    };

    play.paper();
    for (let i = 0; i < nRef.current; i++) timers.push(setTimeout(() => play.clause(), line.clauseAt(i)));
    timers.push(setTimeout(() => follow(line.stampAt - line.clauseAt(0)), line.clauseAt(0)));
    timers.push(setTimeout(stampWhenVisible, line.stampAt));

    return () => {
      timers.forEach(clearTimeout);
      cancelAnimationFrame(frame);
      observer?.disconnect();
      moved.forEach((e) => window.removeEventListener(e, stopFollowing));
    };
  }, [active, paperRef]);

  return phase;
}
