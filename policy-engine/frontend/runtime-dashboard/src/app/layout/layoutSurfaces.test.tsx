import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const {
  dismissIncidentMock,
  setLocaleMock,
  toggleThemeMock,
  useCapabilitiesMock,
  useFeatureFlagsMock,
  useHealthMock,
  useRunsLiveStatusMock,
  useRunsSampleMock,
  useRuntimeApiIncidentMock,
  useThemeMock,
} = vi.hoisted(() => ({
  dismissIncidentMock: vi.fn(),
  setLocaleMock: vi.fn(),
  toggleThemeMock: vi.fn(),
  useCapabilitiesMock: vi.fn(),
  useFeatureFlagsMock: vi.fn(),
  useHealthMock: vi.fn(),
  useRunsLiveStatusMock: vi.fn(),
  useRunsSampleMock: vi.fn(),
  useRuntimeApiIncidentMock: vi.fn(),
  useThemeMock: vi.fn(),
}));

vi.mock("@/api/hooks/useCapabilities", () => ({
  useCapabilities: (...args: unknown[]) => useCapabilitiesMock(...args),
}));

vi.mock("@/api/hooks/useHealth", () => ({
  useHealth: (...args: unknown[]) => useHealthMock(...args),
}));

vi.mock("@/app/providers/FeatureFlagProvider", () => ({
  useFeatureFlags: (...args: unknown[]) => useFeatureFlagsMock(...args),
}));

vi.mock("@/app/providers/ThemeProvider", () => ({
  useTheme: (...args: unknown[]) => useThemeMock(...args),
}));

vi.mock("@/app/providers/RunsLiveProvider", () => ({
  useRunsLiveStatus: (...args: unknown[]) => useRunsLiveStatusMock(...args),
}));

vi.mock("@/features/runs/api/useRunsSample", () => ({
  useRunsSample: (...args: unknown[]) => useRunsSampleMock(...args),
}));

vi.mock("@/app/providers/RuntimeApiProvider", () => ({
  useRuntimeApiIncident: (...args: unknown[]) =>
    useRuntimeApiIncidentMock(...args),
}));

vi.mock("@/i18n/LocaleProvider", () => ({
  SUPPORTED_LOCALES: ["en", "uk"],
  useI18n: () => ({
    label: (_namespace: string, value: string | null | undefined, fallback: string) =>
      fallback ?? value ?? "",
    locale: "en",
    setLocale: setLocaleMock,
    t: (key: string, payload?: Record<string, unknown>) =>
      payload ? `${key}:${JSON.stringify(payload)}` : key,
  }),
}));

import AppShell from "@/app/layout/AppShell";
import { GlobalRuntimeBanner } from "@/app/layout/GlobalRuntimeBanner";
import Header from "@/app/layout/Header";
import Sidebar from "@/app/layout/Sidebar";

function renderWithRouter(ui: ReactNode, initialEntry = "/runs") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>{ui}</MemoryRouter>,
  );
}

describe("layout surfaces", () => {
  beforeEach(() => {
    dismissIncidentMock.mockReset();
    setLocaleMock.mockReset();
    toggleThemeMock.mockReset();
    useCapabilitiesMock.mockReset();
    useCapabilitiesMock.mockReturnValue({
      data: {
        features: [
          { enabled: true, key: "workflow_runs", label: "Workflow runs" },
          { enabled: true, key: "lex_pipeline", label: "Lex pipeline" },
        ],
      },
      isError: false,
      isLoading: false,
    });
    useFeatureFlagsMock.mockReset();
    useFeatureFlagsMock.mockReturnValue({
      flags: {
        enableLexKnowledge: true,
        enablePlatformHealth: true,
        enableRunsWorkspace: true,
        enableScenarioComposer: true,
      },
    });
    useHealthMock.mockReset();
    useHealthMock.mockReturnValue({
      data: { status: "ok" },
      isError: false,
      isLoading: false,
    });
    useRunsLiveStatusMock.mockReset();
    useRunsLiveStatusMock.mockReturnValue({
      lastEventAt: Date.now(),
      status: "live",
    });
    useRunsSampleMock.mockReset();
    useRunsSampleMock.mockReturnValue({
      data: {
        runs: [
          { run_id: "run-1", status: "blocked_preflight" },
          { run_id: "run-2", status: "completed" },
        ],
      },
    });
    useRuntimeApiIncidentMock.mockReset();
    useRuntimeApiIncidentMock.mockReturnValue({
      dismissIncident: dismissIncidentMock,
      incident: null,
    });
    useThemeMock.mockReset();
    useThemeMock.mockReturnValue({
      theme: "light",
      toggleTheme: toggleThemeMock,
    });
  });

  it("renders the application shell with sidebar, header, and main content", () => {
    renderWithRouter(
      <AppShell>
        <div>Run workspace</div>
      </AppShell>,
    );

    expect(screen.getByTestId("app-shell")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "common.skipToContent" }),
    ).toBeInTheDocument();
    expect(screen.getByTestId("shell-sidebar")).toBeInTheDocument();
    expect(screen.getByTestId("shell-header")).toBeInTheDocument();
    expect(screen.getByText("Run workspace")).toBeInTheDocument();
  });

  it("renders header status badges and responds to theme and locale controls", async () => {
    const user = userEvent.setup();

    renderWithRouter(<Header />);

    expect(screen.getByText("shell.header.apiOk")).toBeInTheDocument();
    expect(screen.getByText("shell.header.live")).toBeInTheDocument();
    expect(
      screen.getByText("shell.header.runsInReview:{\"count\":1}"),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "shell.header.theme" }));
    await user.click(
      screen.getByRole("button", { name: "shell.header.locale common.locale.uk" }),
    );

    expect(toggleThemeMock).toHaveBeenCalledTimes(1);
    expect(setLocaleMock).toHaveBeenCalledWith("uk");
  });

  it("renders loading and unavailable header states", () => {
    useHealthMock.mockReturnValueOnce({
      data: undefined,
      isError: false,
      isLoading: true,
    });

    renderWithRouter(<Header />);
    expect(screen.getByText("shell.header.checking")).toBeInTheDocument();

    useHealthMock.mockReturnValueOnce({
      data: undefined,
      isError: true,
      isLoading: false,
    });

    renderWithRouter(<Header />);
    expect(screen.getByText("shell.header.unavailable")).toBeInTheDocument();
  });

  it("renders sidebar workspace navigation and watch status branches", () => {
    renderWithRouter(<Sidebar />, "/");

    expect(screen.getByTestId("shell-nav-commandCenter")).toBeInTheDocument();
    expect(screen.getByText("shell.watchStatusBlocked")).toBeInTheDocument();

    useRunsSampleMock.mockReturnValueOnce({
      data: {
        runs: [{ run_id: "run-3", status: "completed" }],
      },
    });

    renderWithRouter(<Sidebar />, "/");
    expect(screen.getByText("shell.watchStatusStable")).toBeInTheDocument();
  });

  it("renders runtime incidents for network and access errors and allows dismissal", async () => {
    const user = userEvent.setup();

    useRuntimeApiIncidentMock.mockReturnValueOnce({
      dismissIncident: dismissIncidentMock,
      incident: {
        code: "runtime_api_network_error",
        detail: "Gateway timeout",
        source: "/api/v1/runs",
        status: 0,
      },
    });

    renderWithRouter(<GlobalRuntimeBanner />);
    expect(screen.getByTestId("runtime-banner")).toBeInTheDocument();
    expect(screen.getByText("shell.runtimeBanner.networkTitle")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "shell.runtimeBanner.dismiss" }));
    expect(dismissIncidentMock).toHaveBeenCalledTimes(1);

    useRuntimeApiIncidentMock.mockReturnValueOnce({
      dismissIncident: dismissIncidentMock,
      incident: {
        code: "forbidden",
        detail: "Access denied",
        source: "/api/v1/control",
        status: 403,
      },
    });

    renderWithRouter(<GlobalRuntimeBanner />);
    expect(
      screen.getByText("shell.runtimeBanner.accessDeniedTitle"),
    ).toBeInTheDocument();
  });
});
