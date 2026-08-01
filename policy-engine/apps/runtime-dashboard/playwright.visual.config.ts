import path from "node:path";
import { fileURLToPath } from "node:url";

import { defineConfig, type PlaywrightTestConfig } from "@playwright/test";

import baseConfig from "./playwright.config";

const dashboardRoot = path.dirname(fileURLToPath(import.meta.url));
const storybookServer = {
  command: "corepack pnpm exec storybook dev --ci --no-open -p 6006",
  cwd: dashboardRoot,
  reuseExistingServer: !process.env.CI,
  timeout: 120_000,
  url: "http://127.0.0.1:6006/iframe.html",
} satisfies NonNullable<
  PlaywrightTestConfig["webServer"]
> extends readonly (infer Server)[]
  ? Server
  : never;

export default defineConfig(baseConfig, {
  testMatch: /runtime-dashboard\.visual\.spec\.ts/,
  webServer: storybookServer,
});
