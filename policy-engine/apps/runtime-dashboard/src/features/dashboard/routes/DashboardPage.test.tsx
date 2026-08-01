import type { PropsWithChildren, ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const {
  useLexGraphStatsMock,
  useSuspenseCapabilitiesMock,
  useSuspenseDataIndexStatsMock,
  useSuspenseDataPromotionCandidatesMock,
  useSuspenseHealthMock,
  useSuspenseRunsSampleMock,
} = vi.hoisted(() => ({
  useLexGraphStatsMock: vi.fn(),
  useSuspenseCapabilitiesMock: vi.fn(),
  useSuspenseDataIndexStatsMock: vi.fn(),
  useSuspenseDataPromotionCandidatesMock: vi.fn(),
  useSuspenseHealthMock: vi.fn(),
  useSuspenseRunsSampleMock: vi.fn(),
}));

vi.mock("recharts", () => {
  function Stub({
    children,
    ...props
  }: PropsWithChildren<Record<string, unknown>>) {
    return <div data-props={JSON.stringify(props)}>{children}</div>;
  }

  return {
    Bar: Stub,
    BarChart: Stub,
    CartesianGrid: Stub,
    Line: Stub,
    LineChart: Stub,
    ResponsiveContainer: Stub,
    Tooltip: Stub,
    XAxis: Stub,
    YAxis: Stub,
  };
});

vi.mock("@/app/routes/PrefetchLink", () => ({
  PrefetchLink: ({
    children,
    to,
    ...props
  }: PropsWithChildren<{ to: string }>) => (
    <a href={to} {...props}>
      {children}
    </a>
  ),
}));

vi.mock("@/shared/components/FeatureAsyncBoundary", () => ({
  FeatureAsyncBoundary: ({ children }: { children: ReactNode }) => children,
}));

vi.mock("@/api/hooks/useCapabilities", () => ({
  useSuspenseCapabilities: (...args: unknown[]) =>
    useSuspenseCapabilitiesMock(...args),
}));

vi.mock("@/api/hooks/useDataIndexStats", () => ({
  useSuspenseDataIndexStats: (...args: unknown[]) =>
    useSuspenseDataIndexStatsMock(...args),
}));

vi.mock("@/api/hooks/useDataPromotionCandidates", () => ({
  useSuspenseDataPromotionCandidates: (...args: unknown[]) =>
    useSuspenseDataPromotionCandidatesMock(...args),
}));

vi.mock("@/api/hooks/useHealth", () => ({
  useSuspenseHealth: (...args: unknown[]) => useSuspenseHealthMock(...args),
}));

vi.mock("@/api/hooks/useLexGraphStats", () => ({
  useLexGraphStats: (...args: unknown[]) => useLexGraphStatsMock(...args),
}));

vi.mock("@/features/runs", async () => {
  const actual = await vi.importActual("@/features/runs");
  return {
    ...actual,
    useSuspenseRunsSample: (...args: unknown[]) =>
      useSuspenseRunsSampleMock(...args),
  };
});

vi.mock("@/shared/i18n/LocaleProvider", async () => {
  const actual = await vi.importActual<typeof import("@/shared/i18n/LocaleProvider")>(
    "@/shared/i18n/LocaleProvider",
  );
  return {
    ...actual,
    useI18n: () => ({
      t: (key: string, payload?: Record<string, unknown>) =>
        payload ? `${key}:${JSON.stringify(payload)}` : key,
    }),
  };
});

import DashboardPage from "@/features/dashboard/routes/DashboardPage";

function renderDashboard() {
  return render(
    <MemoryRouter>
      <DashboardPage />
    </MemoryRouter>,
  );
}

describe("DashboardPage", () => {
  beforeEach(() => {
    useSuspenseCapabilitiesMock.mockReset();
    useSuspenseCapabilitiesMock.mockReturnValue({
      data: {
        features: [{ enabled: true, key: "lex_pipeline", label: "Lex ready" }],
      },
    });
    useSuspenseDataIndexStatsMock.mockReset();
    useSuspenseDataIndexStatsMock.mockReturnValue({
      data: {
        stats: {
          docs_added_last_run: 12,
          index_docs_total: 120,
          source_coverage: {
            world_bank: 12,
            imf: 5,
          },
        },
      },
    });
    useSuspenseDataPromotionCandidatesMock.mockReset();
    useSuspenseDataPromotionCandidatesMock.mockReturnValue({
      data: {
        candidates: [
          {
            confidence: 0.91,
            connector_id: "world-bank",
            dataset_id: "inflation",
            metric_id: "CPI",
            promotion_id: "promotion-1",
            source_lane: "fastlane",
            status: "pending",
          },
        ],
      },
    });
    useSuspenseHealthMock.mockReset();
    useSuspenseHealthMock.mockReturnValue({
      data: { status: "ok" },
    });
    useLexGraphStatsMock.mockReset();
    useLexGraphStatsMock.mockReturnValue({
      data: {
        db_exists: true,
      },
    });
    useSuspenseRunsSampleMock.mockReset();
    useSuspenseRunsSampleMock.mockReturnValue({
      data: {
        runs: [
          {
            duration_ms: 1_000,
            root_artifact_count: 2,
            run_id: "run-001",
            status: "running",
          },
          {
            duration_ms: 2_500,
            root_artifact_count: 1,
            run_id: "run-002",
            status: "completed",
          },
          {
            duration_ms: 1_700,
            root_artifact_count: 0,
            run_id: "run-003",
            status: "blocked_preflight",
          },
        ],
      },
    });
  });

  it("renders dashboard metrics, queues, charts, and promotion shortcuts", () => {
    renderDashboard();

    expect(screen.getByTestId("dashboard-page")).toBeInTheDocument();
    expect(screen.getByText("pages.dashboard.heroTitle")).toBeInTheDocument();
    expect(screen.getByText("pages.dashboard.graphReady")).toBeInTheDocument();
    expect(
      screen.getByText("pages.dashboard.narrativeHeading"),
    ).toBeInTheDocument();
    expect(screen.getByText("run-001")).toBeInTheDocument();
    expect(screen.getByText("pages.dashboard.blockedRuns")).toBeInTheDocument();
    expect(screen.getByText("world bank")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /CPI/ })).toHaveAttribute(
      "href",
      "/evidence?focus=promotion&promotionId=promotion-1",
    );
  });

  it("preserves an unseen run label byte-for-byte with neutral clothing and unavailable derived counts", () => {
    useSuspenseRunsSampleMock.mockReturnValue({
      data: {
        runs: [
          {
            duration_ms: 1_000,
            root_artifact_count: 2,
            run_id: "run-opaque",
            status: "awaiting_external_attestation",
          },
        ],
      },
    });

    renderDashboard();

    const ownerLabel = screen.getByText("awaiting_external_attestation");
    expect(ownerLabel).toHaveClass("bg-white/65", "text-muted");
    expect(screen.getAllByText("common.unavailable").length).toBeGreaterThanOrEqual(
      3,
    );
  });

  it("renders an open health label neutrally without minting authority clothing", () => {
    useSuspenseHealthMock.mockReturnValue({
      data: { status: "degraded_future" },
    });

    renderDashboard();

    expect(
      screen.getByText(
        'pages.dashboard.healthStatus:{"status":"degraded_future"}',
      ),
    ).toHaveClass("bg-white/65", "text-muted");
  });

  it("renders empty states when queue, charts, coverage, and promotions are unavailable", () => {
    useSuspenseDataIndexStatsMock.mockReturnValue({
      data: {
        stats: {
          docs_added_last_run: 0,
          index_docs_total: 0,
          source_coverage: {},
        },
      },
    });
    useSuspenseDataPromotionCandidatesMock.mockReturnValue({
      data: { candidates: [] },
    });
    useSuspenseRunsSampleMock.mockReturnValue({
      data: {
        runs: [],
      },
    });
    useLexGraphStatsMock.mockReturnValue({
      data: {
        db_exists: false,
      },
    });

    renderDashboard();

    expect(
      screen.getByText("pages.dashboard.queueEmptyTitle"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("pages.dashboard.statusChartEmptyTitle"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("pages.dashboard.trendEmptyTitle"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("pages.dashboard.coverageEmptyTitle"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("pages.dashboard.promotionsEmptyTitle"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("pages.dashboard.graphPending"),
    ).toBeInTheDocument();
  });
});
