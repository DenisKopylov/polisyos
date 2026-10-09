import { screen } from "@testing-library/react";
import type { ReactNode } from "react";

import { renderWithProviders } from "@/test/render";

const overviewState = vi.hoisted(() => ({
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
vi.mock("@/api/hooks/useArtifactContent", () => ({
  useSuspenseArtifactContent: vi.fn(),
}));
vi.mock("@/app/authz/AuthzProvider", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("@/app/authz/AuthzProvider")>();
  return { ...actual, usePermission: () => false };
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

describe("OverviewTab", () => {
  beforeEach(() => {
    overviewState.run = { run_id: "run-1" };
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
        completed_design_refs: ["child-computed", "child-budget"],
        root_n9_status: "not_run",
        leaf_terminal_kinds: {
          "child-computed": "grounded_abstention",
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
