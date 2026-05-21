import { expect, test } from "@playwright/test";

import {
  applyRuntimeApiScenario,
  installDashboardTestState,
  readFixtureMetadata,
} from "../helpers/runtime-dashboard";

const INTERFACE_MODE_STORAGE_KEY = "polisyos.runtime.interface-mode";

test.describe("runtime-dashboard control security quality gates", () => {
  test.beforeEach(async ({ page }) => {
    await installDashboardTestState(page);
    await page.addInitScript((storageKey) => {
      window.localStorage.setItem(storageKey, "clerk");
      (window as Window & { __POLICYOS_XSS__?: boolean }).__POLICYOS_XSS__ =
        false;
    }, INTERFACE_MODE_STORAGE_KEY);
  });

  test("@smoke renders security blockers as escaped operator text", async ({
    page,
  }) => {
    const metadata = readFixtureMetadata();
    const jobId = "job_security_route_fixture";
    const unsafeMessage =
      '<img src=x onerror="window.__POLICYOS_XSS__=true">';
    const nextAction =
      "Block dashboard rendering and inspect security_assurance_report before approval.";

    await applyRuntimeApiScenario(page, "ok", [
      {
        matcher: "/api/v1/control/runs/nl",
        method: "POST",
        body: {
          job_id: jobId,
          message: "Security gate failed after deterministic abuse checks",
          meta: {
            generated_at: new Date().toISOString(),
            request_id: "playwright-security-launch",
            source_kinds: ["control_job"],
          },
          run_id: null,
          status: "rejected",
        },
      },
      {
        matcher: /^\/api\/v1\/control\/jobs\/job_security_route_fixture$/,
        method: "GET",
        body: {
          blocking_quality_failures: [
            {
              code: "unsafe_artifact_rendering_detected",
              evidence_ref:
                "quality_evidence/security_assurance_report.json#/issues/0?token=fixture-secret",
              gate: "security_artifact_abuse_gate",
              layer: "security",
              message: unsafeMessage,
              next_action: nextAction,
              phase: "artifact.unsafe_rendering",
            },
          ],
          capability_manifest_ref: null,
          effective_execution_profile: "production",
          error_message: null,
          execution_status: "completed",
          failure: null,
          finished_at: "2026-05-13T10:02:00Z",
          job_id: jobId,
          kind: "natural_language_run",
          meta: {
            generated_at: new Date().toISOString(),
            request_id: "playwright-security-job",
            source_kinds: ["control_job"],
          },
          pipeline_id: null,
          progress: {
            details: {
              security_assurance_report_ref:
                "quality_evidence/security_assurance_report.json?api_key=fixture-secret",
            },
            quality_scorecard: {
              approval_eligibility: {
                eligible: false,
                execution_status: "completed",
                missing_override: true,
                performance_status: "pass",
                quality_status: "fail",
                reasons: ["unsafe_artifact_rendering_detected"],
                requires_override: true,
                state: "quality_failed",
              },
              approval_state: "quality_failed",
              evidence_refs: {
                quality_scorecard:
                  "quality_evidence/quality_scorecard.json?token=fixture-secret",
                security_assurance_report:
                  "quality_evidence/security_assurance_report.json?token=fixture-secret",
              },
            },
            status: "completed",
          },
          quality_gates: [
            {
              blocking: true,
              code: "unsafe_artifact_rendering_detected",
              evidence_ref:
                "quality_evidence/security_assurance_report.json#/issues/0?token=fixture-secret",
              layer: "security",
              message: unsafeMessage,
              name: "security_artifact_abuse_gate",
              next_action: nextAction,
              phase: "artifact.unsafe_rendering",
              status: "fail",
            },
          ],
          quality_evidence_bundle_path:
            ".polisyos/canary_evidence/security_fixture?api_key=fixture-secret",
          quality_scorecard_ref:
            "quality_evidence/quality_scorecard.json?token=fixture-secret",
          quality_status: "fail",
          requested_execution_profile: "production",
          run_id: metadata.core_run_id,
          started_at: "2026-05-13T10:00:05Z",
          state: "completed",
          submitted_at: "2026-05-13T10:00:00Z",
        },
      },
    ]);

    await page.goto("/");
    await expect(
      page.getByText("What policy would you like to analyze?"),
    ).toBeVisible();

    await page
      .getByPlaceholder("Ask a policy question...")
      .fill("Run deterministic security quality checks.");
    await page.getByRole("button", { name: "Analyze" }).click();

    const qualityPanel = page.getByRole("region", { name: "Control quality" });
    const approvalPanel = page.getByRole("region", {
      name: "Control approval",
    });
    await expect(qualityPanel).toBeVisible();
    await expect(approvalPanel).toBeVisible();
    await expect(qualityPanel.getByText("security", { exact: true })).toBeVisible();
    await expect(
      qualityPanel.getByText("unsafe_artifact_rendering_detected"),
    ).toBeVisible();
    await expect(qualityPanel.getByText(unsafeMessage)).toBeVisible();
    await expect(qualityPanel.getByText(nextAction)).toBeVisible();
    await expect(
      qualityPanel.getByText(
        "Evidence: quality_evidence/security_assurance_report.json",
      ),
    ).toBeVisible();
    await expect(page.locator('img[src="x"]')).toHaveCount(0);
    await expect(page.locator("script", { hasText: "POLICYOS_XSS" })).toHaveCount(
      0,
    );
    await expect
      .poll(() =>
        page.evaluate(
          () => (window as Window & { __POLICYOS_XSS__?: boolean }).__POLICYOS_XSS__,
        ),
      )
      .toBe(false);
    await expect(page.getByText(/fixture-secret/)).toHaveCount(0);
  });
});
