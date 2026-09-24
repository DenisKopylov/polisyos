import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

import coverageScope from "./scripts/coverage-scope.json";

import { preserveVitestErrorCause } from "./scripts/preserve-vitest-error-cause";

const buildRoot = path.resolve(
  __dirname,
  "../../_build/apps/runtime-dashboard",
);

export default defineConfig({
  cacheDir: path.resolve(
    __dirname,
    "../../_cache/apps/runtime-dashboard/vitest",
  ),
  plugins: [react(), preserveVitestErrorCause()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    projects: [
      {
        extends: true,
        test: {
          name: "unit",
          exclude: [
            "e2e/**",
            "node_modules/**",
            "dist/**",
            "../../_build/**",
            "src/test/a11y/**/*.spec.ts",
            "src/**/*.browser.test.{ts,tsx}",
          ],
        },
      },
      "./vitest.confidence-ledger-browser.config.ts",
    ],
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: true,
    testTimeout: 15_000,
    coverage: {
      provider: "v8",
      reportsDirectory: path.resolve(buildRoot, "coverage"),
      reporter: ["text", "html", "json-summary", "lcov"],
      ...coverageScope,
    },
  },
});
