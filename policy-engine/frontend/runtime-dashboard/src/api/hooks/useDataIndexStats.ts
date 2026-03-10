import {
  queryOptions,
  useQuery,
  useSuspenseQuery,
} from "@tanstack/react-query";

import { RUNS_SAMPLE_STALE_MS } from "../../lib/constants";
import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";

export type IndexStatsResponse = components["schemas"]["IndexStatsResponse"];

export async function fetchDataIndexStats(): Promise<IndexStatsResponse> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/control/data/index/stats",
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      "Failed to load data index stats",
    );
  }
  return data as IndexStatsResponse;
}

export function dataIndexStatsQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.dataIndexStats(),
    queryFn: fetchDataIndexStats,
    staleTime: RUNS_SAMPLE_STALE_MS,
  });
}

export function useDataIndexStats() {
  return useQuery(dataIndexStatsQueryOptions());
}

export function useSuspenseDataIndexStats() {
  return useSuspenseQuery(dataIndexStatsQueryOptions());
}
