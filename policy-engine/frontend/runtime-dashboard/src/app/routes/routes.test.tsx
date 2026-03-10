import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";

const { composeLoaderMock, trackMock } = vi.hoisted(() => ({
  composeLoaderMock: vi.fn<(args?: unknown) => Promise<void> | null>(
    () => null,
  ),
  trackMock: vi.fn(),
}));

vi.mock("@/app/layout/AppShell", () => ({
  default: ({ children }: { children: React.ReactNode }) => (
    <div data-testid="app-shell">{children}</div>
  ),
}));

vi.mock("@/app/providers/TelemetryProvider", () => ({
  useTelemetry: () => ({
    track: trackMock,
  }),
}));

vi.mock("@/app/providers/RunsLiveProvider", () => ({
  RunsLiveProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/app/providers/RuntimeApiProvider", () => ({
  RuntimeApiProvider: ({ children }: { children: React.ReactNode }) => children,
}));

vi.mock("@/app/routes/RouteErrorElement", () => ({
  RouteErrorElement: () => <div data-testid="route-error-element" />,
}));

vi.mock("@/features/auth/route", () => ({
  loginRoute: {
    element: <div data-testid="login-page">Login</div>,
    handle: { routeId: "auth.login" },
    path: "login",
  },
}));

vi.mock("@/features/composer/route", () => ({
  composerRoute: {
    element: <div data-testid="composer-page">Compose</div>,
    handle: { routeId: "composer.launch" },
    loader: (args: unknown) => composeLoaderMock(args),
    path: "compose",
  },
}));

vi.mock("@/features/dashboard/route", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>(
    "react-router-dom",
  );

  return {
    dashboardRoute: {
      element: (
        <div>
          <div data-testid="dashboard-page">Dashboard</div>
          <actual.Link to="/compose">Go compose</actual.Link>
        </div>
      ),
      handle: { routeId: "dashboard.home" },
      index: true,
    },
  };
});

vi.mock("@/features/artifacts/route", () => ({
  artifactRoute: {
    element: <div data-testid="artifact-page">Artifacts</div>,
    handle: { routeId: "artifacts.detail" },
    path: "artifacts/:artifactId",
  },
}));

vi.mock("@/features/evidence/route", () => ({
  evidenceRoute: {
    element: <div data-testid="evidence-page">Evidence</div>,
    handle: { routeId: "evidence.fabric" },
    path: "evidence",
  },
}));

vi.mock("@/features/lex/route", () => ({
  lexRoute: {
    element: <div data-testid="lex-page">Knowledge</div>,
    handle: { routeId: "lex.knowledge" },
    path: "knowledge",
  },
}));

vi.mock("@/features/platform/route", () => ({
  platformRoute: {
    element: <div data-testid="platform-page">Platform</div>,
    handle: { routeId: "platform.health" },
    path: "platform",
  },
}));

vi.mock("@/features/runs/route", () => ({
  runsRoutes: [],
}));

import { APP_ROUTES } from "@/app/routes/routes";

describe("APP_ROUTES", () => {
  beforeEach(() => {
    composeLoaderMock.mockReset();
    composeLoaderMock.mockResolvedValue(null);
    trackMock.mockReset();
  });

  it("renders login routes without the shell and emits route view telemetry", async () => {
    const router = createMemoryRouter(APP_ROUTES, {
      initialEntries: ["/login"],
    });

    render(<RouterProvider router={router} />);

    expect(await screen.findByTestId("login-page")).toBeInTheDocument();
    expect(screen.queryByTestId("app-shell")).not.toBeInTheDocument();
    await waitFor(() =>
      expect(trackMock).toHaveBeenCalledWith(
        "route.view",
        expect.objectContaining({
          fullPath: "/login",
          path: "/login",
          routeId: "auth.login",
          workspace: "commandCenter",
        }),
      ),
    );
  });

  it.each([
    {
      fullPath: "/compose",
      initialEntry: "/launch",
      pageTestId: "composer-page",
      routeId: "composer.launch",
      workspace: "scenarioComposer",
    },
    {
      fullPath: "/evidence",
      initialEntry: "/sources",
      pageTestId: "evidence-page",
      routeId: "evidence.fabric",
      workspace: "evidenceFabric",
    },
    {
      fullPath: "/evidence",
      initialEntry: "/data",
      pageTestId: "evidence-page",
      routeId: "evidence.fabric",
      workspace: "evidenceFabric",
    },
    {
      fullPath: "/knowledge",
      initialEntry: "/lex",
      pageTestId: "lex-page",
      routeId: "lex.knowledge",
      workspace: "lexKnowledge",
    },
    {
      fullPath: "/platform",
      initialEntry: "/health",
      pageTestId: "platform-page",
      routeId: "platform.health",
      workspace: "platformHealth",
    },
  ])(
    "wraps app routes with the shell and follows legacy redirect from $initialEntry",
    async ({ fullPath, initialEntry, pageTestId, routeId, workspace }) => {
      const router = createMemoryRouter(APP_ROUTES, {
        initialEntries: [initialEntry],
      });

      render(<RouterProvider router={router} />);

      expect(await screen.findByTestId(pageTestId)).toBeInTheDocument();
      expect(screen.getByTestId("app-shell")).toBeInTheDocument();
      await waitFor(() =>
        expect(trackMock).toHaveBeenCalledWith(
          "route.view",
          expect.objectContaining({
            fullPath,
            path: fullPath,
            routeId,
            workspace,
          }),
        ),
      );
    },
  );

  it("tracks route transitions when navigation leaves the dashboard", async () => {
    let resolveComposeLoader: (() => void) | undefined;
    composeLoaderMock.mockImplementationOnce(
      () =>
        new Promise<void>((resolve) => {
          resolveComposeLoader = () => resolve();
        }),
    );
    const router = createMemoryRouter(APP_ROUTES, {
      initialEntries: ["/"],
    });

    render(<RouterProvider router={router} />);

    expect(await screen.findByTestId("dashboard-page")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("link", { name: "Go compose" }));

    await waitFor(() =>
      expect(trackMock).toHaveBeenCalledWith(
        "route.transition.started",
        expect.objectContaining({
          from: "/",
          routeId: "dashboard.home",
          state: "loading",
          to: "/compose",
        }),
      ),
    );

    resolveComposeLoader?.();

    expect(await screen.findByTestId("composer-page")).toBeInTheDocument();
    await waitFor(() =>
      expect(trackMock).toHaveBeenCalledWith(
        "route.transition.ready",
        expect.objectContaining({
          from: "/",
          fromRouteId: "dashboard.home",
          routeId: "composer.launch",
          to: "/compose",
          workspace: "scenarioComposer",
        }),
      ),
    );
  });
});
