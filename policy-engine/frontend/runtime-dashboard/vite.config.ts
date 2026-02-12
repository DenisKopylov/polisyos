import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

const runtimeApiTarget = process.env.RUNTIME_API_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      "/api/v1": {
        target: runtimeApiTarget,
        changeOrigin: true,
      },
      "/health": {
        target: runtimeApiTarget,
        changeOrigin: true,
      },
      "/ready": {
        target: runtimeApiTarget,
        changeOrigin: true,
      },
    },
  },
});
