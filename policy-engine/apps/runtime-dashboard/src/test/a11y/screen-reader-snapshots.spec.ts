import { expect, test } from "@playwright/test";

import {
  installDashboardTestState,
  readFixtureMetadata,
  waitForDashboardSurface,
} from "../../../e2e/helpers/runtime-dashboard";
import { openCapabilityDiscovery } from "../../../e2e/helpers/capabilityDiscovery";

const INTERACTIVE_ROLE_PATTERN =
  /\b(button|checkbox|combobox|link|menuitem|radio|slider|switch|tab|textbox)\b/;

function collectNamelessInteractiveLines(snapshot: string) {
  return snapshot
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => INTERACTIVE_ROLE_PATTERN.test(line))
    .filter((line) => !line.includes('"'));
}

test.describe("runtime-dashboard screen reader snapshots", () => {
  test.beforeEach(async ({ page }) => {
    await installDashboardTestState(page);
  });

  test("runs list exposes named landmarks and actions", async ({ page }) => {
    await page.goto("/runs");
    await waitForDashboardSurface(page, "runs-list");

    const snapshot = await page.locator("body").ariaSnapshot();

    expect(collectNamelessInteractiveLines(snapshot)).toEqual([]);
    expect(snapshot).toContain("main");
    expect(snapshot).toContain('link "Open run"');
  });

  test("run report exposes named export actions and timeline content", async ({
    page,
  }) => {
    const metadata = readFixtureMetadata();

    await page.goto(`/runs/${metadata.run_paper_bound_run_id}/report`);
    await waitForDashboardSurface(page, "run-report");

    const snapshot = await page.locator("body").ariaSnapshot();

    expect(collectNamelessInteractiveLines(snapshot)).toEqual([]);
    expect(snapshot).toContain('button "Export MACHINE packet"');
    expect(snapshot).toContain("heading");
  });

  test("DS10 capability discovery announces candidate-grade incomplete frontier truth", async ({
    page,
  }) => {
    const panel = await openCapabilityDiscovery(page, "incomplete-no-hit");
    const snapshot = await panel.ariaSnapshot();

    expect(collectNamelessInteractiveLines(snapshot)).toEqual([]);
    expect(snapshot).toContain('textbox "Search capabilities"');
    expect(snapshot).toContain("Candidate search returned 0 results");
    expect(snapshot).toContain("recall_unmeasured");
    expect(snapshot).toContain("budget_cutoff");
    expect(snapshot).toContain("legal_norm:index_stale");
    expect(snapshot).toContain("case:producer_missing");
    expect(snapshot).toContain("No capability matched this search.");
    expect(snapshot).toContain("rejected: legal-norm:rejected-near-match");
  });
});
