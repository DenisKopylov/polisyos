import type { QueryClient } from "@tanstack/react-query";
import { useQueryClient } from "@tanstack/react-query";

import { runtimeApiClient } from "../client";
import { createRuntimeApiError } from "../http";
import {
  updateIndexStatsAfterPromotion,
  updatePromotionCandidateStatus,
  updateRunEvidencePromotionStatus,
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
  runId?: string;
};

export type PromotionDecisionCacheSnapshot = {
  candidatesSnapshot: unknown;
  evidenceContextSnapshot?: unknown;
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
  return promotionDecisionResponseSchema.parse(
    data,
  ) as PromotionDecisionResponse;
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
  return promotionDecisionResponseSchema.parse(
    data,
  ) as PromotionDecisionResponse;
}

async function snapshotPromotionDecisionCache(
  queryClient: QueryClient,
  runId?: string,
): Promise<PromotionDecisionCacheSnapshot> {
  await queryClient.cancelQueries({
    queryKey: queryKeys.dataPromotionCandidates(),
  });
  await queryClient.cancelQueries({ queryKey: queryKeys.dataIndexStats() });
  if (runId) {
    await queryClient.cancelQueries({
      queryKey: queryKeys.runEvidenceContext(runId),
    });
  }

  return {
    candidatesSnapshot: queryClient.getQueryData(
      queryKeys.dataPromotionCandidates(),
    ),
    evidenceContextSnapshot: runId
      ? queryClient.getQueryData(queryKeys.runEvidenceContext(runId))
      : undefined,
    indexStatsSnapshot: queryClient.getQueryData(queryKeys.dataIndexStats()),
  };
}

export function applyOptimisticPromotionDecision(
  queryClient: QueryClient,
  promotionId: string,
  status: "approved" | "rejected",
  runId?: string,
) {
  updatePromotionCandidateStatus(queryClient, promotionId, status);
  if (runId) {
    updateRunEvidencePromotionStatus(queryClient, runId, promotionId, status);
  }
  if (status === "approved") {
    updateIndexStatsAfterPromotion(queryClient);
  }
}

export function restorePromotionDecisionSnapshot(
  queryClient: QueryClient,
  snapshot: PromotionDecisionCacheSnapshot | undefined,
  runId?: string,
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
  if (runId) {
    queryClient.setQueryData(
      queryKeys.runEvidenceContext(runId),
      snapshot.evidenceContextSnapshot,
    );
  }
}

export function invalidatePromotionDecisionQueries(
  queryClient: QueryClient,
  runId?: string,
) {
  void queryClient.invalidateQueries({
    queryKey: queryKeys.dataPromotionCandidates(),
  });
  void queryClient.invalidateQueries({ queryKey: queryKeys.dataIndexStats() });
  if (runId) {
    void queryClient.invalidateQueries({
      queryKey: queryKeys.runEvidenceContext(runId),
    });
  }
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
    onMutate: async ({ promotionId, runId }) => {
      const snapshot = await snapshotPromotionDecisionCache(queryClient, runId);
      applyOptimisticPromotionDecision(
        queryClient,
        promotionId,
        "approved",
        runId,
      );
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
      restorePromotionDecisionSnapshot(queryClient, context, variables.runId);
    },
    onSuccess: (_data, variables) => {
      invalidatePromotionDecisionQueries(queryClient, variables.runId);
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
    onMutate: async ({ promotionId, runId }) => {
      const snapshot = await snapshotPromotionDecisionCache(queryClient, runId);
      applyOptimisticPromotionDecision(
        queryClient,
        promotionId,
        "rejected",
        runId,
      );
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
      restorePromotionDecisionSnapshot(queryClient, context, variables.runId);
    },
    onSuccess: (_data, variables) => {
      invalidatePromotionDecisionQueries(queryClient, variables.runId);
    },
    successToast: (data) => ({
      title: "Promotion rejected",
      description: data.message,
      tone: "warning",
    }),
  });
}
