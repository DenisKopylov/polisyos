import { expect, test } from "@playwright/test";

import {
  applyRuntimeApiScenario,
  installDashboardTestState,
  readFixtureMetadata,
  waitForDashboardSurface,
} from "../helpers/runtime-dashboard";

test.describe("runtime-dashboard run flow", () => {
  test.beforeEach(async ({ page }) => {
    await installDashboardTestState(page);
  });

  test("@smoke launches an NL run, monitors tabs, and opens the audit report plus deck", async ({
    page,
  }) => {
    const metadata = readFixtureMetadata();

    await applyRuntimeApiScenario(page, "ok", [
      {
        matcher: "/api/v1/control/runs/nl",
        method: "POST",
        body: {
          message: "Fixture launch accepted",
          meta: {
            generated_at: new Date().toISOString(),
            request_id: "playwright-launch-nl",
            source_kinds: ["core_run"],
          },
          run_id: metadata.core_run_id,
          status: "accepted",
        },
      },
      {
        matcher: /^\/api\/v1\/artifacts\/[^/]+\/content$/,
        method: "GET",
        body: ({ url }) => ({
          artifact: {
            artifact_id: decodeURIComponent(url.pathname.split("/").at(-2) ?? "artifact"),
            kind: "runtime.fixture_artifact",
            max_bytes: 262144,
            media_type: "application/json",
            mode: "json",
            preview: {
              fixture: "run-flow-artifact-content",
              run_id: metadata.core_run_id,
            },
            size_bytes: 76,
            truncated: false,
          },
          meta: {
            generated_at: new Date().toISOString(),
            request_id: "playwright-artifact-content",
            source_kinds: ["core_run"],
          },
        }),
      },
    ]);

    await page.goto("/compose");
    await waitForDashboardSurface(page, "composer");

    await page.getByTestId("composer-mode-nl").click();
    await page
      .getByTestId("composer-nl-brief")
      .fill(
        "Assess the macro outlook, show blockers first, and replan if evidence quality is low.",
      );

    await page
      .getByTestId(/llm-profile-/)
      .first()
      .click();
    await page
      .getByTestId("composer-nl-data-snapshot")
      .fill(metadata.data_snapshot_artifact_id);
    await page.getByTestId("composer-launch-nl").click();

    await expect(page).toHaveURL(/\/runs\/.+\/overview/, {
      timeout: 30_000,
    });
    await waitForDashboardSurface(page, "run-overview");

    const launchedRunId = /\/runs\/([^/]+)\//.exec(page.url())?.[1];
    if (!launchedRunId) {
      throw new Error(`Could not determine launched run id from ${page.url()}`);
    }

    await page.getByTestId("run-tab-link-governance").click();
    await waitForDashboardSurface(page, "run-governance");

    await page.getByTestId("run-tab-link-workflow").click();
    await waitForDashboardSurface(page, "run-workflow");

    await page.getByTestId("run-tab-link-agents").click();
    await waitForDashboardSurface(page, "run-agents");

    await page.getByTestId("run-tab-link-debug").click();
    await waitForDashboardSurface(page, "run-debug");

    await page.getByTestId("run-tab-link-artifacts").click();
    await waitForDashboardSurface(page, "run-artifacts");

    const artifactCard = page.getByTestId(/^artifact-card-/).first();
    await expect(artifactCard).toBeVisible();
    await artifactCard.click();

    const openArtifactLink = page
      .getByRole("link", { name: /Open artifact/i })
      .first();
    await expect(openArtifactLink).toBeVisible();
    await openArtifactLink.click();
    await waitForDashboardSurface(page, "artifact");

    await page.goBack();
    await waitForDashboardSurface(page, "run-artifacts");

    await page.goto(`/runs/${launchedRunId}/report`);
    await waitForDashboardSurface(page, "run-report");
    await expect(
      page.getByRole("button", { name: /Export JSON/i }),
    ).toBeVisible();

    const openDeckLink = page.getByRole("link", { name: /Open deck/i });
    await expect(openDeckLink).toBeVisible();
    await openDeckLink.evaluate((element) => {
      element.scrollIntoView({ block: "center", inline: "nearest" });
    });
    await openDeckLink.click();
    await expect(page).toHaveURL(new RegExp(`/runs/${launchedRunId}/deck`));
    await expect(page.getByTestId("run-deck-page")).toBeVisible();
    await expect(page.getByTestId("run-deck-slide-evidence")).toBeVisible();
  });

  test("supports blocked-run replan and explorer-driven comparison", async ({
    page,
  }) => {
    const metadata = readFixtureMetadata();

    await page.goto("/runs");
    await waitForDashboardSurface(page, "runs-list");
    await expect(
      page.getByRole("link", { name: metadata.core_run_id }),
    ).toBeVisible();

    await page.getByRole("link", { name: metadata.core_run_id }).click();

    await expect(page).toHaveURL(
      new RegExp(`/runs/${metadata.core_run_id}/overview`),
    );
    await waitForDashboardSurface(page, "run-overview");
    await expect(page.getByTestId("run-replan-link")).toBeVisible();

    await page.getByTestId("run-replan-link").click();
    await expect(page).toHaveURL(
      new RegExp(`/compose\\?fromRun=${metadata.core_run_id}`),
    );
    await waitForDashboardSurface(page, "composer");
    await expect(page.getByTestId("composer-operator-brief")).toBeVisible();

    await page.goto(
      `/runs/compare?base=${metadata.core_run_id}&target=${metadata.core_run_id_secondary}`,
    );
    await waitForDashboardSurface(page, "run-compare");
    await expect(page.locator("main table").first()).toBeVisible();
  });
});
