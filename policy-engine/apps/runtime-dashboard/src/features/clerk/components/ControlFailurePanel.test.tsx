import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { renderWithProviders } from "@/test/render";
import { ControlFailurePanel } from "./ControlFailurePanel";

describe("ControlFailurePanel", () => {
  it("renders the stable operator failure envelope", () => {
    renderWithProviders(
      <ControlFailurePanel
        failure={{
          code: "llm_provider_preflight_failed",
          layer: "llm_gateway",
          phase: "provider_preflight",
          message: "model_id missing-model not returned by /v1/models",
          retryable: false,
          model: "missing-model",
          provider: "gonka_proxy",
          next_action: "Check provider credentials and model configuration.",
          artifact_refs: {
            provider_preflight_ref: "sha256:abcdef",
          },
          variant_failures: [],
        }}
      />,
    );

    expect(
      screen.getByText("llm_provider_preflight_failed"),
    ).toBeInTheDocument();
    expect(screen.getByText("llm_gateway")).toBeInTheDocument();
    expect(screen.getByText("provider_preflight")).toBeInTheDocument();
    expect(screen.getByText("not retryable")).toBeInTheDocument();
    expect(screen.getByText("missing-model")).toBeInTheDocument();
    expect(screen.getByText("gonka_proxy")).toBeInTheDocument();
    expect(
      screen.getByText("Check provider credentials and model configuration."),
    ).toBeInTheDocument();
    expect(screen.getByText(/sha256:abcdef/)).toBeInTheDocument();
  });

  it("renders typed honest-diagnostics operator root cause fields", () => {
    renderWithProviders(
      <ControlFailurePanel
        failure={{
          code: "llm_provider_preflight_failed",
          layer: "llm_gateway",
          phase: "provider_preflight",
          message: "model_id missing-model not returned by /v1/models",
          retryable: false,
          next_action: "Check provider credentials and model configuration.",
          artifact_refs: {
            provider_preflight_ref: "sha256:abcdef",
          },
          variant_failures: [],
          operator_diagnostic: {
            authoritative_runtime_state: "failed",
            projection_source: "runtime_control_job_failure",
            owner: "team-runtime-ops",
            phase: "provider_preflight",
            first_blocking_cause: "llm_provider_preflight_failed",
            upstream_missing_input: "llm_provider_model_catalog",
            downstream_impact:
              "No serious decision packet can be materialized.",
            authority_refs: {
              provider_preflight_ref: "sha256:abcdef",
              runtime_event_log: "sha256:bbbb",
            },
            blocker_overridable: false,
            evidence_refs: ["sha256:abcdef"],
            next_diagnostic_command:
              "uv run pytest tests/unit/scientist/orchestration/llm/test_provider_verification.py -q",
          },
        }}
      />,
    );

    const diagnosticPanel = screen.getByRole("region", {
      name: "Operator diagnostic",
    });
    expect(
      within(diagnosticPanel).getByText("runtime_control_job_failure"),
    ).toBeInTheDocument();
    expect(within(diagnosticPanel).getByText("failed")).toBeInTheDocument();
    expect(
      within(diagnosticPanel).getByText("team-runtime-ops"),
    ).toBeInTheDocument();
    expect(
      within(diagnosticPanel).getByText("llm_provider_preflight_failed"),
    ).toBeInTheDocument();
    expect(
      within(diagnosticPanel).getByText("llm_provider_model_catalog"),
    ).toBeInTheDocument();
    expect(
      within(diagnosticPanel).getByText("not overridable"),
    ).toBeInTheDocument();
    expect(
      within(diagnosticPanel).getAllByText(/sha256:abcdef/).length,
    ).toBeGreaterThan(0);
    expect(
      within(diagnosticPanel).getByText(
        "uv run pytest tests/unit/scientist/orchestration/llm/test_provider_verification.py -q",
      ),
    ).toBeInTheDocument();
  });

  it("labels projection lifecycle states without implying approval authority", () => {
    renderWithProviders(
      <ControlFailurePanel
        job={{
          meta: { request_id: "req-labels" },
          job_id: "job-labels",
          kind: "natural_language_run",
          state: "completed",
          effective_execution_profile: "production",
          execution_status: "completed",
          quality_status: "fail",
          operator_diagnostic: {
            authoritative_runtime_state: "completed",
            projection_source: "runtime_quality_scorecard",
            owner: "team-quality-closeout",
            phase: "approval_projection",
            first_blocking_cause: "approval_projection_blocked",
            upstream_missing_input: "runtime_readiness_packet",
            downstream_impact:
              "Publication is blocked until runtime readiness closes.",
            authority_refs: {
              quality_scorecard: "quality_evidence/quality_scorecard.json",
            },
            blocker_overridable: false,
            evidence_refs: ["quality_evidence/quality_scorecard.json"],
            next_diagnostic_command:
              "uv run pytest tests/unit/runtime/quality/test_approval.py -q",
            projection_labels: [
              { state: "draft", label: "draft", authority: "projection_only" },
              {
                state: "projected",
                label: "projected",
                authority: "projection_only",
              },
              {
                state: "blocked",
                label: "blocked",
                authority: "runtime_authority",
              },
              {
                state: "readiness_closed",
                label: "readiness-closed",
                authority: "runtime_authority",
              },
              {
                state: "approved",
                label: "approved",
                authority: "projection_only",
              },
              {
                state: "rejected",
                label: "rejected",
                authority: "projection_only",
              },
              {
                state: "published_blocked",
                label: "published-blocked",
                authority: "runtime_authority",
              },
            ],
          },
        }}
      />,
    );

    const diagnosticPanel = screen.getByRole("region", {
      name: "Operator diagnostic",
    });
    for (const label of [
      "draft",
      "projected",
      "blocked",
      "readiness-closed",
      "approved",
      "rejected",
      "published-blocked",
    ]) {
      expect(within(diagnosticPanel).getByText(label)).toBeInTheDocument();
    }
    expect(
      within(diagnosticPanel).getAllByText("projection only").length,
    ).toBeGreaterThan(0);
    expect(screen.queryByText(/approval granted/i)).not.toBeInTheDocument();
  });

  it("renders quality status separately from completed execution", () => {
    renderWithProviders(
      <ControlFailurePanel
        job={{
          meta: { request_id: "req-quality" },
          job_id: "job-quality",
          kind: "natural_language_run",
          state: "completed",
          effective_execution_profile: "production",
          execution_status: "completed",
          quality_status: "fail",
          quality_scorecard_ref: "quality_evidence/quality_scorecard.json",
          quality_evidence_bundle_path: ".polisyos/canary_evidence/run-1",
          quality_gates: [
            {
              name: "policy_grounding_matrix_present",
              code: "multi_model_policy_disagreement",
              status: "fail",
              layer: "scientist_policy_artifacts",
              phase: "policy_grounding",
              message: "Unsupported policy claim.",
              evidence_ref: "quality_evidence/policy_grounding_matrix.json",
              next_action: "Map final policy claims to evidence refs.",
              blocking: true,
            },
          ],
          blocking_quality_failures: [
            {
              gate: "policy_grounding_matrix_present",
              code: "multi_model_policy_disagreement",
              layer: "scientist_policy_artifacts",
              phase: "policy_grounding",
              message: "Unsupported policy claim.",
              evidence_ref: "quality_evidence/policy_grounding_matrix.json",
              next_action: "Map final policy claims to evidence refs.",
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("quality fail")).toBeInTheDocument();
    expect(screen.getByText("execution completed")).toBeInTheDocument();
    expect(
      screen.getByText("policy_grounding_matrix_present"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("multi_model_policy_disagreement"),
    ).toBeInTheDocument();
    expect(screen.getByText("scientist_policy_artifacts")).toBeInTheDocument();
    expect(screen.getByText("policy_grounding")).toBeInTheDocument();
    expect(screen.getByText("Unsupported policy claim.")).toBeInTheDocument();
    expect(
      screen.getByText("Map final policy claims to evidence refs."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/quality_evidence\/policy_grounding_matrix\.json/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/quality_evidence\/quality_scorecard\.json/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/\.polisyos\/canary_evidence\/run-1/),
    ).toBeInTheDocument();
  });

  it("renders approval readiness separately with grouped gates and sanitized refs", () => {
    renderWithProviders(
      <ControlFailurePanel
        job={{
          meta: { request_id: "req-approval" },
          job_id: "job-approval",
          kind: "natural_language_run",
          state: "completed",
          effective_execution_profile: "production",
          execution_status: "completed",
          quality_status: "fail",
          quality_scorecard_ref:
            "quality_evidence/quality_scorecard.json?token=sk-live-secret",
          quality_evidence_bundle_path:
            ".polisyos/canary_evidence/run-approval?api_key=abc123",
          quality_gates: [
            {
              name: "policy_grounding_matrix_present",
              code: "multi_model_policy_disagreement",
              status: "fail",
              layer: "scientist_policy_artifacts",
              phase: "policy_grounding",
              message: "Unsupported policy claim.",
              evidence_ref:
                "quality_evidence/policy_grounding_matrix.json?signature=secret-signature",
              next_action: "Map final policy claims to evidence refs.",
              blocking: true,
            },
            {
              name: "source_freshness_budget",
              code: "source_freshness_warn",
              status: "warn",
              layer: "fabric_evidence",
              phase: "freshness",
              message: "One source is close to its freshness budget.",
              evidence_ref: "quality_evidence/source_freshness.json",
              next_action: "Refresh stale source evidence.",
              blocking: false,
            },
          ],
          blocking_quality_failures: [
            {
              gate: "policy_grounding_matrix_present",
              code: "multi_model_policy_disagreement",
              layer: "scientist_policy_artifacts",
              phase: "policy_grounding",
              message: "Unsupported policy claim.",
              evidence_ref:
                "quality_evidence/policy_grounding_matrix.json?signature=secret-signature",
              next_action: "Map final policy claims to evidence refs.",
            },
          ],
          progress: {
            quality_scorecard: {
              approval_state: "quality_failed",
              approval_eligibility: {
                eligible: false,
                execution_status: "completed",
                missing_override: true,
                performance_status: "pass",
                quality_status: "fail",
                reasons: ["multi_model_policy_disagreement"],
                requires_override: true,
                state: "quality_failed",
              },
              evidence_refs: {
                approval_packet:
                  "quality_evidence/approval_packet.json?token=packet-secret",
              },
              override_evidence: {
                decision_ref:
                  "quality_evidence/override_decision.json?token=override-secret",
                packet_ref: "quality_evidence/override_packet.json",
                status: "pending",
              },
            },
          },
        }}
      />,
    );

    const approvalPanel = screen.getByRole("region", {
      name: "Control approval",
    });
    expect(approvalPanel).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText("approval quality_failed"),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText("not approval-ready"),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText("multi_model_policy_disagreement"),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText(
        "Map final policy claims to evidence refs.",
      ),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText("scientist_policy_artifacts"),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText("fabric_evidence"),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText("policy_grounding_matrix_present"),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText("source_freshness_budget"),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText(
        "Scorecard: quality_evidence/quality_scorecard.json",
      ),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText(
        "Evidence bundle: .polisyos/canary_evidence/run-approval",
      ),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText(
        "Approval packet: quality_evidence/approval_packet.json",
      ),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText(
        "Override: quality_evidence/override_decision.json",
      ),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText(
        "Override packet: quality_evidence/override_packet.json",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(
        /sk-live-secret|abc123|packet-secret|override-secret|secret-signature/,
      ),
    ).not.toBeInTheDocument();
  });

  it("does not let projection-only approval_ready hide failed serious blockers", () => {
    renderWithProviders(
      <ControlFailurePanel
        job={{
          meta: { request_id: "req-projection-boundary" },
          job_id: "job-projection-boundary",
          kind: "natural_language_run",
          state: "completed",
          effective_execution_profile: "production",
          execution_status: "completed",
          quality_status: "fail",
          runtime_state: "completed",
          projection_source: {
            source_surface: "runtime.control_job",
            source_detail: "control_store_progress",
            authority_level: "projection_only",
            projection_policy: "projection_only",
          },
          authoritative_scorecard_ref:
            "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          approval_projection: {
            eligible: false,
            state: "quality_failed",
            reasons: ["major_claim_missing_grounding"],
            source_surface: "runtime.control_job",
            authority_level: "projection_only",
          },
          unresolved_authority_gaps: [
            {
              code: "major_claim_missing_grounding",
              layer: "scientist_policy_artifacts",
              phase: "policy_grounding",
              message: "Unsupported policy claim.",
              next_diagnostic_command:
                "uv run pytest tests/unit/runtime/http/test_control_api.py -q",
            },
          ],
          next_diagnostic_commands: [
            "uv run pytest tests/unit/runtime/http/test_control_api.py -q",
          ],
          quality_gates: [
            {
              name: "policy_grounding_matrix_present",
              code: "major_claim_missing_grounding",
              status: "fail",
              layer: "scientist_policy_artifacts",
              phase: "policy_grounding",
              message: "Unsupported policy claim.",
              evidence_ref: "quality_evidence/policy_grounding_matrix.json",
              next_action: "Map final policy claims to evidence refs.",
              blocking: true,
            },
          ],
          blocking_quality_failures: [
            {
              gate: "policy_grounding_matrix_present",
              code: "major_claim_missing_grounding",
              layer: "scientist_policy_artifacts",
              phase: "policy_grounding",
              message: "Unsupported policy claim.",
              evidence_ref: "quality_evidence/policy_grounding_matrix.json",
              next_action: "Map final policy claims to evidence refs.",
            },
          ],
          progress: {
            quality_scorecard: {
              approval_state: "approval_ready",
              approval_ready: true,
              approval_eligibility: {
                eligible: true,
                state: "approval_ready",
              },
              evidence_refs: {
                quality_scorecard:
                  "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
              },
            },
          },
        }}
      />,
    );

    const approvalPanel = screen.getByRole("region", {
      name: "Control approval",
    });
    expect(
      within(approvalPanel).getByText("approval quality_failed"),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText("not approval-ready"),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).queryByText("approval-ready"),
    ).not.toBeInTheDocument();
    expect(
      within(approvalPanel).getByText(
        "Projection: runtime.control_job / projection_only",
      ),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText("Runtime state: completed"),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText(
        "uv run pytest tests/unit/runtime/http/test_control_api.py -q",
      ),
    ).toBeInTheDocument();
  });

  it("renders top-level projection authority gaps without nested scorecard data", () => {
    renderWithProviders(
      <ControlFailurePanel
        job={{
          meta: { request_id: "req-top-level-projection" },
          job_id: "job-top-level-projection",
          kind: "natural_language_run",
          state: "completed",
          effective_execution_profile: "production",
          execution_status: "completed",
          quality_status: "fail",
          runtime_state: "completed",
          projection_source: {
            source_surface: "runtime.control_job",
            source_detail: "control_store_progress",
            authority_level: "projection_only",
            projection_policy: "projection_only",
          },
          authoritative_scorecard_ref:
            "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
          approval_projection: {
            eligible: false,
            state: "quality_failed",
            reasons: ["runtime_readiness_packet_missing"],
            source_surface: "runtime.control_job",
            authority_level: "projection_only",
          },
          unresolved_authority_gaps: [
            {
              code: "runtime_readiness_packet_missing",
              layer: "quality_scorecard",
              phase: "readiness",
              message: "Runtime readiness packet has not closed.",
              next_diagnostic_command:
                "uv run pytest tests/unit/runtime/quality/test_approval.py -q",
            },
          ],
          next_diagnostic_commands: [
            "uv run pytest tests/unit/runtime/quality/test_approval.py -q",
          ],
          progress: {
            status: "completed",
          },
        }}
      />,
    );

    const approvalPanel = screen.getByRole("region", {
      name: "Control approval",
    });
    expect(
      within(approvalPanel).getByText("approval quality_failed"),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText("not approval-ready"),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText(
        "Projection: runtime.control_job / projection_only",
      ),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText("Runtime state: completed"),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText(
        "uv run pytest tests/unit/runtime/quality/test_approval.py -q",
      ),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText(
        "Scorecard: sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
      ),
    ).toBeInTheDocument();
  });

  it("hides secret-bearing evidence ref path segments from approval surfaces", () => {
    renderWithProviders(
      <ControlFailurePanel
        job={{
          meta: { request_id: "req-secret-refs" },
          job_id: "job-secret-refs",
          kind: "natural_language_run",
          state: "completed",
          effective_execution_profile: "production",
          execution_status: "completed",
          quality_status: "fail",
          quality_scorecard_ref:
            "quality_evidence/secret/sk-live-secret/quality_scorecard.json",
          quality_evidence_bundle_path:
            ".polisyos/canary_evidence/api_key/abc123",
          quality_gates: [
            {
              name: "policy_grounding_matrix_present",
              code: "multi_model_policy_disagreement",
              status: "fail",
              layer: "scientist_policy_artifacts",
              phase: "policy_grounding",
              message: "Unsupported policy claim.",
              evidence_ref:
                "quality_evidence/token/sk-live-secret/policy_grounding_matrix.json",
              next_action: "Map final policy claims to evidence refs.",
              blocking: true,
            },
          ],
          blocking_quality_failures: [
            {
              gate: "policy_grounding_matrix_present",
              code: "multi_model_policy_disagreement",
              layer: "scientist_policy_artifacts",
              phase: "policy_grounding",
              message: "Unsupported policy claim.",
              evidence_ref:
                "quality_evidence/token/sk-live-secret/policy_grounding_matrix.json",
              next_action: "Map final policy claims to evidence refs.",
            },
          ],
          progress: {
            quality_scorecard: {
              approval_state: "quality_failed",
              approval_eligibility: {
                eligible: false,
                execution_status: "completed",
                performance_status: "pass",
                quality_status: "fail",
                reasons: ["multi_model_policy_disagreement"],
                state: "quality_failed",
              },
              evidence_refs: {
                approval_packet: "quality_evidence/secret/approval_packet.json",
              },
              override_evidence: {
                packet_ref: "quality_evidence/secret/override_packet.json",
                status: "pending",
              },
            },
          },
        }}
      />,
    );

    const approvalPanel = screen.getByRole("region", {
      name: "Control approval",
    });
    expect(
      within(approvalPanel).getByText("multi_model_policy_disagreement"),
    ).toBeInTheDocument();
    expect(
      within(approvalPanel).getByText(
        "Map final policy claims to evidence refs.",
      ),
    ).toBeInTheDocument();
    expect(
      screen.queryByText(
        /sk-live-secret|api_key|abc123|secret\/approval|secret\/override|token\/sk-live/i,
      ),
    ).not.toBeInTheDocument();
  });

  it("renders active Scientist workflow progress for running jobs", () => {
    renderWithProviders(
      <ControlFailurePanel
        job={{
          meta: { request_id: "req-scientist" },
          job_id: "job-scientist",
          kind: "natural_language_run",
          state: "running",
          effective_execution_profile: "production",
          execution_status: "running",
          progress: {
            phase: "scientist_workflow_running",
            scientist_workflow: {
              event_count: 12,
              current_node_alias: "formalize_problem",
              current_event: "NODE_OK",
              current_phase: "scientist.node.formalize_problem",
              latest_artifact_refs: [
                {
                  direction: "outputs",
                  artifact_id: "sha256:cccc",
                  kind: "scientist.formalized_problem",
                  media_type: "application/json",
                },
              ],
            },
          },
        }}
      />,
    );

    expect(screen.getByText("Scientist workflow")).toBeInTheDocument();
    expect(screen.getByText("formalize_problem")).toBeInTheDocument();
    expect(screen.getByText("NODE_OK")).toBeInTheDocument();
    expect(
      screen.getByText("scientist.node.formalize_problem"),
    ).toBeInTheDocument();
    expect(screen.getByText(/sha256:cccc/)).toBeInTheDocument();
  });
});
