import type { QuantityValueOutput } from "@polisyos/runtime-api-client";
import type { z } from "zod";

import type { components } from "./types";
import {
  humanDecisionGateResponseSchema,
  humanDecisionReviewEffectivenessSchema,
  lexSearchRequestSchema,
  lexSearchProfileResponseSchema,
  lexSearchResponseSchema,
  quantityValueSchema,
  runAgentsSchema,
  runDetailsSchema,
  runEvidenceContextSchema,
  runsListSchema,
} from "./validators";
import {
  acquisitionGrowthPayloadSchema,
  acquisitionRouteListResponseSchema,
} from "@/features/runs/api/acquisitionRouteValidators";
import {
  availableHumanDecisionGate,
  humanDecisionDigest,
  humanDecisionReviewEffectivenessFixture,
} from "@/test/fixtures/humanDecision";

function mutableRecord(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new TypeError("expected mutable fixture record");
  }
  return value as Record<string, unknown>;
}

function firstMutableRecord(
  value: unknown,
  fixtureMember: string,
): Record<string, unknown> {
  if (!Array.isArray(value) || value.length === 0) {
    throw new TypeError(`expected non-empty ${fixtureMember} mutation fixture`);
  }
  return mutableRecord(value[0]);
}

type ProjectionFixture = Record<string, unknown> & {
  audience?: components["schemas"]["PolicyDesignCaseProjection"]["audience"];
};

function projectionAuthorityCore(canCloseout: boolean) {
  return {
    authority_role: "projection_only" as const,
    closeout_truth: {
      blocker_codes: [],
      blockers: [],
      can_closeout: canCloseout,
      contested_state: "not_contested",
      limitation_codes: [],
      omission_codes: [],
      status: canCloseout ? "ready" : "blocked",
      verdict: canCloseout ? "can_closeout" : "cannot_closeout",
    },
    evidence_class: "runtime_projection",
    generated_at: "2026-05-19T10:00:00.000Z",
    primary_state: canCloseout ? "publishable" : "projection_only",
    projection_policy: "reads_policy_design_case_only" as const,
    provenance_kind: "runtime_projection" as const,
    states: canCloseout
      ? ["projection_only", "publishable"]
      : ["projection_only"],
    surface: "runtime_dashboard",
  };
}

const projectionMaskingCases = [
  {
    caseId: "missing",
    code: "projection_masked_missing",
    label: "missing evidence label",
  },
  {
    caseId: "stale",
    code: "projection_masked_stale",
    label: "stale evidence label",
  },
  {
    caseId: "conflicting",
    code: "projection_masked_conflicting",
    label: "conflicting evidence label",
  },
  {
    caseId: "reissued",
    code: "projection_masked_reissued",
    label: "reissued evidence label",
  },
  {
    caseId: "withdrawn",
    code: "projection_masked_withdrawn",
    label: "withdrawn evidence label",
  },
  {
    caseId: "non_authoritative",
    code: "projection_masked_non_authoritative",
    label: "non-authoritative evidence label",
  },
  {
    caseId: "projection_only",
    code: "projection_masked_projection_only",
    label: "projection-only evidence label",
  },
] as const;

function runDetailsPayload(label: string) {
  const policyDesignCaseProjection: ProjectionFixture = {
    ...projectionAuthorityCore(false),
    audience: "public",
    labels: [
      {
        authority_role: "projection_only",
        label,
        state: "projection_only",
      },
    ],
    may_not_be_used_for: ["scorecard_authority"],
  };

  return {
    meta: {
      generated_at: "2026-05-19T10:00:00.000Z",
      request_id: "req-projection-mask",
      source_kinds: ["core_run"],
    },
    run: {
      decision_validity_status: undefined as string | null | undefined,
      duration_ms: null,
      finished_at: null,
      has_trace: false,
      has_workflow_report: false,
      operator_diagnostic: {
        authoritative_runtime_state: "blocked",
        downstream_impact: "Projection labels cannot close readiness.",
        first_blocking_cause: "projection_masked",
        next_diagnostic_command: "corepack pnpm test:components",
        owner: "team-runtime-quality",
        phase: "35G.1",
        projection_labels: [
          {
            authority: "projection_only",
            label,
            state: "projection_only",
          },
        ],
        projection_source: "policy_design_case_projection",
      },
      policy_design_case_projection: policyDesignCaseProjection,
      root_artifacts: [],
      run_id: "run-projection-mask",
      source_kind: "core_run",
      started_at: "2026-05-19T09:58:00.000Z",
      status: "failed",
      warnings: [],
    },
    temporal_scope: null,
  };
}

function genericCycleSimulationProjection(runId: string) {
  const ref = (kind: string, suffix: string) => ({
    artifact_id: "sha256:" + suffix.repeat(64),
    kind,
    media_type: "application/json",
  });
  const sourceRef = ref("runtime.compiled_recursive_generation_cycle", "a");
  const n4SourceRef = ref("runtime.generation_source_handoff", "c");
  const contextJobRef = ref("runtime.quality.cycle_substrate_context_job", "b");
  const profileRef = ref(
    "runtime.quality.generic_cycle_simulation_profile",
    "a",
  );
  const childFamilyRef = ref(
    "runtime.quality.generic_cycle_simulation_child_profile_family",
    "7",
  );
  const childSetRef = ref(
    "runtime.quality.recursive_n4_child_profile_set",
    "8",
  );
  const designProblemRef = "sha256:" + "d".repeat(64);

  const observation = (
    cycleIndex: number,
    digest: string,
    candidateId: string,
    status: "joint_simulated" | "simulation_pending_n5",
  ) => {
    const resultRef =
      status === "joint_simulated"
        ? ref("polisyos.runtime.joint_simulation_result", "5")
        : null;
    return {
      atom_ids: [`atom-${cycleIndex}`],
      authority_blockers: ["publication_not_admitted"],
      authority_purpose: "cycle_input_candidate_only",
      candidate_id: candidateId,
      child_profile_family_ref: childFamilyRef,
      child_profile_set_ref: childSetRef,
      context_job_ref: contextJobRef,
      currentness_status: "not_established",
      cycle_index: cycleIndex,
      design_problem_ref: "sha256:" + digest.repeat(64),
      n4_source_ref: n4SourceRef,
      n5_execution_ref:
        status === "joint_simulated"
          ? ref("runtime.quality.generic_cycle_simulation_n5_execution", "2")
          : null,
      n5_input_ref: ref(
        "runtime.quality.generic_cycle_simulation_n5_input",
        "3",
      ),
      n5_request_binding_status:
        status === "joint_simulated" ? "resolved" : "not_established",
      n5_request_content_hash:
        status === "joint_simulated" ? "sha256:" + "4".repeat(64) : null,
      n8_authority_blockers: ["n9_not_admitted"],
      n8_limitation_code:
        status === "joint_simulated"
          ? null
          : "generic_n5_request_binding_not_established",
      n8_lineage_status:
        status === "joint_simulated" ? "resolved" : "not_established",
      n8_status: "value_conditional",
      n8_value_ref: resultRef?.artifact_id ?? null,
      node_ref: "design-problem://" + digest.repeat(64),
      profile_ref: profileRef,
      profile_selection_ref: "sha256:" + "e".repeat(64),
      publication_authority: false,
      selected_outcomes: status === "joint_simulated" ? ["outcome-a"] : [],
      simulation_result_ref: resultRef,
      status,
      world_model_record_content_hash: "sha256:" + "6".repeat(64),
    };
  };

  return {
    artifact_status: "resolved",
    authority_purpose: "cycle_input_candidate_only",
    child_profile_bindings: [
      {
        context_job_ref: contextJobRef,
        currentness_status: "not_established",
        design_problem_ref: designProblemRef,
        historical_binding_status: "resolved",
        limitation_code: null,
        node_ref: "design-problem://" + "d".repeat(64),
        profile_id: "profile-a",
        profile_ref: profileRef,
        profile_selection_ref: "sha256:" + "e".repeat(64),
        semantic_ref: "sha256:" + "f".repeat(64),
        source_atom_refs: ["atom-a"],
        source_ref: n4SourceRef,
        source_result_ref: "sha256:" + "1".repeat(64),
      },
    ],
    child_profile_family_ref: childFamilyRef,
    child_profile_limitation_code: null,
    child_profile_set_ref: childSetRef,
    child_profile_status: "resolved",
    credal_source_attempt_ref: null,
    credal_source_limitation_code: null,
    credal_source_status: null,
    currentness_status: "not_established",
    limitation_code: "n5_sibling_failure_retained",
    n4_source_limitation_code: null,
    n4_source_ref: n4SourceRef,
    n4_source_status: "resolved",
    n5_limitation_code: "n5_sibling_failure_retained",
    n5_observations: [
      observation(0, "d", "candidate-a", "joint_simulated"),
      observation(1, "8", "candidate-b", "simulation_pending_n5"),
    ],
    parent_context_job_ref: contextJobRef,
    parent_profile_id: "parent-profile",
    parent_profile_ref: profileRef,
    publication_authority: false,
    recursive_cycle_checkpoint: {
      schema_version: "policyos.runtime.recursive_cycle_checkpoint.v2",
      status: "partial",
      publication_authority: false,
      budget_stop_node_ref: null,
      pending_frontier: ["design-problem://" + "8".repeat(64)],
      completed_design_refs: [designProblemRef],
      root_n9_status: "not_run",
      leaf_terminal_kinds: {
        ["design-problem://" + "d".repeat(64)]: "completed",
      },
      failed_branches: [
        {
          failed_branch_ref: "design-problem://" + "8".repeat(64),
          origin_node_ref: "design-problem://" + "8".repeat(64),
          stage: "n5",
          exception_type: "BudgetStopped",
          error_code: "child_budget_exhausted",
          error_message:
            "Sibling retained after its independent attempt stopped.",
        },
      ],
    },
    run_id: runId,
    schema_version:
      "policyos.runtime.run_generic_cycle_simulation_projection.v1",
    source_content_hash: "sha256:" + "6".repeat(64),
    source_ref: sourceRef,
  };
}
function genericCycleCredalProjection(runId: string) {
  const projection = mutableRecord(genericCycleSimulationProjection(runId));
  projection.schema_version =
    "policyos.runtime.run_generic_cycle_simulation_projection.v2";
  projection.credal_source_attempt_ref = {
    artifact_id: "sha256:" + "9".repeat(64),
    kind: "runtime.quality.candidate_credal_source_attempt",
    media_type: "application/json",
  };
  projection.credal_source_status = "not_established";
  projection.credal_source_limitation_code =
    "candidate_source_authority_not_established";
  projection.child_profile_family_ref = null;
  projection.child_profile_set_ref = null;
  projection.child_profile_status = "not_established";
  projection.child_profile_limitation_code =
    "generic_n4_source_generation_not_complete";
  projection.child_profile_bindings = [];
  projection.n5_limitation_code = "generic_n4_source_generation_not_complete";
  projection.n5_observations = [];
  projection.limitation_code = "candidate_source_authority_not_established";
  return projection;
}

function genericCycleRefusalProjection(runId: string) {
  return {
    artifact_status: "not_established",
    authority_purpose: "cycle_input_candidate_only",
    child_profile_bindings: [],
    child_profile_status: "not_established",
    currentness_status: "not_established",
    limitation_code: "compiled_cycle_artifact_integrity_not_established",
    n5_observations: [],
    publication_authority: false,
    run_id: runId,
    schema_version:
      "policyos.runtime.run_generic_cycle_simulation_projection.v1",
    source_content_hash: null,
    source_ref: null,
    n4_source_status: null,
  };
}

function runsListPayload(runTerminality: string | undefined) {
  return {
    meta: {
      generated_at: "2026-08-21T12:00:00.000Z",
      request_id: "req-ds8-run-terminality",
      source_kinds: ["core_run"],
    },
    page: {
      count: 1,
      cursor: null,
      limit: 50,
      next_cursor: null,
      total: 1,
    },
    runs: [
      {
        run_id: "run-ds8-terminality",
        run_terminality: runTerminality,
        source_kind: "core_run",
        status: "opaque-owner-status",
      },
    ],
  };
}

describe("runtime API validators", () => {
  it("preserves typed profile-selection provenance and rejects unknown statuses", () => {
    const base = {
      meta: {
        generated_at: "2026-10-11T10:00:00Z",
        request_id: "req-profile-origin",
        source_kinds: ["core_run"],
      },
      context: {
        run_id: "run-profile-origin",
        source_kind: "core_run",
      },
    };

    expect(
      runEvidenceContextSchema.parse({
        ...base,
        context: {
          ...base.context,
          data_view_request_profile_status: "caller_selected_profile",
        },
      }).context.data_view_request_profile_status,
    ).toBe("caller_selected_profile");
    expect(
      runEvidenceContextSchema.parse(base).context
        .data_view_request_profile_status,
    ).toBe("not_established");
    expect(() =>
      runEvidenceContextSchema.parse({
        ...base,
        context: {
          ...base.context,
          data_view_request_profile_status: "trusted_by_response_shape",
        },
      }),
    ).toThrow(/unknown generated data-view request profile status/);
  });

  it("preserves verified acquisition history in a freshly parsed run response", () => {
    const payload = runDetailsPayload("projection only");
    const run = mutableRecord(payload.run);
    run.candidate_simulation = {
      schema_version: "policyos.runtime.run_candidate_simulation_projection.v1",
      run_id: "run-projection-mask",
      artifact_status: "resolved",
      authority_purpose: "candidate_observation_only",
      publication_authority: false,
      source_ref: {
        artifact_id: `sha256:${"a".repeat(64)}`,
        kind: "runtime.compiled_recursive_generation_cycle",
        media_type: "application/json",
      },
      source_content_hash: `sha256:${"a".repeat(64)}`,
      n5_observations: [],
      acquisition_history_limitation_code: null,
      acquisition_history: [
        {
          route_receipt_ref: {
            artifact_id: `sha256:${"b".repeat(64)}`,
            kind: "runtime_quality.acquisition_route_loop_receipt",
            media_type: "application/json",
          },
          reentry_receipt_ref: {
            artifact_id: `sha256:${"c".repeat(64)}`,
            kind: "runtime_quality.acquisition_overlay_reentry_receipt",
            media_type: "application/json",
          },
          route_id: `sha256:${"d".repeat(64)}`,
          action_generation: 3,
          terminal_outcome: "reentry_completed",
          old_candidate_id: "candidate-before",
          new_candidate_id: "candidate-after",
          new_candidate_source_ref: {
            artifact_id: `sha256:${"e".repeat(64)}`,
            kind: "runtime.quality.n4_candidate_scenario_source",
            media_type: "application/json",
          },
          origin_source_ref: null,
          currentness_status: "not_established",
          authority_purpose: "candidate_observation_only",
          publication_authority: false,
        },
      ],
    };

    const parsed = runDetailsSchema.parse(payload);

    expect(parsed.run.candidate_simulation?.acquisition_history).toHaveLength(
      1,
    );
    expect(
      parsed.run.candidate_simulation?.acquisition_history?.[0]
        ?.origin_source_ref,
    ).toBeNull();
    expect(
      parsed.run.candidate_simulation?.acquisition_history?.[0]
        ?.currentness_status,
    ).toBe("not_established");
  });

  it("keeps an absent generic cycle field absent instead of synthesizing a projection", () => {
    const parsed = runDetailsSchema.parse(runDetailsPayload("projection only"));

    expect(parsed.run).not.toHaveProperty("generic_cycle_simulation");
  });

  it("preserves generic cycle simulation lineage through a freshly parsed run response", () => {
    const payload = runDetailsPayload("projection only");
    const run = mutableRecord(payload.run);
    const projection = genericCycleSimulationProjection("run-projection-mask");
    run.generic_cycle_simulation = projection;

    const parsed = runDetailsSchema.parse(payload);

    expect(parsed.run.generic_cycle_simulation).toEqual(projection);
    expect(
      parsed.run.generic_cycle_simulation?.child_profile_bindings[0],
    ).toMatchObject({
      historical_binding_status: "resolved",
      currentness_status: "not_established",
      limitation_code: null,
    });
    expect(parsed.run.generic_cycle_simulation?.n5_observations).toHaveLength(
      2,
    );
    expect(
      parsed.run.generic_cycle_simulation?.recursive_cycle_checkpoint
        ?.failed_branches,
    ).toHaveLength(1);
  });

  it("accepts the canonical budget-stopped v1 checkpoint shape", () => {
    const payload = runDetailsPayload("projection only");
    const projection = genericCycleSimulationProjection("run-projection-mask");
    const checkpoint = mutableRecord(projection.recursive_cycle_checkpoint);
    checkpoint.schema_version =
      "policyos.runtime.recursive_cycle_checkpoint.v1";
    checkpoint.budget_stop_node_ref = "design-problem://" + "8".repeat(64);
    checkpoint.failed_branches = [];
    mutableRecord(payload.run).generic_cycle_simulation = projection;

    const parsed = runDetailsSchema.parse(payload);

    expect(
      parsed.run.generic_cycle_simulation?.recursive_cycle_checkpoint
        ?.schema_version,
    ).toBe("policyos.runtime.recursive_cycle_checkpoint.v1");
  });

  it("preserves a backend-valid typed generic-cycle refusal", () => {
    const payload = runDetailsPayload("projection only");
    mutableRecord(payload.run).generic_cycle_simulation =
      genericCycleRefusalProjection("run-projection-mask");

    const parsed = runDetailsSchema.parse(payload);

    expect(parsed.run.generic_cycle_simulation?.artifact_status).toBe(
      "not_established",
    );
    expect(parsed.run.generic_cycle_simulation?.limitation_code).toBe(
      "compiled_cycle_artifact_integrity_not_established",
    );
    expect(parsed.run.generic_cycle_simulation?.child_profile_bindings).toEqual(
      [],
    );
  });

  it("preserves a backend-valid v2 credal-attempt limitation", () => {
    const payload = runDetailsPayload("projection only");
    mutableRecord(payload.run).generic_cycle_simulation =
      genericCycleCredalProjection("run-projection-mask");

    const parsed = runDetailsSchema.parse(payload);

    expect(parsed.run.generic_cycle_simulation?.schema_version).toBe(
      "policyos.runtime.run_generic_cycle_simulation_projection.v2",
    );
    expect(parsed.run.generic_cycle_simulation?.credal_source_status).toBe(
      "not_established",
    );
    expect(parsed.run.generic_cycle_simulation?.n5_observations).toEqual([]);
  });

  it.each([
    "unknown_version",
    "wrong_authority_purpose",
    "currentness_claimed",
    "publication_authority_claimed",
    "unknown_projection_member",
    "artifact_id_invalid",
    "checkpoint_v2_without_failed_branch",
    "checkpoint_v1_with_failure_shape",
    "child_node_ref_mismatch",
    "child_source_kind_mismatch",
    "child_context_kind_mismatch",
    "child_profile_kind_mismatch",
    "child_atom_refs_unsorted",
    "child_atom_refs_duplicate",
    "child_atom_refs_empty",
    "child_atom_refs_not_python_codepoint_sorted",
    "child_resolved_with_limitation",
    "child_not_established_without_limitation",
    "child_source_media_type_mismatch",
    "child_context_media_type_mismatch",
    "child_profile_media_type_mismatch",
    "n5_design_problem_node_mismatch",
    "n5_source_kind_mismatch",
    "n5_context_kind_mismatch",
    "n5_profile_kind_mismatch",
    "n5_input_kind_mismatch",
    "n5_source_media_type_mismatch",
    "n5_context_media_type_mismatch",
    "n5_profile_media_type_mismatch",
    "n5_input_media_type_mismatch",
    "n5_family_kind_mismatch",
    "n5_set_kind_mismatch",
    "n5_execution_kind_mismatch",
    "n5_result_kind_mismatch",
    "n5_family_media_type_mismatch",
    "n5_set_media_type_mismatch",
    "n5_execution_media_type_mismatch",
    "n5_result_media_type_mismatch",
    "n5_family_without_set",
    "n5_set_without_family",
    "n5_joint_simulated_without_result",
    "n5_joint_simulated_without_execution",
    "n5_request_resolved_without_hash",
    "n5_request_not_established_with_hash",
    "n8_resolved_without_request_binding",
    "n8_conditional_with_wrong_value_ref",
    "n8_conditional_resolved_with_limitation",
    "n8_conditional_unresolved_without_limitation",
    "n8_conditional_unresolved_with_value_ref",
    "n8_nonconditional_with_resolved_lineage",
    "projection_v2_without_credal_attempt",
    "projection_resolved_without_source_ref",
    "projection_resolved_without_source_hash",
    "projection_n4_resolved_without_parent_context",
    "projection_n4_resolved_with_limitation",
    "projection_child_resolved_without_family",
    "projection_child_resolved_without_set",
    "projection_child_resolved_without_rows",
    "projection_child_resolved_with_limitation",
    "projection_child_resolved_with_unresolved_row",
    "projection_child_not_established_without_limitation",
    "credal_attempt_without_v2",
    "credal_v2_without_status",
    "credal_v2_without_limitation",
    "credal_v2_with_resolved_child_status",
    "credal_v2_with_n5_rows",
    "credal_v2_wrong_attempt_ref_kind",
    "credal_v2_wrong_attempt_media_type",
    "refusal_with_source_hash",
    "refusal_with_n4_status",
    "refusal_with_child_rows",
    "refusal_with_n5_rows",
    "refusal_without_limitation",
  ])("rejects malformed supplied generic cycle projection: %s", (control) => {
    const payload = runDetailsPayload("projection only");
    const run = mutableRecord(payload.run);
    const credalControl = control.startsWith("credal_");
    const refusalControl = control.startsWith("refusal_");
    const projection = mutableRecord(
      credalControl
        ? genericCycleCredalProjection("run-projection-mask")
        : refusalControl
          ? genericCycleRefusalProjection("run-projection-mask")
          : genericCycleSimulationProjection("run-projection-mask"),
    );
    run.generic_cycle_simulation = projection;
    expect(runDetailsSchema.safeParse(payload).success).toBe(true);
    const childBinding = () =>
      firstMutableRecord(
        projection.child_profile_bindings,
        "child_profile_bindings",
      );
    const n5Observation = () =>
      firstMutableRecord(projection.n5_observations, "n5_observations");
    const recursiveCheckpoint = () =>
      mutableRecord(projection.recursive_cycle_checkpoint);
    if (control === "unknown_version") {
      projection.schema_version =
        "policyos.runtime.run_generic_cycle_simulation_projection.v3";
    } else if (control === "wrong_authority_purpose") {
      projection.authority_purpose = "publication_ready";
    } else if (control === "currentness_claimed") {
      projection.currentness_status = "current";
    } else if (control === "publication_authority_claimed") {
      projection.publication_authority = true;
    } else if (control === "unknown_projection_member") {
      mutableRecord(projection).unreviewed_status = "resolved";
    } else if (control === "artifact_id_invalid") {
      mutableRecord(projection.source_ref).artifact_id = "report/not-a-cas-ref";
    } else if (control === "checkpoint_v2_without_failed_branch") {
      recursiveCheckpoint().failed_branches = [];
    } else if (control === "checkpoint_v1_with_failure_shape") {
      recursiveCheckpoint().schema_version =
        "policyos.runtime.recursive_cycle_checkpoint.v1";
    } else if (control === "child_node_ref_mismatch") {
      childBinding().node_ref = "design-problem://different";
    } else if (control === "child_source_kind_mismatch") {
      mutableRecord(childBinding().source_ref).kind =
        "runtime.quality.n4_candidate_scenario_source";
    } else if (control === "child_context_kind_mismatch") {
      mutableRecord(childBinding().context_job_ref).kind =
        "runtime.context_job";
    } else if (control === "child_profile_kind_mismatch") {
      mutableRecord(childBinding().profile_ref).kind = "scenario.profile";
    } else if (control === "child_atom_refs_unsorted") {
      childBinding().source_atom_refs = ["atom-z", "atom-a"];
    } else if (control === "child_atom_refs_duplicate") {
      childBinding().source_atom_refs = ["atom-a", "atom-a"];
    } else if (control === "child_atom_refs_empty") {
      childBinding().source_atom_refs = [];
    } else if (control === "child_atom_refs_not_python_codepoint_sorted") {
      childBinding().source_atom_refs = ["\u{10000}", "\uE000"];
    } else if (control === "child_resolved_with_limitation") {
      childBinding().limitation_code = "unexpected_limitation";
    } else if (control === "child_not_established_without_limitation") {
      childBinding().historical_binding_status = "not_established";
      childBinding().limitation_code = null;
    } else if (control === "child_source_media_type_mismatch") {
      mutableRecord(childBinding().source_ref).media_type = "text/plain";
    } else if (control === "child_context_media_type_mismatch") {
      mutableRecord(childBinding().context_job_ref).media_type = "text/plain";
    } else if (control === "child_profile_media_type_mismatch") {
      mutableRecord(childBinding().profile_ref).media_type = "text/plain";
    } else if (control === "n5_design_problem_node_mismatch") {
      n5Observation().node_ref = "design-problem://different";
    } else if (control === "n5_source_kind_mismatch") {
      mutableRecord(n5Observation().n4_source_ref).kind =
        "runtime.quality.n4_candidate_scenario_source";
    } else if (control === "n5_context_kind_mismatch") {
      mutableRecord(n5Observation().context_job_ref).kind =
        "runtime.context_job";
    } else if (control === "n5_profile_kind_mismatch") {
      mutableRecord(n5Observation().profile_ref).kind = "scenario.profile";
    } else if (control === "n5_input_kind_mismatch") {
      mutableRecord(n5Observation().n5_input_ref).kind = "runtime.n5_input";
    } else if (control === "n5_source_media_type_mismatch") {
      mutableRecord(n5Observation().n4_source_ref).media_type = "text/plain";
    } else if (control === "n5_context_media_type_mismatch") {
      mutableRecord(n5Observation().context_job_ref).media_type = "text/plain";
    } else if (control === "n5_profile_media_type_mismatch") {
      mutableRecord(n5Observation().profile_ref).media_type = "text/plain";
    } else if (control === "n5_input_media_type_mismatch") {
      mutableRecord(n5Observation().n5_input_ref).media_type = "text/plain";
    } else if (control === "n5_family_kind_mismatch") {
      mutableRecord(n5Observation().child_profile_family_ref).kind =
        "runtime.family";
    } else if (control === "n5_set_kind_mismatch") {
      mutableRecord(n5Observation().child_profile_set_ref).kind =
        "runtime.profile_set";
    } else if (control === "n5_execution_kind_mismatch") {
      mutableRecord(n5Observation().n5_execution_ref).kind =
        "runtime.n5_execution";
    } else if (control === "n5_result_kind_mismatch") {
      mutableRecord(n5Observation().simulation_result_ref).kind =
        "runtime.simulation_result";
    } else if (control === "n5_family_media_type_mismatch") {
      mutableRecord(n5Observation().child_profile_family_ref).media_type =
        "text/plain";
    } else if (control === "n5_set_media_type_mismatch") {
      mutableRecord(n5Observation().child_profile_set_ref).media_type =
        "text/plain";
    } else if (control === "n5_execution_media_type_mismatch") {
      mutableRecord(n5Observation().n5_execution_ref).media_type = "text/plain";
    } else if (control === "n5_result_media_type_mismatch") {
      mutableRecord(n5Observation().simulation_result_ref).media_type =
        "text/plain";
    } else if (control === "n5_family_without_set") {
      n5Observation().child_profile_set_ref = null;
    } else if (control === "n5_set_without_family") {
      n5Observation().child_profile_family_ref = null;
    } else if (control === "n5_joint_simulated_without_result") {
      n5Observation().simulation_result_ref = null;
      n5Observation().n8_value_ref = null;
    } else if (control === "n5_joint_simulated_without_execution") {
      n5Observation().n5_execution_ref = null;
    } else if (control === "n5_request_resolved_without_hash") {
      n5Observation().n5_request_content_hash = null;
    } else if (control === "n5_request_not_established_with_hash") {
      n5Observation().n5_request_binding_status = "not_established";
    } else if (control === "n8_resolved_without_request_binding") {
      n5Observation().n5_request_binding_status = "not_established";
      n5Observation().n5_request_content_hash = null;
    } else if (control === "n8_conditional_with_wrong_value_ref") {
      n5Observation().n8_value_ref = "sha256:" + "c".repeat(64);
    } else if (control === "n8_conditional_resolved_with_limitation") {
      n5Observation().n8_limitation_code = "unexpected_limitation";
    } else if (control === "n8_conditional_unresolved_without_limitation") {
      n5Observation().n8_lineage_status = "not_established";
      n5Observation().n8_value_ref = null;
      n5Observation().n8_limitation_code = null;
    } else if (control === "n8_conditional_unresolved_with_value_ref") {
      n5Observation().n8_lineage_status = "not_established";
      n5Observation().n8_limitation_code =
        "generic_n5_request_binding_not_established";
    } else if (control === "n8_nonconditional_with_resolved_lineage") {
      n5Observation().n8_status = "value_ready";
    } else if (control === "projection_v2_without_credal_attempt") {
      projection.schema_version =
        "policyos.runtime.run_generic_cycle_simulation_projection.v2";
    } else if (control === "projection_resolved_without_source_ref") {
      projection.source_ref = null;
    } else if (control === "projection_resolved_without_source_hash") {
      projection.source_content_hash = null;
    } else if (control === "projection_n4_resolved_without_parent_context") {
      projection.parent_context_job_ref = null;
    } else if (control === "projection_n4_resolved_with_limitation") {
      projection.n4_source_limitation_code = "unexpected_limitation";
    } else if (control === "projection_child_resolved_without_family") {
      projection.child_profile_family_ref = null;
    } else if (control === "projection_child_resolved_without_set") {
      projection.child_profile_set_ref = null;
    } else if (control === "projection_child_resolved_without_rows") {
      projection.child_profile_bindings = [];
    } else if (control === "projection_child_resolved_with_limitation") {
      projection.child_profile_limitation_code = "unexpected_limitation";
    } else if (control === "projection_child_resolved_with_unresolved_row") {
      childBinding().historical_binding_status = "not_established";
      childBinding().limitation_code = "child_binding_not_established";
    } else if (
      control === "projection_child_not_established_without_limitation"
    ) {
      projection.child_profile_status = "not_established";
      projection.child_profile_limitation_code = null;
    } else if (control === "credal_attempt_without_v2") {
      projection.schema_version =
        "policyos.runtime.run_generic_cycle_simulation_projection.v1";
    } else if (control === "credal_v2_without_status") {
      projection.credal_source_status = null;
    } else if (control === "credal_v2_without_limitation") {
      projection.credal_source_limitation_code = null;
    } else if (control === "credal_v2_with_resolved_child_status") {
      projection.child_profile_status = "resolved";
    } else if (control === "credal_v2_with_n5_rows") {
      projection.n5_observations = genericCycleSimulationProjection(
        "run-projection-mask",
      ).n5_observations;
    } else if (control === "credal_v2_wrong_attempt_ref_kind") {
      mutableRecord(projection.credal_source_attempt_ref).kind =
        "runtime.source_attempt";
    } else if (control === "credal_v2_wrong_attempt_media_type") {
      mutableRecord(projection.credal_source_attempt_ref).media_type =
        "text/plain";
    } else if (control === "refusal_with_source_hash") {
      projection.source_content_hash = "sha256:" + "6".repeat(64);
    } else if (control === "refusal_with_n4_status") {
      projection.n4_source_status = "not_established";
    } else if (control === "refusal_with_child_rows") {
      projection.child_profile_bindings = genericCycleSimulationProjection(
        "run-projection-mask",
      ).child_profile_bindings;
    } else if (control === "refusal_with_n5_rows") {
      projection.n5_observations = genericCycleSimulationProjection(
        "run-projection-mask",
      ).n5_observations;
    } else if (control === "refusal_without_limitation") {
      projection.limitation_code = null;
    }
    run.generic_cycle_simulation = projection;

    const result = runDetailsSchema.safeParse(payload);
    expect(result.success).toBe(false);
    const scalarOnlyControls = new Set([
      "unknown_version",
      "wrong_authority_purpose",
      "currentness_claimed",
      "publication_authority_claimed",
      "unknown_projection_member",
      "artifact_id_invalid",
      "child_atom_refs_empty",
    ]);
    const hasGenericIssue =
      !result.success &&
      result.error.issues.some((issue) => issue.message.startsWith("generic_"));
    expect(scalarOnlyControls.has(control) || hasGenericIssue).toBe(true);
  });
  it("preserves Legal search mode and refusal on a freshly parsed response", () => {
    const factResult = {
      action_canon: "leave",
      audit_miss_prone: true,
      canonical_status: "canonicalized",
      condition_text_uk: "if approved",
      confidence: 0.95,
      confidence_breakdown_json: '{"source":0.95}',
      consistency_score: 0.9,
      constraint_type_canon: "employment",
      doc_family_id: "family-1",
      doc_id: "doc-1",
      doc_name: "Labor Law",
      doc_reestr_code: "R-1",
      effective_from: "2026-01-01",
      effective_to: "",
      empty_spo_retry_eligible: true,
      exception_text_uk: "except with consent",
      fact_id: "fact-1",
      fact_text: "An employee may take leave.",
      fused_confidence: 0.91,
      grounding_status: "exact_quote",
      hallucination_flags_json: "[]",
      jurisdiction: "UA",
      legal_unit_subtype: "article",
      norm_type: "obligation",
      norm_type_canon: "obligation",
      object_name: "employee",
      predicate: "may take",
      procedure_text_uk: "submit an application",
      provision_anchor: "article-17",
      provision_citation: "Article 17",
      quality_band: "high",
      reference_bearing: true,
      reference_resolution_status: "resolved",
      route_class: "direct",
      similarity: 0.88,
      source_quote_uk: "Працівник має право на відпустку.",
      structure_quality: "complete",
      subject_name: "employer",
      temporal_confidence: 0.84,
      temporal_provenance_json: '{"basis":"published"}',
      temporal_resolution_status: "resolved",
      temporal_source_kind: "law",
      temporal_source_scope: "UA",
      temporal_state: "current",
      threshold_bearing: true,
      thresholds_json: '{"days":14}',
      top_domain: "labor",
      trust_tier: "grounded_fact",
      version_id: "version-3",
    };
    const responsePayload = {
      meta: {
        request_id: "request-legal-search",
        generated_at: "2026-10-09T00:00:00Z",
        source_kinds: [],
      },
      query: "employment leave",
      results: [factResult],
      total: 1,
      search_mode: "text",
      vector_refusal_code: "query_profile_unavailable",
    };
    const response = lexSearchResponseSchema.parse(responsePayload);

    expect(response.search_mode).toBe("text");
    expect(response.vector_refusal_code).toBe("query_profile_unavailable");
    expect(response.results).toEqual([factResult]);

    const incompleteFactResult = { ...factResult } as Record<string, unknown>;
    delete incompleteFactResult.temporal_provenance_json;
    expect(
      lexSearchResponseSchema.safeParse({
        ...responsePayload,
        results: [incompleteFactResult],
      }).success,
    ).toBe(false);

    const vectorResponse = lexSearchResponseSchema.parse({
      meta: {
        request_id: "request-legal-vector-search",
        generated_at: "2026-10-09T00:00:00Z",
        source_kinds: [],
      },
      query: "employment leave",
      results: [],
      total: 0,
      search_mode: "vector",
      vector_refusal_code: null,
    });

    expect(vectorResponse.search_mode).toBe("vector");
    expect(vectorResponse.vector_refusal_code).toBeNull();
  });

  it("keeps optional Legal intent distinct from a supplied typed profile", () => {
    const textOnlyRequest = {
      query: "employment leave",
      top_k: 20,
      output_dir: "/tmp/legal",
    };
    const intent = {
      basis_kind: "legal_lex_facts_embedding",
      generation_id: "generation-legal-facts-1",
      inventory_json: '{"basis":{"basis_kind":"legal_lex_facts_embedding"}}',
    } as const;

    const missingIntent = lexSearchRequestSchema.parse(textOnlyRequest);
    expect(missingIntent.query_generation_intent).toBeUndefined();

    const typedIntent = lexSearchRequestSchema.parse({
      ...textOnlyRequest,
      query_generation_intent: [intent],
    });
    expect(typedIntent.query_generation_intent).toEqual([intent]);

    const emptyIntent = lexSearchRequestSchema.parse({
      ...textOnlyRequest,
      query_generation_intent: [],
    });
    expect(emptyIntent.query_generation_intent).toEqual([]);

    const malformedIntentResponse = lexSearchResponseSchema.parse({
      meta: {
        request_id: "request-legal-malformed-intent",
        generated_at: "2026-10-09T00:00:00Z",
        source_kinds: [],
      },
      query: "employment leave",
      results: [],
      total: 0,
      search_mode: "text",
      vector_refusal_code: "query_profile_malformed",
    });
    expect(malformedIntentResponse.search_mode).toBe("text");
    expect(malformedIntentResponse.vector_refusal_code).toBe(
      "query_profile_malformed",
    );
  });

  it("rejects malformed supplied Legal query intent shape", () => {
    const request = {
      query: "employment leave",
      top_k: 20,
      output_dir: "/tmp/legal",
    };
    const completeIntent = {
      basis_kind: "legal_lex_facts_embedding",
      generation_id: "generation-legal-facts-1",
      inventory_json: '{"basis":{"basis_kind":"legal_lex_facts_embedding"}}',
    };

    expect(
      lexSearchRequestSchema.safeParse({
        ...request,
        query_generation_intent: [
          { ...completeIntent, basis_kind: "unregistered_basis" },
        ],
      }).success,
    ).toBe(false);
    expect(
      lexSearchRequestSchema.safeParse({
        ...request,
        query_generation_intent: [
          {
            basis_kind: completeIntent.basis_kind,
            generation_id: "generation",
          },
        ],
      }).success,
    ).toBe(false);
  });

  it("requires the Legal response mode and an explicit refusal slot", () => {
    const response = {
      meta: {
        request_id: "request-legal-search",
        generated_at: "2026-10-09T00:00:00Z",
        source_kinds: [],
      },
      query: "employment leave",
      results: [],
      total: 0,
      search_mode: "text",
      vector_refusal_code: "query_profile_unavailable",
    };

    expect(
      lexSearchResponseSchema.safeParse({
        ...response,
        search_mode: undefined,
      }).success,
    ).toBe(false);
    expect(
      lexSearchResponseSchema.safeParse({
        ...response,
        search_mode: "semantic",
      }).success,
    ).toBe(false);
    expect(
      lexSearchResponseSchema.safeParse({
        ...response,
        vector_refusal_code: undefined,
      }).success,
    ).toBe(false);
  });

  it("keeps selected Legal search snapshots distinct from typed refusals", () => {
    const meta = {
      request_id: "request-legal-profile",
      generated_at: "2026-10-09T00:00:00Z",
      source_kinds: [],
    };
    const intent = {
      basis_kind: "legal_lex_facts_embedding",
      generation_id: "generation-legal-facts-1",
      inventory_json: '{"basis":{"basis_kind":"legal_lex_facts_embedding"}}',
    } as const;

    const available = lexSearchProfileResponseSchema.parse({
      meta,
      status: "available",
      output_dir: "/tmp/legal",
      query_generation_intent: [intent],
    });
    expect(available).toMatchObject({
      query_generation_intent: [intent],
      status: "available",
    });

    const refused = lexSearchProfileResponseSchema.parse({
      meta,
      status: "refused",
      output_dir: "/tmp/legal",
      refusal_code: "selected_generation_unavailable",
    });
    expect(refused.status).toBe("refused");

    expect(
      lexSearchProfileResponseSchema.safeParse({
        meta,
        status: "available",
        output_dir: "/tmp/legal",
        query_generation_intent: [],
      }).success,
    ).toBe(false);
    expect(
      lexSearchProfileResponseSchema.safeParse({
        meta,
        status: "refused",
        output_dir: "/tmp/legal",
        refusal_code: "query_profile_unavailable",
      }).success,
    ).toBe(false);
  });

  it("validates event-level producer costs while preserving unknown values", () => {
    const response = {
      meta: {
        request_id: "request-1",
        generated_at: "2026-10-09T00:00:00Z",
      },
      pipeline: {
        run_id: "run-1",
        source_kind: "core_run",
        total_attempts: 1,
        cost_usd: null,
        attempts: [
          {
            attempt: 1,
            status: "completed",
            steps: [
              {
                attempt: 1,
                agent: "drafter",
                action: "draft",
                status: "ok",
                cost_usd: null,
                cost_events: [
                  {
                    event_id: "provider:unknown",
                    origin_event_id: null,
                    cost_origin: "unknown",
                    amount: null,
                    cost_usd: null,
                    settlement_status: "unknown",
                    durability: "none",
                    receipts: [],
                    payload_digest: "sha256:unknown",
                    model: "model-a",
                    provider: "gateway-a",
                  },
                ],
              },
            ],
          },
        ],
      },
    };

    expect(runAgentsSchema.safeParse(response).success).toBe(true);
    const invalid: unknown = structuredClone(response);
    const invalidPipeline = mutableRecord(mutableRecord(invalid).pipeline);
    const attempts = invalidPipeline.attempts;
    if (!Array.isArray(attempts)) {
      throw new TypeError("expected attempts array");
    }
    const steps = mutableRecord(attempts[0]).steps;
    if (!Array.isArray(steps)) {
      throw new TypeError("expected pipeline steps array");
    }
    const events = mutableRecord(steps[0]).cost_events;
    if (!Array.isArray(events)) {
      throw new TypeError("expected cost events array");
    }
    const invalidEvent = mutableRecord(events[0]);
    invalidEvent.unexpected = true;
    expect(runAgentsSchema.safeParse(invalid).success).toBe(false);
  });

  it("rejects qualification copy that upgrades a pending epoch", () => {
    const qualification = {
      appointment_state: "unappointed",
      appointment_would_establish:
        "authority to qualify native semantic production, append its history head and permit overlay activation",
      appointment_would_not_establish: [
        "gap shape",
        "passport validity",
        "positive delta",
        "re-entry",
      ],
      authority_owner_ref: null,
      authority_role: "semantic epoch policy-admission qualifier",
      code: "policy_admission_missing",
      epoch_state: "pending_epoch_activation",
      status: "not_established",
    };
    const payload = {
      backlog: [],
      carrier_liveness: {},
      n13b_history: {
        admission: "not_reached",
        attempt_count: 5,
        epoch_qualification: qualification,
        execution_phase: "terminal",
        overlay_epoch_count: 0,
        quarantine: "raw_terminal",
        quarantine_count: 2,
        raw_response_count: 2,
        reentry: "deeper_terminal",
        response_admitted_count: 0,
        terminal_count: 5,
        world_growth: "no_growth",
      },
      schema_version: "policyos.runtime.acquisition_growth_projection.v1",
      structural_routes: [],
      summary: {
        actual_network_call_count: 18,
        backlog_count: 0,
        family_scorecard_count: 12,
        metric_resolution_count: 124,
        selected_record_count: 144,
        structural_route_count: 0,
      },
    };

    expect(acquisitionGrowthPayloadSchema.parse(payload)).toMatchObject(
      payload,
    );
    expect(() =>
      acquisitionGrowthPayloadSchema.parse({
        ...payload,
        n13b_history: {
          ...payload.n13b_history,
          epoch_qualification: {
            ...qualification,
            epoch_state: "active",
            status: "qualified",
          },
        },
      }),
    ).toThrow();
  });

  it("rejects forged acquisition hints on a strict structural route", () => {
    const base = {
      backlog: [],
      carrier_liveness: {},
      n13b_history: {
        admission: "not_reached",
        attempt_count: 0,
        epoch_qualification: {
          appointment_state: "unappointed",
          appointment_would_establish:
            "authority to qualify native semantic production, append its history head and permit overlay activation",
          appointment_would_not_establish: [
            "gap shape",
            "passport validity",
            "positive delta",
            "re-entry",
          ],
          authority_owner_ref: null,
          authority_role: "semantic epoch policy-admission qualifier",
          code: "policy_admission_missing",
          epoch_state: "pending_epoch_activation",
          status: "not_established",
        },
        execution_phase: "executing",
        overlay_epoch_count: 0,
        quarantine: "none",
        quarantine_count: 0,
        raw_response_count: 0,
        reentry: "not_established",
        response_admitted_count: 0,
        terminal_count: 0,
        world_growth: "not_established",
      },
      schema_version: "policyos.runtime.acquisition_growth_projection.v1",
      structural_routes: [
        {
          action_eligibility: "not_applicable",
          gap_class: "structural_gap",
          missing_link: "owner_relation_missing",
          route_class: "not_a_data_gap",
          route_id: "capstone:one",
          witness_kind: "estimand_binding_refusal",
        },
      ],
      summary: {
        actual_network_call_count: 0,
        backlog_count: 0,
        family_scorecard_count: 12,
        metric_resolution_count: 124,
        selected_record_count: 0,
        structural_route_count: 1,
      },
    };

    expect(acquisitionGrowthPayloadSchema.parse(base)).toMatchObject(base);
    expect(() =>
      acquisitionGrowthPayloadSchema.parse({
        ...base,
        structural_routes: [
          {
            ...base.structural_routes[0],
            available_catalog_rows: 99,
            cost: 1,
          },
        ],
      }),
    ).toThrow();
  });

  it("rejects a route collection whose row belongs to another run", () => {
    const route = {
      authority_badge: "behavioral_fixture_not_production",
      authority_capability: "producer_missing",
      cell_id: "cell-1",
      cost_basis: { total_amount: 100 },
      execution_capability: "producer_missing",
      external_nonclosures: [],
      planner_record_id: "planner-1",
      planner_report_hash: "sha256:planner",
      qualification_predicate: "not_established",
      qualification_reason: "policy_admission_missing",
      qualification_status: "pending_epoch_activation",
      recommended_strategy: "targeted_primary_data_collection",
      replay_pins: {
        compiled_content_hash: "sha256:compiled-content",
        compiled_ref: "sha256:compiled",
        cost_basis_hash: "sha256:cost",
        design_problem_ref: "sha256:problem",
        source_job_id: "job-1",
        terminal_event_id: "event-1",
      },
      route_id: "sha256:route",
      route_projection_hash: "sha256:route",
      route_status: "costed_actionable",
      run_id: "run-b",
      schema_version: "AcquisitionRouteProjection@1.0",
      tenant_id: "tenant-1",
      world_growth: "no_growth",
    };

    expect(() =>
      acquisitionRouteListResponseSchema.parse({
        routes: [route],
        run_id: "run-a",
      }),
    ).toThrow(/cross-bound/iu);
  });

  it.each(["terminal", "non_terminal", "not_established"] as const)(
    "preserves producer-owned run_terminality state %s",
    (runTerminality) => {
      const parsed = runsListSchema.parse(runsListPayload(runTerminality));

      expect(parsed.runs?.[0]?.run_terminality).toBe(runTerminality);
    },
  );

  it("rejects missing or novel run_terminality instead of inferring from status", () => {
    expect(runsListSchema.safeParse(runsListPayload(undefined)).success).toBe(
      false,
    );
    expect(
      runsListSchema.safeParse(runsListPayload("completed-looking")).success,
    ).toBe(false);
  });

  it("matches the canonical quantity output type bidirectionally", () => {
    expectTypeOf<
      z.output<typeof quantityValueSchema>
    >().toEqualTypeOf<QuantityValueOutput>();
    const quantity = canonicalQuantity();
    expect(quantityValueSchema.parse(quantity)).toEqual(quantity);
  });

  it("rejects quantity uncertainty that omits canonical owner fields", () => {
    const quantity = canonicalQuantity();

    expect(
      quantityValueSchema.safeParse({
        ...quantity,
        uncertainty: { ci_95: [40, 44] },
      }).success,
    ).toBe(false);
  });

  it("preserves canonical quantity uncertainty without client defaults", () => {
    const quantity = canonicalQuantity();

    expect(quantityValueSchema.parse(quantity).uncertainty).toEqual({
      ci_95: [40, 44],
      disputed: false,
      identifiability: "estimated",
    });
  });

  it("accepts a canonical quantity whose optional point is absent", () => {
    const { point: _point, ...quantityWithoutPoint } = canonicalQuantity();

    expect(quantityValueSchema.parse(quantityWithoutPoint)).not.toHaveProperty(
      "point",
    );
  });

  it.each(projectionMaskingCases)(
    "preserves producer projection state when labels contain $caseId evidence text",
    ({ label }) => {
      const parsed = runDetailsSchema.parse(runDetailsPayload(label));
      const projection = parsed.run.policy_design_case_projection as Record<
        string,
        unknown
      >;
      const diagnosticLabel =
        parsed.run.operator_diagnostic?.projection_labels?.[0];

      expect(projection.primary_state).toBe("projection_only");
      expect(projection.states).toEqual(["projection_only"]);
      expect(projection).not.toHaveProperty("fail_closed_codes");
      expect(diagnosticLabel).toMatchObject({
        authority: "projection_only",
        label,
        state: "projection_only",
      });
    },
  );

  it("preserves generated decision validity and rejects an unknown local substitute", () => {
    const payload = runDetailsPayload("projection only");
    payload.run.decision_validity_status = "review_required";

    expect(runDetailsSchema.parse(payload).run.decision_validity_status).toBe(
      "review_required",
    );

    payload.run.decision_validity_status = "replacement";
    expect(runDetailsSchema.safeParse(payload).success).toBe(false);
  });

  it("rejects a projection when generated closeout truth is missing", () => {
    const payload = runDetailsPayload("publishable");
    payload.run.policy_design_case_projection = {
      audience: "public",
      authority_role: "projection_only",
      closeout_truth: {
        status: "ready",
        verdict: "can_closeout",
        can_closeout: null,
      },
      labels: [
        {
          authority_role: "projection_only",
          label: "publishable",
          state: "publishable",
        },
      ],
      may_not_be_used_for: ["scorecard_authority"],
      primary_state: "publishable",
      projection_policy: "reads_policy_design_case_only",
      states: ["publishable", "projection_only"],
    };

    expect(runDetailsSchema.safeParse(payload).success).toBe(false);
  });

  it("preserves generated projection blockers and rejects malformed blocker fields", () => {
    const payload = runDetailsPayload("projection only");
    const projection = payload.run.policy_design_case_projection as {
      closeout_truth: Record<string, unknown>;
    };
    projection.closeout_truth.blockers = [
      {
        code: "future_owner_blocker",
        message: "Owner-supplied blocker message",
        owner: "future-owner",
        severity: "future-owner-severity",
      },
    ];

    expect(
      runDetailsSchema.parse(payload).run.policy_design_case_projection
        ?.closeout_truth.blockers,
    ).toEqual(projection.closeout_truth.blockers);

    projection.closeout_truth.blockers = [
      {
        code: "future_owner_blocker",
        message: "Owner-supplied blocker message",
        owner: 42,
      },
    ];
    expect(runDetailsSchema.safeParse(payload).success).toBe(false);
  });

  it("does not replace producer closeout truth from participation label text", () => {
    const payload = runDetailsPayload("projection only");
    payload.run.policy_design_case_projection = {
      ...projectionAuthorityCore(true),
      audience: "public",
      labels: [
        {
          authority_role: "projection_only",
          label: "projection only",
          state: "projection_only",
        },
      ],
      may_not_be_used_for: ["scorecard_authority"],
      participation_requirements: [
        {
          claim_id: "claim-preference",
          claim_use_requested: "prevalence",
          claim_use_allowed: "prevalence",
          source_kind: "llm_speculation",
          representativeness_class: "unknown",
          public_projection_effect: "supports_claim",
        },
      ],
    };

    const parsed = runDetailsSchema.parse(payload);
    const projection = parsed.run.policy_design_case_projection as Record<
      string,
      unknown
    >;

    expect(projection.closeout_truth).toMatchObject({
      can_closeout: true,
      status: "ready",
      verdict: "can_closeout",
    });
    expect(projection.primary_state).toBe("publishable");
    expect(projection).not.toHaveProperty("fail_closed_codes");
  });

  it("rejects human-decision gate semantic counterexamples", () => {
    expect(
      humanDecisionGateResponseSchema.safeParse(availableHumanDecisionGate())
        .success,
    ).toBe(true);

    const counterexamples: Array<() => unknown> = [
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.reasons = [
          {
            code: "DS9-DECISION-PRODUCER-MISSING",
            message: "Missing producer",
            status: "producer_missing",
          },
        ];
        candidate.reason_codes = ["DS9-DECISION-PRODUCER-MISSING"];
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.contestability = {
          ...candidate.contestability!,
          case_id: "case.other",
        };
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        const selector = mutableRecord(candidate.submission?.selector);
        selector.basis_digest = humanDecisionDigest("8");
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        const continuation = mutableRecord(candidate.continuation);
        continuation.action_kind = "search";
        const selector = mutableRecord(candidate.submission?.selector);
        selector.action_kind = "search";
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.submission!.allowed_decisions = [
          ...candidate.submission!.allowed_decisions,
          { action: "escalate", decision_modes: ["ordinary"] },
        ];
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.submission!.allowed_decisions[0]!.decision_modes = [
          "blocking",
        ];
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.submission!.allowed_decisions = [
          candidate.submission!.allowed_decisions[0]!,
          candidate.submission!.allowed_decisions[0]!,
        ];
        candidate.decision_request!.available_actions = ["approve", "approve"];
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.submission!.allowed_decisions = [];
        candidate.decision_request!.available_actions = [];
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.decision_request!.five_rights_binding.required_role =
          "principal";
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.decision_request!.five_rights_binding.decision_rights_matrix_ref =
          "pdc://s7/other-rights";
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.exposure.required_artifact_digests[1] =
          humanDecisionDigest("6");
        candidate.exposure.completed_artifact_digests[1] =
          humanDecisionDigest("6");
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.exposure.channel = "governed_review";
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.exposure.completed_artifact_digests = [];
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.exposure.completed_artifact_digests.push(
          humanDecisionDigest("6"),
        );
        return candidate;
      },
      () => {
        const candidate = structuredClone(availableHumanDecisionGate());
        candidate.mandate = null;
        return candidate;
      },
    ];

    for (const counterexample of counterexamples) {
      expect(
        humanDecisionGateResponseSchema.safeParse(counterexample()).success,
      ).toBe(false);
    }

    const repeated = structuredClone(availableHumanDecisionGate());
    repeated.decision_request!.five_rights_binding.required_information_refs = [
      repeated.exposure.required_artifact_digests[1]!,
      repeated.exposure.required_artifact_digests[1]!,
    ];
    repeated.exposure.required_artifact_digests.push(
      repeated.exposure.required_artifact_digests[1]!,
    );
    repeated.exposure.completed_artifact_digests.push(
      repeated.exposure.completed_artifact_digests[1]!,
    );
    expect(humanDecisionGateResponseSchema.safeParse(repeated).success).toBe(
      true,
    );
  });

  it.each(["Bad action", "a".repeat(121)])(
    "rejects PA2 action_kind outside the signed action grammar: %s",
    (actionKind) => {
      const candidate = structuredClone(availableHumanDecisionGate());
      mutableRecord(candidate.continuation).action_kind = actionKind;
      mutableRecord(candidate.submission?.selector).action_kind = actionKind;
      candidate.mandate!.action_kind = actionKind;

      expect(humanDecisionGateResponseSchema.safeParse(candidate).success).toBe(
        false,
      );
    },
  );

  it("rejects a production selector whose source and basis refs are not one signed CAS ref", () => {
    const basisRef = humanDecisionDigest("b");
    const productionCandidate = () => {
      const candidate = structuredClone(
        availableHumanDecisionGate(),
      ) as unknown as Record<string, unknown>;
      candidate.source_kind = "production_approval";
      candidate.source_ref = basisRef;
      mutableRecord(candidate.contestability).source_ref = basisRef;
      const continuation = mutableRecord(candidate.continuation);
      continuation.source_kind = "production_approval";
      continuation.source_ref = basisRef;
      continuation.basis_ref = basisRef;
      continuation.basis_digest = basisRef;
      delete continuation.action_kind;
      mutableRecord(candidate.submission).selector =
        structuredClone(continuation);
      return candidate;
    };

    expect(
      humanDecisionGateResponseSchema.safeParse(productionCandidate()).success,
    ).toBe(true);

    for (const changedField of ["basis_ref", "basis_digest"] as const) {
      const candidate = productionCandidate();
      const continuation = mutableRecord(candidate.continuation);
      continuation[changedField] = humanDecisionDigest("8");
      mutableRecord(candidate.submission).selector =
        structuredClone(continuation);

      expect(humanDecisionGateResponseSchema.safeParse(candidate).success).toBe(
        false,
      );
    }
  });

  it("rejects review-effectiveness reconciliation counterexamples", () => {
    expect(
      humanDecisionReviewEffectivenessSchema.safeParse(
        humanDecisionReviewEffectivenessFixture(),
      ).success,
    ).toBe(true);

    const counterexamples: Array<() => unknown> = [
      () =>
        humanDecisionReviewEffectivenessFixture({
          authoritative_for: ["review_effectiveness_measurement"],
        }),
      () =>
        humanDecisionReviewEffectivenessFixture({
          completed_human_decision_count: 0,
          exact_join_count: 1,
        }),
      () =>
        humanDecisionReviewEffectivenessFixture({
          coverage_status: "complete",
        }),
      () =>
        humanDecisionReviewEffectivenessFixture({
          review_count: 1,
          review_time_not_established_count: 1,
        }),
      () =>
        humanDecisionReviewEffectivenessFixture({
          reviewer_independence_rate: 1.01,
        }),
    ];

    for (const counterexample of counterexamples) {
      expect(
        humanDecisionReviewEffectivenessSchema.safeParse(counterexample())
          .success,
      ).toBe(false);
    }
  });
});

function canonicalQuantity() {
  return {
    lineage: {
      freshness: "current" as const,
      id: "lineage:decision-score",
      status: "verified" as const,
    },
    metric_id: "decision-score",
    point: 42,
    quantity_class: "decision" as const,
    time: null,
    uncertainty: {
      ci_95: [40, 44] as [number, number],
      disputed: false,
      identifiability: "estimated" as const,
    },
    unit: { code: "score", system: "unit" },
  };
}
