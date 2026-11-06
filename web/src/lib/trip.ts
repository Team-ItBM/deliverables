import type { PublicTrip } from "../api/types";

/** 입장 화면과 협약서가 함께 쓰는 여행 정보 한 줄. */
export function tripMetaText(t: PublicTrip): string {
  return [t.destination, `${t.duration_days}일`, `${t.party_size}명`].join(" · ");
}
