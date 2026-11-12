import { toBlob } from "html-to-image";

/** 360px 종이를 3배로 그려 1080px PNG 파일을 미리 준비한다. */
export async function preparePaperImage(node: HTMLElement, fileName = "dowon-pact.png"): Promise<File> {
  await document.fonts?.ready;
  const blob = await toBlob(node, { pixelRatio: 3, backgroundColor: "#FAF8F5" });
  if (!blob) throw new Error("capture_failed");
  return new File([blob], fileName, { type: "image/png" });
}

export function canSharePaperImage(file: File): boolean {
  try {
    return typeof navigator.share === "function" && typeof navigator.canShare === "function" && navigator.canShare({ files: [file] });
  } catch {
    return false;
  }
}

/** 사용자 클릭의 호출 스택에서 바로 공유한다. 준비나 다운로드 fallback을 여기서 하지 않는다. */
export function sharePaperImage(file: File): Promise<void> {
  return navigator.share({ files: [file] });
}

/** 브라우저에 다운로드를 요청한다. 실제 파일 저장 완료는 브라우저 밖에서 확인해야 한다. */
export function downloadPaperImage(file: File): void {
  const url = URL.createObjectURL(file);
  const a = document.createElement("a");
  try {
    a.href = url;
    a.download = file.name;
    document.body.appendChild(a);
    a.click();
  } finally {
    a.remove();
    // 링크를 처리하는 브라우저가 파일을 읽을 시간을 주고 해제한다.
    setTimeout(() => URL.revokeObjectURL(url), 10_000);
  }
}
