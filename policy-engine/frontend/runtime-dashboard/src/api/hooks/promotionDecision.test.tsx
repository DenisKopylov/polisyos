import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  useApprovePromotionCandidate,
  useRejectPromotionCandidate,
} from "@/api/hooks/usePromotionDecision";
import { queryKeys } from "@/api/queryKeys";
import { createQueryHookHarness } from "@/test/queryHook";
import {
  mockRuntimePostFailure,
  mockRuntimePostSuccess,
} from "@/test/runtimeApi";

function createMeta() {
  return {
    generated_at: "2026-03-10T10:00:00Z",
    request_id: "req-promotion",
    source_kinds: ["core_run"],
  };
}

function createPromotionCandidates() {
  return {
    meta: createMeta(),
    candidates: [
      {
        connector_id: "bigquery",
        dataset_id: "macro",
        metric_id: "inflation",
        promotion_id: "promotion-1",
        status: "pending",
      },
    ],
  };
}

function createIndexStats() {
  return {
    meta: createMeta(),
    stats: {
      docs_added_last_run: 4,
      last_updated: "2026-03-09T10:00:00Z",
    },
  };
}

describe("promotion decision hooks", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("optimistically approves a promotion and bumps index stats", async () => {
    const { queryClient, wrapper } = createQueryHookHarness();
    queryClient.setQueryData(
      queryKeys.dataPromotionCandidates(),
      createPromotionCandidates(),
    );
    queryClient.setQueryData(queryKeys.dataIndexStats(), createIndexStats());
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const postSpy = mockRuntimePostSuccess({
      meta: createMeta(),
      message: "Promotion candidate approved and source bindings updated.",
      promotion_id: "promotion-1",
      status: "approved",
    });

    const view = renderHook(() => useApprovePromotionCandidate(), { wrapper });
    await act(async () => {
      await view.result.current.mutateAsync({
        promotionId: "promotion-1",
        reason: "Reusable signal",
      });
    });

    expect(postSpy).toHaveBeenCalledWith(
      "/api/v1/control/data/promotion/{promotion_id}/approve",
      {
        body: {
          reason: "Reusable signal",
        },
        params: {
          path: {
            promotion_id: "promotion-1",
          },
        },
      },
    );
    expect(
      queryClient.getQueryData(queryKeys.dataPromotionCandidates()),
    ).toMatchObject({
      candidates: [{ promotion_id: "promotion-1", status: "approved" }],
    });
    expect(queryClient.getQueryData(queryKeys.dataIndexStats())).toMatchObject({
      stats: { docs_added_last_run: 5 },
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.dataPromotionCandidates(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.dataIndexStats(),
    });
  });

  it("updates and invalidates run evidence context when the decision is tied to a run", async () => {
    const { queryClient, wrapper } = createQueryHookHarness();
    queryClient.setQueryData(queryKeys.runEvidenceContext("run-1"), {
      context: {
        promotion_candidates: [
          {
            connector_id: "bigquery",
            dataset_id: "macro",
            metric_id: "inflation",
            promotion_id: "promotion-1",
            status: "pending",
          },
        ],
        run_id: "run-1",
        source_kind: "core_run",
      },
      meta: createMeta(),
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    mockRuntimePostSuccess({
      meta: createMeta(),
      message: "Promotion candidate approved and source bindings updated.",
      promotion_id: "promotion-1",
      status: "approved",
    });

    const view = renderHook(() => useApprovePromotionCandidate(), { wrapper });
    await act(async () => {
      await view.result.current.mutateAsync({
        promotionId: "promotion-1",
        runId: "run-1",
      });
    });

    expect(
      queryClient.getQueryData(queryKeys.runEvidenceContext("run-1")),
    ).toMatchObject({
      context: {
        promotion_candidates: [
          { promotion_id: "promotion-1", status: "approved" },
        ],
      },
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.runEvidenceContext("run-1"),
    });
  });

  it("rolls back a rejected approval when the request fails", async () => {
    const { queryClient, wrapper } = createQueryHookHarness();
    const initialCandidates = createPromotionCandidates();
    const initialStats = createIndexStats();
    queryClient.setQueryData(
      queryKeys.dataPromotionCandidates(),
      initialCandidates,
    );
    queryClient.setQueryData(queryKeys.dataIndexStats(), initialStats);
    mockRuntimePostFailure(500, {
      code: "promotion_failed",
      detail: "Approval failed",
      status: 500,
    });

    const view = renderHook(() => useApprovePromotionCandidate(), { wrapper });
    await act(async () => {
      await expect(
        view.result.current.mutateAsync({
          promotionId: "promotion-1",
        }),
      ).rejects.toMatchObject({
        code: "promotion_failed",
      });
    });

    expect(
      queryClient.getQueryData(queryKeys.dataPromotionCandidates()),
    ).toEqual(initialCandidates);
    expect(queryClient.getQueryData(queryKeys.dataIndexStats())).toEqual(
      initialStats,
    );
  });

  it("optimistically rejects a promotion and restores candidates on error", async () => {
    const { queryClient, wrapper } = createQueryHookHarness();
    const initialCandidates = createPromotionCandidates();
    queryClient.setQueryData(
      queryKeys.dataPromotionCandidates(),
      initialCandidates,
    );
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
    const postSpy = mockRuntimePostSuccess({
      meta: createMeta(),
      message: "Promotion candidate rejected and left in staging.",
      promotion_id: "promotion-1",
      status: "rejected",
    });

    const view = renderHook(() => useRejectPromotionCandidate(), { wrapper });
    await act(async () => {
      await view.result.current.mutateAsync({
        promotionId: "promotion-1",
        reason: "Insufficient confidence",
      });
    });

    expect(postSpy).toHaveBeenCalledWith(
      "/api/v1/control/data/promotion/{promotion_id}/reject",
      {
        body: {
          reason: "Insufficient confidence",
        },
        params: {
          path: {
            promotion_id: "promotion-1",
          },
        },
      },
    );
    expect(
      queryClient.getQueryData(queryKeys.dataPromotionCandidates()),
    ).toMatchObject({
      candidates: [{ promotion_id: "promotion-1", status: "rejected" }],
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: queryKeys.dataPromotionCandidates(),
    });

    vi.restoreAllMocks();

    mockRuntimePostFailure(500, {
      code: "promotion_failed",
      detail: "Reject failed",
      status: 500,
    });
    queryClient.setQueryData(
      queryKeys.dataPromotionCandidates(),
      initialCandidates,
    );
    {
      const view = renderHook(() => useRejectPromotionCandidate(), {
        wrapper,
      });

      await act(async () => {
        await expect(
          view.result.current.mutateAsync({
            promotionId: "promotion-1",
          }),
        ).rejects.toMatchObject({
          code: "promotion_failed",
        });
      });
    }

    expect(
      queryClient.getQueryData(queryKeys.dataPromotionCandidates()),
    ).toEqual(initialCandidates);
  });
});
