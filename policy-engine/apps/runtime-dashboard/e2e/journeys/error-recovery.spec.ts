import { expect, test, type Page } from "@playwright/test";

import {
  applyRuntimeApiScenario,
  clearRuntimeApiScenarios,
  installDashboardTestState,
  readFixtureMetadata,
  waitForDashboardSurface,
} from "../helpers/runtime-dashboard";

async function prepareNlLaunch(page: Page) {
  const metadata = readFixtureMetadata();

  await page.goto("/compose");
  await waitForDashboardSurface(page, "composer");
  await page.getByTestId("composer-mode-nl").click();
  await page
    .getByTestId("composer-nl-brief")
    .fill("Trigger runtime recovery flow for dashboard coverage.");
  await page
    .getByTestId(/llm-profile-/)
    .first()
    .click();
  await page
    .getByTestId("composer-nl-data-snapshot")
    .fill(metadata.data_snapshot_artifact_id);

  return metadata;
}

test.describe("runtime-dashboard error recovery", () => {
  test.beforeEach(async ({ page }) => {
    await installDashboardTestState(page);
  });

  test("redirects to login when runtime requests return 401", async ({
    page,
  }) => {
    await prepareNlLaunch(page);
    await applyRuntimeApiScenario(page, "401");

    await page.getByTestId("composer-launch-nl").click();
    await waitForDashboardSurface(page, "login");
    await expect(page).toHaveURL(/\/login\?next=%2Fcompose/);
  });

  test("surfaces API outages with a runtime incident banner and recovers after reload", async ({
    page,
  }) => {
    const metadata = await prepareNlLaunch(page);
    await applyRuntimeApiScenario(page, "5xx");

    await page.getByTestId("composer-launch-nl").click();
    await expect(page.getByTestId("runtime-banner")).toBeVisible();
    await waitForDashboardSurface(page, "composer");

    await clearRuntimeApiScenarios(page);
    await applyRuntimeApiScenario(page, "ok", [
      {
        matcher: "/api/v1/control/runs/nl",
        method: "POST",
        body: {
          message: "Fixture launch accepted",
          meta: {
            generated_at: new Date().toISOString(),
            request_id: "playwright-launch-recovery",
            source_kinds: ["core_run"],
          },
          run_id: metadata.core_run_id,
          status: "accepted",
        },
      },
    ]);

    await page.getByTestId("composer-launch-nl").click();
    await expect(page).toHaveURL(
      new RegExp(`/runs/${metadata.core_run_id}/overview`),
    );
    await waitForDashboardSurface(page, "run-overview");
  });

  test("keeps empty workspace responses stable on routes that depend on catalog data", async ({
    page,
  }) => {
    await applyRuntimeApiScenario(page, "empty");

    await page.goto("/runs");
    await waitForDashboardSurface(page, "runs-list");
    await expect(page.getByText(/No runs matched/i)).toBeVisible();

    await page.goto("/evidence");
    await waitForDashboardSurface(page, "evidence");
    await expect(
      page.getByText(/No promotion candidates/i).first(),
    ).toBeVisible();

    await page.goto("/knowledge");
    await waitForDashboardSurface(page, "knowledge");
    await expect(page.getByText(/No knowledge graph found/i)).toBeVisible();
  });

  test("treats network failures as runtime incidents without leaving the shell", async ({
    page,
  }) => {
    await prepareNlLaunch(page);
    await applyRuntimeApiScenario(page, "network-fail");

    await page.getByTestId("composer-launch-nl").click();
    await expect(page.getByTestId("app-shell")).toBeVisible();
    await expect(page.getByTestId("runtime-banner")).toBeVisible();
  });
});
