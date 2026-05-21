import { useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";

export type ControlJobResponse =
  components["schemas"]["ControlJobResponse"];

async function fetchControlJobStatus(
  jobId: string,
): Promise<ControlJobResponse> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/control/jobs/{job_id}",
    { params: { path: { job_id: jobId } } },
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      "Failed to fetch control job status",
    );
  }
  return data as ControlJobResponse;
}

export function useControlJobStatus(jobId: string | null | undefined) {
  return useQuery({
    queryKey: queryKeys.controlJobStatus(jobId ?? ""),
    queryFn: () => fetchControlJobStatus(jobId!),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      if (state === "pending" || state === "running") {
        return 3000;
      }
      return false;
    },
  });
}
