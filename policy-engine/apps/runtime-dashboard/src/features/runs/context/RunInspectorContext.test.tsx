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

  return (
    <>
      <div data-testid="transport-status">{summary.transportStatus}</div>
      <div data-testid="live-transport">{String(summary.liveTransport)}</div>
    </>
  );
}

describe("RunInspectorContext", () => {
  beforeEach(() => {
    tMock.mockClear();
    useRunDetailSummaryMock.mockReset();
    useRunLiveUpdatesMock.mockReset();
  });

  it("subscribes by validated Core ID and exposes the live connection state", () => {
    useRunLiveUpdatesMock.mockReturnValue({ isLiveConnected: true });
    useRunDetailSummaryMock.mockReturnValue({
      coreRunId: "core-run-1",
      transportStatus: "live",
    });

    render(
      <RunInspectorProvider runId="run-1">
        <Probe />
      </RunInspectorProvider>,
    );

    expect(useRunLiveUpdatesMock).toHaveBeenCalledWith("core-run-1");
    expect(useRunDetailSummaryMock).toHaveBeenCalledWith("run-1", tMock);
    expect(screen.getByTestId("transport-status")).toHaveTextContent("live");
    expect(screen.getByTestId("live-transport")).toHaveTextContent("true");
  });

  it("does not open a run stream until the summary has a Core identity", () => {
    useRunLiveUpdatesMock.mockReturnValue({ isLiveConnected: false });
    useRunDetailSummaryMock.mockReturnValue({
      coreRunId: undefined,
      transportStatus: "polling",
    });

    render(
      <RunInspectorProvider runId="run-2">
        <Probe />
      </RunInspectorProvider>,
    );

    expect(useRunLiveUpdatesMock).toHaveBeenCalledWith(undefined);
    expect(useRunDetailSummaryMock).toHaveBeenCalledWith("run-2", tMock);
    expect(screen.getByTestId("transport-status")).toHaveTextContent("polling");
    expect(screen.getByTestId("live-transport")).toHaveTextContent("false");
  });

  it("throws when useRunInspector is read outside the provider", () => {
    expect(() => renderHook(() => useRunInspector())).toThrow(
      "useRunInspector must be used within a RunInspectorProvider",
    );
  });
});
