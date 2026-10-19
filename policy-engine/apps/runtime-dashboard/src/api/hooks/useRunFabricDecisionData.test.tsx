import { renderHook, screen, waitFor, within } from "@testing-library/react";
import type { QueryClient } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { queryKeys } from "@/api/queryKeys";
import { RunOverviewProfileLineage } from "@/features/runs/routes/tabs/RunOverviewProfileLineage";
import {
  boundLineageQueryKey,
  profileBindingAdmissionQueryKey,
  profileBindingIdentityKey,
} from "@/shared/ui/quantity/useLineageBatch";
import type {
  LineageBatchSelector,
  LineageGraphView,
  SelectedArtifactRef,
  TemporalRef,
} from "@/shared/ui/quantity/quantity.types";
import { createQueryHookWrapper } from "@/test/queryHook";
import { renderWithProviders } from "@/test/render";
import {
  lineageBatchFixture,
  lineageGraphFixture,
  profileBoundLineageGraphFixture,
  profileTrustMetadataFixture,
  type LineageBatchMetaFixture,
  type LineageTrustMetadataFixture,
} from "@/test/fixtures/profileLineageBatch";
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
const meta: LineageBatchMetaFixture = {
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
const declaredTrustMetadata: LineageTrustMetadataFixture =
  profileTrustMetadataFixture({
    temporalScope,
    hash: "sha256:abc",
    verifiedBy: "selected-profile-reader-fixture",
    verifiedAt: "2026-02-11T12:02:00.000Z",
  });
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
    const user = userEvent.setup();
    window.history.replaceState(null, "", requestUrl);
    const getSpy = mockRuntimeGetSuccess(payload);
    const postSpy = mockRuntimePostSuccess(
      batchPayload(
        profileGraph({
          status: "verified",
          trustMetadata: declaredTrustMetadata,
        }),
        selector.lineageId,
      ),
    );

    const { queryClient } = renderWithProviders(
      <RunOverviewProfileLineage runId={runId} />,
    );
    const row = await screen.findByTestId("overview-decision-quantity");
    await waitFor(() =>
      expect(row).toHaveAttribute("data-profile-binding-status", "verified"),
    );
    expect(row).toHaveAttribute(
      "data-selected-artifact-profile",
      selectedArtifactRef.manifest_profile_sha256,
    );
    expect(row).toHaveAttribute("data-source-run-id", runId);
    expect(row).toHaveAttribute("data-profile-origin", "reader_materialized");
    expect(row).toHaveAttribute(
      "data-profile-temporal-scope",
      JSON.stringify(temporalScope),
    );
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
    expect(postSpy).toHaveBeenCalledTimes(1);
    expect(
      queryClient.getQueryData(
        boundLineageQueryKey(selector, runId, temporalScope),
      ),
    ).toMatchObject({
      lineage: {
        id: selector.lineageId,
        selected_artifact_ref: selectedArtifactRef,
        artifact_ref_provenance: "reader_materialized",
        source_run_id: runId,
      },
      temporal_scope: temporalScope,
    });

    const quantity = within(row).getByTestId("quantity");
    expect(quantity).toHaveAttribute("data-lineage-status", "verified");
    expect(quantity).toHaveAttribute("data-profile-binding-status", "verified");
    await user.click(quantity);
    expect(
      await screen.findByTestId("popover-profile-binding-status"),
    ).toHaveTextContent("verified");
    expect(
      await screen.findByTestId("trust-verification-status"),
    ).toHaveTextContent("verified");
  });

  it("does not cache a batch graph for a different lineage ID", async () => {
    window.history.replaceState(null, "", requestUrl);
    const getSpy = mockRuntimeGetSuccess(payload);
    const postSpy = mockRuntimePostSuccess(
      batchPayload(
        profileGraph({ status: "verified", id: "lin_foreign" }),
        selector.lineageId,
      ),
    );

    const { queryClient } = renderWithProviders(
      <RunOverviewProfileLineage runId={runId} />,
    );

    await expectSelectedProfileRefusal(queryClient);
    expect(postSpy).toHaveBeenCalledWith("/api/v1/lineage/batch", {
      body: {
        lineage_ids: [selector.lineageId],
        selected_artifact_refs: [selectedArtifactRef],
        run_id: runId,
      },
      params: { query: temporalScope },
    });
    expect(postSpy).toHaveBeenCalledTimes(1);
    expect(getSpy).toHaveBeenCalledTimes(1);
    expect(getSpy).toHaveBeenCalledWith(
      "/api/v1/runs/{run_id}/fabric-decision-data",
      expect.any(Object),
    );
  });

  it("does not cache trust for a same-ID graph carrying a sibling profile", async () => {
    window.history.replaceState(null, "", requestUrl);
    const getSpy = mockRuntimeGetSuccess(payload);
    const siblingGraph = profileGraph({
      status: "verified",
      selectedArtifactRef: siblingArtifactRef,
    });
    const postSpy = mockRuntimePostSuccess(
      batchPayload(siblingGraph, selector.lineageId),
    );

    const { queryClient } = renderWithProviders(
      <RunOverviewProfileLineage runId={runId} />,
    );

    await expectSelectedProfileRefusal(queryClient);
    expect(postSpy).toHaveBeenCalledWith("/api/v1/lineage/batch", {
      body: {
        lineage_ids: [selector.lineageId],
        selected_artifact_refs: [selectedArtifactRef],
        run_id: runId,
      },
      params: { query: temporalScope },
    });
    expect(postSpy).toHaveBeenCalledTimes(1);
    expect(getSpy).toHaveBeenCalledTimes(1);
    expect(getSpy).toHaveBeenCalledWith(
      "/api/v1/runs/{run_id}/fabric-decision-data",
      expect.any(Object),
    );
  });

  it("does not cache a profile-bound trust grade when the response omits its declaration", async () => {
    window.history.replaceState(null, "", requestUrl);
    const getSpy = mockRuntimeGetSuccess(payload);
    const undeclaredGraph = lineageGraphFixture({
      lineageId: selector.lineageId,
      status: "verified",
      freshness: "current",
      selectedArtifactRef: null,
      profileBindingStatus: "not_established",
      artifactRefProvenance: null,
      sourceRunId: null,
      trustMetadata: null,
    });
    const postSpy = mockRuntimePostSuccess(
      batchPayload(undeclaredGraph, selector.lineageId),
    );

    const { queryClient } = renderWithProviders(
      <RunOverviewProfileLineage runId={runId} />,
    );

    await expectSelectedProfileRefusal(queryClient);
    expect(postSpy).toHaveBeenCalledWith("/api/v1/lineage/batch", {
      body: {
        lineage_ids: [selector.lineageId],
        selected_artifact_refs: [selectedArtifactRef],
        run_id: runId,
      },
      params: { query: temporalScope },
    });
    expect(postSpy).toHaveBeenCalledTimes(1);
    expect(getSpy).toHaveBeenCalledTimes(1);
    expect(getSpy).toHaveBeenCalledWith(
      "/api/v1/runs/{run_id}/fabric-decision-data",
      expect.any(Object),
    );
  });

  it("keeps trust absent when the exact profile response has no verification metadata", async () => {
    const user = userEvent.setup();
    window.history.replaceState(null, "", requestUrl);
    const getSpy = mockRuntimeGetSuccess(payload);
    const postSpy = mockRuntimePostSuccess(
      batchPayload(profileGraph({ status: "verified" }), selector.lineageId),
    );

    renderWithProviders(<RunOverviewProfileLineage runId={runId} />);
    const row = await screen.findByTestId("overview-decision-quantity");
    await waitFor(() =>
      expect(row).toHaveAttribute("data-profile-binding-status", "verified"),
    );
    const quantity = within(row).getByTestId("quantity");
    expect(quantity).toHaveAttribute("data-lineage-status", "verified");
    expect(quantity).toHaveAttribute("data-profile-binding-status", "verified");
    await user.click(quantity);

    expect(
      await screen.findByTestId("popover-profile-binding-status"),
    ).toHaveTextContent("verified");
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
    expect(postSpy).toHaveBeenCalledTimes(1);
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

async function expectSelectedProfileRefusal(queryClient: QueryClient) {
  const batchQueryKey = [
    "quantity-lineage-batch",
    [profileBindingIdentityKey(selector, runId, temporalScope)],
  ] as const;
  await waitFor(() => {
    expect(queryClient.getQueryState(batchQueryKey)?.status).toBe("error");
  });
  expect(queryClient.getQueryState(batchQueryKey)?.error).toMatchObject({
    message: "Lineage batch response contains an unrequested or unbound item",
  });
  expect(
    queryClient.getQueryData(
      profileBindingAdmissionQueryKey(selector, runId, temporalScope),
    ),
  ).toMatchObject({ outcome: "rejected" });
  expect(
    queryClient.getQueryData(
      boundLineageQueryKey(selector, runId, temporalScope),
    ),
  ).toBeUndefined();

  const row = screen.getByTestId("overview-decision-quantity");
  await waitFor(() =>
    expect(row).toHaveAttribute(
      "data-profile-binding-status",
      "not_established",
    ),
  );
  const quantity = within(row).getByTestId("quantity");
  expect(quantity).toHaveAttribute("data-lineage-status", "verified");
  expect(quantity).toHaveAttribute(
    "data-profile-binding-status",
    "not_established",
  );
  const user = userEvent.setup();
  await user.click(quantity);
  expect(
    await screen.findByTestId("popover-profile-binding-status"),
  ).toHaveTextContent("Profile binding not established");
  expect(
    screen.queryByTestId("trust-verification-status"),
  ).not.toBeInTheDocument();
}

function profileGraph(options: {
  status: LineageGraphView["status"];
  id?: string;
  selectedArtifactRef?: SelectedArtifactRef;
  trustMetadata?: LineageGraphView["trust_metadata"];
}): LineageGraphView {
  return profileBoundLineageGraphFixture({
    lineageId: options.id ?? selector.lineageId,
    status: options.status,
    freshness: "current",
    selectedArtifactRef: options.selectedArtifactRef ?? selectedArtifactRef,
    artifactRefProvenance: "reader_materialized",
    sourceRunId: runId,
    ...(options.trustMetadata === undefined
      ? {}
      : { trustMetadata: options.trustMetadata }),
  });
}

function batchPayload(graph: LineageGraphView, requestedLineageId: string) {
  return lineageBatchFixture({
    meta,
    responseTemporalScope: temporalScope,
    lineages: [graph],
    requestedLineageIds: [requestedLineageId],
  });
}
