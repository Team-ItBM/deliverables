/** scene은 줄바꿈으로 나눈 개요다. 첫 줄은 상황, 다음 줄부터 조건이다(SPEC 5절). */
export function splitScene(scene: string): { lead: string; details: string[] } {
  const lines = scene
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0);
  return { lead: lines[0] ?? "", details: lines.slice(1) };
}

export const MEMO_MAX = 300;

/** 메모는 최대 300자다(SPEC 5절). 서로게이트 쌍이 반으로 잘리지 않게 코드 포인트로 센다. */
export function clampMemo(value: string): string {
  const chars = Array.from(value);
  return chars.length > MEMO_MAX ? chars.slice(0, MEMO_MAX).join("") : value;
}

export function memoLength(value: string): number {
  return Array.from(value).length;
}
