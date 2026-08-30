import { expect, test, type Locator, type Page } from "@playwright/test";

import type { AvailableConfidenceLedgerRiskSpendPacket } from "@polisyos/runtime-api-client";

import { installDashboardTestState } from "./helpers/runtime-dashboard";

const RISK_SPEND_PATH =
  "/api/v1/exports/governed-projections/confidence-ledger-risk-spend";
const TEMPORAL_OWNER_IDS = [
  "confidence-ledger-risk-spend-query-time-semantics",
  "confidence-ledger-risk-spend-time-semantics",
  "confidence-ledger-conditional-time-semantics",
] as const;
const SNAPSHOT_OPTIONS = {
  animations: "disabled",
  caret: "hide",
  maxDiffPixels: 100,
} as const;

async function openRealOwnerRiskSpend(page: Page) {
  await installDashboardTestState(page, { theme: "light" });
  const responsePromise = page.waitForResponse(
    (response) =>
      new URL(response.url()).pathname === RISK_SPEND_PATH &&
      response.status() === 200,
  );

  await page.goto("/runs/cycle-board");
  const response = await responsePromise;
  const rawResponse = await response.body();
  expect(rawResponse.byteLength).toBeGreaterThan(0);

  const packet =
    (await response.json()) as AvailableConfidenceLedgerRiskSpendPacket;
  const riskSpend = page.locator('[data-confidence-surface="risk-spend"]');
  await expect(riskSpend).toBeVisible();
  return { packet, riskSpend };
}

async function expectThreeTemporalOwners(
  page: Page,
  packet: AvailableConfidenceLedgerRiskSpendPacket,
) {
  await expect(
    page.locator('[data-testid^="confidence-ledger-"][data-testid$="time-semantics"]'),
  ).toHaveCount(3);

  for (const ownerId of TEMPORAL_OWNER_IDS) {
    const owner = page.getByTestId(ownerId);
    await expect(owner).toBeVisible();
    await expect(owner.getByTestId("time-semantics-payload-as-of")).toContainText(
      packet.as_of,
    );
    await expect(owner.getByTestId("time-semantics-observed-at")).toContainText(
      packet.freshness.observed_at,
    );
    await expect(owner.getByTestId("time-semantics-source-as-of")).toContainText(
      packet.freshness.source_as_of ?? "unknown",
    );
    await expect(owner.getByTestId("time-semantics-source-state")).toContainText(
      packet.freshness.state,
    );
    await expect(owner.getByTestId("time-semantics-epoch")).toContainText(
      "Epoch not established",
    );
    await expect(owner.getByTestId("time-semantics-validity")).toContainText(
      "not established",
    );
    await expect(owner.getByTestId("time-semantics-revalidation")).toContainText(
      "not required",
    );
  }
}

async function expectRealOwnerRiskSpend(
  page: Page,
  packet: AvailableConfidenceLedgerRiskSpendPacket,
  riskSpend: Locator,
) {
  expect(packet.availability).toBe("available");
  expect(packet.payload.total_spend.amount.numerator).toBe(0);
  expect(packet.payload.scope_total_risk_spend.spent.amount.numerator).toBe(0);
  expect(
    packet.payload.obligation_class_risk_spend.map(
      (row) => row.spent.amount.numerator,
    ),
  ).toEqual(Array<number>(15).fill(0));
  expect(packet.payload.coverage_assessment).toBe("open_world_unresolved");
  expect(packet.payload.instrument_definitions).toHaveLength(13);
  expect(packet.payload.obligation_class_risk_spend).toHaveLength(15);
  expect(packet.payload.positive_register.entries).toEqual([]);
  expect(packet.payload.positive_register.population_count).toBe(0);
  expect(packet.payload.instrument_instances.map((row) => row.certificate_role)).toEqual([
    "refusal",
    "acquisition",
    "acquisition",
  ]);

  const actualRows = riskSpend.locator(
    '[data-confidence-list="actual-rows"] > li',
  );
  await expect(actualRows).toHaveCount(3);
  await expect(actualRows.nth(0)).toContainText("refusal");
  await expect(actualRows.nth(1)).toContainText("acquisition");
  await expect(actualRows.nth(2)).toContainText("acquisition");
  await expect(
    riskSpend.locator('[data-confidence-list="instrument-definitions"] > li'),
  ).toHaveCount(13);
  await expect(
    riskSpend.locator('[data-confidence-list="class-spend"] > li'),
  ).toHaveCount(15);

  const positiveRegister = riskSpend.locator(
    '[data-confidence-section="positive-register"]',
  );
  await expect(positiveRegister).toContainText("0 issued");
  await expect(positiveRegister).toContainText("unappointed");
  await expect(positiveRegister).toContainText("not a load failure");
  await expect(
    page.locator('[data-confidence-surface="risk-spend-source-blocked"]'),
  ).toHaveCount(0);

  const conditionalChip = riskSpend
    .locator('button[data-confidence-trigger="conditional-delta"]')
    .first();
  const accessibleName = await conditionalChip.getAttribute("aria-label");
  expect(accessibleName).toContain(
    packet.payload.total_spend.declared_set_rider,
  );
  expect(accessibleName).toContain(packet.payload.total_spend.locality_rider);
  await expect(conditionalChip).toHaveAttribute("aria-expanded", "false");
  await conditionalChip.click();

  const dialog = page.getByRole("dialog", { name: /conditional envelope/iu });
  await expect(dialog).toBeVisible();
  await expect(conditionalChip).toHaveAttribute("aria-expanded", "true");
  await expect(dialog).toContainText(packet.payload.coverage_envelope.assessment);
  await expect(dialog).toContainText(
    packet.payload.coverage_envelope.declared_set_rider,
  );
  await expect(dialog).toContainText(packet.payload.coverage_envelope.locality_rider);

  await expectThreeTemporalOwners(page, packet);
  await page.evaluate(async () => document.fonts.ready);
  await expect(dialog).toHaveScreenshot(
    "ds17-real-owner-conditional-envelope.png",
    SNAPSHOT_OPTIONS,
  );
}

test(
  "DS17 confidence risk spend real-owner available open-world",
  async ({ page }) => {
    const { packet, riskSpend } = await openRealOwnerRiskSpend(page);
    await expectRealOwnerRiskSpend(page, packet, riskSpend);
  },
);
