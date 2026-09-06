import { expect, test, type Locator, type Page } from "@playwright/test";

import {
  installDashboardTestState,
  readFixtureMetadata,
  waitForDashboardSurface,
} from "../../../e2e/helpers/runtime-dashboard";
import { openCapabilityDiscovery } from "../../../e2e/helpers/capabilityDiscovery";

declare global {
  interface Window {
    __A11Y_PRINTS__?: number;
  }
}

async function tabUntilFocused(
  page: Page,
  locator: Locator,
  counter: { count: number },
  maxTabs: number,
) {
  await expect(locator).toBeVisible();

  for (let index = 0; index < maxTabs; index += 1) {
    await page.keyboard.press("Tab");
    counter.count += 1;

    if (
      await locator.evaluate((element) => element === document.activeElement)
    ) {
      return;
    }
  }

  throw new Error(`Failed to focus locator within ${maxTabs} tab stops.`);
}

async function expectMainFocused(page: Page) {
  await expect(page.locator("#main-content")).toBeFocused();
}

test.describe("runtime-dashboard keyboard-only journeys", () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      window.__A11Y_PRINTS__ = 0;
      window.print = function capturePrint() {
        window.__A11Y_PRINTS__ = Number(window.__A11Y_PRINTS__ ?? 0) + 1;
      };
    });
    await installDashboardTestState(page);
  });

  test("opens a run and downloads the decision packet with keyboard only in at most 20 tab stops", async ({
    page,
  }) => {
    const maxTabStops = 20;
    const tabCounter = { count: 0 };

    await page.goto("/runs");
    await waitForDashboardSurface(page, "runs-list");
    await expectMainFocused(page);

    const skipExplorerButton = page.getByRole("button", {
      name: /skip to run explorer/i,
    });
    await tabUntilFocused(page, skipExplorerButton, tabCounter, 2);
    await page.keyboard.press("Enter");

    let activeRow = page.locator("[data-run-row-id]").first();
    await expect(activeRow).toBeFocused();
    let activeRunId = await activeRow.getAttribute("data-run-row-id");
    if (!activeRunId) {
      throw new Error("The focused run row must expose its navigation target.");
    }
    const targetRunId = readFixtureMetadata().core_run_id;
    const rowIds = await page
      .locator("[data-run-row-id]")
      .evaluateAll((rows) =>
        rows.map((row) => row.getAttribute("data-run-row-id")),
      );
    const activeIndex = rowIds.indexOf(activeRunId);
    const targetIndex = rowIds.indexOf(targetRunId);
    if (activeIndex < 0 || targetIndex < 0) {
      throw new Error("The keyboard journey requires the bound core run row.");
    }
    const navigationKey = targetIndex > activeIndex ? "ArrowDown" : "ArrowUp";
    for (
      let index = 0;
      index < Math.abs(targetIndex - activeIndex);
      index += 1
    ) {
      await page.keyboard.press(navigationKey);
    }
    activeRow = page.locator(`[data-run-row-id="${targetRunId}"]`);
    await expect(activeRow).toBeFocused();
    activeRunId = targetRunId;
    await page.keyboard.press("Enter");

    await expect(page).toHaveURL(new RegExp(`/runs/${activeRunId}/overview`));
    await waitForDashboardSurface(page, "run-overview");
    await expectMainFocused(page);

    const readingViewLink = page.getByTestId("run-reading-view-link");
    await tabUntilFocused(
      page,
      readingViewLink,
      tabCounter,
      maxTabStops - tabCounter.count,
    );
    await page.keyboard.press("Enter");

    await expect(page).toHaveURL(/\/artifacts\/[^?]+\?[^#]*view=reading/);
    await waitForDashboardSurface(page, "artifact");

    const printPacketButton = page.getByRole("button", {
      name: /print\s*\/\s*save pdf/i,
    });
    await expect(printPacketButton).toBeFocused();
    await page.keyboard.press("Enter");

    await expect
      .poll(() => page.evaluate(() => window.__A11Y_PRINTS__ ?? 0))
      .toBeGreaterThanOrEqual(1);

    expect(tabCounter.count).toBeLessThanOrEqual(maxTabStops);
  });

  test("DS10 capability discovery supports keyboard search and MACHINE download", async ({
    page,
  }) => {
    const panel = await openCapabilityDiscovery(page, "executable");
    const input = panel.getByLabel("Search capabilities");
    const tabCounter = { count: 0 };
    await tabUntilFocused(page, input, tabCounter, 80);
    await page.keyboard.press("ControlOrMeta+A");
    await page.keyboard.type("generated legal norm");
    await expect(panel.getByRole("status")).toContainText(
      "Candidate search returned 1 results",
    );

    await page.keyboard.press("Shift+Tab");
    const downloadButton = panel.getByRole("button", {
      name: "Download MACHINE JSON",
    });
    await expect(downloadButton).toBeFocused();
    const downloadPromise = page.waitForEvent("download");
    await page.keyboard.press("Enter");
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe("capability-discovery.json");
  });
});
