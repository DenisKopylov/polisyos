import { useQuery } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";

export type PromotionCandidatesResponse = components["schemas"]["PromotionCandidatesResponse"];

async function fetchPromotionCandidates(): Promise<PromotionCandidatesResponse> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/control/data/promotion/candidates",
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, "Failed to load promotion candidates");
  }
  return data as PromotionCandidatesResponse;
}

export function useDataPromotionCandidates() {
  return useQuery({
    queryKey: queryKeys.dataPromotionCandidates(),
    queryFn: fetchPromotionCandidates,
    staleTime: 10_000,
  });
}
