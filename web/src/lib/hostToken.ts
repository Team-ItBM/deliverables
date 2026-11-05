import { keys, readJSON, remove, writeJSON } from "./storage";

const MOCK = import.meta.env.VITE_MOCK === "1";
export const MOCK_AS_PARTICIPANT = "dowon.mock.asParticipant";

export function getHostToken(code: string): string | null {
  // 모의 모드에서만: 같은 브라우저에서 참여자 화면을 보려고 방장 토큰을 숨긴다.
  if (MOCK && readJSON<boolean>("session", MOCK_AS_PARTICIPANT)) return null;
  return readJSON<string>("local", keys.host(code));
}

export function saveHostToken(code: string, token: string): void {
  writeJSON("local", keys.host(code), token);
}

/**
 * 방장 링크(#host=...)로 들어오면 토큰을 저장하고 주소창에서 지운다.
 * 주소 기록에 토큰이 남지 않도록 replaceState를 쓴다.
 */
export function captureHostTokenFromHash(loc: Location = window.location): string | null {
  const m = /^\/r\/([^/]+)/.exec(loc.pathname);
  const hash = loc.hash.startsWith("#") ? loc.hash.slice(1) : loc.hash;
  const token = new URLSearchParams(hash).get("host");
  if (!m || !token) return null;
  const code = decodeURIComponent(m[1]!);
  saveHostToken(code, token);
  try {
    window.history.replaceState(window.history.state, "", loc.pathname + loc.search);
  } catch {
    /* 무시 */
  }
  return code;
}

export function forgetHostToken(code: string): void {
  remove("local", keys.host(code));
}

export function inviteUrl(code: string): string {
  return `${window.location.origin}/r/${encodeURIComponent(code)}`;
}

export function hostUrl(code: string, token: string): string {
  return `${inviteUrl(code)}#host=${encodeURIComponent(token)}`;
}
