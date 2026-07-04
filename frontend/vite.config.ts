/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev server proxies API calls to the FastAPI backend on :8000.
const backend = "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/research": backend,
      "/status": backend,
      "/report": backend,
      "/health": backend,
      "/metrics": backend,
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
  },
});
