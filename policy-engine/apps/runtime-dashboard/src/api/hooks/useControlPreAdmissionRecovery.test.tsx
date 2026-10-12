import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";

const { readMock, observeMock, byKeyMock, byIdMock } = vi.hoisted(() => ({
  readMock: vi.fn(),
  observeMock: vi.fn(),
  byKeyMock: vi.fn(),
  byIdMock: vi.fn(),
}));

vi.mock("../controlPreAdmissionRecovery", () => ({
  controlPreAdmissionRecoveryRepository: {
    read: (...args: unknown[]) => readMock(...args),
    observe: (...args: unknown[]) => observeMock(...args),
  },
}));
vi.mock("./useControlPreAdmissionAttemptStatus", () => ({
  fetchControlPreAdmissionAttemptByIdempotencyKey: (...args: unknown[]) =>
    byKeyMock(...args),
  fetchControlPreAdmissionAttemptStatus: (...args: unknown[]) =>
    byIdMock(...args),
}));

import { useControlPreAdmissionRecovery } from "./useControlPreAdmissionRecovery";

const scope = { tenantId: "tenant-a", cellId: "cell-a", userId: "principal-a" };
const attempt = {
  attempt_id: "a".repeat(32),
  status: "settled",
  run_id: "run-a",
  job_id: null,
  producer_event_ids: ["producer-event-a"],
};
const pendingRecord = {
  scopeKey: "c".repeat(64),
  scopeSha256: "c".repeat(64),
  bodySha256: "d".repeat(64),
  idempotencyKey: "opaque-recovery-key",
  attemptId: null,
  status: null,
  runId: null,
  jobId: null,
  producerEventIds: [],
  lastSequence: 0,
  updatedAt: null,
};

function renderRecovery() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return renderHook(() => useControlPreAdmissionRecovery(scope), { wrapper });
}

describe("useControlPreAdmissionRecovery", () => {
  beforeEach(() => {
    readMock.mockReset();
    readMock.mockResolvedValue(pendingRecord);
    observeMock.mockReset();
    observeMock.mockImplementation(async (_scope, value) => ({
      ...pendingRecord,
      idempotencyKey: null,
      attemptId: value.attempt_id,
      status: value.status,
      runId: value.run_id,
      producerEventIds: value.producer_event_ids,
      lastSequence: 2,
    }));
    byKeyMock.mockReset();
    byIdMock.mockReset();
  });

  it("resolves a persisted key to server attempt and event refs after remount", async () => {
    byKeyMock.mockResolvedValue(attempt);
    const { result } = renderRecovery();

    await waitFor(() =>
      expect(result.current.data?.attempt?.attempt_id).toBe(attempt.attempt_id),
    );
    expect(byKeyMock).toHaveBeenCalledWith("opaque-recovery-key");
    expect(byIdMock).not.toHaveBeenCalled();
    expect(observeMock).toHaveBeenCalledWith(scope, attempt);
    expect(result.current.data?.record.producerEventIds).toEqual([
      "producer-event-a",
    ]);
  });

  it("does not query a cleared no-attempt record", async () => {
    readMock.mockResolvedValue({ ...pendingRecord, idempotencyKey: null });
    const { result } = renderRecovery();
    await waitFor(() => expect(result.current.data).toBeNull());
    expect(byKeyMock).not.toHaveBeenCalled();
  });

  it("keeps a no-row lookup unresolved instead of clearing the request key", async () => {
    byKeyMock.mockResolvedValue(null);
    const { result } = renderRecovery();

    await waitFor(() =>
      expect(result.current.data?.record.idempotencyKey).toBe(
        "opaque-recovery-key",
      ),
    );
    expect(result.current.data?.attempt).toBeNull();
    expect(observeMock).not.toHaveBeenCalled();
  });
});
