export type RouteLoaderEventDetail = {
  durationMs: number;
  error?: string;
  routeId: string;
  status: "error" | "ready";
};

export const ROUTE_LOADER_EVENT_NAME = "runtime-dashboard:route-loader";

export function dispatchRouteLoaderEvent(detail: RouteLoaderEventDetail) {
  if (typeof window === "undefined") {
    return;
  }

  window.dispatchEvent(
    new CustomEvent<RouteLoaderEventDetail>(ROUTE_LOADER_EVENT_NAME, {
      detail,
    }),
  );
}
