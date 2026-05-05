import {
  queryOptions,
  useQuery,
  useSuspenseQuery,
} from "@tanstack/react-query";

import { HEALTH_REFETCH_MS } from "@/shared/lib/constants";
import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import { healthSchema } from "../validators";

export async function fetchHealth() {
  const { data, error, response } =
    await runtimeApiClient.GET("/api/v1/health");
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      "Failed to load runtime API health",
    );
  }
  return healthSchema.parse(data);
}

export function healthQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.health(),
    queryFn: fetchHealth,
    staleTime: HEALTH_REFETCH_MS,
    refetchInterval: HEALTH_REFETCH_MS,
  });
}

export function useHealth() {
  return useQuery(healthQueryOptions());
}

export function useSuspenseHealth() {
  return useSuspenseQuery(healthQueryOptions());
}
