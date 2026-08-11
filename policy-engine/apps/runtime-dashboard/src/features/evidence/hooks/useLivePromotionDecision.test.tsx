import { act, renderHook, waitFor } from "@testing-library/react";

import { queryKeys } from "@/api/queryKeys";
import { createQueryHookHarness } from "@/test/queryHook";

const {
  approvePromotionRequestMock,
  invalidatePromotionDecisionQueriesMock,
  rejectPromotionRequestMock,
} = vi.hoisted(() => ({
  approvePromotionRequestMock: vi.fn(),
  invalidatePromotionDecisionQueriesMock: vi.fn(),
  rejectPromotionRequestMock: vi.fn(),
}));

vi.mock("@/api/hooks/usePromotionDecision", async () => {
  const actual = await vi.importActual<
    typeof import("@/api/hooks/usePromotionDecision")
  >("@/api/hooks/usePromotionDecision");
  return {
    ...actual,
    approvePromotionRequest: (...args: unknown[]) =>
      approvePromotionRequestMock(...args),
    invalidatePromotionDecisionQueries: (...args: unknown[]) =>
      invalidatePromotionDecisionQueriesMock(...args),
    rejectPromotionRequest: (...args: unknown[]) =>
      rejectPromotionRequestMock(...args),
  };
});

import { useLivePromotionDecision } from "@/features/evidence/hooks/useLivePromotionDecision";

describe("useLivePromotionDecision", () => {
  beforeEach(() => {
    approvePromotionRequestMock.mockReset();
    invalidatePromotionDecisionQueriesMock.mockReset();
    rejectPromotionRequestMock.mockReset();
  });

  it("test_offline_retryable_promotion_never_queues_terminalizes_or_replays", async () => {
    const retryableFailures = [
      { code: "network_unavailable", label: "offline", status: 0 },
      { code: "request_timeout", label: "408", status: 408 },
      { code: "rate_limited", label: "429", status: 429 },
      { code: "server_error", label: "5xx", status: 500 },
    ];
    const decisions = [
      {
        invoke: "approve" as const,
        request: approvePromotionRequestMock,
      },
      {
        invoke: "reject" as const,
        request: rejectPromotionRequestMock,
      },
    ];

    for (const failure of retryableFailures) {
      for (const decision of decisions) {
        const input = {
          promotionId: `promotion-${decision.invoke}-${failure.label}`,
          reason: `exercise ${failure.label}`,
          runId: "run-1",
        };
        const error = { code: failure.code, status: failure.status };
        decision.request.mockRejectedValueOnce(error);
        const onError = vi.fn();
        const { queryClient, wrapper } = createQueryHookHarness();
        const candidates = [
          { promotion_id: input.promotionId, status: "pending" },
        ];
        queryClient.setQueryData(queryKeys.dataPromotionCandidates(), candidates);
        const view = renderHook(() => useLivePromotionDecision(), { wrapper });

        await act(async () => {
          view.result.current[decision.invoke](input, { onError });
        });

        await waitFor(() => {
          expect(decision.request).toHaveBeenCalledWith(input, expect.anything());
          expect(onError).toHaveBeenCalled();
          expect(onError.mock.calls[0]?.[0]).toEqual(error);
        });
        expect(
          queryClient.getQueryData(queryKeys.dataPromotionCandidates()),
        ).toEqual(candidates);
        expect(
          view.result.current.isDecisionPending(input.promotionId),
        ).toBe(false);
        expect(view.result.current).not.toHaveProperty("queuedStateByPromotionId");
        expect(invalidatePromotionDecisionQueriesMock).not.toHaveBeenCalled();
      }
    }

    for (const decision of decisions) {
      const input = {
        promotionId: `promotion-${decision.invoke}-live-success`,
        runId: "run-1",
      };
      const onSuccess = vi.fn();
      decision.request.mockResolvedValueOnce({ message: "server accepted" });
      const { wrapper } = createQueryHookHarness();
      const view = renderHook(() => useLivePromotionDecision(), { wrapper });

      await act(async () => {
        view.result.current[decision.invoke](input, { onSuccess });
      });

      await waitFor(() => {
        expect(decision.request).toHaveBeenCalledWith(input, expect.anything());
        expect(onSuccess).toHaveBeenCalled();
        expect(invalidatePromotionDecisionQueriesMock).toHaveBeenCalledWith(
          expect.anything(),
          input.runId,
        );
      });
    }
  });
});
