import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";

import { renderRouteWithProviders } from "@/test/routes";

const {
  markUiMilestoneMock,
  measureUiLatencyMock,
  useCapabilitiesMock,
  useConnectorsMock,
  useDataIndexStatsMock,
  useDataPromotionCandidatesMock,
  useRunEvidenceContextMock,
  useSourceProfilesMock,
} = vi.hoisted(() => ({
  markUiMilestoneMock: vi.fn(),
  measureUiLatencyMock: vi.fn(),
  useCapabilitiesMock: vi.fn(),
  useConnectorsMock: vi.fn(),
  useDataIndexStatsMock: vi.fn(),
  useDataPromotionCandidatesMock: vi.fn(),
  useRunEvidenceContextMock: vi.fn(),
  useSourceProfilesMock: vi.fn(),
}));

vi.mock("@/api/hooks/useCapabilities", () => ({
  useCapabilities: (...args: unknown[]) => useCapabilitiesMock(...args),
}));

vi.mock("@/api/hooks/useConnectors", () => ({
  useConnectors: (...args: unknown[]) => useConnectorsMock(...args),
}));

vi.mock("@/api/hooks/useDataIndexStats", () => ({
  useDataIndexStats: (...args: unknown[]) => useDataIndexStatsMock(...args),
}));

vi.mock("@/api/hooks/useDataPromotionCandidates", () => ({
  useDataPromotionCandidates: (...args: unknown[]) =>
    useDataPromotionCandidatesMock(...args),
}));

vi.mock("@/api/hooks/useRunEvidenceContext", () => ({
  useRunEvidenceContext: (...args: unknown[]) =>
    useRunEvidenceContextMock(...args),
}));

vi.mock("@/api/hooks/useSourceProfiles", () => ({
  useSourceProfiles: (...args: unknown[]) => useSourceProfilesMock(...args),
}));

vi.mock("@/features/evidence/components/DataIntelligencePanel", () => ({
  __esModule: true,
  default: ({
    degradedMessages,
    focus,
    mode,
  }: {
    degradedMessages: string[];
    focus: string;
    mode: string;
  }) => (
    <div data-testid="data-intelligence-panel">
      {mode}:{focus}:{degradedMessages.join("|")}
    </div>
  ),
}));

vi.mock("@/lib/domain/evidence", () => ({
  findRunEvidenceNeed: (
    context: { dataNeeds?: Array<{ needId: string }> } | null,
    needId: string | null,
  ) => context?.dataNeeds?.find((item) => item.needId === needId) ?? null,
  findRunEvidencePlan: (
    context: { fetchPlans?: Array<{ planId: string }> } | null,
    planId: string | null,
  ) => context?.fetchPlans?.find((item) => item.planId === planId) ?? null,
  findRunEvidencePromotion: (
    context: { promotionCandidates?: Array<{ promotionId: string }> } | null,
    promotionId: string | null,
  ) =>
    context?.promotionCandidates?.find(
      (item) => item.promotionId === promotionId,
    ) ?? null,
  normalizeRunEvidenceContext: (context: unknown) => context,
  resolveDefaultEvidenceFocus: () => "overview",
}));

vi.mock("@/shared/telemetry/performance", () => ({
  markUiMilestone: (...args: unknown[]) => markUiMilestoneMock(...args),
  measureUiLatency: (...args: unknown[]) => measureUiLatencyMock(...args),
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

import EvidenceFabricPage from "@/features/evidence/routes/EvidenceFabricPage";

function LocationProbe() {
  const location = useLocation();

  return (
    <div data-testid="location">
      {location.pathname}
      {location.search}
    </div>
  );
}

function renderEvidencePage(initialEntry = "/evidence") {
  return renderRouteWithProviders({
    element: (
      <>
        <EvidenceFabricPage />
        <LocationProbe />
      </>
    ),
    path: "/evidence",
    initialEntry,
  });
}

describe("EvidenceFabricPage", () => {
  beforeEach(() => {
    markUiMilestoneMock.mockReset();
    measureUiLatencyMock.mockReset();
    useCapabilitiesMock.mockReset();
    useCapabilitiesMock.mockReturnValue({
      data: {
        features: [
          {
            category: "evidence",
            enabled: true,
            key: "profiles",
            label: "Profiles",
          },
        ],
      },
    });
    useConnectorsMock.mockReset();
    useConnectorsMock.mockReturnValue({
      data: {
        connectors: [
          {
            connector_id: "world-bank",
            last_health_check: "2026-03-10T08:00:00Z",
            loaded: true,
          },
        ],
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    useDataIndexStatsMock.mockReset();
    useDataIndexStatsMock.mockReturnValue({
      data: {
        stats: {
          docs_added_last_run: 8,
          index_docs_total: 42,
        },
      },
    });
    useDataPromotionCandidatesMock.mockReset();
    useDataPromotionCandidatesMock.mockReturnValue({
      data: {
        candidates: [
          {
            confidence: 0.82,
            connector_id: "world-bank",
            created_at: null,
            dataset_id: "inflation",
            metadata: {},
            metric_id: "CPI",
            profile_id: "profile-1",
            promotion_id: "promotion-1",
            signals: [],
            source_lane: "fastlane",
            status: "pending",
          },
        ],
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    useRunEvidenceContextMock.mockReset();
    useRunEvidenceContextMock.mockReturnValue({
      data: undefined,
      error: null,
      isError: false,
      isLoading: false,
    });
    useSourceProfilesMock.mockReset();
    useSourceProfilesMock.mockReturnValue({
      data: {
        profiles: [
          {
            connector_available: true,
            connector_family: "warehouse",
            description: "Inflation feed",
            display_name: "World Bank CPI",
            estimated_datasets: 4,
            profile_id: "profile-1",
            source_organization: "World Bank",
          },
        ],
      },
      error: null,
      isError: false,
      isLoading: false,
    });
  });

  it("renders the workspace evidence overview", () => {
    renderEvidencePage();

    expect(screen.getByTestId("evidence-page")).toBeInTheDocument();
    expect(screen.getByText("pages.evidence.heroTitle")).toBeInTheDocument();
    expect(screen.getByText("workspace:overview:")).toBeInTheDocument();
    expect(screen.getAllByText("World Bank CPI")).not.toHaveLength(0);
    expect(screen.getAllByText("CPI")).not.toHaveLength(0);
    expect(markUiMilestoneMock).toHaveBeenCalledWith(
      "evidence.workspace.insight.ready",
      expect.any(Object),
    );
  });

  it("surfaces degraded run-context selectors and clears query params", async () => {
    const user = userEvent.setup();

    useRunEvidenceContextMock.mockReturnValueOnce({
      data: {
        context: {
          dataNeeds: [],
          executionPlanRef: null,
          evidenceBundleRef: null,
          fetchPlans: [],
          inputBindingsRef: null,
          promotionCandidates: [],
          relatedArtifacts: [],
          warnings: [],
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });

    renderEvidencePage(
      "/evidence?runId=run-1&focus=need&needId=missing-need&artifactId=missing-artifact",
    );

    expect(
      screen.getByText(
        'context:need:pages.evidence.degraded.needMissing:{"needId":"missing-need"}|pages.evidence.degraded.artifactMissing:{"artifactId":"missing-artifact"}',
      ),
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "pages.evidence.clearContext" }),
    );

    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent("/evidence"),
    );
  });
});
