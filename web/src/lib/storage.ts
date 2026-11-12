// 브라우저 저장소는 사생활 보호 모드 등에서 막힐 수 있어 모든 읽기·쓰기를 감싼다.

type Area = "local" | "session";

function area(a: Area): Storage | null {
  try {
    return a === "local" ? window.localStorage : window.sessionStorage;
  } catch {
    return null;
  }
}

export function readJSON<T>(a: Area, key: string): T | null {
  try {
    const raw = area(a)?.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export function writeJSON(a: Area, key: string, value: unknown): void {
  try {
    area(a)?.setItem(key, JSON.stringify(value));
  } catch {
    /* 저장하지 못해도 화면은 메모리 상태로 동작한다 */
  }
}

export function remove(a: Area, key: string): void {
  try {
    area(a)?.removeItem(key);
  } catch {
    /* 무시 */
  }
}

export const keys = {
  host: (code: string) => `dowon.host.${code}`,
  session: (code: string) => `dowon.session.${code}`,
  submitted: (code: string) => `dowon.submitted.${code}`,
  pending: (code: string) => `dowon.pending.${code}`,
  push: (code: string, role: string) => `dowon.push.${code}.${role}`,
  seen: (code: string) => `dowon.seen.${code}`,
  sound: "dowon.sound",
};

/** 방 삭제 성공 또는 이미 삭제된 방에만 적용한다. 다른 방과 기기 설정은 보존한다. */
export function clearRoomStorage(code: string): void {
  const roomKeys = [
    keys.host(code),
    keys.session(code),
    keys.submitted(code),
    keys.pending(code),
    keys.push(code, "host"),
    keys.push(code, "participant"),
    keys.seen(code),
  ];
  for (const a of ["local", "session"] as const) {
    for (const key of roomKeys) remove(a, key);
  }
}
