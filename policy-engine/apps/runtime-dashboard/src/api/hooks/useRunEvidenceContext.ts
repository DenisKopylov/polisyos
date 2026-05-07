import {
  queryOptions,
  useQuery,
  useSuspenseQuery,
} from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { runEvidenceContextSchema } from "../validators";

async function fetchRunEvidenceContext(runId: string) {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/runs/{run_id}/evidence-context",
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
      `Failed to load run evidence context for ${runId}`,
    );
  }

  const parsed = runEvidenceContextSchema.parse(data);
  return {
    ...parsed,
    context: {
      ...parsed.context,
      related_artifacts: parsed.context.related_artifacts ?? [],
      data_needs: parsed.context.data_needs ?? [],
      fetch_plans: parsed.context.fetch_plans ?? [],
      promotion_candidates: parsed.context.promotion_candidates ?? [],
      warnings: parsed.context.warnings ?? [],
    },
  };
}

export function runEvidenceContextQueryOptions(runId: string) {
  return queryOptions({
    queryKey: queryKeys.runEvidenceContext(runId),
    queryFn: () => fetchRunEvidenceContext(runId),
  });
}

export function useRunEvidenceContext(
  runId: string | undefined,
  enabled = true,
) {
  return useQuery({
    ...runEvidenceContextQueryOptions(runId ?? "unknown"),
    enabled: Boolean(runId) && enabled,
  });
}

export function useSuspenseRunEvidenceContext(runId: string) {
  return useSuspenseQuery(runEvidenceContextQueryOptions(runId));
}
