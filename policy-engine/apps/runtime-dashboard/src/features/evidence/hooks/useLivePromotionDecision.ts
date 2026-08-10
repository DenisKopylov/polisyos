import { useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  approvePromotionRequest,
  invalidatePromotionDecisionQueries,
  type PromotionDecisionInput,
  rejectPromotionRequest,
} from "@/api/hooks/usePromotionDecision";

type PromotionDecisionCallbacks = {
  onError?: (error: unknown) => void;
  onSuccess?: () => void;
};

export function useLivePromotionDecision() {
  const queryClient = useQueryClient();
  const approveMutation = useMutation({
    mutationFn: approvePromotionRequest,
    onSuccess: (_response, input) => {
      invalidatePromotionDecisionQueries(queryClient, input.runId);
    },
  });
  const rejectMutation = useMutation({
    mutationFn: rejectPromotionRequest,
    onSuccess: (_response, input) => {
      invalidatePromotionDecisionQueries(queryClient, input.runId);
    },
  });

  const approve = useCallback(
    (input: PromotionDecisionInput, callbacks?: PromotionDecisionCallbacks) => {
      approveMutation.mutate(input, callbacks);
    },
    [approveMutation],
  );

  const reject = useCallback(
    (input: PromotionDecisionInput, callbacks?: PromotionDecisionCallbacks) => {
      rejectMutation.mutate(input, callbacks);
    },
    [rejectMutation],
  );

  const isDecisionPending = useCallback(
    (promotionId: string) =>
      (approveMutation.isPending &&
        approveMutation.variables?.promotionId === promotionId) ||
      (rejectMutation.isPending &&
        rejectMutation.variables?.promotionId === promotionId),
    [
      approveMutation.isPending,
      approveMutation.variables,
      rejectMutation.isPending,
      rejectMutation.variables,
    ],
  );

  return {
    approve,
    approveError: approveMutation.error,
    isDecisionPending,
    reject,
    rejectError: rejectMutation.error,
  };
}
