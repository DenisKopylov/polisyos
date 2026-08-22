import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

vi.mock("@/shared/charts", () => ({
  UncertaintyBand: ({ identifiability }: { identifiability: string }) => (
    <div
      data-identifiability={identifiability}
      data-testid="decision-metric-uncertainty"
    />
  ),
}));

import DecisionCardView from "./DecisionCardView";

describe("DecisionCardView", () => {
  it("renders the producer identifiability member without inferring from warnings", () => {
    const view = renderWithProviders(
      <DecisionCardView
        artifactKind="scientist.decision_packet"
        payload={{
          feedback: { issues: [], verdict: "review" },
          metric_significance: {
            gdp_change: {
              effect_size: {
                identifiability: "assumed",
                point: 0.12,
              },
            },
          },
          simulation_results: { gdp_change: 0.12 },
          uncertainty_bounds: {
            gdp_change_ci_level: 0.95,
            gdp_change_lower: 0.1,
            gdp_change_upper: 0.14,
          },
        }}
      />,
    );

    expect(screen.getByTestId("decision-metric-uncertainty")).toHaveAttribute(
      "data-identifiability",
      "assumed",
    );

    view.unmount();
    renderWithProviders(
      <DecisionCardView
        artifactKind="scientist.decision_packet"
        payload={{
          feedback: { issues: [], verdict: "review" },
          metric_significance: {
            gdp_change: {
              assumption_warnings: ["unverified extension"],
              effect_size: {
                identifiability: "novel_owner_extension",
                point: 0.12,
              },
            },
          },
          simulation_results: { gdp_change: 0.12 },
          uncertainty_bounds: {
            gdp_change_lower: 0.1,
            gdp_change_upper: 0.14,
          },
        }}
      />,
    );
    expect(screen.getByTestId("decision-metric-uncertainty")).toHaveAttribute(
      "data-identifiability",
      "unknown",
    );
  });
});
