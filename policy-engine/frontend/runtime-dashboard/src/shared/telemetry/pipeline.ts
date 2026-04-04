import { readActiveRouteTelemetryContext } from "@/shared/telemetry/routeContext";

export type TelemetryPayload = Record<string, unknown>;
export type TelemetryEvent = {
  name: string;
  payload?: TelemetryPayload;
  timestamp: number;
};

const TELEMETRY_ENDPOINT =
  import.meta.env.VITE_TELEMETRY_BEACON_URL?.trim() || "";
const TELEMETRY_RELEASE = import.meta.env.VITE_SENTRY_RELEASE?.trim() || "";

function getCurrentPath() {
  if (typeof window === "undefined") {
    return undefined;
  }
  return `${window.location.pathname}${window.location.search}${window.location.hash}`;
}

function isTelemetryTestHarness() {
  return (
    typeof window !== "undefined" && window.__RUNTIME_DASHBOARD_TEST__ === true
  );
}

export function readTelemetryRelease() {
  return TELEMETRY_RELEASE || undefined;
}

export function buildTelemetryEvent(event: TelemetryEvent): TelemetryEvent {
  const routeContext = readActiveRouteTelemetryContext();

  return {
    ...event,
    payload: {
      fullPath: routeContext.fullPath,
      path: getCurrentPath(),
      release: readTelemetryRelease(),
      routeId: routeContext.routeId,
      viewTimingSource: routeContext.viewTimingSource,
      visibilityState:
        typeof document === "undefined" ? undefined : document.visibilityState,
      workspace: routeContext.workspace,
      ...event.payload,
    },
  };
}

export function emitTelemetry(event: TelemetryEvent) {
  const nextEvent = buildTelemetryEvent(event);

  if (
    import.meta.env.DEV &&
    !import.meta.env.VITEST &&
    !isTelemetryTestHarness()
  ) {
    console.warn("[telemetry]", nextEvent);
  }

  if (!TELEMETRY_ENDPOINT || typeof navigator === "undefined") {
    return nextEvent;
  }

  const body = JSON.stringify(nextEvent);
  if (
    typeof navigator.sendBeacon === "function" &&
    navigator.sendBeacon(TELEMETRY_ENDPOINT, body)
  ) {
    return nextEvent;
  }

  if (typeof fetch === "function") {
    void fetch(TELEMETRY_ENDPOINT, {
      body,
      headers: {
        "content-type": "application/json",
      },
      keepalive: true,
      method: "POST",
    }).catch(() => undefined);
  }

  return nextEvent;
}

export function trackTelemetry(name: string, payload?: TelemetryPayload) {
  return emitTelemetry({
    name,
    payload,
    timestamp: Date.now(),
  });
}
