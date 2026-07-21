import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import { PathAnalysisPanel } from "./PathAnalysisPanel";

describe("PathAnalysisPanel", () => {
  it("preserves unknown effects instead of displaying a zero decomposition", () => {
    renderWithProviders(
      <PathAnalysisPanel
        edges={[]}
        nodes={[
          { id: "policy", kind: "treatment", label: "Policy" },
          { id: "outcome", kind: "outcome", label: "Outcome" },
        ]}
        onClose={vi.fn()}
        paths={[
          {
            edgeIds: ["policy-outcome"],
            id: "direct:policy-outcome",
            label: "Policy -> Outcome",
            nodeIds: ["policy", "outcome"],
            type: "direct",
          },
        ]}
      />,
    );

    expect(screen.queryByText("0.0000")).not.toBeInTheDocument();
    expect(screen.getAllByText("Unknown")).toHaveLength(3);
  });
});
