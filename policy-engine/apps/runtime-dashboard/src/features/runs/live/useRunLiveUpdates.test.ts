import { renderHook, waitFor } from "@testing-library/react";

import { queryKeys } from "@/api/queryKeys";
import { runDetailsSchema } from "@/api/validators";
import { resetRunsLivePreferenceStore } from "@/app/state/useRunsLivePreferenceStore";
import {
  createQueryHookHarness,
  createQueryHookWrapper,
} from "@/test/queryHook";

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

function runDetailsPayload(runId: string) {
  return runDetailsSchema.parse({
    meta: {
      request_id: "request-live-test",
      generated_at: "2026-10-22T10:00:00Z",
      source_kinds: ["core_run"],
    },
    temporal_scope: null,
    run: {
      run_id: runId,
      source_kind: "core_run",
      status: "running",
    },
  });
}

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
      runId: "stable-control-alias",
    });
    handlers?.onMessage?.({
      data: '{"kind":"runs"}',
      lastEventId: "evt-1",
    } as MessageEvent<string>);
    expect(invalidateRunQueriesMock).not.toHaveBeenCalled();

    parseRunsLiveEventMock.mockReturnValue({
      kind: "run.snapshot",
      runId: "run-1",
    });
    handlers?.onMessage?.({
      data: '{"kind":"runs"}',
      lastEventId: "evt-2",
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

  it.each([
    { routeRunId: "control-run-alias", coreRunId: "core-attempt-7" },
    { routeRunId: "run-1", coreRunId: "run-1" },
  ])(
    "keeps the alias subscription and invalidates only strict Core identity caches ($routeRunId)",
    async ({ routeRunId, coreRunId }) => {
      const harness = createQueryHookHarness();
      const invalidateQueries = vi.spyOn(
        harness.queryClient,
        "invalidateQueries",
      );
      harness.queryClient.setQueryData(
        queryKeys.run(routeRunId),
        runDetailsPayload(coreRunId),
      );
      let onMessage: ((event: MessageEvent<string>) => void) | undefined;
      subscribeMock.mockImplementation((request, handlers) => {
        expect(request).toEqual({ channel: "runs.byId", runId: routeRunId });
        onMessage = handlers.onMessage;
        return { close: vi.fn() };
      });
      parseRunsLiveEventMock.mockReturnValue({
        kind: "run.snapshot",
        runId: routeRunId,
      });

      const view = renderHook(() => useRunLiveUpdates(routeRunId), {
        wrapper: harness.wrapper,
      });
      onMessage?.({
        data: JSON.stringify({ run_id: routeRunId }),
        lastEventId: "evt-aliased",
      } as MessageEvent<string>);

      await waitFor(() => {
        expect(invalidateRunQueriesMock).toHaveBeenCalledWith(
          harness.queryClient,
          routeRunId,
        );
        expect(invalidateQueries).toHaveBeenCalledWith({
          queryKey: ["runtime", "run", coreRunId],
        });
      });
      expect(subscribeMock).toHaveBeenCalledTimes(1);
      view.unmount();
    },
  );

  it("does not invalidate a Core owner from a mismatched event or untyped cached details", async () => {
    const routeRunId = "control-run-alias";
    const harness = createQueryHookHarness();
    const invalidateQueries = vi.spyOn(
      harness.queryClient,
      "invalidateQueries",
    );
    harness.queryClient.setQueryData(queryKeys.run(routeRunId), {
      meta: {
        request_id: "request-live-test",
        generated_at: "2026-10-22T10:00:00Z",
        source_kinds: ["core_run"],
      },
      temporal_scope: null,
      run: {
        run_id: "other-owner-core",
        source_kind: "control_run",
        status: "running",
      },
    });
    let onMessage: ((event: MessageEvent<string>) => void) | undefined;
    subscribeMock.mockImplementation((_request, handlers) => {
      onMessage = handlers.onMessage;
      return { close: vi.fn() };
    });
    parseRunsLiveEventMock.mockReturnValue({
      kind: "run.snapshot",
      runId: "different-control-run",
    });

    const view = renderHook(() => useRunLiveUpdates(routeRunId), {
      wrapper: harness.wrapper,
    });
    onMessage?.({
      data: JSON.stringify({ run_id: "different-control-run" }),
      lastEventId: "evt-wrong-owner",
    } as MessageEvent<string>);

    await waitFor(() => expect(subscribeMock).toHaveBeenCalledTimes(1));
    expect(invalidateRunQueriesMock).not.toHaveBeenCalled();
    expect(invalidateQueries).not.toHaveBeenCalledWith({
      queryKey: ["runtime", "run", "other-owner-core"],
    });
    view.unmount();
  });
});
