import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { sentryVitePlugin } from "@sentry/vite-plugin";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";
import { visualizer } from "rollup-plugin-visualizer";
import { VitePWA } from "vite-plugin-pwa";

const runtimeApiTarget = process.env.RUNTIME_API_URL ?? "http://127.0.0.1:8000";
const analyzeBundle = process.env.ANALYZE_BUNDLE === "true";
const sentryAuthToken = process.env.SENTRY_AUTH_TOKEN?.trim();
const sentryOrg = process.env.SENTRY_ORG?.trim();
const sentryProject = process.env.SENTRY_PROJECT?.trim();
const sentryRelease = process.env.VITE_SENTRY_RELEASE?.trim();
const shouldUploadSourcemaps = Boolean(
  sentryAuthToken && sentryOrg && sentryProject && sentryRelease,
);

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      devOptions: {
        enabled: false,
      },
      filename: "sw.js",
      injectManifest: {
        globPatterns: ["**/*.{css,js,html,woff2,png,svg}"],
      },
      registerType: "autoUpdate",
      srcDir: "src",
      strategies: "injectManifest",
    }),
    analyzeBundle
      ? visualizer({
          filename: "dist/bundle-analysis.html",
          gzipSize: true,
          open: false,
        })
      : null,
    shouldUploadSourcemaps
      ? sentryVitePlugin({
          authToken: sentryAuthToken,
          org: sentryOrg,
          project: sentryProject,
          release: {
            name: sentryRelease,
          },
          sourcemaps: {
            assets: "./dist/**",
          },
        })
      : null,
  ].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    manifest: true,
    sourcemap: "hidden",
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/scheduler/")) {
            return "vendor-scheduler";
          }
          if (
            id.includes("node_modules/react-dom") ||
            id.includes("node_modules/react/")
          ) {
            return "vendor-react";
          }
          if (
            id.includes("node_modules/react-hook-form") ||
            id.includes("node_modules/@hookform/")
          ) {
            return "vendor-forms";
          }
          if (id.includes("node_modules/zod")) {
            return "vendor-schema";
          }
          if (id.includes("node_modules/recharts")) {
            return "vendor-recharts";
          }
          if (id.includes("node_modules/react-router")) {
            return "vendor-router";
          }
          if (id.includes("node_modules/@tanstack/react-query")) {
            return "vendor-query";
          }
          if (id.includes("node_modules")) {
            return "vendor";
          }
          return undefined;
        },
      },
    },
  },
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
