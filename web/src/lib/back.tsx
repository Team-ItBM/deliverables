import { createContext, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from "react";

type Handler = () => void;

const Value = createContext<Handler | null>(null);
const Setter = createContext<(h: Handler | null) => void>(() => {});

export function BackProvider({ children }: { children: ReactNode }) {
  const [handler, setHandler] = useState<Handler | null>(null);
  const set = useMemo(() => (h: Handler | null) => setHandler(() => h), []);
  return (
    <Setter.Provider value={set}>
      <Value.Provider value={handler}>{children}</Value.Provider>
    </Setter.Provider>
  );
}

export function useBackHandler(): Handler | null {
  return useContext(Value);
}

/** 화면이 상단 뒤로가기의 동작을 정한다. 부르지 않은 화면에는 버튼이 없다. */
export function useHeaderBack(fn: Handler): void {
  const set = useContext(Setter);
  const latest = useRef(fn);
  latest.current = fn;
  useEffect(() => {
    set(() => latest.current());
    return () => set(null);
  }, [set]);
}
