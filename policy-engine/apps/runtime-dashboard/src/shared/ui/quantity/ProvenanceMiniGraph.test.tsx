import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import { summarizeLineageGraph } from "./lineage-summary";
import { ProvenanceMiniGraph } from "./ProvenanceMiniGraph";
import type { LineageGraphView } from "./quantity.types";

const lineage: LineageGraphView = {
  id: "lin_fixture",
  status: "verified",
  freshness: "current",
  compact_summary: [
    { kind: "source", label: "Source A", id: "s1" },
    { kind: "source", label: "Source B", id: "s2" },
    { kind: "transform", label: "Normalize", id: "t1" },
    { kind: "transform", label: "Winsorize", id: "t2" },
    { kind: "model", label: "DoubleML", id: "m1" },
    { kind: "agent", label: "Formalizer", id: "a1" },
    { kind: "result", label: "Effect size", id: "r1" },
  ],
  nodes: [],
  edges: [],
  exports: { openlineage: "", prov: "" },
};

describe("ProvenanceMiniGraph", () => {
  it("summarizes hidden nodes by kind and stays within the visible-node budget", () => {
    const summary = summarizeLineageGraph(lineage, { maxVisibleNodes: 7 });

    expect(summary.nodes).toHaveLength(5);
    expect(summary.hiddenByKind.source).toBe(1);
    expect(summary.hiddenByKind.transform).toBe(1);
    expect(summary.hiddenTotal).toBe(2);
  });

  it("renders a compact graph", () => {
    renderWithProviders(<ProvenanceMiniGraph lineage={lineage} />);

    expect(screen.getByText("Source A")).toBeInTheDocument();
    expect(screen.getByText("DoubleML")).toBeInTheDocument();
    expect(screen.getByText("+1 Source")).toBeInTheDocument();
    expect(screen.getByText("+1 Transform")).toBeInTheDocument();
  });
});
