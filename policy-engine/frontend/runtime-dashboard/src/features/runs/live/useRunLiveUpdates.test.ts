import { renderHook, waitFor } from "@testing-library/react";

import { resetRunsLivePreferenceStore } from "@/app/state/useRunsLivePreferenceStore";
import { createQueryHookWrapper } from "@/test/queryHook";

const { invalidateRunQueriesMock, parseRunsLiveEventMock, subscribeMock } =
  vi.hoisted(() => ({
    invalidateRunQueriesMock: vi.fn(),
    parseRunsLiveEventMock: vi.fn(),
    subscribeMock: vi.fn(),
  }));

vi.mock("@/app/realtime/runInvalidation", () => ({
  invalidateRunQueries: (...args: unknown[]) =>
    invalidateRunQueriesMock(...args),
}));

vi.mock("@/app/providers/runsLiveMachine", () => ({
  parseRunsLiveEvent: (...args: unknown[]) => parseRunsLiveEventMock(...args),
}));

vi.mock("@/app/realtime/sseTransport", () => ({
  getSseRealtimeTransport: () => ({
    subscribe: (...args: unknown[]) => subscribeMock(...args),
  }),
}));

import { useRunLiveUpdates } from "@/features/runs/live/useRunLiveUpdates";

const EventSourceMock = Object.assign(
  function EventSourceMock(
    _url?: string | URL,
    _eventSourceInitDict?: EventSourceInit,
  ) {
    return undefined;
  },
  {
    CONNECTING: 0,
    OPEN: 1,
    CLOSED: 2,
  },
);

describe("useRunLiveUpdates", () => {
  beforeEach(() => {
    invalidateRunQueriesMock.mockReset();
    parseRunsLiveEventMock.mockReset();
    resetRunsLivePreferenceStore();
    subscribeMock.mockReset();
    localStorage.clear();
    globalThis.EventSource = EventSourceMock as unknown as typeof EventSource;
  });

  it("returns true only when a run id exists and the live transport connects", async () => {
    let handlers:
      | {
          onError?: (error: Event) => void;
          onMessage?: (event: MessageEvent<string>) => void;
          onOpen?: () => void;
        }
      | undefined;
    subscribeMock.mockImplementation((_request, nextHandlers) => {
      handlers = nextHandlers;
      nextHandlers.onOpen?.();
      return {
        close: vi.fn(),
      };
    });

    let view = renderHook(() => useRunLiveUpdates("run-1"), {
      wrapper: createQueryHookWrapper(),
    });
    await waitFor(() => {
      expect(view.result.current.isLiveConnected).toBe(true);
    });
    expect(subscribeMock).toHaveBeenCalledTimes(1);

    parseRunsLiveEventMock.mockReturnValue({
      kind: "run.snapshot",
      runId: "run-1",
    });
    handlers?.onMessage?.({
      data: '{"kind":"runs"}',
      lastEventId: "evt-1",
    } as MessageEvent<string>);
    await waitFor(() => {
      expect(invalidateRunQueriesMock).toHaveBeenCalledWith(
        expect.anything(),
        "run-1",
      );
    });

    view.unmount();

    view = renderHook(() => useRunLiveUpdates(undefined), {
      wrapper: createQueryHookWrapper(),
    });
    expect(view.result.current.isLiveConnected).toBe(false);
    expect(subscribeMock).toHaveBeenCalledTimes(1);

    view.unmount();
    subscribeMock.mockImplementation((_request, nextHandlers) => {
      nextHandlers.onError?.(new Event("error"));
      return {
        close: vi.fn(),
      };
    });

    view = renderHook(() => useRunLiveUpdates("run-1"), {
      wrapper: createQueryHookWrapper(),
    });
    expect(view.result.current.isLiveConnected).toBe(false);
  });
});
