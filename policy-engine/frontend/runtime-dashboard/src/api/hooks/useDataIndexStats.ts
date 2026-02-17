import { useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";

export type IndexStatsResponse = components["schemas"]["IndexStatsResponse"];

async function fetchDataIndexStats(): Promise<IndexStatsResponse> {
  const { data, error, response } = await runtimeApiClient.GET("/api/v1/control/data/index/stats");
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, "Failed to load data index stats");
  }
  return data as IndexStatsResponse;
}

export function useDataIndexStats() {
  return useQuery({
    queryKey: queryKeys.dataIndexStats(),
    queryFn: fetchDataIndexStats,
    staleTime: 10_000,
  });
}
