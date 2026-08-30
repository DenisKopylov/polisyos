import path from "node:path";

import react from "@vitejs/plugin-react";
import { playwright } from "@vitest/browser-playwright";
import { defineConfig } from "vitest/config";

export default defineConfig({
  cacheDir: path.resolve(
    __dirname,
    "../../_cache/apps/runtime-dashboard/vitest-confidence-ledger-browser",
  ),
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    browser: {
      enabled: true,
      headless: true,
      instances: [{ browser: "chromium" }],
      provider: playwright(),
    },
    css: true,
    globals: true,
    include: [
      "src/features/runs/export/confidenceLedgerRiskSpendTwin.browser.test.tsx",
    ],
  },
});
