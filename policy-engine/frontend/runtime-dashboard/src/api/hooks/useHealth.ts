import { useQuery } from "@tanstack/react-query";

import { HEALTH_REFETCH_MS } from "../../lib/constants";
import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { healthSchema } from "../validators";

async function fetchHealth() {
  const { data, error, response } = await runtimeApiClient.GET("/api/v1/health");
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, "Failed to load runtime API health");
  }
  return healthSchema.parse(data);
}

export function useHealth() {
  return useQuery({
    queryKey: queryKeys.health(),
    queryFn: fetchHealth,
    refetchInterval: HEALTH_REFETCH_MS,
  });
}
