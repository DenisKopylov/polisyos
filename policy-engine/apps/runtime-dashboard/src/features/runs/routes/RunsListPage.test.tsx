import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";

import { NetworkStatusProvider } from "@/shared/network";

const { useEpochStalenessMock, useRunsMock } = vi.hoisted(() => ({
  useEpochStalenessMock: vi.fn(),
  useRunsMock: vi.fn(),
}));

vi.mock("@/api/hooks/useRuns", () => ({
  useRuns: (...args: unknown[]) => useRunsMock(...args),
}));

vi.mock("@/features/runs/api/useEpochStaleness", () => ({
  useEpochStaleness: (...args: unknown[]) => useEpochStalenessMock(...args),
}));

vi.mock("@/app/providers/TelemetryProvider", () => ({
  useTelemetryReadyMark: vi.fn(),
}));

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useOptionalI18n: () => ({
    locale: "en",
    t: (path: string) => path,
  }),
  useI18n: () => ({
    label: (
      _mapName: string,
      value: string | null | undefined,
      fallback?: string,
    ) => fallback ?? value ?? "",
    locale: "en",
    t: (path: string, payload?: Record<string, unknown>) =>
      payload ? `${path}:${JSON.stringify(payload)}` : path,
  }),
}));

import RunsListPage from "@/features/runs/routes/RunsListPage";

function LocationProbe() {
  const location = useLocation();

  return (
    <div data-testid="location">
      {location.pathname}
      {location.search}
    </div>
  );
}

function renderRunsListPage(initialEntry = "/runs") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <NetworkStatusProvider>
        <Routes>
          <Route
            path="/runs"
            element={
              <>
                <RunsListPage />
                <LocationProbe />
              </>
            }
          />
          <Route path="/runs/:runId/overview" element={<div>Opened run</div>} />
        </Routes>
      </NetworkStatusProvider>
    </MemoryRouter>,
  );
}

describe("RunsListPage", () => {
  beforeEach(() => {
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: vi.fn(),
      writable: true,
    });
    useRunsMock.mockReset();
    useEpochStalenessMock.mockReset();
    useEpochStalenessMock.mockImplementation(
      ({ runId }: { runId: string }) => ({
        data: {
          projection: {
            current_epoch_ref: `sha256:${"a".repeat(64)}`,
            decision_validity_status: "active",
            owner_as_of: "2026-03-09T12:00:00Z",
            owner_time_reason: null,
            projection_semantic_hash: `sha256:${"b".repeat(64)}`,
            revalidation_required: false,
            run_id: runId,
            scoped_epoch_refs: [`sha256:${"a".repeat(64)}`],
            status: "current",
            temporal_scope: {
              tx_at: "2026-03-09T12:05:00Z",
              valid_at: "2026-03-09T12:00:00Z",
            },
          },
          rawBytes: new Uint8Array(),
        },
        error: null,
        isError: false,
        isLoading: false,
      }),
    );
    useRunsMock.mockImplementation((filters?: { q?: string }) => ({
      data: {
        page: {
          count: filters?.q === "missing" ? 0 : filters?.q === "policy" ? 1 : 2,
          cursor: null,
          limit: 50,
          next_cursor: filters?.q === "missing" ? null : "cursor-next",
          total: filters?.q === "missing" ? 0 : filters?.q === "policy" ? 1 : 2,
        },
        runs:
          filters?.q === "missing"
            ? []
            : filters?.q === "policy"
              ? [
                  {
                    cell_id: null,
                    duration_ms: 1400,
                    finished_at: null,
                    has_trace: true,
                    has_workflow_report: true,
                    root_artifact_count: 2,
                    run_id: "run-002",
                    run_terminality: "not_established",
                    source_kind: "policy",
                    started_at: new Date("2026-03-09T11:00:00Z").toISOString(),
                    status: "completed",
                    tenant_id: null,
                    warnings: [],
                  },
                ]
              : [
                  {
                    cell_id: null,
                    duration_ms: 1200,
                    finished_at: null,
                    has_trace: false,
                    has_workflow_report: false,
                    root_artifact_count: 0,
                    run_id: "run-001",
                    run_terminality: "not_established",
                    source_kind: "etl",
                    started_at: new Date("2026-03-09T10:00:00Z").toISOString(),
                    status: "running",
                    tenant_id: null,
                    warnings: [],
                  },
                  {
                    cell_id: null,
                    duration_ms: 1400,
                    finished_at: null,
                    has_trace: true,
                    has_workflow_report: true,
                    root_artifact_count: 2,
                    run_id: "run-002",
                    run_terminality: "not_established",
                    source_kind: "policy",
                    started_at: new Date("2026-03-09T11:00:00Z").toISOString(),
                    status: "completed",
                    tenant_id: null,
                    warnings: [],
                  },
                ],
      },
      error: null,
      isError: false,
      isLoading: false,
    }));
  });

  afterEach(() => {
    vi.restoreAllMocks();
    delete (HTMLElement.prototype as Partial<HTMLElement>).scrollIntoView;
  });

  it("only handles keyboard navigation when focus is inside the explorer", async () => {
    const user = userEvent.setup();
    renderRunsListPage();

    const firstRow = await screen.findByRole("row", { name: /run-001/i });
    const secondRow = screen.getByRole("row", { name: /run-002/i });

    expect(firstRow).toHaveAttribute("tabindex", "0");
    expect(secondRow).toHaveAttribute("tabindex", "-1");

    await user.keyboard("j");

    expect(firstRow).toHaveAttribute("tabindex", "0");
    expect(secondRow).toHaveAttribute("tabindex", "-1");
  });

  it("keeps run labels opaque and leaves lifecycle counts unavailable", async () => {
    useRunsMock.mockReturnValue({
      data: {
        page: {
          count: 2,
          cursor: null,
          limit: 50,
          next_cursor: null,
          total: 2,
        },
        runs: [
          {
            duration_ms: 1_200,
            root_artifact_count: 0,
            run_id: "run-opaque",
            run_terminality: "not_established",
            source_kind: "core_run",
            started_at: "2026-03-09T10:00:00Z",
            status: "awaiting_external_attestation",
          },
          {
            duration_ms: 1_400,
            root_artifact_count: 0,
            run_id: "run-known-shaped",
            run_terminality: "not_established",
            source_kind: "core_run",
            started_at: "2026-03-09T10:00:01Z",
            status: "completed",
          },
        ],
      },
      error: null,
      isError: false,
      isLoading: false,
    });

    renderRunsListPage();

    expect(
      await screen.findAllByText("awaiting_external_attestation"),
    ).not.toHaveLength(0);
    for (const status of screen.getAllByText("completed")) {
      expect(status).toHaveClass("bg-white/65", "text-muted");
    }
    expect(screen.getAllByText("common.unavailable")).toHaveLength(2);
  });

  it("renders all three run_terminality states without substitution", async () => {
    useRunsMock.mockReturnValue({
      data: {
        page: {
          count: 3,
          cursor: null,
          limit: 50,
          next_cursor: null,
          total: 3,
        },
        runs: [
          {
            duration_ms: 1,
            root_artifact_count: 0,
            run_id: "run-alpha",
            run_terminality: "terminal",
            source_kind: "core_run",
            started_at: "2026-08-21T10:00:00Z",
            status: "still-running-looking",
          },
          {
            duration_ms: 2,
            root_artifact_count: 0,
            run_id: "run-beta",
            run_terminality: "non_terminal",
            source_kind: "core_run",
            started_at: "2026-08-21T10:00:01Z",
            status: "completed-looking",
          },
          {
            duration_ms: 3,
            root_artifact_count: 0,
            run_id: "run-gamma",
            run_terminality: "not_established",
            source_kind: "core_run",
            started_at: "2026-08-21T10:00:02Z",
            status: "terminal-shaped-but-unowned",
          },
        ],
      },
      error: null,
      isError: false,
      isLoading: false,
    });

    renderRunsListPage();

    for (const [runId, runTerminality] of [
      ["run-alpha", "terminal"],
      ["run-beta", "non_terminal"],
      ["run-gamma", "not_established"],
    ] as const) {
      const row = await screen.findByRole("row", { name: new RegExp(runId) });
      expect(
        within(row).getByText(runTerminality, { exact: true }),
      ).toBeVisible();
    }
  });

  it("supports j/k navigation and Enter to open the active run when a row is focused", async () => {
    const user = userEvent.setup();
    renderRunsListPage();

    const firstRow = await screen.findByRole("row", { name: /run-001/i });
    await user.click(firstRow);

    await user.keyboard("j");

    await waitFor(() => {
      expect(screen.getByRole("row", { name: /run-002/i })).toHaveAttribute(
        "tabindex",
        "0",
      );
    });
    expect(
      screen.getByText(
        'pages.runs.activeRunAnnouncement:{"count":2,"position":2,"runId":"run-002","status":"completed"}',
      ),
    ).toBeInTheDocument();

    await user.keyboard("{Enter}");

    await waitFor(() => {
      expect(screen.getByText("Opened run")).toBeInTheDocument();
    });
  });

  it("keeps keyboard behavior consistent in the virtualized table path", async () => {
    const user = userEvent.setup();
    useRunsMock.mockReturnValueOnce({
      data: {
        page: {
          count: 31,
          cursor: null,
          limit: 50,
          next_cursor: "cursor-next",
          total: 31,
        },
        runs: Array.from({ length: 31 }, (_, index) => ({
          cell_id: null,
          duration_ms: 1_000 + index,
          finished_at: null,
          has_trace: false,
          has_workflow_report: false,
          root_artifact_count: index % 3,
          run_id: `run-${String(index + 1).padStart(3, "0")}`,
          run_terminality: "not_established",
          source_kind: index % 2 === 0 ? "workflow" : "policy",
          started_at: new Date(
            `2026-03-09T${String(index % 24).padStart(2, "0")}:00:00Z`,
          ).toISOString(),
          status: index % 2 === 0 ? "running" : "completed",
          tenant_id: null,
          warnings: [],
        })),
      },
      error: null,
      isError: false,
      isLoading: false,
    });

    renderRunsListPage();

    const firstRow = await screen.findByRole("row", { name: /run-001/i });
    await user.click(firstRow);

    await user.keyboard("{ArrowDown}");

    await waitFor(() => {
      expect(screen.getByRole("row", { name: /run-002/i })).toHaveAttribute(
        "tabindex",
        "0",
      );
    });
  });

  it("hydrates filters from search params and passes normalized API filters", async () => {
    renderRunsListPage(
      "/runs?status=running&from=2026-03-09T12:15&to=2026-03-09T14:45&q=policy&cursor=cursor-1",
    );

    await waitFor(() =>
      expect(useRunsMock).toHaveBeenCalledWith({
        cursor: "cursor-1",
        from_ts: new Date("2026-03-09T12:15").toISOString(),
        limit: 50,
        q: "policy",
        status: "running",
        to_ts: new Date("2026-03-09T14:45").toISOString(),
      }),
    );

    expect(
      screen.getByPlaceholderText("pages.runs.searchPlaceholder"),
    ).toHaveValue("policy");
    expect(screen.getByDisplayValue("policy")).toBeInTheDocument();
    expect(screen.getByRole("combobox")).toHaveValue("running");
    expect(screen.getByRole("link", { name: "run-002" })).toBeInTheDocument();
    expect(screen.queryByText("run-001")).not.toBeInTheDocument();
  });

  it("applies filters, paginates with cursor trail, and resets search params", async () => {
    const user = userEvent.setup();
    renderRunsListPage();

    await user.clear(
      screen.getByPlaceholderText("pages.runs.searchPlaceholder"),
    );
    await user.type(
      screen.getByPlaceholderText("pages.runs.searchPlaceholder"),
      "run-002",
    );
    await user.selectOptions(screen.getByRole("combobox"), "completed");
    await user.click(screen.getByRole("button", { name: "pages.runs.apply" }));

    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent(
        "/runs?q=run-002&status=completed",
      ),
    );
    await waitFor(() =>
      expect(useRunsMock).toHaveBeenLastCalledWith({
        cursor: undefined,
        from_ts: undefined,
        limit: 50,
        q: "run-002",
        status: "completed",
        to_ts: undefined,
      }),
    );

    await user.click(screen.getByRole("button", { name: "pages.runs.next" }));
    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent(
        "/runs?cursor=cursor-next&q=run-002&status=completed",
      ),
    );

    await user.click(screen.getByRole("button", { name: "pages.runs.prev" }));
    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent(
        "/runs?q=run-002&status=completed",
      ),
    );

    await user.click(screen.getByRole("button", { name: "pages.runs.reset" }));
    await waitFor(() =>
      expect(screen.getByTestId("location")).toHaveTextContent("/runs"),
    );
    expect(
      screen.getByPlaceholderText("pages.runs.searchPlaceholder"),
    ).toHaveValue("");
    expect(screen.getByRole("combobox")).toHaveValue("");
  });

  it("renders the empty state when the server-side search yields no runs", async () => {
    renderRunsListPage("/runs?q=missing");

    expect(
      await screen.findByText("pages.runs.emptyTitle"),
    ).toBeInTheDocument();
    expect(screen.getByText("pages.runs.emptyBody")).toBeInTheDocument();
  });
});
