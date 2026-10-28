import type { QuantityValueOutput } from "@polisyos/runtime-api-client";
import type { z } from "zod";

import type { components } from "./types";
import { c41JointParentObservation } from "@/test/fixtures/c41JointParent";
import { runN5InteractionEvidenceFixture as n5InteractionEvidenceFixture } from "@/test/fixtures/runN5InteractionEvidence";
import {
  artifactContentSchema,
  artifactInspectorIntakeSchema,
  artifactSchemaSchema,
  humanDecisionGateResponseSchema,
  humanDecisionReviewEffectivenessSchema,
  lexSearchRequestSchema,
  lexSearchProfileResponseSchema,
  lexSearchResponseSchema,
  predictiveCalibrationResponseSchema,
  quantityValueSchema,
  runAgentsSchema,
  runDetailsSchema,
  runEvidenceContextSchema,
  runsListSchema,
} from "./validators";
import { runHteSelectedProjection } from "@/features/runs/domain/__test__/runExecutionHteFixtures";
import {
  acquisitionGrowthPayloadSchema,
  acquisitionRouteListResponseSchema,
} from "@/features/runs/api/acquisitionRouteValidators";
import {
  predictiveCalibrationResponseFixture,
  responseWithoutSelectedRunManifestProfile,
  responseWithUnknownAssociationAuthority,
  responseWithUnknownMetaAuthority,
} from "@/test/fixtures/predictiveCalibrationResponse";
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

function parentJointCandidateSimulationProjection(runId: string) {
  const artifactRef = (kind: string, digit: string) => ({
    artifact_id: `sha256:${digit.repeat(64)}`,
    kind,
    media_type: "application/json",
  });
  const parentAtomIds = [
    "atom_1111111111111111",
    "atom_2222222222222222",
    "atom_3333333333333333",
  ];
  const interactionAtomIds = ["atom-a", "atom-b", "atom-c"];
  const atomHashes = ["4", "5", "6"].map(
    (digit) => `sha256:${digit.repeat(64)}`,
  );
  const parentFrameRef = `sha256:${"d".repeat(64)}`;
  const evidence = n5InteractionEvidenceFixture();
  evidence.numeric_interaction = "additive";
  const interactionPairs: Array<[string, string]> = [
    ["atom-a", "atom-b"],
    ["atom-a", "atom-c"],
    ["atom-b", "atom-c"],
  ];
  evidence.interaction_terms = evidence.interaction_terms.map(
    (term, index) => ({
      ...term,
      atom_ids: interactionPairs[index]!,
    }),
  );
  const childRefs = ["child://a", "child://b", "child://c"];
  return {
    artifact_status: "resolved",
    authority_purpose: "candidate_observation_only",
    publication_authority: false,
    schema_version: "policyos.runtime.run_candidate_simulation_projection.v1",
    run_id: runId,
    source_ref: artifactRef("runtime.compiled_recursive_generation_cycle", "a"),
    source_content_hash: `sha256:${"b".repeat(64)}`,
    n5_observations: [
      {
        node_ref: "design-problem://parent",
        design_problem_ref: parentFrameRef,
        atom_ids: interactionAtomIds,
        selected_outcomes: ["outcome-a"],
        executed_steps: [0],
        replication_seeds: [41, 42],
        status: "joint_simulated",
        simulation_ref: `sha256:${"7".repeat(64)}`,
        simulation_result_ref: artifactRef(
          "polisyos.runtime.joint_simulation_result",
          "7",
        ),
        n4_source_ref: artifactRef(
          "runtime.quality.n4_candidate_scenario_source",
          "8",
        ),
        context_job_ref: artifactRef(
          "runtime.quality.cycle_substrate_context_job",
          "9",
        ),
        n5_input_ref: artifactRef(
          "runtime.quality.candidate_simulation_n5_input",
          "a",
        ),
        profile_config_ref: `runtime-config:candidate-simulation/fixture@${atomHashes[0]}`,
        profile_selection_ref: `sha256:${"c".repeat(64)}`,
        lineage_status: "resolved",
        lineage_limitation_code: null,
        currentness_status: "not_established",
        world_model_record_content_hash: `sha256:${"e".repeat(64)}`,
        k_world_ref_before: `sha256:${"e".repeat(64)}`,
        k_world_ref_after: `sha256:${"e".repeat(64)}`,
        authority_blockers: [],
        n5_interaction_evidence: evidence,
        n8_numeric_interaction: "additive",
        n8_numeric_interaction_basis:
          "finite_checked_model_point_estimate_only",
        n8_interaction_sampling_status: "estimated",
        n8_status: "value_pending_n8",
        n8_authority_blockers: ["joint_interaction_rule_not_established"],
        n8_joint_request_content_hash: `sha256:${"f".repeat(64)}`,
        n8_joint_world_model_record_ref: "world_model_record_parent",
        n8_joint_outcome_units: { "outcome-a": "synthetic_score" },
        n8_joint_parent_atom_ids: parentAtomIds,
        n8_joint_parent_atom_content_hashes: atomHashes,
        n8_parent_child_refs: childRefs,
        n8_parent_child_source_bindings: childRefs.map((childRef, index) => ({
          child_node_ref: childRef,
          child_design_problem_ref: parentFrameRef,
          n4_source_ref: artifactRef(
            "runtime.quality.n4_candidate_scenario_source",
            "8",
          ),
          context_job_ref: artifactRef(
            "runtime.quality.cycle_substrate_context_job",
            "9",
          ),
          n5_input_ref: artifactRef(
            "runtime.quality.candidate_simulation_n5_input",
            "a",
          ),
          n5_result_ref: artifactRef(
            "polisyos.runtime.joint_simulation_result",
            "7",
          ),
          profile_config_ref: `runtime-config:candidate-simulation/fixture@${atomHashes[index]}`,
          profile_selection_ref: `sha256:${"c".repeat(64)}`,
          source_intervention_id: interactionAtomIds[index],
          source_atom_id: parentAtomIds[index],
          source_atom_content_hash: atomHashes[index],
          source_problem_frame_ref: parentFrameRef,
          parent_atom_id: parentAtomIds[index],
          parent_atom_content_hash: atomHashes[index],
        })),
        n8_joint_scope_status: "resolved",
        n8_joint_scope_limitation_code: null,
        n8_joint_value_limitation_code:
          "joint_interaction_rule_not_established",
        n8_candidate_joint_selection_status: "resolved",
        n8_candidate_joint_selection_content_hash: "sha256:" + "f".repeat(64),
        n8_candidate_parent_atom_ids: parentAtomIds,
        n8_candidate_parent_atom_content_hashes: atomHashes,
        n8_candidate_parent_intervention_ids: interactionAtomIds,
        n8_candidate_parent_child_refs: childRefs,
        n8_candidate_joint_selection_limitation_code: null,
        n8_candidate_member_basis: "hypothetical_all_unique_n4_source_members",
        n8_source_candidate_relationship: "alternatives",
        n8_policy_composition_status: "not_established",
        n8_policy_composition_limitation_code:
          "n4_source_candidates_are_alternatives_not_authored_compound_design",
        n8_child_to_parent_refinement_status: "not_established",
        n8_child_to_parent_refinement_limitation_code:
          "child_to_parent_refinement_rule_not_established",
      },
    ],
  };
}

function genericCycleSimulationProjection(
  runId: string,
  jointAtomIds: readonly string[] = ["atom-a", "atom-b", "atom-c"],
) {
  const ref = (
    kind: string,
    suffix: string,
    manifest_profile_sha256?: string,
  ) => ({
    artifact_id: "sha256:" + suffix.repeat(64),
    kind,
    media_type: "application/json",
    ...(manifest_profile_sha256 ? { manifest_profile_sha256 } : {}),
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
    const selectedResultProfile = "sha256:" + "9".repeat(64);
    const resultRef =
      status === "joint_simulated"
        ? ref(
            "polisyos.runtime.joint_simulation_result",
            "5",
            selectedResultProfile,
          )
        : null;
    const resultBody =
      resultRef == null
        ? null
        : {
            schema_version:
              "policyos.runtime.run_generic_cycle_simulation_n5_result_body.v1",
            artifact_ref: resultRef,
            artifact_schema_name: "policyos.runtime.n5.joint_simulation_result",
            artifact_schema_version: "4.0.0",
            result_schema_version:
              "policyos.runtime.joint_simulation_horizon.v4",
            selected_manifest_profile_sha256: selectedResultProfile,
            world_model_record_ref: "sha256:" + "1".repeat(64),
            world_model_record_content_hash: "sha256:" + "6".repeat(64),
            atom_ids: [...jointAtomIds],
            selected_outcomes: ["outcome-a"],
            horizon: {
              start: 0,
              end: 0,
              step: 1,
              valid_time_role: "valid_time",
              transaction_time_role: "transaction_time",
              scenario_branch_policy: "hold_world_record_constant",
            },
            trajectories: [
              {
                run_level: "joint",
                atom_ids: [...jointAtomIds],
                points: [
                  {
                    step: 0,
                    outcomes: { "outcome-a": 0.75 },
                    effects: { "outcome-a": 0.25 },
                  },
                ],
              },
            ],
            uncertainty_kind: "K_sim",
            authority_purpose: "cycle_input_candidate_only",
            candidate_status: "candidate_unverified",
            currentness_status: "not_established",
            publication_authority: false,
          };
    return {
      atom_ids:
        status === "joint_simulated"
          ? [...jointAtomIds]
          : [`atom-${cycleIndex}`],
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
      n8_authority_blockers:
        status === "joint_simulated"
          ? [
              "n9_not_admitted",
              "interaction_numeric_classification_unsupported",
            ]
          : ["n9_not_admitted"],
      n5_interaction_evidence:
        status === "joint_simulated" ? n5InteractionEvidenceFixture() : null,
      n8_numeric_interaction:
        status === "joint_simulated" ? "unsupported" : null,
      n8_numeric_interaction_basis:
        status === "joint_simulated"
          ? "finite_checked_model_point_estimate_only"
          : null,
      n8_interaction_sampling_status:
        status === "joint_simulated" ? "estimated" : null,
      n8_limitation_code:
        status === "joint_simulated"
          ? null
          : "generic_n5_request_binding_not_established",
      n8_lineage_status:
        status === "joint_simulated" ? "resolved" : "not_established",
      n8_status:
        status === "joint_simulated" ? "value_conditional" : "value_pending_n8",
      n8_value_ref: resultRef?.artifact_id ?? null,
      node_ref: "design-problem://" + digest.repeat(64),
      profile_ref: profileRef,
      profile_selection_ref: "sha256:" + "e".repeat(64),
      publication_authority: false,
      selected_outcomes: status === "joint_simulated" ? ["outcome-a"] : [],
      executed_steps: status === "joint_simulated" ? [0] : [],
      replication_seeds: status === "joint_simulated" ? [41, 42] : [],
      simulation_result_ref: resultRef,
      simulation_result_body: resultBody,
      simulation_result_body_status:
        resultRef == null
          ? "not_applicable"
          : resultBody == null
            ? "not_established"
            : "resolved",
      simulation_result_body_limitation_code:
        resultRef != null && resultBody == null
          ? "generic_n5_result_body_request_binding_not_established"
          : null,
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
    n6_cycle_history_status: null,
    n6_cycle_history_limitation_code: null,
    n6_cycle_history: [],
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

function genericCycleN6HistoryEntry() {
  return {
    cycle_index: 1,
    design_problem_basis_ref: null,
    design_problem_ref: "sha256:" + "d".repeat(64),
    generation_cycle_run_terminal_status: "completed",
    grounding_current_valid: false,
    grounding_status: "grounding_gap",
    node_ref: "design-problem://" + "d".repeat(64),
    refinement_decision: "refine",
    search_iteration_status: "refined_shadow",
    selected_candidate_content_hash: "sha256:" + "e".repeat(64),
    selected_candidate_ref: "candidate://candidate-a",
    terminal_kind: "grounded_partial_admissible",
    value_authority_blockers: ["publication_not_admitted"],
    value_decision_grade: null,
    value_ref: null,
    value_status: "value_conditional",
    voi_next_action: "advance",
  };
}

function genericCycleN6Projection(runId: string, version: "v3" | "v4" = "v3") {
  const projection = mutableRecord(
    version === "v4"
      ? genericCycleCredalProjection(runId)
      : genericCycleSimulationProjection(runId),
  );
  projection.schema_version =
    version === "v3"
      ? "policyos.runtime.run_generic_cycle_simulation_projection.v3"
      : "policyos.runtime.run_generic_cycle_simulation_projection.v4";
  projection.n6_cycle_history_status = "resolved";
  projection.n6_cycle_history_limitation_code = null;
  projection.n6_cycle_history = [genericCycleN6HistoryEntry()];
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

function c41V5Payload() {
  const payload = runDetailsPayload("projection only");
  const projection = mutableRecord(
    genericCycleSimulationProjection("run-projection-mask"),
  );
  const first = firstMutableRecord(
    projection.n5_observations,
    "n5_observations",
  );
  first.n5_owner_join_status = "resolved";
  const limited = structuredClone(first);
  limited.candidate_id = "candidate-limited";
  limited.cycle_index = 1;
  limited.design_problem_ref = `sha256:${"8".repeat(64)}`;
  limited.node_ref = `design-problem://${"8".repeat(64)}`;
  limited.n5_execution_ref = null;
  limited.n5_owner_join_status = "unavailable";
  limited.n5_owner_join_limitation_code = "generic_n5_owner_view_absent";
  limited.n5_request_binding_status = "not_established";
  limited.n5_request_content_hash = null;
  limited.n8_lineage_status = "not_established";
  limited.n8_value_ref = null;
  limited.n8_limitation_code =
    "n5_execution_request_provenance_not_established";
  limited.n8_authority_blockers = [
    ...((limited.n8_authority_blockers as string[]) ?? []),
    "n5_execution_request_provenance_not_established",
  ];
  limited.authority_blockers = [
    ...((limited.authority_blockers as string[]) ?? []),
    "n5_execution_request_provenance_not_established",
  ];
  limited.simulation_result_body = null;
  limited.simulation_result_body_status = "not_established";
  limited.simulation_result_body_limitation_code =
    "generic_n5_result_body_request_binding_not_established";
  projection.n5_observations = [first, limited];
  projection.schema_version =
    "policyos.runtime.run_generic_cycle_simulation_projection.v5";
  projection.joint_parent_status = "resolved";
  projection.joint_parent_observations = [c41JointParentObservation()];
  mutableRecord(payload.run).generic_cycle_simulation = projection;
  return payload;
}

describe("runtime API validators", () => {
  it("parses a v5 parent assessment separately from mixed child owner outcomes", () => {
    const parsed = runDetailsSchema.parse(c41V5Payload());
    const projection = parsed.run.generic_cycle_simulation;
    expect(projection?.schema_version).toBe(
      "policyos.runtime.run_generic_cycle_simulation_projection.v5",
    );
    expect(
      projection?.n5_observations.map((row) => row.n5_owner_join_status),
    ).toEqual(["resolved", "unavailable"]);
    expect(projection?.n5_observations[1]?.status).toBe("joint_simulated");
    expect(projection?.n5_observations[1]?.authority_blockers).toContain(
      "n5_execution_request_provenance_not_established",
    );
    expect(projection?.joint_parent_status).toBe("resolved");
    expect(projection?.joint_parent_observations?.[0]).toMatchObject({
      n8_status: "value_conditional",
      n8_candidate_decision_grade: "low",
      n8_joint_scope_status: "not_established",
      n8_source_candidate_relationship: "alternatives",
      n8_policy_composition_status: "not_established",
    });
    expect(
      projection?.joint_parent_observations?.[0]?.n5_interaction_evidence
        ?.higher_order_residuals["outcome-a"]?.["0"],
    ).toBe(1);
    expect(projection?.publication_authority).toBe(false);
  });

  it("retains v5 parent unavailability with its limitation and successful child", () => {
    const payload = c41V5Payload();
    const projection = mutableRecord(
      mutableRecord(payload.run).generic_cycle_simulation,
    );
    projection.joint_parent_status = "not_established";
    projection.joint_parent_observations = [];
    projection.joint_parent_limitation_code =
      "generic_joint_parent_result_not_established";
    const parsed = runDetailsSchema.parse(payload).run.generic_cycle_simulation;
    expect(parsed?.joint_parent_status).toBe("not_established");
    expect(parsed?.joint_parent_limitation_code).toBe(
      "generic_joint_parent_result_not_established",
    );
    expect(parsed?.n5_observations[0]?.n5_owner_join_status).toBe("resolved");
  });

  it("retains a refused owner-conflict row alongside a resolved sibling", () => {
    const payload = c41V5Payload();
    const projection = mutableRecord(
      mutableRecord(payload.run).generic_cycle_simulation,
    );
    const rows = projection.n5_observations as Record<string, unknown>[];
    const conflict = rows[1]!;
    conflict.n5_execution_ref = rows[0]!.n5_execution_ref;
    conflict.n5_owner_join_status = "mismatch";
    conflict.n5_owner_join_limitation_code =
      "generic_n5_execution_cycle_join_mismatch";
    conflict.status = "simulation_blocked";
    conflict.n8_status = "value_blocked";
    conflict.n8_limitation_code = "n5_execution_request_provenance_conflict";
    conflict.n5_interaction_evidence = null;
    conflict.n8_numeric_interaction = null;
    conflict.n8_numeric_interaction_basis = null;
    conflict.n8_interaction_sampling_status = null;
    conflict.atom_ids = [];
    conflict.selected_outcomes = [];
    conflict.executed_steps = [];
    conflict.replication_seeds = [];
    const parsed = runDetailsSchema.parse(payload).run.generic_cycle_simulation;
    expect(
      parsed?.n5_observations.map((row) => row.n5_owner_join_status),
    ).toEqual(["resolved", "mismatch"]);
    expect(parsed?.n5_observations[1]?.status).toBe("simulation_blocked");
    expect(parsed?.n5_observations[1]?.n8_status).toBe("value_blocked");
  });

  it("accepts the v5 owner-join extension even without a parent joint row", () => {
    const payload = c41V5Payload();
    const projection = mutableRecord(
      mutableRecord(payload.run).generic_cycle_simulation,
    );
    delete projection.joint_parent_status;
    delete projection.joint_parent_observations;
    const parsed = runDetailsSchema.parse(payload).run.generic_cycle_simulation;
    expect(parsed?.schema_version).toBe(
      "policyos.runtime.run_generic_cycle_simulation_projection.v5",
    );
    expect(parsed?.n5_observations[0]?.n5_owner_join_status).toBe("resolved");
    expect(parsed?.joint_parent_status).toBeUndefined();
  });

  it.each([
    "v1_with_new_extension",
    "v5_without_extension",
    "resolved_owner_missing_execution",
    "limited_owner_missing_reason",
    "mismatch_with_unblocked_row",
    "resolved_parent_blocked",
    "resolved_parent_missing_result",
    "parent_missing_selection",
    "conditional_parent_missing_grade",
    "conditional_parent_wrong_ref",
    "conditional_parent_missing_provenance",
    "parent_claims_authority",
    "parent_residual_removed_with_markers",
  ])("refuses contradictory v5 candidate status or evidence: %s", (control) => {
    const payload = c41V5Payload();
    const projection = mutableRecord(
      mutableRecord(payload.run).generic_cycle_simulation,
    );
    const children = projection.n5_observations as Record<string, unknown>[];
    const first = children[0]!;
    const limited = children[1]!;
    const parent = firstMutableRecord(
      projection.joint_parent_observations,
      "joint_parent_observations",
    );
    if (control === "v1_with_new_extension") {
      projection.schema_version =
        "policyos.runtime.run_generic_cycle_simulation_projection.v1";
    } else if (control === "v5_without_extension") {
      delete projection.joint_parent_status;
      delete projection.joint_parent_observations;
      limited.n5_execution_ref = first.n5_execution_ref;
      for (const child of children) {
        delete child.n5_owner_join_status;
        delete child.n5_owner_join_limitation_code;
      }
    } else if (control === "resolved_owner_missing_execution") {
      first.n5_execution_ref = null;
    } else if (control === "limited_owner_missing_reason") {
      delete limited.n5_owner_join_limitation_code;
    } else if (control === "mismatch_with_unblocked_row") {
      limited.n5_execution_ref = first.n5_execution_ref;
      limited.n5_owner_join_status = "mismatch";
    } else if (control === "resolved_parent_blocked") {
      parent.status = "simulation_blocked";
    } else if (control === "resolved_parent_missing_result") {
      parent.simulation_result_ref = null;
    } else if (control === "parent_missing_selection") {
      delete parent.n8_candidate_joint_selection_status;
    } else if (control === "conditional_parent_missing_grade") {
      delete parent.n8_candidate_decision_grade;
    } else if (control === "conditional_parent_wrong_ref") {
      parent.n8_candidate_value_ref = `sha256:${"0".repeat(64)}`;
    } else if (control === "conditional_parent_missing_provenance") {
      parent.n8_authority_blockers = (
        parent.n8_authority_blockers as string[]
      ).filter(
        (code) => code !== "n5_execution_request_provenance_not_established",
      );
    } else if (control === "parent_claims_authority") {
      projection.publication_authority = true;
    } else {
      const evidence = mutableRecord(parent.n5_interaction_evidence);
      evidence.higher_order_residuals = {};
      evidence.higher_order_residual_sampling = {};
    }
    expect(runDetailsSchema.safeParse(payload).success).toBe(false);
  });

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
          old_candidate_id: "candidate-after",
          new_candidate_id: "candidate-after",
          new_candidate_source_ref: {
            artifact_id: `sha256:${"e".repeat(64)}`,
            kind: "runtime.quality.n4_candidate_scenario_source",
            media_type: "application/json",
            manifest_profile_sha256: "sha256:" + "a".repeat(64),
          },
          origin_source_ref: {
            artifact_id: "sha256:" + "f".repeat(64),
            kind: "runtime.quality.n4_candidate_scenario_source",
            media_type: "application/json",
            manifest_profile_sha256: "sha256:" + "b".repeat(64),
          },
          expected_origin_source_ref: {
            artifact_id: "sha256:" + "f".repeat(64),
            kind: "runtime.quality.n4_candidate_scenario_source",
            media_type: "application/json",
            manifest_profile_sha256: "sha256:" + "b".repeat(64),
          },
          schema_version:
            "policyos.runtime.run_candidate_simulation_acquisition_history.v2",
          reentry_receipt_schema_version:
            "policyos.runtime.acquisition_overlay_reentry.v3",
          continuation_join_status: "v3_occurrence_joined",
          origin_source_binding_status: "verified_same_candidate_root",
          currentness_status: "not_established",
          authority_purpose: "candidate_observation_only",
          publication_authority: false,
          continuation: {
            source_generation_run_content_hash: `sha256:${"1".repeat(64)}`,
            continued_generation_run_content_hash: `sha256:${"2".repeat(64)}`,
            source_cycle_index: 1,
            continued_cycle_index: 2,
            previous_n4_source_ref: {
              artifact_id: `sha256:${"6".repeat(64)}`,
              kind: "runtime.quality.n4_candidate_scenario_source",
              media_type: "application/json",
            },
            previous_n5_input_ref: {
              artifact_id: `sha256:${"7".repeat(64)}`,
              kind: "runtime.quality.candidate_simulation_n5_input",
              media_type: "application/json",
            },
            selected_n4_source_ref: {
              artifact_id: `sha256:${"e".repeat(64)}`,
              kind: "runtime.quality.n4_candidate_scenario_source",
              media_type: "application/json",
              manifest_profile_sha256: "sha256:" + "a".repeat(64),
            },
            selected_n5_input_ref: {
              artifact_id: `sha256:${"8".repeat(64)}`,
              kind: "runtime.quality.candidate_simulation_n5_input",
              media_type: "application/json",
            },
            previous_profile_selection_ref: `sha256:${"9".repeat(64)}`,
            previous_profile_content_hash: `sha256:${"d".repeat(64)}`,
            selected_profile_selection_ref: `sha256:${"9".repeat(64)}`,
            selected_profile_content_hash: `sha256:${"a".repeat(64)}`,
            selected_target_world_slot: "government.balance",
            previous_selected_target_baseline_hash: `sha256:${"b".repeat(64)}`,
            selected_target_baseline_hash: `sha256:${"c".repeat(64)}`,
            source_currentness_status: "not_established",
            source_currentness_reason: "n6_census_issuer_not_appointed",
            continuation_currentness_status: "not_established",
            continuation_currentness_reason: "n6_census_issuer_not_appointed",
            n9_status: "not_promoted",
            n9_reason: "generation_cycle_n6_census_not_established",
            n9_certified_candidate_ids: [],
            current_candidate_occurrences: [
              {
                candidate_id: "candidate-after",
                cycle_index: 2,
                content_hash: `sha256:${"a".repeat(64)}`,
                source_content_hash: null,
                front: "research",
                certified_by_n9: false,
              },
            ],
            current_fronts: {
              decision_candidate_ids: [],
              research_candidate_ids: ["candidate-after"],
              quarantine_candidate_ids: [],
              portfolio_candidate_ids: [],
            },
            currentness_status: "not_established",
            authority_purpose: "candidate_observation_only",
            publication_authority: false,
          },
        },
      ],
    };

    const parsed = runDetailsSchema.parse(payload);

    expect(parsed.run.candidate_simulation?.acquisition_history).toHaveLength(
      1,
    );
    expect(
      parsed.run.candidate_simulation?.acquisition_history?.[0]
        ?.expected_origin_source_ref,
    ).toMatchObject({
      artifact_id: "sha256:" + "f".repeat(64),
      manifest_profile_sha256: "sha256:" + "b".repeat(64),
    });
    expect(
      parsed.run.candidate_simulation?.acquisition_history?.[0]
        ?.currentness_status,
    ).toBe("not_established");

    const malformedJoin = structuredClone(payload);
    const malformedJoinEntry = firstMutableRecord(
      mutableRecord(mutableRecord(malformedJoin.run).candidate_simulation)
        .acquisition_history,
      "acquisition_history",
    );
    malformedJoinEntry.continuation_join_status = "legacy_occurrence_unbound";
    expect(() => runDetailsSchema.parse(malformedJoin)).toThrow(
      "candidate_acquisition_receipt_join_status_invalid",
    );
    const callerLabeledRoot = structuredClone(payload);
    const callerLabeledEntry = firstMutableRecord(
      mutableRecord(mutableRecord(callerLabeledRoot.run).candidate_simulation)
        .acquisition_history,
      "acquisition_history",
    );
    callerLabeledEntry.origin_source_binding_status = "observed_only";
    expect(() => runDetailsSchema.parse(callerLabeledRoot)).toThrow(
      "candidate_acquisition_receipt_join_status_invalid",
    );
    const missingV3Continuation = structuredClone(payload);
    const missingContinuationEntry = firstMutableRecord(
      mutableRecord(
        mutableRecord(missingV3Continuation.run).candidate_simulation,
      ).acquisition_history,
      "acquisition_history",
    );
    delete missingContinuationEntry.continuation;
    expect(() => runDetailsSchema.parse(missingV3Continuation)).toThrow(
      "candidate_acquisition_receipt_join_status_invalid",
    );

    const legacyMissingMetadata = structuredClone(payload);
    const legacyEntry = firstMutableRecord(
      mutableRecord(
        mutableRecord(legacyMissingMetadata.run).candidate_simulation,
      ).acquisition_history,
      "acquisition_history",
    );
    delete legacyEntry.expected_origin_source_ref;
    delete legacyEntry.schema_version;
    delete legacyEntry.reentry_receipt_schema_version;
    delete legacyEntry.continuation_join_status;
    delete legacyEntry.origin_source_binding_status;
    const parsedLegacy = runDetailsSchema.parse(legacyMissingMetadata);
    expect(
      parsedLegacy.run.candidate_simulation?.acquisition_history?.[0]
        ?.schema_version,
    ).toBeUndefined();

    const missingExpectedOrigin = structuredClone(payload);
    const missingExpectedEntry = firstMutableRecord(
      mutableRecord(
        mutableRecord(missingExpectedOrigin.run).candidate_simulation,
      ).acquisition_history,
      "acquisition_history",
    );
    delete missingExpectedEntry.expected_origin_source_ref;
    expect(() => runDetailsSchema.parse(missingExpectedOrigin)).toThrow(
      "candidate_acquisition_same_candidate_origin_binding_invalid",
    );
    const wrongOriginProfile = structuredClone(payload);
    const wrongOriginEntry = firstMutableRecord(
      mutableRecord(mutableRecord(wrongOriginProfile.run).candidate_simulation)
        .acquisition_history,
      "acquisition_history",
    );
    mutableRecord(wrongOriginEntry.origin_source_ref).manifest_profile_sha256 =
      "sha256:" + "c".repeat(64);
    expect(() => runDetailsSchema.parse(wrongOriginProfile)).toThrow(
      "candidate_acquisition_same_candidate_origin_binding_invalid",
    );
    const wrongSelectedN4Profile = structuredClone(payload);
    const wrongSelectedEntry = firstMutableRecord(
      mutableRecord(
        mutableRecord(wrongSelectedN4Profile.run).candidate_simulation,
      ).acquisition_history,
      "acquisition_history",
    );
    mutableRecord(
      mutableRecord(wrongSelectedEntry.continuation).selected_n4_source_ref,
    ).manifest_profile_sha256 = "sha256:" + "c".repeat(64);
    expect(() => runDetailsSchema.parse(wrongSelectedN4Profile)).toThrow(
      "candidate_acquisition_continuation_source_binding_invalid",
    );
    const unjoinedCandidate = structuredClone(payload);
    const unjoinedEntry = firstMutableRecord(
      mutableRecord(mutableRecord(unjoinedCandidate.run).candidate_simulation)
        .acquisition_history,
      "acquisition_history",
    );
    unjoinedEntry.old_candidate_id = "candidate-not-in-continuation";
    unjoinedEntry.new_candidate_id = "candidate-not-in-continuation";
    expect(() => runDetailsSchema.parse(unjoinedCandidate)).toThrow(
      "candidate_acquisition_continuation_candidate_missing",
    );
    const differentCandidateWithExpectedOrigin = structuredClone(payload);
    const differentCandidateEntry = firstMutableRecord(
      mutableRecord(
        mutableRecord(differentCandidateWithExpectedOrigin.run)
          .candidate_simulation,
      ).acquisition_history,
      "acquisition_history",
    );
    differentCandidateEntry.old_candidate_id = "candidate-before";
    expect(() =>
      runDetailsSchema.parse(differentCandidateWithExpectedOrigin),
    ).toThrow("candidate_acquisition_expected_origin_without_same_candidate");
    const targetNoOp = structuredClone(payload);
    const targetNoOpRun = mutableRecord(targetNoOp.run);
    const targetNoOpCandidate = mutableRecord(
      targetNoOpRun.candidate_simulation,
    );
    const targetNoOpHistory =
      targetNoOpCandidate.acquisition_history as unknown[];
    const targetNoOpEntry = mutableRecord(targetNoOpHistory[0]);
    const targetNoOpContinuation = mutableRecord(targetNoOpEntry.continuation);
    targetNoOpContinuation.selected_target_baseline_hash =
      targetNoOpContinuation.previous_selected_target_baseline_hash;
    expect(() => runDetailsSchema.parse(targetNoOp)).toThrow(
      "run_candidate_simulation_continuation_projection_invalid",
    );

    const wrongFront = structuredClone(payload);
    const wrongFrontRun = mutableRecord(wrongFront.run);
    const wrongFrontCandidate = mutableRecord(
      wrongFrontRun.candidate_simulation,
    );
    const wrongFrontHistory =
      wrongFrontCandidate.acquisition_history as unknown[];
    const wrongFrontEntry = mutableRecord(wrongFrontHistory[0]);
    const wrongFrontContinuation = mutableRecord(wrongFrontEntry.continuation);
    const occurrences = mutableRecord(wrongFrontContinuation)
      .current_candidate_occurrences as unknown[];
    mutableRecord(occurrences[0]).front = "decision";
    expect(() => runDetailsSchema.parse(wrongFront)).toThrow(
      "run_candidate_simulation_continuation_projection_invalid",
    );

    const swappedSource = structuredClone(payload);
    const swappedRun = mutableRecord(swappedSource.run);
    const swappedCandidate = mutableRecord(swappedRun.candidate_simulation);
    const swappedHistory = swappedCandidate.acquisition_history as unknown[];
    const swappedEntry = mutableRecord(swappedHistory[0]);
    const swappedContinuation = mutableRecord(swappedEntry.continuation);
    const previousN5 = mutableRecord(
      mutableRecord(swappedContinuation).previous_n5_input_ref,
    );
    const selectedN5 = mutableRecord(
      mutableRecord(swappedContinuation).selected_n5_input_ref,
    );
    selectedN5.artifact_id = previousN5.artifact_id;
    expect(() => runDetailsSchema.parse(swappedSource)).toThrow(
      "candidate_acquisition_same_candidate_continuation_binding_invalid",
    );
  });

  it("keeps additive evidence pending when parent coupling scope is absent", () => {
    const payload = runDetailsPayload("projection only");
    const run = mutableRecord(payload.run);
    const projection =
      parentJointCandidateSimulationProjection("run-parent-n8");
    const observation = firstMutableRecord(
      projection.n5_observations,
      "n5_observations",
    );
    observation.n8_authority_blockers = [
      "parent_joint_coupling_evidence_not_established",
    ];
    observation.n8_joint_outcome_units = {};
    observation.n8_joint_parent_atom_ids = [];
    observation.n8_joint_parent_atom_content_hashes = [];
    observation.n8_parent_child_refs = [];
    observation.n8_parent_child_source_bindings = [];
    observation.n8_joint_scope_status = "not_established";
    observation.n8_joint_scope_limitation_code =
      "parent_joint_coupling_evidence_not_established";
    observation.n8_joint_value_limitation_code = null;
    run.candidate_simulation = projection;

    const parsed = runDetailsSchema.parse(payload);
    expect(parsed.run.candidate_simulation?.n5_observations[0]).toMatchObject({
      n8_numeric_interaction: "additive",
      n8_status: "value_pending_n8",
      n8_joint_scope_status: "not_established",
      n8_joint_scope_limitation_code:
        "parent_joint_coupling_evidence_not_established",
      n8_joint_value_limitation_code: null,
      n8_candidate_joint_selection_status: "resolved",
      n8_candidate_member_basis: "hypothetical_all_unique_n4_source_members",
      n8_source_candidate_relationship: "alternatives",
      n8_policy_composition_status: "not_established",
      n8_child_to_parent_refinement_status: "not_established",
    });
    const parsedObservation =
      parsed.run.candidate_simulation?.n5_observations[0];
    expect(
      parsedObservation?.n5_interaction_evidence?.interaction_terms.map(
        (term) => term.atom_ids,
      ),
    ).toEqual([
      ["atom-a", "atom-b"],
      ["atom-a", "atom-c"],
      ["atom-b", "atom-c"],
    ]);
    expect(
      parsedObservation?.n5_interaction_evidence?.interaction_terms.map(
        (term) => term.replication_sampling_by_step["0"],
      ),
    ).toEqual([
      {
        status: "estimated",
        replicate_count: 2,
        seeds: [41, 42],
        samples: [
          { seed: 41, value: 0 },
          { seed: 42, value: 0 },
        ],
        mean: 0,
        standard_error: 0,
      },
      {
        status: "estimated",
        replicate_count: 2,
        seeds: [41, 42],
        samples: [
          { seed: 41, value: 0 },
          { seed: 42, value: 0 },
        ],
        mean: 0,
        standard_error: 0,
      },
      {
        status: "estimated",
        replicate_count: 2,
        seeds: [41, 42],
        samples: [
          { seed: 41, value: 0 },
          { seed: 42, value: 0 },
        ],
        mean: 0,
        standard_error: 0,
      },
    ]);
    expect(
      parsedObservation?.n5_interaction_evidence
        ?.higher_order_residual_sampling["outcome-a"]?.["0"],
    ).toMatchObject({
      status: "estimated",
      seeds: [41, 42],
      samples: [
        { seed: 41, value: 1 },
        { seed: 42, value: -1 },
      ],
      mean: 0,
      standard_error: 1,
    });

    const removedCandidateBasis = mutableRecord(
      parentJointCandidateSimulationProjection("run-parent-n8"),
    );
    const removedCandidateObservation = firstMutableRecord(
      removedCandidateBasis.n5_observations,
      "n5_observations",
    );
    removedCandidateObservation.n8_candidate_member_basis = null;
    const removedCandidatePayload = runDetailsPayload("projection only");
    mutableRecord(removedCandidatePayload.run).candidate_simulation =
      removedCandidateBasis;
    expect(runDetailsSchema.safeParse(removedCandidatePayload).success).toBe(
      false,
    );

    const falselyComposed = mutableRecord(
      parentJointCandidateSimulationProjection("run-parent-n8"),
    );
    const falselyComposedObservation = firstMutableRecord(
      falselyComposed.n5_observations,
      "n5_observations",
    );
    falselyComposedObservation.n8_policy_composition_status = "resolved";
    const falselyComposedPayload = runDetailsPayload("projection only");
    mutableRecord(falselyComposedPayload.run).candidate_simulation =
      falselyComposed;
    expect(runDetailsSchema.safeParse(falselyComposedPayload).success).toBe(
      false,
    );

    const removedBinding = mutableRecord(
      parentJointCandidateSimulationProjection("run-parent-n8"),
    );
    const removedObservation = firstMutableRecord(
      removedBinding.n5_observations,
      "n5_observations",
    );
    const childBindings = removedObservation.n8_parent_child_source_bindings;
    if (!Array.isArray(childBindings))
      throw new TypeError("expected child source bindings");
    removedObservation.n8_parent_child_source_bindings = childBindings.slice(1);
    const removedPayload = runDetailsPayload("projection only");
    mutableRecord(removedPayload.run).candidate_simulation = removedBinding;
    expect(runDetailsSchema.safeParse(removedPayload).success).toBe(false);

    const foreignFrame = mutableRecord(
      parentJointCandidateSimulationProjection("run-parent-n8"),
    );
    const foreignObservation = firstMutableRecord(
      foreignFrame.n5_observations,
      "n5_observations",
    );
    const foreignBindings = foreignObservation.n8_parent_child_source_bindings;
    if (!Array.isArray(foreignBindings))
      throw new TypeError("expected child source bindings");
    mutableRecord(foreignBindings[0]).source_problem_frame_ref =
      `sha256:${"0".repeat(64)}`;
    const foreignPayload = runDetailsPayload("projection only");
    mutableRecord(foreignPayload.run).candidate_simulation = foreignFrame;
    expect(runDetailsSchema.safeParse(foreignPayload).success).toBe(false);

    const mismatchedSelectedAxes = mutableRecord(
      parentJointCandidateSimulationProjection("run-parent-n8"),
    );
    const mismatchedObservation = firstMutableRecord(
      mismatchedSelectedAxes.n5_observations,
      "n5_observations",
    );
    mismatchedObservation.atom_ids = ["atom-0"];
    const mismatchedPayload = runDetailsPayload("projection only");
    mutableRecord(mismatchedPayload.run).candidate_simulation =
      mismatchedSelectedAxes;
    expect(runDetailsSchema.safeParse(mismatchedPayload).success).toBe(false);

    const removedPair = mutableRecord(
      parentJointCandidateSimulationProjection("run-parent-n8"),
    );
    const removedPairObservation = firstMutableRecord(
      removedPair.n5_observations,
      "n5_observations",
    );
    const interactionEvidence = mutableRecord(
      removedPairObservation.n5_interaction_evidence,
    );
    if (!Array.isArray(interactionEvidence.interaction_terms)) {
      throw new TypeError("expected interaction terms");
    }
    interactionEvidence.interaction_terms =
      interactionEvidence.interaction_terms.slice(1);
    const removedPairPayload = runDetailsPayload("projection only");
    mutableRecord(removedPairPayload.run).candidate_simulation = removedPair;
    expect(runDetailsSchema.safeParse(removedPairPayload).success).toBe(false);

    const removedResidual = mutableRecord(
      parentJointCandidateSimulationProjection("run-parent-n8"),
    );
    const removedResidualObservation = firstMutableRecord(
      removedResidual.n5_observations,
      "n5_observations",
    );
    const evidenceWithRemovedResidual = mutableRecord(
      removedResidualObservation.n5_interaction_evidence,
    );
    evidenceWithRemovedResidual.higher_order_residual_sampling = {};
    const removedResidualPayload = runDetailsPayload("projection only");
    mutableRecord(removedResidualPayload.run).candidate_simulation =
      removedResidual;
    expect(runDetailsSchema.safeParse(removedResidualPayload).success).toBe(
      false,
    );
  });

  it("retains historical parent selection identities while coupling scope remains unestablished", () => {
    const selection = mutableRecord(
      parentJointCandidateSimulationProjection("run-parent-n8"),
    );
    const observation = firstMutableRecord(
      selection.n5_observations,
      "n5_observations",
    );
    const selectedAtomIds = structuredClone(
      observation.n8_candidate_parent_atom_ids,
    );
    const selectedChildRefs = structuredClone(
      observation.n8_candidate_parent_child_refs,
    );
    observation.n8_authority_blockers = [
      "parent_joint_coupling_evidence_not_established",
    ];
    observation.n8_joint_outcome_units = {};
    observation.n8_joint_parent_atom_ids = [];
    observation.n8_joint_parent_atom_content_hashes = [];
    observation.n8_parent_child_refs = [];
    observation.n8_parent_child_source_bindings = [];
    observation.n8_joint_scope_status = "not_established";
    observation.n8_joint_scope_limitation_code =
      "parent_joint_coupling_evidence_not_established";
    observation.n8_joint_value_limitation_code = null;
    observation.n8_candidate_member_basis = "not_established";
    observation.n8_source_candidate_relationship = "not_established";
    observation.n8_policy_composition_limitation_code =
      "legacy_selection_receipt_has_no_composition_basis";
    observation.n8_child_to_parent_refinement_limitation_code =
      "legacy_selection_receipt_has_no_refinement_basis";

    const payload = runDetailsPayload("projection only");
    mutableRecord(payload.run).candidate_simulation = selection;
    const admitted =
      runDetailsSchema.parse(payload).run.candidate_simulation
        ?.n5_observations[0];

    expect(admitted).toMatchObject({
      n8_candidate_joint_selection_status: "resolved",
      n8_candidate_member_basis: "not_established",
      n8_source_candidate_relationship: "not_established",
      n8_policy_composition_status: "not_established",
      n8_policy_composition_limitation_code:
        "legacy_selection_receipt_has_no_composition_basis",
      n8_child_to_parent_refinement_status: "not_established",
      n8_child_to_parent_refinement_limitation_code:
        "legacy_selection_receipt_has_no_refinement_basis",
      n8_joint_scope_status: "not_established",
      n8_joint_scope_limitation_code:
        "parent_joint_coupling_evidence_not_established",
      n8_status: "value_pending_n8",
    });
    expect(admitted?.n8_candidate_parent_atom_ids).toEqual(selectedAtomIds);
    expect(admitted?.n8_candidate_parent_child_refs).toEqual(selectedChildRefs);
    expect(admitted?.n8_joint_parent_atom_ids).toEqual([]);
    expect(admitted?.n8_parent_child_source_bindings).toEqual([]);
  });

  it("leaves an incomplete selected parent basis pending without inventing identities", () => {
    const projection = mutableRecord(
      parentJointCandidateSimulationProjection("run-parent-n8"),
    );
    const observation = firstMutableRecord(
      projection.n5_observations,
      "n5_observations",
    );
    observation.n8_authority_blockers = [
      "parent_joint_selected_child_program_not_established",
    ];
    observation.n8_status = "value_pending_n8";
    observation.n8_joint_scope_status = "not_established";
    observation.n8_joint_scope_limitation_code =
      "parent_joint_selected_child_program_not_established";
    observation.n8_joint_value_limitation_code = null;
    observation.n8_joint_request_content_hash = null;
    observation.n8_joint_world_model_record_ref = null;
    observation.n8_joint_outcome_units = {};
    observation.n8_joint_parent_atom_ids = [];
    observation.n8_joint_parent_atom_content_hashes = [];
    observation.n8_parent_child_refs = [];
    observation.n8_parent_child_source_bindings = [];
    observation.n8_candidate_joint_selection_status = "not_established";
    observation.n8_candidate_joint_selection_content_hash = null;
    observation.n8_candidate_parent_atom_ids = [];
    observation.n8_candidate_parent_atom_content_hashes = [];
    observation.n8_candidate_parent_intervention_ids = [];
    observation.n8_candidate_parent_child_refs = [];
    observation.n8_candidate_joint_selection_limitation_code =
      "parent_joint_candidate_source_selection_not_established";
    observation.n8_candidate_member_basis = "not_established";
    observation.n8_source_candidate_relationship = "not_established";
    observation.n8_policy_composition_status = "not_established";
    observation.n8_policy_composition_limitation_code =
      "parent_joint_candidate_source_selection_not_established";
    observation.n8_child_to_parent_refinement_status = "not_established";
    observation.n8_child_to_parent_refinement_limitation_code =
      "parent_joint_candidate_source_selection_not_established";

    const payload = runDetailsPayload("projection only");
    mutableRecord(payload.run).candidate_simulation = projection;
    const parsed = runDetailsSchema.parse(payload);
    const admitted = parsed.run.candidate_simulation?.n5_observations[0];

    expect(admitted).toMatchObject({
      n8_candidate_joint_selection_status: "not_established",
      n8_candidate_joint_selection_content_hash: null,
      n8_candidate_parent_atom_ids: [],
      n8_candidate_parent_atom_content_hashes: [],
      n8_joint_scope_status: "not_established",
      n8_status: "value_pending_n8",
    });
  });

  it("requires full Core ArtifactRef metadata at the run projection boundary", () => {
    const reference = {
      artifact_id: "sha256:" + "a".repeat(64),
      kind: "ir.model_spec",
      media_type: "application/json",
    };
    const completePayload = runDetailsPayload("projection only");
    mutableRecord(completePayload.run).root_artifacts = [reference];
    expect(runDetailsSchema.parse(completePayload).run.root_artifacts).toEqual([
      reference,
    ]);

    const missingKindPayload = runDetailsPayload("projection only");
    mutableRecord(missingKindPayload.run).root_artifacts = [
      { artifact_id: reference.artifact_id, media_type: reference.media_type },
    ];
    expect(runDetailsSchema.safeParse(missingKindPayload).success).toBe(false);

    const missingMediaTypePayload = runDetailsPayload("projection only");
    mutableRecord(missingMediaTypePayload.run).root_input_artifacts = [
      { artifact_id: reference.artifact_id, kind: "fabric.data_snapshot" },
    ];
    expect(runDetailsSchema.safeParse(missingMediaTypePayload).success).toBe(
      false,
    );

    const missingCandidateMetadata = mutableRecord(
      parentJointCandidateSimulationProjection("run-parent-n8"),
    );
    const observation = firstMutableRecord(
      missingCandidateMetadata.n5_observations,
      "n5_observations",
    );
    observation.n4_source_ref = { artifact_id: reference.artifact_id };
    const candidatePayload = runDetailsPayload("projection only");
    mutableRecord(candidatePayload.run).candidate_simulation =
      missingCandidateMetadata;
    expect(runDetailsSchema.safeParse(candidatePayload).success).toBe(false);
  });

  it("keeps an absent generic cycle field absent instead of synthesizing a projection", () => {
    const parsed = runDetailsSchema.parse(runDetailsPayload("projection only"));

    expect(parsed.run).not.toHaveProperty("generic_cycle_simulation");
  });

  it("retains the current direct-method selection returned by RunDetails GET", () => {
    const payload = runDetailsPayload("projection only");
    const projection = {
      status: "absent",
      candidate_only: true,
      limitations: ["no_direct_method_request"],
    };
    mutableRecord(payload.run).method_execution_selection = projection;

    const parsed = runDetailsSchema.parse(payload);

    expect(parsed.run.method_execution_selection).toEqual(projection);
    const withUnknownTopLevelField = structuredClone(payload);
    mutableRecord(withUnknownTopLevelField.run).unreviewed_run_field = true;
    expect(runDetailsSchema.safeParse(withUnknownTopLevelField).success).toBe(
      false,
    );
  });

  it("strictly validates a selected direct-method HTE in the RunDetails GET", () => {
    const payload = runDetailsPayload("projection only");
    const projection = runHteSelectedProjection();
    mutableRecord(payload.run).method_execution_selection = projection;

    const parsed = runDetailsSchema.parse(payload);
    expect(parsed.run.method_execution_selection).toEqual(projection);

    const withUnknownHteField = structuredClone(payload);
    const untypedRun = mutableRecord(withUnknownHteField.run);
    const untypedProjection = mutableRecord(
      untypedRun.method_execution_selection,
    );
    const selected = mutableRecord(untypedProjection.selection);
    mutableRecord(selected.hte).unreviewed_summary_field = true;
    expect(runDetailsSchema.safeParse(withUnknownHteField).success).toBe(false);
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

  it("binds the surfaced N5 body to kind, media, schema, profile, and basis", () => {
    const controls = [
      (body: Record<string, unknown>) => {
        mutableRecord(body.artifact_ref).kind = "runtime.other_result";
      },
      (body: Record<string, unknown>) => {
        mutableRecord(body.artifact_ref).media_type = "text/plain";
      },
      (body: Record<string, unknown>) => {
        body.artifact_schema_version = "3.0.0";
      },
      (body: Record<string, unknown>) => {
        body.selected_manifest_profile_sha256 = "sha256:" + "8".repeat(64);
      },
      (body: Record<string, unknown>) => {
        const trajectories = body.trajectories as unknown[];
        mutableRecord(trajectories[0]).points = [
          {
            step: 0,
            outcomes: { "outcome-a": 0.75 },
            effects: { other_outcome: 0.25 },
          },
        ];
      },
    ];
    for (const mutate of controls) {
      const payload = runDetailsPayload("projection only");
      const projection = mutableRecord(
        genericCycleSimulationProjection("run-projection-mask"),
      );
      const observation = firstMutableRecord(
        projection.n5_observations,
        "n5_observations",
      );
      const body = mutableRecord(observation.simulation_result_body);
      mutate(body);
      mutableRecord(payload.run).generic_cycle_simulation = projection;
      expect(runDetailsSchema.safeParse(payload).success).toBe(false);
    }
  });

  it("requires a body or explicit body-specific refusal for every persisted result reference", () => {
    const rejects = (
      mutate: (observation: Record<string, unknown>) => void,
    ) => {
      const payload = runDetailsPayload("projection only");
      const projection = mutableRecord(
        genericCycleSimulationProjection("run-projection-mask"),
      );
      const observation = firstMutableRecord(
        projection.n5_observations,
        "n5_observations",
      );
      mutate(observation);
      mutableRecord(payload.run).generic_cycle_simulation = projection;
      expect(runDetailsSchema.safeParse(payload).success).toBe(false);
    };

    rejects((observation) => {
      delete observation.simulation_result_body;
      delete observation.simulation_result_body_status;
      delete observation.simulation_result_body_limitation_code;
    });
    rejects((observation) => {
      observation.simulation_result_body = null;
      observation.simulation_result_body_status = "not_established";
      delete observation.simulation_result_body_limitation_code;
      observation.n8_limitation_code = "law_status_unknown";
      observation.n8_lineage_status = "not_established";
      observation.n8_value_ref = null;
    });
    rejects((observation) => {
      observation.simulation_result_body_status = "resolved";
      observation.simulation_result_body_limitation_code = null;
      delete observation.simulation_result_body;
    });
    rejects((observation) => {
      observation.status = "simulation_blocked";
    });
    rejects((observation) => {
      const body = mutableRecord(observation.simulation_result_body);
      mutableRecord(body.artifact_ref).artifact_id = "sha256:" + "f".repeat(64);
    });
    rejects((observation) => {
      mutableRecord(observation.simulation_result_ref).manifest_profile_sha256 =
        null;
      delete observation.simulation_result_body;
      delete observation.simulation_result_body_status;
      delete observation.simulation_result_body_limitation_code;
    });

    const unavailable = runDetailsPayload("projection only");
    const projection = mutableRecord(
      genericCycleSimulationProjection("run-projection-mask"),
    );
    const observation = firstMutableRecord(
      projection.n5_observations,
      "n5_observations",
    );
    observation.simulation_result_body = null;
    observation.simulation_result_body_status = "not_established";
    observation.simulation_result_body_limitation_code =
      "generic_n5_result_body_content_refused";
    mutableRecord(unavailable.run).generic_cycle_simulation = projection;
    expect(runDetailsSchema.safeParse(unavailable).success).toBe(true);
  });

  it("recomputes and preserves shared-seed interaction samples and fails closed on mismatches", () => {
    const payload = runDetailsPayload("projection only");
    const projection = genericCycleSimulationProjection("run-projection-mask");
    mutableRecord(payload.run).generic_cycle_simulation = projection;
    const parsed = runDetailsSchema.parse(payload);
    const observation = parsed.run.generic_cycle_simulation?.n5_observations[0];
    expect(
      observation?.n5_interaction_evidence?.interaction_terms[0]
        ?.replication_sampling_by_step["0"],
    ).toMatchObject({
      seeds: [41, 42],
      samples: [
        { seed: 41, value: 0 },
        { seed: 42, value: 0 },
      ],
      mean: 0,
      standard_error: 0,
    });

    const corrupted = mutableRecord(
      genericCycleSimulationProjection("run-projection-mask")
        .n5_observations[0],
    );
    const evidence = mutableRecord(corrupted.n5_interaction_evidence);
    const term = firstMutableRecord(
      evidence.interaction_terms,
      "interaction_terms",
    );
    const samplingByStep = mutableRecord(term.replication_sampling_by_step);
    const step = mutableRecord(samplingByStep["0"]);
    step.samples = [
      { seed: 41, value: 1 },
      { seed: 42, value: -1 },
    ];
    const corruptedPayload = runDetailsPayload("projection only");
    const corruptedProjection = mutableRecord(
      genericCycleSimulationProjection("run-projection-mask"),
    );
    corruptedProjection.n5_observations = [corrupted];
    mutableRecord(corruptedPayload.run).generic_cycle_simulation =
      corruptedProjection;
    expect(runDetailsSchema.safeParse(corruptedPayload).success).toBe(false);
  });

  it("retains legacy N5 uncertainty as a limitation without current-scope requirements", () => {
    const payload = runDetailsPayload("projection only");
    const projection = mutableRecord(
      genericCycleSimulationProjection("run-projection-mask"),
    );
    const observation = firstMutableRecord(
      projection.n5_observations,
      "n5_observations",
    );
    const evidence = mutableRecord(observation.n5_interaction_evidence);
    evidence.schema_version = "policyos.runtime.joint_simulation_horizon.v3";
    evidence.numeric_interaction = "unsupported";
    evidence.numeric_interaction_basis = "not_established";
    evidence.interaction_sampling_status = "not_established";
    evidence.interaction_terms = [];
    evidence.higher_order_residuals = {};
    evidence.higher_order_residual_sampling = {};
    observation.n8_numeric_interaction = "unsupported";
    observation.n8_numeric_interaction_basis = "not_established";
    observation.n8_interaction_sampling_status = "not_established";
    observation.n8_authority_blockers = [
      ...((observation.n8_authority_blockers as string[]) ?? []),
      "legacy_interaction_not_established",
    ];
    delete observation.executed_steps;
    delete observation.replication_seeds;
    projection.n5_observations = [observation];
    mutableRecord(payload.run).generic_cycle_simulation = projection;

    const parsed = runDetailsSchema.parse(payload);

    expect(
      parsed.run.generic_cycle_simulation?.n5_observations[0]
        ?.n5_interaction_evidence?.numeric_interaction,
    ).toBe("unsupported");
    expect(
      parsed.run.generic_cycle_simulation?.n5_observations[0]
        ?.n5_interaction_evidence?.interaction_sampling_status,
    ).toBe("not_established");
  });

  it.each([
    "remove_pair_keep_status_markers",
    "foreign_pair_atoms",
    "foreign_pair_outcome",
    "foreign_pair_step",
    "foreign_pair_seeds",
    "checked_orders_not_bound_to_parent_atoms",
    "remove_residual_keep_status_markers",
    "foreign_residual_outcome",
    "foreign_residual_step",
    "parent_selected_atoms_mismatch",
    "parent_selected_outcomes_mismatch",
    "missing_parent_step_basis",
    "missing_parent_seed_basis",
  ])("rejects current N5 evidence outside its parent basis: %s", (control) => {
    const payload = runDetailsPayload("projection only");
    const projection = genericCycleSimulationProjection("run-projection-mask");
    const observation = mutableRecord(projection.n5_observations[0]);
    const evidence = mutableRecord(observation.n5_interaction_evidence);
    const term = firstMutableRecord(
      evidence.interaction_terms,
      "interaction_terms",
    );
    if (control === "remove_pair_keep_status_markers") {
      evidence.interaction_terms = (
        evidence.interaction_terms as unknown[]
      ).slice(1);
    } else if (control === "foreign_pair_atoms") {
      term.atom_ids = ["atom-a", "foreign-atom"];
    } else if (control === "foreign_pair_outcome") {
      term.outcome = "foreign-outcome";
    } else if (control === "foreign_pair_step") {
      term.by_step = { "1": 0 };
      const summaries = mutableRecord(term.replication_sampling_by_step);
      term.replication_sampling_by_step = {
        "1": summaries["0"],
      };
    } else if (control === "foreign_pair_seeds") {
      const summaries = mutableRecord(term.replication_sampling_by_step);
      const summary = mutableRecord(summaries["0"]);
      summary.seeds = [42, 43];
      summary.samples = [
        { seed: 42, value: 0 },
        { seed: 43, value: 0 },
      ];
    } else if (control === "checked_orders_not_bound_to_parent_atoms") {
      evidence.checked_interaction_orders = [1, 2];
    } else if (control === "remove_residual_keep_status_markers") {
      evidence.higher_order_residuals = {};
      evidence.higher_order_residual_sampling = {};
    } else if (control === "foreign_residual_outcome") {
      const residualSampling = mutableRecord(
        evidence.higher_order_residual_sampling,
      );
      evidence.higher_order_residuals = { "foreign-outcome": { "0": 0 } };
      evidence.higher_order_residual_sampling = {
        "foreign-outcome": residualSampling["outcome-a"],
      };
    } else if (control === "foreign_residual_step") {
      const residualSampling = mutableRecord(
        evidence.higher_order_residual_sampling,
      );
      const outcomeSampling = mutableRecord(residualSampling["outcome-a"]);
      evidence.higher_order_residuals = { "outcome-a": { "1": 0 } };
      evidence.higher_order_residual_sampling = {
        "outcome-a": { "1": outcomeSampling["0"] },
      };
    } else if (control === "parent_selected_atoms_mismatch") {
      observation.atom_ids = ["atom-a", "atom-b"];
    } else if (control === "parent_selected_outcomes_mismatch") {
      observation.selected_outcomes = ["other-outcome"];
    } else if (control === "missing_parent_step_basis") {
      delete observation.executed_steps;
    } else if (control === "missing_parent_seed_basis") {
      delete observation.replication_seeds;
    }
    mutableRecord(payload.run).generic_cycle_simulation = projection;

    const result = runDetailsSchema.safeParse(payload);

    expect(result.success).toBe(false);
    const issues = result.success ? [] : result.error.issues;
    expect(issues).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          message: expect.stringMatching(/^run_n5_interaction_scope_/),
        }),
      ]),
    );
  });

  it("derives a complete four-atom pair basis under permutation", () => {
    const payload = runDetailsPayload("projection only");
    const atoms = ["atom-d", "atom-c", "atom-b", "atom-a"];
    const projection = genericCycleSimulationProjection(
      "four-atom-permutation",
      atoms,
    );
    const observation = mutableRecord(projection.n5_observations[0]);
    const evidence = mutableRecord(observation.n5_interaction_evidence);
    const template = firstMutableRecord(
      evidence.interaction_terms,
      "interaction_terms",
    );
    const pairs = atoms.flatMap((left, index) =>
      atoms.slice(index + 1).map((right) => [left, right]),
    );
    evidence.interaction_terms = pairs.map((atom_ids) => ({
      ...template,
      atom_ids,
    }));
    evidence.checked_interaction_orders = [1, 2];
    mutableRecord(payload.run).generic_cycle_simulation = projection;

    const parsed = runDetailsSchema.parse(payload);
    expect(
      parsed.run.generic_cycle_simulation?.n5_observations[0]
        ?.simulation_result_body?.atom_ids,
    ).toEqual(atoms);
    expect(
      parsed.run.generic_cycle_simulation?.n5_observations[0]
        ?.simulation_result_body?.trajectories[0]?.atom_ids,
    ).toEqual(atoms);

    evidence.interaction_terms = (
      evidence.interaction_terms as unknown[]
    ).slice(1);
    const missingPair = runDetailsSchema.safeParse(payload);
    expect(missingPair.success).toBe(false);
    const missingPairIssues = missingPair.success
      ? []
      : missingPair.error.issues;
    expect(missingPairIssues).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          message: "run_n5_interaction_scope_pair_set_incomplete",
        }),
      ]),
    );
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

  it.each(["v3", "v4"] as const)(
    "preserves the complete candidate-only N6 history under %s",
    (version) => {
      const payload = runDetailsPayload("projection only");
      mutableRecord(payload.run).generic_cycle_simulation =
        genericCycleN6Projection("run-projection-mask", version);

      const parsed = runDetailsSchema.parse(payload);
      const projection = parsed.run.generic_cycle_simulation;

      expect(projection?.schema_version).toBe(
        version === "v3"
          ? "policyos.runtime.run_generic_cycle_simulation_projection.v3"
          : "policyos.runtime.run_generic_cycle_simulation_projection.v4",
      );
      expect(projection?.n6_cycle_history_status).toBe("resolved");
      expect(projection?.n6_cycle_history).toHaveLength(1);
      expect(projection?.n6_cycle_history?.[0]).toMatchObject({
        node_ref: "design-problem://" + "d".repeat(64),
        cycle_index: 1,
        selected_candidate_ref: "candidate://candidate-a",
        terminal_kind: "grounded_partial_admissible",
        grounding_current_valid: false,
        value_authority_blockers: ["publication_not_admitted"],
        voi_next_action: "advance",
      });
      expect(projection?.authority_purpose).toBe("cycle_input_candidate_only");
      expect(projection?.currentness_status).toBe("not_established");
      expect(projection?.publication_authority).toBe(false);
    },
  );

  it.each([
    "missing_schema_version",
    "unknown_schema_version",
    "history_extension_under_v1",
    "v3_history_status_missing",
    "v3_resolved_without_rows",
    "v3_not_established_with_rows",
    "v3_duplicate_node_cycle",
    "v3_credal_extension_without_v4",
    "v4_missing_n6_history",
    "v4_credal_status_missing",
    "v3_profile_ref_kind_mismatch",
  ])("rejects malformed supplied N6/version binding: %s", (control) => {
    const payload = runDetailsPayload("projection only");
    const run = mutableRecord(payload.run);
    const projection = mutableRecord(
      control === "v4_missing_n6_history" ||
        control === "v4_credal_status_missing"
        ? genericCycleCredalProjection("run-projection-mask")
        : genericCycleN6Projection("run-projection-mask"),
    );
    run.generic_cycle_simulation = projection;

    if (control === "missing_schema_version") {
      delete projection.schema_version;
    } else if (control === "unknown_schema_version") {
      projection.schema_version =
        "policyos.runtime.run_generic_cycle_simulation_projection.v5";
    } else if (control === "history_extension_under_v1") {
      projection.schema_version =
        "policyos.runtime.run_generic_cycle_simulation_projection.v1";
    } else if (control === "v3_history_status_missing") {
      delete projection.n6_cycle_history_status;
    } else if (control === "v3_resolved_without_rows") {
      projection.n6_cycle_history = [];
    } else if (control === "v3_not_established_with_rows") {
      projection.n6_cycle_history_status = "not_established";
      projection.n6_cycle_history_limitation_code =
        "n6_cycle_history_not_emitted";
    } else if (control === "v3_duplicate_node_cycle") {
      projection.n6_cycle_history = [
        genericCycleN6HistoryEntry(),
        genericCycleN6HistoryEntry(),
      ];
    } else if (control === "v3_credal_extension_without_v4") {
      projection.credal_source_status = "not_established";
      projection.credal_source_limitation_code =
        "candidate_source_authority_not_established";
    } else if (control === "v4_missing_n6_history") {
      projection.schema_version =
        "policyos.runtime.run_generic_cycle_simulation_projection.v4";
      projection.n6_cycle_history_status = null;
      projection.n6_cycle_history_limitation_code = null;
      projection.n6_cycle_history = [];
    } else if (control === "v4_credal_status_missing") {
      projection.schema_version =
        "policyos.runtime.run_generic_cycle_simulation_projection.v4";
      projection.n6_cycle_history_status = "resolved";
      projection.n6_cycle_history_limitation_code = null;
      projection.n6_cycle_history = [genericCycleN6HistoryEntry()];
      projection.credal_source_status = null;
    } else if (control === "v3_profile_ref_kind_mismatch") {
      mutableRecord(
        firstMutableRecord(
          projection.child_profile_bindings,
          "child_profile_bindings",
        ).profile_ref,
      ).kind = "runtime.unbound_profile";
    }

    expect(runDetailsSchema.safeParse(payload).success).toBe(false);
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
    "n8_interaction_qualification_mismatch",
    "n5_interaction_seed_mismatch",
    "n5_interaction_se_mismatch",
    "n5_interaction_summary_removed_with_additive_marker",
    "n5_legacy_interaction_laundering",
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
    } else if (control === "n8_interaction_qualification_mismatch") {
      n5Observation().n8_numeric_interaction = "additive";
    } else if (
      control === "n5_interaction_summary_removed_with_additive_marker"
    ) {
      const evidence = mutableRecord(n5Observation().n5_interaction_evidence);
      const term = firstMutableRecord(
        evidence.interaction_terms,
        "interaction_terms",
      );
      delete term.replication_sampling_by_step;
    } else if (control === "n5_interaction_seed_mismatch") {
      const evidence = mutableRecord(n5Observation().n5_interaction_evidence);
      const term = firstMutableRecord(
        evidence.interaction_terms,
        "interaction_terms",
      );
      const samplingByStep = mutableRecord(term.replication_sampling_by_step);
      const step = mutableRecord(samplingByStep["0"]);
      step.samples = [
        { seed: 41, value: 0 },
        { seed: 43, value: 0 },
      ];
    } else if (control === "n5_interaction_se_mismatch") {
      const evidence = mutableRecord(n5Observation().n5_interaction_evidence);
      const term = firstMutableRecord(
        evidence.interaction_terms,
        "interaction_terms",
      );
      const samplingByStep = mutableRecord(term.replication_sampling_by_step);
      const step = mutableRecord(samplingByStep["0"]);
      step.standard_error = 1;
    } else if (control === "n5_legacy_interaction_laundering") {
      const evidence = mutableRecord(n5Observation().n5_interaction_evidence);
      evidence.schema_version = "policyos.runtime.joint_simulation_horizon.v3";
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
    const interactionControls = new Set([
      "n5_interaction_seed_mismatch",
      "n5_interaction_se_mismatch",
      "n5_interaction_summary_removed_with_additive_marker",
      "n5_legacy_interaction_laundering",
    ]);
    const hasInteractionIssue =
      !result.success &&
      result.error.issues.some(
        (issue) =>
          issue.message.startsWith("run_n5_") ||
          issue.path.includes("replication_sampling_by_step"),
      );
    expect(
      scalarOnlyControls.has(control) ||
        hasGenericIssue ||
        (interactionControls.has(control) && hasInteractionIssue),
    ).toBe(true);
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

  it("preserves the typed Legal source-relation refusal and rejects malformed supplied values", () => {
    const response = {
      meta: {
        request_id: "request-legal-relation-refusal",
        generated_at: "2026-10-16T00:00:00Z",
        source_kinds: [],
      },
      query: "employment leave",
      results: [],
      total: 0,
      search_mode: "text",
      vector_refusal_code: null,
    } as const;
    const refusal = {
      code: "legal_source_relation_verification_not_established",
      status: "verification_missing",
    } as const;

    expect(
      lexSearchResponseSchema.parse({
        ...response,
        legal_relation_refusal: refusal,
      }).legal_relation_refusal,
    ).toEqual(refusal);
    expect(lexSearchResponseSchema.parse(response)).not.toHaveProperty(
      "legal_relation_refusal",
    );
    expect(
      lexSearchResponseSchema.parse({
        ...response,
        legal_relation_refusal: null,
      }).legal_relation_refusal,
    ).toBeNull();

    for (const invalidRefusal of [
      { code: "different_refusal", status: "verification_missing" },
      {
        code: refusal.code,
        status: "verified",
      },
      { ...refusal, issuer: "untrusted-adjacent-field" },
    ]) {
      expect(
        lexSearchResponseSchema.safeParse({
          ...response,
          legal_relation_refusal: invalidRefusal,
        }).success,
      ).toBe(false);
    }
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
        unattributed_cost_events: [
          {
            event_id: "preflight:unknown-attempt",
            cost_origin: "unknown",
            amount: null,
            cost_usd: null,
            settlement_status: "unknown",
            durability: "ledger",
            control_job_attempt: null,
            pre_admission_attempt_id: "0123456789abcdef0123456789abcdef",
          },
        ],
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

    const ambiguous: unknown = structuredClone(response);
    const ambiguousPipeline = mutableRecord(mutableRecord(ambiguous).pipeline);
    const unattributed = ambiguousPipeline.unattributed_cost_events;
    if (!Array.isArray(unattributed)) {
      throw new TypeError("expected unattributed cost event array");
    }
    const ambiguousEvent = mutableRecord(unattributed[0]);
    ambiguousEvent.control_job_attempt = 1;
    expect(runAgentsSchema.safeParse(ambiguous).success).toBe(false);

    const nonLedgerAttempt: unknown = structuredClone(response);
    const nonLedgerPipeline = mutableRecord(
      mutableRecord(nonLedgerAttempt).pipeline,
    );
    const nonLedgerAttempts = nonLedgerPipeline.attempts;
    if (!Array.isArray(nonLedgerAttempts)) {
      throw new TypeError("expected attempts array");
    }
    const nonLedgerSteps = mutableRecord(nonLedgerAttempts[0]).steps;
    if (!Array.isArray(nonLedgerSteps)) {
      throw new TypeError("expected pipeline steps array");
    }
    const nonLedgerEvents = mutableRecord(nonLedgerSteps[0]).cost_events;
    if (!Array.isArray(nonLedgerEvents)) {
      throw new TypeError("expected cost events array");
    }
    const nonLedgerEvent = mutableRecord(nonLedgerEvents[0]);
    nonLedgerEvent.control_job_attempt = 1;
    nonLedgerEvent.durability = "memory";
    expect(runAgentsSchema.safeParse(nonLedgerAttempt).success).toBe(false);
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

describe("predictive calibration response custody", () => {
  it("accepts a complete limited response with selected profiles and candidate-only status", () => {
    const parsed = predictiveCalibrationResponseSchema.parse(
      predictiveCalibrationResponseFixture,
    );
    expect(parsed.association.assessment).toBe("limited");
    expect(parsed.association.authority_scope).toBe("predictive_only");
    expect(parsed.association.observed_hit_rate).toBe(0.75);
    expect(parsed.association.s10.calibration_status).toBe("limit");
    expect(parsed.association.counterfactual_credibility_status).toBe(
      "not_established",
    );
    expect(parsed.association.run_manifest_ref.manifest_profile_sha256).toMatch(
      /^sha256:[0-9a-f]{64}$/,
    );
  });

  it("rejects missing selected profile and authority-shaped unknown fields", () => {
    expect(
      predictiveCalibrationResponseSchema.safeParse(
        responseWithoutSelectedRunManifestProfile(),
      ).success,
    ).toBe(false);
    expect(
      predictiveCalibrationResponseSchema.safeParse(
        responseWithUnknownAssociationAuthority(),
      ).success,
    ).toBe(false);
    expect(
      predictiveCalibrationResponseSchema.safeParse(
        responseWithUnknownMetaAuthority(),
      ).success,
    ).toBe(false);
  });
});

// Values follow the Core inspector response and the canonical limited-diagnostic example.
const artifactContentApiPreviewFixture = {
  meta: {
    generated_at: "2026-02-11T12:00:00Z",
    request_id: "req_0123456789abcdef",
    source_kinds: [],
  },
  artifact: {
    artifact_id:
      "sha256:0842d275aa73d47d96580633444cc0a3b11697f86520fcf155c2ab7c7a33f047",
    canon_read_status: "declared_bytes_conformant",
    kind: "ir.backtest_report",
    manifest_profile_sha256:
      "sha256:7bdf7798abb83b6463e4b672f4b388730f442965f1fef930d3504b1eeef7f123",
    max_bytes: 4096,
    media_type: "application/json",
    mode: "json",
    predictive_coverage_diagnostic: {
      assessment: "limited",
      canon_read_status: "declared_bytes_conformant",
      causal_effect_status: "not_established",
      counterfactual_credibility_status: "not_established",
      effective_time_status: "not_established",
      issuer_status: "not_established",
      may_not_use_for: [
        "promotion",
        "publication",
        "policy_selection",
        "causal_effect_claim",
      ],
      measurement_status: "not_measured",
      metric: "predictive_interval_coverage",
      producer_attestation_status: "not_established",
      reason_code: "no_evaluated_intervals",
      s10_metric_mapping_status: "not_established",
      s10_threshold_status: "not_established",
      scenarios: [
        {
          interval_available_count: 0,
          interval_evaluated_count: 0,
          interval_hit_count: 0,
          interval_requested_count: 1,
          interval_type: "prediction",
          metric_name: "outcome",
          nominal_confidence_level: 0.9,
          observed_hit_rate: null,
          scenario_id: "openapi-no-intervals",
        },
      ],
      source_artifact_id:
        "sha256:0842d275aa73d47d96580633444cc0a3b11697f86520fcf155c2ab7c7a33f047",
      source_manifest_profile_sha256:
        "sha256:7bdf7798abb83b6463e4b672f4b388730f442965f1fef930d3504b1eeef7f123",
      source_materialization: "reader_materialized",
      source_schema_version: "1.0",
    },
    preview: { schema_version: "1.0" },
    size_bytes: 1024,
    truncated: false,
  },
} satisfies components["schemas"]["ArtifactContentResponse"];

const decisionPacketContentApiResponseFixture = {
  meta: {
    generated_at: "2026-02-11T12:00:00Z",
    request_id: "req_0123456789abcdef",
    source_kinds: [],
  },
  artifact: {
    artifact_id:
      "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    canon_read_status: "declared_bytes_conformant",
    decision_packet_preview: {
      hte_projection_status: "absent",
      document_outline: [
        {
          section_id: "policy_answer",
          section_type: "policy",
          title: "Recommendation",
        },
      ],
    },
    kind: "scientist.decision_packet",
    manifest_profile_sha256:
      "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    max_bytes: 4096,
    media_type: "application/json",
    mode: "json",
    preview: { policy_answer: "Approve the targeted support package." },
    size_bytes: 1024,
    truncated: false,
  },
} satisfies components["schemas"]["ArtifactContentResponse"];

const artifactSchemaApiResponseFixture = {
  meta: {
    generated_at: "2026-02-11T12:00:00Z",
    request_id: "req_0123456789abcdef",
    source_kinds: [],
  },
  schema: {
    artifact_id:
      "sha256:0842d275aa73d47d96580633444cc0a3b11697f86520fcf155c2ab7c7a33f047",
    canon_read_status: "declared_bytes_conformant",
    kind: "ir.backtest_report",
    manifest_profile_sha256:
      "sha256:7bdf7798abb83b6463e4b672f4b388730f442965f1fef930d3504b1eeef7f123",
    media_type: "application/json",
    schema_name: "ir.backtest_report",
    schema_version: "1.0",
    top_level_keys: ["schema_version", "scenarios"],
  },
} satisfies components["schemas"]["ArtifactSchemaResponse"];

function artifactInspectorIntakeFixture() {
  return {
    manifest: {
      artifact_id: artifactContentApiPreviewFixture.artifact.artifact_id,
      manifest_profile_sha256:
        artifactContentApiPreviewFixture.artifact.manifest_profile_sha256,
      kind: "ir.backtest_report",
      media_type: "application/json",
      schema_name: "ir.backtest_report",
      schema_version: "1.0",
    },
    content: structuredClone(artifactContentApiPreviewFixture.artifact),
  };
}

const coreCanonReadStatuses = [
  "not_applicable",
  "not_evaluated",
  "declared_bytes_conformant",
  "profile_absent_unqualified_candidate",
  "declared_unknown_candidate",
] as const;

describe("artifact preview canonical read status custody", () => {
  it("preserves typed API content and predictive fields without qualification upgrades", () => {
    const parsed = artifactContentSchema.parse(
      artifactContentApiPreviewFixture,
    );
    const diagnostic = parsed.artifact.predictive_coverage_diagnostic;

    expect(parsed.artifact).toEqual(artifactContentApiPreviewFixture.artifact);
    expect(parsed.artifact.canon_read_status).toBe("declared_bytes_conformant");
    expect(diagnostic).toEqual(
      artifactContentApiPreviewFixture.artifact.predictive_coverage_diagnostic,
    );
    expect(diagnostic?.assessment).toBe("limited");
    expect(diagnostic?.source_materialization).toBe("reader_materialized");
    expect(diagnostic?.producer_attestation_status).toBe("not_established");
    expect(diagnostic?.may_not_use_for).toEqual([
      "promotion",
      "publication",
      "policy_selection",
      "causal_effect_claim",
    ]);

    const decisionPacket = artifactContentSchema.parse(
      decisionPacketContentApiResponseFixture,
    );
    expect(decisionPacket.artifact).toEqual(
      decisionPacketContentApiResponseFixture.artifact,
    );
    expect(decisionPacket.artifact.decision_packet_preview).toEqual(
      decisionPacketContentApiResponseFixture.artifact.decision_packet_preview,
    );

    const schema = artifactSchemaSchema.parse(artifactSchemaApiResponseFixture);
    expect(schema.schema).toEqual(artifactSchemaApiResponseFixture.schema);
  });

  it.each(coreCanonReadStatuses)(
    "accepts and preserves the Core status %s in all three preview contracts",
    (status) => {
      const content = structuredClone(artifactContentApiPreviewFixture);
      const contentArtifact = mutableRecord(content.artifact);
      contentArtifact.canon_read_status = status;
      mutableRecord(
        contentArtifact.predictive_coverage_diagnostic,
      ).canon_read_status = status;
      expect(
        artifactContentSchema.parse(content).artifact.canon_read_status,
      ).toBe(status);
      expect(
        artifactContentSchema.parse(content).artifact
          .predictive_coverage_diagnostic?.canon_read_status,
      ).toBe(status);

      const schema = structuredClone(artifactSchemaApiResponseFixture);
      mutableRecord(schema.schema).canon_read_status = status;
      expect(artifactSchemaSchema.parse(schema).schema.canon_read_status).toBe(
        status,
      );
    },
  );

  it("maps legacy omissions to not_evaluated and rejects explicit null", () => {
    const missingContentStatus = structuredClone(
      artifactContentApiPreviewFixture,
    );
    delete mutableRecord(missingContentStatus.artifact).canon_read_status;
    const parsedMissingContentStatus =
      artifactContentSchema.parse(missingContentStatus);
    expect(parsedMissingContentStatus.artifact.canon_read_status).toBe(
      "not_evaluated",
    );

    const missingDiagnosticStatus = structuredClone(
      artifactContentApiPreviewFixture,
    );
    const missingDiagnosticStatusArtifact = mutableRecord(
      missingDiagnosticStatus.artifact,
    );
    delete missingDiagnosticStatusArtifact.canon_read_status;
    delete mutableRecord(
      missingDiagnosticStatusArtifact.predictive_coverage_diagnostic,
    ).canon_read_status;
    const parsedMissingDiagnosticStatus = artifactContentSchema.parse(
      missingDiagnosticStatus,
    );
    expect(parsedMissingDiagnosticStatus.artifact.canon_read_status).toBe(
      "not_evaluated",
    );
    expect(
      parsedMissingDiagnosticStatus.artifact.predictive_coverage_diagnostic
        ?.canon_read_status,
    ).toBe("not_evaluated");

    const missingSchemaStatus = structuredClone(
      artifactSchemaApiResponseFixture,
    );
    delete mutableRecord(missingSchemaStatus.schema).canon_read_status;
    expect(
      artifactSchemaSchema.parse(missingSchemaStatus).schema.canon_read_status,
    ).toBe("not_evaluated");

    const nullContentStatus = structuredClone(artifactContentApiPreviewFixture);
    mutableRecord(nullContentStatus.artifact).canon_read_status = null;
    expect(artifactContentSchema.safeParse(nullContentStatus).success).toBe(
      false,
    );

    const nullDiagnosticStatus = structuredClone(
      artifactContentApiPreviewFixture,
    );
    mutableRecord(
      mutableRecord(nullDiagnosticStatus.artifact)
        .predictive_coverage_diagnostic,
    ).canon_read_status = null;
    expect(artifactContentSchema.safeParse(nullDiagnosticStatus).success).toBe(
      false,
    );

    const nullSchemaStatus = structuredClone(artifactSchemaApiResponseFixture);
    mutableRecord(nullSchemaStatus.schema).canon_read_status = null;
    expect(artifactSchemaSchema.safeParse(nullSchemaStatus).success).toBe(
      false,
    );
  });

  it("joins predictive diagnostics to the exact JSON manifest with each status marker held fixed", () => {
    const mutations = [
      [
        "diagnostic artifact ID",
        (intake: ReturnType<typeof artifactInspectorIntakeFixture>) => {
          mutableRecord(
            mutableRecord(intake.content).predictive_coverage_diagnostic,
          ).source_artifact_id = "sha256:" + "c".repeat(64);
        },
      ],
      [
        "manifest artifact ID",
        (intake: ReturnType<typeof artifactInspectorIntakeFixture>) => {
          intake.manifest.artifact_id = "sha256:" + "c".repeat(64);
        },
      ],
      [
        "diagnostic profile",
        (intake: ReturnType<typeof artifactInspectorIntakeFixture>) => {
          mutableRecord(
            mutableRecord(intake.content).predictive_coverage_diagnostic,
          ).source_manifest_profile_sha256 = "sha256:" + "c".repeat(64);
        },
      ],
      [
        "manifest profile",
        (intake: ReturnType<typeof artifactInspectorIntakeFixture>) => {
          intake.manifest.manifest_profile_sha256 = "sha256:" + "c".repeat(64);
        },
      ],
      [
        "diagnostic status",
        (intake: ReturnType<typeof artifactInspectorIntakeFixture>) => {
          mutableRecord(
            mutableRecord(intake.content).predictive_coverage_diagnostic,
          ).canon_read_status = "not_evaluated";
        },
      ],
      [
        "diagnostic kind",
        (intake: ReturnType<typeof artifactInspectorIntakeFixture>) => {
          mutableRecord(intake.content).kind = "other.report";
          intake.manifest.kind = "other.report";
        },
      ],
      [
        "diagnostic schema name",
        (intake: ReturnType<typeof artifactInspectorIntakeFixture>) => {
          intake.manifest.schema_name = "other.report";
        },
      ],
      [
        "diagnostic schema version",
        (intake: ReturnType<typeof artifactInspectorIntakeFixture>) => {
          intake.manifest.schema_version = "2.0";
        },
      ],
      [
        "JSON mode",
        (intake: ReturnType<typeof artifactInspectorIntakeFixture>) => {
          mutableRecord(intake.content).mode = "text";
        },
      ],
      [
        "JSON media type",
        (intake: ReturnType<typeof artifactInspectorIntakeFixture>) => {
          mutableRecord(intake.content).media_type = "text/plain";
          intake.manifest.media_type = "text/plain";
        },
      ],
    ] as const;

    for (const [label, mutate] of mutations) {
      const intake = artifactInspectorIntakeFixture();
      mutate(intake);
      const diagnostic = mutableRecord(
        mutableRecord(intake.content).predictive_coverage_diagnostic,
      );
      expect({ label, value: diagnostic.assessment }).toEqual({
        label,
        value: "limited",
      });
      expect({ label, value: diagnostic.source_materialization }).toEqual({
        label,
        value: "reader_materialized",
      });
      expect({ label, value: diagnostic.producer_attestation_status }).toEqual({
        label,
        value: "not_established",
      });
      expect({ label, value: diagnostic.may_not_use_for }).toEqual({
        label,
        value: [
          "promotion",
          "publication",
          "policy_selection",
          "causal_effect_claim",
        ],
      });
      expect({
        label,
        success: artifactInspectorIntakeSchema.safeParse(intake).success,
      }).toEqual({ label, success: false });
    }
  });

  it("joins schema views to the same manifest schema name and version", () => {
    const manifest = {
      artifact_id: artifactSchemaApiResponseFixture.schema.artifact_id,
      manifest_profile_sha256:
        artifactSchemaApiResponseFixture.schema.manifest_profile_sha256,
      kind: artifactSchemaApiResponseFixture.schema.kind,
      media_type: artifactSchemaApiResponseFixture.schema.media_type,
      schema_name: artifactSchemaApiResponseFixture.schema.schema_name,
      schema_version: artifactSchemaApiResponseFixture.schema.schema_version,
    };
    const valid = {
      manifest,
      schema: structuredClone(artifactSchemaApiResponseFixture.schema),
    };
    expect(artifactInspectorIntakeSchema.safeParse(valid).success).toBe(true);

    const wrongName = structuredClone(valid);
    mutableRecord(wrongName.schema).schema_name = "other.schema";
    expect(artifactInspectorIntakeSchema.safeParse(wrongName).success).toBe(
      false,
    );

    const wrongVersion = structuredClone(valid);
    mutableRecord(wrongVersion.schema).schema_version = "2.0";
    expect(artifactInspectorIntakeSchema.safeParse(wrongVersion).success).toBe(
      false,
    );
  });

  it("strips future unconsumed response fields without changing limited status", () => {
    const futureContent = structuredClone(artifactContentApiPreviewFixture);
    const artifact = mutableRecord(futureContent.artifact);
    artifact.future_reader_annotation = { status: "publishable" };
    const diagnostic = mutableRecord(artifact.predictive_coverage_diagnostic);
    diagnostic.future_authority_label = "publishable";
    mutableRecord((diagnostic.scenarios as unknown[])[0]).future_metric_label =
      "conformant";

    const parsed = artifactContentSchema.parse(futureContent);
    expect(mutableRecord(parsed.artifact)).not.toHaveProperty(
      "future_reader_annotation",
    );
    expect(
      mutableRecord(parsed.artifact.predictive_coverage_diagnostic)
        .future_authority_label,
    ).toBeUndefined();
    expect(parsed.artifact.canon_read_status).toBe("declared_bytes_conformant");
    expect(parsed.artifact.predictive_coverage_diagnostic?.assessment).toBe(
      "limited",
    );
    expect(
      parsed.artifact.predictive_coverage_diagnostic
        ?.producer_attestation_status,
    ).toBe("not_established");

    const futureSchema = structuredClone(artifactSchemaApiResponseFixture);
    mutableRecord(futureSchema.schema).future_schema_flag = "established";
    const parsedSchema = artifactSchemaSchema.parse(futureSchema);
    expect(mutableRecord(parsedSchema.schema)).not.toHaveProperty(
      "future_schema_flag",
    );
    expect(parsedSchema.schema.canon_read_status).toBe(
      "declared_bytes_conformant",
    );
  });

  it("rejects authority upgrades while canonical status markers remain intact", () => {
    const mutations = [
      { label: "assessment", field: "assessment", value: "publishable" },
      {
        label: "source materialization",
        field: "source_materialization",
        value: "producer_materialized",
      },
      {
        label: "producer attestation",
        field: "producer_attestation_status",
        value: "verified",
      },
      {
        label: "S10 mapping",
        field: "s10_metric_mapping_status",
        value: "established",
      },
      {
        label: "S10 threshold",
        field: "s10_threshold_status",
        value: "established",
      },
      { label: "issuer", field: "issuer_status", value: "verified" },
      {
        label: "effective time",
        field: "effective_time_status",
        value: "current",
      },
      {
        label: "counterfactual credibility",
        field: "counterfactual_credibility_status",
        value: "established",
      },
      {
        label: "causal effect",
        field: "causal_effect_status",
        value: "established",
      },
    ] as const;
    for (const { label, field, value } of mutations) {
      const upgraded = structuredClone(artifactContentApiPreviewFixture);
      const artifact = mutableRecord(upgraded.artifact);
      const diagnostic = mutableRecord(artifact.predictive_coverage_diagnostic);
      artifact.canon_read_status = "declared_bytes_conformant";
      diagnostic.canon_read_status = "declared_bytes_conformant";
      diagnostic[field] = value;
      expect({
        label,
        success: artifactContentSchema.safeParse(upgraded).success,
      }).toEqual({ label, success: false });
    }

    const missingRestriction = structuredClone(
      artifactContentApiPreviewFixture,
    );
    mutableRecord(
      mutableRecord(missingRestriction.artifact).predictive_coverage_diagnostic,
    ).may_not_use_for = ["promotion"];
    expect(artifactContentSchema.safeParse(missingRestriction).success).toBe(
      false,
    );
  });

  it("rejects unknown statuses and malformed present nested values", () => {
    const unknownContentStatus = structuredClone(
      artifactContentApiPreviewFixture,
    );
    mutableRecord(unknownContentStatus.artifact).canon_read_status =
      "conformant";
    expect(artifactContentSchema.safeParse(unknownContentStatus).success).toBe(
      false,
    );

    const unknownDiagnosticStatus = structuredClone(
      artifactContentApiPreviewFixture,
    );
    mutableRecord(
      mutableRecord(unknownDiagnosticStatus.artifact)
        .predictive_coverage_diagnostic,
    ).canon_read_status = "conformant";
    expect(
      artifactContentSchema.safeParse(unknownDiagnosticStatus).success,
    ).toBe(false);

    const unknownSchemaStatus = structuredClone(
      artifactSchemaApiResponseFixture,
    );
    mutableRecord(unknownSchemaStatus.schema).canon_read_status = "conformant";
    expect(artifactSchemaSchema.safeParse(unknownSchemaStatus).success).toBe(
      false,
    );

    const malformedScenario = structuredClone(artifactContentApiPreviewFixture);
    const diagnostic = mutableRecord(
      mutableRecord(malformedScenario.artifact).predictive_coverage_diagnostic,
    );
    const scenarios = diagnostic.scenarios as unknown[];
    mutableRecord(scenarios[0]).interval_evaluated_count = "0";
    expect(artifactContentSchema.safeParse(malformedScenario).success).toBe(
      false,
    );
  });

  it("accepts typed unassigned scalar claims and rejects scope or amount escalation", () => {
    const scalar = {
      source_kind: "step_summary",
      source_field: "reported_cost_usd",
      claimed_value_usd: 0.01,
      scope: "not_established",
      attempt: 2,
      agent: "llm_producer_settlement",
      model_variant_id: "legacy-variant",
    };
    const response = {
      meta: {
        request_id: "request-1",
        generated_at: "2026-10-18T10:00:00Z",
      },
      pipeline: {
        run_id: "run-1",
        source_kind: "core_run",
        total_attempts: 1,
        owner_control_job_attempt: 2,
        attempts: [
          {
            attempt: 2,
            status: "unknown",
            unattributed_cost_scalars: [scalar],
            steps: [
              {
                attempt: 2,
                agent: "llm_producer_settlement",
                action: "durable_ledger",
                status: "info",
                settlement_event_ids: [],
                unattributed_cost_scalars: [scalar],
              },
            ],
          },
        ],
        unattributed_cost_scalars: [scalar],
      },
    };

    expect(runAgentsSchema.safeParse(response).success).toBe(true);
    const legacyResponse = structuredClone(response);
    expect(
      Reflect.deleteProperty(
        legacyResponse.pipeline,
        "owner_control_job_attempt",
      ),
    ).toBe(true);
    expect(runAgentsSchema.safeParse(legacyResponse).success).toBe(true);
    for (const ownerAttempt of [0, true]) {
      expect(
        runAgentsSchema.safeParse({
          ...response,
          pipeline: {
            ...response.pipeline,
            owner_control_job_attempt: ownerAttempt,
          },
        }).success,
      ).toBe(false);
    }
    expect(
      runAgentsSchema.safeParse({
        ...response,
        pipeline: {
          ...response.pipeline,
          attempts: [
            {
              attempt: 1,
              status: "unknown",
              steps: [
                {
                  attempt: 1,
                  agent: "llm_producer_settlement",
                  action: "durable_ledger",
                  cost_events: [
                    {
                      event_id: "old-attempt-under-owner-2",
                      cost_origin: "reported",
                      amount: "0.01",
                      cost_usd: 0.01,
                      settlement_status: "committed",
                      durability: "ledger",
                      control_job_attempt: 1,
                    },
                  ],
                },
              ],
            },
          ],
        },
      }).success,
    ).toBe(false);
    expect(
      runAgentsSchema.safeParse({
        ...response,
        pipeline: {
          ...response.pipeline,
          unattributed_cost_scalars: [{ ...scalar, scope: "current_attempt" }],
        },
      }).success,
    ).toBe(false);
    expect(
      runAgentsSchema.safeParse({
        ...response,
        pipeline: {
          ...response.pipeline,
          unattributed_cost_scalars: [{ ...scalar, claimed_value_usd: true }],
        },
      }).success,
    ).toBe(false);
  });

  it("materializes canonical defaults across nested AgentPipeline DTOs", () => {
    const legacyResponse = {
      meta: { request_id: "request-r9", generated_at: "2026-10-18T10:00:00Z" },
      pipeline: {
        run_id: "run-r9",
        source_kind: "core_run",
        total_attempts: 2,
        attempts: [
          {
            attempt: 2,
            steps: [
              {
                agent: "critic",
                action: "approved",
                cost_events: [
                  {
                    event_id: "event-r9",
                    cost_origin: "unknown",
                    settlement_status: "unknown",
                  },
                ],
                unattributed_cost_scalars: [
                  {
                    source_kind: "step_summary",
                    source_field: "cost_usd",
                    claimed_value_usd: 0.25,
                  },
                ],
              },
              { agent: "critic", action: "reviewed" },
            ],
          },
          { attempt: 3 },
        ],
      },
    };
    const parsed = runAgentsSchema.safeParse(legacyResponse);
    expect(parsed.success).toBe(true);
    if (!parsed.success)
      throw new Error("expected canonical legacy defaults to parse");

    const eventDefaults = {
      event_id: "event-r9",
      origin_event_id: null,
      cost_origin: "unknown",
      control_job_attempt: null,
      pre_admission_attempt_id: null,
      amount: null,
      cost_usd: null,
      settlement_status: "unknown",
      durability: null,
      receipts: [],
      payload_digest: null,
      model: null,
      provider: null,
    };
    const scalarDefaults = {
      source_kind: "step_summary",
      source_field: "cost_usd",
      claimed_value_usd: 0.25,
      scope: "not_established",
      attempt: null,
      agent: null,
      model: null,
      model_variant_id: null,
      source_index: null,
    };
    const stepDefaults = {
      attempt: 1,
      status: "info",
      timestamp: null,
      summary: null,
      details: {},
      details_cost_scope: "not_established",
      prompt: null,
      response: null,
      model: null,
      provider: null,
      model_variant_id: null,
      latency_ms: null,
      cost_usd: null,
      reported_cost_usd: null,
      estimated_cost_usd: null,
      cost_origin: null,
      cost_origin_counts: {},
      settlement_status_counts: {},
      settlement_event_ids: [],
      token_usage: {},
    };
    const attemptDefaults = {
      status: "unknown",
      verdict: null,
      started_at: null,
      finished_at: null,
      duration_ms: null,
      cost_usd: null,
      reported_cost_usd: null,
      estimated_cost_usd: null,
      cost_origin_counts: {},
      settlement_status_counts: {},
      unattributed_cost_scalars: [],
      notes: [],
    };
    expect(parsed.data.pipeline.owner_control_job_attempt).toBeNull();
    expect(parsed.data.pipeline.attempts).toEqual([
      {
        ...attemptDefaults,
        attempt: 2,
        steps: [
          {
            ...stepDefaults,
            agent: "critic",
            action: "approved",
            cost_events: [eventDefaults],
            unattributed_cost_scalars: [scalarDefaults],
          },
          {
            ...stepDefaults,
            agent: "critic",
            action: "reviewed",
            cost_events: [],
            unattributed_cost_scalars: [],
          },
        ],
      },
      { ...attemptDefaults, attempt: 3, steps: [] },
    ]);
    // A step default is independent of both its parent ordinal and owner evidence.
    expect(parsed.data.pipeline.attempts[0]?.steps[0]?.attempt).toBe(1);
  });

  it("keeps required AgentPipeline fields and malformed values distinct from defaults", () => {
    const legacyResponse = {
      meta: {
        request_id: "request-r9-controls",
        generated_at: "2026-10-18T10:00:00Z",
      },
      pipeline: {
        run_id: "run-r9-controls",
        source_kind: "core_run",
        total_attempts: 2,
        attempts: [
          {
            attempt: 2,
            steps: [
              {
                agent: "critic",
                action: "approved",
                cost_events: [
                  {
                    event_id: "event-r9",
                    cost_origin: "unknown",
                    settlement_status: "unknown",
                  },
                ],
                unattributed_cost_scalars: [
                  {
                    source_kind: "step_summary",
                    source_field: "cost_usd",
                    claimed_value_usd: 0.25,
                  },
                ],
              },
            ],
          },
        ],
      },
    };
    type Part = string | number;
    const setPath = (value: unknown, path: Part[], replacement: unknown) => {
      let current = value;
      for (const part of path.slice(0, -1)) {
        current = Array.isArray(current)
          ? current[part as number]
          : mutableRecord(current)[String(part)];
      }
      const last = path[path.length - 1];
      if (last === undefined) throw new Error("expected non-empty path");
      if (Array.isArray(current)) {
        if (typeof last !== "number")
          throw new Error("expected numeric array path");
        current[last] = replacement;
      } else mutableRecord(current)[String(last)] = replacement;
    };
    const deletePath = (value: unknown, path: Part[]) => {
      let current = value;
      for (const part of path.slice(0, -1)) {
        current = Array.isArray(current)
          ? current[part as number]
          : mutableRecord(current)[String(part)];
      }
      const last = path[path.length - 1];
      if (last === undefined) throw new Error("expected non-empty path");
      expect(Reflect.deleteProperty(current as object, String(last))).toBe(
        true,
      );
    };
    const collectPaths = (
      value: unknown,
      matches: (candidate: unknown) => boolean,
      path: Part[] = [],
    ): Part[][] => {
      if (matches(value)) return [path];
      if (Array.isArray(value)) {
        return value.flatMap((entry, index) =>
          collectPaths(entry, matches, [...path, index]),
        );
      }
      if (value && typeof value === "object") {
        return Object.entries(value).flatMap(([key, entry]) =>
          collectPaths(entry, matches, [...path, key]),
        );
      }
      return [];
    };
    const output = runAgentsSchema.parse(legacyResponse);
    const emptyObject = (value: unknown) =>
      value !== null &&
      typeof value === "object" &&
      !Array.isArray(value) &&
      Object.keys(value).length === 0;
    for (const [matches, malformedValue] of [
      [(value: unknown) => value === null, []],
      [(value: unknown) => Array.isArray(value), null],
      [emptyObject, null],
    ] as const) {
      for (const path of collectPaths(output, matches)) {
        const malformed = structuredClone(legacyResponse);
        setPath(malformed, path, malformedValue);
        expect(runAgentsSchema.safeParse(malformed).success).toBe(false);
      }
    }

    for (const path of collectPaths(output, (value) => value === null)) {
      const explicitNull = structuredClone(legacyResponse);
      setPath(explicitNull, path, null);
      expect(runAgentsSchema.safeParse(explicitNull).success).toBe(true);
    }

    const requiredPaths: Part[][] = [
      ["meta"],
      ["pipeline"],
      ["meta", "request_id"],
      ["meta", "generated_at"],
      ["pipeline", "run_id"],
      ["pipeline", "source_kind"],
      ["pipeline", "attempts", 0, "attempt"],
      ["pipeline", "attempts", 0, "steps", 0, "agent"],
      ["pipeline", "attempts", 0, "steps", 0, "action"],
      ["pipeline", "attempts", 0, "steps", 0, "cost_events", 0, "event_id"],
      ["pipeline", "attempts", 0, "steps", 0, "cost_events", 0, "cost_origin"],
      [
        "pipeline",
        "attempts",
        0,
        "steps",
        0,
        "cost_events",
        0,
        "settlement_status",
      ],
      [
        "pipeline",
        "attempts",
        0,
        "steps",
        0,
        "unattributed_cost_scalars",
        0,
        "source_kind",
      ],
      [
        "pipeline",
        "attempts",
        0,
        "steps",
        0,
        "unattributed_cost_scalars",
        0,
        "source_field",
      ],
      [
        "pipeline",
        "attempts",
        0,
        "steps",
        0,
        "unattributed_cost_scalars",
        0,
        "claimed_value_usd",
      ],
    ];
    expect(requiredPaths).toHaveLength(15);
    for (const path of requiredPaths) {
      const missing = structuredClone(legacyResponse);
      deletePath(missing, path);
      expect(runAgentsSchema.safeParse(missing).success).toBe(false);
    }

    const malformedValues: Array<[Part[], unknown]> = [
      [["pipeline", "attempts", 0, "steps", 0, "attempt"], null],
      [["pipeline", "attempts", 0, "steps", 0, "attempt"], 0],
      [["pipeline", "attempts", 0, "steps", 0, "attempt"], 1.5],
      [["pipeline", "attempts", 0, "steps", 0, "attempt"], true],
      [["pipeline", "attempts", 0, "attempt"], 1.5],
      [["pipeline", "attempts", 0, "attempt"], 0],
      [["pipeline", "attempts", 0, "attempt"], true],
      [["pipeline", "attempts", 0, "attempt"], null],
      [["pipeline", "attempts", 0, "duration_ms"], 0.5],
      [["pipeline", "attempts", 0, "cost_origin_counts"], { reported: 1.5 }],
      [
        ["pipeline", "attempts", 0, "settlement_status_counts"],
        { committed: 1.5 },
      ],
      [["pipeline", "attempts", 0, "status"], null],
      [["pipeline", "total_attempts"], -1],
      [["pipeline", "total_attempts"], 0.5],
      [["pipeline", "total_attempts"], true],
      [["pipeline", "total_attempts"], null],
      [["pipeline", "cost_origin_counts"], { reported: 1.5 }],
      [["pipeline", "settlement_status_counts"], { committed: 1.5 }],
      [["pipeline", "owner_control_job_attempt"], true],
      [["pipeline", "owner_control_job_attempt"], 0],
      [["pipeline", "owner_control_job_attempt"], 1.5],
      [["pipeline", "owner_control_job_attempt"], "2"],
      [["pipeline", "attempts", 0, "steps", 0, "latency_ms"], 1.5],
      [
        ["pipeline", "attempts", 0, "steps", 0, "cost_origin_counts"],
        { reported: 1.5 },
      ],
      [
        ["pipeline", "attempts", 0, "steps", 0, "settlement_status_counts"],
        { committed: 1.5 },
      ],
      [["pipeline", "attempts", 0, "steps", 0, "token_usage"], { input: 1.5 }],
      [["pipeline", "attempts", 0, "steps", 0, "status"], "blocked"],
      [["pipeline", "attempts", 0, "steps", 0, "status"], null],
      [
        ["pipeline", "attempts", 0, "steps", 0, "details_cost_scope"],
        "current",
      ],
      [["pipeline", "attempts", 0, "steps", 0, "details_cost_scope"], null],
      [
        [
          "pipeline",
          "attempts",
          0,
          "steps",
          0,
          "cost_events",
          0,
          "control_job_attempt",
        ],
        1.5,
      ],
      [
        [
          "pipeline",
          "attempts",
          0,
          "steps",
          0,
          "cost_events",
          0,
          "control_job_attempt",
        ],
        0,
      ],
      [
        [
          "pipeline",
          "attempts",
          0,
          "steps",
          0,
          "unattributed_cost_scalars",
          0,
          "attempt",
        ],
        0,
      ],
      [
        [
          "pipeline",
          "attempts",
          0,
          "steps",
          0,
          "unattributed_cost_scalars",
          0,
          "scope",
        ],
        "current",
      ],
      [
        [
          "pipeline",
          "attempts",
          0,
          "steps",
          0,
          "unattributed_cost_scalars",
          0,
          "scope",
        ],
        null,
      ],
      [
        [
          "pipeline",
          "attempts",
          0,
          "steps",
          0,
          "unattributed_cost_scalars",
          0,
          "attempt",
        ],
        1.5,
      ],
      [
        [
          "pipeline",
          "attempts",
          0,
          "steps",
          0,
          "unattributed_cost_scalars",
          0,
          "source_index",
        ],
        0.5,
      ],
      [
        [
          "pipeline",
          "attempts",
          0,
          "steps",
          0,
          "unattributed_cost_scalars",
          0,
          "claimed_value_usd",
        ],
        true,
      ],
    ];
    for (const [path, replacement] of malformedValues) {
      const malformed = structuredClone(legacyResponse);
      setPath(malformed, path, replacement);
      expect(runAgentsSchema.safeParse(malformed).success).toBe(false);
    }
    const explicitNullOwner = structuredClone(legacyResponse);
    setPath(explicitNullOwner, ["pipeline", "owner_control_job_attempt"], null);
    expect(runAgentsSchema.safeParse(explicitNullOwner).success).toBe(true);
  });

  it("materializes fresh defaults for an empty AgentPipeline view", () => {
    const response = {
      meta: {
        request_id: "request-empty-r9",
        generated_at: "2026-10-18T10:00:00Z",
      },
      pipeline: { run_id: "run-empty-r9", source_kind: "core_run" },
    };
    const first = runAgentsSchema.parse(response);
    const second = runAgentsSchema.parse(response);
    expect(first).toEqual({
      meta: {
        request_id: "request-empty-r9",
        generated_at: "2026-10-18T10:00:00Z",
        source_kinds: [],
      },
      pipeline: {
        run_id: "run-empty-r9",
        source_kind: "core_run",
        owner_control_job_attempt: null,
        total_attempts: 0,
        cost_usd: null,
        reported_cost_usd: null,
        estimated_cost_usd: null,
        cost_origin_counts: {},
        settlement_status_counts: {},
        latest_verdict: null,
        attempts: [],
        unattributed_cost_events: [],
        unattributed_cost_scalars: [],
        decision_packet_ref: null,
        reflexion_terminal_ref: null,
        retrieval: null,
        execution_plan_ref: null,
        method_catalog_snapshot_ref: null,
        preflight: null,
        evaluator: null,
        iteration_lifecycle: null,
        reproducibility: null,
        performance_summary: null,
        source: null,
        notes: [],
      },
    });
    expect(first.pipeline.notes).not.toBe(second.pipeline.notes);
    expect(first.pipeline.cost_origin_counts).not.toBe(
      second.pipeline.cost_origin_counts,
    );
    expect(first.pipeline.attempts).not.toBe(second.pipeline.attempts);
  });

  it("defaults opaque step details to an unestablished cost scope", () => {
    const legacyDetails = {
      meta: {
        request_id: "request-details-scope",
        generated_at: "2026-10-18T10:00:00Z",
      },
      pipeline: {
        run_id: "run-details-scope",
        source_kind: "core_run",
        total_attempts: 1,
        attempts: [
          {
            attempt: 1,
            status: "completed",
            steps: [
              {
                agent: "critic",
                action: "approved",
                details: {
                  nested: { cost_usd: 0.73, annotation: "diagnostic $9 only" },
                },
              },
            ],
          },
        ],
      },
    };
    const parsed = runAgentsSchema.safeParse(legacyDetails);
    expect(parsed.success).toBe(true);
    if (!parsed.success) {
      throw new Error("expected legacy details payload to parse");
    }
    expect(
      parsed.data.pipeline.attempts?.[0]?.steps?.[0]?.details_cost_scope,
    ).toBe("not_established");

    const malformed = structuredClone(legacyDetails);
    const malformedPipeline = mutableRecord(malformed.pipeline);
    const malformedAttempts = malformedPipeline.attempts as unknown[];
    const malformedAttempt = mutableRecord(malformedAttempts[0]);
    const malformedSteps = malformedAttempt.steps as unknown[];
    mutableRecord(malformedSteps[0]).details_cost_scope = "current";
    expect(runAgentsSchema.safeParse(malformed).success).toBe(false);
  });

  it("rejects current cost projections without a verified owner context", () => {
    const event = {
      event_id: "ownerless-current-ledger-claim",
      cost_origin: "reported",
      amount: "0.03",
      cost_usd: 0.03,
      settlement_status: "committed",
      durability: "ledger",
      control_job_attempt: 2,
      pre_admission_attempt_id: null,
    };
    const ownerless = {
      meta: {
        request_id: "request-ownerless",
        generated_at: "2026-10-18T10:00:00Z",
      },
      pipeline: {
        run_id: "run-ownerless",
        source_kind: "core_run",
        total_attempts: 1,
        cost_usd: 0.03,
        reported_cost_usd: 0.02,
        estimated_cost_usd: 0.01,
        cost_origin_counts: { reported: 1 },
        settlement_status_counts: { committed: 1 },
        attempts: [
          {
            attempt: 2,
            status: "completed",
            cost_usd: 0.03,
            reported_cost_usd: 0.02,
            estimated_cost_usd: 0.01,
            cost_origin_counts: { reported: 1 },
            settlement_status_counts: { committed: 1 },
            steps: [
              {
                agent: "llm_producer_settlement",
                action: "durable_ledger",
                cost_usd: 0.03,
                reported_cost_usd: 0.02,
                estimated_cost_usd: 0.01,
                cost_origin_counts: { reported: 1 },
                settlement_status_counts: { committed: 1 },
                cost_events: [event],
              },
            ],
          },
        ],
      },
    };

    expect(runAgentsSchema.safeParse(ownerless).success).toBe(false);
    const withoutProjection = (value: Record<string, unknown>) => ({
      ...value,
      cost_usd: null,
      reported_cost_usd: null,
      estimated_cost_usd: null,
      cost_origin_counts: {},
      settlement_status_counts: {},
    });
    const honestUnknown = {
      ...ownerless,
      pipeline: withoutProjection({
        ...ownerless.pipeline,
        attempts: ownerless.pipeline.attempts.map((attempt) =>
          withoutProjection({
            ...attempt,
            steps: attempt.steps.map((step) => withoutProjection(step)),
          }),
        ),
      }),
    };
    expect(runAgentsSchema.safeParse(honestUnknown).success).toBe(true);

    const noOwnerWithRawEvent = structuredClone(honestUnknown);
    expect(runAgentsSchema.safeParse(noOwnerWithRawEvent).success).toBe(true);

    for (const malformedOwner of [true, 0, 1.5, "2"]) {
      const malformed = {
        ...honestUnknown,
        pipeline: {
          ...honestUnknown.pipeline,
          owner_control_job_attempt: malformedOwner,
        },
      };
      expect(runAgentsSchema.safeParse(malformed).success).toBe(false);
    }
  });
});
