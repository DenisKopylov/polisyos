import { act, renderHook, waitFor } from "@testing-library/react";

import { createQueryHookHarness } from "@/test/queryHook";

const {
  applyOptimisticPromotionDecisionMock,
  enqueuePromotionDecisionMock,
  useApprovePromotionCandidateMock,
  useNetworkStatusMock,
  useOfflineQueueMock,
  useRejectPromotionCandidateMock,
} = vi.hoisted(() => ({
  applyOptimisticPromotionDecisionMock: vi.fn(),
  enqueuePromotionDecisionMock: vi.fn(),
  useApprovePromotionCandidateMock: vi.fn(),
  useNetworkStatusMock: vi.fn(),
  useOfflineQueueMock: vi.fn(),
  useRejectPromotionCandidateMock: vi.fn(),
}));

vi.mock("@/api/hooks/usePromotionDecision", async () => {
  const actual = await vi.importActual<
    typeof import("@/api/hooks/usePromotionDecision")
  >("@/api/hooks/usePromotionDecision");
  return {
    ...actual,
    applyOptimisticPromotionDecision: (...args: unknown[]) =>
      applyOptimisticPromotionDecisionMock(...args),
    useApprovePromotionCandidate: (...args: unknown[]) =>
      useApprovePromotionCandidateMock(...args),
    useRejectPromotionCandidate: (...args: unknown[]) =>
      useRejectPromotionCandidateMock(...args),
  };
});

vi.mock("@/app/providers/OfflineQueueProvider", () => ({
  useOfflineQueue: (...args: unknown[]) => useOfflineQueueMock(...args),
}));

vi.mock("@/shared/network", () => ({
  useNetworkStatus: (...args: unknown[]) => useNetworkStatusMock(...args),
}));

import { useQueuedPromotionDecision } from "@/features/evidence/hooks/useQueuedPromotionDecision";

describe("useQueuedPromotionDecision", () => {
  beforeEach(() => {
    applyOptimisticPromotionDecisionMock.mockReset();
    enqueuePromotionDecisionMock.mockReset();
    enqueuePromotionDecisionMock.mockResolvedValue(undefined);
    useApprovePromotionCandidateMock.mockReset();
    useRejectPromotionCandidateMock.mockReset();
    useNetworkStatusMock.mockReset();
    useOfflineQueueMock.mockReset();

    useNetworkStatusMock.mockReturnValue({ online: true });
    useOfflineQueueMock.mockReturnValue({
      enqueuePromotionDecision: enqueuePromotionDecisionMock,
      isFlushing: false,
      items: [],
    });
    useApprovePromotionCandidateMock.mockReturnValue({
      error: null,
      isPending: false,
      mutate: vi.fn(),
      variables: undefined,
    });
    useRejectPromotionCandidateMock.mockReturnValue({
      error: null,
      isPending: false,
      mutate: vi.fn(),
      variables: undefined,
    });
  });

  it("queues approvals immediately when the client is offline", async () => {
    useNetworkStatusMock.mockReturnValue({ online: false });
    const onQueued = vi.fn();
    const { wrapper } = createQueryHookHarness();
    const view = renderHook(() => useQueuedPromotionDecision(), { wrapper });

    act(() => {
      view.result.current.approve(
        {
          promotionId: "promotion-1",
          reason: "Queue offline approval",
        },
        { onQueued },
      );
    });

    await waitFor(() => {
      expect(applyOptimisticPromotionDecisionMock).toHaveBeenCalledWith(
        expect.anything(),
        "promotion-1",
        "approved",
        undefined,
      );
      expect(enqueuePromotionDecisionMock).toHaveBeenCalledWith(
        "promotion.approve",
        {
          promotionId: "promotion-1",
          reason: "Queue offline approval",
        },
      );
      expect(onQueued).toHaveBeenCalled();
    });
  });

  it("invokes online mutations and success callbacks", () => {
    const onSuccess = vi.fn();
    const rejectMutateMock = vi.fn(
      (
        _input: unknown,
        options?: {
          onSuccess?: () => void;
        },
      ) => {
        options?.onSuccess?.();
      },
    );
    useRejectPromotionCandidateMock.mockReturnValue({
      error: null,
      isPending: false,
      mutate: rejectMutateMock,
      variables: undefined,
    });

    const { wrapper } = createQueryHookHarness();
    const view = renderHook(() => useQueuedPromotionDecision(), { wrapper });

    act(() => {
      view.result.current.reject(
        {
          promotionId: "promotion-2",
          reason: "Reject online",
        },
        { onSuccess },
      );
    });

    expect(rejectMutateMock).toHaveBeenCalledWith(
      {
        promotionId: "promotion-2",
        reason: "Reject online",
      },
      expect.objectContaining({
        onError: expect.any(Function),
        onSuccess: expect.any(Function),
      }),
    );
    expect(onSuccess).toHaveBeenCalled();
  });

  it("surfaces non-queueable mutation errors without writing to the offline queue", () => {
    const onError = vi.fn();
    const approveMutateMock = vi.fn(
      (
        _input: unknown,
        options?: {
          onError?: (error: unknown) => void;
        },
      ) => {
        options?.onError?.({
          code: "invalid_request",
          status: 400,
        });
      },
    );
    useApprovePromotionCandidateMock.mockReturnValue({
      error: { code: "invalid_request", status: 400 },
      isPending: false,
      mutate: approveMutateMock,
      variables: undefined,
    });

    const { wrapper } = createQueryHookHarness();
    const view = renderHook(() => useQueuedPromotionDecision(), { wrapper });

    act(() => {
      view.result.current.approve({ promotionId: "promotion-3" }, { onError });
    });

    expect(onError).toHaveBeenCalledWith({
      code: "invalid_request",
      status: 400,
    });
    expect(enqueuePromotionDecisionMock).not.toHaveBeenCalled();
  });

  it("queues retryable server failures after an online mutation error", async () => {
    const onQueued = vi.fn();
    const rejectMutateMock = vi.fn(
      (
        _input: unknown,
        options?: {
          onError?: (error: unknown) => void;
        },
      ) => {
        options?.onError?.({
          code: "server_error",
          status: 500,
        });
      },
    );
    useRejectPromotionCandidateMock.mockReturnValue({
      error: { code: "server_error", status: 500 },
      isPending: false,
      mutate: rejectMutateMock,
      variables: undefined,
    });

    const { wrapper } = createQueryHookHarness();
    const view = renderHook(() => useQueuedPromotionDecision(), { wrapper });

    act(() => {
      view.result.current.reject(
        {
          promotionId: "promotion-4",
          reason: "Queue on server failure",
        },
        { onQueued },
      );
    });

    await waitFor(() => {
      expect(applyOptimisticPromotionDecisionMock).toHaveBeenCalledWith(
        expect.anything(),
        "promotion-4",
        "rejected",
        undefined,
      );
      expect(enqueuePromotionDecisionMock).toHaveBeenCalledWith(
        "promotion.reject",
        {
          promotionId: "promotion-4",
          reason: "Queue on server failure",
        },
      );
      expect(onQueued).toHaveBeenCalled();
    });
  });

  it("tracks queued state and pending decisions by promotion id", () => {
    useOfflineQueueMock.mockReturnValue({
      enqueuePromotionDecision: enqueuePromotionDecisionMock,
      isFlushing: true,
      items: [
        {
          kind: "promotion.reject",
          payload: { promotionId: "promotion-5" },
          status: "queued",
          updatedAt: 100,
        },
        {
          kind: "promotion.approve",
          payload: { promotionId: "promotion-5" },
          status: "retrying",
          updatedAt: 200,
        },
      ],
    });
    useApprovePromotionCandidateMock.mockReturnValue({
      error: null,
      isPending: true,
      mutate: vi.fn(),
      variables: { promotionId: "promotion-6" },
    });

    const { wrapper } = createQueryHookHarness();
    const view = renderHook(() => useQueuedPromotionDecision(), { wrapper });

    expect(
      view.result.current.queuedStateByPromotionId.get("promotion-5"),
    ).toEqual({
      decision: "approved",
      queueStatus: "retrying",
      updatedAt: 200,
    });
    expect(view.result.current.isDecisionPending("promotion-5")).toBe(true);
    expect(view.result.current.isDecisionPending("promotion-6")).toBe(true);
    expect(view.result.current.isDecisionPending("promotion-7")).toBe(false);
  });
});
