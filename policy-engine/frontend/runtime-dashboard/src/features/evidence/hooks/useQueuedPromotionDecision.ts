import { useCallback, useMemo } from "react";
import { useQueryClient } from "@tanstack/react-query";

import {
  applyOptimisticPromotionDecision,
  type PromotionDecisionInput,
  useApprovePromotionCandidate,
  useRejectPromotionCandidate,
} from "@/api/hooks/usePromotionDecision";
import { isRuntimeApiRequestError } from "@/api/http";
import { useOfflineQueue } from "@/app/providers/OfflineQueueProvider";
import { useNetworkStatus } from "@/shared/network";

type QueuedPromotionState = {
  decision: "approved" | "rejected";
  queueStatus: "failed" | "queued" | "retrying";
  updatedAt: number;
};

type PromotionDecisionCallbacks = {
  onError?: (error: unknown) => void;
  onQueued?: () => void;
  onSuccess?: () => void;
};

function shouldQueuePromotionDecision(error: unknown) {
  if (!isRuntimeApiRequestError(error)) {
    return true;
  }

  return error.status >= 500 || error.status === 408 || error.status === 429;
}

export function useQueuedPromotionDecision() {
  const queryClient = useQueryClient();
  const { enqueuePromotionDecision, items, isFlushing } = useOfflineQueue();
  const networkStatus = useNetworkStatus();
  const approveMutation = useApprovePromotionCandidate();
  const rejectMutation = useRejectPromotionCandidate();

  const queuedStateByPromotionId = useMemo(() => {
    const nextState = new Map<string, QueuedPromotionState>();

    for (const item of items) {
      const current = nextState.get(item.payload.promotionId);
      if (current && current.updatedAt > item.updatedAt) {
        continue;
      }
      nextState.set(item.payload.promotionId, {
        decision: item.kind === "promotion.approve" ? "approved" : "rejected",
        queueStatus: item.status,
        updatedAt: item.updatedAt,
      });
    }

    return nextState;
  }, [items]);

  const enqueueOfflineDecision = useCallback(
    async (kind: "promotion.approve" | "promotion.reject", input: PromotionDecisionInput) => {
      applyOptimisticPromotionDecision(
        queryClient,
        input.promotionId,
        kind === "promotion.approve" ? "approved" : "rejected",
      );
      await enqueuePromotionDecision(kind, input);
    },
    [enqueuePromotionDecision, queryClient],
  );

  const approve = useCallback(
    (input: PromotionDecisionInput, callbacks?: PromotionDecisionCallbacks) => {
      if (!networkStatus.online) {
        void enqueueOfflineDecision("promotion.approve", input).then(() => {
          callbacks?.onQueued?.();
        });
        return;
      }

      approveMutation.mutate(input, {
        onSuccess: () => {
          callbacks?.onSuccess?.();
        },
        onError: (error) => {
          if (!shouldQueuePromotionDecision(error)) {
            callbacks?.onError?.(error);
            return;
          }

          void enqueueOfflineDecision("promotion.approve", input).then(() => {
            callbacks?.onQueued?.();
          });
        },
      });
    },
    [approveMutation, enqueueOfflineDecision, networkStatus.online],
  );

  const reject = useCallback(
    (input: PromotionDecisionInput, callbacks?: PromotionDecisionCallbacks) => {
      if (!networkStatus.online) {
        void enqueueOfflineDecision("promotion.reject", input).then(() => {
          callbacks?.onQueued?.();
        });
        return;
      }

      rejectMutation.mutate(input, {
        onSuccess: () => {
          callbacks?.onSuccess?.();
        },
        onError: (error) => {
          if (!shouldQueuePromotionDecision(error)) {
            callbacks?.onError?.(error);
            return;
          }

          void enqueueOfflineDecision("promotion.reject", input).then(() => {
            callbacks?.onQueued?.();
          });
        },
      });
    },
    [enqueueOfflineDecision, networkStatus.online, rejectMutation],
  );

  const isDecisionPending = useCallback(
    (promotionId: string) =>
      (approveMutation.isPending &&
        approveMutation.variables?.promotionId === promotionId) ||
      (rejectMutation.isPending &&
        rejectMutation.variables?.promotionId === promotionId) ||
      (isFlushing && queuedStateByPromotionId.has(promotionId)),
    [
      approveMutation.isPending,
      approveMutation.variables,
      isFlushing,
      queuedStateByPromotionId,
      rejectMutation.isPending,
      rejectMutation.variables,
    ],
  );

  return {
    approve,
    approveError: approveMutation.error,
    isDecisionPending,
    queuedStateByPromotionId,
    reject,
    rejectError: rejectMutation.error,
  };
}
