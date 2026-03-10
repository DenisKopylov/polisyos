import type { QueryClient } from "@tanstack/react-query";
import { useQueryClient } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import {
  updateIndexStatsAfterPromotion,
  updatePromotionCandidateStatus,
} from "../optimistic";
import { queryKeys } from "../queryKeys";
import type { components } from "../types";
import { useControlPlaneMutation } from "../useControlPlaneMutation";
import { promotionDecisionResponseSchema } from "../validators";
import { useLogger } from "@/shared/telemetry/logger";

export type PromotionDecisionRequest =
  components["schemas"]["PromotionDecisionRequest"];
export type PromotionDecisionResponse =
  components["schemas"]["PromotionDecisionResponse"];

export type PromotionDecisionInput = {
  promotionId: string;
  reason?: string;
};

export type PromotionDecisionCacheSnapshot = {
  candidatesSnapshot: unknown;
  indexStatsSnapshot: unknown;
};

export async function approvePromotionRequest({
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
    throw createRuntimeApiError(
      response,
      error,
      "Failed to approve promotion candidate",
    );
  }
  return promotionDecisionResponseSchema.parse(data) as PromotionDecisionResponse;
}

export async function rejectPromotionRequest({
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
    throw createRuntimeApiError(
      response,
      error,
      "Failed to reject promotion candidate",
    );
  }
  return promotionDecisionResponseSchema.parse(data) as PromotionDecisionResponse;
}

async function snapshotPromotionDecisionCache(
  queryClient: QueryClient,
): Promise<PromotionDecisionCacheSnapshot> {
  await queryClient.cancelQueries({
    queryKey: queryKeys.dataPromotionCandidates(),
  });
  await queryClient.cancelQueries({ queryKey: queryKeys.dataIndexStats() });

  return {
    candidatesSnapshot: queryClient.getQueryData(
      queryKeys.dataPromotionCandidates(),
    ),
    indexStatsSnapshot: queryClient.getQueryData(queryKeys.dataIndexStats()),
  };
}

export function applyOptimisticPromotionDecision(
  queryClient: QueryClient,
  promotionId: string,
  status: "approved" | "rejected",
) {
  updatePromotionCandidateStatus(queryClient, promotionId, status);
  if (status === "approved") {
    updateIndexStatsAfterPromotion(queryClient);
  }
}

export function restorePromotionDecisionSnapshot(
  queryClient: QueryClient,
  snapshot: PromotionDecisionCacheSnapshot | undefined,
) {
  if (!snapshot) {
    return;
  }

  queryClient.setQueryData(
    queryKeys.dataPromotionCandidates(),
    snapshot.candidatesSnapshot,
  );
  queryClient.setQueryData(
    queryKeys.dataIndexStats(),
    snapshot.indexStatsSnapshot,
  );
}

export function invalidatePromotionDecisionQueries(queryClient: QueryClient) {
  void queryClient.invalidateQueries({
    queryKey: queryKeys.dataPromotionCandidates(),
  });
  void queryClient.invalidateQueries({ queryKey: queryKeys.dataIndexStats() });
}

export function useApprovePromotionCandidate() {
  const queryClient = useQueryClient();
  const logger = useLogger({
    tags: {
      mutation: "promotion.approve",
    },
  });
  return useControlPlaneMutation({
    errorToast: {
      title: "Promotion approval failed",
      description: "Atlas restored the previous promotion state.",
      tone: "error",
    },
    mutationId: "promotion.approve",
    mutationFn: approvePromotionRequest,
    onMutate: async ({ promotionId }) => {
      const snapshot = await snapshotPromotionDecisionCache(queryClient);
      applyOptimisticPromotionDecision(queryClient, promotionId, "approved");
      return snapshot;
    },
    onError: (error, variables, context) => {
      logger.warn({
        error,
        event: "mutation.promotion_approve.error",
        message: `Failed to approve promotion ${variables.promotionId}`,
        tags: {
          promotionId: variables.promotionId,
        },
      });
      restorePromotionDecisionSnapshot(queryClient, context);
    },
    onSuccess: () => {
      invalidatePromotionDecisionQueries(queryClient);
    },
    successToast: (data) => ({
      title: "Promotion approved",
      description: data.message,
      tone: "success",
    }),
  });
}

export function useRejectPromotionCandidate() {
  const queryClient = useQueryClient();
  const logger = useLogger({
    tags: {
      mutation: "promotion.reject",
    },
  });
  return useControlPlaneMutation({
    errorToast: {
      title: "Promotion rejection failed",
      description: "Atlas restored the previous promotion state.",
      tone: "error",
    },
    mutationId: "promotion.reject",
    mutationFn: rejectPromotionRequest,
    onMutate: async ({ promotionId }) => {
      const snapshot = await snapshotPromotionDecisionCache(queryClient);
      applyOptimisticPromotionDecision(queryClient, promotionId, "rejected");
      return snapshot;
    },
    onError: (error, variables, context) => {
      logger.warn({
        error,
        event: "mutation.promotion_reject.error",
        message: `Failed to reject promotion ${variables.promotionId}`,
        tags: {
          promotionId: variables.promotionId,
        },
      });
      restorePromotionDecisionSnapshot(queryClient, context);
    },
    onSuccess: () => {
      invalidatePromotionDecisionQueries(queryClient);
    },
    successToast: (data) => ({
      title: "Promotion rejected",
      description: data.message,
      tone: "warning",
    }),
  });
}
