import { useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { runDetailsSchema } from "../validators";

async function fetchRunDetails(runId: string) {
  const { data, error, response } = await runtimeApiClient.GET("/api/v1/runs/{run_id}", {
    params: {
      path: {
        run_id: runId,
      },
    },
  });

  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, `Failed to load run ${runId}`);
  }
  return runDetailsSchema.parse(data);
}

export function useRunDetails(runId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.run(runId ?? "unknown"),
    queryFn: () => fetchRunDetails(runId ?? ""),
    enabled: Boolean(runId),
  });
}
