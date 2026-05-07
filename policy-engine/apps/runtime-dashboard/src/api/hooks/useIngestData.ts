import { useQueryClient } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";
import { useControlPlaneMutation } from "../useControlPlaneMutation";

export type IngestRequest = components["schemas"]["IngestRequest"];
export type IngestResponse = components["schemas"]["IngestResponse"];

async function ingestData(body: IngestRequest): Promise<IngestResponse> {
  const { data, error, response } = await runtimeApiClient.POST(
    "/api/v1/control/data/ingest",
    {
      body,
    },
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, "Failed to ingest data");
  }
  return data as IngestResponse;
}

export function useIngestData() {
  const queryClient = useQueryClient();
  return useControlPlaneMutation({
    blockWhenOffline: true,
    mutationId: "data.ingest",
    mutationFn: ingestData,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.cacheStatus() });
    },
  });
}
