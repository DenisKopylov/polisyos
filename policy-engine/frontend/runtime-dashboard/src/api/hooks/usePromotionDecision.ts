import { useMutation, useQueryClient } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";

export type PromotionDecisionRequest = components["schemas"]["PromotionDecisionRequest"];
export type PromotionDecisionResponse = components["schemas"]["PromotionDecisionResponse"];

type PromotionDecisionInput = {
  promotionId: string;
  reason?: string;
};

async function approvePromotion({
  promotionId,
  reason,
}: PromotionDecisionInput): Promise<PromotionDecisionResponse> {
  const body: PromotionDecisionRequest = { reason: reason ?? null };
  const { data, error, response } = await runtimeApiClient.POST(
    "/api/v1/control/data/promotion/{promotion_id}/approve",
    {
      params: { path: { promotion_id: promotionId } },
      body,
    },
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, "Failed to approve promotion candidate");
  }
  return data as PromotionDecisionResponse;
}

async function rejectPromotion({
  promotionId,
  reason,
}: PromotionDecisionInput): Promise<PromotionDecisionResponse> {
  const body: PromotionDecisionRequest = { reason: reason ?? null };
  const { data, error, response } = await runtimeApiClient.POST(
    "/api/v1/control/data/promotion/{promotion_id}/reject",
    {
      params: { path: { promotion_id: promotionId } },
      body,
    },
  );
  if (error || !response.ok || !data) {
    throw createRuntimeApiError(response, error, "Failed to reject promotion candidate");
  }
  return data as PromotionDecisionResponse;
}

export function useApprovePromotionCandidate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: approvePromotion,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.dataPromotionCandidates() });
      queryClient.invalidateQueries({ queryKey: queryKeys.dataIndexStats() });
    },
  });
}

export function useRejectPromotionCandidate() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: rejectPromotion,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.dataPromotionCandidates() });
    },
  });
}
