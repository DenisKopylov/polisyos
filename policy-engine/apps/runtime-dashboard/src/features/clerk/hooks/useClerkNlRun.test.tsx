import { act, renderHook } from "@testing-library/react";

const {
  buildNaturalLanguageLaunchRequestMock,
  closeMock,
  launchMutationMock,
  subscribeMock,
} = vi.hoisted(() => ({
  buildNaturalLanguageLaunchRequestMock: vi.fn(() => ({
    nl_request: "question",
  })),
  closeMock: vi.fn(),
  launchMutationMock: vi.fn(),
  subscribeMock: vi.fn(),
}));

vi.mock("@/api/hooks/useLaunchNlRun", () => ({
  useLaunchNlRun: () => ({
    isPending: false,
    mutateAsync: launchMutationMock,
  }),
}));

vi.mock("@/api/hooks/useLlmProfiles", () => ({
  useLlmProfiles: () => ({ data: { profiles: [{ model_id: "model-1" }] } }),
}));

vi.mock("@/app/realtime/sseTransport", () => ({
  getSseRealtimeTransport: () => ({ subscribe: subscribeMock }),
}));

vi.mock("@/features/composer", () => ({
  buildNaturalLanguageLaunchRequest: buildNaturalLanguageLaunchRequestMock,
}));

vi.mock("@/shared/i18n/LocaleProvider", () => ({
  useI18n: () => ({ locale: "en" }),
}));

vi.mock("../domain/clerkDefaults", () => ({
  buildClerkFormDefaults: () => ({}),
}));

import { useClerkNlRun } from "./useClerkNlRun";
import { useChatStore } from "../state/useChatStore";

function resetStore() {
  useChatStore.setState({
    activeSessionId: null,
    currentRunId: null,
    isStreaming: false,
    messages: [],
    sessions: [],
  });
}

describe("useClerkNlRun", () => {
  beforeEach(() => {
    localStorage.clear();
    resetStore();
    buildNaturalLanguageLaunchRequestMock.mockClear();
    closeMock.mockReset();
    launchMutationMock.mockReset();
    subscribeMock.mockReset();
    subscribeMock.mockReturnValue({ close: closeMock });
  });

  it("launch acceptance rejection and transport failure never fabricate run lifecycle", async () => {
    launchMutationMock
      .mockResolvedValueOnce({
        job_id: "job-accepted",
        message: "accepted",
        run_id: "run-accepted",
        status: "accepted",
      })
      .mockResolvedValueOnce({
        job_id: "job-rejected",
        message: "rejected",
        run_id: "run-rejected",
        status: "rejected",
      })
      .mockRejectedValueOnce(new Error("transport unavailable"));
    const { result } = renderHook(() => useClerkNlRun());

    await act(async () => result.current.submit("accepted question"));
    expect(useChatStore.getState().messages.at(-1)).toMatchObject({
      runId: "run-accepted",
    });
    expect(useChatStore.getState().messages.at(-1)).not.toHaveProperty(
      "runStatus",
    );

    resetStore();
    await act(async () => result.current.submit("rejected question"));
    expect(useChatStore.getState().messages.at(-1)).not.toHaveProperty(
      "runStatus",
    );

    resetStore();
    await act(async () => result.current.submit("failed question"));
    expect(useChatStore.getState().messages.at(-1)).toMatchObject({
      error: "transport unavailable",
    });
    expect(useChatStore.getState().messages.at(-1)).not.toHaveProperty(
      "runStatus",
    );
  });

  it("novel SSE status cannot finish without finished_at", async () => {
    launchMutationMock.mockResolvedValue({
      job_id: "job-stream",
      message: "accepted",
      run_id: "run-stream",
      status: "accepted",
    });
    const { result } = renderHook(() => useClerkNlRun());

    await act(async () => result.current.submit("stream question"));
    expect(useChatStore.getState().messages.at(-1)).not.toHaveProperty(
      "runStatus",
    );

    const handlers = subscribeMock.mock.calls[0]?.[1] as {
      onMessage: (event: { data: string }) => void;
    };
    act(() => {
      handlers.onMessage({
        data: JSON.stringify({ status: "completed_future" }),
      });
    });

    expect(useChatStore.getState().messages.at(-1)).toMatchObject({
      runStatus: "completed_future",
    });
    expect(useChatStore.getState().isStreaming).toBe(true);
    expect(useChatStore.getState().currentRunId).toBe("run-stream");
    expect(closeMock).not.toHaveBeenCalled();
  });

  it("does not persist or finish from whitespace-only finished_at", async () => {
    launchMutationMock.mockResolvedValue({
      job_id: "job-stream",
      message: "accepted",
      run_id: "run-stream",
      status: "accepted",
    });
    const { result } = renderHook(() => useClerkNlRun());

    await act(async () => result.current.submit("stream question"));
    const handlers = subscribeMock.mock.calls[0]?.[1] as {
      onMessage: (event: { data: string }) => void;
    };
    act(() => {
      handlers.onMessage({
        data: JSON.stringify({
          finished_at: "   ",
          status: "completed_future",
        }),
      });
    });

    expect(useChatStore.getState().messages.at(-1)).toMatchObject({
      runStatus: "completed_future",
    });
    expect(useChatStore.getState().messages.at(-1)).not.toHaveProperty(
      "runFinishedAt",
    );
    expect(useChatStore.getState().isStreaming).toBe(true);
    expect(useChatStore.getState().currentRunId).toBe("run-stream");
    expect(closeMock).not.toHaveBeenCalled();
  });
});
