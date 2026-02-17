import { useMutation, useQueryClient } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";

export type DataDiscoverRequest = components["schemas"]["DataDiscoverRequest"];
export type DataDiscoverResponse = components["schemas"]["DataDiscoverResponse"];

async function discoverDataSources(body: DataDiscoverRequest): Promise<DataDiscoverResponse> {
  const { data, error, response } = await runtimeApiClient.POST("/api/v1/control/data/discover", {
    body,
  });
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, "Failed to discover data sources");
  }
  return data as DataDiscoverResponse;
}

export function useDiscoverDataSources() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: discoverDataSources,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.dataIndexStats() });
    },
  });
}
