import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { mockRuntimeGetSuccess } from "@/test/runtimeApi";
import { renderWithProviders } from "@/test/render";

import { ProvenancePopover } from "./ProvenancePopover";
import type { LineageGraphView, QuantityValue } from "./quantity.types";

const meta = {
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
  uncertainty: { ci_95: [0.15, 0.31] },
  time: {
    valid_at: "2026-04-15T12:00:00Z",
    tx_at: "2026-04-16T09:20:00Z",
  },
  quantity_class: "decision",
  label: "Effect size",
};

const lineage: LineageGraphView = {
  id: "artifact:sha256:fixture",
  status: "verified",
  freshness: "current",
  compact_summary: [
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
  exports: {
    openlineage: "/api/v1/lineage/artifact:sha256:fixture/export/openlineage",
    prov: "/api/v1/lineage/artifact:sha256:fixture/export/prov",
  },
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("ProvenancePopover", () => {
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
});
