import {
  buildComposerDraftKey,
  createComposerDraftRepository,
  type ComposerDraftRecord,
} from "@/features/composer/state/composerDraftRepository";

const scope = { tenantId: "tenant-a", userId: "reviewer-a" };
const workflowDraft: ComposerDraftRecord = {
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
    expectedOutputs: [{ description: "Decision packet", kind: "decision_packet" }],
    governanceConstraints: [
      { rule: "legal review", scope: "legal", severity: "warning" },
    ],
    modelSpecRef: "model-default",
    policySpecRef: "policy-default",
    trinityRef: "trinity-default",
  },
};
const nlDraft: ComposerDraftRecord = {
  fromRunId: null,
  key: "nl:new",
  mode: "nl",
  updatedAt: 1_710_000_000_001,
  values: {
    checkpointPolicy: "strict",
    domainHint: "custom",
    executionIntent: "Find constraints",
    expectedOutputs: [{ description: "Decision packet", kind: "decision_packet" }],
    governanceConstraints: [
      { rule: "legal review", scope: "legal", severity: "warning" },
    ],
    maxIterations: 3,
    maxParallelModels: 2,
    nlDataSourceRef: "artifact-2",
    nlRequest: "Assess the policy",
    perModelBudgetUsd: "",
    runBudgetUsd: "",
    selectedLlmModels: ["openai/gpt-5.4"],
  },
};
const partialWorkflowDraft: ComposerDraftRecord = {
  ...workflowDraft,
  fromRunId: null,
  key: "workflow:new",
  values: { ...workflowDraft.values, dataSourceRef: "" },
};
const partialNlDraft: ComposerDraftRecord = {
  ...nlDraft,
  values: {
    ...nlDraft.values,
    nlRequest: "",
    selectedLlmModels: [],
  },
};

function createMemoryPort() {
  const records = new Map<string, unknown>();
  return {
    delete: vi.fn(async (key: string) => {
      records.delete(key);
    }),
    get: vi.fn(async (key: string) => records.get(key)),
    put: vi.fn(async (record: { envelope: unknown; key: string }) => {
      records.set(record.key, record);
    }),
    records,
  };
}

describe("composerDraftRepository", () => {
  it("builds stable logical keys for new and cloned drafts", () => {
    expect(buildComposerDraftKey("workflow", null)).toBe("workflow:new");
    expect(buildComposerDraftKey("nl", "run-7")).toBe("nl:run-7");
  });

  it("does not touch IndexedDB without a settled tenant-user scope", async () => {
    const port = createMemoryPort();
    const repository = createComposerDraftRepository({
      clock: () => new Date("2026-08-14T10:00:00.000Z"),
      database: port,
    });

    await expect(repository.load(null, workflowDraft.key)).resolves.toBeNull();
    await expect(repository.save(null, workflowDraft)).resolves.toBe(false);
    await expect(repository.delete(null, workflowDraft.key)).resolves.toBe(false);

    expect(port.get).not.toHaveBeenCalled();
    expect(port.put).not.toHaveBeenCalled();
    expect(port.delete).not.toHaveBeenCalled();
  });

  it("persists and hydrates valid workflow and natural-language drafts in one scope", async () => {
    const port = createMemoryPort();
    const repository = createComposerDraftRepository({
      clock: () => new Date("2026-08-14T10:00:00.000Z"),
      database: port,
      // @ts-expect-error The composer TTL is fixed by its canonical owner.
      ttlMs: 48 * 60 * 60 * 1_000,
    });

    await expect(repository.save(scope, workflowDraft)).resolves.toBe(true);
    await expect(repository.save(scope, nlDraft)).resolves.toBe(true);
    await expect(repository.load(scope, workflowDraft.key)).resolves.toEqual(workflowDraft);
    await expect(repository.load(scope, nlDraft.key)).resolves.toEqual(nlDraft);
    const storedWorkflow = port.put.mock.calls[0]![0] as {
      envelope: { expiresAt: string; issuedAt: string };
    };
    expect(storedWorkflow.envelope).toMatchObject({
      expiresAt: "2026-08-15T10:00:00.000Z",
      issuedAt: "2026-08-14T10:00:00.000Z",
    });
    expect(
      Date.parse(storedWorkflow.envelope.expiresAt) -
        Date.parse(storedWorkflow.envelope.issuedAt),
    ).toBe(24 * 60 * 60 * 1_000);
  });

  it("round-trips exact in-progress workflow and natural-language defaults before launch admission", async () => {
    const port = createMemoryPort();
    const repository = createComposerDraftRepository({
      clock: () => new Date("2026-08-14T10:00:00.000Z"),
      database: port,
    });

    await expect(repository.save(scope, partialWorkflowDraft)).resolves.toBe(true);
    await expect(repository.save(scope, partialNlDraft)).resolves.toBe(true);
    await expect(
      repository.load(scope, partialWorkflowDraft.key),
    ).resolves.toEqual(partialWorkflowDraft);
    await expect(repository.load(scope, partialNlDraft.key)).resolves.toEqual(
      partialNlDraft,
    );
  });

  it("rejects blank stored model identifiers while allowing an empty in-progress selection", async () => {
    const port = createMemoryPort();
    const repository = createComposerDraftRepository({
      clock: () => new Date("2026-08-14T10:00:00.000Z"),
      database: port,
    });
    await repository.save(scope, nlDraft);
    const physicalKey = port.put.mock.calls[0]![0].key as string;
    const valid = port.records.get(physicalKey) as {
      envelope: Record<string, unknown>;
      key: string;
    };

    for (const modelId of ["", "   "]) {
      const stored = {
        ...valid,
        envelope: {
          ...valid.envelope,
          encodedPayload: {
            ...nlDraft,
            values: { ...nlDraft.values, selectedLlmModels: [modelId] },
          },
        },
      };
      port.records.set(physicalKey, stored);
      await expect(repository.load(scope, nlDraft.key)).resolves.toBeNull();
      expect(port.records.get(physicalKey)).toBe(stored);
    }
    expect(port.put).toHaveBeenCalledTimes(1);
  });

  it("fails closed without rewriting legacy, foreign, expired, copied, or codec-invalid bytes", async () => {
    const port = createMemoryPort();
    const repository = createComposerDraftRepository({
      clock: () => new Date("2026-08-14T10:00:00.000Z"),
      database: port,
    });
    await repository.save(scope, workflowDraft);
    const physicalKey = port.put.mock.calls[0]![0].key as string;
    const valid = port.records.get(physicalKey) as {
      envelope: Record<string, unknown>;
      key: string;
    };
    const cases: Array<[string, unknown]> = [
      ["legacy", workflowDraft],
      ["malformed", { key: physicalKey, envelope: "not-an-envelope" }],
      ["extra wrapper field", { ...valid, extra: true }],
      [
        "wrong version",
        { ...valid, envelope: { ...valid.envelope, version: 2 } },
      ],
      [
        "expired",
        {
          ...valid,
          envelope: {
            ...valid.envelope,
            expiresAt: "2026-08-14T09:59:59.999Z",
            issuedAt: "2026-08-13T09:59:59.999Z",
          },
        },
      ],
      [
        "prior tenant",
        { ...valid, envelope: { ...valid.envelope, tenantId: "tenant-prior" } },
      ],
      [
        "prior user",
        { ...valid, envelope: { ...valid.envelope, userId: "reviewer-prior" } },
      ],
      [
        "future issued",
        {
          ...valid,
          envelope: {
            ...valid.envelope,
            expiresAt: "2026-08-15T10:00:00.001Z",
            issuedAt: "2026-08-14T10:00:00.001Z",
          },
        },
      ],
      [
        "copied slot",
        { ...valid, envelope: { ...valid.envelope, slot: "workflow:new" } },
      ],
      [
        "extended ttl",
        {
          ...valid,
          envelope: { ...valid.envelope, expiresAt: "2026-08-15T10:00:00.001Z" },
        },
      ],
      [
        "invalid codec",
        {
          ...valid,
          envelope: {
            ...valid.envelope,
            encodedPayload: { ...workflowDraft, values: { not: "a form" } },
          },
        },
      ],
    ];

    for (const [_label, raw] of cases) {
      port.records.set(physicalKey, raw);
      await expect(repository.load(scope, workflowDraft.key)).resolves.toBeNull();
      expect(port.records.get(physicalKey)).toBe(raw);
    }
    expect(port.put).toHaveBeenCalledTimes(1);
  });

  it("contains IndexedDB failures and refuses to leave a caller-supplied expiry seam", async () => {
    const database = {
      delete: vi.fn(async () => {
        throw new Error("delete unavailable");
      }),
      get: vi.fn(async () => {
        throw new Error("get unavailable");
      }),
      put: vi.fn(async () => {
        throw new Error("put unavailable");
      }),
    };
    const repository = createComposerDraftRepository({
      clock: () => new Date("2026-08-14T10:00:00.000Z"),
      database,
    });

    await expect(repository.load(scope, workflowDraft.key)).resolves.toBeNull();
    await expect(repository.save(scope, workflowDraft)).resolves.toBe(false);
    await expect(repository.delete(scope, workflowDraft.key)).resolves.toBe(false);
  });

  it("contains owner clock failures at the async composer boundary", async () => {
    const port = createMemoryPort();
    const validRepository = createComposerDraftRepository({
      clock: () => new Date("2026-08-14T10:00:00.000Z"),
      database: port,
    });
    await validRepository.save(scope, workflowDraft);
    const clockFailureRepository = createComposerDraftRepository({
      clock: () => {
        throw new Error("clock unavailable");
      },
      database: port,
    });

    await expect(
      clockFailureRepository.load(scope, workflowDraft.key),
    ).resolves.toBeNull();
    await expect(clockFailureRepository.save(scope, workflowDraft)).resolves.toBe(false);
    expect(port.put).toHaveBeenCalledTimes(1);
  });

  it("contains real composer codec exceptions without writing or replacing stored bytes", async () => {
    const port = createMemoryPort();
    const repository = createComposerDraftRepository({
      clock: () => new Date("2026-08-14T10:00:00.000Z"),
      database: port,
    });
    await repository.save(scope, workflowDraft);
    const physicalKey = port.put.mock.calls[0]![0].key as string;
    const valid = port.records.get(physicalKey) as {
      envelope: Record<string, unknown>;
      key: string;
    };
    const hostilePayload = new Proxy(
      {},
      {
        get() {
          throw new Error("codec input unavailable");
        },
      },
    );
    const hostileStored = {
      ...valid,
      envelope: { ...valid.envelope, encodedPayload: hostilePayload },
    };
    port.records.set(physicalKey, hostileStored);

    await expect(repository.load(scope, workflowDraft.key)).resolves.toBeNull();
    expect(port.records.get(physicalKey)).toBe(hostileStored);
    await expect(
      repository.save(scope, hostilePayload as unknown as ComposerDraftRecord),
    ).resolves.toBe(false);
    expect(port.put).toHaveBeenCalledTimes(1);
  });
});
