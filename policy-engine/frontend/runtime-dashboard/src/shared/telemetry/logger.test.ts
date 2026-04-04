describe("structured logger", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubEnv(
      "VITE_TELEMETRY_BEACON_URL",
      "https://telemetry.example/collect",
    );
    Object.defineProperty(globalThis.navigator, "sendBeacon", {
      configurable: true,
      value: vi.fn(() => true),
    });
    window.__RUNTIME_DASHBOARD_TEST__ = true;
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.restoreAllMocks();
  });

  it("emits a stable structured envelope through telemetry", async () => {
    const { setActiveRouteTelemetryContext } =
      await import("@/shared/telemetry/routeContext");
    setActiveRouteTelemetryContext({
      fullPath: "/runs/R-1/overview",
      path: "/runs/R-1/overview",
      routeId: "runs.detail.overview",
      workspace: "runs",
    });
    const { createLogger } = await import("@/shared/telemetry/logger");
    const logger = createLogger({
      tags: {
        surface: "overview",
      },
    });

    logger.error({
      error: new Error("boom"),
      event: "ui.error.feature",
      message: "Feature failed",
      requestId: "req-42",
      tags: {
        feature: "runs.overview.decision",
      },
    });

    const sendBeaconMock = navigator.sendBeacon as unknown as ReturnType<
      typeof vi.fn
    >;
    expect(sendBeaconMock).toHaveBeenCalledTimes(1);

    const [, body] = sendBeaconMock.mock.calls[0];
    expect(JSON.parse(String(body))).toMatchObject({
      name: "app.log",
      payload: {
        event: "ui.error.feature",
        fullPath: "/runs/R-1/overview",
        level: "error",
        message: "Feature failed",
        requestId: "req-42",
        routeId: "runs.detail.overview",
        tags: {
          feature: "runs.overview.decision",
          surface: "overview",
        },
        workspace: "runs",
      },
    });
  });
});
