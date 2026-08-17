import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { FALLBACK_CAPABILITY_MANIFEST } from "@/shared/lib/capabilities";
import { policyDiffFixture } from "@/features/runs/compare/fixtures";
import { untracedDecisionQuantity } from "@/shared/ui/quantity";

const {
  renderArtifactViewerMock,
  useArtifactContentMock,
  useAuthzMock,
  useCapabilitiesMock,
  useCompareCandidatesMock,
  useCompareRunsMock,
  useCounterfactualMetricsMock,
  useDepthNCycleBoardProjectionMock,
  useGovernanceDebugMock,
  useNodeDebugMock,
  usePermissionMock,
  useReviewCollaborationEnabledMock,
  useFeatureFlagsMock,
  useRunAgentsMock,
  useRunDetailSummaryMock,
  useRunDetailsMock,
  useRunEvidenceContextMock,
  useRunErrorsMock,
  useRunInspectorMock,
  useRunLineageMock,
  useRunNodesMock,
  useRunScenariosMock,
  useRunTimelineMock,
  useRunWorkflowMock,
  useTelemetryReadyMarkMock,
} = vi.hoisted(() => ({
  renderArtifactViewerMock: vi.fn(),
  useArtifactContentMock: vi.fn(),
  useAuthzMock: vi.fn(),
  useCapabilitiesMock: vi.fn(),
  useCompareCandidatesMock: vi.fn(),
  useCompareRunsMock: vi.fn(),
  useCounterfactualMetricsMock: vi.fn(),
  useDepthNCycleBoardProjectionMock: vi.fn(),
  useGovernanceDebugMock: vi.fn(),
  useNodeDebugMock: vi.fn(),
  usePermissionMock: vi.fn(),
  useReviewCollaborationEnabledMock: vi.fn(),
  useFeatureFlagsMock: vi.fn(),
  useRunAgentsMock: vi.fn(),
  useRunDetailSummaryMock: vi.fn(),
  useRunDetailsMock: vi.fn(),
  useRunEvidenceContextMock: vi.fn(),
  useRunErrorsMock: vi.fn(),
  useRunInspectorMock: vi.fn(),
  useRunLineageMock: vi.fn(),
  useRunNodesMock: vi.fn(),
  useRunScenariosMock: vi.fn(),
  useRunTimelineMock: vi.fn(),
  useRunWorkflowMock: vi.fn(),
  useTelemetryReadyMarkMock: vi.fn(),
}));

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({
    label: (
      _namespace: string,
      value: string | null | undefined,
      fallback: string,
    ) => fallback ?? value ?? "",
    t: (key: string) => key,
  }),
}));

vi.mock("@/app/providers/TelemetryProvider", () => ({
  useTelemetryReadyMark: (...args: unknown[]) =>
    useTelemetryReadyMarkMock(...args),
}));

vi.mock("@/app/providers/FeatureFlagProvider", () => ({
  useFeatureFlags: (...args: unknown[]) => useFeatureFlagsMock(...args),
}));

vi.mock("@/app/authz/AuthzProvider", () => ({
  AuthzProvider: ({ children }: { children: React.ReactNode }) => children,
  useAuthz: () => useAuthzMock(),
  useMaybeAuthz: () => useAuthzMock(),
  usePermission: (...args: unknown[]) => usePermissionMock(...args),
  useReviewCollaborationEnabled: () => useReviewCollaborationEnabledMock(),
}));

vi.mock("@/shared/components/ErrorBoundary", () => ({
  FeatureErrorBoundary: ({ children }: { children: ReactNode }) => children,
  PageErrorBoundary: ({ children }: { children: ReactNode }) => children,
  PanelErrorBoundary: ({ children }: { children: ReactNode }) => children,
}));

vi.mock("@/features/runs/context/RunInspectorContext", () => ({
  RunInspectorProvider: ({ children }: { children: React.ReactNode }) =>
    children,
  useRunInspector: () => useRunInspectorMock(),
}));

vi.mock("@/api/hooks/useCapabilities", () => ({
  useCapabilities: (...args: unknown[]) => useCapabilitiesMock(...args),
}));

vi.mock("@/api/hooks/useCompareRuns", () => ({
  useCompareCandidates: (...args: unknown[]) =>
    useCompareCandidatesMock(...args),
  useCompareRuns: (...args: unknown[]) => useCompareRunsMock(...args),
}));

vi.mock("@/api/hooks/useCounterfactualMetrics", () => ({
  useCounterfactualMetrics: (...args: unknown[]) =>
    useCounterfactualMetricsMock(...args),
}));

vi.mock("@/features/runs/api/useDepthNCycleBoardProjection", () => ({
  useDepthNCycleBoardProjection: (...args: unknown[]) =>
    useDepthNCycleBoardProjectionMock(...args),
}));

vi.mock("@/api/hooks/useScenarioCapabilities", () => ({
  useRunScenarios: (...args: unknown[]) => useRunScenariosMock(...args),
  useScenarioCapabilities: vi.fn(),
}));

vi.mock("@/api/hooks/useArtifactContent", () => ({
  useArtifactContent: (...args: unknown[]) => useArtifactContentMock(...args),
  useSuspenseArtifactContent: (...args: unknown[]) =>
    useArtifactContentMock(...args),
}));

vi.mock("@/api/hooks/useRunTimeline", () => ({
  useRunTimeline: (...args: unknown[]) => useRunTimelineMock(...args),
  useSuspenseRunTimeline: (...args: unknown[]) => useRunTimelineMock(...args),
}));

vi.mock("@/api/hooks/useRunDetails", () => ({
  useRunDetails: (...args: unknown[]) => useRunDetailsMock(...args),
}));

vi.mock("@/api/hooks/useRunErrors", () => ({
  useRunErrors: (...args: unknown[]) => useRunErrorsMock(...args),
  useSuspenseRunErrors: (...args: unknown[]) => useRunErrorsMock(...args),
}));

vi.mock("@/api/hooks/useRunNodes", () => ({
  useRunNodes: (...args: unknown[]) => useRunNodesMock(...args),
}));

vi.mock("@/api/hooks/useNodeDebug", () => ({
  useNodeDebug: (...args: unknown[]) => useNodeDebugMock(...args),
}));

vi.mock("@/api/hooks/useRunWorkflow", () => ({
  useRunWorkflow: (...args: unknown[]) => useRunWorkflowMock(...args),
  useSuspenseRunWorkflow: (...args: unknown[]) => useRunWorkflowMock(...args),
}));

vi.mock("@/api/hooks/useRunLineage", () => ({
  useRunLineage: (...args: unknown[]) => useRunLineageMock(...args),
  useSuspenseRunLineage: (...args: unknown[]) => useRunLineageMock(...args),
}));

vi.mock("@/api/hooks/useGovernanceDebug", () => ({
  useGovernanceDebug: (...args: unknown[]) => useGovernanceDebugMock(...args),
  useSuspenseGovernanceDebug: (...args: unknown[]) =>
    useGovernanceDebugMock(...args),
}));

vi.mock("@/api/hooks/useRunEvidenceContext", () => ({
  useRunEvidenceContext: (...args: unknown[]) =>
    useRunEvidenceContextMock(...args),
  useSuspenseRunEvidenceContext: (...args: unknown[]) =>
    useRunEvidenceContextMock(...args),
}));

vi.mock("@/api/hooks/useRunAgents", () => ({
  useRunAgents: (...args: unknown[]) => useRunAgentsMock(...args),
  useSuspenseRunAgents: (...args: unknown[]) => useRunAgentsMock(...args),
}));

vi.mock("@/features/artifacts", async () => {
  const actual = await vi.importActual<typeof import("@/features/artifacts")>(
    "@/features/artifacts",
  );

  return {
    ...actual,
    renderArtifactViewer: (...args: unknown[]) =>
      renderArtifactViewerMock(...args),
  };
});

vi.mock("@/features/runs/components/AgentPipelinePanel", () => ({
  default: ({ payload }: { payload: { mode?: string } }) => (
    <div data-testid="agent-pipeline-panel">{payload.mode ?? "pipeline"}</div>
  ),
}));

vi.mock("@/features/runs/components/GovernanceReport", () => ({
  default: ({ data }: { data: { status?: string } }) => (
    <div data-testid="governance-report">{data.status ?? "governance"}</div>
  ),
}));

vi.mock("@/features/runs/components/debug/ErrorsPanel", () => ({
  default: ({ errors }: { errors: Array<{ code: string }> }) => (
    <div data-testid="errors-panel">{errors.length}</div>
  ),
}));

vi.mock("@/features/runs/components/debug/NodeDebugPanel", () => ({
  default: ({
    debugData,
    onSelectAlias,
    selectedAlias,
  }: {
    debugData: { detail?: string } | null;
    onSelectAlias: (alias: string) => void;
    selectedAlias: string | null;
  }) => (
    <button
      data-testid="node-debug-panel"
      type="button"
      onClick={() => onSelectAlias("node-b")}
    >
      {selectedAlias ?? "none"}:{debugData?.detail ?? "no-debug"}
    </button>
  ),
}));

vi.mock("@/features/runs/components/WorkflowDagPanel", () => ({
  default: ({ runId }: { runId: string }) => (
    <div data-testid="workflow-dag-panel">{runId}</div>
  ),
}));

vi.mock("@/features/causal", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/features/causal")>();

  return {
    ...actual,
    AdjustmentSetHighlight: () => (
      <div data-testid="adjustment-set-highlight" />
    ),
    CausalGraphCanvas: ({
      edges,
      highlightedPath,
      nodes,
    }: {
      edges: unknown[];
      highlightedPath?: string[];
      nodes: unknown[];
    }) => (
      <div data-testid="causal-graph-canvas">
        {nodes.length}:{edges.length}:{highlightedPath?.length ?? 0}
      </div>
    ),
    EdgeDetailPanel: () => <div data-testid="edge-detail-panel" />,
    IdentificationOverlay: () => <div data-testid="identification-overlay" />,
    NodeDetailPanel: () => <div data-testid="node-detail-panel" />,
    PathAnalysisPanel: ({ paths }: { paths: unknown[] }) => (
      <div data-testid="path-analysis-panel">{paths.length}</div>
    ),
    TransportOverlay: () => <div data-testid="transport-overlay" />,
  };
});

vi.mock("@/shared/ui/LineageGraph", () => ({
  default: ({ nodes }: { nodes: unknown[] }) => (
    <div data-testid="lineage-graph">{nodes.length}</div>
  ),
}));

vi.mock("@/features/runs/routes/useRunDetailSummary", async () => {
  const actual = await vi.importActual(
    "@/features/runs/routes/useRunDetailSummary",
  );
  return {
    ...actual,
    useRunDetailSummary: (...args: unknown[]) =>
      useRunDetailSummaryMock(...args),
  };
});

import RunComparePage from "@/features/runs/routes/RunComparePage";
import RunDeckPage from "@/features/runs/routes/RunDeckPage";
import RunDetailLayout from "@/features/runs/routes/RunDetailLayout";
import RunReportPage from "@/features/runs/routes/RunReportPage";
import AgentsTab from "@/features/runs/routes/tabs/AgentsTab";
import ArtifactsTab from "@/features/runs/routes/tabs/ArtifactsTab";
import CausalTab from "@/features/runs/routes/tabs/CausalTab";
import DebugTab from "@/features/runs/routes/tabs/DebugTab";
import EvidenceTab from "@/features/runs/routes/tabs/EvidenceTab";
import GovernanceTab from "@/features/runs/routes/tabs/GovernanceTab";
import OverviewTab from "@/features/runs/routes/tabs/OverviewTab";
import WorkflowTab from "@/features/runs/routes/tabs/WorkflowTab";

function createSummary(overrides: Record<string, unknown> = {}) {
  const selectedNeed = {
    geography: "CA",
    metric: "Inflation",
    needId: "need-1",
    notes: ["need-note"],
    timeEnd: "2024",
    timeStart: "2020",
    granularity: "annual",
  };
  const selectedPlan = {
    connectorId: "world-bank",
    datasetId: "inflation-dataset",
    matchedNeedIds: ["need-1"],
    metricId: "inflation",
    notes: ["plan-note"],
    planId: "plan-1",
    sourceLane: "fastlane",
  };
  const selectedPromotion = {
    confidence: 0.82,
    connectorId: "world-bank",
    datasetId: "inflation-dataset",
    metricId: "inflation",
    promotionId: "promotion-1",
    sourceLane: "explorelane",
    status: "pending",
  };

  return {
    agentsQuery: { error: null, isError: false, isLoading: false },
    artifactRefs: [
      { artifact_id: "artifact-1", kind: "decision_card" },
      { artifact_id: "artifact-2", kind: "simulation_results" },
    ],
    blockerCount: 2,
    decisionArtifact: { kind: "decision_card", mode: "preview" },
    decisionArtifactQuery: { error: null, isError: false, isLoading: false },
    decisionHeadline: "Decision headline",
    decisionScore: untracedDecisionQuantity({
      metricId: "test.decision_score",
      point: 0.82,
    }),
    decisionScoreStyle: { "--score-angle": "278deg" },
    decisionView: {
      confidence: "HIGH",
      distributional: {
        breakdowns: [
          {
            dimensionLabel: "Region",
            rows: [
              {
                cohortLabel: "North",
                direction: "positive",
                isVulnerable: false,
                populationShare: 0.41,
                primaryDelta: 0.2,
              },
              {
                cohortLabel: "South",
                direction: "negative",
                isVulnerable: true,
                populationShare: 0.12,
                primaryDelta: -0.1,
              },
            ],
          },
        ],
      },
      keyMetrics: [
        {
          ciLevel: 0.95,
          ciLower: 0.8,
          ciUpper: 1.6,
          formatted: "+1.2",
          name: "GDP",
          unit: "%",
          value: 1.2,
        },
        {
          assumptionWarnings: ["unmeasured confounder"],
          ciLevel: null,
          ciLower: null,
          ciUpper: null,
          formatted: "+0.4",
          name: "Inflation",
          unit: "%",
          value: 0.4,
        },
      ],
      policySummary: "Policy summary",
      verdict: "APPROVE",
    },
    evidenceContext: {
      dataNeeds: [selectedNeed],
      fetchPlans: [selectedPlan],
      promotionCandidates: [selectedPromotion],
      relatedArtifacts: [{ artifact_id: "artifact-1", kind: "decision_card" }],
      warnings: ["warning-a"],
    },
    evidenceContextQuery: { error: null, isError: false, isLoading: false },
    governance: {
      status: "ready",
      transport_summary: { status: "transportable" },
    },
    governanceIssues: [
      {
        code: "issue-1",
        message: "Issue one",
        passId: "legal-pass",
        severity: "warning",
      },
    ],
    governanceQuery: { error: null, isError: false, isLoading: false },
    pipeline: {
      decision_packet_ref: {
        artifact_id: "artifact-1",
        kind: "scientist.decision_packet",
      },
      evaluator: { scores: { total_score: 0.91 }, verdict: "APPROVE" },
      iteration_lifecycle: { state: "completed" },
      mode: "nl",
      preflight: { diagnostics: [{}], ready_to_run: true },
    },
    primaryDecisionArtifactId: "artifact-1",
    primaryIssue: null,
    run: {
      duration_ms: 1200,
      root_artifacts: [{ artifact_id: "artifact-1", kind: "decision_card" }],
      run_id: "run-1",
      source_kind: "core_run",
      started_at: "2026-03-09T10:00:00Z",
      status: "completed",
    },
    runBootstrapPending: false,
    runDetailsQuery: { error: null, isError: false, isLoading: false },
    runReady: true,
    selectedNeed,
    selectedPlan,
    selectedPromotion,
    transportStatus: "transportable",
    ...overrides,
  };
}

function toEvidenceContextPayload(
  context: ReturnType<typeof createSummary>["evidenceContext"],
) {
  return {
    run_id: "run-1",
    source_kind: "core_run",
    related_artifacts: context.relatedArtifacts ?? [],
    warnings: context.warnings ?? [],
    data_needs: (context.dataNeeds ?? []).map((need) => ({
      need_id: need.needId,
      metric: need.metric,
      geography: need.geography,
      time_start: need.timeStart,
      time_end: need.timeEnd,
      granularity: need.granularity,
      notes: need.notes,
    })),
    fetch_plans: (context.fetchPlans ?? []).map((plan) => ({
      plan_id: plan.planId,
      metric_id: plan.metricId,
      connector_id: plan.connectorId,
      dataset_id: plan.datasetId,
      source_lane: plan.sourceLane,
      matched_need_ids: plan.matchedNeedIds,
      notes: plan.notes,
    })),
    promotion_candidates: (context.promotionCandidates ?? []).map(
      (promotion) => ({
        promotion_id: promotion.promotionId,
        metric_id: promotion.metricId,
        connector_id: promotion.connectorId,
        dataset_id: promotion.datasetId,
        source_lane: promotion.sourceLane,
        confidence: promotion.confidence,
        status: promotion.status,
      }),
    ),
  };
}

function renderRoute(
  path: string,
  routePath: string,
  element: React.ReactNode,
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={routePath} element={element} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function renderNestedRunDetail(path: string) {
  // The DS16 panels are producer-bound as of C05, so this route now needs a query client
  // like `renderRoute` already had.
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/runs/:runId" element={<RunDetailLayout />}>
          <Route
            path="overview"
            element={<div data-testid="outlet-overview" />}
          />
          <Route
            path="governance"
            element={<div data-testid="outlet-governance" />}
          />
        </Route>
        <Route path="/runs" element={<RunDetailLayout />} />
      </Routes>
    </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("run detail surfaces", () => {
  beforeEach(() => {
    const summary = createSummary();

    window.localStorage.clear();
    useTelemetryReadyMarkMock.mockReset();
    useFeatureFlagsMock.mockReturnValue({
      flags: {
        atlasCommandPalette: true,
        atlasNestedSurfaces: true,
      },
      isEnabled: (key: string) =>
        key === "atlasCommandPalette" || key === "atlasNestedSurfaces",
      source: "props",
      status: "ready",
    });
    useAuthzMock.mockReturnValue({
      can: () => true,
      hasRole: () => false,
      isWorkspaceAllowed: () => true,
      permissions: new Set<string>(),
      roles: new Set<string>(),
      status: "ready",
      user: { feature_overrides: { enableReviewCollaboration: false } },
    });
    usePermissionMock.mockReturnValue(true);
    useReviewCollaborationEnabledMock.mockReturnValue(false);
    useCapabilitiesMock.mockReturnValue({
      data: FALLBACK_CAPABILITY_MANIFEST,
    });
    useCompareCandidatesMock.mockReturnValue({
      data: { candidates: [] },
      error: null,
      isError: false,
      isLoading: false,
    });
    useCompareRunsMock.mockReturnValue({
      data: policyDiffFixture,
      error: null,
      isError: false,
      isLoading: false,
    });
    useRunScenariosMock.mockReturnValue({
      data: { scenarios: [] },
      error: null,
      isError: false,
      isLoading: false,
    });
    useCounterfactualMetricsMock.mockReturnValue({
      data: { metrics: {} },
      error: null,
      isError: false,
      isLoading: false,
    });
    useDepthNCycleBoardProjectionMock.mockReturnValue({
      data: undefined,
      error: null,
      isError: false,
      isLoading: false,
    });
    useRunInspectorMock.mockReturnValue(summary);
    useGovernanceDebugMock.mockReturnValue({
      data: {
        debug: {
          ...summary.governance,
          issues: summary.governanceIssues,
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    useRunAgentsMock.mockReturnValue({
      data: { pipeline: summary.pipeline },
      error: null,
      isError: false,
      isLoading: false,
    });
    useRunEvidenceContextMock.mockReturnValue({
      data: {
        context: toEvidenceContextPayload(summary.evidenceContext),
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    useRunTimelineMock.mockReturnValue({
      data: {
        timeline: {
          events: [
            {
              event: "start",
              index: 1,
              input_artifact_ids: ["artifact-1"],
              output_artifact_ids: ["artifact-2"],
              phase: "bootstrap",
              timestamp: "2026-03-09T10:00:05Z",
            },
          ],
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    useRunErrorsMock.mockReturnValue({
      data: {
        errors: [
          {
            code: "runtime_failed",
            message: "Runtime failed",
            source: "executor",
            timestamp: "2026-03-09T10:01:00Z",
          },
        ],
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    useRunNodesMock.mockReturnValue({
      data: {
        nodes: [{ alias: "node-a" }, { alias: "node-b" }],
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    useNodeDebugMock.mockReturnValue({
      data: { debug: { detail: "node-debug" } },
      error: null,
      isError: false,
      isLoading: false,
    });
    useRunWorkflowMock.mockReturnValue({
      data: { workflow: { summary: { node_count: 2 } } },
      error: null,
      isError: false,
      isLoading: false,
    });
    useRunDetailsMock.mockReturnValue({
      data: {
        run: {
          artifacts: [],
          run_id: "run-1",
          source_kind: "core_run",
          status: "completed",
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    useRunLineageMock.mockReturnValue({
      data: {
        lineage: {
          edges: [{ from: "artifact-1", to: "artifact-2" }],
          is_complete: true,
          missing_artifact_ids: ["artifact-missing"],
          nodes: [{ id: "artifact-1" }, { id: "artifact-2" }],
          root_artifact_ids: ["artifact-1"],
          total_edges: 1,
          total_nodes: 2,
          total_size_bytes: 2048,
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    useArtifactContentMock.mockImplementation((artifactId?: string) => ({
      data: artifactId
        ? {
            artifact: {
              artifact_id: artifactId,
              kind:
                artifactId === "artifact-2"
                  ? "simulation_results"
                  : "decision_card",
              mode: "preview",
              preview: { artifactId },
              size_bytes: artifactId === "artifact-2" ? 4096 : 1024,
              truncated: artifactId === "artifact-2",
            },
          }
        : undefined,
      error: null,
      isError: false,
      isLoading: false,
    }));
    useRunDetailSummaryMock.mockImplementation((runId: string) =>
      createSummary({
        artifactRefs:
          runId === "run-2"
            ? [{ artifact_id: "artifact-3", kind: "decision_card" }]
            : [{ artifact_id: "artifact-1", kind: "decision_card" }],
        blockerCount: runId === "run-2" ? 1 : 2,
        decisionScore: untracedDecisionQuantity({
          metricId: "test.decision_score",
          point: runId === "run-2" ? 0.63 : 0.82,
        }),
        evidenceContext: {
          dataNeeds: [{ metric: runId === "run-2" ? "GDP" : "Inflation" }],
          fetchPlans: runId === "run-2" ? [] : [{ planId: "plan-1" }],
          promotionCandidates:
            runId === "run-2" ? [] : [{ promotionId: "promotion-1" }],
        },
        run: {
          duration_ms: 1200,
          root_artifacts: [],
          run_id: runId,
          source_kind: "core_run",
          started_at: "2026-03-09T10:00:00Z",
          status: "completed",
        },
      }),
    );
    renderArtifactViewerMock.mockImplementation(
      ({ kind }: { kind: string }) => (
        <div data-testid="artifact-viewer">{kind}</div>
      ),
    );
    vi.spyOn(window, "print").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders bootstrap state and redirects legacy tab requests in RunDetailLayout", async () => {
    useRunInspectorMock.mockReturnValue(
      createSummary({
        run: null,
        runBootstrapPending: true,
      }),
    );

    renderNestedRunDetail("/runs/run-1/governance?tab=decision");

    expect(await screen.findByTestId("run-detail-page")).toBeInTheDocument();
    expect(screen.getByTestId("run-tab-nav")).toBeInTheDocument();

    useRunInspectorMock.mockReturnValue(createSummary());
    renderNestedRunDetail("/runs/run-1/governance?tab=decision");

    expect(await screen.findByTestId("outlet-overview")).toBeInTheDocument();
    expect(screen.getByTestId("run-tab-link-overview")).toBeInTheDocument();
  });

  it("renders required-state and action branches in RunDetailLayout", async () => {
    renderNestedRunDetail("/runs");
    expect(screen.getByText("pages.runs.requiredRunId")).toBeInTheDocument();

    useRunInspectorMock.mockReturnValue(
      createSummary({
        pipeline: {
          evaluator: { scores: { total_score: 0.5 }, verdict: "REPLAN_NEEDED" },
          preflight: { diagnostics: [{}], ready_to_run: false },
        },
      }),
    );
    renderNestedRunDetail("/runs/run-1/overview");

    expect(await screen.findByTestId("run-replan-link")).toBeInTheDocument();
  });

  it("keeps novel owner grades neutral and does not infer replanning from their labels", async () => {
    const summary = createSummary();
    useRunInspectorMock.mockReturnValue(
      createSummary({
        decisionView: {
          ...summary.decisionView,
          verdict: "future-packet-grade",
        },
        pipeline: {
          ...summary.pipeline,
          evaluator: {
            ...summary.pipeline.evaluator,
            verdict: "REPLAN_FUTURE_OWNER_GRADE",
          },
          preflight: { diagnostics: [], ready_to_run: true },
        },
      }),
    );

    renderNestedRunDetail("/runs/run-1/overview");

    expect(await screen.findByTestId("run-evaluator-grade")).toHaveTextContent(
      "REPLAN_FUTURE_OWNER_GRADE",
    );
    expect(screen.getByTestId("run-evaluator-grade")).toHaveAttribute(
      "data-decision-grade-presentation",
      "unrecognized",
    );
    expect(screen.getByTestId("run-packet-grade")).toHaveTextContent(
      "future-packet-grade",
    );
    expect(screen.queryByTestId("run-replan-link")).not.toBeInTheDocument();
  });

  it("keeps the open run status label opaque and neutral", async () => {
    useRunInspectorMock.mockReturnValue(
      createSummary({
        run: {
          duration_ms: 1_200,
          root_artifacts: [],
          run_id: "run-1",
          source_kind: "core_run",
          started_at: "2026-03-09T10:00:00Z",
          status: "completed_future",
        },
      }),
    );

    renderNestedRunDetail("/runs/run-1/overview");

    expect(await screen.findByText("completed_future")).toHaveClass(
      "bg-white/65",
      "text-muted",
    );
  });

  it("renders the Atlas decision packet summary in RunDetailLayout", async () => {
    renderNestedRunDetail("/runs/run-1/overview");

    expect(
      await screen.findByTestId("run-decision-packet"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("ambient-telemetry-hud")).toBeInTheDocument();
    expect(screen.getByTestId("ambient-trust-threshold")).toBeInTheDocument();
    expect(
      screen.getByText("pages.runs.decisionPacketHeading"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("pages.runs.impactDeltasTitle"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("pages.runs.strongestEvidenceTitle"),
    ).toBeInTheDocument();
    expect(screen.getByText("pages.runs.uncertaintyTitle")).toBeInTheDocument();
    expect(
      screen.getByTestId("run-detail-uncertainty-visual"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("scientific-depth-panel")).toHaveTextContent(
      "common.unavailable",
    );
    expect(
      screen.getByTestId("public-sector-readiness-panel"),
    ).toHaveTextContent("common.unavailable");
    expect(screen.getByTestId("publication-packet-panel")).toBeInTheDocument();
    expect(screen.getByTestId("argument-map-panel")).toBeInTheDocument();
    expect(
      screen.getByTestId("deterministic-explanations-panel"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("citation-model-card-panel")).toBeInTheDocument();
    expect(screen.getByTestId("coverage-caveat-panel")).toBeInTheDocument();
    expect(screen.getByTestId("threshold-contract-panel")).toBeInTheDocument();
    expect(screen.getByTestId("glossary-lens-panel")).toBeInTheDocument();
    expect(screen.getByTestId("bureaucratic-forms-panel")).toBeInTheDocument();
    expect(screen.getByTestId("operator-craft-panel")).toBeInTheDocument();
    expect(screen.getByTestId("operator-threshold-dial")).toBeInTheDocument();
    expect(screen.getByTestId("annotation-surface-panel")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-wallet-panel")).toBeInTheDocument();
    expect(screen.getByTestId("reading-onboarding-panel")).toBeInTheDocument();
    expect(
      within(screen.getByTestId("run-detail-uncertainty-visual")).getAllByText(
        "GDP",
      ).length,
    ).toBeGreaterThan(0);
    expect(
      screen.getByText(
        "Inflation Dataset is queued on Explorelane with 82% confidence.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("Decision Card")).toBeInTheDocument();
    expect(screen.getByTestId("run-reading-view-link")).toHaveAttribute(
      "href",
      "/artifacts/artifact-1?tab=content&view=reading",
    );
  });

  it("label text shape blocker count timestamp and truthiness do not change posture", async () => {
    useRunInspectorMock.mockReturnValue(
      createSummary({
        blockerCount: 9,
        governancePass: true,
        transportStatus: "verified",
        verifiedAt: "2026-07-31T10:00:00Z",
      }),
    );

    renderNestedRunDetail("/runs/run-1/overview");

    const strip = await screen.findByTestId("provenance-strip");
    expect(strip).toHaveTextContent("Governance blocked");
    expect(within(strip).queryByLabelText("verified")).not.toBeInTheDocument();
    for (const item of within(strip).getAllByRole("listitem")) {
      expect(item).not.toHaveAttribute("data-intent");
    }
    for (const glyph of within(strip).getAllByRole("img")) {
      expect(glyph).not.toHaveAttribute("data-glyph-intent");
    }
  });

  it("blocker counts cannot select provenance clothing", async () => {
    useRunInspectorMock.mockReturnValue(createSummary({ blockerCount: 7 }));
    const blockedView = renderNestedRunDetail("/runs/run-1/overview");
    const blockedStrip = await screen.findByTestId("provenance-strip");
    const blockedClothing = within(blockedStrip)
      .getAllByRole("img")
      .map((glyph) => ({
        color: glyph.style.color,
        intent: glyph.getAttribute("data-glyph-intent"),
      }));
    blockedView.unmount();

    useRunInspectorMock.mockReturnValue(createSummary({ blockerCount: 0 }));
    renderNestedRunDetail("/runs/run-1/overview");
    const passingStrip = await screen.findByTestId("provenance-strip");
    const passingClothing = within(passingStrip)
      .getAllByRole("img")
      .map((glyph) => ({
        color: glyph.style.color,
        intent: glyph.getAttribute("data-glyph-intent"),
      }));

    expect(blockedClothing).toEqual(passingClothing);
    expect(
      passingClothing.every(
        ({ color, intent }) => color === "" && intent === null,
      ),
    ).toBe(true);
  });

  it("renders honest-diagnostics operator root cause fields from run projection", async () => {
    useRunInspectorMock.mockReturnValue(
      createSummary({
        run: {
          duration_ms: 1200,
          operator_diagnostic: {
            authoritative_runtime_state: "failed",
            projection_source: "runtime_run_details",
            owner: "team-policy-semantics",
            phase: "policy_grounding",
            first_blocking_cause: "policy_grounding_matrix_ref_missing",
            upstream_missing_input: "policy_grounding_matrix_ref",
            downstream_impact:
              "Readiness and approval projections remain closed.",
            authority_refs: {
              quality_scorecard: "quality_evidence/quality_scorecard.json",
              runtime_event_log: "sha256:bbbb",
            },
            blocker_overridable: false,
            evidence_refs: ["quality_evidence/policy_grounding_matrix.json"],
            next_diagnostic_command:
              "uv run pytest tests/unit/runtime/quality/test_scorecard.py -q",
          },
          root_artifacts: [
            { artifact_id: "artifact-1", kind: "decision_card" },
          ],
          run_id: "run-1",
          source_kind: "core_run",
          started_at: "2026-03-09T10:00:00Z",
          status: "failed",
        },
      }),
    );
    renderNestedRunDetail("/runs/run-1/overview");

    const diagnosticPanel = await screen.findByTestId(
      "operator-diagnostic-panel",
    );
    expect(
      within(diagnosticPanel).getByText("runtime_run_details"),
    ).toBeInTheDocument();
    expect(within(diagnosticPanel).getByText("failed")).toBeInTheDocument();
    expect(
      within(diagnosticPanel).getByText("team-policy-semantics"),
    ).toBeInTheDocument();
    expect(
      within(diagnosticPanel).getByText("policy_grounding_matrix_ref_missing"),
    ).toBeInTheDocument();
    expect(
      within(diagnosticPanel).getByText("policy_grounding_matrix_ref"),
    ).toBeInTheDocument();
    expect(
      within(diagnosticPanel).getByText(
        "uv run pytest tests/unit/runtime/quality/test_scorecard.py -q",
      ),
    ).toBeInTheDocument();
  });

  it("renders comparison, report, and deck pages", async () => {
    renderRoute("/runs/compare", "/runs/compare", <RunComparePage />);
    expect(
      screen.getByText("pages.runs.compare.requiredTitle"),
    ).toBeInTheDocument();

    renderRoute(
      "/runs/compare?base=run-1&target=run-2",
      "/runs/compare",
      <RunComparePage />,
    );
    expect(screen.getByTestId("policy-diff-view")).toBeInTheDocument();
    expect(screen.getAllByText("Employment rate").length).toBeGreaterThan(0);

    renderRoute("/report", "/report", <RunReportPage />);
    expect(
      screen.getByText("pages.runs.report.requiredTitle"),
    ).toBeInTheDocument();

    renderRoute("/runs/run-1/report", "/runs/:runId/report", <RunReportPage />);
    await userEvent.click(
      screen.getByRole("button", { name: "pages.runs.report.printPdf" }),
    );
    expect(window.print).toHaveBeenCalled();
    expect(
      screen.getByRole("button", { name: "pages.runs.report.exportJson" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Runtime failed")).toBeInTheDocument();

    renderRoute("/deck", "/deck", <RunDeckPage />);
    expect(
      screen.getByText("pages.runs.deck.requiredTitle"),
    ).toBeInTheDocument();

    renderRoute("/runs/run-1/deck", "/runs/:runId/deck", <RunDeckPage />);
    expect(screen.getByTestId("run-deck-page")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "pages.runs.deck.printPdf" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("run-deck-slide-evidence")).toBeInTheDocument();
    expect(
      within(screen.getByTestId("run-deck-page")).queryByText(
        /\b(?:ratify|hold|recommendation)\b/iu,
      ),
    ).not.toBeInTheDocument();
  });

  it("renders reading onboarding as a neutral checklist, never an approval gate", async () => {
    renderNestedRunDetail("/runs/run-1/overview");

    const panel = await screen.findByTestId("reading-onboarding-panel");
    expect(within(panel).queryByText(/approval/iu)).not.toBeInTheDocument();
    expect(
      within(panel).getByTestId("reading-onboarding-progress"),
    ).toHaveAttribute("data-presentation", "interaction-neutral");
    expect(
      within(panel).getByTestId("reading-onboarding-completion-step"),
    ).toHaveAttribute("data-presentation", "interaction-neutral");
  });

  it("renders OverviewTab with decision, governance, evidence, and timeline sections", () => {
    const summary = createSummary();
    useRunInspectorMock.mockReturnValue(
      createSummary({
        pipeline: {
          ...summary.pipeline,
          evaluator: {
            ...summary.pipeline.evaluator,
            verdict: "future-overview-grade",
          },
        },
      }),
    );

    renderRoute("/runs/run-1/overview", "/runs/:runId/:tab", <OverviewTab />);

    expect(screen.getByTestId("run-tab-overview")).toBeInTheDocument();
    expect(screen.getAllByText("Policy summary").length).toBeGreaterThan(0);
    expect(screen.getByTestId("overview-reading-view-link")).toHaveAttribute(
      "href",
      "/artifacts/artifact-1?tab=content&view=reading",
    );
    expect(screen.getByText("Issue one")).toBeInTheDocument();
    expect(screen.getAllByText("Inflation").length).toBeGreaterThan(0);
    expect(screen.getByText("start")).toBeInTheDocument();
    expect(screen.getByTestId("overview-evaluator-grade")).toHaveTextContent(
      "future-overview-grade",
    );
    expect(screen.getByTestId("overview-evaluator-grade")).toHaveAttribute(
      "data-decision-grade-presentation",
      "unrecognized",
    );
    expect(
      screen.getByTestId("overview-scenario-workbench"),
    ).toBeInTheDocument();
    expect(useDepthNCycleBoardProjectionMock).toHaveBeenCalledWith();
  });

  it("keeps novel and missing governance severity labels opaque and neutral", () => {
    const summary = createSummary();
    useGovernanceDebugMock.mockReturnValue({
      data: {
        debug: {
          ...summary.governance,
          issues: [
            {
              code: "future-severity",
              message: "Future owner label",
              severity: "future_owner_severity",
            },
            {
              code: "missing-severity",
              message: "Missing owner label",
            },
          ],
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });

    renderRoute("/runs/run-1/overview", "/runs/:runId/:tab", <OverviewTab />);

    expect(
      screen.getByTestId("overview-governance-severity-future-severity"),
    ).toHaveTextContent("future_owner_severity");
    expect(
      screen.getByTestId("overview-governance-severity-future-severity"),
    ).toHaveAttribute("data-presentation", "owner-label-neutral");
    expect(
      screen.getByTestId("overview-governance-severity-missing-severity"),
    ).toHaveTextContent("common.unknown");
    expect(
      screen.getByTestId("overview-governance-severity-missing-severity"),
    ).toHaveAttribute("data-presentation", "owner-label-neutral");
  });

  it("renders EvidenceTab with deep links and warnings", () => {
    renderRoute("/runs/run-1/evidence", "/runs/:runId/:tab", <EvidenceTab />);

    expect(screen.getByTestId("run-tab-evidence")).toBeInTheDocument();
    expect(screen.getByTestId("evidence-link-need-need-1")).toHaveAttribute(
      "href",
      expect.stringContaining("/evidence?runId=run-1&focus=need&needId=need-1"),
    );
    expect(
      screen.getByTestId("promotion-action-link-promotion-1"),
    ).toHaveAttribute(
      "href",
      expect.stringContaining(
        "/evidence?runId=run-1&focus=promotion&promotionId=promotion-1",
      ),
    );
    expect(screen.getAllByText("warning-a")).toHaveLength(2);
  });

  it("renders ArtifactsTab and switches the selected artifact", async () => {
    renderRoute("/runs/run-1/artifacts", "/runs/:runId/:tab", <ArtifactsTab />);

    expect(screen.getByTestId("run-tab-artifacts")).toBeInTheDocument();
    expect(screen.getByTestId("artifact-viewer")).toHaveTextContent(
      "decision_card",
    );

    await userEvent.click(screen.getByTestId("artifact-card-artifact-2"));

    await waitFor(() =>
      expect(useArtifactContentMock).toHaveBeenLastCalledWith("artifact-2", {
        maxBytes: 262144,
      }),
    );
    expect(
      screen.getByRole("link", { name: "common.openArtifact" }),
    ).toHaveAttribute("href", "/artifacts/artifact-2");
  });

  it("renders DebugTab with timeline, node debug, and runtime errors", async () => {
    renderRoute("/runs/run-1/debug", "/runs/:runId/:tab", <DebugTab />);

    expect(screen.getByTestId("run-tab-debug")).toBeInTheDocument();
    expect(screen.getAllByText("start").length).toBeGreaterThan(0);
    expect(await screen.findByTestId("node-debug-panel")).toHaveTextContent(
      "node-a:node-debug",
    );
    expect(await screen.findByTestId("errors-panel")).toHaveTextContent("1");
  });

  it("renders WorkflowTab with DAG, lineage graph, and missing artifact warning", async () => {
    renderRoute("/runs/run-1/workflow", "/runs/:runId/:tab", <WorkflowTab />);

    expect(screen.getByTestId("run-tab-workflow")).toBeInTheDocument();
    expect(
      await screen.findByTestId("run-choreography-panel"),
    ).toHaveTextContent("1");
    expect(await screen.findByTestId("workflow-dag-panel")).toHaveTextContent(
      "run-1",
    );
    expect(await screen.findByTestId("lineage-graph")).toHaveTextContent("2");
    expect(screen.getByText("pages.runs.missingArtifacts")).toBeInTheDocument();
  });

  it("renders CausalTab as an editable draft atlas when no DAG artifact exists", async () => {
    const rendered = renderRoute(
      "/runs/run-1/causal",
      "/runs/:runId/:tab",
      <CausalTab />,
    );

    expect(
      await screen.findByTestId("causal-atlas-editor"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("causal-graph-canvas")).toHaveTextContent(
      "2:1:0",
    );
    expect(screen.getByText("phase32.causal.draft")).toBeInTheDocument();

    await userEvent.type(
      screen.getByLabelText("phase32.causal.nodeLabel"),
      "Mediator",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "phase32.causal.addNode" }),
    );
    expect(screen.getByTestId("causal-graph-canvas")).toHaveTextContent(
      "3:1:0",
    );

    rendered.unmount();
    renderRoute("/runs/run-1/causal", "/runs/:runId/:tab", <CausalTab />);

    expect(await screen.findByTestId("causal-graph-canvas")).toHaveTextContent(
      "3:1:0",
    );
  });

  it("renders AgentsTab and GovernanceTab through lazy panels", async () => {
    renderRoute("/runs/run-1/agents", "/runs/:runId/:tab", <AgentsTab />);
    expect(await screen.findByTestId("agent-pipeline-panel")).toHaveTextContent(
      "nl",
    );

    renderRoute(
      "/runs/run-1/governance",
      "/runs/:runId/:tab",
      <GovernanceTab />,
    );
    expect(await screen.findByTestId("governance-report")).toHaveTextContent(
      "ready",
    );
    expect(screen.getByTestId("dispute-registry-panel")).toHaveTextContent(
      "Issue one",
    );
    expect(
      screen.getByTestId("public-sector-readiness-panel"),
    ).toBeInTheDocument();
  });

  it("renders both producer-bound panels with their sanctioned refusal", () => {
    // C05 replaced containment with binding: the panels now read a producer and render
    // its typed refusals. The sanctioned refusal key is still what a panel shows when
    // the producer has served no member.
    renderNestedRunDetail("/runs/run-1/overview");

    expect(
      screen.getByTestId("public-sector-readiness-panel"),
    ).toHaveTextContent("common.unavailable");
    expect(screen.getByTestId("scientific-depth-panel")).toHaveTextContent(
      "common.unavailable",
    );
  });

  it("renders public-sector containment in Governance", async () => {
    renderRoute(
      "/runs/run-1/governance",
      "/runs/:runId/:tab",
      <GovernanceTab />,
    );

    expect(
      await screen.findByTestId("public-sector-readiness-panel"),
    ).toHaveTextContent("unavailable");
  });

  it("persists locally added dispute objections across governance remounts", async () => {
    const rendered = renderRoute(
      "/runs/run-1/governance",
      "/runs/:runId/:tab",
      <GovernanceTab />,
    );

    await userEvent.type(
      await screen.findByLabelText("phase32.disputes.titleLabel"),
      "Reviewer objection",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "phase32.disputes.add" }),
    );

    expect(screen.getByTestId("dispute-registry-panel")).toHaveTextContent(
      "Reviewer objection",
    );

    rendered.unmount();
    renderRoute(
      "/runs/run-1/governance",
      "/runs/:runId/:tab",
      <GovernanceTab />,
    );

    expect(
      await screen.findByTestId("dispute-registry-panel"),
    ).toHaveTextContent("Reviewer objection");
  });
});
