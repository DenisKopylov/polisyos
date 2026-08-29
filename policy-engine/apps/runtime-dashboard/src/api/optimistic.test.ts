import { QueryClient } from "@tanstack/react-query";

import * as optimisticRunCache from "@/api/optimistic";
import { queryKeys } from "@/api/queryKeys";

describe("optimistic run cache", () => {
  it("does not fabricate RunSummary records for launch interaction state", () => {
    expect(Object.keys(optimisticRunCache)).not.toEqual(
      expect.arrayContaining([
        "applyOptimisticRunToCache",
        "buildLaunchedRunSummary",
        "createOptimisticRun",
        "createOptimisticRunDetails",
        "replaceOptimisticRunInCache",
      ]),
    );
  });

  it("keeps every acquisition authority cache untouched by every optimistic updater", () => {
    const queryClient = new QueryClient();
    const routeList = Object.freeze({ routes: ["owner-route"] });
    const routeDetail = Object.freeze({ route_id: "owner-route" });
    const growth = Object.freeze({ world_growth: "not_established" });
    const entries = [
      [queryKeys.runAcquisitionRoutes("run-1"), routeList],
      [queryKeys.runAcquisitionRoute("run-1", "owner-route"), routeDetail],
      [queryKeys.acquisitionGrowth(), growth],
    ] as const;
    for (const [key, value] of entries) queryClient.setQueryData(key, value);

    for (const update of Object.values(optimisticRunCache)) {
      expect(update).toEqual(expect.any(Function));
      (update as (...args: unknown[]) => unknown)(
        queryClient,
        "run-1",
        "promotion-1",
        "approved",
      );
    }

    for (const [key, value] of entries) {
      expect(queryClient.getQueryData(key)).toBe(value);
    }
  });
});
