import { useMutation, useQueryClient } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";

export type DataResolveRequest = components["schemas"]["DataResolveRequest"];
export type DataResolveResponse = components["schemas"]["DataResolveResponse"];

async function resolveDataNeeds(body: DataResolveRequest): Promise<DataResolveResponse> {
  const { data, error, response } = await runtimeApiClient.POST("/api/v1/control/data/resolve", {
    body,
  });
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, "Failed to resolve data needs");
  }
  return data as DataResolveResponse;
}

export function useResolveDataNeeds() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: resolveDataNeeds,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.dataIndexStats() });
    },
  });
}
