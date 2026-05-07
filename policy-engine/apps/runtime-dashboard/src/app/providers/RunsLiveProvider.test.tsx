import type { PropsWithChildren } from "react";
import { act, render, screen, waitFor } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";

import {
  RunsLiveProvider,
  useRunsLiveStatus,
} from "@/app/providers/RunsLiveProvider";
import {
  RUN_ACTIVE_REFETCH_MS,
  RUNS_LIVE_HEARTBEAT_MS,
  RUNS_LIVE_RETRY_MS,
} from "@/shared/lib/constants";
import { createTestQueryClient } from "@/test/queryClient";

const { trackMock } = vi.hoisted(() => ({
  trackMock: vi.fn(),
}));

vi.mock("@/app/providers/TelemetryProvider", () => ({
  useTelemetry: () => ({
    track: trackMock,
  }),
}));

vi.mock("@/app/providers/LiveAnnouncerProvider", () => ({
  useLiveAnnouncer: () => ({
    announce: vi.fn(),
  }),
}));

type MockMessageListener = (event: MessageEvent<string>) => void;

class MockEventSource {
  static instances: MockEventSource[] = [];

  readonly url: string;
  readonly withCredentials: boolean;
  readonly close = vi.fn(() => {
    this.readyState = 2;
  });
  readonly listeners = new Map<string, Set<MockMessageListener>>();
  onerror: ((event: Event) => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onopen: ((event: Event) => void) | null = null;
  readyState = 0;

  constructor(url: string, options?: { withCredentials?: boolean }) {
    this.url = url;
    this.withCredentials = options?.withCredentials ?? false;
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: EventListener) {
    const existing = this.listeners.get(type) ?? new Set<MockMessageListener>();
    existing.add(listener as unknown as MockMessageListener);
    this.listeners.set(type, existing);
  }

  emit(type: string, payload: unknown, lastEventId = "") {
    const event = {
      data: typeof payload === "string" ? payload : JSON.stringify(payload),
      lastEventId,
    } as MessageEvent<string>;
    if (type === "message") {
      this.onmessage?.(event);
      return;
    }
    for (const listener of this.listeners.get(type) ?? []) {
      listener(event);
    }
  }

  fail() {
    this.onerror?.(new Event("error"));
  }

  open() {
    this.readyState = 1;
    this.onopen?.(new Event("open"));
  }

  static reset() {
    MockEventSource.instances = [];
  }
}

function RunsLiveProbe() {
  const live = useRunsLiveStatus();

  return (
    <div>
      <span data-testid="runs-live-status">{live.status}</span>
      <span data-testid="runs-live-cursor">{live.cursor ?? "none"}</span>
    </div>
  );
}

function renderRunsLive(initialEntries: string[]) {
  const queryClient = createTestQueryClient();

  function Wrapper({ children }: PropsWithChildren) {
    return (
      <MemoryRouter initialEntries={initialEntries}>
        <QueryClientProvider client={queryClient}>
          <RunsLiveProvider>{children}</RunsLiveProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );
  }

  return {
    queryClient,
    ...render(<RunsLiveProbe />, { wrapper: Wrapper }),
  };
}

describe("RunsLiveProvider", () => {
  beforeEach(() => {
    MockEventSource.reset();
    trackMock.mockReset();
    window.localStorage.clear();
    vi.restoreAllMocks();
    vi.stubGlobal("EventSource", MockEventSource);
    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "visible",
    });
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("stays offline and tracks storage-based disablement", async () => {
    window.localStorage.setItem("polisyos.runtime.disableLive", "true");

    renderRunsLive(["/runs"]);

    await waitFor(() =>
      expect(screen.getByTestId("runs-live-status")).toHaveTextContent(
        "offline",
      ),
    );
    expect(MockEventSource.instances).toHaveLength(0);
    expect(trackMock).toHaveBeenCalledWith("runs.live.disabled", {
      path: "/runs",
      reason: "storage",
    });
  });

  it("connects to the live stream, updates the cursor, and dedupes invalidations", async () => {
    const nowSpy = vi.spyOn(Date, "now").mockReturnValue(1000);
    const { queryClient } = renderRunsLive(["/runs"]);
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.instances[0]?.url).toContain("/api/v1/runs/live");
    expect(MockEventSource.instances[0]?.withCredentials).toBe(true);

    act(() => {
      MockEventSource.instances[0]?.open();
    });

    await waitFor(() =>
      expect(screen.getByTestId("runs-live-status")).toHaveTextContent("live"),
    );

    act(() => {
      MockEventSource.instances[0]?.emit(
        "snapshot",
        { runs: [{ run_id: "run-1" }], type: "snapshot" },
        "cursor-1",
      );
      MockEventSource.instances[0]?.emit(
        "snapshot",
        { runs: [{ run_id: "run-2" }], type: "snapshot" },
        "cursor-1",
      );
    });

    await waitFor(() =>
      expect(screen.getByTestId("runs-live-cursor")).toHaveTextContent(
        "cursor-1",
      ),
    );
    expect(invalidateSpy).toHaveBeenCalledTimes(1);
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["runtime", "runs"],
    });
    expect(trackMock).toHaveBeenCalledWith("runs.live.connected", {
      path: "/runs",
    });

    nowSpy.mockRestore();
  });

  it("falls back to polling after heartbeat timeout and reconnects", async () => {
    vi.useFakeTimers();
    vi.spyOn(Math, "random").mockReturnValue(0);
    const view = renderRunsLive(["/runs"]);
    const { queryClient } = view;
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    act(() => {
      MockEventSource.instances[0]?.open();
    });

    expect(screen.getByTestId("runs-live-status")).toHaveTextContent("live");

    await act(async () => {
      await vi.advanceTimersByTimeAsync(RUNS_LIVE_HEARTBEAT_MS * 2);
    });

    expect(screen.getByTestId("runs-live-status")).toHaveTextContent("polling");
    expect(MockEventSource.instances[0]?.close).toHaveBeenCalled();
    expect(trackMock).toHaveBeenCalledWith("runs.live.heartbeat_timeout", {
      path: "/runs",
    });

    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "hidden",
    });

    await act(async () => {
      await vi.advanceTimersByTimeAsync(RUNS_LIVE_RETRY_MS);
      await vi.advanceTimersByTimeAsync(
        RUN_ACTIVE_REFETCH_MS - RUNS_LIVE_RETRY_MS,
      );
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["runtime", "runs"],
    });

    Object.defineProperty(document, "visibilityState", {
      configurable: true,
      value: "visible",
    });
    act(() => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    expect(MockEventSource.instances).toHaveLength(2);
    expect(MockEventSource.instances[1]?.url).toContain("/api/v1/runs/live");
    expect(trackMock).toHaveBeenCalledWith("runs.live.reconnect_scheduled", {
      cursor: null,
      delayMs: RUNS_LIVE_RETRY_MS,
      path: "/runs",
      retryAttempt: 1,
    });

    view.unmount();
  });
});
