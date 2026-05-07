import { act, render, renderHook, waitFor } from "@testing-library/react";

import { ROUTE_LOADER_EVENT_NAME } from "@/shared/telemetry/routeLoaderEvents";

const vitalsState = vi.hoisted(() => {
  const callbacks: {
    cls?: (metric: {
      delta: number;
      id: string;
      rating: string;
      value: number;
    }) => void;
    fid?: (metric: {
      delta: number;
      id: string;
      rating: string;
      value: number;
    }) => void;
    inp?: (metric: {
      delta: number;
      id: string;
      rating: string;
      value: number;
    }) => void;
    lcp?: (metric: {
      delta: number;
      id: string;
      rating: string;
      value: number;
    }) => void;
    ttfb?: (metric: {
      delta: number;
      id: string;
      rating: string;
      value: number;
    }) => void;
  } = {};

  return {
    callbacks,
    onCLSMock: vi.fn(
      (
        callback: (metric: {
          delta: number;
          id: string;
          rating: string;
          value: number;
        }) => void,
      ) => {
        callbacks.cls = callback;
      },
    ),
    onFIDMock: vi.fn(
      (
        callback: (metric: {
          delta: number;
          id: string;
          rating: string;
          value: number;
        }) => void,
      ) => {
        callbacks.fid = callback;
      },
    ),
    onINPMock: vi.fn(
      (
        callback: (metric: {
          delta: number;
          id: string;
          rating: string;
          value: number;
        }) => void,
      ) => {
        callbacks.inp = callback;
      },
    ),
    onLCPMock: vi.fn(
      (
        callback: (metric: {
          delta: number;
          id: string;
          rating: string;
          value: number;
        }) => void,
      ) => {
        callbacks.lcp = callback;
      },
    ),
    onTTFBMock: vi.fn(
      (
        callback: (metric: {
          delta: number;
          id: string;
          rating: string;
          value: number;
        }) => void,
      ) => {
        callbacks.ttfb = callback;
      },
    ),
  };
});

vi.mock("web-vitals", () => ({
  onCLS: vitalsState.onCLSMock,
  onFID: vitalsState.onFIDMock,
  onINP: vitalsState.onINPMock,
  onLCP: vitalsState.onLCPMock,
  onTTFB: vitalsState.onTTFBMock,
}));

describe("TelemetryProvider", () => {
  beforeEach(() => {
    vi.resetModules();
    vitalsState.callbacks.cls = undefined;
    vitalsState.callbacks.fid = undefined;
    vitalsState.callbacks.inp = undefined;
    vitalsState.callbacks.lcp = undefined;
    vitalsState.callbacks.ttfb = undefined;
    vitalsState.onCLSMock.mockClear();
    vitalsState.onFIDMock.mockClear();
    vitalsState.onINPMock.mockClear();
    vitalsState.onLCPMock.mockClear();
    vitalsState.onTTFBMock.mockClear();
    vi.stubEnv(
      "VITE_TELEMETRY_BEACON_URL",
      "https://telemetry.example/collect",
    );
    window.__RUNTIME_DASHBOARD_TEST__ = true;
    Object.defineProperty(globalThis.navigator, "sendBeacon", {
      configurable: true,
      value: vi.fn(() => true),
    });
    vi.spyOn(performance, "getEntriesByType").mockImplementation((type) =>
      type === "navigation"
        ? ([
            {
              domComplete: 120,
              domInteractive: 80,
              loadEventEnd: 150,
              responseEnd: 40,
            },
          ] as unknown as PerformanceEntry[])
        : [],
    );
    vi.spyOn(performance, "mark").mockImplementation(
      () =>
        ({
          detail: null,
          duration: 0,
          entryType: "mark",
          name: "mock",
          startTime: 0,
          toJSON: () => ({}),
        }) as PerformanceMark,
    );
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("emits ready, loader, vitals, and navigation telemetry through sendBeacon", async () => {
    const { TelemetryProvider, useTelemetryReadyMark } =
      await import("@/shared/telemetry/TelemetryProvider");

    function Probe() {
      useTelemetryReadyMark("runs.list.page", { routeId: "runs.list" });
      return <div>ready</div>;
    }

    render(
      <TelemetryProvider>
        <Probe />
      </TelemetryProvider>,
    );

    act(() => {
      window.dispatchEvent(
        new CustomEvent(ROUTE_LOADER_EVENT_NAME, {
          detail: {
            durationMs: 42,
            routeId: "runs.list",
            status: "ready",
          },
        }),
      );
      window.dispatchEvent(
        new CustomEvent(ROUTE_LOADER_EVENT_NAME, {
          detail: {
            durationMs: 13,
            error: "failed",
            routeId: "runs.list",
            status: "error",
          },
        }),
      );
      vitalsState.callbacks.cls?.({
        delta: 0.01,
        id: "cls-1",
        rating: "good",
        value: 0.01,
      });
      vitalsState.callbacks.inp?.({
        delta: 220,
        id: "inp-1",
        rating: "needs-improvement",
        value: 220,
      });
      vitalsState.callbacks.lcp?.({
        delta: 1800,
        id: "lcp-1",
        rating: "good",
        value: 1800,
      });
      vitalsState.callbacks.ttfb?.({
        delta: 110,
        id: "ttfb-1",
        rating: "good",
        value: 110,
      });
    });

    await waitFor(() =>
      expect(
        navigator.sendBeacon as unknown as ReturnType<typeof vi.fn>,
      ).toHaveBeenCalled(),
    );

    expect(performance.mark).toHaveBeenCalledWith("runs.list.page:ready");
    const calls = (navigator.sendBeacon as unknown as ReturnType<typeof vi.fn>)
      .mock.calls;
    const names = calls.map(([, body]) => JSON.parse(String(body)).name);
    expect(names).toContain("perf.navigation.sample");
    expect(names).toContain("ui.ready");
    expect(names).toContain("loader.error");
    expect(names).toContain("loader.ready");
    expect(names).toContain("web-vitals.cls");
    expect(names).toContain("web-vitals.inp");
    expect(names).toContain("web-vitals.lcp");
    expect(names).toContain("web-vitals.ttfb");
  });

  it("tracks query success and error events through the fetch fallback", async () => {
    Object.defineProperty(globalThis.navigator, "sendBeacon", {
      configurable: true,
      value: vi.fn(() => false),
    });
    const fetchMock = vi.fn<
      (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>
    >(() => Promise.resolve(new Response(null, { status: 204 })));
    vi.stubGlobal("fetch", fetchMock);

    const { queryClient } = await import("@/api/queryClient");
    const { TelemetryProvider } =
      await import("@/shared/telemetry/TelemetryProvider");
    queryClient.clear();

    render(
      <TelemetryProvider>
        <div>telemetry</div>
      </TelemetryProvider>,
    );

    await act(async () => {
      await queryClient.fetchQuery({
        queryFn: () => Promise.resolve("ok"),
        queryKey: ["telemetry", "success"],
      });
    });

    await act(async () => {
      await expect(
        queryClient.fetchQuery({
          queryFn: () => Promise.reject(new Error("boom")),
          queryKey: ["telemetry", "error"],
          retry: false,
        }),
      ).rejects.toThrow("boom");
    });

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    const events = fetchMock.mock.calls.map(
      (call) =>
        JSON.parse(String(call[1]?.body)) as {
          name: string;
          payload?: Record<string, unknown>;
        },
    );
    const names = events.map((event) => event.name);
    expect(names).toContain("query.fetch.success");
    expect(names).toContain("query.fetch.error");
    expect(
      events.find((event) => event.name === "query.fetch.error")?.payload,
    ).toMatchObject({
      error: "boom",
      queryHash: '["telemetry","error"]',
    });
  });

  it("requires useTelemetry to be read inside a provider", async () => {
    const { useTelemetry } =
      await import("@/shared/telemetry/TelemetryProvider");

    expect(() => renderHook(() => useTelemetry())).toThrow(
      "useTelemetry must be used within TelemetryProvider",
    );
  });
});
