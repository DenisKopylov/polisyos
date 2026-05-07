import {
  queryOptions,
  useQuery,
  useSuspenseQuery,
} from "@tanstack/react-query";

import { RUNS_SAMPLE_STALE_MS } from "@/shared/lib/constants";
import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";
import { promotionCandidatesSchema } from "../validators";

export type PromotionCandidatesResponse =
  components["schemas"]["PromotionCandidatesResponse"];

export async function fetchPromotionCandidates(): Promise<PromotionCandidatesResponse> {
  const { data, error, response } = await runtimeApiClient.GET(
    "/api/v1/control/data/promotion/candidates",
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(
      response,
      error,
      "Failed to load promotion candidates",
    );
  }
  return promotionCandidatesSchema.parse(data) as PromotionCandidatesResponse;
}

export function dataPromotionCandidatesQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.dataPromotionCandidates(),
    queryFn: fetchPromotionCandidates,
    staleTime: RUNS_SAMPLE_STALE_MS,
  });
}

export function useDataPromotionCandidates() {
  return useQuery(dataPromotionCandidatesQueryOptions());
}

export function useSuspenseDataPromotionCandidates() {
  return useSuspenseQuery(dataPromotionCandidatesQueryOptions());
}
