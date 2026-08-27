import { expect, test } from "@playwright/test";

import {
  installDashboardTestState,
  waitForDashboardSurface,
} from "./helpers/runtime-dashboard";

test("DS11 trust posture", async ({ page }) => {
  await installDashboardTestState(page);
  await page.goto("/trust");
  await waitForDashboardSurface(page, "trust");
  await expect(page.getByTestId("trust-posture-register")).toBeVisible();
  await expect(page).toHaveScreenshot("ds11-trust-posture.png", {
    animations: "disabled",
    caret: "hide",
    maxDiffPixels: 100,
  });
});
