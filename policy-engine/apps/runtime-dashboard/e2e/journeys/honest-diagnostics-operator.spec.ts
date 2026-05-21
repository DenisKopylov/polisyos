import { expect, test } from "@playwright/test";

import {
  applyRuntimeApiScenario,
  installDashboardTestState,
  readFixtureMetadata,
  waitForDashboardSurface,
} from "../helpers/runtime-dashboard";

const INTERFACE_MODE_STORAGE_KEY = "polisyos.runtime.interface-mode";

const nextDiagnosticCommand =
  "uv run pytest tests/unit/runtime/quality/test_scorecard.py -q";

const operatorDiagnostic = {
  authoritative_runtime_state: "failed",
  projection_source: "runtime_quality_scorecard",
  owner: "team-policy-semantics",
  phase: "policy_grounding",
  first_blocking_cause: "policy_grounding_matrix_ref_missing",
  upstream_missing_input: "policy_grounding_matrix_ref",
  downstream_impact: "Readiness and approval projections remain closed.",
  authority_refs: {
    quality_scorecard: "quality_evidence/quality_scorecard.json",
    runtime_event_log: "sha256:bbbb",
  },
  blocker_overridable: false,
  evidence_refs: ["quality_evidence/policy_grounding_matrix.json"],
  next_diagnostic_command: nextDiagnosticCommand,
  projection_labels: [
    { state: "draft", label: "draft", authority: "projection_only" },
    { state: "projected", label: "projected", authority: "projection_only" },
    { state: "blocked", label: "blocked", authority: "runtime_authority" },
    {
      state: "readiness_closed",
      label: "readiness-closed",
      authority: "runtime_authority",
    },
    { state: "approved", label: "approved", authority: "projection_only" },
    { state: "rejected", label: "rejected", authority: "projection_only" },
    {
      state: "published_blocked",
      label: "published-blocked",
      authority: "runtime_authority",
    },
  ],
};

test.describe("runtime-dashboard honest diagnostics operator UX", () => {
  test.beforeEach(async ({ page }) => {
    await installDashboardTestState(page);
    await page.addInitScript((storageKey) => {
      window.localStorage.setItem(storageKey, "clerk");
    }, INTERFACE_MODE_STORAGE_KEY);
  });

  test("@smoke explains a failed serious run from API projections without bundle internals", async ({
    page,
  }) => {
    const metadata = readFixtureMetadata();
    const jobId = "job_operator_diagnostic_route_fixture";
    const qualityMessage = "Policy grounding matrix is missing.";
    const nextAction = "Attach the policy grounding matrix ref.";

    await applyRuntimeApiScenario(page, "ok", [
      {
        matcher: "/api/v1/control/runs/nl",
        method: "POST",
        body: {
          job_id: jobId,
          message: "Quality gate failed after execution",
          meta: {
            generated_at: new Date().toISOString(),
            request_id: "playwright-operator-diagnostic-launch",
            source_kinds: ["control_job"],
          },
          run_id: null,
          status: "rejected",
        },
      },
      {
        matcher:
          /^\/api\/v1\/control\/jobs\/job_operator_diagnostic_route_fixture$/,
        method: "GET",
        body: {
          blocking_quality_failures: [
            {
              code: "policy_grounding_matrix_ref_missing",
              evidence_ref: "quality_evidence/policy_grounding_matrix.json",
              gate: "policy_grounding_matrix_present",
              layer: "scientist_policy_artifacts",
              message: qualityMessage,
              next_action: nextAction,
              operator_diagnostic: operatorDiagnostic,
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
            request_id: "playwright-operator-diagnostic-job",
            source_kinds: ["control_job"],
          },
          operator_diagnostic: operatorDiagnostic,
          pipeline_id: null,
          approval_projection: {
            eligible: false,
            reasons: ["policy_grounding_matrix_ref_missing"],
            source_surface: "runtime.control_job",
            authority_level: "projection_only",
            state: "quality_failed",
          },
          authoritative_scorecard_ref:
            "quality_evidence/quality_scorecard.json",
          projection_source: {
            authority_level: "projection_only",
            projection_policy: "projection_only",
            source_detail: "control_store_progress",
            source_surface: "runtime.control_job",
          },
          progress: {
            quality_scorecard: {
              approval_state: "quality_failed",
              approval_eligibility: {
                eligible: false,
                execution_status: "completed",
                missing_override: false,
                performance_status: "pass",
                quality_status: "fail",
                reasons: ["policy_grounding_matrix_ref_missing"],
                requires_override: false,
                state: "quality_failed",
              },
              evidence_refs: {
                quality_scorecard: "quality_evidence/quality_scorecard.json",
              },
            },
            status: "completed",
          },
          quality_gates: [
            {
              blocking: true,
              code: "policy_grounding_matrix_ref_missing",
              evidence_ref: "quality_evidence/policy_grounding_matrix.json",
              layer: "scientist_policy_artifacts",
              message: qualityMessage,
              name: "policy_grounding_matrix_present",
              next_action: nextAction,
              operator_diagnostic: operatorDiagnostic,
              phase: "policy_grounding",
              status: "fail",
            },
          ],
          quality_evidence_bundle_path:
            ".polisyos/canary_evidence/operator-diagnostic",
          quality_scorecard_ref: "quality_evidence/quality_scorecard.json",
          quality_status: "fail",
          requested_execution_profile: "production",
          run_id: metadata.core_run_id,
          runtime_state: "failed",
          started_at: "2026-04-12T09:00:05Z",
          state: "completed",
          submitted_at: "2026-04-12T09:00:00Z",
          unresolved_authority_gaps: [
            {
              code: "policy_grounding_matrix_ref_missing",
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
      {
        matcher: `/api/v1/runs/${metadata.core_run_id}`,
        method: "GET",
        body: ({ payload }) => {
          const record = structuredClone(payload) as {
            run?: Record<string, unknown>;
          };
          record.run = {
            ...(record.run ?? {}),
            operator_diagnostic: {
              ...operatorDiagnostic,
              projection_source: "runtime_run_details",
            },
            status: "failed",
          };
          return record;
        },
      },
    ]);

    await page.goto("/");
    await expect(
      page.getByText("What policy would you like to analyze?"),
    ).toBeVisible();

    await page
      .getByPlaceholder("Ask a policy question...")
      .fill("Explain the first serious run blocker for operators.");
    await page.getByRole("button", { name: "Analyze" }).click();

    const controlDiagnostic = page.getByRole("region", {
      name: "Operator diagnostic",
    });
    await expect(controlDiagnostic).toBeVisible();
    await expect(
      controlDiagnostic.getByText("runtime_quality_scorecard"),
    ).toBeVisible();
    await expect(controlDiagnostic.getByText("failed")).toBeVisible();
    await expect(
      controlDiagnostic.getByText("policy_grounding_matrix_ref_missing"),
    ).toBeVisible();
    await expect(
      controlDiagnostic.getByText("policy_grounding_matrix_ref", {
        exact: true,
      }),
    ).toBeVisible();
    await expect(
      controlDiagnostic.getByText("team-policy-semantics"),
    ).toBeVisible();
    await expect(controlDiagnostic.getByText("not overridable")).toBeVisible();
    await expect(
      controlDiagnostic.getByText(
        "quality_scorecard: quality_evidence/quality_scorecard.json",
      ),
    ).toBeVisible();
    await expect(
      controlDiagnostic.getByText(
        "quality_evidence/policy_grounding_matrix.json",
        {
          exact: true,
        },
      ),
    ).toBeVisible();
    await expect(
      controlDiagnostic.getByText(nextDiagnosticCommand),
    ).toBeVisible();

    for (const label of [
      "draft",
      "projected",
      "blocked",
      "readiness-closed",
      "approved",
      "rejected",
      "published-blocked",
    ]) {
      await expect(
        controlDiagnostic.getByText(label, { exact: true }),
      ).toBeVisible();
    }
    await expect(controlDiagnostic.getByText("projection only")).toBeVisible();
    await expect(page.getByText(/approval granted/i)).toHaveCount(0);

    await page.goto(`/runs/${metadata.core_run_id}/overview`);
    await waitForDashboardSurface(page, "run-overview");

    const runDiagnostic = page.getByRole("region", {
      name: "Operator diagnostic",
    });
    await expect(runDiagnostic).toBeVisible();
    await expect(runDiagnostic.getByText("runtime_run_details")).toBeVisible();
    await expect(runDiagnostic.getByText("failed")).toBeVisible();
    await expect(
      runDiagnostic.getByText("policy_grounding_matrix_ref_missing"),
    ).toBeVisible();
    await expect(
      runDiagnostic.getByText("team-policy-semantics"),
    ).toBeVisible();
    await expect(runDiagnostic.getByText(nextDiagnosticCommand)).toBeVisible();
    await expect(page.getByText(/bundle internals/i)).toHaveCount(0);
  });
});
