import { expect, test } from "@playwright/test";

import {
  applyRuntimeApiScenario,
  installDashboardTestState,
  readFixtureMetadata,
} from "../helpers/runtime-dashboard";

const INTERFACE_MODE_STORAGE_KEY = "polisyos.runtime.interface-mode";

test.describe("runtime-dashboard control quality failures", () => {
  test.beforeEach(async ({ page }) => {
    await installDashboardTestState(page);
    await page.addInitScript((storageKey) => {
      window.localStorage.setItem(storageKey, "clerk");
    }, INTERFACE_MODE_STORAGE_KEY);
  });

  test("@smoke renders a completed quality-failed control job without an operational failure", async ({
    page,
  }) => {
    const metadata = readFixtureMetadata();
    const jobId = "job_quality_route_fixture";
    const qualityMessage =
      "LLM model variants produced materially different major recommendation actions.";
    const nextAction =
      "Run policy adjudication across model variants and persist the chosen recommendation with disagreement rationale.";
    const nextDiagnosticCommand =
      "uv run pytest tests/unit/runtime/http/test_control_api.py -q";
    const evidenceBundlePath =
      ".polisyos/canary_evidence/20260412T090300Z_job_quality_route_fixture";

    await applyRuntimeApiScenario(page, "ok", [
      {
        matcher: "/api/v1/control/runs/nl",
        method: "POST",
        body: {
          job_id: jobId,
          message: "Quality gate failed after execution",
          meta: {
            generated_at: new Date().toISOString(),
            request_id: "playwright-quality-launch",
            source_kinds: ["control_job"],
          },
          run_id: null,
          status: "rejected",
        },
      },
      {
        matcher: /^\/api\/v1\/control\/jobs\/job_quality_route_fixture$/,
        method: "GET",
        body: {
          blocking_quality_failures: [
            {
              code: "multi_model_policy_disagreement",
              evidence_ref: "quality_evidence/policy_grounding_matrix.json",
              gate: "policy_grounding_matrix_present",
              layer: "scientist_policy_artifacts",
              message: qualityMessage,
              next_action: nextAction,
              phase: "policy_grounding",
            },
          ],
          capability_manifest_ref: null,
          effective_execution_profile: "production",
          error_message: null,
          execution_status: "completed",
          failure: null,
          finished_at: "2026-04-12T09:03:00Z",
          job_id: jobId,
          kind: "natural_language_run",
          meta: {
            generated_at: new Date().toISOString(),
            request_id: "playwright-quality-job",
            source_kinds: ["control_job"],
          },
          pipeline_id: null,
          approval_projection: {
            eligible: false,
            reasons: ["multi_model_policy_disagreement"],
            source_surface: "runtime.control_job",
            authority_level: "projection_only",
            state: "quality_failed",
          },
          authoritative_scorecard_ref:
            "quality_evidence/quality_scorecard.json?token=fixture-secret",
          projection_source: {
            authority_level: "projection_only",
            projection_policy: "projection_only",
            source_detail: "control_store_progress",
            source_surface: "runtime.control_job",
          },
          progress: {
            details: {
              evidence_bundle_path: `${evidenceBundlePath}?api_key=fixture-secret`,
            },
            quality_scorecard: {
              approval_eligibility: {
                eligible: true,
                execution_status: "completed",
                missing_override: true,
                performance_status: "pass",
                quality_status: "pass",
                reasons: [],
                requires_override: true,
                state: "approval_ready",
              },
              approval_ready: true,
              approval_state: "approval_ready",
              evidence_refs: {
                approval_packet:
                  "quality_evidence/approval_packet.json?token=fixture-secret",
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
              code: "multi_model_policy_disagreement",
              evidence_ref: "quality_evidence/policy_grounding_matrix.json",
              layer: "scientist_policy_artifacts",
              message: qualityMessage,
              name: "policy_grounding_matrix_present",
              next_action: nextAction,
              phase: "policy_grounding",
              status: "fail",
            },
            {
              blocking: false,
              code: "source_freshness_warn",
              evidence_ref: "quality_evidence/source_freshness.json",
              layer: "fabric_evidence",
              message: "One source is close to its freshness budget.",
              name: "source_freshness_budget",
              next_action: "Refresh stale source evidence.",
              phase: "freshness",
              status: "warn",
            },
          ],
          quality_evidence_bundle_path: `${evidenceBundlePath}?api_key=fixture-secret`,
          quality_scorecard_ref:
            "quality_evidence/quality_scorecard.json?token=fixture-secret",
          quality_status: "fail",
          requested_execution_profile: "production",
          run_id: metadata.core_run_id,
          runtime_state: "completed",
          started_at: "2026-04-12T09:00:05Z",
          state: "completed",
          submitted_at: "2026-04-12T09:00:00Z",
          unresolved_authority_gaps: [
            {
              code: "multi_model_policy_disagreement",
              layer: "scientist_policy_artifacts",
              message: qualityMessage,
              next_action: nextAction,
              next_diagnostic_command: nextDiagnosticCommand,
              phase: "policy_grounding",
            },
          ],
          next_diagnostic_commands: [nextDiagnosticCommand],
        },
      },
    ]);

    await page.goto("/");
    await expect(
      page.getByText("What policy would you like to analyze?"),
    ).toBeVisible();

    await page
      .getByPlaceholder("Ask a policy question...")
      .fill("Compare production policy recommendations across model variants.");
    await page.getByRole("button", { name: "Analyze" }).click();

    const qualityPanel = page.getByRole("region", { name: "Control quality" });
    const approvalPanel = page.getByRole("region", {
      name: "Control approval",
    });
    await expect(qualityPanel).toBeVisible();
    await expect(approvalPanel).toBeVisible();
    await expect(
      page.getByRole("region", { name: "Control failure" }),
    ).toHaveCount(0);
    await expect(qualityPanel.getByText("quality fail")).toBeVisible();
    await expect(qualityPanel.getByText("execution completed")).toBeVisible();
    await expect(
      qualityPanel.getByText("multi_model_policy_disagreement"),
    ).toBeVisible();
    await expect(
      qualityPanel.getByText("scientist_policy_artifacts"),
    ).toBeVisible();
    await expect(
      qualityPanel.getByText("policy_grounding", { exact: true }),
    ).toBeVisible();
    await expect(qualityPanel.getByText(qualityMessage)).toBeVisible();
    await expect(qualityPanel.getByText(nextAction)).toBeVisible();
    await expect(
      qualityPanel.getByText(
        "Evidence: quality_evidence/policy_grounding_matrix.json",
      ),
    ).toBeVisible();
    await expect(
      approvalPanel.getByText("approval quality_failed"),
    ).toBeVisible();
    await expect(approvalPanel.getByText("not approval-ready")).toBeVisible();
    await expect(
      approvalPanel.getByText("approval-ready", { exact: true }),
    ).toHaveCount(0);
    await expect(approvalPanel.getByText("override required")).toBeVisible();
    await expect(
      approvalPanel.getByText(
        "Projection: runtime.control_job / projection_only",
      ),
    ).toBeVisible();
    await expect(
      approvalPanel.getByText("Runtime state: completed"),
    ).toBeVisible();
    await expect(
      approvalPanel.getByText("multi_model_policy_disagreement"),
    ).toBeVisible();
    await expect(approvalPanel.getByText(nextAction)).toBeVisible();
    await expect(approvalPanel.getByText(nextDiagnosticCommand)).toBeVisible();
    await expect(
      approvalPanel.getByText("scientist_policy_artifacts"),
    ).toBeVisible();
    await expect(approvalPanel.getByText("fabric_evidence")).toBeVisible();
    await expect(
      approvalPanel.getByText("policy_grounding_matrix_present"),
    ).toBeVisible();
    await expect(
      approvalPanel.getByText("source_freshness_budget"),
    ).toBeVisible();
    await expect(
      approvalPanel.getByText(
        "Scorecard: quality_evidence/quality_scorecard.json",
      ),
    ).toBeVisible();
    await expect(
      approvalPanel.getByText(`Evidence bundle: ${evidenceBundlePath}`),
    ).toBeVisible();
    await expect(
      approvalPanel.getByText(
        "Approval packet: quality_evidence/approval_packet.json",
      ),
    ).toBeVisible();
    await expect(
      approvalPanel.getByText(
        "Override packet: quality_evidence/override_packet.json",
      ),
    ).toBeVisible();
    await expect(page.getByText(/fixture-secret/)).toHaveCount(0);
  });
});
