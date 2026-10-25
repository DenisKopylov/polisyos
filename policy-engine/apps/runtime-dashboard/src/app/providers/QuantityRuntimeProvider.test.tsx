import type { PropsWithChildren, ReactElement } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, renderHook, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  mockRuntimeGetFailure,
  mockRuntimeGetSuccess,
  mockRuntimePostSuccess,
} from "@/test/runtimeApi";
import { LocaleProvider } from "@/shared/i18n/LocaleProvider";
import {
  type LineageBatchSelector,
  type QuantityValue,
  type TemporalRef,
  useQuantityRuntimeBridge,
} from "@/shared/ui/quantity";
import {
  boundLineageQueryKey,
  profileBindingAdmissionQueryKey,
} from "@/shared/ui/quantity/useLineageBatch";

import { TemporalCursorProvider } from "./TemporalCursorProvider";
import { TrustViewProvider } from "./TrustViewProvider";
import { QuantityRuntimeProvider } from "./QuantityRuntimeProvider";

const meta = {
  generated_at: "2026-07-19T12:00:00Z",
  request_id: "req-quantity-runtime-provider",
  source_kinds: ["core_run"],
} as const;

const temporalScope = {
  branch: "main",
  scenario_id: "scenario-a",
  snapshot_id: "snapshot-a",
  tx_at: "2026-07-18T12:00:00Z",
  valid_at: "2026-07-17T12:00:00Z",
} satisfies TemporalRef;

const committedTemporalScope = {
  ...temporalScope,
  tx_at: "2026-07-18T12:00:00.000Z",
  valid_at: "2026-07-17T12:00:00.000Z",
} satisfies TemporalRef;

const lineage = {
  id: "lineage-a",
  status: "verified",
  freshness: "current",
  exports: {
    openlineage: "/api/v1/lineage/lineage-a/export/openlineage",
    prov: "/api/v1/lineage/lineage-a/export/prov",
  },
} as const;
const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, gcTime: Infinity } },
});

afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/");
  window.localStorage.clear();
  queryClient.clear();
});

describe("QuantityRuntimeProvider", () => {
  it("maps the committed cursor and validates a single lineage response", async () => {
    window.history.replaceState(
      null,
      "",
      "/runs/run-a?valid_at=2026-07-17T12%3A00%3A00Z&tx_at=2026-07-18T12%3A00%3A00Z&branch=main&snapshot_id=snapshot-a&scenario_id=scenario-a",
    );
    const getSpy = mockRuntimeGetSuccess({
      lineage,
      meta,
      temporal_scope: temporalScope,
    });
    const { result } = renderHook(() => useQuantityRuntimeBridge(), {
      wrapper: providerWrapper,
    });

    expect(result.current.temporalScope).toEqual(committedTemporalScope);
    await expect(
      result.current.fetchLineage("lineage-a", result.current.temporalScope),
    ).resolves.toMatchObject({
      lineage: {
        compact_summary: [],
        edges: [],
        metadata: {},
        nodes: [],
      },
    });
    expect(getSpy).toHaveBeenCalledWith("/api/v1/lineage/{lineage_id}", {
      params: {
        path: { lineage_id: "lineage-a" },
        query: committedTemporalScope,
      },
    });

    getSpy.mockResolvedValueOnce({
      data: { lineage: { id: "lineage-a" }, meta },
      error: undefined,
      response: new Response("{}", { status: 200 }),
    } as never);
    await expect(
      result.current.fetchLineage("lineage-a", null),
    ).rejects.toThrow();

    getSpy.mockResolvedValueOnce({
      data: {
        lineage: {
          ...lineage,
          id: "lineage-b",
          hash: "sha256:foreign-lineage",
          trust_metadata: {
            hash: "sha256:foreign-lineage",
            verification_status: "verified",
            verified_by: "runtime-verifier",
            verified_at: "2026-07-19T11:00:00Z",
            verification_method: "lineage_hash_match",
            freshness: "current",
            dispute_status: "none",
            temporal_scope: temporalScope,
          },
        },
        meta,
        temporal_scope: temporalScope,
      },
      error: undefined,
      response: new Response("{}", { status: 200 }),
    } as never);
    await expect(
      result.current.fetchLineage("lineage-a", null),
    ).rejects.toThrow("does not match the requested lineage ID");
  });

  it("posts batch identities and normalizes optional graph collections", async () => {
    const postSpy = mockRuntimePostSuccess({
      lineages: [lineage],
      meta,
      temporal_scope: temporalScope,
    });
    const { result } = renderHook(() => useQuantityRuntimeBridge(), {
      wrapper: providerWrapper,
    });

    const response = await result.current.fetchLineageBatch(
      legacySelectors(["lineage-a", "lineage-b"]),
      undefined,
      temporalScope,
    );

    expect(response.lineages?.[0]).toMatchObject({
      compact_summary: [],
      edges: [],
      metadata: {},
      nodes: [],
    });
    expect(postSpy).toHaveBeenCalledWith("/api/v1/lineage/batch", {
      body: { lineage_ids: ["lineage-a", "lineage-b"] },
      params: { query: temporalScope },
    });
  });

  it("joins aliases and partial duplicate batches to server resolutions", async () => {
    const canonicalA = "artifact:canonical-a";
    const canonicalB = "artifact:canonical-b";
    const postSpy = mockRuntimePostSuccess({
      lineages: [
        { ...lineage, id: canonicalA },
        { ...lineage, id: canonicalB },
        { ...lineage, id: canonicalA },
      ],
      lineage_resolutions: [
        {
          requested_lineage_id: "artifact-alias-a",
          resolved_lineage_id: canonicalA,
        },
        {
          requested_lineage_id: "artifact-alias-b",
          resolved_lineage_id: canonicalB,
        },
        {
          requested_lineage_id: "artifact-alias-a",
          resolved_lineage_id: canonicalA,
        },
      ],
      meta,
      temporal_scope: temporalScope,
    });
    const { result } = renderHook(() => useQuantityRuntimeBridge(), {
      wrapper: providerWrapper,
    });

    const response = await result.current.fetchLineageBatch(
      legacySelectors([
        "artifact-alias-a",
        "artifact-alias-b",
        "artifact-alias-a",
      ]),
      undefined,
      temporalScope,
    );

    expect(response.lineages?.map((item) => item.id)).toEqual([
      canonicalA,
      canonicalB,
      canonicalA,
    ]);
    expect(postSpy).toHaveBeenCalledWith("/api/v1/lineage/batch", {
      body: {
        lineage_ids: [
          "artifact-alias-a",
          "artifact-alias-b",
          "artifact-alias-a",
        ],
      },
      params: { query: temporalScope },
    });
  });

  it("accepts mapped partial alias subsequences in requested order", async () => {
    const canonicalA = "artifact:canonical-a";
    const canonicalB = "artifact:canonical-b";
    mockRuntimePostSuccess({
      lineages: [
        { ...lineage, id: canonicalB },
        { ...lineage, id: canonicalA },
      ],
      lineage_resolutions: [
        {
          requested_lineage_id: "artifact-alias-b",
          resolved_lineage_id: canonicalB,
        },
        {
          requested_lineage_id: "artifact-alias-a",
          resolved_lineage_id: canonicalA,
        },
      ],
      meta,
      temporal_scope: temporalScope,
    });
    const { result } = renderHook(() => useQuantityRuntimeBridge(), {
      wrapper: providerWrapper,
    });

    await expect(
      result.current.fetchLineageBatch(
        legacySelectors([
          "artifact-alias-a",
          "artifact-alias-b",
          "artifact-alias-a",
        ]),
        undefined,
        temporalScope,
      ),
    ).resolves.toMatchObject({
      lineages: [{ id: canonicalB }, { id: canonicalA }],
    });
  });

  it("rejects a foreign requested selector when its resolved graph ID matches", async () => {
    mockRuntimePostSuccess({
      lineages: [{ ...lineage, id: "artifact:canonical-a" }],
      lineage_resolutions: [
        {
          requested_lineage_id: "artifact-alias-foreign",
          resolved_lineage_id: "artifact:canonical-a",
        },
      ],
      meta,
      temporal_scope: temporalScope,
    });
    const { result } = renderHook(() => useQuantityRuntimeBridge(), {
      wrapper: providerWrapper,
    });

    await expect(
      result.current.fetchLineageBatch(
        legacySelectors(["artifact-alias-a"]),
        undefined,
        temporalScope,
      ),
    ).rejects.toThrow("unrequested or unbound item");
  });

  it("does not downgrade malformed present mappings to legacy exact-ID responses", async () => {
    mockRuntimePostSuccess({
      lineages: [{ ...lineage, id: "artifact:canonical-a" }],
      lineage_resolutions: [{ requested_lineage_id: "artifact:canonical-a" }],
      meta,
      temporal_scope: temporalScope,
    });
    const { result } = renderHook(() => useQuantityRuntimeBridge(), {
      wrapper: providerWrapper,
    });

    await expect(
      result.current.fetchLineageBatch(
        legacySelectors(["artifact:canonical-a"]),
        undefined,
        temporalScope,
      ),
    ).rejects.toThrow();
  });

  it("refuses inconsistent batch resolutions and aliases from legacy responses", async () => {
    const { result } = renderHook(() => useQuantityRuntimeBridge(), {
      wrapper: providerWrapper,
    });
    const postSpy = mockRuntimePostSuccess({
      lineages: [{ ...lineage, id: "artifact:canonical-a" }],
      lineage_resolutions: [
        {
          requested_lineage_id: "artifact-alias-a",
          resolved_lineage_id: "artifact:other",
        },
      ],
      meta,
      temporal_scope: temporalScope,
    });
    await expect(
      result.current.fetchLineageBatch(
        legacySelectors(["artifact-alias-a"]),
        undefined,
        temporalScope,
      ),
    ).rejects.toThrow("does not match its returned lineage");

    postSpy.mockResolvedValueOnce({
      data: {
        lineages: [{ ...lineage, id: "artifact:canonical-a" }],
        lineage_resolutions: [
          { requested_lineage_id: "artifact-alias-a", extra: "ignored" },
        ],
        meta,
        temporal_scope: temporalScope,
      },
      error: undefined,
      response: new Response("{}", { status: 200 }),
    } as never);
    await expect(
      result.current.fetchLineageBatch(
        legacySelectors(["artifact-alias-a"]),
        undefined,
        temporalScope,
      ),
    ).rejects.toThrow();

    postSpy.mockResolvedValueOnce({
      data: {
        lineages: [{ ...lineage, id: "artifact:canonical-a" }],
        meta,
        temporal_scope: temporalScope,
      },
      error: undefined,
      response: new Response("{}", { status: 200 }),
    } as never);
    await expect(
      result.current.fetchLineageBatch(
        legacySelectors(["artifact-alias-a"]),
        undefined,
        temporalScope,
      ),
    ).rejects.toThrow("unrequested or unbound item");
  });

  it("posts exact run/profile refs and refuses a same-ID response without the profile declaration", async () => {
    const selectedArtifactRef = {
      artifact_id: `sha256:${"a".repeat(64)}`,
      kind: "core.decision_packet",
      media_type: "application/json",
      manifest_profile_sha256: `sha256:${"b".repeat(64)}`,
    };
    const selector: LineageBatchSelector = {
      lineageId: `artifact:${selectedArtifactRef.artifact_id}`,
      selectedArtifactRef,
      artifactRefProvenance: "reader_materialized",
      sourceRunId: "run-profile-a",
    };
    const selectedGraph = {
      ...lineage,
      id: selector.lineageId,
      selected_artifact_ref: selectedArtifactRef,
      profile_binding_status: "verified",
      artifact_ref_provenance: "reader_materialized",
      source_run_id: "run-profile-a",
      trust_metadata: null,
    };
    const postSpy = mockRuntimePostSuccess({
      lineages: [selectedGraph],
      lineage_resolutions: [
        {
          requested_lineage_id: selector.lineageId,
          resolved_lineage_id: selector.lineageId,
        },
      ],
      meta,
      temporal_scope: temporalScope,
    });
    const { result } = renderHook(() => useQuantityRuntimeBridge(), {
      wrapper: providerWrapper,
    });

    await expect(
      result.current.fetchLineageBatch(
        [selector],
        "run-profile-a",
        temporalScope,
      ),
    ).resolves.toMatchObject({
      lineages: [{ selected_artifact_ref: selectedArtifactRef }],
    });
    expect(postSpy).toHaveBeenCalledWith("/api/v1/lineage/batch", {
      body: {
        lineage_ids: [selector.lineageId],
        selected_artifact_refs: [selectedArtifactRef],
        run_id: "run-profile-a",
      },
      params: { query: temporalScope },
    });

    postSpy.mockResolvedValueOnce({
      data: {
        lineages: [
          {
            ...selectedGraph,
            selected_artifact_ref: null,
            profile_binding_status: "not_established",
            artifact_ref_provenance: null,
          },
        ],
        lineage_resolutions: [
          {
            requested_lineage_id: selector.lineageId,
            resolved_lineage_id: selector.lineageId,
          },
        ],
        meta,
        temporal_scope: temporalScope,
      },
      error: undefined,
      response: new Response("{}", { status: 200 }),
    } as never);
    await expect(
      result.current.fetchLineageBatch(
        [selector],
        "run-profile-a",
        temporalScope,
      ),
    ).rejects.toThrow("unbound item");
  });

  it("routes exports by format and preserves transport failures", async () => {
    const getSpy = mockRuntimeGetSuccess({
      format: "openlineage",
      lineage_id: "lineage-a",
      meta,
      payload: { run: { runId: "lineage-a" } },
      temporal_scope: temporalScope,
    });
    const { result } = renderHook(() => useQuantityRuntimeBridge(), {
      wrapper: providerWrapper,
    });

    await expect(
      result.current.fetchLineageExport(
        "lineage-a",
        "openlineage",
        temporalScope,
      ),
    ).resolves.toMatchObject({ format: "openlineage" });
    expect(getSpy).toHaveBeenCalledWith(
      "/api/v1/lineage/{lineage_id}/export/openlineage",
      expect.any(Object),
    );

    getSpy.mockResolvedValueOnce({
      data: {
        format: "openlineage",
        lineage_id: "lineage-b",
        meta,
        payload: { run: { runId: "lineage-b" } },
        temporal_scope: temporalScope,
      },
      error: undefined,
      response: new Response("{}", { status: 200 }),
    } as never);
    await expect(
      result.current.fetchLineageExport(
        "lineage-a",
        "openlineage",
        temporalScope,
      ),
    ).rejects.toThrow("requested subject and format");

    getSpy.mockResolvedValueOnce({
      data: {
        format: "prov",
        lineage_id: "lineage-a",
        meta,
        payload: { run: { runId: "lineage-a" } },
        temporal_scope: temporalScope,
      },
      error: undefined,
      response: new Response("{}", { status: 200 }),
    } as never);
    await expect(
      result.current.fetchLineageExport(
        "lineage-a",
        "openlineage",
        temporalScope,
      ),
    ).rejects.toThrow("requested subject and format");

    getSpy.mockRestore();
    const failedGet = mockRuntimeGetFailure(503, {
      code: "lineage_unavailable",
      detail: "lineage export offline",
      request_id: "req-export-failure",
      status: 503,
      status_code: 503,
      title: "Lineage unavailable",
      type: "about:blank",
    });
    await expect(
      result.current.fetchLineageExport("lineage-a", "prov", temporalScope),
    ).rejects.toMatchObject({
      code: "lineage_unavailable",
      detail: "lineage export offline",
      name: "RuntimeApiRequestError",
      status: 503,
    });
    expect(failedGet).toHaveBeenCalledWith(
      "/api/v1/lineage/{lineage_id}/export/prov",
      expect.any(Object),
    );
  });

  it("emits quantity trust only for the complete lineage/profile/run/origin/time tuple", () => {
    const { result } = renderHook(() => useQuantityRuntimeBridge(), {
      wrapper: providerWrapper,
    });
    const withoutTrust = quantity();
    const selectedArtifactRef = {
      artifact_id: `sha256:${"a".repeat(64)}`,
      kind: "core.decision_packet",
      media_type: "application/json",
      manifest_profile_sha256: `sha256:${"b".repeat(64)}`,
    };
    const trustMetadata = {
      dispute_status: "none" as const,
      freshness: "current" as const,
      hash: "sha256:lineage-a",
      temporal_scope: temporalScope,
      verification_status: "verified" as const,
      verified_at: "2026-07-19T11:00:00Z",
      verified_by: "runtime-verifier",
      verification_method: "content-hash",
    };
    const sourceLineage = {
      ...withoutTrust.lineage,
      artifact_ref: selectedArtifactRef,
      artifact_ref_provenance: "reader_materialized" as const,
      source_run_id: "run-profile-a",
      hash: "sha256:lineage-a",
      trust_metadata: trustMetadata,
    };
    const embeddedOnly: QuantityValue = {
      ...withoutTrust,
      lineage: sourceLineage,
    };

    expect(
      result.current.renderTrustMetadata?.(embeddedOnly, "expanded"),
    ).toBeNull();

    const withExactBinding: QuantityValue = {
      ...embeddedOnly,
      profile_binding_status: "verified",
      profile_binding_context: {
        status: "verified",
        lineageId: sourceLineage.id,
        selectedArtifactRef,
        sourceRunId: "run-profile-a",
        origin: "reader_materialized",
        temporalScope,
        admissionGeneration: 1,
      },
    };
    const siblingLineageQuantity: QuantityValue = {
      ...withExactBinding,
      lineage: { ...withExactBinding.lineage, id: "artifact:sibling-lineage" },
    };
    expect(
      result.current.renderTrustMetadata?.(siblingLineageQuantity, "expanded"),
    ).toBeNull();

    const otherProfileQuantity: QuantityValue = {
      ...withExactBinding,
      lineage: {
        ...withExactBinding.lineage,
        artifact_ref: {
          ...selectedArtifactRef,
          manifest_profile_sha256: `sha256:${"c".repeat(64)}`,
        },
      },
    };
    const otherRunQuantity: QuantityValue = {
      ...withExactBinding,
      lineage: { ...withExactBinding.lineage, source_run_id: "run-profile-b" },
    };
    const otherOriginQuantity: QuantityValue = {
      ...withExactBinding,
      lineage: {
        ...withExactBinding.lineage,
        artifact_ref_provenance: "run_output_ref",
      },
    };
    const otherTimeQuantity: QuantityValue = {
      ...withExactBinding,
      lineage: {
        ...withExactBinding.lineage,
        trust_metadata: {
          ...trustMetadata,
          temporal_scope: { ...temporalScope, branch: "other-branch" },
        },
      },
    };
    const unestablishedQuantity: QuantityValue = {
      ...withExactBinding,
      profile_binding_status: "not_established",
    };
    for (const changedMember of [
      otherProfileQuantity,
      otherRunQuantity,
      otherOriginQuantity,
      otherTimeQuantity,
      unestablishedQuantity,
    ]) {
      expect(
        result.current.renderTrustMetadata?.(changedMember, "expanded"),
      ).toBeNull();
    }

    const trustNode = result.current.renderTrustMetadata?.(
      withExactBinding,
      "expanded",
    );
    const selector = {
      lineageId: sourceLineage.id,
      selectedArtifactRef,
      artifactRefProvenance: "reader_materialized" as const,
      sourceRunId: "run-profile-a",
    };
    const graph = {
      id: sourceLineage.id,
      status: "verified",
      freshness: "current",
      hash: "sha256:lineage-a",
      selected_artifact_ref: selectedArtifactRef,
      profile_binding_status: "verified",
      artifact_ref_provenance: "reader_materialized",
      source_run_id: "run-profile-a",
      trust_metadata: trustMetadata,
      nodes: [],
      edges: [],
      exports: { openlineage: "/openlineage", prov: "/prov" },
    } as const;
    queryClient.setQueryData(
      profileBindingAdmissionQueryKey(selector, "run-profile-a", temporalScope),
      { generation: 1, outcome: "admitted" },
    );
    queryClient.setQueryData(
      boundLineageQueryKey(selector, "run-profile-a", temporalScope),
      {
        lineage: graph,
        temporal_scope: temporalScope,
        profileBindingGeneration: 1,
      },
    );
    render(trustNode as ReactElement, {
      wrapper: providerWrapper,
    });

    expect(screen.getByText("runtime-verifier")).toBeInTheDocument();
  });
});

function legacySelectors(ids: readonly string[]): LineageBatchSelector[] {
  return ids.map((lineageId) => ({
    lineageId,
    selectedArtifactRef: null,
    artifactRefProvenance: null,
    sourceRunId: null,
  }));
}

function providerWrapper({ children }: PropsWithChildren) {
  return (
    <QueryClientProvider client={queryClient}>
      <LocaleProvider>
        <TemporalCursorProvider>
          <TrustViewProvider>
            <QuantityRuntimeProvider>{children}</QuantityRuntimeProvider>
          </TrustViewProvider>
        </TemporalCursorProvider>
      </LocaleProvider>
    </QueryClientProvider>
  );
}

function quantity(): QuantityValue {
  return {
    lineage,
    metric_id: "metric-a",
    point: 42,
    quantity_class: "decision",
    time: temporalScope,
    unit: { code: "count", system: "unit" },
  };
}
