import { useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { runErrorsSchema } from "../validators";

async function fetchRunErrors(runId: string) {
  const { data, error, response } = await runtimeApiClient.GET("/api/v1/debug/runs/{run_id}/errors", {
    params: {
      path: {
        run_id: runId,
      },
    },
  });

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, `Failed to load run errors for ${runId}`);
  }

  const parsed = runErrorsSchema.parse(data);
  return {
    ...parsed,
    errors: parsed.errors ?? [],
  };
}

export function useRunErrors(runId: string | undefined, enabled = true) {
  return useQuery({
    queryKey: queryKeys.runErrors(runId ?? "unknown"),
    queryFn: () => fetchRunErrors(runId ?? ""),
    enabled: Boolean(runId) && enabled,
  });
}
