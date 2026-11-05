import { toBlob } from "html-to-image";

/**
 * 화면 밖에 360px 폭으로 그린 같은 종이를 3배로 그려 1080px 이미지를 만든다(DESIGN.md pact-paper).
 * 공유 시트가 파일을 받으면 공유하고, 아니면 내려받는다.
 */
export async function savePaperImage(node: HTMLElement, fileName: string): Promise<"shared" | "downloaded" | "cancelled"> {
  const blob = await toBlob(node, { pixelRatio: 3, cacheBust: true, backgroundColor: "#FAF8F5" });
  if (!blob) throw new Error("capture_failed");
  const file = new File([blob], fileName, { type: "image/png" });
  const nav = navigator as Navigator & { canShare?: (d: ShareData) => boolean };
  if (typeof nav.share === "function" && nav.canShare?.({ files: [file] })) {
    try {
      await nav.share({ files: [file], title: "여행 동행 협약서" });
      return "shared";
    } catch (err) {
      if ((err as { name?: string }).name === "AbortError") return "cancelled";
      // 공유 실패는 내려받기로 넘어간다.
    }
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
  return "downloaded";
}
