import { useState } from "react";
import { MOCK_AS_PARTICIPANT } from "../lib/hostToken";
import { readJSON, writeJSON } from "../lib/storage";

// 모의 모드(VITE_MOCK=1)에서만 보이는 막대. 다음 생성 결과의 종류와 방장 토큰 숨김을 바꾼다.
// mock/server.ts의 MOCK_VARIANT와 같은 키다. 서버 코드를 실서비스 번들에 넣지 않으려고 문자열로 둔다.
const VARIANT_KEY = "dowon.mock.variant";
const COUNT_KEY = "dowon.mock.count";

export function MockBar() {
  const [v, setV] = useState(() => {
    try {
      return localStorage.getItem(VARIANT_KEY) ?? "proposed";
    } catch {
      return "proposed";
    }
  });
  const [count, setCount] = useState(() => {
    try {
      return localStorage.getItem(COUNT_KEY) ?? "3";
    } catch {
      return "3";
    }
  });
  const [asParticipant, setAsParticipant] = useState(() => readJSON<boolean>("session", MOCK_AS_PARTICIPANT) === true);
  return (
    <div className="mock-bar" role="region" aria-label="모의 모드 설정">
      <span>모의 모드</span>
      <label>
        다음 생성
        <select
          value={v}
          onChange={(e) => {
            setV(e.target.value);
            try {
              localStorage.setItem(VARIANT_KEY, e.target.value);
            } catch {
              /* 무시 */
            }
          }}
        >
          <option value="proposed">조항 있는 결과</option>
          <option value="unresolved">미해결 결과</option>
          <option value="fail">생성 실패</option>
        </select>
      </label>
      <label>
        새 방 문항
        <select
          value={count}
          onChange={(e) => {
            setCount(e.target.value);
            try {
              localStorage.setItem(COUNT_KEY, e.target.value);
            } catch {
              /* 무시 */
            }
          }}
        >
          {["3", "6", "8"].map((n) => (
            <option key={n} value={n}>
              {n}개
            </option>
          ))}
        </select>
      </label>
      <label>
        <input
          type="checkbox"
          checked={asParticipant}
          onChange={(e) => {
            setAsParticipant(e.target.checked);
            writeJSON("session", MOCK_AS_PARTICIPANT, e.target.checked);
            window.location.reload();
          }}
        />
        참여자로 보기
      </label>
    </div>
  );
}
