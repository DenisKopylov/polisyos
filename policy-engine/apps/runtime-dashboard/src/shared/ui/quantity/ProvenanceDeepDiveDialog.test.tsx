import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import { ProvenanceDeepDiveDialog } from "./ProvenanceDeepDiveDialog";
import type { LineageGraphView, QuantityValue } from "./quantity.types";

const quantity: QuantityValue = {
  point: 0.23,
  unit: { code: "1", system: "ucum", display: "ratio" },
  metric_id: "effect_size",
  lineage: {
    id: "artifact:sha256:fixture",
    status: "verified",
    freshness: "current",
  },
  quantity_class: "decision",
  label: "Effect size",
};

const lineage: LineageGraphView = {
  id: "artifact:sha256:fixture",
  status: "verified",
  freshness: "current",
  hash: "sha256:abc",
  compact_summary: [],
  nodes: [
    {
      id: "artifact:sha256:source",
      kind: "dataset",
      label: "QES 2024 Q3",
      timestamp: "2026-04-15T12:00:00Z",
    },
  ],
  edges: [],
  exports: {
    openlineage: "/api/v1/lineage/artifact:sha256:fixture/export/openlineage",
    prov: "/api/v1/lineage/artifact:sha256:fixture/export/prov",
  },
};

describe("ProvenanceDeepDiveDialog", () => {
  it("renders full graph, raw source links, and temporal export links", () => {
    renderWithProviders(
      <ProvenanceDeepDiveDialog
        open
        onOpenChange={() => undefined}
        quantity={quantity}
        lineage={lineage}
        temporalScope={{ valid_at: "2026-04-15T12:00:00Z" }}
      />,
    );

    expect(screen.getByText("Provenance deep dive")).toBeInTheDocument();
    expect(screen.getAllByText("QES 2024 Q3")).toHaveLength(2);
    expect(screen.getByRole("link", { name: /QES 2024 Q3/i })).toHaveAttribute(
      "href",
      "/artifacts/sha256:source",
    );
    expect(screen.getByRole("link", { name: /OpenLineage/i })).toHaveAttribute(
      "href",
      "/api/v1/lineage/artifact:sha256:fixture/export/openlineage?valid_at=2026-04-15T12%3A00%3A00.000Z",
    );
  });
});
