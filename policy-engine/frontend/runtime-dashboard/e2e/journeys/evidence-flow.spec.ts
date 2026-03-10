import { expect, test } from "@playwright/test";

import {
  installDashboardTestState,
  readFixtureMetadata,
  waitForDashboardSurface,
} from "../helpers/runtime-dashboard";

test.describe("runtime-dashboard evidence flow", () => {
  test.beforeEach(async ({ page }) => {
    await installDashboardTestState(page);
  });

  test("@smoke reviews evidence context, opens artifact lineage, and records promotion decisions", async ({
    page,
  }) => {
    const metadata = readFixtureMetadata();

    await page.goto(
      `/evidence?runId=${metadata.core_run_id}&focus=promotion&promotionId=${metadata.promotion_candidate_id}`,
    );
    await waitForDashboardSurface(page, "evidence");

    const needButton = page.getByTestId(/^evidence-need-/).first();
    await expect(needButton).toBeVisible();
    await needButton.click();
    await expect(page).toHaveURL(/focus=need/);

    const planButton = page.getByTestId(/^evidence-plan-/).first();
    await expect(planButton).toBeVisible();
    await planButton.click();
    await expect(page).toHaveURL(/focus=plan/);

    const promotionButton = page.getByTestId(
      `evidence-promotion-${metadata.promotion_candidate_id}`,
    );
    await expect(promotionButton).toBeVisible();
    await promotionButton.click();
    await expect(page).toHaveURL(/focus=promotion/);

    const approveButton = page.getByTestId(
      `promotion-approve-${metadata.promotion_candidate_id}`,
    );
    const rejectButton = page.getByTestId(
      `promotion-reject-${metadata.promotion_candidate_id}`,
    );

    await approveButton.click();
    await expect(page.getByText(/status=approved/i)).toBeVisible();

    await rejectButton.click();
    await expect(page.getByText(/status=rejected/i)).toBeVisible();

    await page.getByTestId(/^evidence-artifact-/).first().click();
    await expect(page).toHaveURL(/focus=artifact/);

    await page.getByRole("link", { name: /Open artifact/i }).first().click();
    await waitForDashboardSurface(page, "artifact");

    await page.getByRole("button", { name: /Lineage/i }).click();
    await expect(page.getByText(/lineage/i).first()).toBeVisible();
  });
});
