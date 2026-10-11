import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";

import { evidenceArtifactRefKey } from "@/features/evidence/domain/context";
import { renderRouteWithProviders } from "@/test/routes";

const {
  markUiMilestoneMock,
  measureUiLatencyMock,
  useConnectorsMock,
  useDataIndexStatsMock,
  useDataPromotionCandidatesMock,
  useRunEvidenceContextMock,
  useSourceProfilesMock,
} = vi.hoisted(() => ({
  markUiMilestoneMock: vi.fn(),
  measureUiLatencyMock: vi.fn(),
  useConnectorsMock: vi.fn(),
  useDataIndexStatsMock: vi.fn(),
  useDataPromotionCandidatesMock: vi.fn(),
  useRunEvidenceContextMock: vi.fn(),
  useSourceProfilesMock: vi.fn(),
}));

vi.mock("@/features/evidence/components/CapabilityDiscoveryPanel", () => ({
  CapabilityDiscoveryPanel: ({
    request,
  }: {
    request: { search: { query_text: string } };
  }) => (
    <div data-testid="capability-discovery-request">
      {request.search.query_text}
    </div>
  ),
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
    selectedArtifact,
  }: {
    degradedMessages: string[];
    focus: string;
    mode: string;
    selectedArtifact?: {
      artifact_id: string;
      kind?: string | null;
      media_type?: string | null;
      manifest_profile_sha256?: string | null;
    } | null;
  }) => (
    <div data-testid="data-intelligence-panel">
      {mode}:{focus}:{degradedMessages.join("|")}
      <span data-testid="selected-artifact-profile">
        {selectedArtifact?.manifest_profile_sha256 ?? "none"}
      </span>
      <span data-testid="selected-artifact-kind">
        {selectedArtifact?.kind ?? "none"}
      </span>
      <span data-testid="selected-artifact-media-type">
        {selectedArtifact?.media_type ?? "none"}
      </span>
    </div>
  ),
}));

vi.mock("@/shared/lib/domain/evidence", async () => {
  const actual = await vi.importActual<
    typeof import("@/shared/lib/domain/evidence")
  >("@/shared/lib/domain/evidence");

  return {
    ...actual,
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
  };
});

vi.mock("@/shared/telemetry/performance", () => ({
  markUiMilestone: (...args: unknown[]) => markUiMilestoneMock(...args),
  measureUiLatency: (...args: unknown[]) => measureUiLatencyMock(...args),
}));

vi.mock("@/shared/i18n/LocaleProvider", async () => {
  const actual = await vi.importActual<
    typeof import("@/shared/i18n/LocaleProvider")
  >("@/shared/i18n/LocaleProvider");
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

  it("binds a palette-selected capability ref into the real discovery request", () => {
    renderEvidencePage(
      "/evidence?capability=capability%3Agenerated%3Aowner-row",
    );

    expect(
      screen.getByTestId("capability-discovery-request"),
    ).toHaveTextContent("capability:generated:owner-row");
  });

  it("does not render impossible authored manifest feature rows", () => {
    renderEvidencePage();

    expect(screen.queryByText("Profiles")).not.toBeInTheDocument();
  });

  it("renders the workspace evidence overview", () => {
    renderEvidencePage();

    expect(screen.getByTestId("evidence-page")).toBeInTheDocument();
    const metricStrip = screen.getByTestId("evidence-metric-strip");
    expect(metricStrip).toBeInTheDocument();
    expect(screen.getByText("pages.evidence.heroTitle")).toBeInTheDocument();
    expect(
      within(metricStrip).getByText("pages.evidence.connectors"),
    ).toBeInTheDocument();
    expect(
      within(metricStrip).getByText("common.confidence"),
    ).toBeInTheDocument();
    expect(screen.getByText("workspace:overview:")).toBeInTheDocument();
    expect(screen.getByTestId("freshness-braid-panel")).toHaveTextContent(
      "world-bank",
    );
    expect(screen.getAllByText("World Bank CPI")).not.toHaveLength(0);
    expect(screen.getAllByText("CPI")).not.toHaveLength(0);
    expect(markUiMilestoneMock).toHaveBeenCalledWith(
      "evidence.workspace.insight.ready",
      expect.any(Object),
    );
  });

  it("hard-coded copy cannot mint verified provenance", () => {
    renderEvidencePage();

    const strip = screen.getByTestId("provenance-strip");
    expect(
      within(strip).getByText("Live", { selector: "span" }),
    ).toBeInTheDocument();
    expect(within(strip).queryByLabelText("verified")).not.toBeInTheDocument();
    for (const item of within(strip).getAllByRole("listitem")) {
      expect(item).not.toHaveAttribute("data-intent");
    }
    for (const glyph of within(strip).getAllByRole("img")) {
      expect(glyph).not.toHaveAttribute("data-glyph-intent");
    }
  });

  it("switches the production slice between freshness braid and connector cards", async () => {
    const user = userEvent.setup();

    renderEvidencePage();

    await user.click(
      screen.getByRole("button", {
        name: "phase32.connectors.title",
      }),
    );

    expect(screen.getByTestId("connector-character-cards")).toHaveTextContent(
      "world-bank",
    );
    expect(screen.getByTestId("location")).toHaveTextContent(
      "surface=connector-cards",
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

  it("keeps same-blob profile refs separately selectable through the evidence view", async () => {
    const user = userEvent.setup();
    const profileA = `sha256:${"a".repeat(64)}`;
    const profileB = `sha256:${"b".repeat(64)}`;
    const refA = {
      artifact_id: "shared-blob",
      kind: "fabric.data_snapshot",
      media_type: "application/json",
      manifest_profile_sha256: profileA,
    };
    const refB = { ...refA, manifest_profile_sha256: profileB };
    useRunEvidenceContextMock.mockReturnValue({
      data: {
        context: {
          dataNeeds: [],
          dataSnapshotRef: refA,
          dataViewRequestRef: null,
          evidenceBundleRef: null,
          executionPlanRef: null,
          fetchPlans: [],
          inputBindingsRef: null,
          promotionCandidates: [],
          relatedArtifacts: [refB],
          runId: "run-profiled",
          warnings: [],
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });

    renderEvidencePage("/evidence?runId=run-profiled");

    const refKeyA = evidenceArtifactRefKey(refA);
    const refKeyB = evidenceArtifactRefKey(refB);
    const profileAButton = screen.getByTestId(
      `evidence-artifact-${encodeURIComponent(refKeyA)}`,
    );
    const profileBButton = screen.getByTestId(
      `evidence-artifact-${encodeURIComponent(refKeyB)}`,
    );
    expect(profileAButton).not.toBe(profileBButton);
    expect(profileAButton).toHaveTextContent(profileA);
    expect(profileBButton).toHaveTextContent(profileB);

    const expectSelectedProfile = (profile: string, refKey: string) => {
      expect(screen.getByTestId("selected-artifact-profile")).toHaveTextContent(
        profile,
      );
      const selectedRoute = new URL(
        screen.getByTestId("location").textContent ?? "",
        window.location.origin,
      );
      expect(selectedRoute.pathname).toBe("/evidence");
      expect(selectedRoute.searchParams.get("runId")).toBe("run-profiled");
      expect(selectedRoute.searchParams.get("focus")).toBe("artifact");
      expect(selectedRoute.searchParams.get("artifactId")).toBe("shared-blob");
      expect(selectedRoute.searchParams.get("artifactRefKey")).toBe(refKey);
    };

    await user.click(profileAButton);
    expectSelectedProfile(profileA, refKeyA);
    await user.click(profileBButton);
    expectSelectedProfile(profileB, refKeyB);

    const profileNavigation = screen.getByRole("link", {
      name: "Open evidence shared-blob",
    });
    expect(profileNavigation).toHaveAttribute(
      "data-evidence-ref",
      refA.artifact_id,
    );
    const profileNavigationRoute = new URL(
      profileNavigation.getAttribute("href") ?? "",
      window.location.origin,
    );
    expect(profileNavigationRoute.pathname).toBe("/evidence");
    expect(profileNavigationRoute.searchParams.get("runId")).toBe(
      "run-profiled",
    );
    expect(profileNavigationRoute.searchParams.get("focus")).toBe("artifact");
    expect(profileNavigationRoute.searchParams.get("artifactId")).toBe(
      refA.artifact_id,
    );
    expect(profileNavigationRoute.searchParams.get("artifactRefKey")).toBe(
      refKeyA,
    );
  });

  it("refuses an ID-only selector when multiple manifest profiles are present", () => {
    const profileA = `sha256:${"a".repeat(64)}`;
    const profileB = `sha256:${"b".repeat(64)}`;
    const refA = {
      artifact_id: "shared-blob",
      kind: "fabric.data_snapshot",
      media_type: "application/json",
      manifest_profile_sha256: profileA,
    };
    useRunEvidenceContextMock.mockReturnValueOnce({
      data: {
        context: {
          dataNeeds: [],
          dataSnapshotRef: refA,
          dataViewRequestRef: null,
          evidenceBundleRef: null,
          executionPlanRef: null,
          fetchPlans: [],
          inputBindingsRef: null,
          promotionCandidates: [],
          relatedArtifacts: [{ ...refA, manifest_profile_sha256: profileB }],
          runId: "run-profiled",
          warnings: [],
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });

    renderEvidencePage("/evidence?runId=run-profiled&artifactId=shared-blob");

    expect(screen.getByTestId("selected-artifact-profile")).toHaveTextContent(
      "none",
    );
    expect(screen.getByTestId("data-intelligence-panel")).toHaveTextContent(
      "artifactProfileAmbiguous",
    );
  });

  it("keeps same-ID same-profile refs with different kind or media selectable", async () => {
    const user = userEvent.setup();
    const profile = `sha256:${"a".repeat(64)}`;
    const jsonRef = {
      artifact_id: "shared-blob",
      kind: "fabric.data_snapshot",
      media_type: "application/json",
      manifest_profile_sha256: profile,
    };
    const textRef = {
      ...jsonRef,
      kind: "fabric.text_snapshot",
      media_type: "text/plain",
    };
    useRunEvidenceContextMock.mockReturnValue({
      data: {
        context: {
          dataNeeds: [],
          dataSnapshotRef: jsonRef,
          dataViewRequestRef: null,
          evidenceBundleRef: null,
          executionPlanRef: null,
          fetchPlans: [],
          inputBindingsRef: null,
          promotionCandidates: [],
          relatedArtifacts: [textRef],
          runId: "run-profiled",
          warnings: [],
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });

    renderEvidencePage("/evidence?runId=run-profiled");

    const jsonKey = evidenceArtifactRefKey(jsonRef);
    const textKey = evidenceArtifactRefKey(textRef);
    expect(
      screen.getByTestId(`evidence-artifact-${encodeURIComponent(jsonKey)}`),
    ).toBeInTheDocument();
    await user.click(
      screen.getByTestId(`evidence-artifact-${encodeURIComponent(textKey)}`),
    );
    expect(screen.getByTestId("selected-artifact-kind")).toHaveTextContent(
      "fabric.text_snapshot",
    );
    expect(
      screen.getByTestId("selected-artifact-media-type"),
    ).toHaveTextContent("text/plain");
  });

  it("refuses repeated full-ref selectors instead of selecting the last value", () => {
    const ref = {
      artifact_id: "shared-blob",
      kind: "fabric.data_snapshot",
      media_type: "application/json",
      manifest_profile_sha256: `sha256:${"a".repeat(64)}`,
    };
    useRunEvidenceContextMock.mockReturnValueOnce({
      data: {
        context: {
          dataNeeds: [],
          dataSnapshotRef: ref,
          dataViewRequestRef: null,
          evidenceBundleRef: null,
          executionPlanRef: null,
          fetchPlans: [],
          inputBindingsRef: null,
          promotionCandidates: [],
          relatedArtifacts: [],
          runId: "run-profiled",
          warnings: [],
        },
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    const key = evidenceArtifactRefKey(ref);

    renderEvidencePage(
      `/evidence?runId=run-profiled&artifactId=shared-blob&artifactRefKey=${encodeURIComponent(key)}&artifactRefKey=${encodeURIComponent(key)}`,
    );

    expect(screen.getByTestId("selected-artifact-profile")).toHaveTextContent(
      "none",
    );
    expect(screen.getByTestId("data-intelligence-panel")).toHaveTextContent(
      "artifactReferenceInvalid",
    );
  });
});
