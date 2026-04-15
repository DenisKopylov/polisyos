import {
  queryOptions,
  useQuery,
  useSuspenseQuery,
} from "@tanstack/react-query";

import {
  RUNS_DEFAULT_LIMIT,
  RUNS_SAMPLE_LIMIT,
  RUNS_SAMPLE_STALE_MS,
} from "../../lib/constants";
import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { runsListSchema } from "../validators";

export type RunsFilters = {
  limit?: number;
  cursor?: string;
  q?: string;
  status?: string;
  from_ts?: string;
  to_ts?: string;
};

export async function fetchRuns(filters: RunsFilters) {
  const { data, error, response } = await runtimeApiClient.GET("/api/v1/runs", {
    params: {
      query: {
        limit: filters.limit ?? RUNS_DEFAULT_LIMIT,
        cursor: filters.cursor ?? null,
        q: filters.q ?? null,
        status: filters.status ?? null,
        from_ts: filters.from_ts ?? null,
        to_ts: filters.to_ts ?? null,
      },
    },
  });

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, "Failed to load runs list");
  }
  const parsed = runsListSchema.parse(data);
  return {
    ...parsed,
    runs: parsed.runs ?? [],
  };
}

export function runsQueryOptions(filters: RunsFilters) {
  const isSampleQuery =
    (filters.limit ?? RUNS_DEFAULT_LIMIT) === RUNS_SAMPLE_LIMIT &&
    !filters.cursor &&
    !filters.q &&
    !filters.status &&
    !filters.from_ts &&
    !filters.to_ts;

  return queryOptions({
    queryKey: queryKeys.runs(filters),
    queryFn: () => fetchRuns(filters),
    staleTime: isSampleQuery ? RUNS_SAMPLE_STALE_MS : 30_000,
  });
}

export function useRuns(filters: RunsFilters) {
  return useQuery(runsQueryOptions(filters));
}

export function useSuspenseRuns(filters: RunsFilters) {
  return useSuspenseQuery(runsQueryOptions(filters));
}
