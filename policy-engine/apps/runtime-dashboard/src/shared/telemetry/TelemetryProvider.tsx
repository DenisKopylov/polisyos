import {
  createContext,
  type PropsWithChildren,
  useContext,
  useEffect,
  useMemo,
  useRef,
} from "react";
import type { QueryCacheNotifyEvent } from "@tanstack/react-query";
import { onCLS, onINP, onLCP, onTTFB, type Metric } from "web-vitals";

import { queryClient } from "@/api/queryClient";
import {
  ROUTE_LOADER_EVENT_NAME,
  type RouteLoaderEventDetail,
} from "@/shared/telemetry/routeLoaderEvents";
import { initializeSentry } from "@/shared/telemetry/sentry";
import {
  emitTelemetry,
  trackTelemetry,
  type TelemetryPayload,
} from "@/shared/telemetry/pipeline";
import { markUiMilestone } from "@/shared/telemetry/performance";

type TelemetryContextValue = {
  track: (name: string, payload?: TelemetryPayload) => void;
};

const TelemetryContext = createContext<TelemetryContextValue | null>(null);

function extractErrorMessage(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }
  if (typeof error === "string") {
    return error;
  }
  return "unknown";
}

function getQueryActionType(event: QueryCacheNotifyEvent) {
  if (event.type !== "updated") {
    return "";
  }
  const action = event.action as { type?: unknown };
  return typeof action.type === "string" ? action.type : "";
}

export function TelemetryProvider({ children }: PropsWithChildren) {
  const inflightQueriesRef = useRef(new Map<string, number>());

  const trackWebVital = useMemo(
    () => (name: string, metric: Metric) => {
      emitTelemetry({
        name,
        payload: {
          delta: metric.delta,
          metricId: metric.id,
          navigationType: metric.navigationType,
          rating: metric.rating,
          value: metric.value,
        },
        timestamp: Date.now(),
      });
    },
    [],
  );

  const value = useMemo<TelemetryContextValue>(
    () => ({
      track: trackTelemetry,
    }),
    [],
  );

  useEffect(() => {
    initializeSentry();
  }, []);

  useEffect(() => {
    onCLS((metric) => trackWebVital("web-vitals.cls", metric));
    onINP((metric) => trackWebVital("web-vitals.inp", metric));
    onLCP((metric) => trackWebVital("web-vitals.lcp", metric));
    onTTFB((metric) => trackWebVital("web-vitals.ttfb", metric));
    void import("web-vitals").then((module) => {
      const maybeOnFID = (
        module as typeof module & {
          onFID?: (callback: (metric: Metric) => void) => void;
        }
      ).onFID;
      maybeOnFID?.((metric) => trackWebVital("web-vitals.fid_legacy", metric));
    });
  }, [trackWebVital]);

  useEffect(() => {
    return queryClient.getQueryCache().subscribe((event) => {
      const actionType = getQueryActionType(event);
      if (!actionType) {
        return;
      }

      const queryHash = event.query.queryHash;
      if (actionType === "fetch") {
        inflightQueriesRef.current.set(queryHash, performance.now());
        return;
      }

      if (actionType !== "success" && actionType !== "error") {
        return;
      }

      const startedAt = inflightQueriesRef.current.get(queryHash);
      inflightQueriesRef.current.delete(queryHash);
      const durationMs =
        startedAt == null
          ? undefined
          : Math.round(performance.now() - startedAt);

      if (actionType === "success") {
        value.track("query.fetch.success", {
          durationMs,
          observers: event.query.getObserversCount(),
          queryHash,
        });
        return;
      }

      value.track("query.fetch.error", {
        durationMs,
        error: extractErrorMessage(event.query.state.error),
        failureCount: event.query.state.fetchFailureCount,
        observers: event.query.getObserversCount(),
        queryHash,
      });
    });
  }, [value]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const handleRouteLoaderEvent = (event: Event) => {
      const detail = (event as CustomEvent<RouteLoaderEventDetail>).detail;
      if (!detail) {
        return;
      }

      value.track(detail.status === "ready" ? "loader.ready" : "loader.error", {
        durationMs: detail.durationMs,
        error: detail.error,
        routeId: detail.routeId,
      });
    };

    window.addEventListener(ROUTE_LOADER_EVENT_NAME, handleRouteLoaderEvent);
    return () =>
      window.removeEventListener(
        ROUTE_LOADER_EVENT_NAME,
        handleRouteLoaderEvent,
      );
  }, [value]);

  useEffect(() => {
    if (typeof performance === "undefined") {
      return;
    }

    const navigationEntry = performance.getEntriesByType("navigation")[0] as
      | PerformanceNavigationTiming
      | undefined;

    if (!navigationEntry) {
      return;
    }

    value.track("perf.navigation.sample", {
      domCompleteMs: Math.round(navigationEntry.domComplete),
      domInteractiveMs: Math.round(navigationEntry.domInteractive),
      loadEventEndMs: Math.round(navigationEntry.loadEventEnd),
      responseEndMs: Math.round(navigationEntry.responseEnd),
    });
  }, [value]);

  return (
    <TelemetryContext.Provider value={value}>
      {children}
    </TelemetryContext.Provider>
  );
}

export function useTelemetry() {
  const context = useContext(TelemetryContext);
  if (!context) {
    throw new Error("useTelemetry must be used within TelemetryProvider");
  }
  return context;
}

export function useTelemetryReadyMark(
  markName: string,
  payload?: TelemetryPayload,
) {
  const { track } = useTelemetry();
  const payloadRef = useRef(payload);

  useEffect(() => {
    payloadRef.current = payload;
  }, [payload]);

  useEffect(() => {
    markUiMilestone(`${markName}:ready`, payloadRef.current);

    track("ui.ready", {
      durationMs:
        typeof performance === "undefined"
          ? undefined
          : Math.round(performance.now()),
      mark: markName,
      ...payloadRef.current,
    });
  }, [markName, track]);
}
