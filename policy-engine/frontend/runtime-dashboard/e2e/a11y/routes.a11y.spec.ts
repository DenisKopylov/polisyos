import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

import {
  DASHBOARD_ROUTE_SURFACES,
  installDashboardTestState,
  readFixtureMetadata,
  waitForDashboardSurface,
} from "../helpers/runtime-dashboard";

test.describe("runtime-dashboard route accessibility", () => {
  test.beforeEach(async ({ page }) => {
    await installDashboardTestState(page);
  });

  for (const surface of DASHBOARD_ROUTE_SURFACES) {
    test(`${surface.name} passes axe`, async ({ page }) => {
      const metadata = readFixtureMetadata();

      await page.goto(surface.path(metadata));
      await waitForDashboardSurface(page, surface.ready);

      const results = await new AxeBuilder({ page }).analyze();
      expect(results.violations).toEqual([]);
    });
  }
});
