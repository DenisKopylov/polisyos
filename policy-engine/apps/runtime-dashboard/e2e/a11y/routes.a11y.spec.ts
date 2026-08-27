import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import { WCAG_AA_TAGS } from "@/test/a11yTags";
import {
  DASHBOARD_ROUTE_SURFACES,
  installDashboardTestState,
  readFixtureMetadata,
  waitForDashboardSurface,
} from "../helpers/runtime-dashboard";

async function analyzeWithRetry(
  page: Parameters<typeof AxeBuilder>[0]["page"],
) {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      await page.waitForLoadState("domcontentloaded");
      await page.waitForLoadState("networkidle").catch(() => undefined);
      return await new AxeBuilder({ page })
        .withTags([...WCAG_AA_TAGS])
        .analyze();
    } catch (error) {
      if (
        error instanceof Error &&
        error.message.includes("Execution context was destroyed") &&
        attempt === 0
      ) {
        await page.waitForLoadState("domcontentloaded");
        continue;
      }
      throw error;
    }
  }

  throw new Error("axe analysis did not complete");
}

test.describe("runtime-dashboard route accessibility", () => {
  test.beforeEach(async ({ page }) => {
    await installDashboardTestState(page);
  });

  for (const surface of DASHBOARD_ROUTE_SURFACES) {
    test(`${surface.name} passes axe`, async ({ page }) => {
      if (surface.ready === "trust") {
        test.setTimeout(120_000);
      }

      const metadata = readFixtureMetadata();

      await page.goto(surface.path(metadata));
      await waitForDashboardSurface(page, surface.ready);

      const results = await analyzeWithRetry(page);
      expect(results.violations).toEqual([]);
    });
  }
});
