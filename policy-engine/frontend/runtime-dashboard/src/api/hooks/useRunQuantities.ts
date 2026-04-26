import {
  queryOptions,
  useQuery,
  useSuspenseQuery,
} from "@tanstack/react-query";

import {
  toApiTemporalParams,
  type TemporalScope,
} from "@/app/providers/temporal-scope";
import { useMaybeTemporalCursor } from "@/app/providers/useTemporalCursor";
import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { runQuantitiesSchema } from "../validators";

async function fetchRunQuantities(
  runId: string,
  temporalScope?: TemporalScope | null,
) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/runs/{run_id}/quantities",
    {
      params: {
        path: {
          run_id: runId,
        },
        query: toApiTemporalParams(temporalScope),
      },
    },
  );

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to load quantities for ${runId}`,
    );
  }

  const parsed = runQuantitiesSchema.parse(data);
  return {
    ...parsed,
    entries: parsed.entries ?? [],
    quantities: parsed.quantities ?? [],
  };
}

export function runQuantitiesQueryOptions(
  runId: string,
  temporalScope?: TemporalScope | null,
) {
  return queryOptions({
    queryKey: queryKeys.runQuantities(runId, temporalScope),
    queryFn: () => fetchRunQuantities(runId, temporalScope),
  });
}

export function useRunQuantities(runId: string | undefined, enabled = true) {
  const temporalCursor = useMaybeTemporalCursor();
  const temporalScope = temporalCursor?.committedScope ?? null;
  return useQuery({
    ...runQuantitiesQueryOptions(runId ?? "unknown", temporalScope),
    enabled: Boolean(runId) && enabled,
  });
}

export function useSuspenseRunQuantities(runId: string) {
  const temporalCursor = useMaybeTemporalCursor();
  return useSuspenseQuery(
    runQuantitiesQueryOptions(runId, temporalCursor?.committedScope ?? null),
  );
}
