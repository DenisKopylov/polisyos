export type RouteTelemetryContext = {
  fullPath: string;
  path: string;
  routeId: string;
  viewStartedAt: number;
  viewTimingSource: "hard-navigation" | "route-transition";
  workspace: string;
};

const DEFAULT_ROUTE_CONTEXT: RouteTelemetryContext = {
  fullPath: "/",
  path: "/",
  routeId: "unknown",
  viewStartedAt: 0,
  viewTimingSource: "hard-navigation",
  workspace: "unknown",
};

let activeRouteTelemetryContext = DEFAULT_ROUTE_CONTEXT;

export function readActiveRouteTelemetryContext() {
  return activeRouteTelemetryContext;
}

export function setActiveRouteTelemetryContext(
  nextContext: Omit<RouteTelemetryContext, "viewStartedAt" | "viewTimingSource"> &
    Partial<Pick<RouteTelemetryContext, "viewStartedAt" | "viewTimingSource">>,
) {
  activeRouteTelemetryContext = {
    ...activeRouteTelemetryContext,
    ...nextContext,
  };
}

export function setActiveRouteViewTiming(
  viewStartedAt: number,
  viewTimingSource: RouteTelemetryContext["viewTimingSource"],
) {
  activeRouteTelemetryContext = {
    ...activeRouteTelemetryContext,
    viewStartedAt,
    viewTimingSource,
  };
}
