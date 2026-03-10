import {
  dispatchRouteLoaderEvent,
  ROUTE_LOADER_EVENT_NAME,
  type RouteLoaderEventDetail,
} from "@/shared/telemetry/routeLoaderEvents";
import { createLogger } from "@/shared/telemetry/logger";

export { ROUTE_LOADER_EVENT_NAME };
export type { RouteLoaderEventDetail };

const logger = createLogger({
  tags: {
    area: "route-loader",
  },
});

function markPerformance(label: string) {
  if (typeof performance === "undefined") {
    return;
  }
  performance.mark(label);
}

export async function instrumentRouteLoader<T>(
  routeId: string,
  load: () => Promise<T>,
) {
  const startedAt =
    typeof performance === "undefined" ? Date.now() : performance.now();
  markPerformance(`${routeId}:loader:start`);

  try {
    const result = await load();
    const finishedAt =
      typeof performance === "undefined" ? Date.now() : performance.now();
    markPerformance(`${routeId}:loader:ready`);
    logger.info({
      event: "route.loader.ready",
      message: `Route loader ${routeId} ready`,
      tags: {
        durationMs: Math.round(finishedAt - startedAt),
        routeId,
      },
    });
    dispatchRouteLoaderEvent({
      durationMs: Math.round(finishedAt - startedAt),
      routeId,
      status: "ready",
    });
    return result;
  } catch (error) {
    const finishedAt =
      typeof performance === "undefined" ? Date.now() : performance.now();
    markPerformance(`${routeId}:loader:error`);
    logger.error({
      error,
      event: "route.loader.error",
      message: `Route loader ${routeId} failed`,
      tags: {
        durationMs: Math.round(finishedAt - startedAt),
        routeId,
      },
    });
    dispatchRouteLoaderEvent({
      durationMs: Math.round(finishedAt - startedAt),
      error: error instanceof Error ? error.message : String(error),
      routeId,
      status: "error",
    });
    throw error;
  }
}
