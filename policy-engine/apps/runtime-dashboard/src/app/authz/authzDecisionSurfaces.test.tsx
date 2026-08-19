import type { ReactNode } from "react";
import { act, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const {
  isDiscoveryCapabilityEnabledMock,
  useAuthMeMock,
  useCapabilitiesMock,
  useDensityMock,
  useFeatureFlagsMock,
  useGlobalShortcutMock,
  useHealthMock,
  useRunsLiveStatusMock,
  useRunsSampleMock,
  useThemeMock,
} = vi.hoisted(() => ({
  isDiscoveryCapabilityEnabledMock: vi.fn(),
  useAuthMeMock: vi.fn(),
  useCapabilitiesMock: vi.fn(),
  useDensityMock: vi.fn(),
  useFeatureFlagsMock: vi.fn(),
  useGlobalShortcutMock: vi.fn(),
  useHealthMock: vi.fn(),
  useRunsLiveStatusMock: vi.fn(),
  useRunsSampleMock: vi.fn(),
  useThemeMock: vi.fn(),
}));

vi.mock("@/api/hooks/useAuthMe", () => ({
  useAuthMe: () => useAuthMeMock(),
}));

vi.mock("@/api/hooks/useCapabilities", () => ({
  isDiscoveryCapabilityEnabled: (...args: unknown[]) =>
    isDiscoveryCapabilityEnabledMock(...args),
  useCapabilities: () => useCapabilitiesMock(),
  useCapabilityDiscovery: () => ({ state: "available" }),
}));

vi.mock("@/api/hooks/useHealth", () => ({
  useHealth: () => useHealthMock(),
}));

vi.mock("@/app/providers/FeatureFlagProvider", () => ({
  useFeatureFlag: (key: string) => Boolean(useFeatureFlagsMock().flags[key]),
  useFeatureFlags: () => useFeatureFlagsMock(),
}));

vi.mock("@/app/providers/DensityProvider", () => ({
  useDensity: () => useDensityMock(),
}));

vi.mock("@/app/providers/RunsLiveProvider", () => ({
  useRunsLiveStatus: () => useRunsLiveStatusMock(),
}));

vi.mock("@/app/providers/ThemeProvider", () => ({
  useTheme: () => useThemeMock(),
}));

vi.mock("@/shared/lib/hooks", () => ({
  useGlobalShortcut: (...args: unknown[]) => useGlobalShortcutMock(...args),
}));

vi.mock("@polisyos/atlas-ui", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@polisyos/atlas-ui")>();
  return {
    ...actual,
    CommandDialog: ({
      children,
      open,
    }: {
      children: ReactNode;
      open: boolean;
    }) =>
      open ? <div data-testid="actual-command-palette">{children}</div> : null,
    CommandEmpty: ({ children }: { children: ReactNode }) => (
      <div>{children}</div>
    ),
    CommandGroup: ({ children }: { children: ReactNode }) => (
      <div>{children}</div>
    ),
    CommandInput: ({ placeholder }: { placeholder?: string }) => (
      <input aria-label={placeholder} />
    ),
    CommandItem: ({
      children,
      disabled,
      onSelect,
    }: {
      children: ReactNode;
      disabled?: boolean;
      onSelect?: () => void;
    }) => (
      <button disabled={disabled} type="button" onClick={onSelect}>
        {children}
      </button>
    ),
    CommandList: ({ children }: { children: ReactNode }) => (
      <div>{children}</div>
    ),
    CommandSeparator: () => <hr />,
    CommandShortcut: ({ children }: { children: ReactNode }) => (
      <span>{children}</span>
    ),
  };
});

vi.mock("@/features/runs", () => ({
  RUN_DETAIL_TAB_REGISTRY: [],
  useRunsSample: () => useRunsSampleMock(),
}));

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({
    locale: "en",
    setLocale: vi.fn(),
    t: (key: string) => key,
  }),
}));

vi.mock("@/shared/ui/trust-view", () => ({
  TrustViewToggle: () => <button type="button">trust-view</button>,
}));

vi.mock("@/shared/components/ErrorBoundary", () => ({
  PageErrorBoundary: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

import Header from "@/app/layout/Header";
import Sidebar from "@/app/layout/Sidebar";
import { AppMobileNav } from "@/app/layout/AppMobileNav";
import { AuthzProvider } from "@/app/authz/AuthzProvider";
import {
  InterfaceModeProvider,
  useInterfaceMode,
} from "@/app/providers/InterfaceModeProvider";
import { WorkspaceBoundary } from "@/app/routes/WorkspaceBoundary";
import { CommandPalette } from "@/features/commandPalette";
import { buildFeatureFlags } from "@/test/featureFlags";

const allowedPrincipal = {
  meta: {
    generated_at: "2026-08-19T00:00:00Z",
    request_id: "c09a-authz-surface",
    source_kinds: [],
  },
  user_id: "analyst-a",
  display_name: "Analyst A",
  tenant_id: "tenant-a",
  principal_type: "user" as const,
  cell_id: "cell-a",
  roles: ["analyst"],
  permissions: ["dashboard.view", "mode.analyst", "runs.launch", "runs.view"],
  mfa_verified: true,
  feature_overrides: { enableReviewCollaboration: false },
};

function ProtectedChrome() {
  const { mode } = useInterfaceMode();
  return (
    <>
      <span data-testid="current-interface-mode">{mode}</span>
      <Header />
      <Sidebar />
      <AppMobileNav />
      <CommandPalette />
      <WorkspaceBoundary workspaceKey="scenarioComposer">
        <div data-testid="protected-workspace">protected workspace</div>
      </WorkspaceBoundary>
    </>
  );
}

function tree(withProvider: boolean) {
  const surfaces = (
    <InterfaceModeProvider>
      <ProtectedChrome />
    </InterfaceModeProvider>
  );
  return (
    <MemoryRouter initialEntries={["/compose"]}>
      {withProvider ? <AuthzProvider>{surfaces}</AuthzProvider> : surfaces}
    </MemoryRouter>
  );
}

function expectProtectedChromeDenied() {
  expect(screen.getByTestId("current-interface-mode")).toHaveTextContent(
    "clerk",
  );
  expect(screen.queryByTestId("protected-workspace")).not.toBeInTheDocument();
  expect(
    screen.queryByTestId("shell-nav-scenarioComposer"),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByRole("radio", { name: "mode.analyst" }),
  ).not.toBeInTheDocument();
  expect(
    screen.queryByText("shell.header.launchScenario"),
  ).not.toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "shell.header.theme" }),
  ).toBeInTheDocument();
  expect(screen.getByTestId("shell-sidebar")).toBeInTheDocument();
  expect(
    within(
      screen.getByRole("navigation", { name: "mobile.nav.ariaLabel" }),
    ).queryAllByRole("link"),
  ).toHaveLength(0);
}

function expectClerkProtectedLinksDenied() {
  expect(screen.queryByTestId("shell-nav-clerk-chat")).not.toBeInTheDocument();
  expect(screen.queryByTestId("shell-nav-clerk-runs")).not.toBeInTheDocument();
  expect(screen.getByTestId("shell-sidebar")).toBeInTheDocument();
}

describe("current verified Authz decision across application chrome", () => {
  beforeEach(() => {
    window.localStorage.clear();
    isDiscoveryCapabilityEnabledMock.mockReset();
    isDiscoveryCapabilityEnabledMock.mockReturnValue(true);
    useCapabilitiesMock.mockReturnValue({
      data: {
        features: [
          { enabled: true, key: "workflow_runs", label: "Workflow runs" },
          {
            enabled: true,
            key: "evaluator_reports",
            label: "Evaluator reports",
          },
        ],
      },
      isError: false,
      isLoading: false,
    });
    useFeatureFlagsMock.mockReturnValue({ flags: buildFeatureFlags() });
    useDensityMock.mockReturnValue({
      cycleDensity: vi.fn(),
      density: "comfortable",
    });
    useGlobalShortcutMock.mockReset();
    useHealthMock.mockReturnValue({
      data: { status: "ok" },
      isError: false,
      isLoading: false,
    });
    useRunsLiveStatusMock.mockReturnValue({
      lastEventAt: null,
      status: "idle",
    });
    useRunsSampleMock.mockReturnValue({ data: { runs: [] } });
    useThemeMock.mockReturnValue({
      resolvedTheme: "light",
      theme: "light",
      toggleTheme: vi.fn(),
    });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("restores the implicit analyst default only after identity becomes verified", () => {
    useAuthMeMock.mockReturnValue({
      data: undefined,
      isError: false,
      isFetching: true,
      isLoading: true,
      isSuccess: false,
    });
    const view = render(tree(true));

    expectProtectedChromeDenied();
    expect(window.localStorage.getItem("polisyos.runtime.interface-mode")).toBe(
      null,
    );

    useAuthMeMock.mockReturnValue({
      data: allowedPrincipal,
      isError: false,
      isFetching: false,
      isLoading: false,
      isSuccess: true,
    });
    view.rerender(tree(true));

    expect(screen.getByTestId("current-interface-mode")).toHaveTextContent(
      "analyst",
    );
    expect(screen.getByTestId("protected-workspace")).toBeInTheDocument();
    expect(window.localStorage.getItem("polisyos.runtime.interface-mode")).toBe(
      null,
    );

    useAuthMeMock.mockReturnValue({
      data: allowedPrincipal,
      isError: false,
      isFetching: true,
      isLoading: false,
      isSuccess: true,
    });
    view.rerender(tree(true));
    expectProtectedChromeDenied();
    expect(window.localStorage.getItem("polisyos.runtime.interface-mode")).toBe(
      null,
    );

    useAuthMeMock.mockReturnValue({
      data: allowedPrincipal,
      isError: false,
      isFetching: false,
      isLoading: false,
      isSuccess: true,
    });
    view.rerender(tree(true));
    expect(screen.getByTestId("current-interface-mode")).toHaveTextContent(
      "analyst",
    );
    view.unmount();

    window.localStorage.setItem("polisyos.runtime.interface-mode", "clerk");
    const explicitClerk = render(tree(true));
    expect(screen.getByTestId("current-interface-mode")).toHaveTextContent(
      "clerk",
    );
    useAuthMeMock.mockReturnValue({
      data: allowedPrincipal,
      isError: false,
      isFetching: true,
      isLoading: false,
      isSuccess: true,
    });
    explicitClerk.rerender(tree(true));
    useAuthMeMock.mockReturnValue({
      data: allowedPrincipal,
      isError: false,
      isFetching: false,
      isLoading: false,
      isSuccess: true,
    });
    explicitClerk.rerender(tree(true));
    expect(screen.getByTestId("current-interface-mode")).toHaveTextContent(
      "clerk",
    );
    expect(window.localStorage.getItem("polisyos.runtime.interface-mode")).toBe(
      "clerk",
    );
  });

  it("test_unknown_authz_decision_never_defaults_authority_surface_to_allow", () => {
    const states = [
      {
        label: "loading",
        query: {
          data: undefined,
          isError: false,
          isFetching: true,
          isLoading: true,
          isSuccess: false,
        },
      },
      {
        label: "terminal identity error with retained bytes",
        query: {
          data: allowedPrincipal,
          isError: true,
          isFetching: false,
          isLoading: false,
          isSuccess: false,
        },
      },
      {
        label: "cached prior tenant while current identity refetches",
        query: {
          data: allowedPrincipal,
          isError: false,
          isFetching: true,
          isLoading: false,
          isSuccess: true,
        },
      },
    ];

    for (const { label, query } of states) {
      window.localStorage.clear();
      useAuthMeMock.mockReturnValue(query);
      const view = render(tree(true));
      expect({ label, denied: true }).toEqual({ label, denied: true });
      expectProtectedChromeDenied();
      view.unmount();
    }

    useAuthMeMock.mockReturnValue({
      data: allowedPrincipal,
      isError: false,
      isFetching: false,
      isLoading: false,
      isSuccess: true,
    });
    window.localStorage.clear();
    const currentView = render(tree(true));
    expect(screen.getByTestId("current-interface-mode")).toHaveTextContent(
      "analyst",
    );
    expect(screen.getByTestId("protected-workspace")).toBeInTheDocument();
    expect(
      screen.getByTestId("shell-nav-scenarioComposer"),
    ).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "mode.analyst" })).toBeChecked();
    expect(screen.getByText("shell.header.launchScenario")).toBeInTheDocument();
    const currentMobileNavigation = screen.getByRole("navigation", {
      name: "mobile.nav.ariaLabel",
    });
    expect(
      within(currentMobileNavigation).getByRole("link", {
        name: "mobile.nav.home",
      }),
    ).toBeInTheDocument();
    expect(
      within(currentMobileNavigation).getByRole("link", {
        name: "mobile.nav.runs",
      }),
    ).toBeInTheDocument();
    expect(
      within(currentMobileNavigation).getByRole("link", {
        name: "mobile.nav.compose",
      }),
    ).toBeInTheDocument();
    expect(
      within(currentMobileNavigation).queryByRole("link", {
        name: "mobile.nav.evidence",
      }),
    ).not.toBeInTheDocument();

    useAuthMeMock.mockReturnValue({
      data: allowedPrincipal,
      isError: false,
      isFetching: true,
      isLoading: false,
      isSuccess: true,
    });
    currentView.rerender(tree(true));
    expectProtectedChromeDenied();
    currentView.unmount();

    useAuthMeMock.mockReturnValue({
      data: { ...allowedPrincipal, permissions: [], tenant_id: "tenant-b" },
      isError: false,
      isFetching: false,
      isLoading: false,
      isSuccess: true,
    });
    const deniedView = render(tree(true));
    expectProtectedChromeDenied();
    deniedView.unmount();

    window.localStorage.clear();
    const absentView = render(tree(false));
    expectProtectedChromeDenied();
    expect(
      screen.queryByTestId("actual-command-palette"),
    ).not.toBeInTheDocument();
    const shortcut = useGlobalShortcutMock.mock.calls.at(-1)?.[3];
    expect(shortcut).toEqual(expect.any(Function));
    act(() => {
      shortcut();
    });
    expect(screen.getByTestId("actual-command-palette")).toBeInTheDocument();
    expect(
      screen.queryByRole("button", {
        name: /surfaceRegistry\.panels\.annotationSurface\.label/i,
      }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /shell\.nav\.commandCenter/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /commandPalette\.toggleTheme/i }),
    ).toBeInTheDocument();
    absentView.unmount();

    window.localStorage.setItem("polisyos.runtime.interface-mode", "clerk");
    for (const { label, query } of states) {
      useAuthMeMock.mockReturnValue(query);
      const view = render(tree(true));
      expect({ label: `clerk ${label}`, denied: true }).toEqual({
        label: `clerk ${label}`,
        denied: true,
      });
      expectClerkProtectedLinksDenied();
      view.unmount();
    }

    useAuthMeMock.mockReturnValue({
      data: allowedPrincipal,
      isError: false,
      isFetching: false,
      isLoading: false,
      isSuccess: true,
    });
    const clerkAllowedView = render(tree(true));
    expect(screen.getByTestId("shell-nav-clerk-chat")).toBeInTheDocument();
    expect(screen.getByTestId("shell-nav-clerk-runs")).toBeInTheDocument();
    clerkAllowedView.unmount();

    useAuthMeMock.mockReturnValue({
      data: { ...allowedPrincipal, permissions: ["runs.view"] },
      isError: false,
      isFetching: false,
      isLoading: false,
      isSuccess: true,
    });
    const chatDeniedView = render(tree(true));
    expect(
      screen.queryByTestId("shell-nav-clerk-chat"),
    ).not.toBeInTheDocument();
    expect(screen.getByTestId("shell-nav-clerk-runs")).toBeInTheDocument();
    chatDeniedView.unmount();

    useAuthMeMock.mockReturnValue({
      data: { ...allowedPrincipal, permissions: ["dashboard.view"] },
      isError: false,
      isFetching: false,
      isLoading: false,
      isSuccess: true,
    });
    const runsDeniedView = render(tree(true));
    expect(screen.getByTestId("shell-nav-clerk-chat")).toBeInTheDocument();
    expect(
      screen.queryByTestId("shell-nav-clerk-runs"),
    ).not.toBeInTheDocument();
    runsDeniedView.unmount();

    const absentClerkView = render(tree(false));
    expectClerkProtectedLinksDenied();
    absentClerkView.unmount();
  });
});
