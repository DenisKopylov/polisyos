import type { QueryClient } from "@tanstack/react-query";

import { queryKeys } from "@/api/queryKeys";
import type { PromotionCandidatesResponse } from "@/api/hooks/useDataPromotionCandidates";
import type { IndexStatsResponse } from "@/api/hooks/useDataIndexStats";
import type { components } from "@/api/types";

export type RunEvidenceContextResponse = {
  context: components["schemas"]["RunEvidenceContextView"];
  meta: components["schemas"]["ApiMeta"];
};

export function updatePromotionCandidateStatus(
  queryClient: QueryClient,
  promotionId: string,
  status: components["schemas"]["PromotionDecisionResponse"]["status"],
) {
  queryClient.setQueryData<PromotionCandidatesResponse | undefined>(
    queryKeys.dataPromotionCandidates(),
    (current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        candidates: (current.candidates ?? []).map((candidate) =>
          candidate.promotion_id === promotionId
            ? { ...candidate, status }
            : candidate,
        ),
      };
    },
  );
}

export function updateRunEvidencePromotionStatus(
  queryClient: QueryClient,
  runId: string,
  promotionId: string,
  status: components["schemas"]["PromotionDecisionResponse"]["status"],
) {
  queryClient.setQueryData<RunEvidenceContextResponse | undefined>(
    queryKeys.runEvidenceContext(runId),
    (current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        context: {
          ...current.context,
          promotion_candidates: (
            current.context.promotion_candidates ?? []
          ).map((candidate) =>
            candidate.promotion_id === promotionId
              ? { ...candidate, status }
              : candidate,
          ),
        },
      };
    },
  );
}

export function updateIndexStatsAfterPromotion(queryClient: QueryClient) {
  queryClient.setQueryData<IndexStatsResponse | undefined>(
    queryKeys.dataIndexStats(),
    (current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        stats: {
          ...current.stats,
          docs_added_last_run: (current.stats.docs_added_last_run ?? 0) + 1,
          last_updated: new Date().toISOString(),
        },
      };
    },
  );
}
