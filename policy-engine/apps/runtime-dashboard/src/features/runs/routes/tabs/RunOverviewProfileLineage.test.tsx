import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { renderWithProviders } from "@/test/render";
import { TrustInspector } from "@/shared/ui/trust-view";
import {
  boundLineageQueryKey,
  profileBindingAdmissionQueryKey,
} from "@/shared/ui/quantity/useLineageBatch";
import type {
  LineageBatchResponsePayload,
  LineageGraphView,
  QuantityValue,
  SelectedArtifactRef,
  TemporalRef,
} from "@/shared/ui/quantity/quantity.types";

const mocks = vi.hoisted(() => ({
  useRunFabricDecisionData: vi.fn(),
  useLineageBatch: vi.fn(),
}));

vi.mock("@/api/hooks/useRunFabricDecisionData", () => ({
  useRunFabricDecisionData: mocks.useRunFabricDecisionData,
}));
vi.mock("@/shared/ui/quantity/useLineageBatch", async (importOriginal) => {
  const actual =
    await importOriginal<
      typeof import("@/shared/ui/quantity/useLineageBatch")
    >();
  return { ...actual, useLineageBatch: mocks.useLineageBatch };
});

import { RunOverviewProfileLineage } from "./RunOverviewProfileLineage";

const runId = "run-profile-lineage";
const temporalScope: TemporalRef = {
  valid_at: "2026-04-15T12:00:00Z",
  tx_at: "2026-04-15T12:05:00Z",
  branch: "main",
  snapshot_id: null,
  scenario_id: null,
};
const artifactId = `sha256:${"a".repeat(64)}`;
const selectedRef: SelectedArtifactRef = {
  artifact_id: artifactId,
  kind: "core.decision_packet",
  media_type: "application/json",
  manifest_profile_sha256: `sha256:${"b".repeat(64)}`,
};
const quantity = {
  label: "Decision cost",
  metric_id: "decision_cost",
  point: 120,
  unit: { code: "[USD]", display: "USD", system: "ucum" },
  quantity_class: "decision",
  lineage: {
    id: `artifact:${artifactId}`,
    status: "pending",
    freshness: "unknown",
    artifact_ref: selectedRef,
    artifact_ref_provenance: "reader_materialized",
    source_run_id: runId,
    trust_metadata: null,
  },
} as unknown as QuantityValue;

const verifiedBy = "CanonicalProfileReader@1";
const trustScope = { ...temporalScope };

afterEach(() => {
  vi.clearAllMocks();
  window.history.replaceState(null, "", "/");
});

describe("RunOverviewProfileLineage", () => {
  it("feeds exact run/profile/time lineage into the displayed quantity and TrustInspector", async () => {
    const user = userEvent.setup();
    const graph = profileGraph(selectedRef);
    configureQueries(graph);
    window.history.replaceState(
      null,
      "",
      `/runs/${runId}/overview?trust=expanded`,
    );

    const { queryClient } = renderWithProviders(
      <>
        <RunOverviewProfileLineage runId={runId} />
        <TrustInspector />
      </>,
    );
    seedBoundAdmission(queryClient, graph);

    const quantityRow = await screen.findByTestId("overview-decision-quantity");
    expect(quantityRow).toBeVisible();
    expect(quantityRow).toHaveAttribute(
      "data-profile-binding-status",
      "verified",
    );
    expect(
      within(quantityRow).getByRole("button", { name: /120/ }),
    ).toHaveAttribute("data-lineage-status", "pending");
    const statusButton = within(quantityRow).getByRole("button", {
      name: "verified",
    });
    await user.click(statusButton);
    expect(await screen.findByRole("dialog")).toHaveTextContent(verifiedBy);
    expect(screen.getByRole("dialog")).toHaveTextContent(
      "selected-profile-reader",
    );
    expect(screen.getByTestId("trust-inspector-subject-id")).toHaveTextContent(
      `artifact:${artifactId}`,
    );
    expect(
      screen.getByTestId("trust-inspector-profile-lineage"),
    ).toHaveTextContent(`artifact:${artifactId}`);
    expect(
      screen.getByTestId("trust-inspector-selected-artifact-ref"),
    ).toHaveTextContent(selectedRef.manifest_profile_sha256);
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
    const hashButton = within(quantityRow).getByRole("button", {
      name: /sha256:/,
    });
    await user.click(hashButton);
    expect(await screen.findByRole("dialog")).toHaveTextContent(verifiedBy);
    expect(
      screen.getByTestId("trust-inspector-selected-artifact-ref"),
    ).toHaveTextContent(selectedRef.manifest_profile_sha256);
    expect(
      screen.getByTestId("trust-inspector-profile-origin"),
    ).toHaveTextContent("reader_materialized");
    expect(screen.getByTestId("trust-inspector-source-run")).toHaveTextContent(
      runId,
    );
    expect(
      screen.getByTestId("trust-inspector-profile-time"),
    ).toHaveTextContent(JSON.stringify(temporalScope));

    expect(mocks.useLineageBatch).toHaveBeenCalledWith(
      [
        {
          lineageId: `artifact:${artifactId}`,
          selectedArtifactRef: selectedRef,
          artifactRefProvenance: "reader_materialized",
          sourceRunId: runId,
        },
      ],
      { enabled: true, runId, temporalScope },
    );
  });

  it("suppresses cached bound trust when the current batch query is rejected", async () => {
    configureQueries(profileGraph(selectedRef));
    mocks.useLineageBatch.mockReturnValue({
      data: batchResponse(profileGraph(selectedRef)),
      error: new Error("profile binding refused"),
      isError: true,
      isLoading: false,
    });
    window.history.replaceState(
      null,
      "",
      `/runs/${runId}/overview?trust=expanded`,
    );

    renderWithProviders(
      <>
        <RunOverviewProfileLineage runId={runId} />
        <TrustInspector />
      </>,
    );

    const quantityRow = await screen.findByTestId("overview-decision-quantity");
    expect(quantityRow).toHaveAttribute(
      "data-profile-binding-status",
      "not_established",
    );
    expect(
      within(quantityRow).getByRole("button", { name: /120/ }),
    ).toHaveAttribute("data-lineage-status", "pending");
    expect(
      within(quantityRow).getByRole("button", { name: /120/ }),
    ).toBeVisible();
    expect(within(quantityRow).getAllByRole("button")).toHaveLength(1);
    expect(
      within(quantityRow).queryByRole("button", { name: /sha256:/ }),
    ).not.toBeInTheDocument();
  });

  it("shows a visible primary-envelope error instead of dropping a malformed profile as absent", async () => {
    mocks.useRunFabricDecisionData.mockReturnValue({
      data: undefined,
      error: new Error("invalid selected profile"),
      isError: true,
      isLoading: false,
    });
    mocks.useLineageBatch.mockReturnValue({
      data: undefined,
      isError: false,
      isLoading: false,
    });

    renderWithProviders(<RunOverviewProfileLineage runId={runId} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Decision quantities could not be loaded.",
    );
    expect(
      screen.queryByTestId("overview-decision-quantity"),
    ).not.toBeInTheDocument();
    expect(screen.queryByTestId("profile-binding-status")).toBeNull();
  });

  it("keeps source lineage status separate when the profile binding is not established", async () => {
    const unprofiledQuantity = {
      ...quantity,
      lineage: {
        ...quantity.lineage,
        status: "verified",
        artifact_ref: null,
        artifact_ref_provenance: null,
        source_run_id: runId,
        trust_metadata: {
          verification_status: "verified",
          freshness: "current",
          dispute_status: "none",
          verified_by: "embedded-but-unbound",
          temporal_scope: trustScope,
        },
      },
    } as unknown as QuantityValue;
    mocks.useRunFabricDecisionData.mockReturnValue({
      data: {
        run_id: runId,
        temporal_scope: temporalScope,
        quantities: [unprofiledQuantity],
      },
      isError: false,
      isLoading: false,
    });
    mocks.useLineageBatch.mockReturnValue({
      data: batchResponse(unestablishedGraph(unprofiledQuantity.lineage.id)),
      isError: false,
      isLoading: false,
    });
    window.history.replaceState(
      null,
      "",
      `/runs/${runId}/overview?trust=expanded`,
    );

    renderWithProviders(
      <>
        <RunOverviewProfileLineage runId={runId} />
        <TrustInspector />
      </>,
    );

    const quantityRow = await screen.findByTestId("overview-decision-quantity");
    expect(quantityRow).toHaveAttribute(
      "data-profile-binding-status",
      "not_established",
    );
    expect(
      within(quantityRow).getByRole("button", { name: /120/ }),
    ).toHaveAttribute("data-lineage-status", "verified");
    expect(
      within(quantityRow).getByRole("button", { name: /120/ }),
    ).toBeVisible();
    expect(screen.getByTestId("profile-binding-status")).toHaveTextContent(
      "Profile binding not established",
    );
    expect(within(quantityRow).getAllByRole("button")).toHaveLength(1);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("keeps quantity values visible but withholds trust when the batch returns a sibling profile", async () => {
    const siblingRef = {
      ...selectedRef,
      manifest_profile_sha256: `sha256:${"c".repeat(64)}`,
    };
    configureQueries(profileGraph(siblingRef));
    window.history.replaceState(
      null,
      "",
      `/runs/${runId}/overview?trust=expanded`,
    );

    renderWithProviders(
      <>
        <RunOverviewProfileLineage runId={runId} />
        <TrustInspector />
      </>,
    );

    const quantityRow = await screen.findByTestId("overview-decision-quantity");
    expect(quantityRow).toBeVisible();
    expect(quantityRow).toHaveAttribute(
      "data-profile-binding-status",
      "not_established",
    );
    expect(
      within(quantityRow).getByRole("button", { name: /120/ }),
    ).toHaveAttribute("data-lineage-status", "pending");
    expect(
      within(quantityRow).getByRole("button", { name: /120/ }),
    ).toBeVisible();
    expect(screen.getByTestId("profile-binding-status")).toHaveTextContent(
      "Profile binding not established",
    );
    expect(within(quantityRow).getAllByRole("button")).toHaveLength(1);
    expect(
      within(quantityRow).queryByRole("button", { name: /sha256:/ }),
    ).not.toBeInTheDocument();
    expect(screen.getByText(/Lineage details are unavailable/)).toBeVisible();
  });
});

function configureQueries(graph: LineageGraphView) {
  mocks.useRunFabricDecisionData.mockReturnValue({
    data: {
      run_id: runId,
      temporal_scope: temporalScope,
      quantities: [quantity],
    },
    isError: false,
    isLoading: false,
  });
  mocks.useLineageBatch.mockReturnValue({
    data: batchResponse(graph),
    isError: false,
    isLoading: false,
  });
}

function profileGraph(ref: SelectedArtifactRef): LineageGraphView {
  return {
    id: `artifact:${artifactId}`,
    status: "verified",
    freshness: "current",
    selected_artifact_ref: ref,
    profile_binding_status: "verified",
    artifact_ref_provenance: "reader_materialized",
    source_run_id: runId,
    trust_metadata: {
      verification_status: "verified",
      freshness: "current",
      dispute_status: "none",
      verified_by: verifiedBy,
      verified_at: "2026-04-15T12:00:00Z",
      verification_method: "selected-profile-reader",
      temporal_scope: trustScope,
    },
    nodes: [],
    edges: [],
  } as unknown as LineageGraphView;
}

function batchResponse(graph: LineageGraphView): LineageBatchResponsePayload {
  return {
    meta: {
      generated_at: "2026-04-15T12:05:00Z",
      request_id: "run-profile-lineage-test",
      source_kinds: ["core_run"],
    },
    temporal_scope: temporalScope,
    lineages: [graph],
    lineage_resolutions: [
      {
        requested_lineage_id: graph.id,
        resolved_lineage_id: graph.id,
      },
    ],
  } as unknown as LineageBatchResponsePayload;
}

function seedBoundAdmission(
  queryClient: ReturnType<typeof renderWithProviders>["queryClient"],
  graph: LineageGraphView,
) {
  const selector = {
    lineageId: graph.id,
    selectedArtifactRef: graph.selected_artifact_ref ?? null,
    artifactRefProvenance: graph.artifact_ref_provenance ?? null,
    sourceRunId: graph.source_run_id ?? null,
  };
  const generation = 1;
  queryClient.setQueryData(
    profileBindingAdmissionQueryKey(selector, runId, temporalScope),
    {
      generation,
      outcome: "admitted",
      graph: {
        lineage: graph,
        temporal_scope: temporalScope,
        profileBindingGeneration: generation,
      },
    },
  );
  queryClient.setQueryData(
    boundLineageQueryKey(selector, runId, temporalScope),
    {
      lineage: graph,
      temporal_scope: temporalScope,
      profileBindingGeneration: generation,
    },
  );
}

function unestablishedGraph(lineageId: string): LineageGraphView {
  return {
    id: lineageId,
    status: "verified",
    freshness: "current",
    selected_artifact_ref: null,
    profile_binding_status: "not_established",
    artifact_ref_provenance: null,
    source_run_id: null,
    trust_metadata: null,
    nodes: [],
    edges: [],
  } as unknown as LineageGraphView;
}
