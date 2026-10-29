import { retainedAcquisitionHistoryFixture } from "@/test/fixtures/retainedAcquisitionHistory";
import { fireEvent, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";

import { runDetailsSchema } from "../../../../api/validators";
import { runN5InteractionEvidenceFixture } from "@/test/fixtures/runN5InteractionEvidence";
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
          selected_n4_source_ref: { ...source },
          continued_cycle_index: 2,
          current_candidate_occurrences: [
            { candidate_id: candidateId, cycle_index: 2 },
          ],
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

  it("renders the v5 parent joint candidate separately from child rows", () => {
    const projection = genericCycleSimulationProjection("run-1");
    const v5 = {
      ...projection,
      schema_version:
        "policyos.runtime.run_generic_cycle_simulation_projection.v5",
      joint_parent_status: "resolved",
      joint_parent_observations: [c41JointParentObservation()],
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
    expect(parent).toHaveTextContent("non_additive");
    expect(parent).toHaveTextContent(
      "Higher-order residual for outcome-a, step 0: 1",
    );
    expect(parent).toHaveTextContent("alternatives");
    expect(parent).toHaveTextContent(
      "n5_execution_request_provenance_not_established",
    );
    expect(screen.getAllByTestId("overview-generic-cycle-n5-row")).toHaveLength(
      2,
    );
    expect(
      screen.getAllByTestId("overview-generic-cycle-n5-owner-join"),
    ).toHaveLength(2);
    expect(parent).not.toHaveTextContent("publication_ready");
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
