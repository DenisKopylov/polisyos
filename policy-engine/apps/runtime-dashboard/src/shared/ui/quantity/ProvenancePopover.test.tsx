import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  mockRuntimeGetSuccess,
  mockRuntimePostSuccess,
} from "@/test/runtimeApi";
import { renderWithProviders } from "@/test/render";
import {
  lineageBatchFixture,
  lineageGraphFixture,
} from "@/test/fixtures/profileLineageBatch";

import { ProvenancePopover } from "./ProvenancePopover";
import { boundLineageQueryKey } from "./useLineageBatch";
import type {
  LineageBatchResponsePayload,
  LineageGraphView,
  QuantityValue,
  SelectedArtifactRef,
  TemporalRef,
} from "./quantity.types";

const meta: LineageBatchResponsePayload["meta"] & {
  source_kinds: "core_run"[];
} = {
  generated_at: "2026-04-24T12:00:00Z",
  request_id: "req-popover",
  source_kinds: ["core_run"],
};

const quantity: QuantityValue = {
  point: 0.23,
  unit: { code: "1", system: "ucum", display: "ratio" },
  metric_id: "effect_size",
  lineage: {
    id: "artifact:sha256:fixture",
    status: "verified",
    freshness: "current",
    compact_summary: [
      { kind: "source", label: "QES 2024 Q3" },
      { kind: "result", label: "effect_size" },
    ],
  },
  uncertainty: {
    ci_95: [0.15, 0.31],
    disputed: false,
    identifiability: "estimated",
  },
  time: {
    valid_at: "2026-04-15T12:00:00Z",
    tx_at: "2026-04-16T09:20:00Z",
  },
  quantity_class: "decision",
  label: "Effect size",
};

const lineage: LineageGraphView = lineageGraphFixture({
  lineageId: "artifact:sha256:fixture",
  status: "verified",
  freshness: "current",
  compactSummary: [
    { kind: "source", label: "QES 2024 Q3", id: "n1" },
    { kind: "transform", label: "Winsorize", id: "n2" },
    { kind: "model", label: "DoubleML", id: "n3" },
    { kind: "result", label: "effect_size", id: "n4" },
  ],
  nodes: [
    {
      id: "artifact:sha256:source",
      kind: "dataset",
      label: "QES 2024 Q3",
      timestamp: "2026-04-15T12:00:00Z",
    },
  ],
  edges: [],
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ProvenancePopover", () => {
  it("renders generated lineage and verification metadata without a local trust status", async () => {
    renderWithProviders(
      <ProvenancePopover
        quantity={{
          ...quantity,
          lineage: {
            ...quantity.lineage,
            id: "untraced",
            status: "verified",
            freshness: "stale",
            trust_metadata: {
              verification_status: "pending",
              freshness: "current",
              dispute_status: "under_review",
            },
          },
        }}
        open
        onOpenChange={() => undefined}
      >
        <button type="button">Open generated metadata</button>
      </ProvenancePopover>,
    );

    expect(
      await screen.findByTestId("lineage-verification-status"),
    ).toHaveTextContent("verified");
    expect(screen.getByTestId("lineage-freshness")).toHaveTextContent("stale");
    expect(
      screen.queryByTestId("trust-verification-status"),
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId("trust-freshness")).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("trust-dispute-status"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("local-provenance-status"),
    ).not.toBeInTheDocument();
  });

  it("uses explicit null time and shows trust only for an exact profile/run/origin tuple", async () => {
    const user = userEvent.setup();
    const profileQuantity = profileBoundQuantity({ temporalScope: null });
    const postSpy = mockRuntimePostSuccess(
      profileBatch(profileQuantity, {
        status: "verified",
        temporal_scope: null,
        trustMetadata: declaredTrustMetadata(null),
      }),
    );
    window.history.replaceState(
      null,
      "",
      "/runs/run-popover?valid_at=2026-05-01T12%3A00%3A00Z&branch=cursor-branch",
    );

    const { queryClient } = renderWithProviders(
      <ProvenancePopover
        quantity={profileQuantity}
        open
        onOpenChange={() => undefined}
        temporalScope={null}
      >
        <button type="button">Open bound profile</button>
      </ProvenancePopover>,
    );

    expect(
      await screen.findByTestId("trust-verification-status"),
    ).toHaveTextContent("verified");
    expect(screen.getByTestId("popover-profile-lineage")).toHaveTextContent(
      profileQuantity.lineage.id,
    );
    expect(
      screen.getByTestId("popover-selected-artifact-ref"),
    ).toHaveTextContent(
      profileQuantity.lineage.artifact_ref!.manifest_profile_sha256,
    );
    expect(screen.getByTestId("popover-profile-origin")).toHaveTextContent(
      "reader_materialized",
    );
    expect(screen.getByTestId("popover-source-run")).toHaveTextContent(
      "run-popover",
    );
    expect(postSpy).toHaveBeenCalledWith("/api/v1/lineage/batch", {
      body: {
        lineage_ids: [profileQuantity.lineage.id],
        selected_artifact_refs: [profileQuantity.lineage.artifact_ref],
        run_id: "run-popover",
      },
      params: {
        query: {
          branch: undefined,
          scenario_id: undefined,
          snapshot_id: undefined,
          tx_at: undefined,
          valid_at: undefined,
        },
      },
    });
    expect(postSpy).toHaveBeenCalledTimes(1);

    await user.click(screen.getByRole("button", { name: /deep dive/i }));
    await screen.findByTestId("provenance-profile-context");
    expect(
      screen.getByTestId("provenance-profile-binding-status"),
    ).toHaveTextContent("verified");
    expect(screen.getByTestId("provenance-profile-lineage")).toHaveTextContent(
      profileQuantity.lineage.id,
    );
    expect(
      screen.getByTestId("provenance-profile-selected-artifact-ref"),
    ).toHaveTextContent(
      profileQuantity.lineage.artifact_ref!.manifest_profile_sha256,
    );
    expect(screen.getByTestId("provenance-profile-origin")).toHaveTextContent(
      "reader_materialized",
    );
    expect(
      screen.getByTestId("provenance-profile-source-run"),
    ).toHaveTextContent("run-popover");
    expect(screen.getByTestId("provenance-profile-time")).toHaveTextContent(
      "null",
    );
    expect(
      screen.getByTestId("provenance-profile-export-generic"),
    ).toBeVisible();

    postSpy.mockResolvedValueOnce({
      data: undefined,
      error: { code: "profile_refused", detail: "profile changed" },
      response: new Response("{}", { status: 409 }),
    } as never);
    const selector = {
      lineageId: profileQuantity.lineage.id,
      selectedArtifactRef: profileQuantity.lineage
        .artifact_ref as SelectedArtifactRef,
      artifactRefProvenance: profileQuantity.lineage.artifact_ref_provenance,
      sourceRunId: profileQuantity.lineage.source_run_id,
    };
    const queryKey = boundLineageQueryKey(selector, "run-popover", null);
    await queryClient.invalidateQueries({ queryKey, exact: true });
    await waitFor(() => {
      expect(queryClient.getQueryState(queryKey)?.status).toBe("error");
    });
    expect(
      screen.queryByTestId("trust-verification-status"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("provenance-profile-context"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("provenance-profile-export-generic"),
    ).not.toBeInTheDocument();
  });

  it("suppresses embedded trust after a profile-bound response fails origin admission", async () => {
    const profileQuantity = profileBoundQuantity({
      embeddedTrust: true,
      temporalScope,
    });
    const response = profileBatch(profileQuantity, {
      status: "verified",
      temporal_scope: temporalScope,
      trustMetadata: declaredTrustMetadata(temporalScope),
      response_origin: "run_output_ref",
    });
    const postSpy = mockRuntimePostSuccess(response);
    window.history.replaceState(null, "", "/runs/run-popover?trust=expanded");

    const selector = {
      lineageId: profileQuantity.lineage.id,
      selectedArtifactRef: profileQuantity.lineage
        .artifact_ref as SelectedArtifactRef,
      artifactRefProvenance: profileQuantity.lineage.artifact_ref_provenance,
      sourceRunId: profileQuantity.lineage.source_run_id,
    };
    const { queryClient } = renderWithProviders(
      <ProvenancePopover
        quantity={profileQuantity}
        open
        onOpenChange={() => undefined}
        temporalScope={temporalScope}
      >
        <button type="button">Open mismatched profile</button>
      </ProvenancePopover>,
    );

    expect(
      await screen.findByText(/Unable to load full lineage/i),
    ).toBeVisible();
    expect(postSpy).toHaveBeenCalledWith("/api/v1/lineage/batch", {
      body: {
        lineage_ids: [profileQuantity.lineage.id],
        selected_artifact_refs: [profileQuantity.lineage.artifact_ref],
        run_id: "run-popover",
      },
      params: {
        query: {
          branch: temporalScope.branch,
          scenario_id: temporalScope.scenario_id,
          snapshot_id: temporalScope.snapshot_id,
          tx_at: temporalScope.tx_at,
          valid_at: temporalScope.valid_at,
        },
      },
    });
    const rejectedQueryKey = boundLineageQueryKey(
      selector,
      "run-popover",
      temporalScope,
    );
    await waitFor(() =>
      expect(queryClient.getQueryState(rejectedQueryKey)?.status).toBe("error"),
    );
    expect(queryClient.getQueryState(rejectedQueryKey)?.error).toMatchObject({
      message: "Lineage batch response contains an unrequested or unbound item",
    });
    expect(queryClient.getQueryData(rejectedQueryKey)).toBeUndefined();
    expect(
      screen.queryByTestId("trust-verification-status"),
    ).not.toBeInTheDocument();
  });

  it("shows compact provenance and opens deep dive", async () => {
    const user = userEvent.setup();
    mockRuntimeGetSuccess({ meta, temporal_scope: null, lineage });
    renderWithProviders(
      <ProvenancePopover
        quantity={quantity}
        open
        onOpenChange={() => undefined}
      >
        <button type="button">Open</button>
      </ProvenancePopover>,
    );

    expect(await screen.findByText("Provenance")).toBeInTheDocument();
    expect(screen.getByText("QES 2024 Q3")).toBeInTheDocument();
    expect(screen.getByText("95% CI 0.15 to 0.31")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /deep dive/i }));
    expect(await screen.findByText("Provenance deep dive")).toBeInTheDocument();
    expect(screen.getByText("Raw sources")).toBeInTheDocument();
  });

  it("keeps a profileless quantity with unestablished binding informational", async () => {
    const profilelessQuantity: QuantityValue = {
      ...quantity,
      profile_binding_status: "not_established",
      profile_binding_temporal_scope: temporalScope,
    };
    const getSpy = mockRuntimeGetSuccess({
      meta,
      temporal_scope: null,
      lineage,
    });

    renderWithProviders(
      <ProvenancePopover
        quantity={profilelessQuantity}
        open
        onOpenChange={() => undefined}
      >
        <button type="button">Open profileless quantity</button>
      </ProvenancePopover>,
    );

    expect(
      await screen.findByTestId("popover-profile-binding-status"),
    ).toHaveTextContent("Profile binding not established");
    expect(screen.getByText("0.23 ratio")).toBeVisible();
    expect(getSpy).not.toHaveBeenCalled();
  });

  it("keeps a source-run candidate informational without an admitted overview context", async () => {
    const profileQuantity = profileBoundQuantity({
      embeddedTrust: true,
      temporalScope: null,
      includeBindingContext: false,
    });
    const postSpy = mockRuntimePostSuccess(
      profileBatch(profileQuantity, {
        status: "verified",
        temporal_scope: null,
      }),
    );
    window.history.replaceState(null, "", "/runs/run-popover?trust=expanded");

    renderWithProviders(
      <ProvenancePopover
        quantity={profileQuantity}
        open
        onOpenChange={() => undefined}
        temporalScope={null}
      >
        <button type="button">Open unbound candidate</button>
      </ProvenancePopover>,
    );

    expect(
      await screen.findByTestId("popover-profile-binding-status"),
    ).toHaveTextContent("Profile binding not established");
    expect(screen.queryByTestId("trust-verification-status")).toBeNull();
    expect(postSpy).not.toHaveBeenCalled();
  });
});

function profileBoundQuantity(
  options: {
    embeddedTrust?: boolean;
    temporalScope?: TemporalRef | null;
    includeBindingContext?: boolean;
  } = {},
): QuantityValue {
  const artifactId = `sha256:${"a".repeat(64)}`;
  const selectedArtifactRef: SelectedArtifactRef = {
    artifact_id: artifactId,
    kind: "core.decision_packet",
    media_type: "application/json",
    manifest_profile_sha256: `sha256:${"b".repeat(64)}`,
  };
  const value = {
    ...quantity,
    lineage: {
      ...quantity.lineage,
      id: `artifact:${artifactId}`,
      artifact_ref: selectedArtifactRef,
      artifact_ref_provenance: "reader_materialized",
      source_run_id: "run-popover",
      trust_metadata: options.embeddedTrust
        ? {
            verification_status: "verified",
            freshness: "current",
            dispute_status: "none",
            verified_by: "embedded-unbound",
            temporal_scope: temporalScope,
          }
        : null,
    },
    profile_binding_status: "verified",
    profile_binding_temporal_scope: options.temporalScope ?? null,
  } as unknown as QuantityValue;
  if (options.includeBindingContext === false) {
    return value;
  }
  return {
    ...value,
    profile_binding_context: {
      status: "verified",
      lineageId: value.lineage.id,
      selectedArtifactRef,
      sourceRunId: "run-popover",
      origin: "reader_materialized",
      temporalScope: options.temporalScope ?? null,
      admissionGeneration: 1,
    },
  } as QuantityValue;
}

const temporalScope: TemporalRef = {
  valid_at: "2026-04-15T12:00:00Z",
  tx_at: "2026-04-16T09:20:00Z",
  branch: "main",
  snapshot_id: null,
  scenario_id: null,
};

function profileBatch(
  value: QuantityValue,
  options: {
    status: LineageGraphView["status"];
    temporal_scope: TemporalRef | null;
    trustMetadata?: NonNullable<LineageGraphView["trust_metadata"]>;
    response_origin?: "run_output_ref" | "reader_materialized";
  },
): LineageBatchResponsePayload {
  const selectedRef = value.lineage.artifact_ref;
  const sourceRunId = value.lineage.source_run_id;
  if (!selectedRef || !sourceRunId) {
    throw new Error("Profile batch fixture requires its selected ref and run");
  }
  const graph = lineageGraphFixture({
    lineageId: value.lineage.id,
    status: options.status,
    freshness: "current",
    selectedArtifactRef: selectedRef,
    profileBindingStatus: "verified",
    artifactRefProvenance: options.response_origin ?? "reader_materialized",
    sourceRunId,
    ...(options.trustMetadata === undefined
      ? {}
      : { trustMetadata: options.trustMetadata }),
  });
  return lineageBatchFixture({
    meta,
    responseTemporalScope: options.temporal_scope,
    lineages: [graph],
  });
}

function declaredTrustMetadata(
  temporal_scope: TemporalRef | null | undefined,
): NonNullable<LineageGraphView["trust_metadata"]> {
  return {
    hash: "sha256:selected-profile-lineage-fixture",
    verification_status: "verified",
    freshness: "current",
    dispute_status: "none",
    verified_by: "selected-profile-reader-fixture",
    verified_at: "2026-04-15T12:00:00Z",
    verification_method: "selected-profile-reader",
    temporal_scope,
  };
}
