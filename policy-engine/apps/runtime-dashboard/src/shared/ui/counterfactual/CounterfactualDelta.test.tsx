import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import { CounterfactualDelta } from "./CounterfactualDelta";
import { counterfactualMetric } from "./counterfactualTestData";

describe("CounterfactualDelta", () => {
  it("keeps an absent delta unknown without point collapse", () => {
    renderWithProviders(
      <CounterfactualDelta
        value={{ ...counterfactualMetric.delta, point: null }}
      />,
    );

    expect(screen.getByTestId("counterfactual-delta")).toHaveAttribute(
      "data-counterfactual-value-state",
      "unknown",
    );
    expect(screen.getByTestId("counterfactual-delta")).not.toHaveAttribute(
      "aria-label",
    );
  });
});
