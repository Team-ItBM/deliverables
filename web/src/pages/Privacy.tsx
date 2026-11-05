import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import privacyMd from "../../../docs/PRIVACY.md?raw";
import { Markdown } from "../components/Markdown";

/** docs/PRIVACY.md를 빌드 때 그대로 넣어 그린다. 문서를 고치면 다음 빌드에 반영된다. */
export function Privacy() {
  const { hash } = useLocation();
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView();
  }, [hash]);
  return (
    <main className="page">
      <Markdown source={privacyMd} />
    </main>
  );
}
