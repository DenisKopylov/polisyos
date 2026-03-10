import {
  queryOptions,
  useQuery,
  useSuspenseQuery,
} from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { runAgentsSchema } from "../validators";

async function fetchRunAgents(runId: string) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/runs/{run_id}/agents",
    {
      params: {
        path: {
          run_id: runId,
        },
      },
    },
  );

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      `Failed to load run agents for ${runId}`,
    );
  }

  const parsed = runAgentsSchema.parse(data);
  return {
    ...parsed,
    pipeline: {
      ...parsed.pipeline,
      attempts: parsed.pipeline.attempts ?? [],
    },
  };
}

export function runAgentsQueryOptions(runId: string) {
  return queryOptions({
    queryKey: queryKeys.runAgents(runId),
    queryFn: () => fetchRunAgents(runId),
  });
}

export function useRunAgents(runId: string | undefined, enabled = true) {
  return useQuery({
    ...runAgentsQueryOptions(runId ?? "unknown"),
    enabled: Boolean(runId) && enabled,
  });
}

export function useSuspenseRunAgents(runId: string) {
  return useSuspenseQuery(runAgentsQueryOptions(runId));
}
