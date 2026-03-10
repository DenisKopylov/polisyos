import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import LineageGraph from "./LineageGraph";

describe("LineageGraph", () => {
  it("renders the empty state when there are no nodes", () => {
    renderWithProviders(<LineageGraph nodes={[]} edges={[]} />);

    expect(screen.getByText("Lineage graph is empty.")).toBeInTheDocument();
  });

  it("renders the threshold fallback when the graph exceeds the configured size", () => {
    renderWithProviders(
      <LineageGraph
        nodes={Array.from({ length: 3 }, (_, index) => ({
          artifact_id: `artifact-${index}`,
          depth: index,
          status: "ok",
        }))}
        edges={[]}
        maxNodesForGraph={2}
      />,
    );

    expect(
      screen.getByText("Graph has 3 nodes, which is above render threshold (2)."),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "Narrow the lineage scope (`max_depth`/`max_nodes`) for interactive rendering.",
      ),
    ).toBeInTheDocument();
  });

  it("renders lineage cards and artifact inspection links", () => {
    renderWithProviders(
      <LineageGraph
        nodes={[
          {
            artifact_id: "artifact-root",
            depth: 0,
            kind: "decision_packet",
            status: "ok",
          },
          {
            artifact_id: "artifact-child",
            depth: 1,
            kind: "evidence_bundle",
            status: "error",
          },
        ]}
        edges={[
          {
            parent_artifact_id: "artifact-root",
            child_artifact_id: "artifact-child",
            role: "derived_from",
          },
        ]}
        rootArtifactIds={["artifact-root"]}
      />,
    );

    expect(screen.getByText("artifact-root")).toBeInTheDocument();
    expect(screen.getByText("artifact-child")).toBeInTheDocument();
    expect(screen.getByText("decision_packet")).toBeInTheDocument();
    expect(screen.getByText("evidence_bundle")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Inspect" })[0]).toHaveAttribute(
      "href",
      "/artifacts/artifact-root",
    );
  });
});
