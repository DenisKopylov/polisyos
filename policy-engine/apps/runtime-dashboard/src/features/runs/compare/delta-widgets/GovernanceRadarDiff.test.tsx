import { screen } from "@testing-library/react";

import { renderWithProviders } from "@/test/render";

import type { DeltaQuantity } from "../compare-types";
import { policyDiffFixture } from "../fixtures";
import { GovernanceRadarDiff } from "./GovernanceRadarDiff";

function deltaWithSignificance(significance: string): DeltaQuantity {
  const fixtureDelta = policyDiffFixture.deltas?.[0];
  if (!fixtureDelta) {
    throw new TypeError("policy diff fixture requires a governance delta");
  }
  return {
    ...(fixtureDelta as DeltaQuantity),
    significance: significance as DeltaQuantity["significance"],
    lineage_delta: { ...fixtureDelta.lineage_delta },
  };
}

function presentationAttributes(panel: HTMLElement) {
  return [panel, ...panel.querySelectorAll<HTMLElement>("*")].map(
    (element) => ({
      className: element.getAttribute("class"),
      style: element.getAttribute("style"),
      tagName: element.tagName,
    }),
  );
}

describe("GovernanceRadarDiff", () => {
  it("preserves a novel producer significance label without synthesized governance percentages", () => {
    renderWithProviders(
      <GovernanceRadarDiff
        deltas={[deltaWithSignificance("future_owner_significance")]}
      />,
    );

    expect(screen.getByTestId("governance-significance")).toHaveTextContent(
      "future_owner_significance",
    );
    expect(screen.getByTestId("governance-radar-diff")).not.toHaveTextContent(
      "%",
    );
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("changing significance does not change numeric posture or authority color", () => {
    const { rerender } = renderWithProviders(
      <GovernanceRadarDiff deltas={[deltaWithSignificance("uncertain")]} />,
    );
    const initial = screen.getByTestId("governance-significance");
    const panel = screen.getByTestId("governance-radar-diff");
    const initialPresentation = presentationAttributes(panel);

    expect(initial).toHaveClass("text-muted");
    expect(panel).not.toHaveTextContent("%");
    expect(JSON.stringify(initialPresentation)).not.toMatch(/color-status/iu);

    rerender(
      <GovernanceRadarDiff deltas={[deltaWithSignificance("worsened")]} />,
    );

    const changed = screen.getByTestId("governance-significance");
    expect(changed).toHaveTextContent("worsened");
    expect(
      presentationAttributes(screen.getByTestId("governance-radar-diff")),
    ).toEqual(initialPresentation);
    expect(
      JSON.stringify(
        presentationAttributes(screen.getByTestId("governance-radar-diff")),
      ),
    ).not.toMatch(/color-status/iu);
    expect(screen.getByTestId("governance-radar-diff")).not.toHaveTextContent(
      "%",
    );
  });
});
