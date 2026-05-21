import { expect, test } from "@playwright/test";

import {
  applyRuntimeApiScenario,
  installDashboardTestState,
  readFixtureMetadata,
} from "../helpers/runtime-dashboard";

const INTERFACE_MODE_STORAGE_KEY = "polisyos.runtime.interface-mode";

test.describe("runtime-dashboard control resilience degradation", () => {
  test.beforeEach(async ({ page }) => {
    await installDashboardTestState(page);
    await page.addInitScript((storageKey) => {
      window.localStorage.setItem(storageKey, "clerk");
    }, INTERFACE_MODE_STORAGE_KEY);
  });

  test("@smoke keeps performance budget warnings separate from quality and operational failures", async ({
    page,
  }) => {
    const metadata = readFixtureMetadata();
    const jobId = "job_resilience_route_fixture";
    const nextAction =
      "Inspect dashboard smoke trace and disable noncritical panels before approval.";

    await applyRuntimeApiScenario(page, "ok", [
      {
        matcher: "/api/v1/control/runs/nl",
        method: "POST",
        body: {
          job_id: jobId,
          message: "Performance budget warning requires operator review",
          meta: {
            generated_at: new Date().toISOString(),
            request_id: "playwright-resilience-launch",
            source_kinds: ["control_job"],
          },
          run_id: null,
          status: "accepted",
        },
      },
      {
        matcher: /^\/api\/v1\/control\/jobs\/job_resilience_route_fixture$/,
        method: "GET",
        body: {
          blocking_quality_failures: [],
          capability_manifest_ref: null,
          effective_execution_profile: "production",
          error_message: null,
          execution_status: "completed",
          failure: null,
          finished_at: "2026-05-13T09:03:00Z",
          job_id: jobId,
          kind: "natural_language_run",
          meta: {
            generated_at: new Date().toISOString(),
            request_id: "playwright-resilience-job",
            source_kinds: ["control_job"],
          },
          pipeline_id: null,
          progress: {
            quality_scorecard: {
              approval_eligibility: {
                eligible: false,
                execution_status: "completed",
                missing_override: true,
                performance_status: "warn",
                quality_status: "pass",
                reasons: ["performance_budget_warn"],
                requires_override: true,
                state: "override_required",
              },
              approval_state: "override_required",
              evidence_refs: {
                resilience_report: "quality_evidence/runtime_resilience_matrix.json",
              },
              performance_budget_issues: [
                {
                  budget_ms: 3000,
                  classification: "performance_warning",
                  layer: "dashboard",
                  next_action: nextAction,
                  observed_value_ms: 4200,
                  phase: "dashboard.first_meaningful_route_render",
                  status: "over_budget",
                },
              ],
              performance_status: "warn",
              quality_status: "pass",
            },
            status: "completed",
          },
          quality_gates: [],
          quality_evidence_bundle_path: null,
          quality_scorecard_ref: "quality_evidence/quality_scorecard.json",
          quality_status: "pass",
          requested_execution_profile: "production",
          run_id: metadata.core_run_id,
          started_at: "2026-05-13T09:00:05Z",
          state: "completed",
          submitted_at: "2026-05-13T09:00:00Z",
        },
      },
    ]);

    await page.goto("/");
    await expect(
      page.getByText("What policy would you like to analyze?"),
    ).toBeVisible();

    await page
      .getByPlaceholder("Ask a policy question...")
      .fill("Run resilience degraded dashboard rendering check.");
    await page.getByRole("button", { name: "Analyze" }).click();

    const approvalPanel = page.getByRole("region", {
      name: "Control approval",
    });
    await expect(approvalPanel).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Control failure" }),
    ).toHaveCount(0);
    await expect(
      page.getByRole("region", { name: "Control quality" }),
    ).toHaveCount(0);
    await expect(approvalPanel.getByText("performance_budget_warn")).toBeVisible();
    await expect(approvalPanel.getByText("Performance", { exact: true })).toBeVisible();
    await expect(approvalPanel.getByText("warn", { exact: true })).toBeVisible();
    await expect(
      approvalPanel.getByText("dashboard.first_meaningful_route_render"),
    ).toBeVisible();
    await expect(
      approvalPanel.getByText("dashboard / performance_warning"),
    ).toBeVisible();
    await expect(
      approvalPanel.getByText("observed 4200ms / budget 3000ms"),
    ).toBeVisible();
    await expect(approvalPanel.getByText(nextAction)).toBeVisible();
  });
});
