import type { PropsWithChildren } from "react";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createQueryHookHarness } from "@/test/queryHook";

import {
  QuantityRuntimeBridgeProvider,
  type QuantityRuntimeBridgeValue,
} from "./QuantityRuntimeBridge";
import type {
  LineageBatchResponsePayload,
  LineageGraphView,
  LineageResponsePayload,
  LineageBatchSelector,
  SelectedArtifactRef,
  TemporalRef,
} from "./quantity.types";
import { useLineage } from "./useLineage";
import {
  alignLineageBatchResponses,
  boundLineageQueryKey,
  profileBindingAdmissionQueryKey,
  profileBindingIdentityKey,
  sameTemporalScope,
  useAdmittedBoundLineage,
  useProfileBindingAdmission,
  useBoundLineage,
  useLineageBatch,
} from "./useLineageBatch";

const meta: LineageResponsePayload["meta"] = {
  generated_at: "2026-04-24T12:00:00Z",
  request_id: "req-lineage-hook",
  source_kinds: ["core_run"],
};

const temporalScope: TemporalRef = {
  valid_at: "2026-04-15T12:00:00Z",
  tx_at: "2026-04-15T12:05:00Z",
  branch: "main",
  snapshot_id: null,
  scenario_id: null,
};

const artifactId = `sha256:${"a".repeat(64)}`;
const profileA: SelectedArtifactRef = {
  artifact_id: artifactId,
  kind: "core.decision_packet",
  media_type: "application/json",
  manifest_profile_sha256: `sha256:${"1".repeat(64)}`,
};
const profileB: SelectedArtifactRef = {
  ...profileA,
  manifest_profile_sha256: `sha256:${"2".repeat(64)}`,
};
const selectorA: LineageBatchSelector = {
  lineageId: `artifact:${artifactId}`,
  selectedArtifactRef: profileA,
  artifactRefProvenance: "reader_materialized",
  sourceRunId: "run-1",
};
const selectorB: LineageBatchSelector = {
  ...selectorA,
  selectedArtifactRef: profileB,
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("lineage hooks", () => {
  it("delegates one legacy lineage lookup with the canonical temporal ref", async () => {
    const response = {
      meta,
      temporal_scope: { valid_at: "2026-04-15T12:00:00Z" },
      lineage: {
        id: "lin_a",
        status: "verified",
        freshness: "current",
        exports: { openlineage: "/openlineage", prov: "/prov" },
      },
    } satisfies LineageResponsePayload;
    const bridge = runtimeBridge();
    vi.mocked(bridge.fetchLineage).mockResolvedValue(response);

    const { result } = renderHook(
      () =>
        useLineage("lin_a", {
          temporalScope: { valid_at: "2026-04-15T12:00:00Z" },
        }),
      { wrapper: bridgeWrapper(bridge).wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(bridge.fetchLineage).toHaveBeenCalledWith("lin_a", {
      valid_at: "2026-04-15T12:00:00Z",
    });
  });

  it("preserves an explicitly omitted scope instead of inheriting the cursor", async () => {
    const bridge = runtimeBridge();
    bridge.temporalScope = temporalScope;
    vi.mocked(bridge.fetchLineage).mockResolvedValue({
      meta,
      temporal_scope: undefined,
      lineage: {
        id: "lin_a",
        status: "verified",
        freshness: "current",
        exports: { openlineage: "/openlineage", prov: "/prov" },
      },
    } satisfies LineageResponsePayload);

    const { result } = renderHook(
      () => useLineage("lin_a", { temporalScope: undefined }),
      { wrapper: bridgeWrapper(bridge).wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(bridge.fetchLineage).toHaveBeenCalledWith("lin_a", undefined);
  });

  it("keeps same-byte artifact views with different profiles as separate batch selectors", async () => {
    const bridge = runtimeBridge();
    vi.mocked(bridge.fetchLineageBatch).mockResolvedValue(
      batchResponse([profileGraph(profileA), profileGraph(profileB)]),
    );

    const harness = bridgeWrapper(bridge);
    const { result } = renderHook(
      () =>
        useLineageBatch([selectorA, selectorB], {
          runId: "run-1",
          temporalScope,
        }),
      { wrapper: harness.wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(bridge.fetchLineageBatch).toHaveBeenCalledTimes(1);
    expect(bridge.fetchLineageBatch).toHaveBeenCalledWith(
      [selectorA, selectorB],
      "run-1",
      temporalScope,
    );
    expect(
      result.current.data?.lineages?.map((item) => item.selected_artifact_ref),
    ).toEqual([profileA, profileB]);
    const keyA = boundLineageQueryKey(selectorA, "run-1", temporalScope);
    const keyB = boundLineageQueryKey(selectorB, "run-1", temporalScope);
    expect(keyA).not.toEqual(keyB);
    expect(harness.queryClient.getQueryData(keyA)).toMatchObject({
      lineage: { selected_artifact_ref: profileA },
    });
    expect(harness.queryClient.getQueryData(keyB)).toMatchObject({
      lineage: { selected_artifact_ref: profileB },
    });
  });

  it("shares the exact run/profile/time graph with a later provenance consumer", async () => {
    const bridge = runtimeBridge();
    const graph = profileGraph(profileA);
    vi.mocked(bridge.fetchLineageBatch).mockResolvedValue(
      batchResponse([graph]),
    );

    const harness = bridgeWrapper(bridge);
    const { result } = renderHook(
      () => {
        const batch = useLineageBatch([selectorA], {
          runId: "run-1",
          temporalScope,
        });
        const bound = useBoundLineage(selectorA, {
          enabled: batch.isSuccess,
          runId: "run-1",
          temporalScope,
        });
        return { batch, bound };
      },
      { wrapper: harness.wrapper },
    );

    await waitFor(() => expect(result.current.bound.isSuccess).toBe(true));
    expect(bridge.fetchLineageBatch).toHaveBeenCalledTimes(1);
    expect(result.current.bound.data?.lineage.selected_artifact_ref).toEqual(
      profileA,
    );
    expect(
      harness.queryClient.getQueryData(
        boundLineageQueryKey(selectorA, "run-1", temporalScope),
      ),
    ).toMatchObject({ lineage: { selected_artifact_ref: profileA } });
  });

  it("rejects an older cached graph after the shared identity fails revalidation", async () => {
    const bridge = runtimeBridge();
    vi.mocked(bridge.fetchLineageBatch)
      .mockResolvedValueOnce(batchResponse([profileGraph(profileA)]))
      .mockRejectedValueOnce(new Error("profile batch revalidation failed"));

    const harness = bridgeWrapper(bridge);
    const { result } = renderHook(
      () => {
        const batch = useLineageBatch([selectorA], {
          runId: "run-1",
          temporalScope,
        });
        const bound = useAdmittedBoundLineage(selectorA, {
          enabled: false,
          runId: "run-1",
          temporalScope,
        });
        const admission = useProfileBindingAdmission(
          selectorA,
          "run-1",
          temporalScope,
        );
        return { batch, bound, admission };
      },
      { wrapper: harness.wrapper },
    );

    await waitFor(() => {
      expect(result.current.batch.isSuccess).toBe(true);
      expect(result.current.bound.profileBindingContext).not.toBeNull();
    });
    const cachedGraph = harness.queryClient.getQueryData<{
      profileBindingGeneration?: number;
    }>(boundLineageQueryKey(selectorA, "run-1", temporalScope));
    expect(cachedGraph?.profileBindingGeneration).toBe(1);
    expect(result.current.admission).toMatchObject({
      generation: 1,
      outcome: "admitted",
      graph: { profileBindingGeneration: 1 },
    });

    await harness.queryClient.refetchQueries({
      queryKey: ["quantity-lineage-batch"],
    });

    await waitFor(() => expect(result.current.batch.isError).toBe(true));
    expect(result.current.admission).toEqual({
      generation: 2,
      outcome: "rejected",
    });
    expect(result.current.bound.profileBindingContext).toBeNull();
    expect(
      harness.queryClient.getQueryData(
        boundLineageQueryKey(selectorA, "run-1", temporalScope),
      ),
    ).toMatchObject({ profileBindingGeneration: 1 });
    expect(
      harness.queryClient.getQueryData(
        profileBindingAdmissionQueryKey(selectorA, "run-1", temporalScope),
      ),
    ).toEqual({ generation: 2, outcome: "rejected" });
  });

  it("keys one admission by every member of the full profile identity", () => {
    const identity = profileBindingIdentityKey(
      selectorA,
      "run-1",
      temporalScope,
    );
    const changes = [
      profileBindingIdentityKey(
        { ...selectorA, lineageId: "artifact:other" },
        "run-1",
        temporalScope,
      ),
      profileBindingIdentityKey(
        {
          ...selectorA,
          selectedArtifactRef: { ...profileA, kind: "core.other" },
        },
        "run-1",
        temporalScope,
      ),
      profileBindingIdentityKey(
        {
          ...selectorA,
          selectedArtifactRef: { ...profileA, media_type: "application/other" },
        },
        "run-1",
        temporalScope,
      ),
      profileBindingIdentityKey(
        { ...selectorA, selectedArtifactRef: profileB },
        "run-1",
        temporalScope,
      ),
      profileBindingIdentityKey(
        { ...selectorA, sourceRunId: "run-2" },
        "run-1",
        temporalScope,
      ),
      profileBindingIdentityKey(
        { ...selectorA, artifactRefProvenance: "run_output_ref" },
        "run-1",
        temporalScope,
      ),
      profileBindingIdentityKey(selectorA, "run-2", temporalScope),
      profileBindingIdentityKey(selectorA, "run-1", {
        ...temporalScope,
        branch: "other-branch",
      }),
      profileBindingIdentityKey(selectorA, "run-1", {
        ...temporalScope,
        branch: null,
      }),
      profileBindingIdentityKey(selectorA, "run-1", {
        ...temporalScope,
        branch: undefined,
      }),
      profileBindingIdentityKey(selectorA, "run-1", null),
      profileBindingIdentityKey(selectorA, "run-1", undefined),
    ];
    expect(new Set(changes).size).toBe(changes.length);
    expect(changes).not.toContain(identity);
    expect(sameTemporalScope({ branch: null }, {})).toBe(false);
  });

  it("preserves an omitted batch scope instead of inheriting a runtime cursor", async () => {
    const bridge = runtimeBridge();
    bridge.temporalScope = temporalScope;
    const legacySelector: LineageBatchSelector = {
      lineageId: "legacy:quantity",
      selectedArtifactRef: null,
      artifactRefProvenance: null,
      sourceRunId: null,
    };
    const legacyGraph = {
      id: legacySelector.lineageId,
      status: "verified",
      freshness: "current",
      profile_binding_status: "not_established",
      selected_artifact_ref: null,
      artifact_ref_provenance: null,
      source_run_id: null,
      trust_metadata: null,
      nodes: [],
      edges: [],
    } as unknown as LineageGraphView;
    vi.mocked(bridge.fetchLineageBatch).mockResolvedValue(
      batchResponse([legacyGraph], undefined),
    );
    const harness = bridgeWrapper(bridge);

    const { result } = renderHook(
      () =>
        useLineageBatch([legacySelector], {
          temporalScope: undefined,
        }),
      { wrapper: harness.wrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(bridge.fetchLineageBatch).toHaveBeenCalledWith(
      [legacySelector],
      undefined,
      undefined,
    );
    expect(
      harness.queryClient.getQueryData(
        profileBindingAdmissionQueryKey(legacySelector, undefined, undefined),
      ),
    ).toMatchObject({ outcome: "rejected" });
  });

  it("rejects a same-id response carrying the sibling profile", () => {
    const response = batchResponse([profileGraph(profileB)]);
    expect(() =>
      alignLineageBatchResponses([selectorA], response, {
        runId: "run-1",
        temporalScope,
      }),
    ).toThrow(/unrequested or unbound item|selected profile/);
  });

  it("allows a legacy informational graph while refusing a trust grade", () => {
    const legacy = {
      id: selectorA.lineageId,
      status: "verified",
      freshness: "current",
      profile_binding_status: "not_established",
      selected_artifact_ref: null,
      artifact_ref_provenance: null,
      source_run_id: null,
      trust_metadata: null,
      nodes: [],
      edges: [],
    } as unknown as LineageGraphView;
    const response = batchResponse([legacy]);

    expect(
      alignLineageBatchResponses(
        [{ lineageId: selectorA.lineageId }],
        response,
        { runId: "run-1", temporalScope },
      ),
    ).toEqual([{ requestIndex: 0, lineage: legacy }]);
  });

  it("does not cache a same-ID response that omits its selected-profile declaration", async () => {
    const bridge = runtimeBridge();
    const undeclared = {
      ...profileGraph(profileA),
      selected_artifact_ref: null,
      profile_binding_status: "not_established",
      trust_metadata: null,
    } as unknown as LineageGraphView;
    vi.mocked(bridge.fetchLineageBatch).mockResolvedValue(
      batchResponse([undeclared]),
    );

    const harness = bridgeWrapper(bridge);
    const { result } = renderHook(
      () =>
        useLineageBatch([selectorA], {
          runId: "run-1",
          temporalScope,
        }),
      { wrapper: harness.wrapper },
    );

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error?.message).toContain("unbound item");
    expect(
      harness.queryClient.getQueryData(
        boundLineageQueryKey(selectorA, "run-1", temporalScope),
      ),
    ).toBeUndefined();
  });

  it("requires every profile/run/origin/time selector member", () => {
    const graph = profileGraph(profileA);
    const response = batchResponse([graph]);

    expect(() =>
      alignLineageBatchResponses(
        [{ ...selectorA, sourceRunId: null }],
        response,
        { runId: "run-1", temporalScope },
      ),
    ).toThrow(/unrequested or unbound item/);
    expect(() =>
      alignLineageBatchResponses(
        [{ ...selectorA, artifactRefProvenance: null }],
        response,
        { runId: "run-1", temporalScope },
      ),
    ).toThrow(/unrequested or unbound item/);
    expect(() =>
      alignLineageBatchResponses([selectorA], response, {
        runId: "run-2",
        temporalScope,
      }),
    ).toThrow(/unrequested or unbound item/);

    const siblingOrigin = {
      ...graph,
      artifact_ref_provenance: "run_output_ref",
    } as unknown as LineageGraphView;
    expect(() =>
      alignLineageBatchResponses([selectorA], batchResponse([siblingOrigin]), {
        runId: "run-1",
        temporalScope,
      }),
    ).toThrow(/unrequested or unbound item/);
  });

  it("keeps explicit null time distinct from omitted time and follows cursor changes", async () => {
    const nullScopedGraph = profileGraph(profileA, null);
    const nullScopedResponse = batchResponse([nullScopedGraph], null);
    expect(
      alignLineageBatchResponses([selectorA], nullScopedResponse, {
        runId: "run-1",
        temporalScope: null,
      }),
    ).toHaveLength(1);
    expect(() =>
      alignLineageBatchResponses([selectorA], nullScopedResponse),
    ).toThrow(/temporal scope/);
    expect(boundLineageQueryKey(selectorA, "run-1", null)).not.toEqual(
      boundLineageQueryKey(selectorA, "run-1", undefined),
    );

    const bridge = runtimeBridge();
    const firstScope = temporalScope;
    const secondScope = { ...temporalScope, branch: "cursor-next" };
    vi.mocked(bridge.fetchLineageBatch).mockImplementation(
      async (_selectors, _runId, scope) =>
        batchResponse([profileGraph(profileA, scope)], scope),
    );
    const harness = createQueryHookHarness();
    let activeScope: TemporalRef | null = firstScope;
    function CursorWrapper({ children }: PropsWithChildren) {
      return (
        <harness.wrapper>
          <QuantityRuntimeBridgeProvider
            value={{ ...bridge, temporalScope: activeScope }}
          >
            {children}
          </QuantityRuntimeBridgeProvider>
        </harness.wrapper>
      );
    }
    const { result, rerender } = renderHook(
      () => useLineageBatch([selectorA], { runId: "run-1" }),
      { wrapper: CursorWrapper },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    activeScope = secondScope;
    rerender();
    await waitFor(() =>
      expect(bridge.fetchLineageBatch).toHaveBeenCalledTimes(2),
    );
    expect(result.current.data?.temporal_scope).toEqual(secondScope);

    const pinned = renderHook(
      () =>
        useBoundLineage(selectorA, {
          runId: "run-1",
          temporalScope: null,
        }),
      { wrapper: CursorWrapper },
    );
    await waitFor(() => expect(pinned.result.current.isSuccess).toBe(true));
    expect(bridge.fetchLineageBatch).toHaveBeenLastCalledWith(
      [selectorA],
      "run-1",
      null,
    );
  });

  it("rejects trust metadata from a different temporal scope", () => {
    const wrongScope = profileGraph(profileA, {
      ...temporalScope,
      branch: "other-branch",
    });
    expect(() =>
      alignLineageBatchResponses([selectorA], batchResponse([wrongScope]), {
        runId: "run-1",
        temporalScope,
      }),
    ).toThrow(/temporal scope/);
  });
});

function profileGraph(
  ref: SelectedArtifactRef,
  trustScope: TemporalRef | null | undefined = temporalScope,
): LineageGraphView {
  return {
    id: `artifact:${ref.artifact_id}`,
    status: "verified",
    freshness: "current",
    selected_artifact_ref: ref,
    profile_binding_status: "verified",
    artifact_ref_provenance: "reader_materialized",
    source_run_id: "run-1",
    trust_metadata: {
      verification_status: "verified",
      freshness: "current",
      dispute_status: null,
      verified_by: "producer-owner",
      verified_at: "2026-04-15T12:00:00Z",
      verification_method: "selected-profile-reader",
      temporal_scope: trustScope,
    },
    nodes: [],
    edges: [],
  } as unknown as LineageGraphView;
}

function batchResponse(
  lineages: LineageGraphView[],
  responseScope: TemporalRef | null | undefined = temporalScope,
): LineageBatchResponsePayload {
  return {
    meta,
    temporal_scope: responseScope,
    lineages,
    lineage_resolutions: lineages.map((lineage) => ({
      requested_lineage_id: lineage.id,
      resolved_lineage_id: lineage.id,
    })),
  } as unknown as LineageBatchResponsePayload;
}

function runtimeBridge(): QuantityRuntimeBridgeValue {
  return {
    fetchLineage: vi.fn(),
    fetchLineageBatch: vi.fn(),
    fetchLineageExport: vi.fn(),
    temporalScope: null,
    trustMode: "off",
  };
}

function bridgeWrapper(value: QuantityRuntimeBridgeValue) {
  const harness = createQueryHookHarness();
  function BridgeWrapper({ children }: PropsWithChildren) {
    return (
      <harness.wrapper>
        <QuantityRuntimeBridgeProvider value={value}>
          {children}
        </QuantityRuntimeBridgeProvider>
      </harness.wrapper>
    );
  }
  return { wrapper: BridgeWrapper, queryClient: harness.queryClient };
}
