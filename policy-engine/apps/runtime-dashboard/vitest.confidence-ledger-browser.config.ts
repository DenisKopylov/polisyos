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
  optimizeDeps: { include: ["axe-core"] },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    name: "confidence-ledger-browser",
    attachmentsDir: path.resolve(
      __dirname,
      "../../_build/apps/runtime-dashboard/vitest-attachments",
    ),
    browser: {
      enabled: true,
      headless: true,
      instances: [{ browser: "chromium" }],
      provider: playwright(),
    },
    css: true,
    globals: true,
    include: [
      "src/features/runs/components/ConfidenceLedgerRiskSpend.a11y.browser.test.tsx",
      "src/features/runs/export/confidenceLedgerRiskSpendTwin.browser.test.tsx",
    ],
  },
});
