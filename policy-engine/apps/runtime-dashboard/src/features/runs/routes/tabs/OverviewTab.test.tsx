import { fireEvent, screen, within } from "@testing-library/react";
import type { ReactNode } from "react";

import { runDetailsSchema } from "@/api/validators";
import * as performanceTelemetry from "@/shared/telemetry/performance";
import { renderWithProviders } from "@/test/render";

const overviewState = vi.hoisted(() => ({
  artifactContentMock: vi.fn(),
  predictiveCalibrationQuery: {
    isPending: true,
    error: undefined,
    data: undefined,
  } as Record<string, unknown>,
  predictiveCalibrationMutation: {
    isPending: false,
    isError: false,
    error: undefined,
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
  useSuspenseGovernanceDebug: () => ({
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
  }),
}));
vi.mock("@/api/hooks/useRunEvidenceContext", () => ({
  useSuspenseRunEvidenceContext: () => ({ data: { context: {} } }),
}));
vi.mock("@/api/hooks/useRunTimeline", () => ({
  useSuspenseRunTimeline: () => ({ data: { timeline: { events: [] } } }),
}));
vi.mock("@/api/hooks/useRunPredictiveCalibration", () => ({
  useRunPredictiveCalibration: () => overviewState.predictiveCalibrationQuery,
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
function parsedRunWithGenericCycleSimulation(projectionRunId = "run-1") {
  return runDetailsSchema.parse({
    meta: {
      request_id: "req-generic-cycle",
      generated_at: "2026-10-11T10:00:00Z",
      source_kinds: ["core_run"],
    },
    run: {
      run_id: "run-1",
      source_kind: "core_run",
      status: "failed",
      generic_cycle_simulation:
        genericCycleSimulationProjection(projectionRunId),
    },
    temporal_scope: null,
  }).run;
}

describe("OverviewTab", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
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
    overviewState.run = { run_id: "run-1" };
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
      root_artifacts: [model, policy, rule],
      root_input_artifacts: [observed],
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

  it("renders parsed generic cycle children and the retained failed sibling as candidate-only history", () => {
    overviewState.run =
      parsedRunWithGenericCycleSimulation() as unknown as Record<
        string,
        unknown
      >;

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
      screen.getByTestId("overview-generic-cycle-failed-branches"),
    ).toHaveTextContent(
      "Sibling retained after its independent attempt stopped.",
    );
    expect(panel).not.toHaveTextContent("publication_ready");
  });

  it("withholds otherwise well-shaped children when the generic projection belongs to another run", () => {
    overviewState.run = parsedRunWithGenericCycleSimulation(
      "run-other",
    ) as unknown as Record<string, unknown>;

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

  it("renders acquisition history as observed candidate lineage with unknown currentness", () => {
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
      n5_observations: [],
      acquisition_history_limitation_code: null,
      acquisition_history: [
        {
          route_receipt_ref: {
            artifact_id: `sha256:${"d".repeat(64)}`,
            kind: "runtime_quality.acquisition_route_loop_receipt",
            media_type: "application/json",
          },
          reentry_receipt_ref: {
            artifact_id: `sha256:${"e".repeat(64)}`,
            kind: "runtime_quality.acquisition_overlay_reentry_receipt",
            media_type: "application/json",
          },
          route_id: `sha256:${"f".repeat(64)}`,
          action_generation: 1,
          terminal_outcome: "reentry_completed",
          old_candidate_id: "candidate-before",
          new_candidate_id: "candidate-after",
          new_candidate_source_ref: {
            artifact_id: `sha256:${"a".repeat(64)}`,
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

    renderWithProviders(<OverviewTab />);

    const history = screen.getByTestId("overview-acquisition-history");
    expect(history).toHaveTextContent("Prior candidate: candidate-before");
    expect(history).toHaveTextContent("Re-entry candidate: candidate-after");
    expect(history).toHaveTextContent("Currentness: not_established");
    expect(history).toHaveTextContent(
      "Origin source: not linked in this record",
    );
    expect(history).toHaveTextContent(
      "Currentness and publication authority are not established.",
    );
    expect(history).toHaveTextContent(`sha256:${"a".repeat(64)}`);
  });

  it("withholds malformed acquisition rows instead of trusting authority markers", () => {
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

    renderWithProviders(<OverviewTab />);

    expect(
      screen.getByTestId("overview-acquisition-history-refused"),
    ).toBeVisible();
    expect(screen.queryByText("candidate-after")).not.toBeInTheDocument();
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

  it("refuses malformed N5 observation rows", () => {
    overviewState.run.candidate_simulation = {
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
    renderWithProviders(<OverviewTab />);
    expect(screen.getAllByTestId("overview-simulation-refused")).toHaveLength(
      2,
    );
  });
});
