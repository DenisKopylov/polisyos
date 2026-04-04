import { expect, test } from "@playwright/test";

const FIXTURE_RUN_ID = "R_core_api_001";
const FIXTURE_PROMOTION_ID = "promotion_fixture_001";
const LIVE_STORAGE_KEY = "polisyos.runtime.disableLive";
const THEME_STORAGE_KEY = "polisyos.runtime.theme";

test.describe("runtime-dashboard visual baselines", () => {
  test.use({
    viewport: { width: 1440, height: 1200 },
  });

  test.beforeEach(async ({ page }) => {
    await page.addInitScript((storageKey) => {
      window.localStorage.setItem(storageKey, "true");
    }, LIVE_STORAGE_KEY);
  });

  test("command center shell", async ({ page }) => {
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: "Command Center" }),
    ).toBeVisible();
    await expect(page.locator(".workspace-frame").first()).toHaveScreenshot(
      "command-center-shell.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("scenario composer dark theme", async ({ page }) => {
    await page.addInitScript((storageKey) => {
      window.localStorage.setItem(storageKey, "dark");
    }, THEME_STORAGE_KEY);
    await page.goto("/compose");
    await expect(
      page.getByRole("heading", { name: "Scenario Composer" }),
    ).toBeVisible();
    await expect(page.locator(".workspace-frame").first()).toHaveScreenshot(
      "scenario-composer-dark.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });

  test("run detail overview", async ({ page }) => {
    await page.goto(`/runs/${FIXTURE_RUN_ID}/overview`);
    await expect(page.getByTestId("run-detail-page")).toBeVisible();
    await expect(
      page.getByTestId("run-detail-page").locator("aside").first(),
    ).toHaveScreenshot("run-detail-summary.png", {
      animations: "disabled",
      caret: "hide",
    });
  });

  test("evidence promotion focus", async ({ page }) => {
    await page.goto(
      `/evidence?runId=${FIXTURE_RUN_ID}&focus=promotion&promotionId=${FIXTURE_PROMOTION_ID}`,
    );
    await expect(
      page.getByTestId(`promotion-approve-${FIXTURE_PROMOTION_ID}`),
    ).toBeVisible();
    await expect(page.locator(".workspace-frame").first()).toHaveScreenshot(
      "evidence-promotion-focus.png",
      {
        animations: "disabled",
        caret: "hide",
      },
    );
  });
});
