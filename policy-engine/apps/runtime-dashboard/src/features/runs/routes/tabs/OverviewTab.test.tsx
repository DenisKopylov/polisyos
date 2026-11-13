import { retainedAcquisitionHistoryFixture } from "@/test/fixtures/retainedAcquisitionHistory";
import { failedCandidateSimulationFixture } from "@/test/fixtures/failedCandidateSimulation";
import { fireEvent, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";

import { runDetailsSchema } from "../../../../api/validators";
import { runN5InteractionEvidenceFixture } from "@/test/fixtures/runN5InteractionEvidence";
import { predictiveCalibrationResponseFixture } from "@/test/fixtures/predictiveCalibrationResponse";
import { c41JointParentObservation } from "@/test/fixtures/c41JointParent";
import * as performanceTelemetry from "@/shared/telemetry/performance";
import { renderWithProviders } from "@/test/render";

const overviewState = vi.hoisted(() => ({
  artifactContentMock: vi.fn(),
  evidenceContextMock: vi.fn(),
  governanceDebugMock: vi.fn(),
  predictiveCalibrationQueryMock: vi.fn(),
  timelineMock: vi.fn(),
  predictiveCalibrationQuery: {
    isPending: true,
    error: undefined,
    data: undefined,
  } as Record<string, unknown>,
  predictiveCalibrationMutation: {
    isPending: false,
    isError: false,
    error: undefined as Error | undefined,
    mutate: vi.fn(),
  },
  canCreatePredictiveCalibration: false,
  decisionArtifact: null as Record<string, unknown> | null,
  primaryDecisionArtifactRef: null as Record<string, unknown> | null,
  run: { run_id: "run-1" } as Record<string, unknown>,
}));

vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useParams: () => ({ runId: "run-1" }) };
});
vi.mock("@/api/hooks/useGovernanceDebug", () => ({
  useSuspenseGovernanceDebug: (...args: unknown[]) =>
    overviewState.governanceDebugMock(...args),
}));
vi.mock("@/api/hooks/useRunEvidenceContext", () => ({
  useSuspenseRunEvidenceContext: (...args: unknown[]) =>
    overviewState.evidenceContextMock(...args),
}));
vi.mock("@/api/hooks/useRunTimeline", () => ({
  useSuspenseRunTimeline: (...args: unknown[]) =>
    overviewState.timelineMock(...args),
}));
vi.mock("@/api/hooks/useRunPredictiveCalibration", () => ({
  useRunPredictiveCalibration: (...args: unknown[]) => {
    overviewState.predictiveCalibrationQueryMock(...args);
    return overviewState.predictiveCalibrationQuery;
  },
  useCreateRunPredictiveCalibration: () =>
    overviewState.predictiveCalibrationMutation,
}));
vi.mock("@/api/hooks/useArtifactContent", () => ({
  useSuspenseArtifactContent: (...args: unknown[]) =>
    overviewState.artifactContentMock(...args),
}));
vi.mock("@/app/authz/AuthzProvider", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/app/authz/AuthzProvider")>();
  return {
    ...actual,
    usePermission: (permission: string) =>
      permission === "runs.feedback.evaluate" &&
      overviewState.canCreatePredictiveCalibration,
  };
});
vi.mock("@/app/providers/FeatureFlagProvider", async (importOriginal) => {
  const actual =
    await importOriginal<
      typeof import("@/app/providers/FeatureFlagProvider")
    >();
  return { ...actual, useFeatureFlag: () => false };
});
vi.mock("@/features/runs/context/RunInspectorContext", () => ({
  useRunInspector: () => ({
    blockerCount: 2,
    decisionHeadline: "Decision",
    evidenceContext: { dataNeeds: [], fetchPlans: [], promotionCandidates: [] },
    primaryDecisionArtifactId: null,
    primaryDecisionArtifactRef: overviewState.primaryDecisionArtifactRef,
    run: overviewState.run,
  }),
}));
vi.mock("@/shared/components/FeatureAsyncBoundary", () => ({
  FeatureAsyncBoundary: ({ children }: { children: ReactNode }) => children,
}));
vi.mock("@/features/runs/components/RunExplainabilityPanel", () => ({
  RunExplainabilityPanel: () => null,
}));
vi.mock("@/features/whatif", () => ({ ScenarioWorkbench: () => null }));

import OverviewTab from "./OverviewTab";

function parsedRun(candidateSimulation?: unknown): Record<string, unknown> {
  const { run } = runDetailsSchema.parse({
    meta: {
      request_id: "req-overview",
      generated_at: "2026-10-12T10:00:00Z",
      source_kinds: ["core_run"],
    },
    run: {
      run_id: "run-1",
      source_kind: "core_run",
      status: "failed",
      ...(candidateSimulation === undefined
        ? {}
        : { candidate_simulation: candidateSimulation }),
    },
    temporal_scope: null,
  });
  return { ...run };
}

function sameCandidateAcquisitionHistoryProjection() {
  const n4 = (d: string, p: string) => ({
    artifact_id: "sha256:" + d.repeat(64),
    kind: "runtime.quality.n4_candidate_scenario_source",
    media_type: "application/json",
    manifest_profile_sha256: "sha256:" + p.repeat(64),
  });
  const source = n4("a", "b"),
    root = n4("c", "d"),
    candidateId = "candidate-same";
  return {
    schema_version: "policyos.runtime.run_candidate_simulation_projection.v1",
    run_id: "run-1",
    artifact_status: "resolved",
    authority_purpose: "candidate_observation_only",
    publication_authority: false,
    source_ref: {
      artifact_id: "sha256:" + "e".repeat(64),
      kind: "runtime.compiled_recursive_generation_cycle",
      media_type: "application/json",
    },
    source_content_hash: "sha256:" + "f".repeat(64),
    limitation_code: null,
    n5_observations: [],
    acquisition_history_limitation_code: null,
    acquisition_history: [
      {
        route_receipt_ref: {
          artifact_id: "sha256:" + "1".repeat(64),
          kind: "runtime_quality.acquisition_route_loop_receipt",
          media_type: "application/json",
        },
        reentry_receipt_ref: {
          artifact_id: "sha256:" + "2".repeat(64),
          kind: "runtime_quality.acquisition_overlay_reentry_receipt",
          media_type: "application/json",
        },
        route_id: "sha256:" + "3".repeat(64),
        action_generation: 1,
        terminal_outcome: "reentry_completed",
        old_candidate_id: candidateId,
        new_candidate_id: candidateId,
        new_candidate_source_ref: source,
        origin_source_ref: root,
        expected_origin_source_ref: { ...root },
        schema_version:
          "policyos.runtime.run_candidate_simulation_acquisition_history.v2",
        reentry_receipt_schema_version:
          "policyos.runtime.acquisition_overlay_reentry.v3",
        continuation_join_status: "v3_occurrence_joined",
        origin_source_binding_status: "verified_same_candidate_root",
        continuation: {
          source_generation_run_content_hash: "sha256:" + "4".repeat(64),
          continued_generation_run_content_hash: "sha256:" + "5".repeat(64),
          source_cycle_index: 1,
          previous_n4_source_ref: root,
          previous_n5_input_ref: {
            artifact_id: "sha256:" + "6".repeat(64),
            kind: "runtime.quality.candidate_simulation_n5_input",
            media_type: "application/json",
            manifest_profile_sha256: "sha256:" + "7".repeat(64),
          },
          selected_n5_input_ref: {
            artifact_id: "sha256:" + "8".repeat(64),
            kind: "runtime.quality.candidate_simulation_n5_input",
            media_type: "application/json",
            manifest_profile_sha256: "sha256:" + "9".repeat(64),
          },
          selected_n4_source_ref: { ...source },
          previous_profile_selection_ref: "sha256:" + "a".repeat(64),
          previous_profile_content_hash: "sha256:" + "b".repeat(64),
          selected_profile_selection_ref: "sha256:" + "a".repeat(64),
          selected_profile_content_hash: "sha256:" + "c".repeat(64),
          selected_target_world_slot: "government.tax_rate",
          previous_selected_target_baseline_hash: "sha256:" + "d".repeat(64),
          selected_target_baseline_hash: "sha256:" + "e".repeat(64),
          continued_cycle_index: 2,
          source_currentness_status: "not_established",
          source_currentness_reason: "historical_observation",
          continuation_currentness_status: "not_established",
          continuation_currentness_reason: "historical_observation",
          n9_status: "not_promoted",
          n9_reason: "candidate_observation_only",
          n9_certified_candidate_ids: [],
          current_candidate_occurrences: [
            {
              candidate_id: candidateId,
              cycle_index: 2,
              content_hash: "sha256:" + "f".repeat(64),
              source_content_hash: null,
              front: "research",
              certified_by_n9: false,
            },
          ],
          current_fronts: {
            decision_candidate_ids: [],
            research_candidate_ids: [candidateId],
            quarantine_candidate_ids: [],
            portfolio_candidate_ids: [],
          },
          currentness_status: "not_established",
          authority_purpose: "candidate_observation_only",
          publication_authority: false,
        },
        currentness_status: "not_established",
        authority_purpose: "candidate_observation_only",
        publication_authority: false,
      },
    ],
  };
}

function genericCycleSimulationProjection(
  runId: string,
  terminalKinds?: Record<string, string> | null,
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
  const leafTerminalKinds =
    terminalKinds === undefined
      ? { ["design-problem://" + "d".repeat(64)]: "completed" }
      : (terminalKinds ?? undefined);
  const completedDesignRefs =
    terminalKinds != null && Object.keys(terminalKinds).length > 0
      ? Object.keys(terminalKinds)
      : [designProblemRef];

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
            atom_ids: ["atom-a", "atom-b", "atom-c"],
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
                run_level: "individual",
                atom_ids: ["atom-a"],
                points: [
                  {
                    step: 0,
                    outcomes: { "outcome-a": 0.45 },
                    effects: { "outcome-a": 0.05 },
                  },
                ],
              },
              {
                run_level: "individual",
                atom_ids: ["atom-b"],
                points: [
                  {
                    step: 0,
                    outcomes: { "outcome-a": 0.55 },
                    effects: { "outcome-a": 0.15 },
                  },
                ],
              },
              {
                run_level: "joint",
                atom_ids: ["atom-a", "atom-b", "atom-c"],
                points: [
                  {
                    step: 0,
                    outcomes: { "outcome-a": 0.75 },
                    effects: { "outcome-a": 3.25 },
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
    const interactionEvidence = runN5InteractionEvidenceFixture();
    interactionEvidence.numeric_interaction = "additive";
    return {
      atom_ids:
        status === "joint_simulated"
          ? ["atom-a", "atom-b", "atom-c"]
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
      n8_authority_blockers: ["n9_not_admitted"],
      n8_limitation_code:
        status === "joint_simulated"
          ? null
          : "generic_n5_request_binding_not_established",
      n8_lineage_status:
        status === "joint_simulated" ? "resolved" : "not_established",
      n8_numeric_interaction:
        status === "joint_simulated"
          ? interactionEvidence.numeric_interaction
          : null,
      n8_numeric_interaction_basis:
        status === "joint_simulated"
          ? interactionEvidence.numeric_interaction_basis
          : null,
      n8_interaction_sampling_status:
        status === "joint_simulated"
          ? interactionEvidence.interaction_sampling_status
          : null,
      n8_status:
        status === "joint_simulated" ? "value_conditional" : "value_pending_n8",
      n8_value_ref: resultRef?.artifact_id ?? null,
      n5_interaction_evidence:
        status === "joint_simulated" ? interactionEvidence : null,
      executed_steps: status === "joint_simulated" ? [0] : [],
      replication_seeds: status === "joint_simulated" ? [41, 42] : [],
      node_ref: "design-problem://" + digest.repeat(64),
      profile_ref: profileRef,
      profile_selection_ref: "sha256:" + "e".repeat(64),
      publication_authority: false,
      selected_outcomes: status === "joint_simulated" ? ["outcome-a"] : [],
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
      completed_design_refs: completedDesignRefs,
      root_n9_status: "not_run",
      leaf_terminal_kinds: leafTerminalKinds,
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

function genericRootOnlyCycleSimulationProjection(runId: string) {
  const projection = genericCycleSimulationProjection(runId);
  const rootObservation = {
    ...projection.n5_observations[0]!,
    child_profile_family_ref: null,
    child_profile_set_ref: null,
    n5_owner_join_status: "resolved",
    n5_owner_join_limitation_code: null,
    simulation_result_body: null,
    simulation_result_body_status: "not_established",
    simulation_result_body_limitation_code:
      "generic_n5_result_body_request_binding_not_established",
    n8_status: "value_pending_n8",
    n8_lineage_status: "not_established",
    n8_value_ref: null,
    n8_limitation_code: "value_gate_pending_n8",
    n8_authority_blockers: ["value_gate_pending_n8"],
    n5_interaction_evidence: null,
    n8_numeric_interaction: null,
    n8_numeric_interaction_basis: null,
    n8_interaction_sampling_status: null,
  };
  Object.assign(projection, {
    schema_version:
      "policyos.runtime.run_generic_cycle_simulation_projection.v5",
    child_profile_family_ref: null,
    child_profile_set_ref: null,
    child_profile_status: "not_established",
    child_profile_limitation_code:
      "generic_n4_child_profile_family_not_established",
    child_profile_bindings: [],
    n5_observations: [rootObservation],
    n5_limitation_code: null,
    limitation_code: null,
    recursive_cycle_checkpoint: null,
    candidate_evaluation_attempts: [
      {
        node_ref: rootObservation.node_ref,
        candidate_id: "first-local-failure",
        candidate_content_hash: "sha256:" + "a".repeat(64),
        cycle_index: 0,
        problem_ref: rootObservation.design_problem_ref,
        attempt_ref: "sha256:" + "b".repeat(64),
        failure_stage: "n5",
        failure_scope: "candidate_local",
        simulation_status: "simulation_blocked",
        value_status: "value_pending_n8",
      },
    ],
  });
  return projection;
}

function selectedNumericalAcquisitionProjection() {
  // Display-only composition; the served backend test qualifies owner replay.
  const projection = sameCandidateAcquisitionHistoryProjection();
  const entry = projection.acquisition_history[0]!;
  const original = failedCandidateSimulationFixture().n5_observations[0]!;
  const observation = {
    ...original,
    candidate_id: entry.new_candidate_id,
    cycle_index: entry.continuation.continued_cycle_index,
    n4_source_ref: entry.new_candidate_source_ref,
    n5_input_ref: entry.continuation.selected_n5_input_ref,
    profile_selection_ref: entry.continuation.selected_profile_selection_ref,
    result_body: {
      ...original.result_body,
      outcome_units: { "government.balance": "declared_currency_unit" },
      unit_provenance: "declared_candidate_model",
      model_declaration_ref: {
        artifact_id: "sha256:" + "e".repeat(64),
        kind: "runtime.quality.candidate_simulation_model_declaration",
        media_type: "application/json",
        manifest_profile_sha256: "sha256:" + "f".repeat(64),
      },
    },
  };
  return {
    ...projection,
    acquisition_history: [
      {
        ...entry,
        evaluation_provenance: "new_execution",
        selected_n5_observation: observation,
        continuation: {
          ...entry.continuation,
          current_candidate_occurrences:
            entry.continuation.current_candidate_occurrences.map((row) => ({
              ...row,
              front: "quarantine",
            })),
          current_fronts: {
            ...entry.continuation.current_fronts,
            research_candidate_ids: [],
            quarantine_candidate_ids: [entry.new_candidate_id],
          },
        },
      },
    ],
  };
}

function modelRevisedAcquisitionProjection() {
  const projection = selectedNumericalAcquisitionProjection();
  const entry = projection.acquisition_history[0]!;
  const ref = (kind: string, digit: string) => ({
    artifact_id: "sha256:" + digit.repeat(64),
    kind,
    media_type: "application/json",
    manifest_profile_sha256: "sha256:" + "f".repeat(64),
  });
  return {
    ...projection,
    acquisition_history: [
      {
        ...entry,
        continuation: {
          ...entry.continuation,
          selected_target_baseline_hash:
            entry.continuation.previous_selected_target_baseline_hash,
          model_revision: {
            evaluation_decision_ref: ref(
              "runtime_quality.acquisition_evaluation_decision",
              "1",
            ),
            previous_input_ref: entry.continuation.previous_n5_input_ref,
            selected_input_ref: entry.continuation.selected_n5_input_ref,
            previous_declaration_ref: ref(
              "runtime.quality.candidate_simulation_model_declaration",
              "4",
            ),
            selected_declaration_ref:
              entry.selected_n5_observation.result_body.model_declaration_ref,
            previous_ncm_ref: ref("ir.ncm_spec", "5"),
            selected_ncm_ref: ref("ir.ncm_spec", "6"),
            previous_basis_ref: ref(
              "runtime_quality.acquisition_evaluation_basis",
              "7",
            ),
            selected_basis_ref: ref(
              "runtime_quality.acquisition_evaluation_basis",
              "8",
            ),
            changed_field: "outcome_per_target_unit",
            predicate_provenance: "recomputed",
            authority_purpose: "candidate_observation_only",
            publication_authority: false,
          },
        },
      },
    ],
  };
}

function authoredJointParentObservation() {
  // A display-contract fixture; the served test verifies the request and CAS relation.
  const original = c41JointParentObservation();
  const derivedIds = [
    "atom_aaaaaaaaaaaaaaaa",
    "atom_bbbbbbbbbbbbbbbb",
    "atom_cccccccccccccccc",
  ];
  const ref = (kind: string, digit: string) => ({
    artifact_id: "sha256:" + digit.repeat(64),
    kind,
    media_type: "application/json",
    manifest_profile_sha256: "sha256:" + "f".repeat(64),
  });
  const evidence = original.n5_interaction_evidence!;
  return {
    ...original,
    n5_interaction_evidence: {
      ...evidence,
      schema_version: "policyos.runtime.joint_simulation_horizon.v5",
    },
    n8_candidate_member_basis: "authored_materialized_n4_source_members",
    n8_selected_member_relationship: "joint_components",
    n8_candidate_derived_atom_ids: [...derivedIds],
    n8_candidate_derived_atom_content_hashes: ["a", "b", "c"].map(
      (digit) => "sha256:" + digit.repeat(64),
    ),
    n8_candidate_parent_intervention_ids: [...original.atom_ids],
    n8_policy_composition_status: "authored_candidate",
    n8_policy_composition_limitation_code:
      "authored_candidate_coupling_not_established",
    n8_authored_joint_relation_ref: ref(
      "runtime.quality.recursive_authored_joint_relation",
      "7",
    ),
    n8_authored_joint_request_payload_ref: ref(
      "runtime.control_job_payload.natural_language_run",
      "8",
    ),
    n8_authored_joint_intent_digest: "sha256:" + "9".repeat(64),
    n8_authority_blockers: original.n8_authority_blockers!.map((code) =>
      code ===
      "n4_source_candidates_are_alternatives_not_authored_compound_design"
        ? "authored_candidate_coupling_not_established"
        : code,
    ),
  };
}
function currentCheapConsequencesFixture(evaluation: {
  candidate_id: string;
  candidate_content_hash: string;
  cycle_index: number;
}) {
  return {
    source_cycle_index: evaluation.cycle_index,
    candidate_id: evaluation.candidate_id,
    candidate_content_hash: evaluation.candidate_content_hash,
    grounding_status: "grounding_failed",
    grounding_current_valid: false,
    value_status: "value_blocked",
    value_decision_grade: "blocked",
    value_authority_blockers: ["current_source_invalidation"],
    value_ref: null,
    voi_next_action: "blocked",
    voi_reason:
      "The current source requires repair before another policy action.",
    terminal_kind: "tool_failure",
    refinement_decision: "block_candidate",
    search_iteration_status: "blocked_no_retry",
    current_planner_report_ref: null,
    scope: "current_cheap_consequences_at_recorded_action",
    numerical_provenance: "retained_prior",
  };
}

function parsedRunWithGenericCycleSimulation(
  projectionRunId = "run-1",
  terminalKinds?: Record<string, string> | null,
  includeCycleHistory = false,
  historyVersion: "v3" | "v4" = "v3",
): Record<string, unknown> {
  const projection = genericCycleSimulationProjection(
    projectionRunId,
    terminalKinds,
  );
  if (includeCycleHistory) {
    Object.assign(projection, {
      schema_version:
        historyVersion === "v3"
          ? "policyos.runtime.run_generic_cycle_simulation_projection.v3"
          : "policyos.runtime.run_generic_cycle_simulation_projection.v4",
      n6_cycle_history_status: "resolved",
      n6_cycle_history_limitation_code: null,
      n6_cycle_history: [
        {
          cycle_index: 2,
          design_problem_basis_ref: null,
          design_problem_ref: "sha256:" + "d".repeat(64),
          generation_cycle_run_terminal_status: "completed",
          grounding_current_valid: false,
          grounding_status: "grounded_shadow",
          node_ref: "design-problem://" + "d".repeat(64),
          refinement_decision: "refine",
          search_iteration_status: "refined_shadow",
          selected_candidate_content_hash: "sha256:" + "a".repeat(64),
          selected_candidate_ref: "candidate://candidate-a",
          terminal_kind: "grounded_partial_admissible",
          value_authority_blockers: ["publication_not_admitted"],
          value_decision_grade: "medium",
          value_ref: "sha256:" + "b".repeat(64),
          value_status: "value_conditional",
          voi_next_action: "advance",
        },
      ],
      ...(historyVersion === "v4"
        ? {
            credal_source_attempt_ref: null,
            credal_source_limitation_code:
              "candidate_source_authority_not_established",
            credal_source_status: "not_established",
            child_profile_bindings: [],
            child_profile_set_ref: null,
            child_profile_status: "not_established",
            child_profile_limitation_code:
              "generic_n4_source_generation_not_complete",
            n5_observations: [],
            n5_limitation_code: "generic_n4_source_generation_not_complete",
            limitation_code: "candidate_source_authority_not_established",
          }
        : {}),
    });
  }
  const { run } = runDetailsSchema.parse({
    meta: {
      request_id: "req-generic-cycle",
      generated_at: "2026-10-11T10:00:00Z",
      source_kinds: ["core_run"],
    },
    run: {
      run_id: "run-1",
      source_kind: "core_run",
      status: "failed",
      generic_cycle_simulation: projection,
    },
    temporal_scope: null,
  });
  return { ...run };
}

function runWithJointParent(parent: unknown): Record<string, unknown> {
  const run = parsedRunWithGenericCycleSimulation();
  const projection = run.generic_cycle_simulation as Record<string, unknown>;
  Object.assign(projection, {
    schema_version:
      "policyos.runtime.run_generic_cycle_simulation_projection.v5",
    joint_parent_status: "resolved",
    joint_parent_observations: [parent],
    n5_observations: (
      projection.n5_observations as Record<string, unknown>[]
    ).map((row, index) =>
      index === 0
        ? { ...row, n5_owner_join_status: "resolved" }
        : {
            ...row,
            n5_owner_join_status: "not_established",
            n5_owner_join_limitation_code:
              "generic_n5_owner_ref_not_established",
          },
    ),
  });
  return run;
}

describe("OverviewTab", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    overviewState.evidenceContextMock.mockReset();
    overviewState.evidenceContextMock.mockReturnValue({
      data: { context: {} },
    });
    overviewState.governanceDebugMock.mockReset();
    overviewState.governanceDebugMock.mockReturnValue({
      data: {
        debug: {
          issues: [
            { code: "known", message: "Known blocker", severity: "fail" },
            {
              code: "novel",
              message: "Novel severity",
              severity: "future_owner_severity",
            },
          ],
        },
      },
    });
    overviewState.predictiveCalibrationQueryMock.mockReset();
    overviewState.timelineMock.mockReset();
    overviewState.timelineMock.mockReturnValue({
      data: { timeline: { events: [] } },
    });
    overviewState.artifactContentMock.mockReset();
    overviewState.artifactContentMock.mockImplementation(() => ({
      data: { artifact: overviewState.decisionArtifact },
    }));
    overviewState.decisionArtifact = null;
    overviewState.predictiveCalibrationQuery = {
      isPending: true,
      error: undefined,
      data: undefined,
    };
    overviewState.primaryDecisionArtifactRef = null;
    overviewState.canCreatePredictiveCalibration = false;
    overviewState.predictiveCalibrationMutation = {
      isPending: false,
      isError: false,
      error: undefined,
      mutate: vi.fn(),
    };
    overviewState.run = parsedRun();
  });

  it("routes Core-only overview reads through the resolved Core identity", () => {
    overviewState.run = { ...parsedRun(), run_id: "core-attempt-7" };

    renderWithProviders(<OverviewTab />);

    expect(overviewState.governanceDebugMock).toHaveBeenCalledWith(
      "core-attempt-7",
    );
    expect(overviewState.evidenceContextMock).toHaveBeenCalledWith(
      "core-attempt-7",
    );
    expect(overviewState.timelineMock).toHaveBeenCalledWith("core-attempt-7");
    expect(overviewState.predictiveCalibrationQueryMock).toHaveBeenCalledWith(
      "core-attempt-7",
    );
  });

  it("keeps the run-bound action hidden without the existing evaluation permission", () => {
    overviewState.predictiveCalibrationQuery = {
      isPending: false,
      error: { status: 404, code: "run_predictive_calibration_not_found" },
      data: undefined,
    };

    renderWithProviders(<OverviewTab />);

    expect(
      screen.getByTestId("overview-predictive-calibration-permission"),
    ).toBeVisible();
    expect(
      screen.queryByTestId("overview-predictive-calibration-form"),
    ).not.toBeInTheDocument();
  });

  it("submits exact selected run refs with a new intent and no parameter defaults", () => {
    const candidate = {
      artifact_id: `sha256:${"a".repeat(64)}`,
      kind: "runtime.quality.n4_candidate_scenario_source",
      media_type: "application/json",
      manifest_profile_sha256: `sha256:${"b".repeat(64)}`,
    };
    const observed = {
      artifact_id: `sha256:${"c".repeat(64)}`,
      kind: "fabric.data_snapshot",
      media_type: "application/json",
      manifest_profile_sha256: `sha256:${"d".repeat(64)}`,
    };
    const valueDataProfile = {
      artifact_id: `sha256:${"2".repeat(64)}`,
      kind: "runtime.value_data_profile",
      media_type: "application/json",
      manifest_profile_sha256: `sha256:${"3".repeat(64)}`,
    };
    const nonJsonValueDataProfile = {
      artifact_id: `sha256:${"4".repeat(64)}`,
      kind: "runtime.value_data_profile",
      media_type: "text/plain",
      manifest_profile_sha256: `sha256:${"5".repeat(64)}`,
    };
    const model = {
      ...observed,
      artifact_id: `sha256:${"e".repeat(64)}`,
      kind: "ir.model_spec",
    };
    const policy = {
      ...observed,
      artifact_id: `sha256:${"f".repeat(64)}`,
      kind: "ir.policy_spec",
    };
    const rule = {
      ...observed,
      artifact_id: `sha256:${"1".repeat(64)}`,
      kind: "ir.forecast_calibration_rule",
    };
    overviewState.canCreatePredictiveCalibration = true;
    overviewState.predictiveCalibrationQuery = {
      isPending: false,
      error: { status: 404, code: "run_predictive_calibration_not_found" },
      data: undefined,
    };
    overviewState.run = {
      run_id: "run-1",
      source_kind: "core_run",
      root_artifacts: [model, policy, rule],
      root_input_artifacts: [
        observed,
        nonJsonValueDataProfile,
        valueDataProfile,
      ],
      candidate_simulation: {
        run_id: "run-1",
        artifact_status: "resolved",
        n5_observations: [
          {
            status: "joint_simulated",
            lineage_status: "resolved",
            n4_source_ref: candidate,
          },
        ],
      },
    };
    vi.stubGlobal("crypto", { randomUUID: () => "intent-r228-1" });

    const view = renderWithProviders(<OverviewTab />);

    expect(screen.getByTestId("predictive-candidate-source")).toHaveValue("");
    expect(screen.getByTestId("predictive-observed-source")).toHaveValue("");
    expect(screen.getByTestId("predictive-threshold")).toHaveValue(null);
    const form = screen.getByTestId("overview-predictive-calibration-form");
    const valueDataProfileSelect = screen.getByTestId(
      "predictive-value-data-profile",
    );
    expect(
      within(valueDataProfileSelect).queryByRole("option", {
        name: `runtime.value_data_profile · ${nonJsonValueDataProfile.artifact_id}`,
      }),
    ).not.toBeInTheDocument();
    const values: Record<string, string> = {
      candidate_source_ref: JSON.stringify([
        candidate.artifact_id,
        candidate.kind,
        candidate.media_type,
        candidate.manifest_profile_sha256,
      ]),
      observed_source_ref: JSON.stringify([
        observed.artifact_id,
        observed.kind,
        observed.media_type,
        observed.manifest_profile_sha256,
      ]),
      model_spec_ref: JSON.stringify([
        model.artifact_id,
        model.kind,
        model.media_type,
        model.manifest_profile_sha256,
      ]),
      policy_spec_ref: JSON.stringify([
        policy.artifact_id,
        policy.kind,
        policy.media_type,
        policy.manifest_profile_sha256,
      ]),
      calibration_rule_ref: JSON.stringify([
        rule.artifact_id,
        rule.kind,
        rule.media_type,
        rule.manifest_profile_sha256,
      ]),
      target_metric: "metric",
      calibration_threshold: "0.9",
      seed: "0",
      train_start: "0",
      train_end: "30",
      holdout_start: "30",
      holdout_end: "34",
      horizon: "4",
      alpha: "0.3",
      beta: "0.1",
      data_valid_time: "2026-01-01T00:00",
      calibration_window_start: "2026-01-02T00:00",
      calibration_window_end: "2026-01-03T00:00",
      policy_effective_time: "2026-01-04T00:00",
      prediction_time: "2026-01-05T00:00",
      observation_time: "2026-01-06T00:00",
    };
    for (const [name, value] of Object.entries(values)) {
      const input = within(form).getByLabelText(/.+/, {
        selector: `[name="${name}"]`,
      });
      fireEvent.change(input, { target: { value } });
    }
    fireEvent.change(screen.getByTestId("predictive-value-data-profile"), {
      target: {
        value: JSON.stringify([
          valueDataProfile.artifact_id,
          valueDataProfile.kind,
          valueDataProfile.media_type,
          valueDataProfile.manifest_profile_sha256,
        ]),
      },
    });
    fireEvent.change(screen.getByTestId("predictive-value-data-unit"), {
      target: { value: "UA" },
    });
    fireEvent.submit(form);

    const submitted =
      overviewState.predictiveCalibrationMutation.mutate.mock.calls[0]?.[0];
    expect(submitted).toMatchObject({
      intent_id: "intent-r228-1",
      candidate_source_ref: candidate,
      observed_source_ref: observed,
      model_spec_ref: model,
      policy_spec_ref: policy,
      calibration_rule_ref: rule,
      value_data_profile_ref: valueDataProfile,
      value_data_unit_id: "UA",
      split: {
        train_start: 0,
        train_end: 30,
        holdout_start: 30,
        holdout_end: 34,
        horizon: 4,
      },
    });
    expect(submitted.candidate_source_ref.manifest_profile_sha256).toBe(
      candidate.manifest_profile_sha256,
    );

    overviewState.predictiveCalibrationMutation.isError = true;
    overviewState.predictiveCalibrationMutation.error = new Error(
      "response lost after persistence",
    );
    view.rerender(<OverviewTab />);
    fireEvent.click(
      screen.getByTestId("overview-predictive-calibration-retry"),
    );
    expect(
      overviewState.predictiveCalibrationMutation.mutate,
    ).toHaveBeenNthCalledWith(2, submitted);
  });

  it("keeps hook order and the selected profile through a mismatch-to-live transition", () => {
    const milestoneSpy = vi.spyOn(performanceTelemetry, "markUiMilestone");
    const latencySpy = vi.spyOn(performanceTelemetry, "measureUiLatency");
    const decisionReadyName = "runs.overview.decision.ready";
    const decisionReadyContext = {
      routeId: "runs.detail.overview",
      surface: "overview",
    };
    const decisionReadyMilestones = () =>
      milestoneSpy.mock.calls.filter(([name]) => name === decisionReadyName);
    const decisionReadyLatencies = () =>
      latencySpy.mock.calls.filter(
        ([input]) => input.endMark === decisionReadyName,
      );
    const profile = `sha256:${"a".repeat(64)}`;
    const selectedRef = {
      artifact_id: "decision-artifact",
      kind: "scientist.decision_packet",
      media_type: "application/json",
      manifest_profile_sha256: profile,
    };
    overviewState.primaryDecisionArtifactRef = selectedRef;
    overviewState.decisionArtifact = {
      ...selectedRef,
      manifest_profile_sha256: `sha256:${"b".repeat(64)}`,
      mode: "preview",
    };

    const view = renderWithProviders(<OverviewTab />);

    expect(
      screen.getByTestId("overview-artifact-profile-mismatch"),
    ).toBeVisible();
    expect(overviewState.artifactContentMock).toHaveBeenNthCalledWith(
      1,
      selectedRef,
      { maxBytes: 256 * 1024 },
    );
    expect(decisionReadyMilestones()).toEqual([]);
    expect(decisionReadyLatencies()).toEqual([]);

    overviewState.decisionArtifact = { ...selectedRef, mode: "preview" };
    view.rerender(<OverviewTab />);

    expect(
      screen.queryByTestId("overview-artifact-profile-mismatch"),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId("overview-reading-view-link")).toHaveAttribute(
      "href",
      expect.stringContaining(encodeURIComponent(profile)),
    );
    expect(overviewState.artifactContentMock).toHaveBeenNthCalledWith(
      2,
      selectedRef,
      { maxBytes: 256 * 1024 },
    );
    expect(decisionReadyMilestones()).toEqual([
      [decisionReadyName, decisionReadyContext],
    ]);
    expect(decisionReadyLatencies()).toEqual([
      [
        {
          context: decisionReadyContext,
          endMark: decisionReadyName,
          metric: "time_to_decision_ms",
        },
      ],
    ]);
  });

  it("shows empirical predictive evidence with explicit authority and time limits", () => {
    overviewState.predictiveCalibrationQuery = {
      isPending: false,
      error: undefined,
      data: {
        association: {
          schema_version:
            "polisyos.runtime.predictive_calibration_association.v5",
          assessment: "limited",
          authority_scope: "predictive_only",
          intent_id: "intent-ui-fixture",
          observed_numerator: 3,
          observed_denominator: 4,
          observed_hit_rate: 0.75,
          issuer_status: "not_established",
          source_time_status: "not_established",
          population_scope_status: "not_established",
          counterfactual_credibility_status: "not_established",
          evidence_reason_codes: [],
          empirical_evidence_ref: { artifact_id: `sha256:${"a".repeat(64)}` },
          uncertainty_bundle_ref: {
            artifact_id: `sha256:${"b".repeat(64)}`,
            kind: "ir.forecasting_uncertainty_bundle",
            media_type: "application/json",
            manifest_profile_sha256: `sha256:${"c".repeat(64)}`,
          },
          s10: {
            calibration_status: "limit",
            forecast_tier: "limited_local_model",
          },
        },
      },
    };

    renderWithProviders(<OverviewTab />);

    const panel = screen.getByTestId("overview-predictive-calibration");
    expect(panel).toHaveTextContent("Empirical predictive diagnostic");
    expect(panel).toHaveTextContent("3 / 4");
    expect(panel).toHaveTextContent("75%");
    expect(
      screen.queryByTestId(
        "overview-predictive-calibration-observation-limitation",
      ),
    ).not.toBeInTheDocument();
    expect(panel).toHaveTextContent("predictive_only");
    expect(panel).toHaveTextContent("not_established");
    expect(panel).toHaveTextContent("not a policy recommendation");
    const intervalLink = screen.getByTestId(
      "overview-predictive-uncertainty-bundle",
    ) as HTMLAnchorElement;
    const selectedRef = JSON.parse(
      new URL(intervalLink.href).searchParams.get("artifactRefKey") ?? "null",
    );
    expect(selectedRef).toEqual([
      `sha256:${"b".repeat(64)}`,
      "ir.forecasting_uncertainty_bundle",
      "application/json",
      `sha256:${"c".repeat(64)}`,
    ]);
  });

  it("withholds populated diagnostic counts when the v5 source is not established", () => {
    overviewState.predictiveCalibrationQuery = {
      isPending: false,
      error: undefined,
      data: {
        association: {
          ...predictiveCalibrationResponseFixture.association,
          schema_version:
            "polisyos.runtime.predictive_calibration_association.v5",
          observed_numerator: 99,
          observed_denominator: 100,
          observed_hit_rate: 0.99,
          evidence_reason_codes: ["backtest_source_not_established"],
        },
      },
    };

    renderWithProviders(<OverviewTab />);

    const panel = screen.getByTestId("overview-predictive-calibration");
    expect(panel).toHaveTextContent(
      "The diagnostic could not be verified and is withheld.",
    );
    expect(panel).not.toHaveTextContent("99 / 100");
    expect(panel).not.toHaveTextContent("99%");
    expect(
      screen.getByTestId(
        "overview-predictive-calibration-observation-limitation",
      ),
    ).toHaveTextContent("backtest source has not been established");
  });

  it("shows unavailable for null v5 observations with the source limitation", () => {
    overviewState.predictiveCalibrationQuery = {
      isPending: false,
      error: undefined,
      data: {
        association: {
          ...predictiveCalibrationResponseFixture.association,
          schema_version:
            "polisyos.runtime.predictive_calibration_association.v5",
          observed_numerator: null,
          observed_denominator: null,
          observed_hit_rate: null,
          evidence_reason_codes: ["backtest_source_not_established"],
        },
      },
    };

    renderWithProviders(<OverviewTab />);

    const panel = screen.getByTestId("overview-predictive-calibration");
    expect(panel).toHaveTextContent(
      "The diagnostic could not be verified and is withheld.",
    );
    expect(panel).not.toHaveTextContent("3 / 4");
    expect(panel).not.toHaveTextContent("75%");
    expect(
      screen.getByTestId(
        "overview-predictive-calibration-observation-limitation",
      ),
    ).toHaveTextContent("backtest source has not been established");
  });

  it("keeps historical populated counts unavailable when the admission flag is missing", () => {
    const { evidence_reason_codes: _historicalReasonCodes, ...historical } =
      predictiveCalibrationResponseFixture.association;
    overviewState.predictiveCalibrationQuery = {
      isPending: false,
      error: undefined,
      data: {
        association: {
          ...historical,
          schema_version:
            "polisyos.runtime.predictive_calibration_association.v4",
          observed_numerator: 12,
          observed_denominator: 12,
          observed_hit_rate: 1,
        },
      },
    };

    renderWithProviders(<OverviewTab />);

    const panel = screen.getByTestId("overview-predictive-calibration");
    expect(panel).toHaveTextContent(
      "The diagnostic could not be verified and is withheld.",
    );
    expect(panel).not.toHaveTextContent("12 / 12");
    expect(panel).not.toHaveTextContent("100%");
    expect(
      screen.getByTestId(
        "overview-predictive-calibration-observation-limitation",
      ),
    ).toHaveTextContent("historical diagnostic");
    expect(
      screen.getByTestId(
        "overview-predictive-calibration-observation-limitation",
      ),
    ).toHaveTextContent("not reported as observed");
  });

  it("does not infer observed counts when the saved association version is missing", () => {
    const {
      schema_version: _historicalSchemaVersion,
      evidence_reason_codes: _historicalReasonCodes,
      ...unversionedHistorical
    } = predictiveCalibrationResponseFixture.association;
    overviewState.predictiveCalibrationQuery = {
      isPending: false,
      error: undefined,
      data: {
        association: {
          ...unversionedHistorical,
          observed_numerator: 7,
          observed_denominator: 8,
          observed_hit_rate: 0.875,
        },
      },
    };

    renderWithProviders(<OverviewTab />);

    const panel = screen.getByTestId("overview-predictive-calibration");
    expect(panel).toHaveTextContent(
      "The diagnostic could not be verified and is withheld.",
    );
    expect(panel).not.toHaveTextContent("7 / 8");
    expect(panel).not.toHaveTextContent("87.5%");
    expect(
      screen.getByTestId(
        "overview-predictive-calibration-observation-limitation",
      ),
    ).toHaveTextContent("historical diagnostic");
  });

  it.each(["v3", "v4"] as const)(
    "renders the parsed %s cycle history as candidate-only run detail",
    (version) => {
      overviewState.run = parsedRunWithGenericCycleSimulation(
        "run-1",
        undefined,
        true,
        version,
      );

      renderWithProviders(<OverviewTab />);

      const panel = screen.getByTestId("overview-generic-cycle-simulation");
      expect(panel).toHaveTextContent(
        "Persisted candidate lineage only. Currentness and publication authority are not established.",
      );
      expect(
        screen.getByTestId("overview-generic-cycle-history-status"),
      ).toHaveTextContent("Cycle history status: resolved");
      const rows = screen.getAllByTestId("overview-generic-cycle-history-row");
      expect(rows).toHaveLength(1);
      expect(rows[0]).toHaveTextContent("cycle 2");
      expect(rows[0]).toHaveTextContent("candidate://candidate-a");
      expect(rows[0]).toHaveTextContent("grounded_partial_admissible");
      expect(rows[0]).toHaveTextContent("current valid: false");
      expect(panel).not.toHaveTextContent("publication_ready");
    },
  );

  it("renders a resolved root N5 owner join with an unavailable body, child-profile limitation and local failure", () => {
    const projection = genericRootOnlyCycleSimulationProjection("run-1");
    const { run } = runDetailsSchema.parse({
      meta: {
        request_id: "req-root-only-cycle",
        generated_at: "2026-10-12T10:00:00Z",
        source_kinds: ["core_run"],
      },
      run: {
        run_id: "run-1",
        source_kind: "core_run",
        status: "failed",
        generic_cycle_simulation: projection,
      },
      temporal_scope: null,
    });
    overviewState.run = { ...run };

    expect(run.generic_cycle_simulation?.n5_observations[0]).toMatchObject({
      n8_status: "value_pending_n8",
      n8_lineage_status: "not_established",
      n8_value_ref: null,
      n8_limitation_code: "value_gate_pending_n8",
      n8_authority_blockers: ["value_gate_pending_n8"],
      n5_interaction_evidence: null,
      simulation_result_body: null,
      simulation_result_body_status: "not_established",
    });

    renderWithProviders(<OverviewTab />);

    const panel = screen.getByTestId("overview-generic-cycle-simulation");
    expect(
      screen.getByTestId("overview-generic-cycle-simulation-status"),
    ).toHaveTextContent("not_established");
    expect(
      screen.getByTestId(
        "overview-generic-cycle-simulation-profile-limitation",
      ),
    ).toHaveTextContent("generic_n4_child_profile_family_not_established");
    expect(
      screen.queryByTestId("overview-generic-cycle-profile-bindings"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("overview-generic-cycle-n5-owner-join"),
    ).toHaveTextContent("resolved");
    const n5Row = screen.getByTestId("overview-generic-cycle-n5-row");
    expect(n5Row).toHaveTextContent("value_pending_n8");
    expect(n5Row).toHaveTextContent("value_gate_pending_n8");
    expect(
      screen.getByTestId("overview-generic-cycle-n5-result-body-limited"),
    ).toHaveTextContent(
      "The numerical result is unavailable or did not pass verification.",
    );
    const attempts = screen.getByTestId("overview-candidate-attempt-history");
    expect(attempts).toHaveTextContent("first-local-failure");
    expect(attempts).toHaveTextContent("cycle 0: local n5 refusal");
    expect(attempts).toHaveTextContent("simulation_blocked");
    expect(panel).not.toHaveTextContent("publication_ready");
  });

  it("keeps normal, resource and abstention stops distinct in the visible cycle history", () => {
    const run = parsedRunWithGenericCycleSimulation("run-1", undefined, true);
    const projection = run.generic_cycle_simulation as Record<string, unknown>;
    const template = (
      projection.n6_cycle_history as Record<string, unknown>[]
    )[0]!;
    const stops = [
      ["frontier_stable", "stop", "stopped"],
      ["grounded_partial_admissible", "stop", "stopped"],
      ["budget_exhausted", "stop", "stopped"],
      ["grounded_abstention", "abstain", "abstained"],
    ];
    projection.n6_cycle_history = stops.map(
      ([terminal, decision, status], index) => ({
        ...template,
        cycle_index: index,
        terminal_kind: terminal,
        voi_next_action: "stop",
        refinement_decision: decision,
        search_iteration_status: status,
      }),
    );
    overviewState.run = run;

    renderWithProviders(<OverviewTab />);

    const rows = screen.getAllByTestId("overview-generic-cycle-history-row");
    expect(rows).toHaveLength(stops.length);
    for (const [index, [terminal, decision, status]] of stops.entries()) {
      expect(rows[index]).toHaveTextContent(terminal!);
      expect(rows[index]).toHaveTextContent(decision!);
      expect(rows[index]).toHaveTextContent(status!);
    }
    expect(rows[2]).not.toHaveTextContent("abstained");
    expect(rows[3]).toHaveTextContent("abstained");
  });

  it.each([
    ["refinement_decision", "abstain"],
    ["search_iteration_status", "abstained"],
  ])("withholds a stop with a corrupted sibling %s", (field, value) => {
    const run = parsedRunWithGenericCycleSimulation("run-1", undefined, true);
    const projection = run.generic_cycle_simulation as Record<string, unknown>;
    const row = (projection.n6_cycle_history as Record<string, unknown>[])[0]!;
    Object.assign(row, {
      terminal_kind: "frontier_stable",
      voi_next_action: "stop",
      refinement_decision: "stop",
      search_iteration_status: "stopped",
      [field!]: value,
    });
    overviewState.run = run;

    renderWithProviders(<OverviewTab />);

    expect(
      screen.getByTestId("overview-generic-cycle-simulation-refused"),
    ).toHaveTextContent("projection_version_binding_invalid");
    expect(
      screen.queryByTestId("overview-generic-cycle-history"),
    ).not.toBeInTheDocument();
  });

  it("withholds the current cycle history when its parsed run binding differs", () => {
    overviewState.run = parsedRunWithGenericCycleSimulation(
      "run-other",
      undefined,
      true,
    );

    renderWithProviders(<OverviewTab />);

    expect(
      screen.getByTestId("overview-generic-cycle-simulation-refused"),
    ).toHaveTextContent("run_id_mismatch");
    expect(
      screen.queryByTestId("overview-generic-cycle-history"),
    ).not.toBeInTheDocument();
  });

  it("shows retained candidate numbers without claiming the failed cycle completed", () => {
    overviewState.run = parsedRun(failedCandidateSimulationFixture());
    renderWithProviders(<OverviewTab />);
    const panel = screen.getByTestId("overview-candidate-simulation");
    expect(panel).toHaveTextContent("retained-tax-candidate");
    expect(panel).toHaveTextContent(
      "Publication authority is not established.",
    );
    expect(panel).toHaveTextContent(
      "The simulation completed before a later stage failed.",
    );
    expect(panel).toHaveTextContent(
      "The policy cycle is incomplete; these results do not establish success.",
    );
    expect(panel).toHaveTextContent("Later failure: Value assessment");
    expect(panel).toHaveTextContent("simulation_only_k_sim_not_world_evidence");
    expect(panel).toHaveTextContent("simulation_effect_basis_not_established");
    const body = screen.getByTestId("overview-candidate-n5-result-body");
    expect(body).toHaveTextContent("Persisted N5 result");
    expect(body).toHaveTextContent("Intervention atoms: tax-atom");
    expect(body).toHaveTextContent("government.balance");
    expect(body).toHaveTextContent("3.25");
    expect(body).toHaveTextContent("0.75");
    expect(screen.getByRole("link", { name: "Error details" })).toHaveAttribute(
      "href",
      "/runs/run-1/debug",
    );
    expect(
      screen.queryByTestId("overview-recursive-checkpoint"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/Completed child computations:/),
    ).not.toBeInTheDocument();
    expect(panel).not.toHaveTextContent("publication_ready");
  });

  it("withholds unresolved retained numbers and does not invent an absent failure stage", () => {
    overviewState.run = parsedRun({
      schema_version:
        "policyos.runtime.run_failed_candidate_simulation_projection.v1",
      run_id: "run-1",
      artifact_status: "not_established",
      limitation_code: "candidate_n5_output_not_established",
    });
    renderWithProviders(<OverviewTab />);
    const panel = screen.getByTestId("overview-candidate-simulation");
    expect(panel).toHaveTextContent("candidate_n5_output_not_established");
    expect(panel).toHaveTextContent("The policy cycle is incomplete");
    expect(panel).not.toHaveTextContent("Later failure:");
    expect(panel).not.toHaveTextContent(
      "The simulation completed before a later stage failed.",
    );
    expect(
      screen.queryByTestId("overview-candidate-n5-result-body"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("overview-recursive-checkpoint"),
    ).not.toBeInTheDocument();
  });

  it.each([true, false])(
    "offers a retained N4 calibration source only when its outer failed projection is resolved (%s)",
    (resolved) => {
      const fixture = failedCandidateSimulationFixture();
      if (!resolved) {
        fixture.artifact_status = "not_established";
        Reflect.set(
          fixture,
          "limitation_code",
          "candidate_n5_output_not_established",
        );
        const row = fixture.n5_observations[0]!;
        Reflect.deleteProperty(row, "result_body");
        row.result_body_status = "not_established";
        Reflect.set(
          row,
          "result_body_limitation_code",
          "candidate_n5_result_body_content_refused",
        );
      }
      overviewState.run = parsedRun(fixture);
      overviewState.canCreatePredictiveCalibration = true;
      overviewState.predictiveCalibrationQuery = {
        isPending: false,
        error: { status: 404, code: "run_predictive_calibration_not_found" },
        data: undefined,
      };
      renderWithProviders(<OverviewTab />);
      const choices = screen.getByTestId("predictive-candidate-source");
      const name =
        "runtime.quality.n4_candidate_scenario_source · " +
        fixture.n5_observations[0]!.n4_source_ref.artifact_id;
      expect(within(choices).queryAllByRole("option", { name })).toHaveLength(
        resolved ? 1 : 0,
      );
    },
  );

  it("renders parsed generic cycle children and the retained failed sibling as candidate-only history", () => {
    overviewState.run = parsedRunWithGenericCycleSimulation();

    renderWithProviders(<OverviewTab />);

    const panel = screen.getByTestId("overview-generic-cycle-simulation");
    expect(panel).toHaveTextContent("Generic cycle simulation");
    expect(panel).toHaveTextContent(
      "Persisted candidate lineage only. Currentness and publication authority are not established.",
    );
    expect(panel).toHaveTextContent("Artifact status: resolved");
    expect(panel).toHaveTextContent("Child-profile status: resolved");
    expect(panel).toHaveTextContent("Currentness: not_established");
    expect(screen.getAllByTestId("overview-generic-cycle-n5-row")).toHaveLength(
      2,
    );
    expect(
      screen.getByTestId("overview-generic-cycle-n5-observations"),
    ).toHaveTextContent("joint_simulated");
    expect(
      screen.getByTestId("overview-generic-cycle-n5-observations"),
    ).toHaveTextContent("simulation_pending_n5");
    expect(
      screen.getByTestId("overview-generic-cycle-profile-bindings"),
    ).toHaveTextContent("profile-a");
    expect(
      screen.getByTestId("overview-generic-cycle-profile-bindings"),
    ).toHaveTextContent("resolved");
    expect(
      screen.getByTestId("overview-generic-cycle-checkpoint"),
    ).toHaveTextContent("design-problem://" + "d".repeat(64) + ": completed");
    expect(
      screen.getByTestId("overview-generic-cycle-failed-branches"),
    ).toHaveTextContent(
      "Sibling retained after its independent attempt stopped.",
    );
    expect(
      screen.getByTestId("overview-generic-cycle-n5-result-body"),
    ).toHaveTextContent("Persisted N5 result");
    expect(
      screen.getByTestId("overview-generic-cycle-n5-result-body"),
    ).toHaveTextContent("outcome-a");
    expect(
      screen.getByTestId("overview-generic-cycle-n5-result-body"),
    ).toHaveTextContent("3.25");
    expect(
      screen.getByTestId("overview-generic-cycle-n5-result-body"),
    ).toHaveTextContent("Intervention atoms: atom-a");
    expect(
      screen.getByTestId("overview-generic-cycle-n5-result-body"),
    ).toHaveTextContent("Intervention atoms: atom-b");
    expect(panel).not.toHaveTextContent("publication_ready");
  });

  it.each(["v4", "v5"] as const)(
    "renders the parent joint candidate with %s numerical qualification",
    (n5Version) => {
      const projection = genericCycleSimulationProjection("run-1");
      const parentObservation = c41JointParentObservation();
      Reflect.set(
        parentObservation.n5_interaction_evidence!,
        "schema_version",
        "policyos.runtime.joint_simulation_horizon." + n5Version,
      );
      const v5 = {
        ...projection,
        schema_version:
          "policyos.runtime.run_generic_cycle_simulation_projection.v5",
        joint_parent_status: "resolved",
        joint_parent_observations: [parentObservation],
        n5_observations: projection.n5_observations.map((row, index) =>
          index === 0
            ? { ...row, n5_owner_join_status: "resolved" }
            : {
                ...row,
                n5_owner_join_status: "not_established",
                n5_owner_join_limitation_code:
                  "generic_n5_owner_ref_not_established",
              },
        ),
      };
      overviewState.run = runDetailsSchema.parse({
        meta: {
          request_id: "req-v5",
          generated_at: "2026-10-11T10:00:00Z",
          source_kinds: ["core_run"],
        },
        run: {
          run_id: "run-1",
          source_kind: "core_run",
          status: "completed",
          generic_cycle_simulation: v5,
        },
        temporal_scope: null,
      }).run;
      renderWithProviders(<OverviewTab />);
      const parent = screen.getByTestId("overview-generic-cycle-joint-parent");
      expect(parent).toHaveTextContent("Parent joint candidate assessment");
      expect(parent).toHaveTextContent("value_conditional");
      expect(parent).toHaveTextContent("low");
      expect(parent).toHaveTextContent(
        n5Version === "v4" ? "unsupported" : "non_additive",
      );
      expect(
        parentObservation.n5_interaction_evidence?.numeric_interaction,
      ).toBe("non_additive");
      expect(
        screen
          .queryAllByTestId("overview-v4-interaction-classification-limitation")
          .map((node) => node.textContent),
      ).toEqual(
        n5Version === "v4"
          ? [
              "The interaction classification in this historical result is unsupported.",
            ]
          : [],
      );
      expect(parent.textContent?.includes("non_additive")).toBe(
        n5Version === "v5",
      );
      expect(parent).toHaveTextContent(
        "Higher-order residual for outcome-a, step 0: 1",
      );
      expect(parent).toHaveTextContent("alternatives");
      expect(parent).toHaveTextContent(
        "n5_execution_request_provenance_not_established",
      );
      expect(
        screen.getAllByTestId("overview-generic-cycle-n5-row"),
      ).toHaveLength(2);
      expect(
        screen.getAllByTestId("overview-generic-cycle-n5-owner-join"),
      ).toHaveLength(2);
      expect(parent).not.toHaveTextContent("publication_ready");
    },
  );

  it("distinguishes original alternatives from materialized authored joint components", () => {
    overviewState.run = runWithJointParent(authoredJointParentObservation());

    renderWithProviders(<OverviewTab />);

    const parent = screen.getByTestId(
      "overview-generic-cycle-joint-parent-row",
    );
    const authored = screen.getByTestId("overview-authored-joint-components");
    expect(parent).toHaveTextContent("source candidates: alternatives");
    expect(authored).toHaveTextContent(
      "Selected relationship: joint_components; composition: authored_candidate",
    );
    expect(authored).toHaveTextContent("child refinement: not_established");
    expect(authored).toHaveTextContent("Original N4 source atoms:");
    expect(authored).toHaveTextContent(
      "Materialized N5 component atoms: atom_aaaaaaaaaaaaaaaa",
    );
    expect(authored).toHaveTextContent(
      "authored_candidate_coupling_not_established",
    );
    expect(
      within(authored).getByRole("link", {
        name: /Candidate composition relation:/,
      }),
    ).toHaveAttribute("href", expect.stringContaining("7".repeat(64)));
    expect(
      within(authored).getByRole("link", {
        name: /Original authorized composition request:/,
      }),
    ).toHaveAttribute("href", expect.stringContaining("8".repeat(64)));
    expect(parent).toHaveTextContent("value_conditional");
    expect(parent).not.toHaveTextContent("publication_ready");
  });

  it.each([
    "missing_relation",
    "wrong_derived_atom",
    "unbound_request",
    "claimed_coupling",
  ])("withholds authored joint projection with %s", (mutation) => {
    const parent = authoredJointParentObservation();
    if (mutation === "missing_relation")
      Reflect.set(parent, "n8_authored_joint_relation_ref", null);
    if (mutation === "wrong_derived_atom")
      parent.n8_candidate_derived_atom_ids[0] = "atom_eeeeeeeeeeeeeeee";
    if (mutation === "unbound_request")
      Reflect.set(
        parent.n8_authored_joint_request_payload_ref,
        "manifest_profile_sha256",
        null,
      );
    if (mutation === "claimed_coupling")
      parent.n8_joint_scope_status = "resolved";
    overviewState.run = runWithJointParent(parent);

    renderWithProviders(<OverviewTab />);

    expect(
      screen.getByTestId("overview-generic-cycle-simulation-refused"),
    ).toHaveTextContent("projection_version_binding_invalid");
    expect(
      screen.queryByTestId("overview-authored-joint-components"),
    ).not.toBeInTheDocument();
  });

  it("shows a withheld parent assessment without hiding child observations", () => {
    const projection = {
      ...genericCycleSimulationProjection("run-1"),
      schema_version:
        "policyos.runtime.run_generic_cycle_simulation_projection.v5",
      joint_parent_status: "not_established",
      joint_parent_limitation_code:
        "generic_joint_parent_result_not_established",
    };
    overviewState.run = runDetailsSchema.parse({
      meta: {
        request_id: "req-v5-missing",
        generated_at: "2026-10-11T10:00:00Z",
        source_kinds: ["core_run"],
      },
      run: {
        run_id: "run-1",
        source_kind: "core_run",
        status: "completed",
        generic_cycle_simulation: projection,
      },
      temporal_scope: null,
    }).run;
    renderWithProviders(<OverviewTab />);
    expect(
      screen.getByTestId("overview-generic-cycle-joint-parent-limitation"),
    ).toHaveTextContent("generic_joint_parent_result_not_established");
    expect(
      screen.queryByTestId("overview-generic-cycle-joint-parent-row"),
    ).not.toBeInTheDocument();
    expect(screen.getAllByTestId("overview-generic-cycle-n5-row")).toHaveLength(
      2,
    );
  });

  it("renders generic leaf outcomes separately from the pending frontier", () => {
    const terminalKinds = {
      "child-admissible": "grounded_admissible",
      "child-partial": "grounded_partial_admissible",
      "child-stable": "frontier_stable",
      "child-budget": "budget_exhausted",
      "child-abstained": "grounded_abstention",
    };
    overviewState.run = parsedRunWithGenericCycleSimulation(
      "run-1",
      terminalKinds,
    );

    renderWithProviders(<OverviewTab />);

    const checkpoint = screen.getByTestId("overview-generic-cycle-checkpoint");
    expect(checkpoint).toHaveTextContent(
      "Pending frontier: design-problem://" + "8".repeat(64),
    );
    expect(checkpoint).toHaveTextContent(
      "Completed child computations: " + Object.keys(terminalKinds).join(", "),
    );
    for (const [nodeRef, kind] of Object.entries(terminalKinds)) {
      expect(checkpoint).toHaveTextContent(nodeRef + ": " + kind);
    }
    expect(checkpoint).not.toHaveTextContent("Not established");
  });

  it.each([
    ["missing", null],
    ["empty", {}],
  ] as const)(
    "keeps %s generic leaf terminal outcomes not established",
    (_label, terminalKinds) => {
      overviewState.run = parsedRunWithGenericCycleSimulation(
        "run-1",
        terminalKinds,
      );

      renderWithProviders(<OverviewTab />);

      const unavailable = screen.getByTestId(
        "overview-generic-cycle-terminal-kinds-not-established",
      );
      expect(unavailable).toHaveTextContent("Not established");
      expect(unavailable).not.toHaveTextContent("grounded_abstention");
    },
  );

  it("withholds otherwise well-shaped children when the generic projection belongs to another run", () => {
    overviewState.run = parsedRunWithGenericCycleSimulation("run-other");

    renderWithProviders(<OverviewTab />);

    const panel = screen.getByTestId("overview-generic-cycle-simulation");
    expect(
      screen.getByTestId("overview-generic-cycle-simulation-refused"),
    ).toHaveTextContent("run_id_mismatch");
    expect(panel).not.toHaveTextContent("candidate-a");
    expect(panel).not.toHaveTextContent(
      "child_profile_currentness_not_established",
    );
  });

  it("renders governance severity only through the private issuer", () => {
    renderWithProviders(<OverviewTab />);

    expect(
      screen.getByTestId("overview-governance-severity-known"),
    ).toHaveAttribute("data-authority-recognition", "unrecognized");
    expect(
      screen.getByTestId("overview-governance-severity-known"),
    ).toHaveAttribute("data-presentation-tone", "neutral");
    expect(
      screen.getByTestId("overview-governance-severity-novel"),
    ).toHaveAttribute("data-authority-recognition", "unrecognized");
    expect(
      screen.getByTestId("overview-governance-severity-novel"),
    ).toHaveAttribute("data-presentation-tone", "neutral");
  });

  it("renders only resolved persisted N5 observations as candidate evidence", () => {
    overviewState.run.candidate_simulation = {
      schema_version: "policyos.runtime.run_candidate_simulation_projection.v1",
      run_id: "run-1",
      artifact_status: "resolved",
      authority_purpose: "candidate_observation_only",
      publication_authority: false,
      source_ref: {
        artifact_id: `sha256:${"b".repeat(64)}`,
        kind: "runtime.compiled_recursive_generation_cycle",
        media_type: "application/json",
      },
      source_content_hash: `sha256:${"c".repeat(64)}`,
      limitation_code: null,
      n5_observations: [
        {
          node_ref: "node-a",
          design_problem_ref: `sha256:${"d".repeat(64)}`,
          cycle_index: 0,
          candidate_id: "candidate-a",
          atom_ids: ["atom-a"],
          selected_outcomes: ["outcome-a"],
          status: "joint_simulated",
          simulation_ref: `sha256:${"e".repeat(64)}`,
          simulation_result_ref: {
            artifact_id: `sha256:${"f".repeat(64)}`,
            kind: "polisyos.runtime.joint_simulation_result",
            media_type: "application/json",
          },
          world_model_record_content_hash: `sha256:${"a".repeat(64)}`,
          k_world_ref_before: `sha256:${"a".repeat(64)}`,
          k_world_ref_after: `sha256:${"a".repeat(64)}`,
          authority_blockers: ["s8_blocked", "n9_not_admitted"],
        },
      ],
      recursive_cycle_checkpoint: null,
    };
    renderWithProviders(<OverviewTab />);
    expect(screen.getByText("joint_simulated")).toBeVisible();
    expect(screen.getByText("s8_blocked")).toBeVisible();
    expect(screen.getByText("outcome-a")).toBeVisible();
    expect(screen.getByTestId("overview-simulation-ref")).toHaveTextContent(
      `sha256:${"f".repeat(64)}`,
    );
    expect(
      screen.getByTestId("overview-candidate-simulation"),
    ).toHaveTextContent("Publication authority is not established.");
  });

  it("keeps a blocked reentry attempt visible without inventing numerical success", () => {
    const projection = sameCandidateAcquisitionHistoryProjection();
    Object.assign(projection.acquisition_history[0]!.continuation, {
      selected_simulation_status: "simulation_blocked",
      selected_simulation_authority_blockers: [
        "current_compute_budget_unavailable",
      ],
    });
    overviewState.run = parsedRun(projection);
    renderWithProviders(<OverviewTab />);
    const simulation = screen.getByTestId(
      "overview-acquisition-selected-simulation",
    );
    expect(simulation).toHaveTextContent("simulation_blocked");
    expect(simulation).toHaveTextContent("current_compute_budget_unavailable");
    expect(
      screen.queryByTestId("overview-acquisition-selected-n5-result-body"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("overview-acquisition-numerical-provenance"),
    ).not.toBeInTheDocument();
  });

  it("shows the admitted source and original retained evaluation separately", () => {
    const projection = sameCandidateAcquisitionHistoryProjection();
    overviewState.run.candidate_simulation = {
      ...projection,
      acquisition_history: [retainedAcquisitionHistoryFixture()],
    };
    renderWithProviders(<OverviewTab />);
    const history = screen.getByTestId("overview-acquisition-history-retained");
    expect(history).toHaveTextContent(
      "Newly admitted source: sha256:" + "3".repeat(64),
    );
    expect(history).toHaveTextContent(
      "Prior evaluation source: sha256:" + "9".repeat(64),
    );
    expect(history).toHaveTextContent(
      "Original evaluation: run run-original, job job-original, cycle 1",
    );
    expect(history).toHaveTextContent("Retained candidate: candidate-prior");
    expect(
      screen.getByTestId("overview-acquisition-source-reaction-link"),
    ).toHaveTextContent(
      "Source reaction at that decision: sha256:" + "0".repeat(64),
    );
    expect(history).toHaveTextContent("Currentness: not_established");
    expect(history).not.toHaveTextContent("Re-entry candidate:");
  });

  it("shows the latest worsening occurrence with its own selected numbers and declared units", () => {
    overviewState.run = parsedRun(selectedNumericalAcquisitionProjection());

    renderWithProviders(<OverviewTab />);

    const occurrence = screen.getByTestId(
      "overview-acquisition-current-occurrence",
    );
    expect(occurrence).toHaveTextContent("candidate-same; cycle 2");
    expect(occurrence).toHaveTextContent("occurrence sha256:" + "f".repeat(64));
    expect(occurrence).toHaveTextContent("front quarantine");
    expect(
      screen.getByTestId("overview-acquisition-numerical-provenance"),
    ).toHaveTextContent("new_execution; original evaluation cycle 2");
    const result = screen.getByTestId(
      "overview-acquisition-selected-n5-result-body",
    );
    expect(result).toHaveTextContent("3.25");
    expect(result).toHaveTextContent("0.75");
    expect(result).toHaveTextContent(
      "government.balance = declared_currency_unit (declared_candidate_model)",
    );
    expect(result).toHaveTextContent("Horizon: 0–1, step 1");
    expect(result).not.toHaveTextContent("publication_ready");
  });

  it("shows retained original numbers without attributing them to the new admitted source", () => {
    const projection = selectedNumericalAcquisitionProjection();
    const numerical =
      projection.acquisition_history[0]!.selected_n5_observation;
    const retained = retainedAcquisitionHistoryFixture();
    const selected = retained.retained_evaluation;
    const history = {
      ...retained,
      retained_evaluation: {
        ...selected,
        candidate_id: numerical.candidate_id,
        cycle_index: numerical.cycle_index,
        n4_source_ref: numerical.n4_source_ref,
        context_job_ref: numerical.context_job_ref,
        n5_input_ref: numerical.n5_input_ref,
        n5_execution_ref: numerical.n5_execution_ref,
        n5_result_ref: numerical.simulation_result_ref,
      },
      selected_n5_observation: numerical,
      current_cheap_consequences: currentCheapConsequencesFixture({
        ...selected,
        candidate_id: numerical.candidate_id,
        cycle_index: numerical.cycle_index,
      }),
    };
    overviewState.run = parsedRun({
      ...projection,
      acquisition_history: [history],
    });

    renderWithProviders(<OverviewTab />);

    expect(
      screen.getByTestId("overview-acquisition-numerical-provenance"),
    ).toHaveTextContent("retained_prior; original evaluation cycle 2");
    expect(
      screen.getByTestId("overview-acquisition-retained-n5-result-body"),
    ).toHaveTextContent("0.75");
    expect(
      screen.queryByTestId("overview-acquisition-selected-n5-result-body"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("overview-acquisition-history-retained"),
    ).toHaveTextContent("The prior evaluation keeps its original inputs.");
    const cheap = screen.getByTestId(
      "overview-acquisition-current-cheap-consequences",
    );
    expect(cheap).toHaveTextContent("value_blocked");
    expect(cheap).toHaveTextContent("current_source_invalidation");
    expect(cheap).toHaveTextContent("Next action: blocked");
    expect(cheap).toHaveTextContent("the numerical evaluation is retained");
  });

  it("withholds retained history when cheap consequences name another candidate", () => {
    const retained = retainedAcquisitionHistoryFixture();
    const cheap = currentCheapConsequencesFixture(retained.retained_evaluation);
    cheap.candidate_id = "foreign-candidate";
    overviewState.run.candidate_simulation = {
      ...sameCandidateAcquisitionHistoryProjection(),
      acquisition_history: [{ ...retained, current_cheap_consequences: cheap }],
    };
    renderWithProviders(<OverviewTab />);
    expect(
      screen.getByTestId("overview-acquisition-history-refused"),
    ).toBeVisible();
    expect(
      screen.queryByTestId("overview-acquisition-current-cheap-consequences"),
    ).not.toBeInTheDocument();
  });

  it("shows a bound same-target candidate model change without claiming independent evidence", () => {
    overviewState.run = parsedRun(modelRevisedAcquisitionProjection());

    renderWithProviders(<OverviewTab />);

    const revision = screen.getByTestId("overview-acquisition-model-revision");
    expect(revision).toHaveTextContent("outcome_per_target_unit");
    expect(revision).toHaveTextContent(
      "not an independent empirical replication",
    );
    expect(revision).toHaveTextContent(
      "Model-change decision: sha256:" + "1".repeat(64),
    );
    expect(
      screen.getByTestId("overview-acquisition-selected-n5-result-body"),
    ).toHaveTextContent("0.75");
  });

  it.each(["missing_revision", "wrong_input", "wrong_model", "self_asserted"])(
    "withholds equal-target numeric history with %s evidence",
    (mutation) => {
      const projection = modelRevisedAcquisitionProjection();
      const row = projection.acquisition_history[0]!;
      const revision = row.continuation.model_revision;
      if (mutation === "missing_revision")
        Reflect.set(row.continuation, "model_revision", null);
      if (mutation === "wrong_input")
        revision.selected_input_ref = revision.previous_input_ref;
      if (mutation === "wrong_model")
        revision.selected_declaration_ref = revision.previous_declaration_ref;
      if (mutation === "self_asserted")
        revision.predicate_provenance = "consumer_asserted";
      overviewState.run.candidate_simulation = projection;

      renderWithProviders(<OverviewTab />);

      expect(
        screen.getByTestId("overview-acquisition-history-refused"),
      ).toBeVisible();
      expect(
        screen.queryByTestId("overview-acquisition-selected-n5-result-body"),
      ).not.toBeInTheDocument();
    },
  );

  it.each(["candidate_id", "cycle_index", "n5_input_ref"])(
    "withholds selected numerical history when its %s is substituted",
    (field) => {
      const projection = selectedNumericalAcquisitionProjection();
      const row = projection.acquisition_history[0]!;
      Reflect.set(
        row.selected_n5_observation,
        field,
        field === "candidate_id"
          ? "foreign-candidate"
          : field === "cycle_index"
            ? 99
            : row.continuation.previous_n5_input_ref,
      );
      overviewState.run.candidate_simulation = projection;

      renderWithProviders(<OverviewTab />);

      expect(
        screen.getByTestId("overview-acquisition-history-refused"),
      ).toBeVisible();
      expect(
        screen.queryByTestId("overview-acquisition-selected-n5-result-body"),
      ).not.toBeInTheDocument();
    },
  );

  it("withholds a v3 row whose retained evaluation tuple was removed", () => {
    const projection = sameCandidateAcquisitionHistoryProjection();
    overviewState.run.candidate_simulation = {
      ...projection,
      acquisition_history: [
        { ...retainedAcquisitionHistoryFixture(), retained_evaluation: null },
      ],
    };
    renderWithProviders(<OverviewTab />);
    expect(
      screen.queryByTestId("overview-acquisition-history-retained"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTestId("overview-acquisition-history-refused"),
    ).toBeVisible();
  });

  it("renders same-candidate history only with a joined source and root origin", () => {
    overviewState.run.candidate_simulation =
      sameCandidateAcquisitionHistoryProjection();
    renderWithProviders(<OverviewTab />);
    const history = screen.getByTestId("overview-acquisition-history");
    expect(history).toHaveTextContent("Prior candidate: candidate-same");
    expect(history).toHaveTextContent("Re-entry candidate: candidate-same");
    expect(history).toHaveTextContent("Currentness: not_established");
    expect(history).toHaveTextContent("sha256:" + "a".repeat(64));
    expect(history).toHaveTextContent("sha256:" + "c".repeat(64));
    expect(history).toHaveTextContent(
      "Currentness and publication authority are not established.",
    );
  });

  it("labels metadata-missing legacy history as limited and keeps its origin observational", () => {
    const projection = sameCandidateAcquisitionHistoryProjection();
    const row = projection.acquisition_history[0]! as unknown as Record<
      string,
      unknown
    >;
    delete row.expected_origin_source_ref;
    delete row.schema_version;
    delete row.reentry_receipt_schema_version;
    delete row.continuation_join_status;
    delete row.origin_source_binding_status;
    overviewState.run.candidate_simulation = projection;
    renderWithProviders(<OverviewTab />);
    const history = screen.getByTestId("overview-acquisition-history");
    expect(history).toHaveTextContent("Lineage metadata is missing or legacy");
    expect(history).toHaveTextContent("Observed origin source");
    expect(history).not.toHaveTextContent("Verified root origin");
  });

  it("keeps a quarantined source ref forensic without claiming a verified root", () => {
    const projection = sameCandidateAcquisitionHistoryProjection();
    const row = projection.acquisition_history[0]! as unknown as Record<
      string,
      unknown
    >;
    row.terminal_outcome = "quarantined_no_growth";
    delete row.reentry_receipt_ref;
    delete row.old_candidate_id;
    delete row.new_candidate_id;
    delete row.new_candidate_source_ref;
    delete row.expected_origin_source_ref;
    delete row.continuation;
    row.reentry_receipt_schema_version = null;
    row.continuation_join_status = "not_applicable";
    row.origin_source_binding_status = "observed_only";
    overviewState.run.candidate_simulation = projection;
    renderWithProviders(<OverviewTab />);
    const history = screen.getByTestId("overview-acquisition-history");
    expect(history).toHaveTextContent("Observed origin source");
    expect(history).toHaveTextContent("sha256:" + "c".repeat(64));
    expect(history).not.toHaveTextContent("Verified root origin");
  });

  it("marks metadata-free quarantine history as limited", () => {
    const projection = sameCandidateAcquisitionHistoryProjection();
    const row = projection.acquisition_history[0]! as unknown as Record<
      string,
      unknown
    >;
    row.terminal_outcome = "quarantined_no_growth";
    delete row.reentry_receipt_ref;
    delete row.old_candidate_id;
    delete row.new_candidate_id;
    delete row.new_candidate_source_ref;
    delete row.expected_origin_source_ref;
    delete row.continuation;
    delete row.schema_version;
    delete row.reentry_receipt_schema_version;
    delete row.continuation_join_status;
    delete row.origin_source_binding_status;
    overviewState.run.candidate_simulation = projection;
    renderWithProviders(<OverviewTab />);
    const history = screen.getByTestId("overview-acquisition-history");
    expect(history).toHaveTextContent("Lineage metadata is missing or legacy");
    expect(history).toHaveTextContent("Observed origin source");
    expect(history).not.toHaveTextContent("Verified root origin");
  });

  it("refuses same-candidate UI history when the origin profile differs", () => {
    const projection = sameCandidateAcquisitionHistoryProjection();
    projection.acquisition_history[0]!.origin_source_ref.manifest_profile_sha256 =
      "sha256:" + "e".repeat(64);
    overviewState.run.candidate_simulation = projection;
    renderWithProviders(<OverviewTab />);
    expect(
      screen.getByTestId("overview-acquisition-history-refused"),
    ).toBeVisible();
    expect(
      screen.queryByText("Prior candidate: candidate-same"),
    ).not.toBeInTheDocument();
  });

  it("rejects malformed acquisition lineage before dashboard candidate rendering", () => {
    const malformed = {
      schema_version: "policyos.runtime.run_candidate_simulation_projection.v1",
      run_id: "run-1",
      artifact_status: "resolved",
      authority_purpose: "candidate_observation_only",
      publication_authority: false,
      source_ref: null,
      source_content_hash: `sha256:${"c".repeat(64)}`,
      limitation_code: "n5_observation_not_emitted",
      n5_observations: [],
      acquisition_history: [
        {
          route_receipt_ref: {
            artifact_id: `sha256:${"d".repeat(64)}`,
            kind: "runtime_quality.acquisition_route_loop_receipt",
            media_type: "application/json",
          },
          route_id: `sha256:${"f".repeat(64)}`,
          action_generation: 1,
          terminal_outcome: "quarantined_no_growth",
          currentness_status: "not_established",
          authority_purpose: "publishable",
          publication_authority: true,
        },
      ],
    };
    expect(
      runDetailsSchema.safeParse({
        meta: {
          request_id: "req-overview",
          generated_at: "2026-10-12T10:00:00Z",
          source_kinds: ["core_run"],
        },
        run: {
          run_id: "run-1",
          source_kind: "core_run",
          status: "failed",
          candidate_simulation: malformed,
        },
        temporal_scope: null,
      }).success,
    ).toBe(false);

    overviewState.run = parsedRun();
    renderWithProviders(<OverviewTab />);
    expect(screen.queryByTestId("overview-candidate-simulation")).toBeNull();
  });

  it("keeps the V2 budget frontier distinct from a root outcome", () => {
    overviewState.run.candidate_simulation = {
      schema_version: "policyos.runtime.run_candidate_simulation_projection.v1",
      run_id: "run-1",
      artifact_status: "resolved",
      authority_purpose: "candidate_observation_only",
      publication_authority: false,
      source_ref: null,
      source_content_hash: `sha256:${"c".repeat(64)}`,
      limitation_code: "n5_observation_not_emitted",
      n5_observations: [],
      recursive_cycle_checkpoint: {
        schema_version: "policyos.runtime.recursive_cycle_checkpoint.v1",
        status: "partial",
        publication_authority: false,
        budget_stop_node_ref: "child-budget",
        pending_frontier: ["child-pending"],
        completed_design_refs: [
          "child-computed",
          "child-partial",
          "child-stable",
          "child-budget",
        ],
        root_n9_status: "not_run",
        leaf_terminal_kinds: {
          "child-computed": "grounded_abstention",
          "child-partial": "grounded_partial_admissible",
          "child-stable": "frontier_stable",
          "child-budget": "budget_exhausted",
        },
        failed_branches: [],
      },
    };
    renderWithProviders(<OverviewTab />);
    const panel = screen.getByTestId("overview-recursive-checkpoint");
    expect(panel).toHaveTextContent("Root outcome remains pending.");
    expect(panel).toHaveTextContent("child-pending");
    expect(panel).toHaveTextContent("child-budget: budget_exhausted");
    expect(panel).toHaveTextContent("child-computed: grounded_abstention");
    expect(panel).toHaveTextContent(
      "child-partial: grounded_partial_admissible",
    );
    expect(panel).toHaveTextContent("child-stable: frontier_stable");
    expect(panel).toHaveTextContent("Root N9: not_run");
  });

  it("renders the exact independent sibling failure as a limited checkpoint", () => {
    overviewState.run.candidate_simulation = {
      schema_version: "policyos.runtime.run_candidate_simulation_projection.v1",
      run_id: "run-1",
      artifact_status: "resolved",
      authority_purpose: "candidate_observation_only",
      publication_authority: false,
      source_ref: null,
      source_content_hash: `sha256:${"c".repeat(64)}`,
      limitation_code: "n5_result_reference_not_established",
      n5_observations: [],
      recursive_cycle_checkpoint: {
        schema_version: "policyos.runtime.recursive_cycle_checkpoint.v2",
        status: "partial",
        publication_authority: false,
        budget_stop_node_ref: null,
        pending_frontier: ["sibling-b"],
        completed_design_refs: ["sibling-a"],
        root_n9_status: "not_run",
        leaf_terminal_kinds: { "sibling-a": "grounded_abstention" },
        failed_branches: [
          {
            failed_branch_ref: "sibling-c",
            origin_node_ref: "sibling-c-leaf",
            stage: "leaf_generation",
            exception_type: "GenerationCycleError",
            error_code: "n4_source_resolution_failed",
            error_message: "Exact producer source could not be resolved.",
          },
        ],
      },
    };
    renderWithProviders(<OverviewTab />);
    const failure = screen.getByTestId("overview-recursive-failure");
    expect(failure).toHaveTextContent("sibling-c");
    expect(failure).toHaveTextContent("sibling-c-leaf");
    expect(failure).toHaveTextContent("n4_source_resolution_failed");
    expect(failure).toHaveTextContent(
      "Exact producer source could not be resolved.",
    );
  });

  it("rejects malformed N5 rows at the run API boundary before dashboard consumers", () => {
    const malformed = {
      schema_version: "policyos.runtime.run_candidate_simulation_projection.v1",
      run_id: "run-1",
      artifact_status: "resolved",
      authority_purpose: "candidate_observation_only",
      publication_authority: false,
      source_ref: null,
      source_content_hash: `sha256:${"c".repeat(64)}`,
      limitation_code: null,
      n5_observations: [null, { node_ref: "bad", status: "joint_simulated" }],
      recursive_cycle_checkpoint: null,
    };
    expect(
      runDetailsSchema.safeParse({
        meta: {
          request_id: "req-overview",
          generated_at: "2026-10-12T10:00:00Z",
          source_kinds: ["core_run"],
        },
        run: {
          run_id: "run-1",
          source_kind: "core_run",
          status: "failed",
          candidate_simulation: malformed,
        },
        temporal_scope: null,
      }).success,
    ).toBe(false);

    overviewState.run = parsedRun();
    renderWithProviders(<OverviewTab />);
    expect(screen.queryByTestId("overview-candidate-simulation")).toBeNull();
  });
});

describe("recorded candidate local refusal surface", () => {
  it("shows the earlier candidate refusal and useful N5 ref without claiming verification", () => {
    const projection = sameCandidateAcquisitionHistoryProjection();
    Reflect.set(projection, "candidate_evaluation_attempts", [
      {
        node_ref: "design-problem://attempt",
        candidate_id: "earlier-local-refusal",
        candidate_content_hash: "sha256:" + "a".repeat(64),
        cycle_index: 2,
        problem_ref: "sha256:" + "b".repeat(64),
        attempt_ref: "sha256:" + "c".repeat(64),
        failure_stage: "n8",
        simulation_status: "joint_simulated",
        simulation_authority_blockers: [
          "simulation_only_k_sim_not_world_evidence",
        ],
        value_status: "value_blocked",
        value_decision_grade: "blocked",
        value_authority_blockers: ["candidate_value_unavailable"],
        simulation_result_ref: {
          artifact_id: "sha256:" + "d".repeat(64),
          kind: "polisyos.runtime.joint_simulation_result",
          media_type: "application/json",
        },
      },
    ]);
    overviewState.run = parsedRun(projection);
    renderWithProviders(<OverviewTab />);
    const history = screen.getByTestId("overview-candidate-attempt-history");
    expect(history).toHaveTextContent("earlier-local-refusal");
    expect(history).toHaveTextContent("cycle 2: local n8 refusal");
    expect(history).toHaveTextContent("joint_simulated");
    expect(history).toHaveTextContent("value_blocked");
    expect(history).toHaveTextContent("candidate_value_unavailable");
    expect(history).toHaveTextContent("not execution reservations");
    expect(history).toHaveTextContent("not independently verified");
    expect(
      screen.getByRole("link", {
        name:
          "polisyos.runtime.joint_simulation_result: sha256:" + "d".repeat(64),
      }),
    ).toHaveAttribute("href", expect.stringContaining("d".repeat(64)));
    expect(
      screen.queryByTestId("overview-candidate-attempt-history-limited"),
    ).not.toBeInTheDocument();
  });

  it("shows a missing canonical attempt-context history as a limitation", () => {
    const projection = sameCandidateAcquisitionHistoryProjection();
    Reflect.set(
      projection,
      "candidate_evaluation_attempts_limitation_code",
      "candidate_attempt_context_history_not_established",
    );
    overviewState.run = parsedRun(projection);
    renderWithProviders(<OverviewTab />);
    expect(
      screen.getByTestId("overview-candidate-attempt-history-limited"),
    ).toHaveTextContent("candidate_attempt_context_history_not_established");
    expect(
      screen.queryByTestId("overview-candidate-attempt"),
    ).not.toBeInTheDocument();
  });
});

function candidateCurrentBasisUiFixture() {
  const limitation = "candidate_source_basis_prior_occurrence_not_revalidated";
  return {
    status: "resolved",
    generation_run_content_hash: "sha256:" + "c".repeat(64),
    basis_cycle_index: 2,
    basis_transition_content_hash: "sha256:" + "b".repeat(64),
    occurrences: [
      {
        candidate_id: "old-accepted-candidate",
        cycle_index: 1,
        content_hash: "sha256:" + "a".repeat(64),
        source_content_hash: null,
        front: "research",
        certified_by_n9: false,
        candidate_basis_cycle_index: 2,
        candidate_basis_content_hash: "sha256:" + "b".repeat(64),
        candidate_basis_status: "prior_basis_not_revalidated",
        candidate_basis_limitation_code: limitation,
        historical_front: "decision",
        historical_certified_by_n9: true,
        historical_value_status: "value_ready",
        historical_value_decision_grade: "high",
        historical_value_ref: "value://old-accepted",
        historical_value_blockers: [],
        value_status: "value_pending_n8",
        value_blockers: [limitation],
      },
    ],
    fronts: {
      decision_candidate_ids: [],
      research_candidate_ids: ["old-accepted-candidate"],
      quarantine_candidate_ids: [],
      portfolio_candidate_ids: [],
    },
  };
}

describe("current candidate basis surface", () => {
  it("keeps old N9/value acceptance historical and shows the pending value on the selected basis", () => {
    const projection = sameCandidateAcquisitionHistoryProjection();
    Reflect.set(
      projection,
      "candidate_source_current_projection",
      candidateCurrentBasisUiFixture(),
    );
    overviewState.run = parsedRun(projection);
    renderWithProviders(<OverviewTab />);
    const view = screen.getByTestId("overview-candidate-source-current");
    expect(view).toHaveTextContent("old-accepted-candidate");
    expect(view).toHaveTextContent(
      "Deployment currentness and publication authority are not established",
    );
    expect(
      within(view).getByTestId("overview-candidate-basis-historical"),
    ).toHaveTextContent("front decision; N9 true; value value_ready");
    const effective = within(view).getByTestId(
      "overview-candidate-basis-effective",
    );
    expect(effective).toHaveTextContent("value_pending_n8");
    expect(effective).toHaveTextContent("N9 false");
    expect(effective).not.toHaveTextContent("value://old-accepted");
    expect(view).toHaveTextContent(
      "candidate_source_basis_prior_occurrence_not_revalidated",
    );
    expect(view).toHaveTextContent("c".repeat(64));
  });

  it("withholds a raw current view after its required basis metadata is stripped", () => {
    const projection = sameCandidateAcquisitionHistoryProjection();
    Reflect.set(
      projection,
      "candidate_source_current_projection",
      candidateCurrentBasisUiFixture(),
    );
    const run = parsedRun(projection);
    const rawProjection = run.candidate_simulation as Record<string, unknown>;
    const rawView = rawProjection.candidate_source_current_projection as Record<
      string,
      unknown
    >;
    rawView.occurrences = [
      {
        candidate_id: "borrowed",
        cycle_index: 1,
        content_hash: "sha256:" + "a".repeat(64),
        source_content_hash: null,
        front: "decision",
        certified_by_n9: true,
      },
    ];
    overviewState.run = run;
    renderWithProviders(<OverviewTab />);
    const view = screen.getByTestId("overview-candidate-source-current");
    expect(view).toHaveTextContent(
      "candidate_source_current_projection_contract_invalid",
    );
    expect(
      within(view).queryByTestId("overview-acquisition-current-occurrence"),
    ).not.toBeInTheDocument();
  });

  it("shows an owner snapshot mismatch as unavailable without reusing old current rows", () => {
    const projection = sameCandidateAcquisitionHistoryProjection();
    Reflect.set(projection, "candidate_source_current_projection", {
      status: "not_established",
      issues: ["candidate_source_current_between_read_snapshot_mismatch"],
    });
    overviewState.run = parsedRun(projection);
    renderWithProviders(<OverviewTab />);
    const view = screen.getByTestId("overview-candidate-source-current");
    expect(view).toHaveTextContent(
      "candidate_source_current_between_read_snapshot_mismatch",
    );
    expect(
      within(view).queryByTestId("overview-acquisition-current-occurrence"),
    ).not.toBeInTheDocument();
  });
});

describe("candidate acquisition history surface", () => {
  it("renders candidate lineage with its blocked N5 and without observed admission", () => {
    const ref = (kind: string, digit: string) => ({
      artifact_id: "sha256:" + digit.repeat(64),
      kind,
      media_type: "application/json",
      manifest_profile_sha256: "sha256:" + "f".repeat(64),
    });
    const projection = sameCandidateAcquisitionHistoryProjection();
    Reflect.set(projection, "acquisition_history", [
      {
        schema_version:
          "policyos.runtime.run_candidate_simulation_acquisition_history.v4",
        route_receipt_ref: ref(
          "runtime_quality.acquisition_route_loop_receipt",
          "1",
        ),
        reentry_receipt_ref: ref(
          "runtime_quality.candidate_source_reentry_receipt",
          "2",
        ),
        route_id: "sha256:" + "3".repeat(64),
        action_generation: 1,
        terminal_outcome: "candidate_reentry_completed",
        candidate_action_ref: ref(
          "runtime_quality.acquisition_candidate_action_receipt",
          "4",
        ),
        candidate_source_ref: ref(
          "runtime.quality.candidate_acquisition_source",
          "5",
        ),
        data_snapshot_ref: ref("fabric.data_snapshot", "6"),
        world_model_ref: ref("runtime.quality.world_model_record", "7"),
        context_job_ref: ref(
          "runtime.quality.cycle_substrate_context_job",
          "8",
        ),
        model_declaration_ref: ref(
          "runtime.quality.candidate_simulation_model_declaration",
          "9",
        ),
        ncm_ref: ref("ir.ncm_spec", "a"),
        n4_source_ref: null,
        n5_input_ref: null,
        n5_execution_ref: null,
        n5_result_ref: null,
        simulation_status: "simulation_blocked",
        simulation_authority_blockers: ["n5_blocked"],
        source_cycle_index: 0,
        continued_cycle_index: 1,
        source_generation_run_content_hash: "sha256:" + "b".repeat(64),
        continued_generation_run_content_hash: "sha256:" + "c".repeat(64),
        basis_transition_content_hash: "sha256:" + "d".repeat(64),
        limitations: ["candidate_only"],
        observed_admission: false,
        currentness_status: "not_established",
        authority_purpose: "candidate_observation_only",
        publication_authority: false,
      },
    ]);
    overviewState.run = parsedRun(projection);
    renderWithProviders(<OverviewTab />);
    const row = screen.getByTestId("overview-acquisition-history-candidate");
    expect(row).toHaveTextContent("simulation_blocked");
    expect(row).toHaveTextContent(
      "no observed admission or publication authority",
    );
    expect(row).toHaveTextContent(
      "runtime.quality.candidate_acquisition_source",
    );
    expect(row).toHaveTextContent("n5_blocked");
  });
});

describe("verified recursive capacity checkpoint", () => {
  it("shows pending capacity stop without claiming physical need or root N9", () => {
    const run = parsedRunWithGenericCycleSimulation();
    const projection = run.generic_cycle_simulation as Record<string, unknown>;
    projection.recursive_cycle_checkpoint = {
      schema_version: "policyos.runtime.recursive_cycle_checkpoint.v3",
      status: "partial",
      publication_authority: false,
      budget_stop_node_ref: null,
      pending_frontier: ["pending-child"],
      completed_design_refs: ["completed-child"],
      root_n9_status: "not_run",
      leaf_terminal_kinds: {},
      failed_branches: [],
      capacity_stop_parent_node_ref: "root",
      capacity_pending_child_node_ref: "pending-child",
      capacity_pending_child_index: 1,
      capacity_source_content_hash: "sha256:" + "a".repeat(64),
      capacity_limitation_code: "physical_need_not_established",
    };
    overviewState.run = run;
    renderWithProviders(<OverviewTab />);
    const view = screen.getByTestId("overview-generic-cycle-checkpoint");
    expect(view).toHaveTextContent("pending-child");
    expect(view).toHaveTextContent("physical_need_not_established");
    expect(view).toHaveTextContent("not_run");
    expect(view).toHaveTextContent(
      "physical need for the pending child is not established",
    );
  });
});

describe("candidate frontier history", () => {
  beforeEach(() => {
    overviewState.governanceDebugMock.mockReturnValue({
      data: { debug: { issues: [] } },
    });
    overviewState.evidenceContextMock.mockReturnValue({
      data: { context: {} },
    });
    overviewState.timelineMock.mockReturnValue({
      data: { timeline: { events: [] } },
    });
    overviewState.predictiveCalibrationQuery = {
      isPending: true,
      error: undefined,
      data: undefined,
    };
    overviewState.artifactContentMock.mockReturnValue({
      data: { artifact: null },
    });
  });

  it("renders a friendly message when terminal candidate history is unavailable", () => {
    const projection = sameCandidateAcquisitionHistoryProjection();
    Reflect.set(projection, "acquisition_history", []);
    Reflect.set(
      projection,
      "acquisition_history_limitation_code",
      "acquisition_action_history_terminal_projection_unavailable",
    );
    overviewState.run = parsedRun(projection);

    renderWithProviders(<OverviewTab />);

    const limitation = screen.getByTestId(
      "overview-acquisition-history-limitation",
    );
    expect(limitation).toHaveTextContent(
      "Some candidate acquisition history is unavailable in this view.",
    );
    expect(limitation).not.toHaveTextContent(
      "acquisition_action_history_terminal_projection_unavailable",
    );
  });

  it("keeps verified earlier rows visible with the partial-history message", () => {
    const projection = sameCandidateAcquisitionHistoryProjection();
    Reflect.set(projection, "acquisition_history", [
      retainedAcquisitionHistoryFixture(),
    ]);
    Reflect.set(
      projection,
      "acquisition_history_limitation_code",
      "acquisition_action_history_terminal_projection_unavailable",
    );
    overviewState.run = parsedRun(projection);

    renderWithProviders(<OverviewTab />);

    expect(
      screen.getByTestId("overview-acquisition-history-retained"),
    ).toBeInTheDocument();
    const limitation = screen.getByTestId(
      "overview-acquisition-history-limitation",
    );
    expect(limitation).toHaveTextContent(
      "Some candidate acquisition history is unavailable in this view.",
    );
    expect(limitation).not.toHaveTextContent(
      "acquisition_action_history_terminal_projection_unavailable",
    );
  });

  it("renders a blocked latest candidate without a borrowed numeric result", () => {
    const ref = (kind: string) => ({
      artifact_id: "sha256:" + "1".repeat(64),
      kind,
      media_type: "application/json",
      manifest_profile_sha256: "sha256:" + "f".repeat(64),
    });
    const route = ref("runtime_quality.acquisition_route_loop_receipt");
    const action = ref("runtime_quality.acquisition_candidate_action_receipt");
    const source = ref("runtime.quality.candidate_acquisition_source");
    const failure = ref("runtime_quality.candidate_source_reentry_receipt");
    const reentry = {
      schema_version:
        "policyos.runtime.run_candidate_simulation_acquisition_history.v4",
      route_receipt_ref: route,
      reentry_receipt_ref: failure,
      route_id: "sha256:" + "2".repeat(64),
      action_generation: 2,
      terminal_outcome: "candidate_reentry_completed",
      candidate_action_ref: action,
      candidate_source_ref: source,
      data_snapshot_ref: ref("fabric.data_snapshot"),
      world_model_ref: ref("runtime.quality.world_model_record"),
      context_job_ref: ref("runtime.quality.cycle_substrate_context_job"),
      model_declaration_ref: ref(
        "runtime.quality.candidate_simulation_model_declaration",
      ),
      ncm_ref: ref("ir.ncm_spec"),
      n4_source_ref: null,
      n5_input_ref: null,
      n5_execution_ref: null,
      n5_result_ref: null,
      simulation_status: "simulation_blocked",
      simulation_authority_blockers: ["n5_blocked"],
      source_cycle_index: 0,
      continued_cycle_index: 1,
      source_generation_run_content_hash: "sha256:" + "3".repeat(64),
      continued_generation_run_content_hash: "sha256:" + "4".repeat(64),
      basis_transition_content_hash: "sha256:" + "5".repeat(64),
      limitations: ["candidate_only"],
      observed_admission: false,
      currentness_status: "not_established",
      authority_purpose: "candidate_observation_only",
      publication_authority: false,
    };
    const candidate = {
      schema_version:
        "policyos.runtime.run_candidate_simulation_acquisition_history.v5",
      route_receipt_ref: route,
      route_id: reentry.route_id,
      action_generation: 2,
      terminal_outcome: "candidate_reentry_completed",
      candidate_action_ref: action,
      candidate_source_ref: source,
      evaluation_decision_ref: ref(
        "runtime_quality.acquisition_evaluation_decision",
      ),
      current_basis_ref: ref("runtime_quality.acquisition_evaluation_basis"),
      selected_basis_ref: ref("runtime_quality.acquisition_evaluation_basis"),
      selected_evaluation_witness_ref: failure,
      comparison_result: "not_established",
      predicate_provenance: "not_established",
      comparison_reason_codes: ["prior_comparison_unavailable"],
      selected_basis_role: "blocked",
      current_basis_provenance: "not_established",
      selected_basis_provenance: "not_established",
      current_basis_limitations: ["candidate_only"],
      selected_basis_limitations: ["candidate_only"],
      frontier_ref: "sha256:" + "6".repeat(64),
      frontier_revision: 2,
      frontier_selection: "selected",
      selected_evaluation: null,
      selected_n5_observation: null,
      reentry,
      current_continuation_ref: null,
      current_cheap_consequences: null,
      evaluation_provenance: "not_established",
      observed_admission: false,
      currentness_status: "not_established",
      authority_purpose: "candidate_observation_only",
      publication_authority: false,
    };
    const projection = sameCandidateAcquisitionHistoryProjection();
    Reflect.set(projection, "acquisition_history", [candidate]);
    overviewState.run = parsedRun(projection);
    renderWithProviders(<OverviewTab />);
    const row = screen.getByTestId("overview-acquisition-history-candidate-v5");
    expect(row).toHaveTextContent("simulation_blocked");
    expect(row).toHaveTextContent("prior_comparison_unavailable");
    expect(row).toHaveTextContent("N5 provenance: not_established");
    expect(
      within(row).queryByTestId("overview-candidate-v5-n5"),
    ).not.toBeInTheDocument();
  });
});
