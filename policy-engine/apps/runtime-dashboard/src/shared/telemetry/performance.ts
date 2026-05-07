import {
  emitTelemetry,
  type TelemetryPayload,
} from "@/shared/telemetry/pipeline";
import { readActiveRouteTelemetryContext } from "@/shared/telemetry/routeContext";
import { addSentryBreadcrumb } from "@/shared/telemetry/sentry";

type UiLatencyMetric =
  | "time_to_causal_ms"
  | "time_to_decision_ms"
  | "time_to_insight_ms";

const measuredLatencyKeys = new Set<string>();

function readNavigationStart() {
  if (typeof performance === "undefined") {
    return 0;
  }

  const navigationEntry = performance.getEntriesByType("navigation")[0] as
    | PerformanceNavigationTiming
    | undefined;

  return navigationEntry?.startTime ?? 0;
}

function resolveLatencyStart() {
  const route = readActiveRouteTelemetryContext();
  if (route.viewStartedAt > 0) {
    return {
      startedAt: route.viewStartedAt,
      startSource: route.viewTimingSource,
    };
  }

  return {
    startedAt: readNavigationStart(),
    startSource: "hard-navigation" as const,
  };
}

export function markUiMilestone(
  name: string,
  payload?: Record<string, unknown>,
) {
  if (typeof performance !== "undefined") {
    performance.mark(name);
  }

  addSentryBreadcrumb({
    category: "ui.milestone",
    data: payload,
    level: "info",
    message: name,
  });
}

export function measureUiLatency({
  context,
  endMark,
  metric,
}: {
  context?: TelemetryPayload;
  endMark?: string;
  metric: UiLatencyMetric;
}) {
  if (typeof performance === "undefined") {
    return undefined;
  }

  if (endMark) {
    performance.mark(endMark);
  }

  const route = readActiveRouteTelemetryContext();
  const dedupeKey = `${metric}:${route.fullPath}:${route.viewStartedAt}`;
  if (measuredLatencyKeys.has(dedupeKey)) {
    return undefined;
  }
  measuredLatencyKeys.add(dedupeKey);

  const { startedAt, startSource } = resolveLatencyStart();
  const durationMs = Math.max(0, Math.round(performance.now() - startedAt));
  const eventName =
    metric === "time_to_decision_ms"
      ? "perf.time_to_decision"
      : metric === "time_to_causal_ms"
        ? "perf.time_to_causal"
        : "perf.time_to_insight";

  emitTelemetry({
    name: eventName,
    payload: {
      durationMs,
      metric,
      startSource,
      ...context,
    },
    timestamp: Date.now(),
  });

  addSentryBreadcrumb({
    category: "performance",
    data: {
      durationMs,
      metric,
      routeId: route.routeId,
      startSource,
      workspace: route.workspace,
      ...context,
    },
    level: "info",
    message: eventName,
  });

  return durationMs;
}
