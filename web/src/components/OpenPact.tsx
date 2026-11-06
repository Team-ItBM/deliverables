import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { issueSeen } from "../lib/issue";
import { setSoundEnabled, soundEnabled, unlockSound } from "../lib/issueSound";
import { usePrefersReducedMotion } from "../lib/hooks";
import { BottomBar } from "./ui";

/** 제출한 기기와 방장이 협약서를 직접 여는 주 버튼. 연출이 남아 있으면 효과음 설정(기본 꺼짐)을 함께 둔다. */
export function OpenPact({ code }: { code: string }) {
  const navigate = useNavigate();
  const reduced = usePrefersReducedMotion();
  const [sound, setSound] = useState(soundEnabled);
  const showSound = !reduced && !issueSeen(code);
  return (
    <BottomBar>
      {showSound && (
        <label className="check">
          <input
            type="checkbox"
            checked={sound}
            onChange={(e) => {
              setSound(e.target.checked);
              setSoundEnabled(e.target.checked);
            }}
          />
          <span>효과음 켜기</span>
        </label>
      )}
      <button
        type="button"
        className="btn btn-primary"
        onClick={() => {
          unlockSound();
          navigate(`/r/${encodeURIComponent(code)}/result`, { state: { started: true } });
        }}
      >
        협약서 보기
      </button>
    </BottomBar>
  );
}
