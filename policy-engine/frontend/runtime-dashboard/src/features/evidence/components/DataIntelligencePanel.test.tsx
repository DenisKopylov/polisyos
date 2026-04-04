import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { renderWithProviders } from "@/test/render";

const {
  approveMock,
  usePermissionMock,
  useReviewCollaborationEnabledMock,
  useReviewCollaborationSurfaceMock,
  discoverMutateMock,
  previewMutateMock,
  rejectMock,
  resolveMutateMock,
  useDataCatalogSearchMock,
  useDataIndexStatsMock,
  useDataPromotionCandidatesMock,
  useDiscoverDataSourcesMock,
  usePreviewFetchPlanMock,
  useQueuedPromotionDecisionMock,
  useResolveDataNeedsMock,
} = vi.hoisted(() => ({
  approveMock: vi.fn(),
  usePermissionMock: vi.fn(),
  useReviewCollaborationEnabledMock: vi.fn(),
  useReviewCollaborationSurfaceMock: vi.fn(),
  discoverMutateMock: vi.fn(),
  previewMutateMock: vi.fn(),
  rejectMock: vi.fn(),
  resolveMutateMock: vi.fn(),
  useDataCatalogSearchMock: vi.fn(),
  useDataIndexStatsMock: vi.fn(),
  useDataPromotionCandidatesMock: vi.fn(),
  useDiscoverDataSourcesMock: vi.fn(),
  usePreviewFetchPlanMock: vi.fn(),
  useQueuedPromotionDecisionMock: vi.fn(),
  useResolveDataNeedsMock: vi.fn(),
}));

vi.mock("@/api/hooks/useDataCatalogSearch", () => ({
  useDataCatalogSearch: (...args: unknown[]) =>
    useDataCatalogSearchMock(...args),
}));

vi.mock("@/api/hooks/useDataIndexStats", () => ({
  useDataIndexStats: (...args: unknown[]) => useDataIndexStatsMock(...args),
}));

vi.mock("@/api/hooks/useDataPromotionCandidates", () => ({
  useDataPromotionCandidates: (...args: unknown[]) =>
    useDataPromotionCandidatesMock(...args),
}));

vi.mock("@/api/hooks/useDiscoverDataSources", () => ({
  useDiscoverDataSources: (...args: unknown[]) =>
    useDiscoverDataSourcesMock(...args),
}));

vi.mock("@/api/hooks/usePreviewFetchPlan", () => ({
  usePreviewFetchPlan: (...args: unknown[]) => usePreviewFetchPlanMock(...args),
}));

vi.mock("@/api/hooks/useResolveDataNeeds", () => ({
  useResolveDataNeeds: (...args: unknown[]) => useResolveDataNeedsMock(...args),
}));

vi.mock("@/features/evidence/hooks/useQueuedPromotionDecision", () => ({
  useQueuedPromotionDecision: (...args: unknown[]) =>
    useQueuedPromotionDecisionMock(...args),
}));

vi.mock("@/app/authz/AuthzProvider", async () => {
  const actual = await vi.importActual<
    typeof import("@/app/authz/AuthzProvider")
  >("@/app/authz/AuthzProvider");
  return {
    ...actual,
    usePermission: (...args: unknown[]) => usePermissionMock(...args),
    useReviewCollaborationEnabled: (...args: unknown[]) =>
      useReviewCollaborationEnabledMock(...args),
  };
});

vi.mock("@/app/realtime/useReviewCollaborationSurface", () => ({
  useReviewCollaborationSurface: (...args: unknown[]) =>
    useReviewCollaborationSurfaceMock(...args),
}));

vi.mock("@/i18n/LocaleProvider", async () => {
  const actual = await vi.importActual<typeof import("@/i18n/LocaleProvider")>(
    "@/i18n/LocaleProvider",
  );
  return {
    ...actual,
    useI18n: () => ({
      label: (
        _namespace: string,
        value: string | null | undefined,
        fallback: string,
      ) => fallback ?? value ?? "",
      t: (key: string, payload?: Record<string, unknown>) =>
        payload ? `${key}:${JSON.stringify(payload)}` : key,
    }),
  };
});

import DataIntelligencePanel from "@/features/evidence/components/DataIntelligencePanel";

describe("DataIntelligencePanel", () => {
  beforeEach(() => {
    approveMock.mockReset();
    usePermissionMock.mockReset();
    useReviewCollaborationEnabledMock.mockReset();
    useReviewCollaborationSurfaceMock.mockReset();
    discoverMutateMock.mockReset();
    previewMutateMock.mockReset();
    rejectMock.mockReset();
    resolveMutateMock.mockReset();
    useDataCatalogSearchMock.mockReset();
    useDataIndexStatsMock.mockReset();
    useDataPromotionCandidatesMock.mockReset();
    useDiscoverDataSourcesMock.mockReset();
    usePreviewFetchPlanMock.mockReset();
    useQueuedPromotionDecisionMock.mockReset();
    useResolveDataNeedsMock.mockReset();
    usePermissionMock.mockReturnValue(true);
    useReviewCollaborationEnabledMock.mockReturnValue(false);
    useReviewCollaborationSurfaceMock.mockReturnValue({
      cursors: [],
      isLockedByAnother: false,
      lock: null,
      participants: [],
      status: "idle",
    });

    useDataCatalogSearchMock.mockImplementation(
      ({ metricQuery }: { metricQuery: string }) => ({
        data: metricQuery.trim()
          ? {
              matches: [
                {
                  candidate_id: "catalog-1",
                  confidence: 0.88,
                  connector_id: "world-bank",
                  dataset_id: "inflation",
                  metric_id: metricQuery,
                  source_lane: "fastlane",
                },
              ],
              query: metricQuery,
              total_matches: 1,
            }
          : null,
        error: null,
        isLoading: false,
      }),
    );
    useDataIndexStatsMock.mockReturnValue({
      data: {
        stats: {
          docs_added_last_run: 4,
          index_docs_total: 42,
          index_size_bytes: 2_048,
          indexed_sources: 3,
        },
      },
      error: null,
      isLoading: false,
    });
    useDataPromotionCandidatesMock.mockReturnValue({
      data: {
        candidates: [
          {
            confidence: 0.82,
            connector_id: "world-bank",
            created_at: "2026-03-10T10:00:00Z",
            dataset_id: "inflation",
            metric_id: "inflation",
            promotion_id: "promotion-1",
            source_lane: "fastlane",
            status: "pending",
          },
        ],
      },
      error: null,
      isLoading: false,
    });
    useResolveDataNeedsMock.mockReturnValue({
      data: {
        candidates: [],
        fetch_plans: [
          {
            connector_id: "world-bank",
            dataset_id: "inflation",
            fallbacks: [],
            metric_id: "inflation",
            plan_id: "plan-1",
            quality_min: 0.8,
            source_lane: "fastlane",
          },
        ],
        warnings: ["Review source freshness"],
      },
      error: null,
      isPending: false,
      mutate: resolveMutateMock,
    });
    useDiscoverDataSourcesMock.mockReturnValue({
      data: {
        candidates: [
          {
            candidate_id: "discover-1",
            confidence: 0.77,
            connector_id: "world-bank",
            dataset_id: "inflation",
            metric_id: "inflation",
          },
        ],
        docs_fetched_total: 6,
      },
      error: null,
      isPending: false,
      mutate: discoverMutateMock,
    });
    usePreviewFetchPlanMock.mockReturnValue({
      data: {
        preview: {
          completeness: 0.91,
          coverage_ok: true,
          row_count: 12,
          status: "ok",
        },
      },
      isPending: false,
      mutate: previewMutateMock,
    });
    useQueuedPromotionDecisionMock.mockReturnValue({
      approve: approveMock,
      approveError: null,
      isDecisionPending: () => false,
      queuedStateByPromotionId: new Map(),
      reject: rejectMock,
      rejectError: null,
    });
  });

  it("renders workspace intelligence controls and dispatches resolve, discover, preview, and promotion actions", async () => {
    const user = userEvent.setup();
    renderWithProviders(<DataIntelligencePanel />, {
      interactiveProviders: true,
    });

    await user.type(
      screen.getByLabelText("panels.dataIntelligence.metric"),
      "inflation",
    );
    await user.type(
      screen.getByLabelText("panels.dataIntelligence.geography"),
      "USA",
    );
    await user.clear(
      screen.getByLabelText("panels.dataIntelligence.timeStart"),
    );
    await user.type(
      screen.getByLabelText("panels.dataIntelligence.timeStart"),
      "2015",
    );
    await user.selectOptions(
      screen.getByLabelText("panels.dataIntelligence.granularity"),
      "monthly",
    );
    await user.selectOptions(
      screen.getByLabelText("panels.dataIntelligence.retrievalMode"),
      "fastlane",
    );

    await user.click(screen.getByTestId("evidence-resolve"));
    await user.click(screen.getByTestId("evidence-discover"));
    await user.click(
      screen.getByRole("button", { name: "panels.dataIntelligence.preview" }),
    );

    await user.type(
      screen.getByLabelText("panels.dataIntelligence.decisionReason"),
      "Promote the strongest evidence",
    );
    await user.click(screen.getByTestId("promotion-approve-promotion-1"));
    const approveDialog = screen.getByRole("alertdialog");
    await user.click(
      within(approveDialog).getByRole("button", {
        name: "panels.dataIntelligence.approve",
      }),
    );
    await user.click(screen.getByTestId("promotion-reject-promotion-1"));
    const rejectDialog = screen.getByRole("alertdialog");
    await user.click(
      within(rejectDialog).getByRole("button", {
        name: "panels.dataIntelligence.reject",
      }),
    );

    expect(resolveMutateMock).toHaveBeenCalledWith({
      allow_explore_fallback: true,
      data_needs: [
        expect.objectContaining({
          geography: "USA",
          granularity: "monthly",
          metric: "inflation",
          purpose: "data_intelligence_ui",
          time_start: "2015",
        }),
      ],
      mode: "fastlane",
    });
    expect(discoverMutateMock).toHaveBeenCalledWith({
      cost_budget_usd: 0,
      data_needs: [
        expect.objectContaining({
          metric: "inflation",
        }),
      ],
      max_candidates_total: 50,
      max_discovery_calls_per_source: 25,
      max_sources_per_query: 5,
      time_budget_ms: 5000,
    });
    expect(previewMutateMock).toHaveBeenCalledWith({
      allow_fallback: true,
      fetch_plan: expect.objectContaining({
        connector_id: "world-bank",
        dataset_id: "inflation",
        metric_id: "inflation",
        plan_id: "plan-1",
      }),
    });
    expect(approveMock).toHaveBeenCalledWith(
      {
        promotionId: "promotion-1",
        reason: "Promote the strongest evidence",
      },
      expect.any(Object),
    );
    expect(rejectMock).toHaveBeenCalledWith(
      {
        promotionId: "promotion-1",
        reason: "Promote the strongest evidence",
      },
      expect.any(Object),
    );
    expect(screen.getByText("Review source freshness")).toBeInTheDocument();
    expect(screen.getAllByText(/world-bank/).length).toBeGreaterThan(0);
  }, 15_000);

  it("hydrates context mode from selected run surfaces and auto-previews the selected plan", async () => {
    const onResetContext = vi.fn();
    const user = userEvent.setup();
    const selectedPlan = {
      connectorId: "world-bank",
      datasetId: "inflation",
      dateEnd: "2024",
      dateStart: "2010",
      filters: {},
      granularity: "annual",
      matchedPlanId: null,
      metricId: "inflation",
      planId: "plan-ctx",
      profileId: "profile-1",
      qualityMin: 0.75,
      sourceLane: "fastlane",
    };

    renderWithProviders(
      <DataIntelligencePanel
        mode="context"
        runId="run-77"
        focus="plan"
        runContext={
          {
            dataNeeds: [
              {
                geography: "USA",
                granularity: "annual",
                metric: "inflation",
                needId: "need-1",
                notes: [],
                qualityMin: 0.7,
                timeEnd: "2024",
                timeStart: "2010",
              },
            ],
            fetchPlans: [selectedPlan],
            promotionCandidates: [
              {
                confidence: 0.82,
                connectorId: "world-bank",
                createdAt: "2026-03-10T10:00:00Z",
                datasetId: "inflation",
                matchedPlanId: "plan-ctx",
                metadata: {},
                metricId: "inflation",
                profileId: "profile-1",
                promotionId: "promotion-ctx",
                signals: [],
                sourceLane: "fastlane",
                status: "pending",
              },
            ],
          } as never
        }
        selectedNeed={
          {
            geography: "USA",
            granularity: "annual",
            metric: "inflation",
            needId: "need-1",
            notes: [],
            qualityMin: 0.7,
            timeEnd: "2024",
            timeStart: "2010",
          } as never
        }
        selectedPlan={selectedPlan as never}
        selectedPromotion={
          {
            confidence: 0.82,
            connectorId: "world-bank",
            createdAt: "2026-03-10T10:00:00Z",
            datasetId: "inflation",
            matchedPlanId: "plan-ctx",
            metadata: {},
            metricId: "inflation",
            profileId: "profile-1",
            promotionId: "promotion-ctx",
            signals: [],
            sourceLane: "fastlane",
            status: "pending",
          } as never
        }
        selectedArtifact={
          { artifact_id: "artifact-ctx", kind: "report" } as never
        }
        degradedMessages={["Missing artifact lineage"]}
        onResetContext={onResetContext}
      />,
      { interactiveProviders: true },
    );

    await waitFor(() => {
      expect(previewMutateMock).toHaveBeenCalledWith({
        allow_fallback: true,
        fetch_plan: expect.objectContaining({
          connector_id: "world-bank",
          dataset_id: "inflation",
          metric_id: "inflation",
          plan_id: "plan-ctx",
        }),
      });
    });

    expect(screen.getByText(/run-77/)).toBeInTheDocument();
    expect(screen.getByText(/Missing artifact lineage/)).toBeInTheDocument();
    expect(screen.getByDisplayValue("inflation")).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", {
        name: "panels.dataIntelligence.clearRunContext",
      }),
    );

    expect(onResetContext).toHaveBeenCalled();
  });

  it("disables promotion decisions when another reviewer holds the active lease", () => {
    useReviewCollaborationEnabledMock.mockReturnValue(true);
    useReviewCollaborationSurfaceMock.mockReturnValue({
      cursors: [],
      isLockedByAnother: true,
      lock: {
        accentColor: "#2557a7",
        acquiredAt: "2026-03-10T10:00:00Z",
        displayName: "Reviewer Bob",
        expiresAt: "2026-03-10T10:05:00Z",
        isSelf: false,
        participantId: "reviewer-bob",
      },
      participants: [
        {
          accentColor: "#2557a7",
          displayName: "Reviewer Bob",
          isSelf: false,
          lastSeenAt: "2026-03-10T10:00:00Z",
          participantId: "reviewer-bob",
          sessionCount: 1,
        },
      ],
      status: "live",
    });

    renderWithProviders(
      <DataIntelligencePanel
        mode="context"
        runId="R_core_api_001"
        runContext={{
          runId: "R_core_api_001",
          sourceKind: "runtime.run_evidence_context",
          dataNeeds: [],
          executionPlanRef: null,
          evidenceBundleRef: null,
          fetchPlans: [],
          inputBindingsRef: null,
          promotionCandidates: [
            {
              confidence: 0.82,
              connectorId: "world-bank",
              createdAt: "2026-03-10T10:00:00Z",
              datasetId: "inflation",
              matchedPlanId: null,
              metadata: {},
              metricId: "inflation",
              profileId: null,
              promotionId: "promotion-1",
              signals: [],
              sourceLane: "fastlane",
              status: "pending",
            },
          ],
          relatedArtifacts: [],
          warnings: [],
          dataSnapshotRef: null,
        }}
        selectedPromotion={{
          confidence: 0.82,
          connectorId: "world-bank",
          createdAt: "2026-03-10T10:00:00Z",
          datasetId: "inflation",
          matchedPlanId: null,
          metadata: {},
          metricId: "inflation",
          profileId: null,
          promotionId: "promotion-1",
          signals: [],
          sourceLane: "fastlane",
          status: "pending",
        }}
      />,
      { interactiveProviders: true },
    );

    expect(
      screen.getByText(
        'panels.reviewCollaboration.activeTarget:{"target":"inflation"}',
      ),
    ).toBeInTheDocument();
    expect(screen.getByTestId("promotion-approve-promotion-1")).toBeDisabled();
    expect(screen.getByTestId("promotion-reject-promotion-1")).toBeDisabled();
    expect(
      screen.getByText(
        'panels.reviewCollaboration.lockedBy:{"name":"Reviewer Bob"}',
      ),
    ).toBeInTheDocument();
  });
});
