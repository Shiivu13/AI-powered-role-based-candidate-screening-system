import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// In development the UI calls /api on the Vite server, which proxies to FastAPI.
// Set VITE_API_URL to call a backend on another origin instead.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: {
        "/api": { target: env.BACKEND_URL || "http://127.0.0.1:8000", changeOrigin: true },
      },
    },
  };
});
