import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { App } from "./App";
import { setTransport } from "./api/client";
import { captureHostTokenFromHash } from "./lib/hostToken";
import { boxVariant } from "./mock/boxes";
import "./styles/tokens.css";
import "./styles/app.css";

async function boot() {
  // 방장 링크의 #host=... 를 먼저 저장하고 주소창에서 지운다.
  captureHostTokenFromHash();
  document.documentElement.dataset.boxes = boxVariant() ?? "";

  if (import.meta.env.VITE_MOCK === "1") {
    const { mockTransport } = await import("./mock/server");
    setTransport(mockTransport);
  }

  if ("serviceWorker" in navigator && import.meta.env.VITE_MOCK !== "1") {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      /* 알림 없이도 화면은 동작한다 */
    });
  }

  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </StrictMode>
  );
}

void boot();
