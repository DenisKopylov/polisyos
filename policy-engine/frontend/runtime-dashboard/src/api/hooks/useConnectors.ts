import { useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";

export type ConnectorsListResponse = components["schemas"]["ConnectorsListResponse"];

async function fetchConnectors(): Promise<ConnectorsListResponse> {
  const { data, error, response } = await runtimeApiClient.GET("/api/v1/control/data/connectors");
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, "Failed to load connectors");
  }
  return data as ConnectorsListResponse;
}

export function useConnectors() {
  return useQuery({
    queryKey: queryKeys.connectors(),
    queryFn: fetchConnectors,
  });
}
