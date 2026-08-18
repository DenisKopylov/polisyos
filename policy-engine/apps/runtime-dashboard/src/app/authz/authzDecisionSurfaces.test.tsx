import type { ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const {
  useAuthMeMock,
  useCapabilitiesMock,
  useFeatureFlagsMock,
  useHealthMock,
  useInterfaceModeMock,
  useRunsLiveStatusMock,
  useRunsSampleMock,
  useThemeMock,
} = vi.hoisted(() => ({
  useAuthMeMock: vi.fn(),
  useCapabilitiesMock: vi.fn(),
  useFeatureFlagsMock: vi.fn(),
  useHealthMock: vi.fn(),
  useInterfaceModeMock: vi.fn(),
  useRunsLiveStatusMock: vi.fn(),
  useRunsSampleMock: vi.fn(),
  useThemeMock: vi.fn(),
}));

vi.mock("@/api/hooks/useAuthMe", () => ({
  useAuthMe: () => useAuthMeMock(),
}));

vi.mock("@/api/hooks/useCapabilities", () => ({
  useCapabilities: () => useCapabilitiesMock(),
}));

vi.mock("@/api/hooks/useHealth", () => ({
  useHealth: () => useHealthMock(),
}));

vi.mock("@/app/providers/FeatureFlagProvider", () => ({
  useFeatureFlags: () => useFeatureFlagsMock(),
}));

vi.mock("@/app/providers/InterfaceModeProvider", () => ({
  useInterfaceMode: () => useInterfaceModeMock(),
}));

vi.mock("@/app/providers/RunsLiveProvider", () => ({
  useRunsLiveStatus: () => useRunsLiveStatusMock(),
}));

vi.mock("@/app/providers/ThemeProvider", () => ({
  useTheme: () => useThemeMock(),
}));

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
import { AuthzProvider } from "@/app/authz/AuthzProvider";
import { WorkspaceBoundary } from "@/app/routes/WorkspaceBoundary";
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
  return (
    <>
      <Header />
      <Sidebar />
      <WorkspaceBoundary workspaceKey="scenarioComposer">
        <div data-testid="protected-workspace">protected workspace</div>
      </WorkspaceBoundary>
    </>
  );
}

function tree(withProvider: boolean) {
  const surfaces = <ProtectedChrome />;
  return (
    <MemoryRouter initialEntries={["/compose"]}>
      {withProvider ? <AuthzProvider>{surfaces}</AuthzProvider> : surfaces}
    </MemoryRouter>
  );
}

function expectProtectedChromeDenied() {
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
}

describe("current verified Authz decision across application chrome", () => {
  beforeEach(() => {
    useCapabilitiesMock.mockReturnValue({
      data: {
        features: [
          { enabled: true, key: "workflow_runs", label: "Workflow runs" },
        ],
      },
      isError: false,
      isLoading: false,
    });
    useFeatureFlagsMock.mockReturnValue({ flags: buildFeatureFlags() });
    useHealthMock.mockReturnValue({
      data: { status: "ok" },
      isError: false,
      isLoading: false,
    });
    useInterfaceModeMock.mockReturnValue({
      isAnalyst: true,
      isClerk: false,
      mode: "analyst",
      setMode: vi.fn(),
    });
    useRunsLiveStatusMock.mockReturnValue({
      lastEventAt: null,
      status: "idle",
    });
    useRunsSampleMock.mockReturnValue({ data: { runs: [] } });
    useThemeMock.mockReturnValue({ theme: "light", toggleTheme: vi.fn() });
  });

  afterEach(() => {
    vi.clearAllMocks();
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
    const currentView = render(tree(true));
    expect(screen.getByTestId("protected-workspace")).toBeInTheDocument();
    expect(
      screen.getByTestId("shell-nav-scenarioComposer"),
    ).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "mode.analyst" })).toBeChecked();
    expect(screen.getByText("shell.header.launchScenario")).toBeInTheDocument();

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

    const absentView = render(tree(false));
    expectProtectedChromeDenied();
    absentView.unmount();
  });
});
