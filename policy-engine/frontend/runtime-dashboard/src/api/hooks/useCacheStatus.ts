import { useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";

export type CacheStatusResponse = components["schemas"]["CacheStatusResponse"];

async function fetchCacheStatus(): Promise<CacheStatusResponse> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/control/data/cache",
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, "Failed to load cache status");
  }
  return data as CacheStatusResponse;
}

export function useCacheStatus() {
  return useQuery({
    queryKey: queryKeys.cacheStatus(),
    queryFn: fetchCacheStatus,
  });
}
