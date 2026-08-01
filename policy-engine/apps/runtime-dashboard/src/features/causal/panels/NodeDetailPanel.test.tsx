import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import { NodeDetailPanel } from "./NodeDetailPanel";

describe("NodeDetailPanel", () => {
  it("renders absent producer data availability as unknown", () => {
    renderWithProviders(
      <NodeDetailPanel
        edges={[]}
        node={{ id: "outcome", kind: "outcome", label: "Outcome" }}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("Unknown")).toBeInTheDocument();
    expect(screen.queryByText("Data available")).not.toBeInTheDocument();
  });
});
