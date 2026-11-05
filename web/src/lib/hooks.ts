import { useCallback, useEffect, useRef, useState } from "react";
import { getHostToken } from "./hostToken";

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
