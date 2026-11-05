import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api/client";
import { ApiError } from "../api/errors";
import type { RoomStatus } from "../api/types";
import { loadPending, type PendingSubmission } from "./answerSession";
import { getHostToken } from "./hostToken";
import { keys } from "./storage";

/**
 * 같은 요청을 주기적으로 다시 부른다. 성공하면 3초에서 5초까지 천천히 늘리고,
 * 실패하면 두 배씩 20초까지 늘린다. active가 false면 멈춘다.
 */
export function usePolling<T>(
  fetcher: () => Promise<T>,
  active: (data: T | null) => boolean,
  deps: unknown[]
): { data: T | null; error: unknown; reload: () => void; loading: boolean } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const [tick, setTick] = useState(0);
  const delay = useRef(3000);
  const fetchRef = useRef(fetcher);
  fetchRef.current = fetcher;
  const activeRef = useRef(active);
  activeRef.current = active;

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const run = async () => {
      let next: T | null = null;
      try {
        next = await fetchRef.current();
        if (cancelled) return;
        setData(next);
        setError(null);
        delay.current = Math.min(delay.current + 500, 5000);
      } catch (err) {
        if (cancelled) return;
        setError(err);
        delay.current = Math.min(delay.current * 2, 20000);
      } finally {
        if (!cancelled) setLoading(false);
      }
      if (!cancelled && activeRef.current(next)) timer = setTimeout(run, delay.current);
    };
    void run();
    const onVisible = () => {
      if (document.visibilityState === "visible") {
        clearTimeout(timer);
        delay.current = 3000;
        void run();
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      cancelled = true;
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  const reload = useCallback(() => {
    delay.current = 3000;
    setTick((t) => t + 1);
  }, []);
  return { data, error, reload, loading };
}

export interface ResultCheck {
  /** 결과가 있으면 true, 없으면 false, 아직 모르면 null이다. */
  has: boolean | null;
  /** 결과 존재 여부를 확인하지 못했다. has는 null이다. */
  failed: boolean;
  retry: () => void;
}

const RESULT_CHECK_AUTO_RETRIES = 3;
const RESULT_CHECK_DELAY_MS = 3000;

/**
 * 공개할 결과가 있는지 본다. 재생성이 실패하거나 진행 중이어도 기존 결과는 남아 있어서
 * room_status로는 판단할 수 없다. 응답을 받는 동안에는 결과가 없다.
 * 서버가 없다고 답한 경우(invalid_state)만 "없음"이다. 연결 끊김·429·5xx는 "확인 실패"로 두고
 * 몇 번 자동으로 다시 본다. 그래도 실패하면 화면의 retry로 다시 확인한다.
 */
export function useResultCheck(code: string, status: RoomStatus | undefined): ResultCheck {
  const [has, setHas] = useState<boolean | null>(null);
  const [failed, setFailed] = useState(false);
  const [tick, setTick] = useState(0);
  const autoRetries = useRef(0);
  useEffect(() => {
    if (!status) return;
    if (status === "open") {
      setHas(false);
      setFailed(false);
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    api
      .getResult(code)
      .then(() => {
        if (cancelled) return;
        setHas(true);
        setFailed(false);
        autoRetries.current = 0;
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.definitive) {
          setHas(false);
          setFailed(false);
          autoRetries.current = 0;
          return;
        }
        setHas(null);
        setFailed(true);
        if (autoRetries.current < RESULT_CHECK_AUTO_RETRIES) {
          autoRetries.current += 1;
          timer = setTimeout(() => setTick((t) => t + 1), RESULT_CHECK_DELAY_MS * autoRetries.current);
        }
      });
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [code, status, tick]);
  const retry = useCallback(() => {
    autoRetries.current = 0;
    setTick((t) => t + 1);
  }, []);
  return { has, failed, retry };
}

/** 결과를 모르는 제출. 다른 탭이 확인을 끝내면 storage 이벤트로 알 수 있다. 이 탭의 변경은 refresh로 다시 읽는다. */
export function usePendingSubmission(code: string): { pending: PendingSubmission | null; refresh: () => void } {
  const [pending, setPending] = useState(() => loadPending(code));
  const refresh = useCallback(() => setPending(loadPending(code)), [code]);
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === null || e.key === keys.pending(code)) refresh();
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, [code, refresh]);
  return { pending, refresh };
}

export function useHostToken(code: string): string | null {
  const [token] = useState(() => getHostToken(code));
  return token;
}

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => {
    try {
      return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    } catch {
      return false;
    }
  });
  useEffect(() => {
    let mq: MediaQueryList;
    try {
      mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    } catch {
      return;
    }
    const on = () => setReduced(mq.matches);
    mq.addEventListener?.("change", on);
    return () => mq.removeEventListener?.("change", on);
  }, []);
  return reduced;
}
