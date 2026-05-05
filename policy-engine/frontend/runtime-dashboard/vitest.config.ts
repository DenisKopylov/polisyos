import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

const buildRoot = path.resolve(__dirname, "../../_build/frontend/runtime-dashboard");

export default defineConfig({
  cacheDir: path.resolve(__dirname, "../../_cache/frontend/runtime-dashboard/vitest"),
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: true,
    testTimeout: 15_000,
    exclude: [
      "e2e/**",
      "node_modules/**",
      "dist/**",
      "../../_build/**",
      "src/test/a11y/**/*.spec.ts",
    ],
    coverage: {
      provider: "v8",
      reportsDirectory: path.resolve(buildRoot, "coverage"),
      reporter: ["text", "html", "json-summary", "lcov"],
      include: [
        "src/api/hooks/**/*.{ts,tsx}",
        "src/app/layout/**/*.{ts,tsx}",
        "src/features/artifacts/routes/**/*.{ts,tsx}",
        "src/features/auth/routes/**/*.{ts,tsx}",
        "src/features/composer/**/*.{ts,tsx}",
        "src/features/dashboard/routes/**/*.{ts,tsx}",
        "src/features/evidence/**/*.{ts,tsx}",
        "src/features/lex/routes/**/*.{ts,tsx}",
        "src/features/platform/routes/**/*.{ts,tsx}",
        "src/features/runs/**/*.{ts,tsx}",
        "src/shared/components/**/*.{ts,tsx}",
        "src/shared/ui/**/*.{ts,tsx}",
      ],
      exclude: [
        "src/**/*.stories.{ts,tsx}",
        "src/**/*.test.{ts,tsx}",
        "src/**/*.a11y.test.{ts,tsx}",
        "src/**/index.ts",
        "src/**/route.tsx",
        "src/test/**",
      ],
    },
  },
});
