import { render, renderHook, screen } from "@testing-library/react";

const { tMock, useRunDetailSummaryMock, useRunLiveUpdatesMock } = vi.hoisted(
  () => ({
    tMock: vi.fn((path: string) => path),
    useRunDetailSummaryMock: vi.fn(),
    useRunLiveUpdatesMock: vi.fn(),
  }),
);

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({
    t: tMock,
  }),
}));

vi.mock("@/features/runs/live/useRunLiveUpdates", () => ({
  useRunLiveUpdates: (...args: unknown[]) => useRunLiveUpdatesMock(...args),
}));

vi.mock("@/features/runs/routes/useRunDetailSummary", () => ({
  useRunDetailSummary: (...args: unknown[]) => useRunDetailSummaryMock(...args),
}));

import {
  RunInspectorProvider,
  useRunInspector,
} from "@/features/runs/context/RunInspectorContext";

function Probe() {
  const summary = useRunInspector();

  return <div data-testid="transport-status">{summary.transportStatus}</div>;
}

describe("RunInspectorContext", () => {
  beforeEach(() => {
    tMock.mockClear();
    useRunDetailSummaryMock.mockReset();
    useRunLiveUpdatesMock.mockReset();
  });

  it("passes live connectivity into useRunDetailSummary and exposes the summary", () => {
    useRunLiveUpdatesMock.mockReturnValue({ isLiveConnected: true });
    useRunDetailSummaryMock.mockReturnValue({
      transportStatus: "live",
    });

    render(
      <RunInspectorProvider runId="run-1">
        <Probe />
      </RunInspectorProvider>,
    );

    expect(useRunLiveUpdatesMock).toHaveBeenCalledWith("run-1");
    expect(useRunDetailSummaryMock).toHaveBeenCalledWith("run-1", tMock, {
      liveTransport: true,
    });
    expect(screen.getByTestId("transport-status")).toHaveTextContent("live");
  });

  it("keeps liveTransport disabled when the live layer is disconnected", () => {
    useRunLiveUpdatesMock.mockReturnValue({ isLiveConnected: false });
    useRunDetailSummaryMock.mockReturnValue({
      transportStatus: "polling",
    });

    render(
      <RunInspectorProvider runId="run-2">
        <Probe />
      </RunInspectorProvider>,
    );

    expect(useRunDetailSummaryMock).toHaveBeenCalledWith("run-2", tMock, {
      liveTransport: false,
    });
    expect(screen.getByTestId("transport-status")).toHaveTextContent("polling");
  });

  it("throws when useRunInspector is read outside the provider", () => {
    expect(() => renderHook(() => useRunInspector())).toThrow(
      "useRunInspector must be used within a RunInspectorProvider",
    );
  });
});
