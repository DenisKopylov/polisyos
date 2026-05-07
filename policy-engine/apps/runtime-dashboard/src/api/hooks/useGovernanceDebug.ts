import {
  queryOptions,
  useQuery,
  useSuspenseQuery,
} from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { governanceDebugSchema } from "../validators";

async function fetchGovernanceDebug(runId: string) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/debug/runs/{run_id}/governance",
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
      `Failed to load governance debug for ${runId}`,
    );
  }

  const parsed = governanceDebugSchema.parse(data);
  return {
    ...parsed,
    debug: {
      ...parsed.debug,
      issues: parsed.debug.issues ?? [],
      notes: parsed.debug.notes ?? [],
      fallback_from_decision_packet:
        parsed.debug.fallback_from_decision_packet ?? false,
    },
  };
}

export function governanceDebugQueryOptions(runId: string) {
  return queryOptions({
    queryKey: queryKeys.runGovernanceDebug(runId),
    queryFn: () => fetchGovernanceDebug(runId),
  });
}

export function useGovernanceDebug(runId: string | undefined, enabled = true) {
  return useQuery({
    ...governanceDebugQueryOptions(runId ?? "unknown"),
    enabled: Boolean(runId) && enabled,
  });
}

export function useSuspenseGovernanceDebug(runId: string) {
  return useSuspenseQuery(governanceDebugQueryOptions(runId));
}
