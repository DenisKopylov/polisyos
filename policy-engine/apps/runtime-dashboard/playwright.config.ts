import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig, devices } from "@playwright/test";

const dashboardRoot = path.dirname(fileURLToPath(import.meta.url));
const policyEngineRoot = path.resolve(dashboardRoot, "../..");
const dashboardBuildRoot = path.resolve(
  policyEngineRoot,
  "_build/apps/runtime-dashboard",
);
const fixtureMetadataPath = path.resolve(
  dashboardBuildRoot,
  ".tmp/fixture-runtime.json",
);
const includeQuarantine = process.env.PLAYWRIGHT_INCLUDE_QUARANTINE === "1";
const configuredRetries = Number.parseInt(
  process.env.PLAYWRIGHT_RETRIES ?? "0",
  10,
);

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  timeout: 60_000,
  workers: 1,
  grepInvert: includeQuarantine ? undefined : /@quarantine/,
  outputDir: path.resolve(dashboardBuildRoot, "test-results"),
  reporter: process.env.CI
    ? [
        ["github"],
        [
          "html",
          {
            open: "never",
            outputFolder: path.resolve(dashboardBuildRoot, "playwright-report"),
          },
        ],
      ]
    : [["list"]],
  retries: Number.isNaN(configuredRetries) ? 0 : configuredRetries,
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    testIdAttribute: "data-testid",
  },
  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
      },
    },
    {
      name: "mobile-chromium",
      testIgnore: /runtime-dashboard\.visual\.spec\.ts/,
      use: {
        ...devices["Pixel 7"],
      },
    },
  ],
  webServer: [
    {
      command: `uv run --extra runtime-http python apps/runtime-dashboard/scripts/serve_fixture_runtime_api.py --port 8000 --metadata-file ${fixtureMetadataPath}`,
      url: "http://127.0.0.1:8000/health",
      cwd: policyEngineRoot,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: "corepack pnpm run dev -- --host 127.0.0.1",
      url: "http://127.0.0.1:5173",
      cwd: dashboardRoot,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      env: {
        RUNTIME_API_URL: "http://127.0.0.1:8000",
        VITE_DISABLE_RUNS_LIVE: "true",
      },
    },
  ],
});
