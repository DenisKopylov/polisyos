import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const {
  dismissIncidentMock,
  setInterfaceModeMock,
  setLocaleMock,
  toggleThemeMock,
  useCapabilitiesMock,
  useFeatureFlagsMock,
  useHealthMock,
  useInterfaceModeMock,
  useRunsLiveStatusMock,
  useRunsSampleMock,
  useRuntimeApiIncidentMock,
  useThemeMock,
} = vi.hoisted(() => ({
  dismissIncidentMock: vi.fn(),
  setInterfaceModeMock: vi.fn(),
  setLocaleMock: vi.fn(),
  toggleThemeMock: vi.fn(),
  useCapabilitiesMock: vi.fn(),
  useFeatureFlagsMock: vi.fn(),
  useHealthMock: vi.fn(),
  useInterfaceModeMock: vi.fn(),
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

vi.mock("@/app/providers/InterfaceModeProvider", () => ({
  useInterfaceMode: (...args: unknown[]) => useInterfaceModeMock(...args),
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
    label: (
      _namespace: string,
      value: string | null | undefined,
      fallback: string,
    ) => fallback ?? value ?? "",
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
import { buildFeatureFlags } from "@/test/featureFlags";

function renderWithRouter(ui: ReactNode, initialEntry = "/runs") {
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>{ui}</MemoryRouter>,
  );
}

function mockViewport(width: number) {
  Object.defineProperty(window, "innerWidth", {
    configurable: true,
    value: width,
    writable: true,
  });

  window.matchMedia = vi.fn((query: string) => {
    const maxWidthMatch = query.match(/\(max-width:\s*(\d+)px\)/);
    const minWidthMatch = query.match(/\(min-width:\s*(\d+)px\)/);
    const matches =
      (maxWidthMatch ? width <= Number(maxWidthMatch[1]) : true) &&
      (minWidthMatch ? width >= Number(minWidthMatch[1]) : true);

    return {
      addEventListener: () => undefined,
      addListener: () => undefined,
      dispatchEvent: () => false,
      matches,
      media: query,
      onchange: null,
      removeEventListener: () => undefined,
      removeListener: () => undefined,
    };
  });
}

describe("layout surfaces", () => {
  beforeEach(() => {
    mockViewport(1280);
    dismissIncidentMock.mockReset();
    setInterfaceModeMock.mockReset();
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
      flags: buildFeatureFlags(),
    });
    useHealthMock.mockReset();
    useHealthMock.mockReturnValue({
      data: { status: "ok" },
      isError: false,
      isLoading: false,
    });
    useInterfaceModeMock.mockReset();
    useInterfaceModeMock.mockReturnValue({
      mode: "analyst" as const,
      setMode: setInterfaceModeMock,
      isClerk: false,
      isAnalyst: true,
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

  it("renders bottom navigation only on real mobile widths", () => {
    mockViewport(700);
    const tabletView = renderWithRouter(
      <AppShell>
        <div>Tablet workspace</div>
      </AppShell>,
    );

    expect(
      screen.queryByRole("navigation", { name: "mobile.nav.ariaLabel" }),
    ).not.toBeInTheDocument();
    tabletView.unmount();

    mockViewport(375);
    renderWithRouter(
      <AppShell>
        <div>Mobile workspace</div>
      </AppShell>,
    );

    expect(
      screen.getByRole("navigation", { name: "mobile.nav.ariaLabel" }),
    ).toBeInTheDocument();
  });

  it("renders header status badges and responds to theme and locale controls", async () => {
    const user = userEvent.setup();

    renderWithRouter(<Header />);

    expect(screen.getByText("shell.header.apiOk")).toBeInTheDocument();
    expect(screen.getByText("shell.header.live")).toBeInTheDocument();
    expect(
      screen.getByText('shell.header.runsInReview:{"count":1}'),
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "shell.header.theme" }),
    );
    await user.click(
      screen.getByRole("button", {
        name: "shell.header.locale common.locale.uk",
      }),
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
    expect(
      screen.getByRole("radio", { name: "mode.analyst" }),
    ).toBeChecked();

    useRunsSampleMock.mockReturnValueOnce({
      data: {
        runs: [{ run_id: "run-3", status: "completed" }],
      },
    });

    renderWithRouter(<Sidebar />, "/");
    expect(screen.getByText("shell.watchStatusStable")).toBeInTheDocument();
  });

  it("uses native radio inputs for the mode toggle with tab and arrow keyboard support", async () => {
    const user = userEvent.setup();
    renderWithRouter(<Sidebar />, "/");

    const clerkRadio = screen.getByRole("radio", { name: "mode.clerk" });
    const analystRadio = screen.getByRole("radio", { name: "mode.analyst" });

    for (let index = 0; index < 12; index += 1) {
      await user.tab();
      try {
        expect(analystRadio).toHaveFocus();
        break;
      } catch {
        // Keep tabbing until the checked radio receives focus.
      }
    }

    expect(analystRadio).toHaveFocus();

    await user.keyboard("{ArrowLeft}");
    expect(setInterfaceModeMock).toHaveBeenCalledWith("clerk");

    await user.click(screen.getByText("mode.clerk"));
    expect(setInterfaceModeMock).toHaveBeenCalledWith("clerk");
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
    expect(screen.getByRole("alert")).toBe(screen.getByTestId("runtime-banner"));
    expect(
      screen.getByText("shell.runtimeBanner.networkTitle"),
    ).toBeInTheDocument();

    await user.click(
      screen.getByRole("button", { name: "shell.runtimeBanner.dismiss" }),
    );
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
