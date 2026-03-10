import {
  queryOptions,
  useQuery,
  useSuspenseQuery,
} from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { runLineageSchema } from "../validators";

async function fetchRunLineage(runId: string) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/runs/{run_id}/lineage",
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
      `Failed to load lineage for ${runId}`,
    );
  }

  const parsed = runLineageSchema.parse(data);
  return {
    ...parsed,
    lineage: {
      ...parsed.lineage,
      nodes: parsed.lineage.nodes ?? [],
      edges: parsed.lineage.edges ?? [],
      root_artifact_ids: parsed.lineage.root_artifact_ids ?? [],
      missing_artifact_ids: parsed.lineage.missing_artifact_ids ?? [],
      corrupted_artifact_ids: parsed.lineage.corrupted_artifact_ids ?? [],
    },
  };
}

export function runLineageQueryOptions(runId: string) {
  return queryOptions({
    queryKey: queryKeys.runLineage(runId),
    queryFn: () => fetchRunLineage(runId),
  });
}

export function useRunLineage(runId: string | undefined, enabled = true) {
  return useQuery({
    ...runLineageQueryOptions(runId ?? "unknown"),
    enabled: Boolean(runId) && enabled,
  });
}

export function useSuspenseRunLineage(runId: string) {
  return useSuspenseQuery(runLineageQueryOptions(runId));
}
