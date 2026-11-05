import { ChevronDown } from "lucide-react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { BottomBar, CopyButton, ICON, ShareButton } from "../components/ui";
import { useHeaderBack } from "../lib/back";
import { hostUrl, inviteUrl } from "../lib/hostToken";
import { useHostToken } from "../lib/hooks";
import { inviteShare } from "../lib/shareText";

/** 방을 만든 직후의 안내. 주소가 있어서 새로고침해도 초대 링크를 다시 볼 수 있다. */
export function Created() {
  const { code = "" } = useParams();
  const navigate = useNavigate();
  const token = useHostToken(code);
  const roomPath = `/r/${encodeURIComponent(code)}`;
  useHeaderBack(() => navigate(roomPath));

  if (!token) return <Navigate to={roomPath} replace />;

  return (
    <main className="page">
      <div className="stack-sm">
        <h1 className="t-headline-lg">방을 만들었어요</h1>
        <p className="secondary">동행에게 초대 링크를 보내 주세요. 문항이 준비되면 링크로 들어와 각자 답할 수 있어요.</p>
      </div>
      <p className="link-box">{inviteUrl(code)}</p>
      <details className="fold">
        <summary>
          <span>방장 링크(나만 보관)</span>
          <ChevronDown {...ICON} />
        </summary>
        <div className="fold-body">
          <p className="t-body-sm secondary">
            이 기기를 쓸 수 없을 때 이 링크로 들어오면 결과를 고르고 문구를 고칠 수 있어요. 동행에게 보내지 마세요.
          </p>
          <p className="link-box">{hostUrl(code, token)}</p>
          <div>
            <CopyButton text={hostUrl(code, token)} label="방장 링크 복사" />
          </div>
        </div>
      </details>
      <BottomBar>
        <button type="button" className="btn btn-secondary" onClick={() => navigate(roomPath)}>
          방 화면으로 가기
        </button>
        <ShareButton data={inviteShare(inviteUrl(code))} shareLabel="초대 링크 보내기" copyLabel="초대 링크 복사" />
      </BottomBar>
    </main>
  );
}
