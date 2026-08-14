const {
  deleteComposerDraftRecordMock,
  loadComposerDraftRecordMock,
  saveComposerDraftRecordMock,
} = vi.hoisted(() => ({
  deleteComposerDraftRecordMock: vi.fn(),
  loadComposerDraftRecordMock: vi.fn(),
  saveComposerDraftRecordMock: vi.fn(),
}));

vi.mock("@/app/offline/composerDraftDb", () => ({
  deleteComposerDraftRecord: (...args: unknown[]) =>
    deleteComposerDraftRecordMock(...args),
  loadComposerDraftRecord: (...args: unknown[]) =>
    loadComposerDraftRecordMock(...args),
  saveComposerDraftRecord: (...args: unknown[]) =>
    saveComposerDraftRecordMock(...args),
}));

import {
  buildComposerDraftKey,
  deleteComposerDraft,
  loadComposerDraft,
  saveComposerDraft,
  type ComposerDraftRecord,
} from "@/features/composer/state/composerDraftRepository";

describe("composerDraftRepository", () => {
  beforeEach(() => {
    deleteComposerDraftRecordMock.mockReset();
    loadComposerDraftRecordMock.mockReset();
    saveComposerDraftRecordMock.mockReset();
  });

  it("builds stable keys for new and cloned drafts", () => {
    expect(buildComposerDraftKey("workflow", null)).toBe("workflow:new");
    expect(buildComposerDraftKey("nl", "run-7")).toBe("nl:run-7");
  });

  it("loads, saves, and deletes draft records through the composer database", async () => {
    const draft: ComposerDraftRecord = {
      fromRunId: "run-7",
      key: "workflow:run-7",
      mode: "workflow",
      updatedAt: 1_710_000_000_000,
      values: {
        checkpointPolicy: "strict",
        customParams: [],
        dataSourceRef: "artifact-1",
        dataSourceType: "snapshot",
        executionIntent: "Launch a verified run",
        expectedOutputs: [
          {
            description: "Decision packet",
            kind: "decision_packet",
          },
        ],
        governanceConstraints: [
          {
            rule: "legal review",
            scope: "legal",
            severity: "warning",
          },
        ],
        modelSpecRef: "model-default",
        policySpecRef: "policy-default",
        trinityRef: "trinity-default",
      },
    };

    loadComposerDraftRecordMock.mockResolvedValue(draft);
    saveComposerDraftRecordMock.mockResolvedValue(undefined);
    deleteComposerDraftRecordMock.mockResolvedValue(undefined);

    await expect(loadComposerDraft(draft.key)).resolves.toEqual(draft);
    await saveComposerDraft(draft);
    await deleteComposerDraft(draft.key);

    expect(loadComposerDraftRecordMock).toHaveBeenCalledWith(draft.key);
    expect(saveComposerDraftRecordMock).toHaveBeenCalledWith(draft);
    expect(deleteComposerDraftRecordMock).toHaveBeenCalledWith(draft.key);
  });
});
