import { expect, test } from "@playwright/test";

import {
  applyRuntimeApiScenario,
  installDashboardTestState,
  readFixtureMetadata,
} from "../helpers/runtime-dashboard";

const INTERFACE_MODE_STORAGE_KEY = "polisyos.runtime.interface-mode";

test.describe("runtime-dashboard human-review calibration", () => {
  test.beforeEach(async ({ page }) => {
    await installDashboardTestState(page);
    await page.addInitScript((storageKey) => {
      window.localStorage.setItem(storageKey, "clerk");
    }, INTERFACE_MODE_STORAGE_KEY);
  });

  test("@smoke shows reviewer burden and unresolved disagreement without private notes", async ({
    page,
  }) => {
    const metadata = readFixtureMetadata();
    const jobId = "job_quality_review_fixture";
    const evidenceBundlePath =
      ".polisyos/canary_evidence/20260513T100000Z_job_quality_review_fixture";

    await applyRuntimeApiScenario(page, "ok", [
      {
        matcher: "/api/v1/control/runs/nl",
        method: "POST",
        body: {
          job_id: jobId,
          message: "Quality gate requires human review calibration.",
          meta: {
            generated_at: new Date().toISOString(),
            request_id: "playwright-quality-review-launch",
            source_kinds: ["control_job"],
          },
          run_id: null,
          status: "rejected",
        },
      },
      {
        matcher: /^\/api\/v1\/control\/jobs\/job_quality_review_fixture$/,
        method: "GET",
        body: {
          blocking_quality_failures: [
            {
              code: "reviewer_agreement_below_fail_threshold",
              evidence_ref:
                "quality_evidence/human_review_calibration_report.json",
              gate: "human_review_calibration",
              layer: "governance_review",
              message: "Reviewer agreement is below the production threshold.",
              next_action:
                "Escalate unresolved disagreements before production approval.",
              phase: "human_review",
            },
          ],
          capability_manifest_ref: null,
          effective_execution_profile: "production",
          error_message: null,
          execution_status: "completed",
          failure: null,
          finished_at: "2026-05-13T10:04:00Z",
          job_id: jobId,
          kind: "natural_language_run",
          meta: {
            generated_at: new Date().toISOString(),
            request_id: "playwright-quality-review-job",
            source_kinds: ["control_job"],
          },
          pipeline_id: null,
          progress: {
            details: {
              evidence_bundle_path: `${evidenceBundlePath}?api_key=fixture-secret`,
            },
            quality_scorecard: {
              approval_eligibility: {
                eligible: false,
                execution_status: "completed",
                missing_override: true,
                performance_status: "pass",
                quality_status: "fail",
                reasons: ["reviewer_agreement_below_fail_threshold"],
                requires_override: true,
                state: "quality_failed",
              },
              approval_state: "quality_failed",
              evidence_refs: {
                approval_packet: "quality_evidence/approval_packet.json",
                human_review_calibration_report:
                  "quality_evidence/human_review_calibration_report.json?token=fixture-secret",
              },
              human_review_calibration: {
                status: "fail",
                summary: {
                  agreement_rate: 0.58,
                  override_rate: 0.42,
                  unresolved_disagreement_count: 3,
                },
                reviewer_burden: {
                  total_minutes: 46,
                  reviewer_count: 4,
                },
                quality_signals: [
                  {
                    code: "reviewer_agreement_below_fail_threshold",
                    status: "fail",
                  },
                ],
                private_notes:
                  "raw reviewer note: do not show this in public exports",
              },
              override_evidence: {
                packet_ref: "quality_evidence/override_packet.json",
                status: "missing",
              },
            },
            status: "completed",
          },
          quality_gates: [
            {
              blocking: true,
              code: "reviewer_agreement_below_fail_threshold",
              evidence_ref:
                "quality_evidence/human_review_calibration_report.json",
              layer: "governance_review",
              message: "Reviewer agreement is below the production threshold.",
              name: "human_review_calibration",
              next_action:
                "Escalate unresolved disagreements before production approval.",
              phase: "human_review",
              status: "fail",
            },
          ],
          quality_evidence_bundle_path: `${evidenceBundlePath}?api_key=fixture-secret`,
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
      .fill("Review production approval calibration.");
    await page.getByRole("button", { name: "Analyze" }).click();

    const approvalPanel = page.getByRole("region", {
      name: "Control approval",
    });
    await expect(approvalPanel).toBeVisible();
    await expect(approvalPanel.getByText("human review fail")).toBeVisible();
    await expect(approvalPanel.getByText("agreement 58%")).toBeVisible();
    await expect(approvalPanel.getByText("override rate 42%")).toBeVisible();
    await expect(approvalPanel.getByText("reviewer burden 46m")).toBeVisible();
    await expect(
      approvalPanel.getByText("unresolved disagreements 3"),
    ).toBeVisible();
    await expect(
      approvalPanel.getByText(
        "Human review: quality_evidence/human_review_calibration_report.json",
      ),
    ).toBeVisible();
    await expect(
      page.getByText(/raw reviewer note|fixture-secret/),
    ).toHaveCount(0);
  });
});
