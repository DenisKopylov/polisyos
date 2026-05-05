import { lazy, type ReactNode } from "react";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const {
  isCapabilityEnabledMock,
  isRouteErrorResponseMock,
  useCapabilitiesMock,
  useFeatureFlagsMock,
  useRouteErrorMock,
} = vi.hoisted(() => ({
  isCapabilityEnabledMock: vi.fn(),
  isRouteErrorResponseMock: vi.fn(),
  useCapabilitiesMock: vi.fn(),
  useFeatureFlagsMock: vi.fn(),
  useRouteErrorMock: vi.fn(),
}));

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");

  return {
    ...actual,
    isRouteErrorResponse: (error: unknown) => isRouteErrorResponseMock(error),
    useRouteError: () => useRouteErrorMock(),
  };
});

vi.mock("@/api/hooks/useCapabilities", () => ({
  useCapabilities: () => useCapabilitiesMock(),
}));

vi.mock("@/app/providers/FeatureFlagProvider", () => ({
  useFeatureFlags: () => useFeatureFlagsMock(),
}));

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({
    t: (path: string) => path,
  }),
}));

vi.mock("@/shared/lib/capabilities", () => ({
  isCapabilityEnabled: (...args: unknown[]) => isCapabilityEnabledMock(...args),
}));

vi.mock("@/shared/components/ErrorBoundary", () => ({
  PageErrorBoundary: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("@/shared/ui", () => ({
  Card: ({ children }: { children: ReactNode }) => (
    <div data-testid="card">{children}</div>
  ),
  EmptyState: ({ body, title }: { body: string; title: string }) => (
    <div data-testid="empty-state">
      <span>{title}</span>
      <span>{body}</span>
    </div>
  ),
  PageSkeleton: () => <div data-testid="page-skeleton" />,
  PanelSkeleton: () => <div data-testid="panel-skeleton" />,
}));

import { RouteErrorElement } from "@/app/routes/RouteErrorElement";
import { TabBoundary } from "@/app/routes/TabBoundary";
import { WorkspaceBoundary } from "@/app/routes/WorkspaceBoundary";
import { buildFeatureFlags } from "@/test/featureFlags";

describe("route boundaries", () => {
  beforeEach(() => {
    isCapabilityEnabledMock.mockReset();
    isCapabilityEnabledMock.mockReturnValue(true);
    isRouteErrorResponseMock.mockReset();
    isRouteErrorResponseMock.mockReturnValue(false);
    useCapabilitiesMock.mockReset();
    useCapabilitiesMock.mockReturnValue({
      data: {},
      isLoading: false,
    });
    useFeatureFlagsMock.mockReset();
    useFeatureFlagsMock.mockReturnValue({
      flags: buildFeatureFlags(),
    });
    useRouteErrorMock.mockReset();
    useRouteErrorMock.mockReturnValue(new Error("boom"));
  });

  it("renders route response and error messages through RouteErrorElement", () => {
    isRouteErrorResponseMock.mockReturnValueOnce(true);
    useRouteErrorMock.mockReturnValueOnce({
      status: 404,
      statusText: "Not Found",
    });

    const view = render(<RouteErrorElement />);
    expect(screen.getByTestId("empty-state")).toHaveTextContent(
      "common.pageErrorTitle",
    );
    expect(screen.getByTestId("empty-state")).toHaveTextContent(
      "404 Not Found",
    );

    view.unmount();

    render(<RouteErrorElement />);
    expect(screen.getByTestId("empty-state")).toHaveTextContent("boom");
  });

  it("falls back when route response status text is empty or the error is unknown", () => {
    isRouteErrorResponseMock.mockReturnValueOnce(true);
    useRouteErrorMock.mockReturnValueOnce({
      status: 418,
      statusText: "",
    });

    const view = render(<RouteErrorElement />);
    expect(screen.getByTestId("empty-state")).toHaveTextContent(
      "418 Route error",
    );

    view.unmount();

    isRouteErrorResponseMock.mockReturnValueOnce(false);
    useRouteErrorMock.mockReturnValueOnce({ reason: "opaque" });
    render(<RouteErrorElement />);
    expect(screen.getByTestId("empty-state")).toHaveTextContent(
      "Unknown route error",
    );
  });

  it("blocks workspaces disabled by feature flags", () => {
    useFeatureFlagsMock.mockReturnValue({
      flags: buildFeatureFlags({
        enableScenarioComposer: false,
      }),
    });

    render(
      <MemoryRouter initialEntries={["/compose"]}>
        <WorkspaceBoundary workspaceKey="scenarioComposer">
          <div>content</div>
        </WorkspaceBoundary>
      </MemoryRouter>,
    );

    expect(screen.getByTestId("empty-state")).toHaveTextContent(
      "shell.header.workspaceDisabled",
    );
  });

  it("blocks workspaces with missing required capabilities", () => {
    isCapabilityEnabledMock.mockReturnValue(false);

    render(
      <MemoryRouter initialEntries={["/runs"]}>
        <WorkspaceBoundary workspaceKey="runsDecisions">
          <div>content</div>
        </WorkspaceBoundary>
      </MemoryRouter>,
    );

    expect(screen.getByTestId("empty-state")).toHaveTextContent(
      "workflow_runs",
    );
  });

  it("renders workspace content in the configured layout and shows suspense fallbacks", () => {
    const PendingWorkspaceChild = lazy(
      () =>
        new Promise<{ default: () => ReactNode }>(() => {
          // Keep the promise pending to assert the suspense fallback.
        }),
    );

    const view = render(
      <MemoryRouter initialEntries={["/runs"]}>
        <WorkspaceBoundary workspaceKey="runsDecisions">
          <div data-testid="workspace-child">loaded</div>
        </WorkspaceBoundary>
      </MemoryRouter>,
    );

    expect(screen.getByTestId("workspace-child")).toBeInTheDocument();

    view.unmount();

    render(
      <MemoryRouter initialEntries={["/runs"]}>
        <WorkspaceBoundary workspaceKey="runsDecisions">
          <PendingWorkspaceChild />
        </WorkspaceBoundary>
      </MemoryRouter>,
    );

    expect(screen.getByTestId("page-skeleton")).toBeInTheDocument();
  });

  it("shows the tab suspense fallback while lazy tab content is pending", () => {
    const PendingTab = lazy(
      () =>
        new Promise<{ default: () => ReactNode }>(() => {
          // Keep the promise pending to assert the suspense fallback.
        }),
    );

    render(
      <TabBoundary>
        <PendingTab />
      </TabBoundary>,
    );

    expect(screen.getByTestId("panel-skeleton")).toBeInTheDocument();
  });
});
