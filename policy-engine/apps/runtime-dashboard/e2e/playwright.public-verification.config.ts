import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig, devices } from "@playwright/test";

const dashboardRoot = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "..",
);
const policyEngineRoot = path.resolve(dashboardRoot, "../..");
const fixtureRoot = path.resolve(
  policyEngineRoot,
  "_build/apps/runtime-dashboard/public-verification",
);

export default defineConfig({
  testDir: ".",
  testMatch: [
    "public-decision-verification.browser.ts",
    "journeys/trust-framing-negative-traces.spec.ts",
    "runtime-dashboard.visual.spec.ts",
  ],
  grep: /real verification service|trust-framing-|remains absent from the public decision route/,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 60_000,
  reporter: [["list"]],
  outputDir: path.resolve(fixtureRoot, "test-results"),
  use: {
    baseURL: "http://127.0.0.1:5177",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    testIdAttribute: "data-testid",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: [
    {
      command:
        ".venv/bin/python apps/runtime-dashboard/e2e/fixtures/serve_public_verification_api.py --fixture-root _build/apps/runtime-dashboard/public-verification --port 8017",
      cwd: policyEngineRoot,
      url: "http://127.0.0.1:8017/health",
      timeout: 120_000,
      reuseExistingServer: false,
    },
    {
      command:
        "corepack pnpm exec vite --host 127.0.0.1 --port 5177 --strictPort",
      cwd: dashboardRoot,
      url: "http://127.0.0.1:5177",
      timeout: 120_000,
      reuseExistingServer: false,
      env: {
        RUNTIME_API_URL: "http://127.0.0.1:8017",
        VITE_DISABLE_RUNS_LIVE: "true",
      },
    },
  ],
});
