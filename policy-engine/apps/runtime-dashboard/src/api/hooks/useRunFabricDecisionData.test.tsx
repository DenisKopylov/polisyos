import { renderHook, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { queryKeys } from "@/api/queryKeys";
import { ProvenancePopover } from "@/shared/ui/quantity/ProvenancePopover";
import { boundLineageQueryKey } from "@/shared/ui/quantity/useLineageBatch";
import type {
  LineageBatchSelector,
  LineageGraphView,
  SelectedArtifactRef,
  TemporalRef,
} from "@/shared/ui/quantity/quantity.types";
import { createQueryHookWrapper } from "@/test/queryHook";
import { renderWithProviders } from "@/test/render";
import {
  mockRuntimeGetSuccess,
  mockRuntimePostSuccess,
} from "@/test/runtimeApi";

import {
  runFabricDecisionDataQueryOptions,
  useRunFabricDecisionData,
} from "./useRunFabricDecisionData";

const runId = "R_core_api_001";
const artifactId =
  "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const selectedArtifactRef: SelectedArtifactRef = {
  artifact_id: artifactId,
  kind: "core.decision_packet",
  media_type: "application/json",
  manifest_profile_sha256:
    "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
};
const siblingArtifactRef: SelectedArtifactRef = {
  ...selectedArtifactRef,
  manifest_profile_sha256:
    "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
};
const selector: LineageBatchSelector = {
  lineageId: `artifact:${artifactId}`,
  selectedArtifactRef,
  artifactRefProvenance: "reader_materialized",
  sourceRunId: runId,
};
const meta = {
  generated_at: "2026-02-11T12:05:00.000Z",
  request_id: "req_fixture",
  source_kinds: ["core_run"],
};
const temporalScope: TemporalRef = {
  valid_at: "2026-02-11T12:00:00.000Z",
  tx_at: "2026-02-11T12:01:00.000Z",
  branch: "main",
  snapshot_id: "snapshot-a",
  scenario_id: "scenario-a",
};
const payload = {
  meta,
  run_id: runId,
  source_kind: "core_run",
  temporal_scope: temporalScope,
  decision_data: [
    {
      id: "fabric_decision_data:policy_cost",
      kind: "quantity",
      value: {
        label: "Policy cost",
        metric_id: "policy_cost",
        point: 100,
        unit: { code: "[USD]", display: "USD", system: "ucum" },
      },
      source_contract: { id: "worldbank.wdi.generic", version: "1.1.0" },
      quality: { status: "passed", score: 1 },
      lineage: {
        id: selector.lineageId,
        status: "verified",
        hash: "sha256:abc",
        artifact_ref: selectedArtifactRef,
        artifact_ref_provenance: "reader_materialized",
        source_run_id: runId,
      },
      access: {
        classification: "public",
        pii_tier: "none",
        redaction: "none",
        tenant_scope: "shared_public",
      },
      time: temporalScope,
      replay: {
        status: "replayable",
        manifest_ref: `cas://${artifactId}`,
      },
      gaps: [],
      metadata: { quantity_class: "decision" },
    },
  ],
};

const requestUrl =
  "/runs/R_core_api_001?trust=expanded&valid_at=2026-02-11T12%3A00%3A00.000Z&tx_at=2026-02-11T12%3A01%3A00.000Z&branch=main&snapshot_id=snapshot-a&scenario_id=scenario-a";

afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/");
});

describe("useRunFabricDecisionData", () => {
  it("loads profile-bearing Fabric envelopes without minting trust authority", async () => {
    const getSpy = mockRuntimeGetSuccess(payload);
    const { result } = renderHook(() => useRunFabricDecisionData(runId), {
      wrapper: createQueryHookWrapper(),
    });

    await waitFor(() => {
      if (result.current.error) {
        throw result.current.error;
      }
      expect(result.current.isSuccess).toBe(true);
    });

    expect(result.current.data?.decision_data).toHaveLength(1);
    expect(result.current.data?.quantities[0]?.metric_id).toBe("policy_cost");
    expect(result.current.data?.quantities[0]?.lineage.status).toBe("verified");
    expect(result.current.data?.quantities[0]?.lineage.artifact_ref).toEqual(
      selectedArtifactRef,
    );
    expect(
      result.current.data?.quantities[0]?.lineage.artifact_ref_provenance,
    ).toBe("reader_materialized");
    expect(result.current.data?.quantities[0]?.lineage.source_run_id).toBe(
      runId,
    );
    expect(
      result.current.data?.quantities[0]?.lineage.trust_metadata,
    ).toBeUndefined();
    expect(getSpy).toHaveBeenCalledWith(
      "/api/v1/runs/{run_id}/fabric-decision-data",
      {
        params: {
          path: { run_id: runId },
          query: {},
        },
      },
    );
  });

  it("rejects a malformed present profile as a visible primary-envelope error", async () => {
    const row = payload.decision_data[0];
    const malformedPayload = {
      ...payload,
      decision_data: [
        {
          ...row,
          lineage: {
            ...row.lineage,
            artifact_ref: {
              ...selectedArtifactRef,
              manifest_profile_sha256: "malformed-profile",
            },
          },
        },
      ],
    };
    mockRuntimeGetSuccess(malformedPayload);
    const { result } = renderHook(() => useRunFabricDecisionData(runId), {
      wrapper: createQueryHookWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.data).toBeUndefined();
    expect(result.current.error).toBeInstanceOf(Error);
  });

  it("joins displayed Fabric quantity to its exact run/profile/time batch graph", async () => {
    window.history.replaceState(null, "", requestUrl);
    const getSpy = mockRuntimeGetSuccess(payload);
    const postSpy = mockRuntimePostSuccess(batchPayload(profileGraph()));

    const { queryClient } = renderWithProviders(
      <FabricDecisionQuantityPopover runId={runId} />,
    );

    expect(
      await screen.findByTestId("trust-verification-status"),
    ).toHaveTextContent("verified");
    expect(getSpy).toHaveBeenCalledTimes(1);
    expect(getSpy).toHaveBeenCalledWith(
      "/api/v1/runs/{run_id}/fabric-decision-data",
      expect.any(Object),
    );
    expect(postSpy).toHaveBeenCalledWith("/api/v1/lineage/batch", {
      body: {
        lineage_ids: [selector.lineageId],
        selected_artifact_refs: [selectedArtifactRef],
        run_id: runId,
      },
      params: { query: temporalScope },
    });
    expect(
      queryClient.getQueryData(
        boundLineageQueryKey(selector, runId, temporalScope),
      ),
    ).toMatchObject({
      lineage: {
        id: selector.lineageId,
        selected_artifact_ref: selectedArtifactRef,
        source_run_id: runId,
      },
      temporal_scope: temporalScope,
    });
  });

  it("does not cache a batch graph for a different lineage ID", async () => {
    window.history.replaceState(null, "", requestUrl);
    const getSpy = mockRuntimeGetSuccess(payload);
    const postSpy = mockRuntimePostSuccess(
      batchPayload(profileGraph({ id: "lin_foreign" }), "lin_foreign"),
    );

    const { queryClient } = renderWithProviders(
      <FabricDecisionQuantityPopover runId={runId} />,
    );

    await waitFor(() => {
      expect(
        queryClient.getQueryState(
          boundLineageQueryKey(selector, runId, temporalScope),
        )?.status,
      ).toBe("error");
    });
    expect(
      screen.queryByTestId("trust-verification-status"),
    ).not.toBeInTheDocument();
    expect(getSpy).toHaveBeenCalledTimes(1);
    expect(getSpy).toHaveBeenCalledWith(
      "/api/v1/runs/{run_id}/fabric-decision-data",
      expect.any(Object),
    );
    expect(postSpy).toHaveBeenCalledWith("/api/v1/lineage/batch", {
      body: {
        lineage_ids: [selector.lineageId],
        selected_artifact_refs: [selectedArtifactRef],
        run_id: runId,
      },
      params: { query: temporalScope },
    });
  });

  it("does not cache trust for a same-ID graph carrying a sibling profile", async () => {
    window.history.replaceState(null, "", requestUrl);
    const getSpy = mockRuntimeGetSuccess(payload);
    const siblingGraph = profileGraph({
      selectedArtifactRef: siblingArtifactRef,
    });
    mockRuntimePostSuccess(batchPayload(siblingGraph));

    const { queryClient } = renderWithProviders(
      <FabricDecisionQuantityPopover runId={runId} />,
    );

    await waitFor(() => {
      expect(
        queryClient.getQueryState(
          boundLineageQueryKey(selector, runId, temporalScope),
        )?.status,
      ).toBe("error");
    });
    expect(
      screen.queryByTestId("trust-verification-status"),
    ).not.toBeInTheDocument();
    expect(
      queryClient.getQueryData(
        boundLineageQueryKey(selector, runId, temporalScope),
      ),
    ).toBeUndefined();
    expect(getSpy).toHaveBeenCalledTimes(1);
    expect(getSpy).toHaveBeenCalledWith(
      "/api/v1/runs/{run_id}/fabric-decision-data",
      expect.any(Object),
    );
  });

  it("does not cache a profile-bound trust grade when the response omits its declaration", async () => {
    window.history.replaceState(null, "", requestUrl);
    const getSpy = mockRuntimeGetSuccess(payload);
    const undeclaredGraph = {
      ...profileGraph(),
      selected_artifact_ref: null,
      profile_binding_status: "not_established",
      artifact_ref_provenance: null,
      trust_metadata: null,
    } as unknown as LineageGraphView;
    mockRuntimePostSuccess(batchPayload(undeclaredGraph));

    const { queryClient } = renderWithProviders(
      <FabricDecisionQuantityPopover runId={runId} />,
    );

    await waitFor(() => {
      expect(
        queryClient.getQueryState(
          boundLineageQueryKey(selector, runId, temporalScope),
        )?.status,
      ).toBe("error");
    });
    expect(
      screen.queryByTestId("trust-verification-status"),
    ).not.toBeInTheDocument();
    expect(
      queryClient.getQueryData(
        boundLineageQueryKey(selector, runId, temporalScope),
      ),
    ).toBeUndefined();
    expect(getSpy).toHaveBeenCalledTimes(1);
    expect(getSpy).toHaveBeenCalledWith(
      "/api/v1/runs/{run_id}/fabric-decision-data",
      expect.any(Object),
    );
  });

  it("keeps trust absent when the exact profile response has no verification metadata", async () => {
    window.history.replaceState(null, "", requestUrl);
    const getSpy = mockRuntimeGetSuccess(payload);
    mockRuntimePostSuccess(
      batchPayload(profileGraph({ includeTrustMetadata: false })),
    );

    renderWithProviders(<FabricDecisionQuantityPopover runId={runId} />);

    expect(
      await screen.findByTestId("lineage-verification-status"),
    ).toHaveTextContent("verified");
    expect(
      screen.queryByTestId("trust-verification-status"),
    ).not.toBeInTheDocument();
    expect(getSpy).toHaveBeenCalledTimes(1);
    expect(getSpy).toHaveBeenCalledWith(
      "/api/v1/runs/{run_id}/fabric-decision-data",
      expect.any(Object),
    );
  });

  it("uses all temporal dimensions in the Fabric decision data cache key", () => {
    const temporal = {
      validAt: temporalScope.valid_at,
      txAt: temporalScope.tx_at,
      branch: temporalScope.branch,
      snapshotId: temporalScope.snapshot_id,
      scenarioId: temporalScope.scenario_id,
    };
    const siblingTemporal = { ...temporal, branch: "other-branch" };

    expect(runFabricDecisionDataQueryOptions(runId, temporal).queryKey).toEqual(
      queryKeys.runFabricDecisionData(runId, temporal),
    );
    expect(
      runFabricDecisionDataQueryOptions(runId, temporal).queryKey,
    ).not.toEqual(
      runFabricDecisionDataQueryOptions(runId, siblingTemporal).queryKey,
    );
  });
});

function FabricDecisionQuantityPopover({ runId }: { runId: string }) {
  const result = useRunFabricDecisionData(runId);
  const quantity = result.data?.quantities[0];
  if (!quantity) {
    return null;
  }
  return (
    <ProvenancePopover
      quantity={quantity}
      open
      onOpenChange={() => undefined}
      temporalScope={temporalScope}
    >
      <button type="button">Open quantity provenance</button>
    </ProvenancePopover>
  );
}

function profileGraph(
  options: {
    id?: string;
    selectedArtifactRef?: SelectedArtifactRef;
    includeTrustMetadata?: boolean;
  } = {},
): LineageGraphView {
  const selectedRef = options.selectedArtifactRef ?? selectedArtifactRef;
  const id = options.id ?? selector.lineageId;
  return {
    id,
    status: "verified",
    freshness: "current",
    selected_artifact_ref: selectedRef,
    profile_binding_status: "verified",
    artifact_ref_provenance: "reader_materialized",
    source_run_id: runId,
    exports: {
      openlineage: `/api/v1/lineage/${id}/export/openlineage`,
      prov: `/api/v1/lineage/${id}/export/prov`,
    },
    ...(options.includeTrustMetadata === false
      ? {}
      : {
          trust_metadata: {
            hash: "sha256:lineage-proof",
            verification_status: "verified",
            verified_by: "runtime-verifier",
            verified_at: "2026-02-11T11:59:00.000Z",
            verification_method: "selected-profile-reader",
            freshness: "current",
            dispute_status: "none",
            temporal_scope: temporalScope,
          },
        }),
    compact_summary: [],
    nodes: [],
    edges: [],
  } as unknown as LineageGraphView;
}

function batchPayload(
  graph: LineageGraphView,
  requestedLineageId = selector.lineageId,
) {
  return {
    meta,
    temporal_scope: temporalScope,
    lineages: [graph],
    lineage_resolutions: [
      {
        requested_lineage_id: requestedLineageId,
        resolved_lineage_id: graph.id,
      },
    ],
  };
}
