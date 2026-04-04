import type { ReactNode } from "react";
import { useState } from "react";
import { QueryClientProvider, useSuspenseQuery } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";

const { trackMock } = vi.hoisted(() => ({
  trackMock: vi.fn(),
}));

vi.mock("@/shared/telemetry/TelemetryProvider", () => ({
  TelemetryProvider: ({ children }: { children: ReactNode }) => children,
  useTelemetry: () => ({ track: trackMock }),
  useTelemetryReadyMark: vi.fn(),
}));

import { LocaleProvider } from "@/i18n/LocaleProvider";
import { FeatureAsyncBoundary } from "@/shared/components/FeatureAsyncBoundary";
import { FeatureErrorBoundary } from "@/shared/components/ErrorBoundary";
import { createTestQueryClient } from "@/test/queryClient";

let shouldCrash = true;

function ThrowWhenEnabled() {
  if (shouldCrash) {
    throw new Error("boom");
  }

  return <div>Recovered</div>;
}

function ResetKeyHarness() {
  const [version, setVersion] = useState(1);

  return (
    <div>
      <button type="button" onClick={() => setVersion(2)}>
        Change
      </button>
      <FeatureErrorBoundary
        feature="runs.overview.timeline"
        title="Feature failed"
        body="Retry this block"
        resetKeys={[version]}
      >
        {version === 1 ? <ThrowAlways /> : <div>Recovered 2</div>}
      </FeatureErrorBoundary>
    </div>
  );
}

function ThrowAlways(): never {
  throw new Error("boom");
}

let queryAttempts = 0;

function SuspenseQueryFixture() {
  const query = useSuspenseQuery({
    queryKey: ["feature-async-boundary-test"],
    queryFn: async () => {
      queryAttempts += 1;
      if (queryAttempts === 1) {
        throw new Error("query boom");
      }
      return "loaded";
    },
    retry: false,
  });

  return <div>{query.data}</div>;
}

function renderInRouter(element: ReactNode) {
  const queryClient = createTestQueryClient();
  const router = createMemoryRouter(
    [
      {
        path: "/runs/:runId/:tab",
        element,
        handle: {
          routeId: "runs.detail",
          workspaceKey: "runs",
        },
      },
    ],
    {
      initialEntries: ["/runs/run-1/debug"],
    },
  );

  return render(
    <QueryClientProvider client={queryClient}>
      <LocaleProvider>
        <RouterProvider router={router} />
      </LocaleProvider>
    </QueryClientProvider>,
  );
}

describe("Feature async boundaries", () => {
  beforeEach(() => {
    shouldCrash = true;
    queryAttempts = 0;
    trackMock.mockReset();
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("tracks feature errors and retries crashed widgets", async () => {
    const onReset = vi.fn();

    renderInRouter(
      <FeatureErrorBoundary
        feature="runs.debug.nodePanel"
        title="Feature failed"
        body="Retry this block"
        onReset={() => {
          shouldCrash = false;
          onReset();
        }}
      >
        <ThrowWhenEnabled />
      </FeatureErrorBoundary>,
    );

    expect(await screen.findByText("Feature failed")).toBeInTheDocument();
    expect(trackMock).toHaveBeenCalledWith(
      "ui.error.feature",
      expect.objectContaining({
        feature: "runs.debug.nodePanel",
        message: "boom",
        path: "/runs/run-1/debug",
        routeId: "runs.detail",
        workspace: "runs",
      }),
    );

    await userEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(onReset).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("Recovered")).toBeInTheDocument();
  });

  it("resets crashed widgets when resetKeys change", async () => {
    renderInRouter(<ResetKeyHarness />);

    expect(await screen.findByText("Feature failed")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Change" }));

    expect(await screen.findByText("Recovered 2")).toBeInTheDocument();
  });

  it("resets suspense query errors through the retry action", async () => {
    renderInRouter(
      <FeatureAsyncBoundary
        feature="runs.debug.audit"
        title="Feature failed"
        body="Retry this block"
        loading={<div>Loading</div>}
      >
        <SuspenseQueryFixture />
      </FeatureAsyncBoundary>,
    );

    expect(await screen.findByText("Feature failed")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Retry" }));

    expect(await screen.findByText("loaded")).toBeInTheDocument();
    expect(queryAttempts).toBe(2);
  });
});
