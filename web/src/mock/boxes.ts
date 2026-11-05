// 박스 정리 시안 전환. 모의 모드에서만 값이 있다. 사람이 고른 뒤 지운다.
export const BOX_KEY = "dowon.mock.boxes";

export function boxVariant(): "a" | "b" | null {
  if (import.meta.env.VITE_MOCK !== "1") return null;
  try {
    const v = localStorage.getItem(BOX_KEY);
    return v === "a" || v === "b" ? v : null;
  } catch {
    return null;
  }
}
