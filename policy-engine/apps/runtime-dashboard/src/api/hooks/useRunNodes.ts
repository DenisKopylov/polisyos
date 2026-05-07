import {
  queryOptions,
  useQuery,
  useSuspenseQuery,
} from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { runNodesSchema } from "../validators";

async function fetchRunNodes(runId: string) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/runs/{run_id}/nodes",
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
      `Failed to load nodes for ${runId}`,
    );
  }

  const parsed = runNodesSchema.parse(data);
  return {
    ...parsed,
    nodes: parsed.nodes ?? [],
  };
}

export function runNodesQueryOptions(runId: string) {
  return queryOptions({
    queryKey: queryKeys.runNodes(runId),
    queryFn: () => fetchRunNodes(runId),
  });
}

export function useRunNodes(runId: string | undefined, enabled = true) {
  return useQuery({
    ...runNodesQueryOptions(runId ?? "unknown"),
    enabled: Boolean(runId) && enabled,
  });
}

export function useSuspenseRunNodes(runId: string) {
  return useSuspenseQuery(runNodesQueryOptions(runId));
}
