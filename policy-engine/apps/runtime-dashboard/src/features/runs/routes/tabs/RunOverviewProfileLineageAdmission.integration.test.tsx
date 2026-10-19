import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/render";
import {
  mockRuntimeGetSuccess,
  mockRuntimePostSuccess,
} from "@/test/runtimeApi";
import { TrustInspector } from "@/shared/ui/trust-view";
import {
  boundLineageQueryKey,
  profileBindingAdmissionQueryKey,
} from "@/shared/ui/quantity/useLineageBatch";
import type { LineageBatchSelector } from "@/shared/ui/quantity/quantity.types";

import { RunOverviewProfileLineage } from "./RunOverviewProfileLineage";

const runId = "run-profile-admission-integration";
const artifactId = `sha256:${"a".repeat(64)}`;
const selectedArtifactRef = {
  artifact_id: artifactId,
  kind: "core.decision_packet",
  media_type: "application/json",
  manifest_profile_sha256: `sha256:${"b".repeat(64)}`,
};
const temporalScope = {
  valid_at: "2026-04-15T12:00:00Z",
  tx_at: "2026-04-15T12:05:00Z",
  branch: "main",
  snapshot_id: null,
  scenario_id: null,
};
const lineageId = `artifact:${artifactId}`;
const selector: LineageBatchSelector = {
  lineageId,
  selectedArtifactRef,
  artifactRefProvenance: "reader_materialized",
  sourceRunId: runId,
};

afterEach(() => {
  vi.restoreAllMocks();
  window.history.replaceState(null, "", "/");
});

describe("run overview profile lineage admission", () => {
  it("uses one exact Inspector subject from both profile quantity openers", async () => {
    const user = userEvent.setup();
    window.history.replaceState(
      null,
      "",
      `/runs/${runId}/overview?trust=expanded`,
    );
    mockRuntimeGetSuccess(fabricDecisionDataPayload());
    const postSpy = mockRuntimePostSuccess(batchResponse());
    const { queryClient } = renderWithProviders(
      <>
        <RunOverviewProfileLineage runId={runId} />
        <TrustInspector />
      </>,
    );

    const row = await screen.findByTestId("overview-decision-quantity");
    await waitFor(() =>
      expect(row).toHaveAttribute("data-profile-binding-status", "verified"),
    );
    expect(within(row).getByRole("button", { name: "verified" })).toBeVisible();
    expect(within(row).getByRole("button", { name: /sha256:/ })).toBeVisible();
    expect(
      queryClient.getQueryData(
        boundLineageQueryKey(selector, runId, temporalScope),
      ),
    ).toMatchObject({ profileBindingGeneration: 1 });

    const statusButton = within(row).getByRole("button", {
      name: "verified",
    });
    await user.click(statusButton);
    expect(
      await screen.findByTestId("trust-inspector-profile-context"),
    ).toBeVisible();
    expect(
      screen.getByTestId("trust-inspector-selected-artifact-ref"),
    ).toHaveTextContent(selectedArtifactRef.manifest_profile_sha256);
    expect(
      screen.getByTestId("trust-inspector-profile-lineage"),
    ).toHaveTextContent(lineageId);
    expect(
      screen.getByTestId("trust-inspector-profile-origin"),
    ).toHaveTextContent("reader_materialized");
    expect(screen.getByTestId("trust-inspector-source-run")).toHaveTextContent(
      runId,
    );
    expect(
      screen.getByTestId("trust-inspector-profile-time"),
    ).toHaveTextContent(JSON.stringify(temporalScope));
    expect(
      screen.getByTestId("trust-inspector-follow-on-generic"),
    ).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Close" }));
    const hashButton = within(row).getByRole("button", { name: /sha256:/ });
    await user.click(hashButton);
    expect(
      await screen.findByTestId("trust-inspector-profile-context"),
    ).toBeVisible();
    expect(
      screen.getByTestId("trust-inspector-selected-artifact-ref"),
    ).toHaveTextContent(selectedArtifactRef.manifest_profile_sha256);
    expect(
      screen.getByTestId("trust-inspector-profile-lineage"),
    ).toHaveTextContent(lineageId);
    expect(
      screen.getByTestId("trust-inspector-profile-origin"),
    ).toHaveTextContent("reader_materialized");
    expect(screen.getByTestId("trust-inspector-source-run")).toHaveTextContent(
      runId,
    );
    expect(
      screen.getByTestId("trust-inspector-profile-time"),
    ).toHaveTextContent(JSON.stringify(temporalScope));
    expect(
      screen.getByTestId("trust-inspector-follow-on-generic"),
    ).toBeVisible();
    expect(postSpy).toHaveBeenCalledTimes(1);
  });

  it("restores trust only after matching profile revalidation and rejects mismatched tuple responses", async () => {
    const user = userEvent.setup();
    window.history.replaceState(
      null,
      "",
      `/runs/${runId}/overview?trust=expanded`,
    );
    mockRuntimeGetSuccess(fabricDecisionDataPayload());
    const postSpy = mockRuntimePostSuccess(batchResponse());
    const { queryClient } = renderWithProviders(
      <>
        <RunOverviewProfileLineage runId={runId} />
        <TrustInspector />
      </>,
    );

    const row = await screen.findByTestId("overview-decision-quantity");
    await waitFor(() =>
      expect(row).toHaveAttribute("data-profile-binding-status", "verified"),
    );
    const boundKey = boundLineageQueryKey(selector, runId, temporalScope);
    const cachedState = queryClient.getQueryState(boundKey);
    expect(cachedState?.dataUpdatedAt).toBeGreaterThan(0);
    expect(Date.now() - (cachedState?.dataUpdatedAt ?? 0)).toBeLessThan(30_000);

    postSpy.mockResolvedValueOnce({
      data: undefined,
      error: { message: "profile revalidation failed" },
      response: new Response('{"detail":"profile revalidation failed"}', {
        headers: { "Content-Type": "application/json" },
        status: 503,
      }),
    } as never);
    await queryClient.refetchQueries({
      queryKey: ["quantity-lineage-batch"],
    });

    await waitFor(() =>
      expect(row).toHaveAttribute(
        "data-profile-binding-status",
        "not_established",
      ),
    );
    expect(
      queryClient.getQueryData(
        profileBindingAdmissionQueryKey(selector, runId, temporalScope),
      ),
    ).toEqual({ generation: 2, outcome: "rejected" });
    expect(queryClient.getQueryData(boundKey)).toMatchObject({
      profileBindingGeneration: 1,
    });
    expect(screen.getByText("120")).toBeVisible();
    expect(within(row).getAllByRole("button")).toHaveLength(1);
    expect(
      within(row).queryByRole("button", { name: /sha256:/ }),
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId("trust-inspector-subject-id")).toBeNull();

    await user.click(within(row).getByRole("button", { name: /120/ }));
    expect(
      await screen.findByTestId("popover-profile-binding-status"),
    ).toHaveTextContent("Profile binding not established");
    expect(screen.getByText("120")).toBeVisible();
    expect(screen.queryByTestId("trust-verification-status")).toBeNull();
    expect(screen.queryByTestId("trust-inspector-subject-id")).toBeNull();
    expect(postSpy).toHaveBeenCalledTimes(2);

    const recoveredResponse = batchResponse();
    postSpy.mockResolvedValueOnce(runtimePostSuccess(recoveredResponse));
    await queryClient.refetchQueries({
      queryKey: ["quantity-lineage-batch"],
    });

    const admissionKey = profileBindingAdmissionQueryKey(
      selector,
      runId,
      temporalScope,
    );
    await waitFor(() =>
      expect(row).toHaveAttribute("data-profile-binding-status", "verified"),
    );
    expect(queryClient.getQueryData(admissionKey)).toMatchObject({
      generation: 3,
      outcome: "admitted",
      graph: { profileBindingGeneration: 3 },
    });
    expect(queryClient.getQueryData(boundKey)).toMatchObject({
      profileBindingGeneration: 3,
      lineage: {
        selected_artifact_ref: selectedArtifactRef,
        artifact_ref_provenance: "reader_materialized",
        source_run_id: runId,
      },
    });
    expect(
      await screen.findByTestId("trust-verification-status"),
    ).toHaveTextContent("verified");

    const statusButton = within(row).getByRole("button", {
      name: "verified",
    });
    await user.click(statusButton);
    expect(
      await screen.findByTestId("trust-inspector-profile-context"),
    ).toBeVisible();
    expect(
      within(screen.getByRole("dialog")).getByText("verified", {
        exact: true,
      }),
    ).toBeVisible();
    expect(
      screen.getByTestId("trust-inspector-selected-artifact-ref"),
    ).toHaveTextContent(selectedArtifactRef.manifest_profile_sha256);
    expect(
      screen.getByTestId("trust-inspector-profile-origin"),
    ).toHaveTextContent("reader_materialized");
    expect(screen.getByTestId("trust-inspector-source-run")).toHaveTextContent(
      runId,
    );
    expect(
      screen.getByTestId("trust-inspector-profile-time"),
    ).toHaveTextContent(JSON.stringify(temporalScope));
    await user.click(screen.getByRole("button", { name: "Close" }));

    for (const [index, mismatch] of (
      ["profile", "run", "origin", "time"] as const
    ).entries()) {
      const mismatchedResponse = mismatchedBatchResponse(mismatch);
      postSpy.mockResolvedValueOnce(runtimePostSuccess(mismatchedResponse));
      await queryClient.refetchQueries({
        queryKey: ["quantity-lineage-batch"],
      });

      const generation = index + 4;
      await waitFor(() => {
        expect(queryClient.getQueryData(admissionKey)).toMatchObject({
          generation,
          outcome: "rejected",
        });
        expect(row).toHaveAttribute(
          "data-profile-binding-status",
          "not_established",
        );
      });
      expect(queryClient.getQueryData(boundKey)).toMatchObject({
        profileBindingGeneration: 3,
      });
      expect(within(row).getByRole("button", { name: /120/ })).toBeVisible();
      expect(within(row).getAllByRole("button")).toHaveLength(1);
      expect(
        within(row).queryByRole("button", { name: /sha256:/ }),
      ).not.toBeInTheDocument();
      expect(screen.queryByTestId("trust-inspector-subject-id")).toBeNull();
      expect(screen.queryByTestId("trust-verification-status")).toBeNull();
      expect(postSpy).toHaveBeenCalledTimes(generation);
    }
  });
});

function fabricDecisionDataPayload() {
  return {
    meta: {
      generated_at: "2026-04-15T12:05:00Z",
      request_id: "run-profile-admission-integration",
      source_kinds: ["core_run"],
    },
    run_id: runId,
    source_kind: "core_run",
    temporal_scope: temporalScope,
    decision_data: [
      {
        id: "fabric_decision_data:decision_cost",
        kind: "quantity",
        value: {
          label: "Decision cost",
          metric_id: "decision_cost",
          point: 120,
          unit: { code: "[USD]", display: "USD", system: "ucum" },
        },
        source_contract: { id: "worldbank.wdi.generic", version: "1.1.0" },
        quality: { status: "passed", score: 1 },
        lineage: {
          id: lineageId,
          status: "pending",
          hash: "sha256:quantity-lineage",
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
}

function runtimePostSuccess(data: unknown) {
  return {
    data,
    error: undefined,
    response: new Response(JSON.stringify(data) ?? "null", {
      headers: { "Content-Type": "application/json" },
      status: 200,
    }),
  } as never;
}

function mismatchedBatchResponse(
  mismatch: "profile" | "run" | "origin" | "time",
) {
  const response = batchResponse();
  const lineage = response.lineages[0];
  if (!lineage) {
    throw new Error("The profile admission fixture must contain one lineage");
  }
  const mismatchedLineage = { ...lineage };
  if (mismatch === "profile") {
    mismatchedLineage.selected_artifact_ref = {
      ...selectedArtifactRef,
      manifest_profile_sha256: `sha256:${"c".repeat(64)}`,
    };
  } else if (mismatch === "run") {
    mismatchedLineage.source_run_id = "run-profile-admission-sibling";
  } else if (mismatch === "origin") {
    mismatchedLineage.artifact_ref_provenance = "run_output_ref";
  } else {
    mismatchedLineage.trust_metadata = {
      ...lineage.trust_metadata,
      temporal_scope: { ...temporalScope, branch: "other-branch" },
    };
  }
  return { ...response, lineages: [mismatchedLineage] };
}

function batchResponse() {
  return {
    meta: {
      generated_at: "2026-04-15T12:05:00Z",
      request_id: "run-profile-admission-integration-lineage",
      source_kinds: ["core_run"],
    },
    temporal_scope: temporalScope,
    lineages: [
      {
        id: lineageId,
        status: "verified",
        hash: "sha256:lineage-proof",
        freshness: "current",
        compact_summary: [],
        nodes: [],
        edges: [],
        root_artifact_refs: [],
        selected_artifact_ref: selectedArtifactRef,
        profile_binding_status: "verified",
        artifact_ref_provenance: "reader_materialized",
        source_run_id: runId,
        exports: {
          openlineage: `/api/v1/lineage/${encodeURIComponent(lineageId)}/export/openlineage`,
          prov: `/api/v1/lineage/${encodeURIComponent(lineageId)}/export/prov`,
        },
        metadata: {},
        trust_metadata: {
          hash: "sha256:lineage-proof",
          verification_status: "verified",
          freshness: "current",
          dispute_status: "none",
          verified_by: "canonical-profile-reader",
          verified_at: "2026-04-15T12:00:00Z",
          verification_method: "selected-profile-reader",
          temporal_scope: temporalScope,
        },
      },
    ],
    lineage_resolutions: [
      {
        requested_lineage_id: lineageId,
        resolved_lineage_id: lineageId,
      },
    ],
  };
}
