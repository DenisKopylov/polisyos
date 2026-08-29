import type { ReactElement } from "react";
import { render, screen, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type {
  AcquisitionBacklogProjection,
  AcquisitionGrowthPayload,
  AcquisitionRouteProjection,
  StructuralRouteProjection,
} from "@polisyos/runtime-api-client";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { LocaleProvider } from "@/shared/i18n/LocaleProvider";
import {
  EpochSemanticsProvider,
  type EpochSemantics,
} from "@/shared/ui/temporal/TimeSemanticsLabel";
import { runPaperPacketFixture } from "@/test/fixtures/runPaper";

import { AcquisitionExecutionTimeline } from "./AcquisitionExecutionTimeline";
import { AcquisitionGrowthBacklog } from "./AcquisitionGrowthBacklog";
import { AcquisitionPassportPanel } from "./AcquisitionPassportPanel";
import { AcquisitionQuarantineLedger } from "./AcquisitionQuarantineLedger";
import { AcquisitionRouteDetail } from "./AcquisitionRouteDetail";
import { ConnectorAcquisitionScorecard } from "./ConnectorAcquisitionScorecard";
import CaseWorkspacePage from "../routes/CaseWorkspacePage";

const {
  useAcquisitionRoutesMock,
  useAuthzDecisionMock,
  useCaseInspectionMock,
  useCreateHumanDecisionMock,
  useHumanDecisionGateMock,
  useHumanDecisionReviewEffectivenessMock,
} = vi.hoisted(() => ({
  useAcquisitionRoutesMock: vi.fn(),
  useAuthzDecisionMock: vi.fn(),
  useCaseInspectionMock: vi.fn(),
  useCreateHumanDecisionMock: vi.fn(),
  useHumanDecisionGateMock: vi.fn(),
  useHumanDecisionReviewEffectivenessMock: vi.fn(),
}));

vi.mock("@/app/authz/AuthzProvider", () => ({
  useAuthzDecision: () => useAuthzDecisionMock(),
}));

vi.mock("@/features/runs/api/useCaseInspection", () => ({
  useCaseInspection: (...args: unknown[]) => useCaseInspectionMock(...args),
}));

vi.mock("@/features/runs/api/useAcquisitionRoutes", () => ({
  executeAcquisitionRoute: vi.fn(),
  requestAcquisitionDecision: vi.fn(),
  useAcquisitionGrowth: () => ({ data: undefined }),
  useAcquisitionRoute: () => ({ data: undefined, refetch: vi.fn() }),
  useAcquisitionRoutes: (...args: unknown[]) =>
    useAcquisitionRoutesMock(...args),
}));

vi.mock("@/features/runs/api/useHumanDecisions", () => ({
  fetchHumanDecisionEvidence: vi.fn(),
  withoutHumanDecisionOwnedQuery: (search: string) => search,
  useCreateHumanDecision: (...args: unknown[]) =>
    useCreateHumanDecisionMock(...args),
  useHumanDecisionGate: (...args: unknown[]) =>
    useHumanDecisionGateMock(...args),
  useHumanDecisionReviewEffectiveness: (...args: unknown[]) =>
    useHumanDecisionReviewEffectivenessMock(...args),
}));

const digest = (suffix: string) => `sha256:${suffix.repeat(64).slice(0, 64)}`;

function epoch(status: "current" | "revalidation_required"): EpochSemantics {
  const requiresRevalidation = status === "revalidation_required";
  return {
    asOf: requiresRevalidation
      ? "2026-08-29T13:00:00Z"
      : "2026-08-29T12:00:00Z",
    asOfReason: null,
    currentEpochRef: digest(requiresRevalidation ? "b" : "a"),
    epochRefs: [digest("a"), ...(requiresRevalidation ? [digest("b")] : [])],
    kind: "admitted",
    projectionSemanticHash: digest(requiresRevalidation ? "d" : "c"),
    revalidationRequired: requiresRevalidation,
    status,
    validityStatus: requiresRevalidation ? "review_required" : "active",
  };
}

const projectionTime = {
  freshness: {
    basis: "request_observation",
    observed_at: "2026-08-29T12:02:00Z",
    source_as_of: "2026-08-29T11:58:00Z",
    state: "observed",
  },
  payloadAsOf: "2026-08-29T12:00:00Z",
} as const;

function route(): AcquisitionRouteProjection {
  return {
    authority_badge: "behavioral_fixture_not_production",
    authority_capability: "ready",
    cell_id: "cell-1",
    cost_basis: { currency: "USD", total_amount: 1250 },
    execution_capability: "ready",
    external_nonclosures: [],
    planner_record_id: "acquisition-plan-1",
    planner_report_hash: digest("p"),
    qualification_predicate: "not_established",
    qualification_reason: "policy_admission_missing",
    qualification_status: "pending_epoch_activation",
    recommended_strategy: "targeted_primary_data_collection",
    replay_pins: {
      compiled_content_hash: digest("c"),
      compiled_ref: digest("e"),
      cost_basis_hash: digest("f"),
      design_problem_ref: digest("g"),
      source_job_id: "source-job-1",
      terminal_event_id: "terminal-event-1",
    },
    route_id: digest("r"),
    route_projection_hash: digest("r"),
    route_status: "costed_actionable",
    run_id: "run-1",
    schema_version: "AcquisitionRouteProjection@1.0",
    tenant_id: "tenant-1",
    world_growth: "no_growth",
  };
}

function structuralRoute(): StructuralRouteProjection {
  return {
    action_eligibility: "not_applicable",
    gap_class: "structural_gap",
    missing_link: "grounding_relation_missing",
    route_class: "not_a_data_gap",
    route_id: "capstone:first_vertical",
    witness_kind: "estimand_binding_refusal",
  };
}

function history(): AcquisitionGrowthPayload["n13b_history"] {
  return {
    admission: "not_reached",
    attempt_count: 5,
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
    execution_phase: "terminal",
    overlay_epoch_count: 0,
    quarantine: "raw_terminal",
    quarantine_count: 2,
    raw_response_count: 2,
    reentry: "deeper_terminal",
    response_admitted_count: 0,
    terminal_count: 5,
    world_growth: "no_growth",
  };
}

function backlogRow(): AcquisitionBacklogProjection {
  return {
    authority_boundary: "ranking_only_not_voi",
    binding_confidence: 0,
    classification_basis: "not_established",
    gap_class: "not_established",
    rank: 1,
    ranking_method: "interim_binding_confidence_x_route_demand",
    ranking_score: 0,
    route_demand: 2,
    variable_id: "government.balance",
    voi_owner_fit: "metric_residual_granularity_not_supported",
    voi_owner_integration: "routed_to_gy_n13b",
    voi_owner_ref:
      "polisyos.runtime.quality.acquisition_planner.plan_evidence_acquisition",
  };
}

type DecisionRootCase = Readonly<{
  build: () => ReactElement;
  projectionTimed?: boolean;
  rootTestId: string;
  semanticsTestId: string;
  surface: string;
}>;

const decisionRoots: readonly DecisionRootCase[] = [
  {
    build: () => <AcquisitionExecutionTimeline route={route()} />,
    rootTestId: "acquisition-execution-timeline",
    semanticsTestId: "acquisition-timeline-time-semantics",
    surface: "execution timeline",
  },
  {
    build: () => (
      <AcquisitionGrowthBacklog backlog={[backlogRow()]} {...projectionTime} />
    ),
    projectionTimed: true,
    rootTestId: "acquisition-growth-backlog",
    semanticsTestId: "acquisition-backlog-time-semantics",
    surface: "growth backlog",
  },
  {
    build: () => (
      <AcquisitionPassportPanel history={history()} {...projectionTime} />
    ),
    projectionTimed: true,
    rootTestId: "acquisition-passport-panel",
    semanticsTestId: "acquisition-passport-time-semantics",
    surface: "admission passport",
  },
  {
    build: () => (
      <AcquisitionQuarantineLedger history={history()} {...projectionTime} />
    ),
    projectionTimed: true,
    rootTestId: "acquisition-quarantine-ledger",
    semanticsTestId: "acquisition-quarantine-time-semantics",
    surface: "quarantine ledger",
  },
  {
    build: () => (
      <AcquisitionRouteDetail kind="structural" route={structuralRoute()} />
    ),
    rootTestId: "acquisition-structural-route-capstone:first_vertical",
    semanticsTestId: "acquisition-route-time-semantics",
    surface: "structural route refusal",
  },
  {
    build: () => <AcquisitionRouteDetail kind="run" route={route()} />,
    rootTestId: "acquisition-route-detail",
    semanticsTestId: "acquisition-route-time-semantics",
    surface: "costed run route",
  },
  {
    build: () => (
      <ConnectorAcquisitionScorecard
        carrierLiveness={{
          carrier_disposition: "carrier_current_source_profile_mismatch",
          connector_id: "worldbank.wdi",
          execution_tier: "transport_ready",
          tier_decay_findings: ["execution_tier_decay"],
        }}
        familyCount={12}
        {...projectionTime}
      />
    ),
    projectionTimed: true,
    rootTestId: "connector-acquisition-scorecard",
    semanticsTestId: "connector-acquisition-time-semantics",
    surface: "connector scorecard",
  },
];

function tree(epochValue: EpochSemantics, child: ReactElement) {
  return (
    <LocaleProvider>
      <EpochSemanticsProvider value={epochValue}>
        {child}
      </EpochSemanticsProvider>
    </LocaleProvider>
  );
}

function caseTree(epochValue: EpochSemantics) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return (
    <LocaleProvider>
      <EpochSemanticsProvider value={epochValue}>
        <QueryClientProvider client={queryClient}>
          <MemoryRouter initialEntries={["/runs/run-1/case"]}>
            <Routes>
              <Route element={<CaseWorkspacePage />} path="/runs/:runId/case" />
            </Routes>
          </MemoryRouter>
        </QueryClientProvider>
      </EpochSemanticsProvider>
    </LocaleProvider>
  );
}

describe("acquisition decision-root time semantics", () => {
  beforeEach(() => {
    useAuthzDecisionMock.mockReset();
    useCaseInspectionMock.mockReset();
    useAcquisitionRoutesMock.mockReset();
    useCreateHumanDecisionMock.mockReset();
    useHumanDecisionGateMock.mockReset();
    useHumanDecisionReviewEffectivenessMock.mockReset();
    useAuthzDecisionMock.mockReturnValue({
      can: (permission: string) => permission === "runs.review",
      kind: "verified",
    });
    useCaseInspectionMock.mockReturnValue({
      data: {
        packet: runPaperPacketFixture(),
        rawPacketBytes: new TextEncoder().encode("{}"),
      },
      isError: false,
      isLoading: false,
    });
    useCreateHumanDecisionMock.mockReturnValue({ mutateAsync: vi.fn() });
    useHumanDecisionGateMock.mockReturnValue({
      clear: vi.fn(),
      data: null,
      hasSelector: false,
      isError: false,
      isLoading: false,
      revalidate: vi.fn(),
    });
    useHumanDecisionReviewEffectivenessMock.mockReturnValue({ data: null });
  });

  it.each(decisionRoots)(
    "$surface renders and reacts to admitted epoch semantics",
    ({ build, rootTestId, semanticsTestId }) => {
      const { rerender } = render(tree(epoch("current"), build()));
      const root = screen.getByTestId(rootTestId);
      const semantics = within(root).getByTestId(semanticsTestId);
      expect(
        within(semantics).getByTestId("time-semantics-as-of"),
      ).toHaveTextContent("2026-08-29T12:00:00Z");
      expect(
        within(semantics).getByTestId("time-semantics-epoch"),
      ).toHaveTextContent(digest("a"));
      expect(
        within(semantics).getByTestId("time-semantics-epoch-status"),
      ).toHaveTextContent("current");
      expect(
        within(semantics).getByTestId("time-semantics-validity"),
      ).toHaveTextContent("active");
      rerender(tree(epoch("revalidation_required"), build()));
      const movedRoot = screen.getByTestId(rootTestId);
      const movedSemantics = within(movedRoot).getByTestId(semanticsTestId);
      expect(
        within(movedSemantics).getByTestId("time-semantics-as-of"),
      ).toHaveTextContent("2026-08-29T13:00:00Z");
      expect(
        within(movedSemantics).getByTestId("time-semantics-epoch"),
      ).toHaveTextContent(digest("b"));
      expect(
        within(movedSemantics).getByTestId("time-semantics-epoch-status"),
      ).toHaveTextContent("revalidation required");
      expect(
        within(movedSemantics).getByTestId("time-semantics-validity"),
      ).toHaveTextContent("review_required");
      expect(
        within(movedSemantics).getByTestId("time-semantics-revalidation"),
      ).toHaveTextContent("required");

      rerender(<LocaleProvider>{build()}</LocaleProvider>);
      const unknownRoot = screen.getByTestId(rootTestId);
      const unknownSemantics = within(unknownRoot).getByTestId(semanticsTestId);
      expect(
        within(unknownSemantics).getByTestId("time-semantics-epoch-status"),
      ).toHaveTextContent("not established");
      expect(
        within(unknownSemantics).getByTestId("time-semantics-epoch"),
      ).toHaveTextContent("Epoch not established");
      expect(
        within(unknownSemantics).getByTestId("time-semantics-validity"),
      ).toHaveTextContent("not established");
    },
  );

  it.each(decisionRoots.filter(({ projectionTimed }) => projectionTimed))(
    "$surface binds the governed packet time instead of discarding it",
    ({ build, rootTestId, semanticsTestId }) => {
      render(tree(epoch("current"), build()));
      const root = screen.getByTestId(rootTestId);
      const semantics = within(root).getByTestId(semanticsTestId);
      expect(
        within(semantics).getByTestId("time-semantics-payload-as-of"),
      ).toHaveTextContent(projectionTime.payloadAsOf);
      expect(
        within(semantics).getByTestId("time-semantics-source-state"),
      ).toHaveTextContent("observed");
    },
  );

  it("keeps both case-workspace decision branches under admitted epoch semantics", () => {
    useAcquisitionRoutesMock.mockReturnValue({
      data: { packet: { routes: [route()], run_id: "run-1" } },
      isLoading: false,
    });
    const acquisition = render(caseTree(epoch("current")));
    const caseRoot = screen.getByTestId("case-workspace-page");
    expect(
      within(
        within(caseRoot).getByTestId("case-workspace-boundary-time-semantics"),
      ).getByTestId("time-semantics-epoch-status"),
    ).toHaveTextContent("current");
    expect(
      within(
        within(caseRoot).getByTestId("acquisition-approval-time-semantics"),
      ).getByTestId("time-semantics-epoch-status"),
    ).toHaveTextContent("current");
    acquisition.unmount();

    useAcquisitionRoutesMock.mockReturnValue({
      data: { packet: { routes: [], run_id: "run-1" } },
      isLoading: false,
    });
    const human = render(caseTree(epoch("current")));
    const humanRoot = screen.getByTestId("human-decision-workspace");
    expect(
      within(humanRoot).getByTestId("case-workspace-time-semantics"),
    ).toHaveTextContent("current");
    human.rerender(caseTree(epoch("revalidation_required")));
    expect(
      within(screen.getByTestId("human-decision-workspace")).getByTestId(
        "case-workspace-time-semantics",
      ),
    ).toHaveTextContent("revalidation required");
  });
});
