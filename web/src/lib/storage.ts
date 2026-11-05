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
  push: (code: string, role: string) => `dowon.push.${code}.${role}`,
  seen: (code: string) => `dowon.seen.${code}`,
  sound: "dowon.sound",
};
