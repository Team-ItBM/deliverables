import { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import privacyMd from "../../../docs/PRIVACY.md?raw";
import { Markdown } from "../components/Markdown";
import { useHeaderBack } from "../lib/back";

/** docs/PRIVACY.md를 빌드 때 그대로 넣어 그린다. 문서를 고치면 다음 빌드에 반영된다. */
export function Privacy() {
  const { hash, key } = useLocation();
  const navigate = useNavigate();
  // 앱 안에서 왔으면 그 화면으로, 주소로 바로 열었으면 첫 화면으로 돌아간다.
  useHeaderBack(() => (key === "default" ? navigate("/") : navigate(-1)));
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView();
  }, [hash]);
  return (
    <main className="page">
      <Markdown source={privacyMd} />
    </main>
  );
}
