/// <reference types="vitest" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "VITE_");
  const target = env.VITE_API_BASE || "http://localhost:8000";
  return {
    plugins: [react()],
    server: {
      host: true,
      proxy: { "/api": { target, changeOrigin: true } },
      // docs/PRIVACY.md를 ?raw로 읽기 위해 저장소 루트 접근을 허용한다.
      fs: { allow: [".."] },
    },
    test: {
      environment: "jsdom",
      globals: true,
      setupFiles: ["./src/test/setup.ts"],
    },
  };
});
