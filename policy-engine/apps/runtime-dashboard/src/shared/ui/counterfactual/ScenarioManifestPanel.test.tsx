import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import { ScenarioManifestPanel } from "./ScenarioManifestPanel";
import { scenario } from "./counterfactualTestData";

describe("ScenarioManifestPanel", () => {
  it("renders absent computed_at as unknown, never latest", () => {
    renderWithProviders(
      <ScenarioManifestPanel scenario={{ ...scenario, computed_at: null }} />,
    );

    expect(screen.getByText("Unknown", { selector: "dd" })).toBeInTheDocument();
    expect(screen.queryByText("latest")).not.toBeInTheDocument();
  });

  it("renders an invalid computed_at as unknown", () => {
    renderWithProviders(
      <ScenarioManifestPanel
        scenario={{ ...scenario, computed_at: "not-an-instant" }}
      />,
    );

    expect(screen.getByText("Unknown", { selector: "dd" })).toBeInTheDocument();
  });
});
