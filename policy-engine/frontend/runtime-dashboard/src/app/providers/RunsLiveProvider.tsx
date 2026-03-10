import {
  createContext,
  type PropsWithChildren,
  useContext,
  useEffect,
  useEffectEvent,
  useMemo,
  useReducer,
  useRef,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";

import { getRealtimeClient } from "@/app/realtime/realtimeClient";
import {
  invalidateRunQueries,
  invalidateRunsRootQueries,
} from "@/app/realtime/runInvalidation";
import type { RealtimeSubscription } from "@/app/realtime/types";
import { useLiveAnnouncer } from "@/app/providers/LiveAnnouncerProvider";
import { useTelemetry } from "@/app/providers/TelemetryProvider";
import {
  readRunsLiveDisabledPreference,
  useRunsLivePreferenceStore,
} from "@/app/state/useRunsLivePreferenceStore";
import {
  LOGIN_PATH,
  RUN_ACTIVE_REFETCH_MS,
  RUNS_LIVE_HEARTBEAT_MS,
  RUNS_LIVE_INVALIDATE_DEDUPE_MS,
  RUNS_LIVE_RETRY_MS,
} from "@/lib/constants";
import {
  initialRunsLiveState,
  parseRunsLiveEvent,
  reduceRunsLiveState,
  shouldInvalidateRunsForEvent,
  type RunsLiveStatus,
} from "@/app/providers/runsLiveMachine";

type RunsLiveContextValue = {
  cursor: string | null;
  lastEventAt: number | null;
  status: RunsLiveStatus;
};

const RunsLiveContext = createContext<RunsLiveContextValue | null>(null);
const RUNS_LIVE_DISABLED =
  import.meta.env.VITE_DISABLE_RUNS_LIVE?.trim() === "true";

export function RunsLiveProvider({ children }: PropsWithChildren) {
  const location = useLocation();
  const queryClient = useQueryClient();
  const { announce } = useLiveAnnouncer();
  const { track } = useTelemetry();
  const disableLivePreference = useRunsLivePreferenceStore(
    (state) => state.disableLive,
  );
  const [state, dispatch] = useReducer(
    reduceRunsLiveState,
    initialRunsLiveState,
  );
  const stateRef = useRef(initialRunsLiveState);
  const lastInvalidatedAtRef = useRef<number>(0);
  const announceLiveStatus = useEffectEvent((message: string) => {
    announce(message, "polite");
  });

  useEffect(() => {
    stateRef.current = state;
  }, [state]);

  useEffect(() => {
    const liveDisabled =
      RUNS_LIVE_DISABLED ||
      disableLivePreference ||
      readRunsLiveDisabledPreference();
    if (
      location.pathname.startsWith(LOGIN_PATH) ||
      typeof window === "undefined" ||
      liveDisabled
    ) {
      if (liveDisabled) {
        track("runs.live.disabled", {
          path: location.pathname,
          reason: RUNS_LIVE_DISABLED ? "env" : "storage",
        });
      }
      dispatch({ type: "offline" });
      return;
    }

    let closed = false;
    let heartbeatTimer: number | undefined;
    let pollingTimer: number | undefined;
    let reconnectTimer: number | undefined;
    let retryAttempt = 0;
    let subscription: RealtimeSubscription | null = null;
    const transport = getRealtimeClient();

    const invalidateRuns = () => {
      const now = Date.now();
      if (now - lastInvalidatedAtRef.current < RUNS_LIVE_INVALIDATE_DEDUPE_MS) {
        return;
      }
      lastInvalidatedAtRef.current = now;
      void invalidateRunsRootQueries(queryClient);
    };
    const invalidateRun = (runId: string) => {
      void invalidateRunQueries(queryClient, runId);
    };

    const clearTimers = () => {
      if (heartbeatTimer) {
        window.clearTimeout(heartbeatTimer);
      }
      if (pollingTimer) {
        window.clearInterval(pollingTimer);
      }
      if (reconnectTimer) {
        window.clearTimeout(reconnectTimer);
      }
    };

    const scheduleReconnect = () => {
      if (closed) {
        return;
      }
      const nextRetryAttempt = retryAttempt + 1;
      const jitter = Math.round(Math.random() * 250);
      const delay =
        Math.min(30_000, RUNS_LIVE_RETRY_MS * 2 ** retryAttempt) + jitter;
      retryAttempt = nextRetryAttempt;

      reconnectTimer = window.setTimeout(() => {
        if (document.visibilityState === "hidden") {
          dispatch({ type: "stream-error", retryAttempt });
          scheduleReconnect();
          return;
        }
        connect();
      }, delay);
      track("runs.live.reconnect_scheduled", {
        cursor: stateRef.current.cursor,
        delayMs: delay,
        path: location.pathname,
        retryAttempt,
      });
    };

    const startPolling = () => {
      if (pollingTimer) {
        return;
      }
      dispatch({ type: "polling-started" });
      pollingTimer = window.setInterval(invalidateRuns, RUN_ACTIVE_REFETCH_MS);
    };

    const armHeartbeat = () => {
      if (heartbeatTimer) {
        window.clearTimeout(heartbeatTimer);
      }
      heartbeatTimer = window.setTimeout(() => {
        track("runs.live.heartbeat_timeout", {
          path: location.pathname,
        });
        dispatch({ type: "heartbeat-timeout", now: Date.now() });
        subscription?.close();
        subscription = null;
        startPolling();
        scheduleReconnect();
      }, RUNS_LIVE_HEARTBEAT_MS * 2);
    };

    const connect = () => {
      if (closed) {
        return;
      }
      if (typeof EventSource === "undefined") {
        track("runs.live.eventsource_unavailable", { path: location.pathname });
        startPolling();
        return;
      }

      if (pollingTimer) {
        window.clearInterval(pollingTimer);
        pollingTimer = undefined;
      }

      dispatch({ type: "connect", retryAttempt });
      subscription = transport.subscribe(
        {
          channel: "runs.global",
          cursor: stateRef.current.cursor,
        },
        {
          onOpen: () => {
            retryAttempt = 0;
            dispatch({ type: "stream-open" });
            armHeartbeat();
            announceLiveStatus("Live updates connected.");
            track("runs.live.connected", { path: location.pathname });
          },
          onMessage: (event) => {
            const parsedEvent = parseRunsLiveEvent({
              data: event.data,
              lastEventId: event.lastEventId,
            });
            dispatch({
              type: "stream-event",
              event: parsedEvent,
              now: Date.now(),
            });
            armHeartbeat();
            if (parsedEvent.runId) {
              invalidateRun(parsedEvent.runId);
              if (parsedEvent.kind === "run.status" && parsedEvent.status) {
                announceLiveStatus(
                  `Run ${parsedEvent.runId} status changed to ${parsedEvent.status}.`,
                );
              }
              if (parsedEvent.kind === "governance.waiting") {
                announceLiveStatus(
                  `Run ${parsedEvent.runId} is waiting for a human decision.`,
                );
              }
            }
            if (
              shouldInvalidateRunsForEvent(parsedEvent) &&
              (parsedEvent.kind === "runs.snapshot" ||
                parsedEvent.kind === "run.status" ||
                parsedEvent.kind === "governance.waiting" ||
                parsedEvent.terminal === true)
            ) {
              invalidateRuns();
            }
          },
          onError: () => {
            if (closed) {
              return;
            }
            track("runs.live.error", {
              path: location.pathname,
            });
            dispatch({ type: "stream-error", retryAttempt: retryAttempt + 1 });
            subscription?.close();
            subscription = null;
            startPolling();
            announceLiveStatus("Live updates degraded. Polling fallback enabled.");
            scheduleReconnect();
          },
        },
      );
    };

    const handleVisibilityChange = () => {
      if (
        document.visibilityState === "visible" &&
        stateRef.current.status !== "live"
      ) {
        connect();
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);
    connect();

    return () => {
      closed = true;
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      clearTimers();
      subscription?.close();
    };
  }, [disableLivePreference, location.pathname, queryClient, track]);

  const value = useMemo<RunsLiveContextValue>(
    () => ({
      status: state.status,
      cursor: state.cursor,
      lastEventAt: state.lastHeartbeatAt,
    }),
    [state.cursor, state.lastHeartbeatAt, state.status],
  );

  return (
    <RunsLiveContext.Provider value={value}>
      {children}
    </RunsLiveContext.Provider>
  );
}

export function useRunsLiveStatus() {
  const context = useContext(RunsLiveContext);
  if (!context) {
    throw new Error("useRunsLiveStatus must be used within a RunsLiveProvider");
  }
  return context;
}
