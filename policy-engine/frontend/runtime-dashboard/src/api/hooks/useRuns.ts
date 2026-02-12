import { useQuery } from "@tanstack/react-query";

import { RUNS_DEFAULT_LIMIT } from "../../lib/constants";
import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { runsListSchema } from "../validators";

export type RunsFilters = {
  limit?: number;
  cursor?: string;
  status?: string;
  from_ts?: string;
  to_ts?: string;
};

async function fetchRuns(filters: RunsFilters) {
  const { data, error, response } = await runtimeApiClient.GET("/api/v1/runs", {
    params: {
      query: {
        limit: filters.limit ?? RUNS_DEFAULT_LIMIT,
        cursor: filters.cursor ?? null,
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

export function useRuns(filters: RunsFilters) {
  return useQuery({
    queryKey: queryKeys.runs(filters),
    queryFn: () => fetchRuns(filters),
  });
}
