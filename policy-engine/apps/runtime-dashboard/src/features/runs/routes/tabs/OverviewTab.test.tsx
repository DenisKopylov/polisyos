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

  it("preserves conditional status, refusals and scientific boundaries", () => {
    overviewState.run.conditional_simulation_values = [
      {
        run_id: "run-1",
        candidate_id: "candidate-a",
        world_model_record_content_hash: "sha256:" + "a".repeat(64),
        observation: {
          status: "value_conditional",
          reason: "Persisted N5 scenario replayed",
          authority_blockers: ["s8_blocked", "n9_not_admitted"],
          conditional_interaction_evidence: {
            unit_binding_status: "not_established",
            time_binding_status: "not_established",
            sampling_uncertainty_status: "not_established",
          },
        },
      },
      {
        run_id: "run-1",
        candidate_id: "candidate-b",
        observation: {
          status: "value_blocked",
          reason: "Configured profile changed",
          authority_blockers: ["profile_not_current"],
        },
      },
    ];
    renderWithProviders(<OverviewTab />);
    expect(screen.getByText("value_conditional")).toBeVisible();
    expect(screen.getByText("value_blocked")).toBeVisible();
    expect(screen.getByText("Configured profile changed")).toBeVisible();
    expect(screen.getByText("profile_not_current")).toBeVisible();
    expect(
      screen.getByTestId("overview-simulation-boundaries"),
    ).toHaveTextContent("Sampling uncertainty: not_established");
    expect(
      screen.getByTestId("overview-candidate-simulation"),
    ).toHaveTextContent("Publication authority is not established.");
  });

  it("keeps completed children and budget frontier distinct from root outcome", () => {
    overviewState.run.recursive_cycle_checkpoint = {
      schema_version: "policyos.runtime.recursive_cycle_checkpoint.v1",
      status: "partial",
      publication_authority: false,
      pending_frontier: ["child-pending"],
      completed_design_refs: ["child-computed", "child-budget"],
      root_n9_status: "not_run",
      leaf_terminal_kinds: {
        "child-computed": "grounded_abstention",
        "child-budget": "budget_exhausted",
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

  it("refuses foreign or malformed observation rows", () => {
    overviewState.run.conditional_simulation_values = [
      null,
      {
        run_id: "foreign-run",
        observation: {
          status: "value_conditional",
          reason: "foreign-positive",
        },
      },
    ];
    renderWithProviders(<OverviewTab />);
    expect(screen.getAllByTestId("overview-simulation-refused")).toHaveLength(
      2,
    );
    expect(screen.queryByText("foreign-positive")).not.toBeInTheDocument();
  });
});
