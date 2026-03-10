import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const {
  useCapabilitiesMock,
  useConnectorsMock,
  useHealthMock,
  usePermissionMock,
  useRunsMock,
  useTelemetryReadyMarkMock,
} = vi.hoisted(() => ({
  useCapabilitiesMock: vi.fn(),
  useConnectorsMock: vi.fn(),
  useHealthMock: vi.fn(),
  usePermissionMock: vi.fn(),
  useRunsMock: vi.fn(),
  useTelemetryReadyMarkMock: vi.fn(),
}));

vi.mock("@/api/hooks/useCapabilities", () => ({
  useCapabilities: (...args: unknown[]) => useCapabilitiesMock(...args),
}));

vi.mock("@/api/hooks/useConnectors", () => ({
  useConnectors: (...args: unknown[]) => useConnectorsMock(...args),
}));

vi.mock("@/api/hooks/useHealth", () => ({
  useHealth: (...args: unknown[]) => useHealthMock(...args),
}));

vi.mock("@/api/hooks/useRuns", () => ({
  useRuns: (...args: unknown[]) => useRunsMock(...args),
}));

vi.mock("@/app/authz/AuthzProvider", async () => {
  const actual = await vi.importActual<typeof import("@/app/authz/AuthzProvider")>(
    "@/app/authz/AuthzProvider",
  );
  return {
    ...actual,
    usePermission: (...args: unknown[]) => usePermissionMock(...args),
  };
});

vi.mock("@/app/providers/TelemetryProvider", () => ({
  useTelemetryReadyMark: (...args: unknown[]) =>
    useTelemetryReadyMarkMock(...args),
}));

vi.mock("@/i18n/LocaleProvider", async () => {
  const actual = await vi.importActual<typeof import("@/i18n/LocaleProvider")>(
    "@/i18n/LocaleProvider",
  );
  return {
    ...actual,
    useI18n: () => ({
      label: (
        _namespace: string,
        value: string | null | undefined,
        fallback: string,
      ) => fallback ?? value ?? "",
      t: (key: string, payload?: Record<string, unknown>) =>
        payload ? `${key}:${JSON.stringify(payload)}` : key,
    }),
  };
});

import PlatformHealthPage from "@/features/platform/routes/PlatformHealthPage";

function renderPlatformHealthPage() {
  return render(
    <MemoryRouter>
      <PlatformHealthPage />
    </MemoryRouter>,
  );
}

describe("PlatformHealthPage", () => {
  beforeEach(() => {
    useCapabilitiesMock.mockReset();
    usePermissionMock.mockReset();
    usePermissionMock.mockReturnValue(true);
    useCapabilitiesMock.mockReturnValue({
      data: {
        constraints: {
          max_parallel_models: 4,
        },
        features: [
          {
            category: "control",
            description: "Workflow runs",
            enabled: true,
            key: "workflow_runs",
            label: "Workflow runs",
            stage: "active",
          },
          {
            category: "evidence",
            description: "Promotion lane",
            enabled: false,
            key: "promotion_lane",
            label: "Promotion lane",
            stage: "planned",
          },
        ],
        runtime_api_version: "2026.03",
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    useConnectorsMock.mockReset();
    useConnectorsMock.mockReturnValue({
      data: {
        connectors: [
          {
            connector_id: "world-bank",
            last_health_check: "2026-03-09T10:00:00Z",
            loaded: true,
          },
          {
            connector_id: "imf",
            last_health_check: null,
            loaded: false,
          },
        ],
      },
      error: null,
      isError: false,
      isLoading: false,
    });
    useHealthMock.mockReset();
    useHealthMock.mockReturnValue({
      data: {
        service: "runtime-api",
        status: "ok",
        ts: "2026-03-10T08:00:00Z",
      },
      error: null,
      isError: false,
    });
    useRunsMock.mockReset();
    useRunsMock.mockReturnValue({
      data: {
        runs: [{ run_id: "run-1" }, { run_id: "run-2" }],
      },
    });
    useTelemetryReadyMarkMock.mockReset();
  });

  it("renders runtime, capability, connector, and run status cards", () => {
    renderPlatformHealthPage();

    expect(screen.getByTestId("platform-page")).toBeInTheDocument();
    expect(screen.getByText("pages.platform.heroTitle")).toBeInTheDocument();
    expect(screen.getAllByText("runtime-api")).not.toHaveLength(0);
    expect(screen.getAllByText("Workflow runs")).not.toHaveLength(0);
    expect(screen.getAllByText("Promotion lane")).not.toHaveLength(0);
    expect(screen.getByText("world-bank")).toBeInTheDocument();
    expect(screen.getByText("pages.platform.connectorUnavailable")).toBeInTheDocument();
    expect(useTelemetryReadyMarkMock).toHaveBeenCalledWith(
      "platform.health.page",
      { routeId: "platform.health" },
    );
  });

  it("renders capability and runtime errors while leaving the rest of the page intact", () => {
    useCapabilitiesMock.mockReturnValueOnce({
      data: undefined,
      error: new Error("capability failed"),
      isError: true,
      isLoading: false,
    });
    useHealthMock.mockReturnValueOnce({
      data: undefined,
      error: new Error("health failed"),
      isError: true,
    });

    renderPlatformHealthPage();

    expect(
      screen.getByText("pages.platform.loadCapabilityManifestError"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("pages.platform.loadRuntimeHealthError"),
    ).toBeInTheDocument();
    expect(screen.getByText("pages.platform.connectorReadiness")).toBeInTheDocument();
  });
});
