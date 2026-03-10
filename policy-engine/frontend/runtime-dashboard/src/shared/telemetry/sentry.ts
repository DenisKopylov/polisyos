import * as Sentry from "@sentry/react";

import {
  readActiveRouteTelemetryContext,
  type RouteTelemetryContext,
} from "@/shared/telemetry/routeContext";
import { readTelemetryRelease } from "@/shared/telemetry/pipeline";

type SentryLogLevel = "debug" | "info" | "warning" | "error";

const SENTRY_DSN = import.meta.env.VITE_SENTRY_DSN?.trim() || "";
const SENTRY_ENVIRONMENT =
  import.meta.env.VITE_SENTRY_ENVIRONMENT?.trim() ||
  import.meta.env.MODE ||
  "development";

let sentryInitialized = false;

function isSentryEnabled() {
  return (
    Boolean(SENTRY_DSN) &&
    import.meta.env.PROD &&
    !import.meta.env.VITEST &&
    typeof window !== "undefined" &&
    window.__RUNTIME_DASHBOARD_TEST__ !== true
  );
}

function applyRouteScope(scope: Sentry.Scope, route: RouteTelemetryContext) {
  scope.setTag("routeId", route.routeId);
  scope.setTag("workspace", route.workspace);
  scope.setContext("route", {
    fullPath: route.fullPath,
    path: route.path,
    routeId: route.routeId,
    viewStartedAt: route.viewStartedAt,
    viewTimingSource: route.viewTimingSource,
    workspace: route.workspace,
  });
}

export function initializeSentry() {
  if (!isSentryEnabled() || sentryInitialized) {
    return;
  }

  Sentry.init({
    attachStacktrace: true,
    dsn: SENTRY_DSN,
    enabled: true,
    environment: SENTRY_ENVIRONMENT,
    release: readTelemetryRelease(),
    sendDefaultPii: false,
  });

  sentryInitialized = true;
}

export function addSentryBreadcrumb({
  category,
  data,
  level,
  message,
}: {
  category: string;
  data?: Record<string, unknown>;
  level?: SentryLogLevel;
  message: string;
}) {
  if (!sentryInitialized) {
    return;
  }

  const route = readActiveRouteTelemetryContext();
  Sentry.addBreadcrumb({
    category,
    data: {
      fullPath: route.fullPath,
      routeId: route.routeId,
      workspace: route.workspace,
      ...data,
    },
    level,
    message,
    timestamp: Date.now() / 1_000,
    type: "default",
  });
}

export function captureSentryException(
  error: unknown,
  extra?: {
    extra?: Record<string, unknown>;
    level?: SentryLogLevel;
    tags?: Record<string, string | null | undefined>;
  },
) {
  if (!sentryInitialized) {
    return;
  }

  const route = readActiveRouteTelemetryContext();
  Sentry.withScope((scope) => {
    applyRouteScope(scope, route);
    if (extra?.level) {
      scope.setLevel(extra.level);
    }
    if (extra?.extra) {
      for (const [key, value] of Object.entries(extra.extra)) {
        scope.setExtra(key, value);
      }
    }
    if (extra?.tags) {
      for (const [key, value] of Object.entries(extra.tags)) {
        if (value != null) {
          scope.setTag(key, value);
        }
      }
    }
    Sentry.captureException(
      error instanceof Error ? error : new Error(String(error)),
    );
  });
}
