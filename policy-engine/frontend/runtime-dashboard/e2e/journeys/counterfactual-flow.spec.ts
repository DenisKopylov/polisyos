import { expect, test, type Page } from "@playwright/test";

import {
  applyRuntimeApiScenario,
  installDashboardTestState,
  readFixtureMetadata,
  type RuntimeFixtureMetadata,
  waitForDashboardSurface,
} from "../helpers/runtime-dashboard";

const SCENARIO_ID = "scn_playwright_rate_cut";
const NOW = "2026-04-15T12:00:00.000Z";

test.describe("runtime-dashboard counterfactual flow", () => {
  test.beforeEach(async ({ page }) => {
    await installDashboardTestState(page);
  });

  test("reopens the selected scenario, mode, metrics and URL state", async ({
    browser,
    page,
  }) => {
    const metadata = readFixtureMetadata();
    await applyScenarioOverrides(page, metadata);

    await page.goto(`/runs/${metadata.core_run_id}/overview`);
    await waitForDashboardSurface(page, "run-overview");

    const rail = page.getByTestId("counterfactual-shell-rail");
    await expect(rail).toBeVisible();
    await rail.getByRole("radio", { name: "Actual + Scenario" }).click();

    await expect(page).toHaveURL(new RegExp(`scenario_id=${SCENARIO_ID}`));
    await expect(page).toHaveURL(/cf_mode=actual_vs_scenario/);
    await expect(
      page.getByLabel(/Employment delta: actual and scenario values/),
    ).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Scenario manifest" }),
    ).toBeVisible();

    const sharedUrl = page.url();
    const reopened = await browser.newPage();
    await installDashboardTestState(reopened);
    await applyScenarioOverrides(reopened, metadata);
    await reopened.goto(sharedUrl);
    await waitForDashboardSurface(reopened, "run-overview");

    const reopenedRail = reopened.getByTestId("counterfactual-shell-rail");
    await expect(
      reopenedRail.getByRole("radio", { name: "Actual + Scenario" }),
    ).toHaveAttribute("aria-checked", "true");
    await expect(reopened).toHaveURL(new RegExp(`scenario_id=${SCENARIO_ID}`));
    await expect(
      reopened.getByLabel(/Employment delta: actual and scenario values/),
    ).toBeVisible();
    await reopened.close();
  });
});

async function applyScenarioOverrides(
  page: Page,
  metadata: RuntimeFixtureMetadata,
) {
  const scenario = buildScenario(metadata);
  await applyRuntimeApiScenario(page, "ok", [
    {
      matcher: `/api/v1/runs/${metadata.core_run_id}/scenarios`,
      method: "GET",
      body: {
        meta: apiMeta("scenario-list"),
        run_id: metadata.core_run_id,
        temporal_scope: scenario.temporal_scope,
        scenarios: [scenario],
      },
    },
    {
      matcher: `/api/v1/runs/${metadata.core_run_id}/metrics`,
      method: "GET",
      body: {
        meta: apiMeta("counterfactual-metrics"),
        run_id: metadata.core_run_id,
        temporal_scope: {
          ...scenario.temporal_scope,
          scenario_id: SCENARIO_ID,
        },
        scenario,
        metrics: {
          employment_rate_delta: {
            metric_id: "employment_rate_delta",
            label: "Employment delta",
            actual: quantity(0.23, "employment_rate_delta", "Actual effect"),
            counterfactual: scenarioQuantity(
              0.29,
              "employment_rate_delta",
              "Scenario effect",
            ),
            delta: scenarioQuantity(
              0.06,
              "employment_rate_delta_delta",
              "Counterfactual delta",
            ),
            scenario_ref: {
              id: SCENARIO_ID,
              status: "computed",
              baseline_run_id: metadata.core_run_id,
              temporal_scope: scenario.temporal_scope,
              lineage: lineage("scenario-ref"),
              assumption_ids: ["asm_no_external_shock"],
              manifest_hash: "sha256:playwright",
            },
            assumption_ids: ["asm_no_external_shock"],
          },
        },
      },
    },
  ]);
}

function buildScenario(metadata: RuntimeFixtureMetadata) {
  return {
    id: SCENARIO_ID,
    baseline_run_id: metadata.core_run_id,
    status: "computed",
    temporal_scope: { valid_at: NOW, tx_at: NOW, scenario_id: SCENARIO_ID },
    policy_question: "Rate cut",
    author: "Playwright",
    affected_population: "national_workforce",
    temporal_window: { earliest: NOW, latest: NOW },
    model_family: "fixture_counterfactual",
    model_version: "e2e",
    model_lineage: lineage("model"),
    baseline_lineage: lineage("baseline"),
    baseline_hash: "sha256:baseline",
    computed_at: NOW,
    validity_window: { earliest: NOW, latest: NOW },
    known_limitations: ["Fixture scenario for URL replay."],
    stale_reasons: [],
    interventions: [
      {
        field: "policy_rate",
        operator: "set",
        value: scenarioQuantity(0.25, "policy_rate", "Policy rate"),
        baseline_value: quantity(0.5, "policy_rate", "Policy rate"),
        constraint_ids: ["rate_bound"],
      },
    ],
    assumptions: [
      {
        id: "asm_no_external_shock",
        label: "No external demand shock",
        status: "operator_assumption",
        lineage: lineage("assumption"),
        description: "The scenario keeps external demand stable.",
      },
    ],
    constraints: [
      {
        id: "rate_bound",
        label: "Rate bound",
        field: "policy_rate",
        severity: "warning",
        operator: "range",
        value: scenarioQuantity(0.25, "policy_rate", "Policy rate"),
        message: "Keep the intervention inside the supported fixture range.",
      },
    ],
  };
}

function quantity(point: number, metricId: string, label: string) {
  return {
    point,
    unit: { code: "1", system: "ucum", display: "ratio" },
    metric_id: metricId,
    lineage: lineage(metricId),
    uncertainty: {
      ci_95: [point - 0.02, point + 0.02],
      method: "fixture",
      identifiability: "estimated",
      disputed: false,
    },
    time: { valid_at: NOW, tx_at: NOW },
    quantity_class: "decision",
    label,
  };
}

function scenarioQuantity(point: number, metricId: string, label: string) {
  return {
    ...quantity(point, metricId, label),
    lineage: lineage(`scenario-${metricId}`),
    time: { valid_at: NOW, tx_at: NOW, scenario_id: SCENARIO_ID },
  };
}

function lineage(id: string) {
  return {
    id: `lin_${id}`,
    hash: `sha256:${id}`,
    status: "verified",
    freshness: "current",
    summary: { source: "Playwright fixture", method: "Counterfactual" },
  };
}

function apiMeta(requestId: string) {
  return {
    request_id: `playwright-${requestId}`,
    generated_at: NOW,
    source_kinds: ["core_run"],
  };
}
